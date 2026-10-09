"""Independent controller namespace; old modules and running processes stay untouched."""
import inspect
import time
from pathlib import Path
from policy import keep_revision, select_pool


def build_controller(original):
    namespace=dict(original.__dict__)
    source=inspect.getsource(original.EventController)
    def replace(before,after,count=1):
        nonlocal source
        assert source.count(before)==count, 'Original controller contract changed'
        source=source.replace(before,after)
    replace("self.method in ('online_feedback','random_screen')",
            "self.method in ('online_feedback','random_screen','revision_guard','pool_review','guard_pool')")
    replace("self.method in ('online_once','online_feedback','random_screen')",
            "self.method in ('online_once','online_feedback','random_screen','revision_guard','pool_review','guard_pool')")
    before="""                if replacement:
                    self.candidates[1] = replacement[0]"""
    after="""                revision_guard_audit = None
                if replacement:
                    if self.method in ('revision_guard','guard_pool'):
                        revised_score = score(replacement[0],state,visible,orders,proposed,recurrent,actors,paths[0],5,projected)
                        keep = keep_revision(revision_feedback[1],revised_score,revision_feedback[0])
                        revision_guard_audit = dict(original_score=revision_feedback[1],revised_score=revised_score,
                            adopted=keep,revised_rule=replacement[0].get('rule'),extra_score_calls=1)
                        if keep:self.candidates[1] = replacement[0]
                    else:self.candidates[1] = replacement[0]"""
    replace(before,after)
    replace("revision_failed=revision_failed, **selection", "revision_failed=revision_failed, revision_guard_audit=revision_guard_audit, **selection")
    needle="self.chosen, selection = select(self.candidates,state,visible,orders,proposed,recurrent,actors,paths,5,projected)"
    replace(needle,"self.chosen, selection = self.select_variant(self.candidates,state,visible,orders,proposed,recurrent,actors,paths,5,projected)")
    needle="self.chosen,selection = select(self.candidates,state,visible,orders,proposed,recurrent,actors,paths,5,reports.projection())"
    replace(needle,"self.chosen,selection = self.select_variant(self.candidates,state,visible,orders,proposed,recurrent,actors,paths,5,reports.projection())")
    namespace['keep_revision']=keep_revision
    exec(compile(source,str(Path(__file__)), 'exec'),namespace)
    controller=namespace['EventController']
    original_select=original.select
    def select_variant(self,candidates,state,history,orders,proposed,recurrent,actors,paths,correction_periods,reports):
        if self.method not in ('pool_review','guard_pool'):
            return original_select(candidates,state,history,orders,proposed,recurrent,actors,paths,correction_periods,reports)
        started=time.perf_counter()
        def scorer(candidate,split):
            return original.score(candidate,state,history,orders,proposed,recurrent,actors,paths[split],correction_periods,reports)
        chosen,audit=select_pool(candidates,scorer)
        audit['seconds']=time.perf_counter()-started
        return chosen,audit
    controller.select_variant=select_variant
    return controller


def factory(original):
    isolated=build_controller(original)
    def create(method,client,library,random_rules,identity):
        if method in ('happo','online_feedback'):
            return original.EventController(method,client,library,random_rules,identity)
        assert method in ('revision_guard','pool_review','guard_pool')
        return isolated(method,client,library,random_rules,identity)
    return create
