import torch
import torch.nn as nn
import torch.nn.functional as F

class ActorMLP(nn.Module):
    """
    The Actor (Intuition).
    Reads the State (17-dimensional) and outputs 2 continuous action parameters
    (Price Multiplier and Expose Quantity Percent) mapped between [0.0, 1.0].
    """
    def __init__(self, state_dim=17, action_dim=2):
        super(ActorMLP, self).__init__()
        
        # Dense layers for state mapping
        self.layer1 = nn.Linear(state_dim, 256)
        self.layer2 = nn.Linear(256, 256)
        self.layer3 = nn.Linear(256, 128)
        self.output_layer = nn.Linear(128, action_dim)
        
        # Dynamic policy standard deviation parameter
        self.log_std = nn.Parameter(torch.full((1, action_dim), 0.0))
        
    def forward(self, state):
        # Activation ReLU for hidden layers
        x = F.relu(self.layer1(state))
        x = F.relu(self.layer2(x))
        x = F.relu(self.layer3(x))
        
        # Sigmoid restricts actor output parameters to [0.0, 1.0]
        # action_dim outputs: [price_multiplier_pct, expose_quantity_pct]
        action_mean_percent = torch.sigmoid(self.output_layer(x))
        
        return action_mean_percent, self.log_std


class CriticMLP(nn.Module):
    """
    The Critic (The Financial Evaluator).
    Reads the State and predicts the baseline state value (V-Value / expected future rewards).
    """
    def __init__(self, state_dim=17):
        super(CriticMLP, self).__init__()
        
        self.state_layer = nn.Linear(state_dim, 64)
        self.layer1 = nn.Linear(64, 256)
        self.layer2 = nn.Linear(256, 256)
        self.layer3 = nn.Linear(256, 128)
        
        # Output is a single float representing state baseline value (V-value)
        self.output_layer = nn.Linear(128, 1)

    def forward(self, state):
        x = F.relu(self.state_layer(state))
        x = F.relu(self.layer1(x))
        x = F.relu(self.layer2(x))
        x = F.relu(self.layer3(x))
        
        v_value = self.output_layer(x)
        return v_value
