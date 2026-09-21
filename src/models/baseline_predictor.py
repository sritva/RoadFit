import osmnx as ox
import networkx as nx
import argparse
import os
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

def generate_training_data(G):
    """
    Simulate target data since we don't have real telemetry.
    We will create a synthetic target 'obstruction_risk_score' based on
    width, highway type, length, etc.
    """
    records = []
    
    # Simple mapping for highway types to ordinal for baseline
    highway_mapping = {
        'motorway': 1, 'trunk': 2, 'primary': 3, 'secondary': 4,
        'tertiary': 5, 'unclassified': 6, 'residential': 7, 
        'living_street': 8, 'service': 9, 'track': 10
    }
    
    for u, v, d in G.edges(data=True):
        hw = d.get('highway', 'unclassified')
        if isinstance(hw, list): hw = hw[0]
        
        hw_encoded = highway_mapping.get(hw, 6)
        width = float(d.get('est_width', 4.0))
        length = float(d.get('length', 10.0))
        
        # Synthetic Risk Score: Narrower roads + higher hw_encoded (residential/living) = high risk
        # This gives our model something plausible to learn.
        synthetic_risk = (hw_encoded * 2.0) - width + (length * 0.01)
        synthetic_risk = max(0, synthetic_risk) # ensure positive
        
        record = {
            'highway_type': hw_encoded,
            'est_width': width,
            'length': length,
            'target_risk': synthetic_risk
        }
        records.append(record)
        
    return pd.DataFrame(records)

def train_baseline_model(graph_path: str, model_output_path: str):
    print(f"Loading graph from {graph_path} for data extraction...")
    G = ox.load_graphml(graph_path)
    
    print("Generating synthetic training data...")
    df = generate_training_data(G)
    
    X = df[['highway_type', 'est_width', 'length']]
    y = df['target_risk']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training RandomForestRegressor Baseline...")
    model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
    model.fit(X_train, y_train)
    
    from sklearn.metrics import root_mean_squared_error
    y_pred = model.predict(X_test)
    rmse = root_mean_squared_error(y_test, y_pred)
    
    print(f"Model trained! Test RMSE: {rmse:.4f}")
    
    # Save model
    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    joblib.dump(model, model_output_path)
    print(f"Baseline model saved to {model_output_path}")
    
    return model

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train baseline ML model for obstruction risk")
    parser.add_argument("--graph", type=str, required=True, help="Input GraphML file path for training data")
    parser.add_argument("--output", type=str, default="experiments/baseline_model.pkl", help="Output path for the trained model")
    
    args = parser.parse_args()
    train_baseline_model(args.graph, args.output)
