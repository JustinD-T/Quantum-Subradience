from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
import csv

SWEEP_TIME = 2.5 # seconds

def load_data(path):
    df = pd.read_csv(path, comment='#')
    cols = df.columns

    freq_cols = [col for col in cols if 'Hz' in col]

    amp_df = df[freq_cols]

    return amp_df

def plot_data(df_arr):
    for label, df in df_arr:
        avg_df = df.expanding().mean()
        var = avg_df.std(axis = 1)**2
        time = np.arange(SWEEP_TIME, SWEEP_TIME * (len(var)+1), SWEEP_TIME ) / 60
        plt.plot(time, var, label=label, alpha=0.8)
    plt.xlabel('LOG - Integrated Time (Minutes)')
    plt.ylabel('LOG - Mean Variance')
    plt.xscale('log')
    plt.yscale('log')
    plt.legend()
    plt.suptitle('Variance versus Integration Time (Background)')
    plt.savefig(r'Lab Notes\Tests\Noise Floor\Plots\variance_over_time.png')

if __name__ == "__main__":
    path1000 = r'Lab Notes\Tests\Noise Floor\Data\BackgroundRun1.csv'
    path500 = r'Lab Notes\Tests\Noise Floor\Data\BackgroundRun2.csv'
    data = [('1000 pts', load_data(path1000)), ('500 pts', load_data(path500))]
    plot_data(data)
    
    

