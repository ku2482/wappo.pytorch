import os
import numpy as np
import torch
from torch.optim import RMSprop
from torch.nn.utils import clip_grad_norm_

from .base import BaseAgent
from wappo.network import PPONetwork


class PPOAgent(BaseAgent):

    def __init__(self, source_venv, target_venv, log_dir, device,
                 num_steps=10**6, lr_ppo=5e-4, gamma=0.999,
                 rollout_length=16, num_minibatches=8, epochs_ppo=3,
                 clip_range_ppo=0.2, coef_value=0.5, coef_ent=0.01,
                 lambd=0.95, max_grad_norm=0.5, use_impala=True):
        super().__init__(
            source_venv, target_venv, log_dir, device, num_steps, gamma,
            rollout_length, num_minibatches, epochs_ppo, clip_range_ppo,
            coef_value, coef_ent, lambd, max_grad_norm)

        # PPO network.
        self.ppo_network = PPONetwork(
            self.source_venv.observation_space.shape,
            self.source_venv.action_space.n,
            use_impala=use_impala).to(device)

        # Optimizer.
        self.optim_ppo = RMSprop(self.ppo_network.parameters(), lr=lr_ppo)

    def update(self):
        loss_policies = []
        loss_values = []

        for samples in self.source_storage.iter(self.batch_size):
            self.update_steps += 1
            loss_policy, loss_value = self.update_ppo(samples)
            loss_policies.append(loss_policy)
            loss_values.append(loss_value)

        self.writer.add_scalar(
            'loss/policy', np.mean(loss_policies), self.steps)
        self.writer.add_scalar(
            'loss/value', np.mean(loss_values), self.steps)

    def update_ppo(self, samples):
        states, actions, values_old, \
            value_targets, log_probs_old, advantages = samples
        values, log_probs, mean_entropy = \
            self.ppo_network.evaluate_actions(states, actions)

        # >>> Value >>> #
        values_clipped = values_old + (values - values_old).clamp(
            -self.clip_range_ppo, self.clip_range_ppo)
        loss_value1 = (values - value_targets).pow(2)
        loss_value2 = (values_clipped - value_targets).pow(2)
        loss_value = torch.max(loss_value1, loss_value2).mean()
        # >>> Value >>> #

        # >>> Policy >>> #
        ratio = torch.exp(log_probs - log_probs_old)
        loss_policy1 = -ratio * advantages
        loss_policy2 = -torch.clamp(
            ratio,
            1.0 - self.clip_range_ppo,
            1.0 + self.clip_range_ppo
        ) * advantages
        loss_policy = torch.max(loss_policy1, loss_policy2).mean()
        # >>> Policy >>> #

        # >>> Total >>> #
        loss = loss_policy - \
            self.coef_ent * mean_entropy + self.coef_value * loss_value
        # >>> Total >>> #

        self.optim_ppo.zero_grad()
        loss.backward()
        clip_grad_norm_(self.ppo_network.parameters(), self.max_grad_norm)
        self.optim_ppo.step()

        return loss_policy.detach().item(), loss_value.detach().item()

    def save_models(self, save_dir):
        super().save_models(save_dir)
        torch.save(
            self.ppo_network.state_dict(),
            os.path.join(save_dir, 'ppo_network.pth'))

    def load_models(self, save_dir):
        super().load_models(save_dir)
        self.ppo_network.load_state_dict(
            torch.load(os.path.join(save_dir, 'ppo_network.pth')))
