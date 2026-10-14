"""Per-episode forecast injection into the frozen guard-pool controller."""
import types
import time
import numpy as np

METHODS=('original_merton','center_merton','center_naive','center_timesfm')

def factory(original,guard_adapter,predictor,path_module,seed,batch):
    def create(group,client,library,random_rules,identity):
        assert group in METHODS
        centers=predictor.Centers();last={}
        def forecast(history,trace,period,method='merton',report_age=0):
            assert method=='merton' and period==len(history)+report_age
            started=time.perf_counter();h=min(20,200-period)
            common=dict(group=group,seed=seed,batch=batch,trace=trace,decision_period=period+1,
                delivered_through=period-report_age,report_age=report_age,horizon=h)
            if group=='original_merton':
                result=original.forecasts(history,trace,period,'merton',report_age)
                last.clear();last.update(common,provider='original_merton',seconds=time.perf_counter()-started)
                return result
            base=original.forecasts(history,trace,period,'merton',report_age)
            center=np.asarray(base[0]+base[1],dtype=float).mean(axis=0).tolist()
            prediction={}
            if group=='center_naive':center=[history[-1]]*h
            elif group=='center_timesfm':center,prediction=centers.forecast(history,report_age,h)
            # Same innovation stream across forecast methods; group excluded.
            stream_identity=f'b{batch}_s{seed}_t{trace}_p{period+1}'
            value=path_module.generate(center,history[-1],report_age,stream_identity)
            last.clear();last.update(common,provider=group,center=center,prediction=prediction,
                stream_identity=stream_identity,stream_seeds=value['stream_seeds'],
                seconds=time.perf_counter()-started,diagnostic_draws=32,deployed_paths=6)
            paths=value['deployment']
            return paths[:3],paths[3:]
        isolated=types.SimpleNamespace(**original.__dict__)
        isolated.forecasts=forecast
        klass=guard_adapter.build_controller(isolated)
        inner=klass('guard_pool',client,library,random_rules,identity)
        old_decide=inner.decide
        def decide(*args,**kwargs):
            result,record=old_decide(*args,**kwargs)
            if record and 'forecasts' in record:
                record['forecast_audit']=dict(last)
                record['deployed_forecast_method']=group
            return result,record
        inner.decide=decide
        return inner
    return create
