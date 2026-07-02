import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

class DemandForecastMLP(nn.Module):
    """
    A simple 3-layer Multi-Layer Perceptron (MLP) for demand forecasting.
    You can easily replace the layer definitions or forward function below
    with your custom model architectures.
    """
    def __init__(self, input_dim=10, hidden_dim=64, output_dim=1):
        super(DemandForecastMLP, self).__init__()
        # Layer 1: Input to Hidden
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu1 = nn.ReLU()
        
        # Layer 2: Hidden to Hidden
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.relu2 = nn.ReLU()
        
        # Layer 3: Hidden to Output (Predicted Demand)
        self.fc3 = nn.Linear(hidden_dim, output_dim)
        
    def forward(self, x):
        out = self.fc1(x)
        out = self.relu1(out)
        out = self.fc2(out)
        out = self.relu2(out)
        out = self.fc3(out)
        return out

class ModularForecaster:
    """
    A wrapper class to manage training, prediction, saving, and loading
    of the demand forecasting model.
    """
    def __init__(self, input_dim=10, hidden_dim=64, output_dim=1, lr=0.001):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = DemandForecastMLP(input_dim, hidden_dim, output_dim).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        self.criterion = nn.MSELoss()
        
    def fit(self, X_train, y_train, epochs=100, batch_size=32, verbose=False):
        """
        Fits the model on the provided training data.
        X_train: numpy array of shape (N, input_dim)
        y_train: numpy array of shape (N, output_dim)
        """
        self.model.train()
        X_tensor = torch.FloatTensor(X_train).to(self.device)
        y_tensor = torch.FloatTensor(y_train).to(self.device)
        
        dataset = torch.utils.data.TensorDataset(X_tensor, y_tensor)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            for batch_x, batch_y in loader:
                self.optimizer.zero_grad()
                predictions = self.model(batch_x)
                loss = self.criterion(predictions, batch_y)
                loss.backward()
                self.optimizer.step()
                epoch_loss += loss.item() * batch_x.size(0)
                
            if verbose and (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs} - Loss: {epoch_loss / len(X_train):.4f}")
                
    def predict(self, X):
        """
        Runs inference on the provided feature matrix.
        X: numpy array of shape (N, input_dim) or (input_dim,)
        """
        self.model.eval()
        with torch.no_grad():
            if len(X.shape) == 1:
                X = np.expand_dims(X, axis=0)
            X_tensor = torch.FloatTensor(X).to(self.device)
            preds = self.model(X_tensor)
            return preds.cpu().numpy()
            
    def save(self, filepath):
        """ Saves model weights """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        torch.save(self.model.state_dict(), filepath)
        
    def load(self, filepath):
        """ Loads model weights """
        if os.path.exists(filepath):
            self.model.load_state_dict(torch.load(filepath, map_location=self.device, weights_only=True))
            self.model.eval()
            return True
        return False
