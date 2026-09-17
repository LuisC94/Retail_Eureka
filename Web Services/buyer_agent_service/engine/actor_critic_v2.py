import torch
import torch.nn as nn
import torch.nn.functional as F

class ActorMLP(nn.Module):
    """
    The Actor (Intuition).
    Reads the State (17 variables) and outputs a continuous Action (Order Percentage).
    """
    def __init__(self, state_dim=17, action_dim=1, max_action=500):
        super(ActorMLP, self).__init__()
        
        self.max_action = max_action
        
        self.layer1 = nn.Linear(state_dim, 256)
        self.layer2 = nn.Linear(256, 256)
        self.layer3 = nn.Linear(256, 128)
        self.output_layer = nn.Linear(128, action_dim)
        
        self.log_std = nn.Parameter(torch.full((1, action_dim), 0.0))
        
    def forward(self, state):
        x = F.relu(self.layer1(state))
        x = F.relu(self.layer2(x))
        x = F.relu(self.layer3(x))
        
        action_mean_percent = torch.sigmoid(self.output_layer(x))
        return action_mean_percent, self.log_std


class CriticMLP(nn.Module):
    """
    The Critic (The Judge / Financial Value Forecaster).
    Evaluates the Expected Baseline Value (V-Value) of the 17-dim State.
    """
    def __init__(self, state_dim=17):
        super(CriticMLP, self).__init__()
        
        self.state_layer = nn.Linear(state_dim, 64)
        self.layer1 = nn.Linear(64, 256)
        self.layer2 = nn.Linear(256, 256)
        self.layer3 = nn.Linear(256, 128)
        
        self.output_layer = nn.Linear(128, 1)

    def forward(self, state):
        x = F.relu(self.state_layer(state))
        x = F.relu(self.layer1(x))
        x = F.relu(self.layer2(x))
        x = F.relu(self.layer3(x))
        v_value = self.output_layer(x)
        return v_value
