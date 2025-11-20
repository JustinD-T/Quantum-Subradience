from matplotlib import pyplot as plt
import pandas as pd
import numpy as np

def open_csv(path):
    with open(path, 'r') as f:
        df = pd.read_csv(f)
    return df

def normalize_timestamps(df):
    if 'timestamp' in df.columns:
        df['Time'] = pd.to_datetime(df['timestamp'])
        start_time = df['Time'].iloc[0]
        df['Time'] = (df['Time'] - start_time).dt.total_seconds()
    else:
        df['Time'] = np.arange(len(df))
    return df

def plot_data(df):
    plt.figure(figsize=(8, 6))
    plt.plot(df['Time'], df['pressure'], marker='o', linestyle='-')
    plt.yscale('log')
    plt.xscale('log')
    plt.xlabel('Time (s)')
    plt.ylabel('pressure (mbar)')
    plt.title('Vacuum pressure Over Time')
    plt.grid(True, which="both", ls="--")
    plt.tight_layout()
    plt.show()

def update_plot(csv_path, interval=1.0):
    # initial read to set up the plot and a stable base time
    df = open_csv(csv_path)
    if 'timestamp' in df.columns:
        times = pd.to_datetime(df['timestamp'])
        base_time = times.iloc[0]
        df['Time'] = (times - base_time).dt.total_seconds()
    else:
        base_time = None
        df['Time'] = np.arange(len(df))

    if 'pressure' not in df.columns:
        raise ValueError("CSV must contain a 'pressure' column")

    plt.ion()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_yscale('log')
    line, = ax.plot(df['Time'], df['pressure'], marker='o', linestyle='-')
    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('pressure (mbar)')
    ax.set_title('Vacuum pressure Over Time')
    ax.grid(True, which="both", ls="--")
    fig.tight_layout()
    ax.relim()
    ax.autoscale_view()

    try:
        while True:
            df = open_csv(csv_path)
            if 'timestamp' in df.columns and base_time is not None:
                df['Time'] = (pd.to_datetime(df['timestamp']) - base_time).dt.total_seconds()
            else:
                df['Time'] = np.arange(len(df))

            # update the plotted data
            line.set_data(df['Time']/60/60, df['pressure'])
            ax.relim()
            ax.autoscale_view()

            fig.canvas.draw_idle()
            plt.pause(interval)
    except KeyboardInterrupt:
        plt.ioff()
        # plot remains open; user interrupted updating

if __name__ == '__main__':
    csv_file_path = 'vacuum_log.csv'  # path to your CSV file
    update_interval = 2.0  # seconds
    update_plot(csv_file_path, update_interval)