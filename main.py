import copy

import carla
from ppo_agent.meta.config import Config

from ppo_agent.models import create_model
import torch.multiprocessing as mp
from ppo_agent.chief import chief
from ppo_agent.utils import TrafficLight, Counter
import torch.optim as optim
from ppo_agent.models import Shared_grad_buffers
import torch
from ppo_agent.train import train


class RandomAgent(object):
    def act(self, obs):
        control = carla.VehicleControl()
        control.steer = 0.0
        control.throttle = 1.0
        control.brake = 0.0
        return control


if __name__ == '__main__':
    try:
        mp.set_start_method('spawn')
    except RuntimeError:
        pass
    all_config = Config.fromfile("config_files/agent_config.py")
    # print(all_config.keys())
    env_cfg = all_config.env_cfg
    rollout_cfg = all_config.rollout_cfg
    agent_cfg = all_config.agent_cfg
    trainer_config = all_config.trainer_cfg
    train_cfg = all_config.train_cfg
    num_processes = env_cfg.num_processes
    update_threshold = env_cfg.num_processes

    # env_cfg.rank = 0
    # env_cfg.town = "Town01"
    # env_cfg.amount = [150, 0]
    # env = EnvWrapper(env_cfg)
    # agent = RandomAgent()
    # agent = HumanAgent()

    # vae_params = danet_config()
    # rollout = RolloutStorage(**rollout_cfg)
    # agent = CadreAgent(**agent_config)
    # trainer = Trainer(rollout, agent, train_config)
    # agent_config.rank = 0
    # agent = CadreAgent(agent_config, rollout_cfg)
    _, shared_model_dict = create_model(agent_cfg.model_cfg, load_vae=False)

    parameter_list = []
    for model_name in shared_model_dict:
        shared_model_dict[model_name] = shared_model_dict[model_name].share_memory()
        parameter_list = parameter_list + list(shared_model_dict[model_name].parameters())

    traffic_light = TrafficLight()
    counter = Counter()
    son_process_counter = Counter()
    device = agent_cfg.model_cfg.device_num

    if device == -1:
        device = torch.device("cpu")
    else:
        device = torch.device("cuda:" + str(device))
    shared_grad_buffers = Shared_grad_buffers(shared_model_dict, device)
    optimizer = optim.Adam(parameter_list, lr=trainer_config.lr)

    t = mp.Process(target=chief, args=(
        update_threshold, traffic_light, counter, shared_model_dict, shared_grad_buffers, optimizer,
        son_process_counter, train_cfg.max_grad_norm, num_processes))
    t.start()
    processes = [t]

    # ports = train_config.ports
    for rank in range(num_processes):

        t = mp.Process(target=train, args=(
        rank, train_cfg, copy.deepcopy(agent_cfg), copy.deepcopy(env_cfg), rollout_cfg, trainer_config, traffic_light, counter, shared_model_dict,
        shared_grad_buffers,
        son_process_counter))
        t.start()
        processes.append(t)
    for t in processes:
        t.join()
    # for episode in range(10):
    #     obs = env.reset()
    #     done = False
    #     print('start a new episode...')
    #     while not done:
    #         # action = agent.act(obs)
    #         action = env.action_space.sample()
    #         next_obs, reward, done = env.step(action)
    #         obs = next_obs
    #         # print('reward', reward)
