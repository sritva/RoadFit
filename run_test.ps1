$ErrorActionPreference = "Stop"

# Activate environment
. .\venv\Scripts\Activate.ps1

Write-Host "1. Downloading Graph..."
python .\src\graph_engine\download_graph.py --place "Koramangala, Bengaluru, Karnataka, India" --output "data"

Write-Host "2. Enhancing Features..."
python .\src\graph_engine\feature_extractor.py --input "data\koramangala_bengaluru_karnataka_india_drive.graphml" --output "data\koramangala_enhanced.graphml"

Write-Host "3. Pruning Graph for an SUV (Width 2.2m, Height 2.5m, Weight 2.5t)..."
python .\src\graph_engine\graph_pruner.py --input "data\koramangala_enhanced.graphml" --output "data\koramangala_pruned_suv.graphml" --width 2.2 --height 2.5 --weight 2.5

Write-Host "4. Training Baseline ML Model..."
python .\src\models\baseline_predictor.py --graph "data\koramangala_enhanced.graphml" --output "experiments\baseline_model.pkl"

Write-Host "Test Pipeline Completed!"
