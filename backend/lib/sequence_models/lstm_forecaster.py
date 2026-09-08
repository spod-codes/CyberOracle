import torch
import torch.nn as nn

class LSTMForecaster(nn.Module):
    """
    Input:  (batch, seq_len=16, features=1) — sequence of risk scores
    Output: (batch, horizon) — next K predicted risk scores
    """
    def __init__(self, hidden_size: int = 64, num_layers: int = 2, horizon: int = 8):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=1,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Linear(32, horizon),
            nn.Sigmoid(),  # output in [0, 1]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, 16, 1)
        out, _ = self.lstm(x)
        # Take last hidden state
        return self.head(out[:, -1, :])  # (batch, horizon)
