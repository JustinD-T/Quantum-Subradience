import csv
import pandas as pd
import os


def open_test_file(file_path):
    # Open data
    df = pd.read_csv(file_path, comment='#')
    # Open Header
    with open(file_path, 'r') as f:
        reader = csv.reader(f)
        header = []
        for row in reader:
            if row and row[0].startswith('#'):
                header.append(row)
            else:
                break
    
    return df, header

def split_test_file(df, header, window_size=10, threshold=0.01):
    """
    Splits the test file into three parts: depressurization, transient, and repressurization.

    Args:
        df (pd.DataFrame): The input dataframe with a 'Pressure' column.
        header (list): The header information from the file (not used in this function).
        window_size (int): The number of successive points to confirm a trend change.
        threshold (float): The tolerance for considering the pressure as 'constant'.

    Returns:
        tuple: A tuple containing three dataframes:
               (df_depressurization, df_transient, df_repressurization).
               Returns (None, df, None) if split points are not found.
    """
    pressure = df['Pressure']
    diff = pressure.diff()

    # State: -1 for decreasing, 0 for constant, 1 for increasing
    state = pd.Series(0, index=df.index)
    state[diff > threshold] = 1
    state[diff < -threshold] = -1

    # Find the end of the initial depressurization phase
    # This is the last point in the first long sequence of decreasing/constant pressure
    end_depress = -1
    for i in range(len(state) - window_size):
        # Look for a block that is NOT decreasing/constant
        if not all(s <= 0 for s in state.iloc[i:i + window_size]):
            end_depress = i -1
            break
    
    if end_depress < 0: # No clear end to depressurization found
        return (df, pd.DataFrame(columns=df.columns), pd.DataFrame(columns=df.columns))

    # Find the start of the final repressurization phase
    # This is the first point of the last long sequence of increasing/constant pressure
    start_repress = -1
    for i in range(len(state) - window_size, 0, -1):
         # Look for a block that IS increasing/constant
        if all(s >= 0 for s in state.iloc[i:i + window_size]):
            start_repress = i
        # Once we find a non-increasing block, we've gone too far, so stop
        elif start_repress != -1:
            break

    if start_repress <= end_depress: # No clear repressurization or transient phase found
        return (df, pd.DataFrame(columns=df.columns), pd.DataFrame(columns=df.columns))

    # Split into three dataframes
    df_depressurization = df.iloc[:end_depress + 1].reset_index(drop=True)
    df_transient = df.iloc[end_depress + 1:start_repress].reset_index(drop=True)
    df_repressurization = df.iloc[start_repress:].reset_index(drop=True)

    return df_depressurization, df_transient, df_repressurization

def save_files(df_pressurization, df_depressurization, header, base_path, df_transient=None):

    # Create a directory with the name of the original file
    dir_path = os.path.splitext(base_path)[0]
    os.makedirs(dir_path, exist_ok=True)
    base_filename = os.path.basename(dir_path)

    def save_dataframe(df, suffix, output_dir):
        if df is not None and not df.empty:
            file_path = os.path.join(output_dir, f"{base_filename}{suffix}")
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(header)
                df.to_csv(f, index=False)

    # Save pressurization, depressurization, and transient phases
    save_dataframe(df_pressurization, '_pressurization.csv', dir_path)
    save_dataframe(df_depressurization, '_depressurization.csv', dir_path)
    save_dataframe(df_transient, '_transient.csv', dir_path)


if __name__ == "__main__":
    import argparse

    args = argparse.ArgumentParser(description="Split test data file into pressurization, transient, and depressurization phases.")
    args.add_argument("file_path", help="Path to the test data file")
    args.add_argument("--st", default=False, action='store_true', help="Whether to save transient phase in a file")
    
    file_path = r'ExperimentLogs\ExperimentLog_20260120-135313.csv'
    df, header = open_test_file(file_path)
    df_pressurization, df_transient, df_depressurization = split_test_file(df, header)
    if args.st:
        save_files(df_pressurization, df_depressurization, header, file_path, df_transient)
    else:
        save_files(df_pressurization, df_depressurization, header, file_path)