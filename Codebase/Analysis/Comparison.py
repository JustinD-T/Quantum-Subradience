""" 
methods for taking in n measurements and comparing them
"""
from Utilities import *
from Graphing import *
from SignalSim import *

from matplotlib import pyplot as plt
import numpy as np

class Comparison:

    def __init__(self, paths, savepath, normalize, processing_settings=None):
        "Data is accessed by a dict with keys being a ref and values being meta, powers, etc"

        self.save_path = savepath
        self.processing_settings = processing_settings

        # Load in all data
        self.init_data(paths, normalize)

        print("Data Initialized:")
        print(f"{len(self.refs)} Experiments, References: {self.refs}")

        # Allow user to rename references
        new_refs = []
        for ref in self.refs:
            new = input(f"Rename '{ref}' to: ")
            new_refs.append(new)

        # Change keys in data dict to new refs
        self.data = {new_refs[i] : self.data[self.refs[i]] for i in range(len(self.refs))}
        self.refs = new_refs

        # Process data
        self.process_data()

    def compare(self):
        """Runs all comparisons and saves them to the given path"""

        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path, exist_ok=True)

        self.comparePressures()
        self.compareSignals()

    def init_data(self, paths, normalize):
        """Takes in a list of paths and initialzies them to the class"""
        
        refs = []
        data = {}
        for path in paths:
            powers, freqs, pressures, meta = loadData(path)
            refs.append(meta['Experiment Description'])
            data[meta['Experiment Description']] = {
                'powers' : powers,
                'freqs' : freqs,
                'pressures' : pressures,
                'meta' : meta
            }

        if normalize:
            min_time = min([data[ref]['powers'].shape[1]*float(data[ref]['meta']['Sweep Time (ms)']) for ref in refs])
            for ref in refs:
                n_meas = int(min_time / float(data[ref]['meta']['Sweep Time (ms)']))
                data[ref]['powers'] = data[ref]['powers'][:, :n_meas]
                data[ref]['pressures'] = data[ref]['pressures'][:n_meas]
        
        self.refs = refs
        self.data = data
    
    def process_data(self):

        new_pows = {}
        new_freqs = {}

        # truncate ends
        if self.processing_settings['TRUNCATE_ENDS'] is not None:
            for ref in self.refs:
                freqs = self.data[ref]['freqs']
                freq_mask = (freqs >= freqs.min() + self.processing_settings['TRUNCATE_ENDS']) & (freqs <= freqs.max() - self.processing_settings['TRUNCATE_ENDS'])
                self.data[ref]['freqs'] = freqs[freq_mask]
                self.data[ref]['powers'] = self.data[ref]['powers'][freq_mask, :]

        # center offset
        c_off = self.processing_settings['OFFSET_CENTER'] if self.processing_settings['OFFSET_CENTER'] is not None else 0
            
        # Skip cleaning routine
        for ref in self.refs:

            # Subtract baseline
            freqs = self.data[ref]['freqs']
            pow = subtractBaseline(self.data[ref]['powers'], freqs, (max(freqs)+min(freqs))/2+c_off, self.processing_settings['sigma'], self.processing_settings['deg'], self.processing_settings['n_sub'])

            # bin data
            pows, freqs = binData(pow, freqs, self.processing_settings['bin_factor'])

            new_pows[ref] = pows
            new_freqs[ref] = freqs
        
        # Set processed data to class
        for ref in self.refs:
            self.data[ref]['powers'] = new_pows[ref]
            self.data[ref]['freqs'] = new_freqs[ref]


    # --- COMPARISONS --- 

    def comparePressures(self):
        for exp in self.refs:
            pressures = self.data[exp]['pressures']
            time_axis = float(self.data[exp]['meta']['Sweep Time (ms)']) * np.arange(1, pressures.shape[0]+1, 1)

            plt.plot(time_axis, pressures, label=exp)
        
        plt.xlabel("Time (s)")
        plt.ylabel("Pressure (mbar)")
        plt.title("Pressure Comparison")
        plt.yscale('log')
        plt.grid()
        plt.legend()
        plt.savefig(os.path.join(self.save_path, "Pressure_Comparison.png"), dpi=300)
        plt.close()

    def compareSignals(self, sum_data=False):
        fig, ax = plt.subplots(figsize=(10, 6), facecolor='black')
        ax.set_facecolor('black')

        for exp in self.refs:
            powers = self.data[exp]['powers']
            spectral_axis = self.data[exp]['freqs'] - float(self.data[exp]['meta']['Center Frequency (Hz)'])
            sigma = self.processing_settings['sigma']

            # Integrate or average across measurements
            signal = powers.sum(axis=1) if sum_data else powers.mean(axis=1)

            # Outside-central-region mask for noise statistics
            outside_mask = (spectral_axis < -sigma) | (spectral_axis > sigma)
            signal_mean = np.mean(signal[outside_mask])
            signal_std = np.std(signal[outside_mask])

            # Plot signal and its noise mean
            line = ax.plot(spectral_axis, signal, linewidth=1, label=exp)
            color = line[0].get_color()

            ax.axhline(signal_mean, color=color, linestyle='--', linewidth=0.8,
                    alpha=0.8, label=f'{exp} — noise mean')
            ax.axhline(signal_mean + 3 * signal_std, color=color, linestyle=':',
                    linewidth=0.8, alpha=0.7, label=f'{exp} — ±3σ')
            ax.axhline(signal_mean - 3 * signal_std, color=color, linestyle=':',
                    linewidth=0.8, alpha=0.7)

        # Central region band
        ax.axvspan(-self.processing_settings['sigma'], self.processing_settings['sigma'],
                color='green', alpha=0.15, label=r'$\pm \sigma_{signal}$ Region')
        ax.axhline(0, color='white', linestyle='--', linewidth=0.5, alpha=0.4)

        ax.set_xlabel('Frequency (Hz)', color='white')
        ax.set_ylabel('Power (W)', color='white')
        ax.set_title('Integrated Signal Comparison', color='white')

        for spine in ax.spines.values():
            spine.set_color('white')
        ax.tick_params(colors='white')
        ax.legend(facecolor='black', labelcolor='white', fontsize=7)

        fig.tight_layout()
        plt.savefig(os.path.join(self.save_path, "Signal_Comparison.png"), facecolor='black', dpi=300)
        plt.close()

if __name__ == "__main__":
    
    # Currently supports the following comparisons:
        # Pressure vs Time
    
    # To add:
        # Noise Reduction Comparison

    # Useful paths
    # 1st Acetonitrile Test: "Local Experiments\Experiments\Detection Tests\Acetonitrol\Detection Test #1\HSReader_20260323-203050.csv"
    # 2nd Acetonitrile Test, with plate: "Local Experiments\Experiments\Detection Tests\Acetonitrol\Acetonitrile Detection #2\HSReader_20260324-160217_pickled_data"

    # Processing Settings
        # Setting set to None will ignore, otherwise will use the value in setting (eg. truncate_signal != False, it should =n_meas_to_cut)
    processing_settings = {
        'sigma' : 3e6,
        'deg' : 3,
        'n_sub' : 1,
        'bin_factor' : 40,
        'OFFSET_CENTER' : None, 
        'SIMULATE_SIGNAL' : None, #Unsupported currently
        'INTERPOLATE_PRESSURES' : None, #Unsupported currently
        'TRUNCATE_ENDS' : 1.5e6 #Hz from each end of spectrum, None to ignore
    }

    # Formal
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('--paths', required=True, nargs='+', default=[r''])
    parser.add_argument('--savepath', type=str, default=r'Codebase\Analysis\Comparison Results')
    parser.add_argument('--normalize', action='store_true', default=True, help="Truncate all measuements to integrated time of experiemnt with least data")
    args = parser.parse_args()

    comp = Comparison(args.paths, args.savepath, args.normalize, processing_settings=processing_settings)
    comp.compare()