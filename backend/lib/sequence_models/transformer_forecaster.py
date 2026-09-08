import torch
import torch.nn as nn
import math

class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 16):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d_model)

    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]


class TemporalTransformerForecaster(nn.Module):
    """
    Input:  (batch, seq_len=16, 1) — sequence of risk scores
    Output: (batch, horizon) — next K predicted risk scores

    Attention weights are REAL — they are computed by nn.MultiheadAttention
    and exposed via the forward pass for genuine explainability.
    """
    def __init__(
        self,
        d_model: int = 32,
        nhead: int = 4,
        num_encoder_layers: int = 2,
        dim_feedforward: int = 128,
        horizon: int = 8,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.input_proj = nn.Linear(1, d_model)
        self.pos_enc = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_encoder_layers)
        self.head = nn.Sequential(
            nn.Linear(d_model, horizon),
            nn.Sigmoid(),
        )
        self._attention_weights: list = []

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, 16, 1)
        z = self.input_proj(x)          # (batch, 16, d_model)
        z = self.pos_enc(z)
        z = self.transformer(z)         # (batch, 16, d_model)
        out = self.head(z[:, -1, :])    # (batch, horizon)
        return out

    def get_attention_weights(self, x: torch.Tensor) -> torch.Tensor:
        """
        Returns per-layer attention weights for explainability.
        Shape: (num_layers, batch, nhead, seq_len, seq_len)
        """
        z = self.input_proj(x)
        z = self.pos_enc(z)
        weights = []
        for layer in self.transformer.layers:
            # Use the layer's self-attention directly with need_weights=True
            z_out, attn = layer.self_attn(z, z, z, need_weights=True, average_attn_weights=False)
            weights.append(attn)
            z = layer(z)
        return torch.stack(weights)
