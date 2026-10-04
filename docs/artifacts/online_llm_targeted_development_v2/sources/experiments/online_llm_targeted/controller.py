"""Original controller reuse and elite protection with execution-based carryover."""
import copy
import importlib.util
from pathlib import Path
import sys
import time
from shadow import features,corrected,snapshot,forecasts,score,select,compile_rule,eligible

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('targeted_original_controller',ROOT/'experiments/online_llm/controller.py')
ORIGINAL=importlib.util.module_from_spec(spec);sys.modules[spec.name]=ORIGINAL;spec.loader.exec_module(ORIGINAL)
V1Controller=ORIGINAL.EventController


class ContractController(V1Controller):
    def __init__(self,client,identity):
        super().__init__('online_feedback',client,[],None,identity)

    def decide(self,*args,**kwargs):
        actual,record=super().decide(*args,**kwargs)
        if record:
            record['method']='contract_feedback'
        return actual,record


def public_candidates(candidates):
    return [dict(id=c['id'],rule=copy.deepcopy(c.get('rule'))) for c in candidates]


def protected_and_worst(candidates,feedback):
    zero=feedback[0];assert zero['id']=='zero' and zero['valid']
    valid=[i for i in range(1,4) if feedback[i]['valid']]
    passed=[i for i in valid if eligible(feedback[i],zero)]
    pool=passed or valid
    protected=min(pool,key=lambda i:(feedback[i]['cost'],feedback[i]['downstream'],i)) if pool else None
    options=[i for i in range(1,4) if i!=protected]
    worst=max(options,key=lambda i:(not eligible(feedback[i],zero),
        feedback[i].get('cost',float('inf')),feedback[i].get('downstream',float('inf')),i))
    return protected,worst


class EliteController(V1Controller):
    def __init__(self,client,identity):
        super().__init__('elite_feedback',client,[],None,identity)
        self.last_executed=None;self.last_execution=None;self.pending_execution=None

    def observe_execution(self,completed_period,env,proposed,actual):
        """Called only AFTER successful real step; selection alone cannot retain."""
        if self.pending_execution is not None and actual!=proposed:
            self.last_executed=copy.deepcopy(self.pending_execution)
            self.last_execution=dict(completed_period=completed_period,actual_orders=actual.copy(),
                happo_orders=proposed.copy(),inventory=list(map(int,env.inventory)),backlog=list(map(int,env.backlog)))
        self.pending_execution=None

    def decide(self,env,history,orders,proposed,recurrent,actors,reports,notify):
        period=env.step_num;public=reports.public_state();visible=reports.delivered_history.copy()
        # Carryover is captured before expiry can reset the currently chosen id.
        retained=copy.deepcopy(self.last_executed)
        retained_execution=copy.deepcopy(self.last_execution)
        self.pending_execution=None
        if notify:
            self.notification=period
        slot=self.notification is not None and (period-self.notification)%5==0
        trigger=slot and public['delivered_through_period']>self.last_report and self.events<4
        record=None
        if period>=self.expires:
            self.chosen='zero'
        if trigger:
            self.events+=1;self.last_report=public['delivered_through_period'];started=time.perf_counter()
            context=dict(notification='emergency has occurred',observed_periods=period,
                nodes=features(env,visible,orders,proposed),known_pipeline=[list(map(int,p)) for p in env.order],
                last5_executed_orders=copy.deepcopy(orders[-5:]),available_report=public,
                delivered_reports=copy.deepcopy(reports.deliveries[-10:]),last_two_events=copy.deepcopy(self.memory[-2:]),
                caveat='Observed changes do not prove that a correction caused them.',
                forecast_protocol='6 synthetic Merton paths, 3 search and 3 independent review, horizon20; correction first5.')
            if self.memory:
                previous=self.memory[-1]
                context['observed_change_since_previous_event']=dict(
                    inventory=[int(env.inventory[i])-previous['inventory'][i] for i in range(3)],
                    backlog=[int(env.backlog[i])-previous['backlog'][i] for i in range(3)],
                    executed_orders=copy.deepcopy(orders[previous['observed_periods']:]),
                    newly_delivered_reports=copy.deepcopy([r for r in reports.deliveries if r['end_period']>previous['delivered_through_period']]))
            if retained:
                context['retained_previous_execution']=dict(candidate=dict(id=retained['id'],rule=retained['rule']),
                    execution=retained_execution,note='Observed execution only; current forecast and independent review must still pass.')
            state=snapshot(env,history);paths=forecasts(visible,self.identity['trace'],period,'merton',reports.age)
            projected=reports.projection();identity=dict(self.identity,event=self.events,decision_period=period+1)
            count=2 if retained else 3
            generated=self.client.generate(context,count,identity,'initial');failure=None
            if not generated:
                failure='generation_failed'
                generated=[dict(id=f'event{self.events}_fallback_{i}',rule={'explanation':'Format failure zero fallback',
                    'rules':[{'when':'True','delta':'0'}]},compiled=compile_rule({'rules':[{'when':'True','delta':'0'}]})) for i in range(count)]
            self.candidates=[dict(id='zero')]+([retained] if retained else [])+generated
            assert len(self.candidates)==4
            initial=public_candidates(self.candidates)
            feedback_started=time.perf_counter()
            feedback=[score(c,state,visible,orders,proposed,recurrent,actors,paths[0],5,projected) for c in self.candidates]
            feedback_seconds=time.perf_counter()-feedback_started
            protected,worst=protected_and_worst(self.candidates,feedback)
            protected_id=self.candidates[protected]['id'] if protected is not None else None
            target_id=self.candidates[worst]['id'];replacement=[];revision_failed=False
            if not failure:
                revision=dict(context,search_feedback=feedback,previous_candidates=initial[1:],
                    protected_candidate_id=protected_id,replacement_target_id=target_id,
                    revision_instruction='Return one replacement for replacement_target_id. Preserve protected_candidate_id. Independent review scores are unavailable.')
                replacement=self.client.generate(revision,1,identity,'revision');revision_failed=not bool(replacement)
                if replacement:
                    self.candidates[worst]=replacement[0]
            if protected_id is not None:
                assert any(c['id']==protected_id for c in self.candidates)
            self.chosen,selection=select(self.candidates,state,visible,orders,proposed,recurrent,actors,paths,5,projected)
            self.expires=period+5
            record=dict(**identity,method=self.method,generation_event=True,context=context,forecasts=paths,
                initial_candidates=initial,candidates=public_candidates(self.candidates),initial_candidate_count=3,
                fresh_candidate_count=count,retained_candidate_id=retained['id'] if retained else None,
                retained_execution=retained_execution,protected_candidate_id=protected_id,replacement_target_id=target_id,
                replaced_candidate_id=target_id if replacement else None,replacement_candidate_id=replacement[0]['id'] if replacement else None,
                search_revision_feedback=feedback,revision_scoring_seconds=feedback_seconds,
                failure=failure,revision_failed=revision_failed,revision_requested=not bool(failure),
                **selection,event_seconds=time.perf_counter()-started)
            self.memory.append(dict(event=self.events,observed_periods=period,delivered_through_period=public['delivered_through_period'],
                inventory=list(map(int,env.inventory)),backlog=list(map(int,env.backlog)),
                executed_orders=copy.deepcopy(orders[-5:]),reports=copy.deepcopy(reports.deliveries[-2:])))
            self.memory=self.memory[-2:]
        elif slot and self.events>0:
            state=snapshot(env,history);paths=forecasts(visible,self.identity['trace'],period,'merton',reports.age)
            self.chosen,selection=select(self.candidates,state,visible,orders,proposed,recurrent,actors,paths,5,reports.projection())
            self.expires=period+5
            record=dict(**self.identity,decision_period=period+1,method=self.method,generation_event=False,
                        forecasts=paths,available_report=public,**selection)
        active=next(c for c in self.candidates if c['id']==self.chosen)
        try:
            actual=corrected(active,env,visible,orders,proposed)
        except Exception as exc:
            selected=self.chosen;self.chosen='zero'
            if self.last_executed and self.last_executed['id']==selected:
                self.last_executed=None;self.last_execution=None
            if record is None:
                record=dict(**self.identity,decision_period=period+1,method=self.method,generation_event=False,screening_event=False)
            record.update(execution_failure=type(exc).__name__,selected_before_execution=selected,chosen='zero')
            actual=proposed.copy()
        if self.chosen!='zero' and actual!=proposed:
            self.pending_execution=copy.deepcopy(active)
        return actual,record
