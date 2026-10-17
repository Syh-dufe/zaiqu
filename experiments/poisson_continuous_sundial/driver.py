"""One-shot serial development pilot. No automatic retry or overwrite."""
import json,os,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
OUT=ROOT/'results/poisson_continuous_sundial/development_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8',newline='\n')
def run():
 import winreg
 reg=read(OUT/'registration.json')
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as k:key=winreg.QueryValueEx(k,'DEEPSEEK_API_KEY')[0]
 assert key
 lock=OUT/'driver.started.lock'
 with lock.open('x') as f:f.write(str(os.getpid()))
 env=os.environ.copy();env['DEEPSEEK_API_KEY']=key;env['DEEPSEEK_MODEL']='deepseek-flash'
 tasks=[(lead,seed) for lead in reg['leads'] for seed in reg['model_seeds']]
 done=[];http=semantic=0
 for lead,seed in tasks:
  label=f'L{lead}_seed{seed}';log=OUT/f'{label}.log'
  write(OUT/'progress.json',dict(status='running',current=label,completed=done,http=http,semantic=semantic))
  with log.open('x',encoding='utf-8') as f:
   cp=subprocess.run([sys.executable,'-u',str(HERE/'runner.py'),'run','--lead',str(lead),'--seed',str(seed)],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
  folder=OUT/'runs'/label
  if cp.returncode:
   write(OUT/'failed.json',dict(task=label,exit_code=cp.returncode,preserved_partial=True,completed=done))
   write(OUT/'progress.json',dict(status='failed',current=label,completed=done,http=http,semantic=semantic));return cp.returncode
  audit=read(folder/'independent_audit.json');calls=read(folder/'calls.json')
  http+=len(calls);semantic+=sum(c.get('attempt')==1 for c in calls);done.append(label)
  assert http<=reg['api_http_cap'] and semantic<=reg['api_semantic_cap']
  write(OUT/'progress.json',dict(status='running',completed=done,http=http,semantic=semantic))
 write(OUT/'completed.json',dict(tasks=len(done),episodes=len(done)*4,node_periods=len(done)*2400,http=http,semantic=semantic,api_caps=[reg['api_http_cap'],reg['api_semantic_cap']]))
 write(OUT/'progress.json',dict(status='completed',completed=done,http=http,semantic=semantic))
if __name__=='__main__':sys.exit(run())
