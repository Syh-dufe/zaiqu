"""No-network exercise of the actual Client repair loop with both rule limits."""
import argparse,copy,json,os,socket,urllib.request
from pathlib import Path
import runner
def run(mode,out):
 assert not out.exists();out.mkdir(parents=True);os.environ['DEEPSEEK_API_KEY']='offline_fixture_noncredential'
 fixed,original=runner.setup(mode,16,False,False)
 records=runner.core.read(runner.OLD);bad=records[-2]['response'];values=json.loads(bad['choices'][0]['message']['content'])['candidates'];good=copy.deepcopy(values)
 good[2]['rules']=[r for r in good[2]['rules'] if 'delta' not in r['when']]
 if mode=='sundial':
  for candidate in good:
   candidate['rules']=[dict(when='False',delta='0')]*(6-len(candidate['rules']))+candidate['rules']
 for compiler in (original,fixed):
  try:compiler(values[2]);raise AssertionError('Invalid delta accepted')
  except ValueError as e:
   if compiler is fixed:assert 'delta' in str(e) and 'Allowed input features' in str(e)
 payload=copy.deepcopy(bad);payload['choices'][0]['message']['content']=json.dumps(dict(candidates=good));replies=[bad,payload];requests=[]
 class Reply:
  def __init__(self,v):self.v=v
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def read(self):return json.dumps(self.v).encode()
 def mocked(request,timeout):requests.append(json.loads(request.data));return Reply(replies.pop(0))
 def forbidden(*a,**kw):raise RuntimeError('Network forbidden')
 urllib.request.urlopen=mocked;socket.socket.connect=forbidden;socket.create_connection=forbidden
 client=runner.core.Client(out,runner.core.SYSTEM,'deepseek-flash')
 result=client.generate(dict(fixture=True),3,dict(group='original_merton' if mode=='merton' else 'adapted_sundial',scenario='shock',trace=0,event=1,decision_period=73),'initial')
 assert len(result)==3 and len(requests)==2 and len(client.records)==2 and client.records[0]['status']=='failed' and client.records[1]['status']=='valid'
 assert 'delta is an output field' in requests[1]['messages'][-1]['content']
 runner.core.write(out/'passed.json',dict(status='passed',network_requests=0,mocked_http=2,unchanged_rejection=True,actual_client_repair_loop=True,rule_limit=4 if mode=='merton' else 6,system_unchanged=True))
 print('DIAGNOSTIC_CLIENT_FIXTURE_PASSED',mode,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('merton','sundial'));p.add_argument('out',type=Path);a=p.parse_args();run(a.mode,a.out)
