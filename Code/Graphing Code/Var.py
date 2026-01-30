from Utils import load_data
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

def Rolling_Variance(spec_df, sweep_time=2.5):
    vars = spec_df.expanding(axis=0).mean()
    mean_var = vars.var(axis=1)

    taus = np.arange(1, len(mean_var)+1) * sweep_time

    return taus, mean_var, vars

def plot_rolling_noise_reduction(spec_df):
    taus, mean_var, vars = Rolling_Variance(spec_df)

    plt.figure(figsize=(10, 6))
    plt.loglog(taus, mean_var, label='Mean Rolling Variance', color='black', linewidth=2)

    # for col in vars.columns:
    #     plt.loglog(taus, vars[col], alpha=0.01, color='blue')

    plt.xlabel('Tau (s)')
    plt.ylabel('Variance')
    plt.title('Rolling Variance of Spectrum Over Time')
    plt.legend()
    plt.grid(True, which="both", ls="--")
    plt.show()

if __name__ == "__main__":
    path = r'Code\Graphing Code\ExperimentLog_20260129-123129.csv'
    _, spec = load_data(path)
    plot_rolling_noise_reduction(spec)