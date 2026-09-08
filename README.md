# CyberOracle

An advanced, real-time Machine Learning pipeline for offline adaptive temporal network-state inference. CyberOracle ingests raw network telemetry, dynamically vectors it, and evaluates temporal risk using a unified, mathematically bounded Machine Learning architecture.

## Features

- **True ML Anomaly Detection:** Powered by a pre-trained Scikit-Learn `IsolationForest` fitted on 395,000 vectors from the real-world CIC-IDS-2018 and CTU-13 botnet datasets.
- **Dynamic Feature Ingestion:** Automatically maps and processes CSV files regardless of shape, projecting telemetry (Bytes, Durations, Port mapping matrices, and TCP flag frequencies) into strict ML tensors.
- **AI Interpretability (Surrogate Model):** Employs a dynamic `DecisionTreeRegressor` surrogate to extract true feature importances (Gini bounds), explaining exactly *why* a flow was flagged.
- **Statistical Forecasting:** Implements Holt-Winters Exponential Smoothing via `statsmodels` to forecast forward-looking trajectory bounds and threat momentum.
- **Kernel Evaluation CLI:** A native command-line interface that rips open the `.pkl` ensemble to dump real-time Confusion Matrices and Classification Reports directly to the host OS.

## Tech Stack

- **Frontend:** React, TypeScript, TailwindCSS, Vite
- **Backend:** Python, FastAPI, Scikit-Learn, Pandas, Uvicorn
- **Database:** MongoDB
- **Machine Learning:** IsolationForest, DecisionTreeRegressor, statsmodels (Exponential Smoothing)

## Running the Application

### 1. Database
Ensure MongoDB is running locally on port `27017`.
```bash
mongod --dbpath "C:\Users\spodc\mongodb\data\db"
```

### 2. Backend
Install the requirements and run the FastAPI server:
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn server:app --port 8001
```

### 3. Frontend
Start the React UI:
```bash
cd frontend
npm install
npm run dev
```
Navigate to `http://localhost:3000` to interact with the Dashboard.

## Model Training
The model is pre-trained on a unified blend of the CIC-IDS-2018 and CTU-13 datasets. If you have new data, you can retrain the model locally using the included pipeline:
```bash
cd backend
python train.py
```
This will automatically generate a new `cic_ids_model.pkl` weights file.
