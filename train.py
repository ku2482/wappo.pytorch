from datetime import datetime
import os
import argparse
import yaml
import torch
from pyvirtualdisplay import Display

from wappo.agent import PPOAgent, WAPPOAgent
from wappo.env import make_venv

source_levels = [1543, 7991, 3671, 2336, 6420]
target_levels = [7354, 9570, 6317, 6187, 8430]


def main(args):
    assert 0 <= args.trial < 5, 'trial must between [0, 5).'

    with Display(visible=0, size=(100, 100), backend="xvfb"):
        with open(args.config, 'r') as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)

        device = torch.device(
            'cuda' if args.cuda and torch.cuda.is_available() else 'cpu')

        # Make environments.
        source_venv = make_venv(
            env_id=args.env_id,
            num_envs=config['env']['num_envs'],
            num_levels=source_levels[args.trial])
        target_venv = make_venv(
            env_id=args.env_id,
            num_envs=config['env']['num_envs'],
            num_levels=target_levels[args.trial])

        # Specify the directory to log.
        name = 'wappo' if args.wappo else 'ppo'
        time = datetime.now().strftime("%Y%m%d-%H%M")
        log_dir = os.path.join(
            args.log_dir, f'{args.env_id}', f'{name}-trial{args.trial}-{time}')

        # Save config.
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        with open(os.path.join(log_dir, 'config.yaml'), 'w') as f:
            f.write(yaml.dump(config))

        # Agent.
        if args.wappo:
            agent = WAPPOAgent(
                source_venv=source_venv, target_venv=target_venv,
                device=device, log_dir=log_dir,
                **config['ppo'], **config['wappo'])
        else:
            agent = PPOAgent(
                source_venv=source_venv, target_venv=target_venv,
                device=device, log_dir=log_dir, **config['ppo'])

        agent.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config/wappo.yaml')
    parser.add_argument('--env_id', type=str, default='cartpole-visual-v1')
    parser.add_argument('--log_dir', default='logs')
    parser.add_argument('--trial', type=int, default=0)
    parser.add_argument('--cuda', action='store_true')
    parser.add_argument('--wappo', action='store_true')
    main(parser.parse_args())
