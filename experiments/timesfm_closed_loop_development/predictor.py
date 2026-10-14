"""Frozen causal report-block forecasting; episode-local cache only."""
import math
import sys
import time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
DEPS=Path('C:/Users/13384/.cache/zaiqu-timesfm-pilot/deps')
REVISION='1d952420fba87f3c6dee4f240de0f1a0fbc790e3'
MODEL=Path('C:/Users/13384/.cache/zaiqu-timesfm-pilot/model')/REVISION/'model.safetensors'
_model=None

def model():
    global _model
    if _model is None:
        sys.path.insert(0,str(DEPS))
        from timesfm import ForecastConfig
        from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch
        _model=TimesFM_2p5_200M_torch(torch_compile=False)
        _model.load_checkpoint(str(MODEL),torch_compile=False)
        _model.compile(ForecastConfig(max_context=128,max_horizon=32,per_core_batch_size=4))
    return _model

class Centers:
    def __init__(self):self.cache={}
    def forecast(self,history,age,horizon):
        assert len(history)%3==0 and age in (0,1,2) and 1<=horizon<=20
        blocks=[]
        for i in range(0,len(history),3):
            values=history[i:i+3];assert values[0]==values[1]==values[2]
            blocks.append(float(values[0]))
        assert blocks and all(0<=x<=20 for x in blocks)
        count=math.ceil((age+horizon)/3)
        key=(tuple(blocks),count)
        started=time.perf_counter();hit=key in self.cache
        if not hit:
            import torch
            with torch.inference_mode():points,_=model().forecast(horizon=count,inputs=[np.asarray(blocks,dtype=float)])
            point=np.asarray(points[0],dtype=float)
            assert len(point)==count and np.isfinite(point).all()
            self.cache[key]=point.tolist()
        point=self.cache[key]
        center=np.clip(np.repeat(point,3)[age:age+horizon],0,20).tolist()
        assert len(center)==horizon
        return center,dict(block_history=blocks,block_predictions=point,cache_hit=hit,seconds=time.perf_counter()-started,revision=REVISION)
