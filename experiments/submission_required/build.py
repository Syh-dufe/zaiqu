"""Construct isolated adapters with asserted, reviewable changes to pinned source."""
from common import ROOT,HERE

def replace_once(text,left,right):
    assert text.count(left)==1,(left,text.count(left))
    return text.replace(left,right)

def build():
    text=(ROOT/'experiments/online_llm/controller.py').read_text(encoding='utf-8')
    text=replace_once(text,'class EventController:','class ComponentController:')
    text=replace_once(text,"self.method in ('online_feedback','random_screen')","self.method in ('online_feedback','random_screen','no_feedback','no_review','deterministic_search')")
    text=replace_once(text,"if self.method in ('online_once','online_feedback','random_screen'):","if self.method in ('online_once','online_feedback','random_screen','no_review','deterministic_search'):")
    text=replace_once(text,"            else:\n                generated = self.client.generate(context, 3, identity, 'initial')","            elif self.method == 'deterministic_search':\n                generated = self.construct(state,visible,orders,proposed,recurrent,actors,paths,projected)\n            else:\n                generated = self.client.generate(context, 3, identity, 'initial')")
    text=replace_once(text,"                elif failure:\n                    replacement = []","                elif self.method == 'deterministic_search':\n                    replacement = self.refine(generated,state,visible,orders,proposed,recurrent,actors,paths,projected)\n                elif failure:\n                    replacement = []")
    text=replace_once(text,'paths,5,projected)','paths,5,projected,review=self.method != \'no_review\')')
    text=replace_once(text,'paths,5,reports.projection())','paths,5,reports.projection(),review=self.method != \'no_review\')')
    text=replace_once(text,"            if self.method == 'random_screen':\n                record['random_seed']", "            if self.method == 'deterministic_search':\n                record['candidate_construction'] = self.construction_audit\n            if self.method == 'random_screen':\n                record['random_seed']")
    text += '''

    @staticmethod
    def constant(vector,label):
        rule=dict(rules=[dict(when=f'agent == {i}',delta=str(v)) for i,v in enumerate(vector)])
        return dict(id=label,rule=rule,compiled=compile_rule(rule),vector=list(vector))

    def construct(self,state,visible,orders,proposed,recurrent,actors,paths,projected):
        import itertools
        started=time.perf_counter();seen=set();ranked=[];records=[]
        for index,vector in enumerate(itertools.product((-2,0,2),repeat=3)):
            action=tuple(min(20,max(0,a+v)) for a,v in zip(proposed,vector))
            candidate=self.constant(vector,f'grid_{index}')
            if action in seen:
                records.append(dict(vector=list(vector),action=list(action),duplicate=True));continue
            seen.add(action)
            value=score(candidate,state,visible,orders,proposed,recurrent,actors,paths[0],5,projected)
            records.append(dict(vector=list(vector),action=list(action),score=value))
            if any(vector) and action != tuple(proposed) and value['valid']:
                ranked.append((value['cost'],vector,candidate))
        ranked.sort(key=lambda x:(x[0],x[1]))
        selected=[x[2] for x in ranked[:3]]
        while len(selected)<3:selected.append(self.constant((0,0,0),f'grid_pad_{len(selected)}'))
        self.construction_audit=dict(initial=records,initial_score_calls=sum('score' in x for x in records),
            initial_seconds=time.perf_counter()-started,refinement=[],information='Same public context and causal search paths; no review or true future in construction')
        assert self.construction_audit['initial_score_calls']<=27
        return selected

    def refine(self,generated,state,visible,orders,proposed,recurrent,actors,paths,projected):
        started=time.perf_counter();center=generated[0]['vector'];ranked=[];records=[]
        for node in range(3):
            for step in (-1,1):
                vector=center.copy();vector[node]+=step
                candidate=self.constant(vector,f'neighbor_{node}_{step}')
                value=score(candidate,state,visible,orders,proposed,recurrent,actors,paths[0],5,projected)
                records.append(dict(vector=vector,score=value))
                if value['valid']:ranked.append((value['cost'],tuple(vector),candidate))
        ranked.sort(key=lambda x:(x[0],x[1]))
        self.construction_audit.update(refinement=records,refinement_score_calls=len(records),refinement_seconds=time.perf_counter()-started)
        assert len(records)==6
        return [ranked[0][2]] if ranked else []


from controller import EventController as OriginalController

def ControllerFactory(method,client,library,random_rules,identity):
    if method in ('happo','online_feedback'):
        return OriginalController(method,client,library,random_rules,identity)
    return ComponentController('online_once' if method=='first_only' else method,client,library,random_rules,identity)
'''
    (HERE/'component.py').write_text(text,encoding='utf-8')
    text=(ROOT/'experiments/joint_baseline_confirmation/run_online.py').read_text(encoding='utf-8')
    text=replace_once(text,'from controller import EventController','from controller import EventController\n# Isolated component variants; full strategy remains the original class.\nsys.path.insert(0,str(Path(__file__).parent))\nfrom component import ControllerFactory\nEventController=ControllerFactory')
    text=replace_once(text,"METHODS = ('happo','ippo','online_feedback')","METHODS = ('happo','online_feedback','no_feedback','no_review','first_only','deterministic_search')")
    text=replace_once(text,'not 60<=start<=100 or not 20<=duration<=80','not 40<=start<=120 or not 20<=duration<=80')
    text=replace_once(text,'factor not in (0.5,1.25,1.5)','factor not in (0.5,1.10,1.25,1.5)')
    text=replace_once(text,"files = list(Path(__file__).parent.glob('*.py'))", "files = list(Path(__file__).parent.glob('*.py')) + [ROOT/'experiments/joint_baseline_confirmation/run_online.py',ROOT/'docs/superpowers/specs/2026-10-09-required-experiments-design.md',ROOT/'docs/superpowers/plans/2026-10-09-required-experiments.md']")
    text=replace_once(text,"    parser.add_argument('--preflight',action='store_true')","    parser.add_argument('--preflight',action='store_true')\n    parser.add_argument('--methods',nargs='+',choices=METHODS,default=list(METHODS))\n    parser.add_argument('--phase',choices=('development','confirmation','sensitivity'),default='development')")
    text=replace_once(text,'    opts=parser.parse_args()','    opts=parser.parse_args()\n    global METHODS\n    METHODS=tuple(opts.methods)')
    # global must precede any use of METHODS inside main.
    text=text.replace('def main():\n    parser=', 'def main():\n    global METHODS\n    parser=').replace('    global METHODS\n    METHODS=tuple(opts.methods)','    METHODS=tuple(opts.methods)')
    text=replace_once(text,"    contract=contracts(opts.input_file,opts.operator_library,opts.training_directory)","    contract=contracts(opts.input_file,opts.operator_library,opts.training_directory)\n    contract.update(development_only=opts.phase=='development',independent_confirmation=opts.phase=='confirmation',phase=opts.phase)")
    # Phase is separate from model/source contract to keep strict internal comparisons.
    text=text.replace("\n    contract.update(development_only=opts.phase=='development',independent_confirmation=opts.phase=='confirmation',phase=opts.phase)", '')
    text=text.replace("write(out/'protocol.json',dict(contract,system=SYSTEM,", "write(out/'protocol.json',dict(contract,phase=opts.phase,system=SYSTEM,")
    text=text.replace('assert len(episodes)==24 and len(rows)==14400','assert len(episodes)==len(METHODS)*8 and len(rows)==len(METHODS)*4800')
    text=text.replace('for r in rows})==14400','for r in rows})==len(METHODS)*4800')
    text=replace_once(text,"            for group in ('online_feedback',):", "            for group in [m for m in METHODS if m!='happo']:")
    # Reference remains necessary for prefix checks even when HAPPO is omitted.
    # All production task method lists include HAPPO.
    text=replace_once(text,'        development_only=False,independent_confirmation=True,',"        development_only=opts.phase=='development',independent_confirmation=opts.phase=='confirmation',phase=opts.phase,")
    (HERE/'run_online.py').write_text(text,encoding='utf-8')

if __name__=='__main__':build()
