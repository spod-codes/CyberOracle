"""
train_sequence.py — trains LSTM and Temporal Transformer forecasters on the
pre-generated sequence data from train.py.

Run this AFTER train.py has populated:
  backend/data/sequence_training_data_k{5,8,12,20}.npz

Each .npz contains:
  X: (N, 16) — 16-window sequences of risk scores
  y: (N, K)  — next K risk scores to predict

Saves trained weights to:
  backend/lstm_forecaster_k{K}.pt
  backend/transformer_forecaster_k{K}.pt
"""
import os
import sys
import math
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, random_split

# Allow imports from backend/
sys.path.insert(0, os.path.dirname(__file__))
from lib.sequence_models.lstm_forecaster import LSTMForecaster
from lib.sequence_models.transformer_forecaster import TemporalTransformerForecaster

HORIZONS = [5, 8, 12, 20]
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUT_DIR = os.path.dirname(__file__)

EPOCHS = 60
BATCH_SIZE = 128
LR = 3e-4
PATIENCE = 8  # early stopping patience


def load_data(k: int):
    path = os.path.join(DATA_DIR, f"sequence_training_data_k{k}.npz")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Sequence data not found at {path}. Run train.py first."
        )
    d = np.load(path)
    X = torch.tensor(d["X"], dtype=torch.float32).unsqueeze(-1)  # (N, 16, 1)
    y = torch.tensor(d["y"], dtype=torch.float32)                # (N, K)
    return X, y


def augment(X: torch.Tensor, y: torch.Tensor) -> tuple:
    """
    Data augmentation to prevent LSTM output collapse:
    - Add Gaussian noise to inputs
    - Random amplitude scaling
    - Temporal jitter (circular shift)
    This forces the model to learn the shape of the sequence, not just predict the mean.
    """
    X_aug = X.clone()
    y_aug = y.clone()

    # Gaussian noise (sigma = 0.03 of the [0,1] range)
    X_aug = X_aug + torch.randn_like(X_aug) * 0.03
    y_aug = y_aug + torch.randn_like(y_aug) * 0.02

    # Random amplitude scaling [0.85, 1.15]
    scale = 0.85 + torch.rand(X_aug.shape[0], 1, 1) * 0.30
    X_aug = X_aug * scale
    y_aug = y_aug * scale.squeeze(-1)

    return X_aug.clamp(0, 1), y_aug.clamp(0, 1)


def variance_penalty(pred: torch.Tensor) -> torch.Tensor:
    """
    Penalise near-constant outputs. Rewards predictions that have variance,
    which directly combats output collapse.
    """
    pred_var = pred.var(dim=0).mean()   # variance across batch, averaged over steps
    # We want high variance, so penalty = -var (add with negative weight)
    return -pred_var


def train_model(model, X, y, model_name: str, k: int):
    dataset = TensorDataset(X, y)
    n_val = max(1, int(len(dataset) * 0.15))
    n_train = len(dataset) - n_val
    train_ds, val_ds = random_split(dataset, [n_train, n_val],
                                    generator=torch.Generator().manual_seed(42))
    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_dl   = DataLoader(val_ds,   batch_size=BATCH_SIZE)

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)

    # Warmup + cosine schedule — warmup prevents early collapse
    def lr_lambda(step):
        warmup_steps = 5
        if step < warmup_steps:
            return float(step + 1) / warmup_steps
        progress = (step - warmup_steps) / max(1, EPOCHS - warmup_steps)
        return 0.5 * (1.0 + math.cos(math.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    criterion = nn.HuberLoss(delta=0.1)  # less sensitive to outliers than MSE, avoids mean collapse

    best_val = float("inf")
    best_state = None
    no_improve = 0

    print(f"\n[{model_name} K={k}] Training on {n_train} seqs, validating on {n_val}")

    for epoch in range(1, EPOCHS + 1):
        model.train()
        train_loss = 0.0
        for xb, yb in train_dl:
            # Apply augmentation during training
            xb_a, yb_a = augment(xb, yb)
            optimizer.zero_grad()
            pred = model(xb_a)
            mse  = criterion(pred, yb_a)
            vpen = variance_penalty(pred)
            # Variance penalty weight 0.01 — just enough to break mean collapse
            loss = mse + 0.01 * vpen
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            optimizer.step()
            train_loss += mse.item() * len(xb)
        train_loss /= n_train
        scheduler.step()

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for xb, yb in val_dl:
                pred = model(xb)
                val_loss += criterion(pred, yb).item() * len(xb)
        val_loss /= n_val

        if epoch % 10 == 0 or epoch == 1:
            print(
                f"  Epoch {epoch:3d}/{EPOCHS}  "
                f"train={train_loss:.5f}  val={val_loss:.5f}"
            )

        if val_loss < best_val - 1e-6:
            best_val = val_loss
            best_state = {k_: v.clone() for k_, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= PATIENCE:
                print(f"  Early stopping at epoch {epoch} (best val={best_val:.5f})")
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    save_path = os.path.join(OUT_DIR, f"{model_name.lower().replace(' ', '_')}_k{k}.pt")
    torch.save(model.state_dict(), save_path)
    print(f"  Saved -> {save_path}  (best val={best_val:.5f})")
    return best_val


def main():
    print("=" * 60)
    print("CyberOracle — Sequence Model Trainer")
    print("=" * 60)

    all_results = []

    for k in HORIZONS:
        try:
            X, y = load_data(k)
        except FileNotFoundError as e:
            print(f"  SKIP K={k}: {e}")
            continue

        n_samples = len(X)
        print(f"\n[K={k}] Loaded {n_samples} sequences (16 -> {k} steps)")

        if n_samples < 50:
            print(f"  SKIP K={k}: too few samples ({n_samples}) to train reliably.")
            continue

        # ── Train LSTM ──────────────────────────────────────────
        lstm = LSTMForecaster(hidden_size=64, num_layers=2, horizon=k)
        lstm_loss = train_model(lstm, X, y, "lstm_forecaster", k)
        all_results.append(("LSTM",        k, lstm_loss))

        # ── Train Transformer ────────────────────────────────────
        tfm = TemporalTransformerForecaster(
            d_model=32, nhead=4, num_encoder_layers=2,
            dim_feedforward=128, horizon=k, dropout=0.1
        )
        tfm_loss = train_model(tfm, X, y, "transformer_forecaster", k)
        all_results.append(("Transformer", k, tfm_loss))

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE — Summary")
    print("=" * 60)
    for model_name, k, val_loss in all_results:
        print(f"  {model_name:<14} K={k:<3}  val MSE = {val_loss:.6f}")

    print("\nAll sequence model weights saved to backend/")
    print("You can now select 'LSTM State Encoder' or 'Temporal Transformer'")
    print("in the UI and receive real trained forecasts.")


if __name__ == "__main__":
    main()
