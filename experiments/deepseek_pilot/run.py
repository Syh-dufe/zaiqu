"""Event-triggered DeepSeek rule generation with a frozen official HAPPO."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
from rules import compile_rule, rule_delta, manual_delta, bounded_order, parse_expression

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / "external/liu-inventory"
TRAINING = ROOT / "results/learning_curve/curve_seed11_until_stable_v1"
REVISION = "a7e5a3e83e21565a5799483bc534e39635ec65dd"
SYSTEM = """Design an interpretable emergency replenishment correction rule for a frozen HAPPO policy.
There are 3 serial inventory nodes, agent 0 downstream dispensing point, 1 regional warehouse, 2 upstream supply center.
Lead time=4 periods; actions are integer orders 0..20; costs inventory+backlog equally weighted at each node. Initial stocks and pipeline are fixed by simulator.
You see only current inventories/backlogs/pipelines, observed historical demand and current HAPPO proposed orders. Future demand and event timing are unknown.
Return a JSON object with explanation and rules (1 to 4 entries). Each entry has EXACTLY when and delta, both expression strings <=300 characters.
Rules are checked in order for EACH node; the FIRST matching rule supplies that node's delta, no match means 0.
Allowed features: agent, inventory, backlog, pipeline (sum of in-transit units), arrival (next arrival), incoming (last observed local demand), recent (external last5 demand mean), baseline (external preceding20 mean), growth (recent/baseline), happo (current proposed order).
Expressions may use numeric constants, + - * /, comparisons, and/or/not, conditional expressions, min/max (2..6 args), abs (1 arg). No other names, imports, methods, containers or functions.
delta is clipped to [-6,6], rounded to integer and added to happo, final order clipped to [0,20]. The rule runs for the remaining episode on fresh causal features.
Aim to reduce downstream backlog while avoiding redundant orders when the pipeline is already sufficient and avoiding persistent over-ordering after demand subsides.
Give a concise explanation of the generated mechanics. Do not include markdown or Python code. Example format: {"explanation":"mechanics", "rules":[{"when":"backlog > 5", "delta":"min(6,max(0,backlog / 4))"}]}.
"""


def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name",default="deepseek_flash_5cases_v1")
    options=parser.parse_args()
    if not options.run_name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in options.run_name):
        parser.error("invalid run name")
    target=ROOT/"results/deepseek_pilot"/options.run_name
    if target.exists(): parser.error("existing result directory refused")
    key=os.environ.get("DEEPSEEK_API_KEY")
    if not key: parser.error("DEEPSEEK_API_KEY missing from process environment")
    revision=subprocess.check_output(["git","rev-parse","HEAD"],cwd=UPSTREAM,text=True).strip()
    dirty=subprocess.check_output(["git","status","--porcelain","--untracked-files=no"],cwd=UPSTREAM,text=True)
    if revision!=REVISION or dirty.strip(): parser.error("official checkout changed")
    # Experimental verification of expression and action constraints.
    valid=compile_rule({"rules":[{"when":"backlog > 5", "delta":"min(6,backlog / 4)"}]})
    assert rule_delta(valid,{"backlog":8})==2 and bounded_order(19,6)==20 and bounded_order(1,-6)==0
    try: parse_expression("inventory.__class__")
    except ValueError: pass
    else: raise AssertionError("attribute access must be rejected")
    target.mkdir(parents=True)
    sys.path.insert(0,str(UPSTREAM)); os.chdir(UPSTREAM)
    import numpy as np
    import torch
    from envs import generator
    from envs.env_wrappers import DummyVecEnv
    from runners.separated.runner import CRunner
    torch.set_num_threads(1); torch.manual_seed(11); np.random.seed(20261005)
    base=[generator.merton(200,20).demand_list for _ in range(5)]
    event_rng=random.Random(20261006)
    events=[{"start_index":event_rng.randint(60,100),"duration":event_rng.randint(20,40),"factor":1.5} for _ in range(5)]
    shock=[[min(20,math.ceil(d*e["factor"])) if e["start_index"]<=i<e["start_index"]+e["duration"] else d
            for i,d in enumerate(t)] for t,e in zip(base,events)]
    for e,a,b in zip(events,base,shock):
        s=e["start_index"]; end=s+e["duration"]
        assert a[:s]==b[:s] and a[end:]==b[end:]
        e["actual_ratio"]=sum(b[s:end])/max(sum(a[s:end]),1)
    write_json(target/"demands.json",{"demand_seed":20261005,"event_seed":20261006,"events":events,"base":base,"shock":shock})
    write_json(target/"protocol.json",{"model":"deepseek-flash","thinking":"disabled","temperature":0.2,"max_tokens":1500,
        "timeout_seconds":30,"max_calls":10,"retry_count":0,"system_prompt":SYSTEM,
        "trigger":"last5 > 1.3*preceding20, consecutive 2, min history25",
        "latency":"simulation pauses during request; latency measured separately",
        "manual_rule":"if recent>1.3*baseline or backlog>5: ceil(min(6,max(0,(4*max(incoming,recent)+backlog-inventory-pipeline)/4))) else 0"})
    calls=[]; runtime_failures=[]; episodes=[]; all_rows=[]; hash_checks={}
    config=json.loads((TRAINING/"config.json").read_text())["config"]
    training=json.loads((TRAINING/"completed.json").read_text())
    audit=json.loads((TRAINING/"completion_audit.json").read_text())
    model_dir=Path(training["final_model_directory"]).parent/"models"

    def model_hash(policies):
        digest=hashlib.sha256()
        for policy in policies:
            for network in (policy.actor,policy.critic):
                for name,tensor in network.state_dict().items():
                    digest.update(name.encode()); digest.update(tensor.detach().cpu().numpy().tobytes())
        return digest.hexdigest()

    def generate_rule(context):
        assert len(calls)<10
        body={"model":"deepseek-flash","messages":[{"role":"system","content":SYSTEM},
            {"role":"user","content":json.dumps(context)}],"response_format":{"type":"json_object"},
            "thinking":{"type":"disabled"},"temperature":0.2,"max_tokens":1500}
        record={"index":len(calls),"request":body,"started_unix":time.time(),"status":"started"}
        calls.append(record); write_json(target/"calls.json",calls)
        clock=time.perf_counter(); compiled=None
        try:
            request=urllib.request.Request("https://api.deepseek.com/chat/completions",data=json.dumps(body).encode(),
                headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
            with urllib.request.urlopen(request,timeout=30) as response:
                data=json.load(response)
            record["response"]=data
            choice=data["choices"][0]
            if choice.get("finish_reason")!="stop": raise ValueError("incomplete model output")
            rule=json.loads(choice["message"]["content"])
            compiled=compile_rule(rule); record["rule"]=rule; record["status"]="valid"
        except urllib.error.HTTPError as exc:
            record["status"]="failed"; record["failure"]="HTTP_"+str(exc.code)
        except Exception as exc:
            record["status"]="failed"; record["failure"]=type(exc).__name__
        record["seconds"]=time.perf_counter()-clock
        write_json(target/"calls.json",calls)
        print("API",record["index"],record["status"],round(record["seconds"],2),flush=True)
        return compiled

    class Controller(DummyVecEnv):
        def reset(self):
            self.trace=self.env_list[0].eval_index
            self.history=[]; self.order_history=[]; self.consecutive=0; self.trigger=None; self.compiled=None; self.rule_failed=False
            return super().reset()

        def step(self,actions):
            env=self.env_list[0]; proposed=[int(np.argmax(a)) for a in actions[0]]
            recent=float(np.mean(self.history[-5:])) if self.history else 0.0
            baseline=float(np.mean(self.history[-25:-5])) if len(self.history)>=25 else recent
            is_alarm=len(self.history)>=25 and recent>1.3*baseline
            self.consecutive=self.consecutive+1 if is_alarm else 0
            features=[]
            for node in range(3):
                incoming=self.history[-1] if node==0 and self.history else (self.order_history[-1][node-1] if node>0 and self.order_history else 0)
                features.append({"agent":node,"inventory":int(env.inventory[node]),"backlog":int(env.backlog[node]),
                    "pipeline":int(sum(env.order[node])),"arrival":int(env.order[node][0]),"incoming":int(incoming),
                    "recent":recent,"baseline":baseline,"growth":recent/max(baseline,1e-8),"happo":proposed[node]})
            if self.trigger is None and self.consecutive>=2:
                self.trigger=env.step_num+1
                if self.group=="deepseek":
                    self.compiled=generate_rule({"observed_periods":env.step_num,"observed_last25_demands":self.history[-25:],"nodes":features})
            actual=proposed.copy()
            if self.trigger is not None and self.group!="happo" and not self.rule_failed:
                try:
                    if self.group=="manual": actual=[bounded_order(a,manual_delta(f)) for a,f in zip(proposed,features)]
                    elif self.compiled is not None: actual=[bounded_order(a,rule_delta(self.compiled,f)) for a,f in zip(proposed,features)]
                except Exception as exc:
                    self.rule_failed=True
                    runtime_failures.append({"group":self.group,"scenario":self.scenario,"trace":self.trace,
                        "period":env.step_num+1,"failure":type(exc).__name__})
                    actual=proposed.copy()
            output=super().step([[np.eye(21)[a] for a in actual]])
            demand=int(env.get_demand()[0]); self.history.append(demand); self.order_history.append(actual.copy())
            for node in range(3):
                self.rows.append({"group":self.group,"scenario":self.scenario,"trace":self.trace,"period":env.step_num,"node":node,
                    "demand":demand,"cost":-float(output[1][0,node,0]),"inventory":int(env.inventory[node]),"backlog":int(env.backlog[node]),
                    "happo_order":proposed[node],"actual_order":actual[node],"trigger_period":self.trigger})
            if env.step_num==200:
                episodes.append({"group":self.group,"scenario":self.scenario,"trace":self.trace,"trigger_period":self.trigger,
                    "runtime_rule_failed":self.rule_failed})
                print("EPISODE",self.group,self.scenario,self.trace,"trigger",self.trigger,flush=True)
            return output

    for group in ("happo","manual","deepseek"):
        args=argparse.Namespace(**config); args.model_dir=str(model_dir)
        envs=Controller(args)
        runner=CRunner({"all_args":args,"envs":envs,"eval_envs":envs,"num_agents":3,"device":torch.device("cpu"),"run_dir":target/group})
        before=model_hash(runner.policy); assert before==audit["model_matches"]["official_best"]["sha256"]
        for scenario,demands in (("base",base),("shock",shock)):
            env=envs.env_list[0]; env.eval_data=demands; env.n_eval=5; env.eval_index=0; env.record_act_sta=[[] for _ in range(3)]
            envs.group=group; envs.scenario=scenario; envs.rows=[]
            reward,_=runner.eval()
            assert len(envs.rows)==3000 and math.isclose(-float(reward),float(np.mean([r["cost"] for r in envs.rows])),abs_tol=1e-9)
            all_rows.extend(envs.rows)
            with (target/"periods.csv").open("w",newline="",encoding="utf-8") as stream:
                writer=csv.DictWriter(stream,fieldnames=list(all_rows[0])); writer.writeheader();writer.writerows(all_rows)
            write_json(target/"episodes.json",episodes);write_json(target/"runtime_failures.json",runtime_failures)
        after=model_hash(runner.policy); assert before==after
        hash_checks[group]={"before":before,"after":after,"unchanged":True}
        runner.writter.close();envs.close()
    assert len(all_rows)==18000 and len(episodes)==30
    for scenario in ("base","shock"):
        for trace in range(5):
            ep=[e for e in episodes if e["scenario"]==scenario and e["trace"]==trace]
            assert len({e["trigger_period"] for e in ep})==1
            trigger=ep[0]["trigger_period"] or 201
            reference=[(r["cost"],r["actual_order"]) for r in all_rows if r["group"]=="happo" and r["scenario"]==scenario and r["trace"]==trace and r["period"]<trigger]
            for group in ("manual","deepseek"):
                assert reference==[(r["cost"],r["actual_order"]) for r in all_rows if r["group"]==group and r["scenario"]==scenario and r["trace"]==trace and r["period"]<trigger]
    write_json(target/"completed.json",{"rows":len(all_rows),"episodes":len(episodes),"parameter_checks":hash_checks,
        "training_updates":0,"calls":len(calls),"valid_calls":sum(c["status"]=="valid" for c in calls),
        "failed_calls":sum(c["status"]!="valid" for c in calls),"runtime_failures":runtime_failures,
        "official_revision":revision,"causal_checks":"same demand-only trigger across all groups; all pre-trigger costs and actions identical",
        "limitations":"5 development traces, single HAPPO seed, one generation per triggered episode. Simulator pauses during API. Central shared rule features add coordination beyond dispersed actors."})
    print("DEEPSEEK_PILOT_COMPLETED",flush=True)


if __name__=="__main__": main()
