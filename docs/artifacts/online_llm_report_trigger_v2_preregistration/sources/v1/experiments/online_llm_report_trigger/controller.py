"""Episode-local online event controller; prompts use an explicit public whitelist."""
import copy
import random
import time
from shadow import features, corrected, snapshot, forecasts, score, select, compile_rule


class ReportTriggerController:
    def __init__(self, method, client, library, random_rules, identity):
        self.method, self.client = 'online_feedback', client
        self.library, self.random_rules, self.identity = library, random_rules, identity
        self.notification = None
        self.last_generation_period = None
        self.reference_mean = None
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
        event_allowed = self.method in ('online_feedback','random_screen') or self.events == 0
        means = [float(r['demand_mean']) for r in reports.deliveries[-2:]]
        report_mean = sum(means)/len(means) if means else 0.
        trigger, schedule = scheduling(period, self.notification, new_report, self.events,
            self.last_generation_period, self.reference_mean, report_mean)
        record = None
        if period >= self.expires:
            self.chosen = 'zero'
        if trigger:
            self.last_generation_period = period
            self.reference_mean = report_mean
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
            else:
                generated = self.client.generate(context, 3, identity, 'initial')
            if not generated:
                failure = 'generation_failed'
                # Zero candidates preserve the registered scoring budget after failures.
                generated = [dict(id=f'fallback_{i}', rule={'rules':[{'when':'True','delta':'0'}]},
                                  compiled=compile_rule({'rules':[{'when':'True','delta':'0'}]})) for i in range(3)]
            self.candidates = [dict(id='zero')] + generated
            if self.method in ('online_once','online_feedback','random_screen'):
                feedback_start = time.perf_counter()
                revision_feedback = [score(c,state,visible,orders,proposed,recurrent,actors,paths[0],5,projected) for c in self.candidates]
                feedback_seconds = time.perf_counter()-feedback_start
                if self.method == 'random_screen':
                    replacement = [dict(id='random_revision',rule=random_values[3],compiled=compile_rule(random_values[3]))]
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
            self.chosen, selection = select(self.candidates,state,visible,orders,proposed,recurrent,actors,paths,5,projected)
            self.expires = period+5
            record = dict(**identity, method=self.identity['group'], context=context, forecasts=paths,
                generation_event=True,
                candidates=[dict(id=c['id'],rule=c.get('rule')) for c in self.candidates],
                search_revision_feedback=revision_feedback, revision_scoring_seconds=feedback_seconds,
                failure=failure, revision_failed=revision_failed, **selection, event_seconds=time.perf_counter()-started)
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
            self.chosen,selection = select(self.candidates,state,visible,orders,proposed,recurrent,actors,paths,5,reports.projection())
            self.expires = period+5
            record = dict(**self.identity,decision_period=period+1,method=self.identity['group'],
                          generation_event=False,forecasts=paths,available_report=public,**selection)
        if record is not None:
            record['generation_schedule'] = schedule
        active = next(c for c in self.candidates if c['id']==self.chosen)
        try:
            actual = corrected(active,env,visible,orders,proposed)
        except Exception as exc:
            # Only generated-rule execution gets a HAPPO fallback. Selector,
            # budget, client and programming failures propagate to the batch.
            selected = self.chosen
            self.chosen = 'zero'
            if record is None:
                record = dict(**self.identity,decision_period=period+1,method=self.identity['group'],
                              generation_event=False,screening_event=False)
            record.update(execution_failure=type(exc).__name__,selected_before_execution=selected,chosen='zero')
            actual = proposed.copy()
        return actual, record


def scheduling(period, notification, new_report, events, last_generation_period, reference_mean, report_mean):
    slot = notification is not None and (period-notification) % 5 == 0
    gap = None if last_generation_period is None else period-last_generation_period
    relative_change = None if reference_mean is None else abs(report_mean-reference_mean)/max(1.,abs(reference_mean))
    eligible = slot and new_report and events < 4
    trigger = eligible and (events == 0 or (gap >= 20 and (relative_change >= .25 or gap >= 30)))
    return bool(trigger), dict(period=period, notification=notification, new_report=bool(new_report),
        slot=bool(slot), events_before=events, last_generation_period=last_generation_period,
        reference_mean=reference_mean, report_mean=report_mean, gap=gap,
        relative_change=relative_change, trigger=bool(trigger), minimum_gap=20, maximum_wait=30, threshold=.25)
