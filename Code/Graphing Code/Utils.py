import pandas as pd
import csv
import numpy as np

def load_data(path):
    """
    Takes in path to experiment csv, returns metadata dict, df of headers, df of frequencies
    """

    df = pd.read_csv(path, comment='#')

    headers = [col for col in df.columns if 'Hz' not in col]
    freqs = [col for col in df.columns if 'Hz' in col]

    
    
