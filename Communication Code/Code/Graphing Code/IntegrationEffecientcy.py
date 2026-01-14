import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def parse_experiment_file(filepath):
    """
    Parses metadata and dynamic headers for the Quantum-Subradience format.
    """
    sweep_time = None
    viz_enabled = None
    header_row_index = None
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        # Handle scientific notation: +2.00000000E-002 -> 0.02
        if "Sweep Time (ms):" in line:
            try:
                sweep_time = float(line.split(':')[-1].strip())
            except: pass
        
        if "visualization_enabled:" in line:
            viz_enabled = "True" in line or "true" in line
            
        if line.startswith("Timestamp,"):
            header_row_index = i
            break

    if header_row_index is None or sweep_time is None:
        return None

    df = pd.read_csv(filepath, skiprows=header_row_index)
    
    # Required fields
    cols = ['Absolute Cycle Time (ms)', 'Instrumental Cycle Time (ms)', 'Effective Integration (%)']
    if not all(c in df.columns for c in cols):
        return None

    return {
        'Sweep Time': sweep_time,
        'Viz': "Enabled" if viz_enabled else "Disabled",
        'Abs Cycle': df['Absolute Cycle Time (ms)'].mean(),
        'Inst Cycle': df['Instrumental Cycle Time (ms)'].mean(),
        'Eff Integ': df['Effective Integration (%)'].mean()
    }

def run_normalized_analysis(folder_path):
    results = []
    files = glob.glob(os.path.join(folder_path, "*.csv"))
    
    for f in files:
        data = parse_experiment_file(f)
        if data: results.append(data)
            
    if not results:
        print("No valid data found.")
        return

    df = pd.DataFrame(results)
    
    # NORMALIZATION: 
    # We divide cycle times by the sweep time to see the ratio/overhead factor.
    # This helps identify if the 'increase' is proportional or a fixed lag.
    df['Abs Cycle Norm'] = df['Abs Cycle'] / df['Sweep Time']
    df['Inst Cycle Norm'] = df['Inst Cycle'] / df['Sweep Time']
    
    generate_connected_plot(df)

def generate_connected_plot(df):
    plt.style.use('seaborn-v0_8-muted')
    fig, ax1 = plt.subplots(figsize=(12, 8), dpi=100)
    ax2 = ax1.twinx()

    # Configuration for plotting
    # Format: (column_key, label, axis, color_index)
    plot_config = [
        ('Abs Cycle Norm', 'Normalized Absolute Cycle', ax1, 0),
        ('Inst Cycle Norm', 'Normalized Instrumental Cycle', ax1, 1),
        ('Eff Integ', 'Effective Integration (%)', ax2, 2)
    ]
    
    colors = {
        'Enabled': ['#1F618D', '#1E8449', '#76448A'], 
        'Disabled': ['#5DADE2', '#52BE80', '#AF7AC5']
    }

    for col, label, ax, c_idx in plot_config:
        for viz_status in ['Enabled', 'Disabled']:
            subset = df[df['Viz'] == viz_status].sort_values('Sweep Time')
            if subset.empty: continue
            
            x = subset['Sweep Time']
            y = subset[col]
            
            color = colors[viz_status][c_idx]
            style = '-' if viz_status == 'Enabled' else '--'
            marker = 'o' if viz_status == 'Enabled' else 's'
            
            ax.plot(x, y, label=f"{label} ({viz_status})", 
                    linestyle=style, color=color, marker=marker, 
                    linewidth=2, markersize=5, alpha=0.9)

    # Formatting
    ax1.set_xlabel('Sweep Time (ms)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Normalized Time (Cycle / Sweep)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Effective Integration (%)', fontsize=12, fontweight='bold', color='#76448A')
    
    plt.title('Normalized Performance Trends vs. Sweep Time\n(Values normalized to local Sweep Time)', fontsize=14, pad=15)
    ax1.grid(True, linestyle=':', alpha=0.6)
    
    # Legend
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc='upper left', bbox_to_anchor=(1.15, 1))

    plt.tight_layout()
    plt.savefig("Normalized_Experiment_Analysis.png", bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    run_normalized_analysis("ExperimentLogs")