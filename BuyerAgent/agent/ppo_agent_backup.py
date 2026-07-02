import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal
import numpy as np
from agent.actor_critic_v2 import ActorMLP, CriticMLP

class RunningStat:
    """ Welford's online algorithm """
    def __init__(self, shape=()):
        self.n = 0
        self.mean = np.zeros(shape)
        self.S = np.zeros(shape)

    def push(self, x):
        self.n += 1
        if self.n == 1:
            self.mean = x
            self.S = 0.0
        else:
            old_mean = self.mean.copy()
            self.mean = old_mean + (x - old_mean) / self.n
            self.S = self.S + (x - old_mean) * (x - self.mean)

    @property
    def std(self):
        variance = self.S / (self.n - 1) if self.n > 1 else np.square(self.mean)
        return np.sqrt(variance)

class ParallelRolloutBuffer:
    """ Buffer adapted for parallel N-environments. """
    def __init__(self):
        self.states = []
        self.actions = []
        self.logprobs = []
        self.rewards = []
        self.is_terminals = []
        # Values are NOT stored here during rollout anymore!
    
    def clear(self):
        del self.states[:]
        del self.actions[:]
        del self.logprobs[:]
        del self.rewards[:]
        del self.is_terminals[:]

class ParallelPPOAgent:
    def __init__(self, state_dim, action_dim, max_action, lr_actor=0.0003, lr_critic=0.001, gamma=0.99, K_epochs=30, eps_clip=0.2):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        self.gamma = gamma
        self.eps_clip = eps_clip
        self.K_epochs = K_epochs
        self.max_action = max_action
        
        self.buffer = ParallelRolloutBuffer()
        self.reward_scaler = RunningStat()

        self.policy_actor = ActorMLP(state_dim, action_dim, max_action).to(self.device)
        self.policy_critic = CriticMLP(state_dim).to(self.device)
        
        self.optimizer_actor = optim.Adam(self.policy_actor.parameters(), lr=lr_actor)
        self.optimizer_critic = optim.Adam(self.policy_critic.parameters(), lr=lr_critic)

        self.policy_old_actor = ActorMLP(state_dim, action_dim, max_action).to(self.device)
        self.policy_old_critic = CriticMLP(state_dim).to(self.device)
        self.policy_old_actor.load_state_dict(self.policy_actor.state_dict())
        self.policy_old_critic.load_state_dict(self.policy_critic.state_dict())
        
        self.MseLoss = nn.MSELoss()

    def select_action_batched(self, states_matrix):
        with torch.no_grad():
            state_tensor = torch.FloatTensor(states_matrix).to(self.device)
            
            action_mean_percent, log_std = self.policy_old_actor(state_tensor)
            
            # Aqui a Média Percentual é algo como 0.50.
            # O Clamped log std estabiliza. Um exp(0.0) dá 1.0 (exploração de 100% da escala!)
            clamped_log_std = torch.clamp(log_std, min=-2.3, max=1.5)
            std_tensor = torch.exp(clamped_log_std)
            
            # Escolhemos uma Roda De Volume Percentual estocástica
            dist = Normal(action_mean_percent, std_tensor)
            action_percent = dist.sample()
            
            # O Log Probabilidade é calculado na Matemática Pura Adimensional
            action_logprob = dist.log_prob(action_percent)
            
            # A Ponte Cérebro -> Realidade: Aqui simizamos os Watts reais
            physical_action = torch.round(torch.clamp(action_percent * self.max_action, 0, self.max_action))
            
        # O ROBÔ GUARDA A MÚSICA DIMENSIONLESS NA MEMÓRIA!
        self.buffer.states.append(state_tensor)
        self.buffer.actions.append(action_percent)
        self.buffer.logprobs.append(action_logprob)
        
        return physical_action.cpu().numpy().flatten()

    def evaluate(self, state, action_percent):
        action_mean_percent, log_std = self.policy_actor(state)
        
        # Tem de ser matematicamente simétrico ao Select_Action!
        clamped_log_std = torch.clamp(log_std, min=-2.3, max=1.5)
        std_tensor = torch.exp(clamped_log_std)
        
        dist = Normal(action_mean_percent, std_tensor)
        
        action_logprobs = dist.log_prob(action_percent)
        dist_entropy = dist.entropy()
        
        state_values = self.policy_critic(state)
        
        return action_logprobs, state_values, dist_entropy

    def update(self):
        # 1. Evaluate the entire episode's baseline ONE SINGLE TIME! 
        # (The Great Critic Optimization)
        # We stack all days: shape [TIMESTEPS, NUM_ENVS, 28]
        all_states_tensor = torch.stack(self.buffer.states, dim=0).to(self.device)
        
        with torch.no_grad():
            # Critic processes all 91 days of 32 environments instantly. Shape: [TIMESTEPS, NUM_ENVS, 1]
            all_state_values = self.policy_old_critic(all_states_tensor).squeeze(-1) 
            
        # 2. Monte Carlo Estimate of Return (Discounted cumulative rewards)
        # Note: self.buffer.rewards shape is [TIMESTEPS, NUM_ENVS]
        rewards = []
        discounted_reward = np.zeros(len(self.buffer.rewards[0])) # vector of size NUM_ENVS
        
        # Reverse iterate through time
        for step_t in reversed(range(len(self.buffer.rewards))):
            reward_t = np.array(self.buffer.rewards[step_t])
            is_terminal_t = np.array(self.buffer.is_terminals[step_t])
            
            # Reset discount if terminal (for each env individually)
            discounted_reward[is_terminal_t] = 0
            
            discounted_reward = reward_t + (self.gamma * discounted_reward)
            
            # Welford's Scaler requires pushing items. For matrices, pushing individually or mean is tricky. 
            # We'll vectorize it:
            for val in discounted_reward:
                self.reward_scaler.push(val)
                
            normalized_r = (discounted_reward - self.reward_scaler.mean) / (self.reward_scaler.std + 1e-8)
            clipped_r = np.clip(normalized_r, -3.0, 3.0)
            
            rewards.insert(0, clipped_r)
            
        rewards_tensor = torch.tensor(np.array(rewards), dtype=torch.float32).to(self.device)

        # 3. Flatten the batches for PyTorch
        # Instead of [TIMESTEPS, NUM_ENVS, ...], we flatten to [TIMESTEPS * NUM_ENVS, ...]
        old_states = all_states_tensor.view(-1, all_states_tensor.size(-1)).detach()
        old_actions = torch.stack(self.buffer.actions, dim=0).view(-1, 1).detach()
        old_logprobs = torch.stack(self.buffer.logprobs, dim=0).view(-1, 1).detach()
        
        rewards_flat = rewards_tensor.view(-1, 1)
        old_state_values_flat = all_state_values.view(-1, 1).detach()

        # 4. Calculate Advantages
        advantages = rewards_flat - old_state_values_flat
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-5)

        # 5. Optimize the Policy
        for _ in range(self.K_epochs):
            logprobs, state_values, dist_entropy = self.evaluate(old_states, old_actions)

            ratios = torch.exp(logprobs - old_logprobs)
            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1 - self.eps_clip, 1 + self.eps_clip) * advantages

            actor_loss = -torch.min(surr1, surr2)
            critic_loss = 0.5 * self.MseLoss(state_values, rewards_flat)
            entropy_bonus = 0.05 * dist_entropy
            
            loss = actor_loss + critic_loss - entropy_bonus

            self.optimizer_actor.zero_grad()
            self.optimizer_critic.zero_grad()
            loss.mean().backward()
            self.optimizer_actor.step()
            self.optimizer_critic.step()
            
        # 5. Lock in the new weights! 
        self.policy_old_actor.load_state_dict(self.policy_actor.state_dict())
        self.policy_old_critic.load_state_dict(self.policy_critic.state_dict())

        # 6. Burn the Buffer!
        self.buffer.clear()
        
    def save(self, checkpoint_path):
        torch.save(self.policy_old_actor.state_dict(), checkpoint_path + '_actor.pth')
        torch.save(self.policy_old_critic.state_dict(), checkpoint_path + '_critic.pth')
        
    def load(self, checkpoint_path):
        self.policy_old_actor.load_state_dict(torch.load(checkpoint_path + '_actor.pth', map_location=self.device))
        self.policy_old_critic.load_state_dict(torch.load(checkpoint_path + '_critic.pth', map_location=self.device))
