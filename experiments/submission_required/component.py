"""Episode-local online event controller; prompts use an explicit public whitelist."""
import copy
import random
import time
from shadow import features, corrected, snapshot, forecasts, score, select, compile_rule


class ComponentController:
    def __init__(self, method, client, library, random_rules, identity):
        self.method, self.client = method, client
        self.library, self.random_rules, self.identity = library, random_rules, identity
        self.notification = None
        self.events = 0
        self.last_report = -1
        self.expires = -1
        self.memory = []
        self.candidates = [dict(id='zero')]
        self.chosen = 'zero'
        if client:
            client.reset_episode()

    def decide(self, env, history, orders, proposed, recurrent, actors, reports, notify):
        period = env.step_num
        public = reports.public_state()
        visible = reports.delivered_history.copy()
        if notify:
            self.notification = period
        slot = self.notification is not None and (period-self.notification) % 5 == 0
        new_report = public['delivered_through_period'] > self.last_report
        event_allowed = self.method in ('online_feedback','random_screen','no_feedback','no_review','deterministic_search') or self.events == 0
        trigger = slot and new_report and self.events < 4 and event_allowed and self.method != 'happo'
        record = None
        if period >= self.expires:
            self.chosen = 'zero'
        if trigger:
            self.events += 1
            self.last_report = public['delivered_through_period']
            started = time.perf_counter()
            context = dict(notification='emergency has occurred', observed_periods=period,
                nodes=features(env, visible, orders, proposed), known_pipeline=[list(map(int,p)) for p in env.order],
                last5_executed_orders=copy.deepcopy(orders[-5:]), available_report=public,
                delivered_reports=copy.deepcopy(reports.deliveries[-10:]),
                last_two_events=copy.deepcopy(self.memory[-2:]),
                caveat='Observed changes do not prove that a correction caused them.',
                forecast_protocol='6 synthetic Merton paths, 3 search and 3 independent review, horizon20; correction first5.')
            if self.memory:
                previous = self.memory[-1]
                context['observed_change_since_previous_event'] = dict(
                    inventory=[int(env.inventory[i])-previous['inventory'][i] for i in range(3)],
                    backlog=[int(env.backlog[i])-previous['backlog'][i] for i in range(3)],
                    executed_orders=copy.deepcopy(orders[previous['observed_periods']:]),
                    newly_delivered_reports=copy.deepcopy([r for r in reports.deliveries if r['end_period'] > previous['delivered_through_period']]))
            state = snapshot(env, history)
            paths = forecasts(visible, self.identity['trace'], period, 'merton', reports.age)
            projected = reports.projection()
            identity = dict(self.identity, event=self.events, decision_period=period+1)
            revision_feedback = None
            revision_failed = False
            failure = None
            if self.method == 'llm_library':
                generated = copy.deepcopy(self.library)
            elif self.method == 'random_screen':
                # Event-specific deterministic draws; no outcomes or hidden event data.
                random_seed = 20270803 + 100*self.identity['trace'] + self.events
                rng = random.Random(random_seed)
                random_values = [dict(explanation='Registered constant-vector diagnostic',
                    rules=[dict(when=f'agent == {node}',delta=str(rng.randint(-2,2))) for node in range(3)]) for _ in range(4)]
                generated = [dict(id=f'random_{i}',rule=r,compiled=compile_rule(r)) for i,r in enumerate(random_values[:3])]
            elif self.method == 'deterministic_search':
                generated = self.construct(state,visible,orders,proposed,recurrent,actors,paths,projected)
            else:
                generated = self.client.generate(context, 3, identity, 'initial')
            if not generated:
                failure = 'generation_failed'
                # Zero candidates preserve the registered scoring budget after failures.
                generated = [dict(id=f'fallback_{i}', rule={'rules':[{'when':'True','delta':'0'}]},
                                  compiled=compile_rule({'rules':[{'when':'True','delta':'0'}]})) for i in range(3)]
            self.candidates = [dict(id='zero')] + generated
            if self.method in ('online_once','online_feedback','random_screen','no_review','deterministic_search'):
                feedback_start = time.perf_counter()
                revision_feedback = [score(c,state,visible,orders,proposed,recurrent,actors,paths[0],5,projected) for c in self.candidates]
                feedback_seconds = time.perf_counter()-feedback_start
                if self.method == 'random_screen':
                    replacement = [dict(id='random_revision',rule=random_values[3],compiled=compile_rule(random_values[3]))]
                elif self.method == 'deterministic_search':
                    replacement = self.refine(generated,state,visible,orders,proposed,recurrent,actors,paths,projected)
                elif failure:
                    replacement = []
                else:
                    revision = dict(context, search_feedback=revision_feedback,
                        previous_candidates=[dict(id=c['id'],rule=c['rule']) for c in generated],
                        revision_instruction='Return one replacement candidate; it will replace candidate index0. Review results are unavailable.')
                    replacement = self.client.generate(revision,1,identity,'revision')
                    revision_failed = not bool(replacement)
                if replacement:
                    self.candidates[1] = replacement[0]
            else:
                feedback_seconds = 0.
            self.chosen, selection = select(self.candidates,state,visible,orders,proposed,recurrent,actors,paths,5,projected,review=self.method != 'no_review')
            self.expires = period+5
            record = dict(**identity, method=self.method, context=context, forecasts=paths,
                generation_event=True,
                candidates=[dict(id=c['id'],rule=c.get('rule')) for c in self.candidates],
                search_revision_feedback=revision_feedback, revision_scoring_seconds=feedback_seconds,
                failure=failure, revision_failed=revision_failed, **selection, event_seconds=time.perf_counter()-started)
            if self.method == 'deterministic_search':
                record['candidate_construction'] = self.construction_audit
            if self.method == 'random_screen':
                record['random_seed'] = random_seed
                record['initial_random_candidates'] = random_values[:3]
            # Review outcomes never enter memory or future generator requests.
            self.memory.append(dict(event=self.events,observed_periods=period,
                delivered_through_period=public['delivered_through_period'], inventory=list(map(int,env.inventory)),
                backlog=list(map(int,env.backlog)), executed_orders=copy.deepcopy(orders[-5:]),
                reports=copy.deepcopy(reports.deliveries[-2:])))
            self.memory = self.memory[-2:]
        elif slot and self.events > 0 and self.method != 'happo':
            # Initial-only and exhausted event budgets retain the last3 candidates.
            # Screening remains the old5-period protocol for all correction methods.
            state = snapshot(env,history)
            paths = forecasts(visible,self.identity['trace'],period,'merton',reports.age)
            self.chosen,selection = select(self.candidates,state,visible,orders,proposed,recurrent,actors,paths,5,reports.projection(),review=self.method != 'no_review')
            self.expires = period+5
            record = dict(**self.identity,decision_period=period+1,method=self.method,
                          generation_event=False,forecasts=paths,available_report=public,**selection)
        active = next(c for c in self.candidates if c['id']==self.chosen)
        try:
            actual = corrected(active,env,visible,orders,proposed)
        except Exception as exc:
            # Only generated-rule execution gets a HAPPO fallback. Selector,
            # budget, client and programming failures propagate to the batch.
            selected = self.chosen
            self.chosen = 'zero'
            if record is None:
                record = dict(**self.identity,decision_period=period+1,method=self.method,
                              generation_event=False,screening_event=False)
            record.update(execution_failure=type(exc).__name__,selected_before_execution=selected,chosen='zero')
            actual = proposed.copy()
        return actual, record


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
