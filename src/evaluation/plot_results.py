"""
RoadFit-X: Academic Plotting Engine
Generates:
  1. Pareto Curve (ETTP % vs TRR)
  2. Cumulative Distribution Function (CDF) of Route Clearance Margins
"""
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import numpy as np

def generate_plots(csv_path: str):
    df = pd.read_csv(csv_path)
    
    # Filter only feasible routes for plotting
    df_feasible = df[df['Feasible'] == 1]
    
    # Set seaborn style for academic quality
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.5)
    
    # Define a clean color palette
    palette = {
        "B0 (Unconstrained)": "#e74c3c",       # Red
        "B1 (Hard Constrained)": "#e67e22",    # Orange
        "RoadFit-X (Strict)": "#27ae60",       # Green
        "RoadFit-X (Conservative)": "#2980b9", # Blue
        "RoadFit-X (Exploratory)": "#8e44ad"   # Purple
    }

    # ---------------------------------------------------------
    # Figure 1: ETTP vs TRR Pareto Curve
    # ---------------------------------------------------------
    plt.figure(figsize=(10, 7))
    sns.scatterplot(
        data=df_feasible, 
        x="ETTP_%", y="TRR", 
        hue="Model", style="Model",
        palette=palette,
        s=100, alpha=0.7
    )
    
    # Calculate group means to plot the macro Pareto frontier
    group_means = df_feasible.groupby('Model')[['ETTP_%', 'TRR']].mean().reset_index()
    
    plt.scatter(
        group_means["ETTP_%"], group_means["TRR"], 
        color='black', marker='X', s=200, zorder=5, label="Cluster Mean"
    )

    plt.title("Safety-Efficiency Pareto Frontier (100 Stratified OD Pairs)", fontweight='bold')
    plt.xlabel("Excess Travel Time Penalty (ETTP) % (Lower is Better)")
    plt.ylabel("Tail-Risk Ratio (TRR) (Lower is Safer)")
    plt.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5, label='Risk-Free Baseline (TRR=1)')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig("pareto_curve.png", dpi=300, bbox_inches='tight')
    print("Saved pareto_curve.png")

    # ---------------------------------------------------------
    # Figure 2: CDF of Route Clearance Margins
    # ---------------------------------------------------------
    plt.figure(figsize=(10, 7))
    sns.ecdfplot(
        data=df_feasible, 
        x="MinClearance_m", 
        hue="Model", 
        palette=palette,
        linewidth=3
    )

    plt.title("Cumulative Distribution of Route Bottleneck Clearance", fontweight='bold')
    plt.xlabel("Minimum Lateral Clearance (meters)")
    plt.ylabel("Cumulative Probability")
    plt.axvline(x=0.0, color='red', linestyle='--', linewidth=2, label='Collision Boundary (0.0m)')
    plt.axvline(x=0.2, color='orange', linestyle=':', linewidth=2, label='Safety Margin (0.2m)')
    
    # Optional legend fix for custom axvline if needed, but standard legend works well enough
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig("clearance_cdf.png", dpi=300, bbox_inches='tight')
    print("Saved clearance_cdf.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate RoadFit-X Academic Plots")
    parser.add_argument("--csv", type=str, default="results_100_od.csv", help="Path to experimental results CSV")
    args = parser.parse_args()
    
    generate_plots(args.csv)
