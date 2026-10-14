"""Same frozen guard pool, only the injected synthetic demand provider differs."""
import types,time
METHODS=('original_merton','center_naive','native_sundial','adapted_sundial')

def factory(original,guard_adapter,predictor,path_module,seed,batch):
 def create(group,client,library,random_rules,identity):
  assert group in METHODS
  forecasts=predictor.Centers();last={}
  def forecast(history,trace,period,method='merton',report_age=0):
   assert method=='merton' and period==len(history)+report_age
   started=time.perf_counter();h=min(20,200-period);sid=f'b{batch}_s{seed}_t{trace}_p{period+1}'
   common=dict(group=group,seed=seed,batch=batch,trace=trace,decision_period=period+1,delivered_through=period-report_age,
     report_age=report_age,horizon=h,stream_identity=sid)
   if group=='original_merton':
    pair=original.forecasts(history,trace,period,'merton',report_age)
    last.clear();last.update(common,provider=group,seconds=time.perf_counter()-started);return pair
   if group=='center_naive':
    center=[history[-1]]*h;value=path_module.generate(center,history[-1],report_age,sid)
    last.clear();last.update(common,provider=group,center=center,stream_seeds=value['stream_seeds'],seconds=time.perf_counter()-started)
   else:
    value,prediction=forecasts.forecast(history,report_age,h,sid,group=='adapted_sundial')
    last.clear();last.update(common,provider=group,prediction=prediction,seconds=time.perf_counter()-started)
   deployed=value['deployment'];return deployed[:3],deployed[3:]
  isolated=types.SimpleNamespace(**original.__dict__);isolated.forecasts=forecast
  klass=guard_adapter.build_controller(isolated);inner=klass('guard_pool',client,library,random_rules,identity);old_decide=inner.decide
  def decide(*args,**kwargs):
   result,record=old_decide(*args,**kwargs)
   if record and 'forecasts' in record:record['forecast_audit']=dict(last);record['deployed_forecast_method']=group
   return result,record
  inner.decide=decide;return inner
 return create
