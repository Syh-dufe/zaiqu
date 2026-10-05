"""Independent PPO update using unchanged author's policy/trainer components."""
import json
import numpy as np
import torch

def update(runner,target):
    assert runner.use_centralized_V is False
    audit_path=target/'ippo_update_audit.json'
    history=json.loads(audit_path.read_text(encoding='utf-8')) if audit_path.exists() else []
    infos=[]
    for index in torch.randperm(runner.num_agents):
        agent=int(index);buffer=runner.buffer[agent]
        local_shape=runner.envs.observation_space[agent].shape
        central_shape=runner.envs.share_observation_space[agent].shape
        assert buffer.share_obs.shape[-1]==buffer.obs.shape[-1]==local_shape[-1]
        assert local_shape[-1]<central_shape[-1]
        factor=np.ones((runner.episode_length,runner.n_rollout_threads,1),dtype=np.float32)
        runner.trainer[agent].prep_training();buffer.update_factor(factor)
        assert np.all(buffer.factor==1)
        history.append(dict(agent=agent,update_index=len(history),factor_min=float(buffer.factor.min()),
            factor_max=float(buffer.factor.max()),local_dim=int(local_shape[-1]),central_dim=int(central_shape[-1]),
            critic_dim=int(buffer.share_obs.shape[-1]),step_after_update=runner.completed_steps+runner.episode_length*runner.n_rollout_threads))
        infos.append(runner.trainer[agent].train(buffer))
        assert np.all(buffer.factor==1)
        buffer.after_update()
    audit_path.write_text(json.dumps(history,indent=2),encoding='utf-8')
    return infos
