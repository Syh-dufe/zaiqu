"""Audit all pilot episodes, including false alarms and unfavourable outcomes."""
import argparse
import csv
import json
import statistics
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    p=parser.parse_args().directory
    rows=list(csv.DictReader((p/"periods.csv").open()))
    episodes=json.loads((p/"episodes.json").read_text())
    demands=json.loads((p/"demands.json").read_text())
    calls=json.loads((p/"calls.json").read_text())
    completed=json.loads((p/"completed.json").read_text())
    assert len(rows)==18000 and len(episodes)==30
    assert all(v["unchanged"] for v in completed["parameter_checks"].values())
    assert all(0<=int(r["actual_order"])<=20 and abs(int(r["actual_order"])-int(r["happo_order"]))<=6 for r in rows)
    metrics=[]; summary={}; recovery=[]
    for group in ("happo","manual","deepseek"):
        summary[group]={}
        for scenario in ("base","shock"):
            selected=[]
            for trace in range(5):
                local=[r for r in rows if r["group"]==group and r["scenario"]==scenario and int(r["trace"])==trace]
                downstream=[r for r in local if r["node"]=="0"]
                assert len(local)==600 and [int(r["period"]) for r in downstream]==list(range(1,201))
                item={"group":group,"scenario":scenario,"trace":trace,
                    "mean_cost":statistics.mean(float(r["cost"]) for r in local),
                    "mean_backlog":statistics.mean(int(r["backlog"]) for r in downstream),
                    "cumulative_backlog":sum(int(r["backlog"]) for r in downstream),
                    "peak_backlog":max(int(r["backlog"]) for r in downstream),
                    "terminal_backlog":int(downstream[-1]["backlog"]),
                    "mean_inventory":statistics.mean(int(r["inventory"]) for r in local),
                    "changed_node_periods":sum(r["actual_order"]!=r["happo_order"] for r in local),
                    "positive_corrections":sum(int(r["actual_order"])>int(r["happo_order"]) for r in local),
                    "negative_corrections":sum(int(r["actual_order"])<int(r["happo_order"]) for r in local)}
                metrics.append(item); selected.append(item)
            summary[group][scenario]={metric:statistics.mean(r[metric] for r in selected)
                for metric in selected[0] if metric not in ("group","scenario","trace")}
        for trace,event in enumerate(demands["events"]):
            curve={s:[int(r["backlog"]) for r in rows if r["group"]==group and r["scenario"]==s
                and int(r["trace"])==trace and r["node"]=="0"] for s in ("base","shock")}
            end=event["start_index"]+event["duration"]
            starts=range(end,191)
            first=next((i for i in starts if all(curve["shock"][j]<=curve["base"][j]+5 for j in range(i,i+10))),None)
            sustained=next((i for i in starts if all(curve["shock"][j]<=curve["base"][j]+5 for j in range(i,200))),None)
            recovery.append({"group":group,"trace":trace,"postshock_start_period":end+1,
                "first_window_delay":None if first is None else first-end,
                "sustained_window_delay":None if sustained is None else sustained-end,
                "recross_after_first":False if first is None else any(curve["shock"][j]>curve["base"][j]+5 for j in range(first+10,200)),
                "interpretation":"DeepSeek own base/shock curves have independently generated rules; not a pure shock-effect estimate" if group=="deepseek" else "paired same controller"})
    reference_episodes=[e for e in episodes if e["group"]=="happo"]
    alarm={"normal_episodes_with_alarm":sum(e["trigger_period"] is not None for e in reference_episodes if e["scenario"]=="base"),
           "shock_episodes_with_pre_event_alarm":sum(e["trigger_period"] is not None and e["trigger_period"]<demands["events"][e["trace"]]["start_index"]+1 for e in reference_episodes if e["scenario"]=="shock"),
           "normal_episode_count":5,"shock_episode_count":5}
    for trace in range(5):
        for scenario in ("base","shock"):
            es=[e for e in episodes if e["trace"]==trace and e["scenario"]==scenario]
            assert len({e["trigger_period"] for e in es})==1
    for call in calls:
        assert call["status"] in ("valid","failed")
        context=json.loads(call["request"]["messages"][1]["content"])
        assert set(context)=={"observed_periods","observed_last25_demands","nodes"}
        assert len(context["observed_last25_demands"])==25
    paired=[]
    for group in ("manual","deepseek"):
        for scenario in ("base","shock"):
            for trace in range(5):
                a=next(r for r in metrics if r["group"]==group and r["scenario"]==scenario and r["trace"]==trace)
                b=next(r for r in metrics if r["group"]=="happo" and r["scenario"]==scenario and r["trace"]==trace)
                paired.append({"group":group,"scenario":scenario,"trace":trace,
                    **{f"delta_{m}":a[m]-b[m] for m in ("mean_cost","mean_backlog","cumulative_backlog","terminal_backlog")}})
    same_prompts=[calls[i]["request"]==calls[i+5]["request"] for i in range(5)] if len(calls)==10 else None
    result={"summary":summary,"alarm_audit":alarm,"same_prompt_base_shock":same_prompts,
        "api_calls":len(calls),"valid_calls":sum(c["status"]=="valid" for c in calls),
        "total_seconds":sum(c["seconds"] for c in calls),
        "total_tokens":sum(c.get("response",{}).get("usage",{}).get("total_tokens",0) for c in calls),
        "returned_models":sorted({c.get("response",{}).get("model") for c in calls if "response" in c}),
        "conclusion":"Interface operational, but detector fired in all normal episodes and before all scheduled shocks. Pilot does not demonstrate event-time rule generation or improvement. Preserve all results."}
    for name,data in (("metrics.csv",metrics),("paired_vs_happo.csv",paired),("recovery.csv",recovery)):
        with (p/name).open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    (p/"summary.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__": main()
