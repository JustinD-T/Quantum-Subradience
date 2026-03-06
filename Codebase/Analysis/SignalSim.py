import os

from Utilities import loadData, subtractBaseline

import numpy as np
import matplotlib.pyplot as plt

# I_V =
# PHI_D = 3.56e-5 # sterradians
# A_P = 0.21 # cm^2
# DELTA_V = 5 #GhZ

class SignalSim:
    def __init__(self, meta, pressures, constants):

        # Unpack data
        self.meta = meta
        self.pressures = pressures

        # Unpack constants
        self.ROI_SIGMA = constants['ROI_SIGMA']
        self.BASELINE_DEG = constants['BASELINE_DEG']
        self.CO_SIGNAL = constants['CO_SIGNAL']
        self.N_PTS = constants['N_PTS']
        self.N_MEAS = constants['N_MEAS']
        self.CENTER_FREQ = constants['CENTER_FREQ']
        self.SPAN = constants['SPAN']
        self.SWEEP_TIME = constants['SWEEP_TIME']
        self.CO_POWER = constants['CO_POWER']
        self.CO_BANDWIDTH_ATM = constants['CO_BANDWIDTH_ATM']
        self.ATM_PRESSURE = constants['ATM_PRESSURE']
        self.NOISE_STD = constants['NOISE_STD']
        self.BASELINE_COEFFS = constants['BASELINE_COEFFS']


    def COPower(self, concentration):
        # Gives the expected power for a given concentration (per measurement)
        return (self.CO_POWER * (concentration / 200)) * self.SWEEP_TIME
    
    def COBandwidth(self, pressure):
        # Gives the expected bandwidth at a given pressure
        return self.CO_BANDWIDTH_ATM * (pressure / self.ATM_PRESSURE)
    
    def COPowerAtFreq(self, concentration, pressure, freq):
        # Gives the power at a given frequency
        CO_power = self.COPower(concentration)
        CO_bandwidth = self.COBandwidth(pressure)
        return  CO_power * ( (1 / np.pi) * ( (0.5 * CO_bandwidth) / ((freq - self.CENTER_FREQ)**2 + (0.5 * CO_bandwidth)**2) ) )

    def generateCOSignal(self, pressure, concentration):
        freqs = np.linspace(self.CENTER_FREQ - self.SPAN/2, self.CENTER_FREQ + self.SPAN/2, self.N_PTS)
        signal = self.COPowerAtFreq(concentration, pressure, freqs)
        return signal

    def generateNoise(self):
        # generates a noise measurement using gaussian noise
        return np.random.normal(0, self.NOISE_STD, self.N_PTS)

    def addBaseline(self, measurement):
        """Adds a random baseline to a given measurement, using the same method as the baseline subtraction routine"""

        coeffs_idx = np.random.randint(0, self.BASELINE_COEFFS.shape[0])
        x = np.linspace(self.CENTER_FREQ - self.SPAN/2, self.CENTER_FREQ + self.SPAN/2, self.N_PTS)
        polyval = np.polyval(self.BASELINE_COEFFS[coeffs_idx, :], x)

        return measurement + polyval
    
    def generateMeasurement(self, pressure, concentration):
        
        if self.CO_SIGNAL is True:
            signal = self.generateCOSignal(pressure, concentration) * (1 + np.random.normal(-0.1, 0.1)) # add some variability to the signal power
        noise = self.generateNoise()

        measurement = self.addBaseline(signal + noise)

        return measurement
    
    def simulateFullRun(self):
        simulated_data = np.zeros((self.N_PTS, self.N_MEAS))

        for i in range(self.N_MEAS):
            print(f'Simulating measurement {i+1}/{self.N_MEAS}', end='\r')
            pressure = self.pressures[i]
            concentration = float(self.meta['initial_CO_concentration (ppm)'].replace('>', '').replace('<', '')) * (self.pressures[i] / self.pressures[0]) # Assuming concentration scales linearly with pressure
            simulated_data[:, i] = self.generateMeasurement(pressure, concentration)

        return simulated_data
    
    def getSpectralAxis(self):
        return np.linspace(self.CENTER_FREQ - self.SPAN/2, self.CENTER_FREQ + self.SPAN/2, self.N_PTS)

    def simulateExample(self):
        # Plots CO signal, noise, baseline on seperate graphs, then their combiend sum on the last
        pressure = self.pressures[len(self.pressures) // 2]
        concentration = float(self.meta['initial_CO_concentration (ppm)'].replace('>', '').replace('<', '')) * (pressure / self.pressures[0])
        
        # Get data
        signal = self.generateCOSignal(pressure, concentration)
        noise = self.generateNoise()
        baseline = self.addBaseline(np.zeros_like(signal))
        freqs = self.getSpectralAxis()

        # Plotting
        fig, axs = plt.subplots(4, 1, figsize=(10, 12), sharex=True)
        axs[0].plot(freqs, signal, color='green')
        axs[0].set_title('CO Signal')
        axs[1].plot(freqs, noise, color='red')
        axs[1].set_title('Noise')
        axs[2].plot(freqs, baseline, color='orange')
        axs[2].set_title('Baseline')
        axs[3].plot(freqs, signal + noise + baseline, color='black')
        axs[3].set_title('Combined Signal')
        plt.tight_layout()
        plt.show()



def compute_noise_std(powers, freqs, constants):
    # Gives the standard deviation of measurements
    sub_powers, coeffs = subtractBaseline(powers, freqs, constants['CENTER_FREQ'], constants['ROI_SIGMA'], deg=constants['BASELINE_DEG'], n=1, ret_coeffs=True)

    stds = np.std(sub_powers, axis=0)

    mean_stds = np.mean(stds)

    return mean_stds, coeffs

def getSimulatedData(powers, freqs, pressures, meta, sim_co=True):
    
    constants = {
    'ROI_SIGMA': 1e6,
    'BASELINE_DEG': 3,
    'CO_SIGNAL': sim_co,
    'N_PTS': int(meta['Number of Points']),
    'N_MEAS': powers.shape[1],
    'CENTER_FREQ': float(meta['Center Frequency (Hz)']),
    'SPAN': float(meta['Span']),
    'SWEEP_TIME': float(meta['Sweep Time (ms)']),
    'CO_POWER': 1e-16,
    'CO_BANDWIDTH_ATM': 3.5e9,
    'ATM_PRESSURE': 1012.25,
    }

    NOISE_STD, BASELINE_COEFFS = compute_noise_std(powers, freqs, constants)
    constants['NOISE_STD'] = NOISE_STD
    constants['BASELINE_COEFFS'] = BASELINE_COEFFS


    sim = SignalSim(meta, pressures, constants)
    sim_powers = sim.simulateFullRun()
    sim_freqs = sim.getSpectralAxis()

    return sim_powers, sim_freqs

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str, required=True)
    parser.add_argument('--SIM_CO', action='store_true', help='Run CO signal simulation')
    parser.add_argument('--ex', action='store_true', help='Run example simulation with separate signal/noise/baseline plots', default=False)
    args = parser.parse_args()

    powers, freqs, pressures, meta = loadData(args.path)

    # --- CONSTANTS ---
    constants = {
        'ROI_SIGMA': 1e6,
        'BASELINE_DEG': 3,
        'CO_SIGNAL': args.SIM_CO,
        'N_PTS': int(meta['Number of Points']),
        'N_MEAS': powers.shape[1],
        'CENTER_FREQ': float(meta['Center Frequency (Hz)']),
        'SPAN': float(meta['Span']),
        'SWEEP_TIME': float(meta['Sweep Time (ms)']),
        'CO_POWER': 1e-16,
        'CO_BANDWIDTH_ATM': 3.5e9,
        'ATM_PRESSURE': 1012.25,
    }

    NOISE_STD, BASELINE_COEFFS = compute_noise_std(powers, freqs, constants)
    constants['NOISE_STD'] = NOISE_STD
    constants['BASELINE_COEFFS'] = BASELINE_COEFFS

    # Simulate data

    sim = SignalSim(meta, pressures, constants)
    if args.ex:
        sim.simulateExample()
    else:
        sim_powers = sim.simulateFullRun()
        sim_freqs = sim.getSpectralAxis()
        os.makedirs(os.path.join(os.path.dirname(args.path), 'Simulated_Data'), exist_ok=True)
        np.save(os.path.join(os.path.dirname(args.path), 'Simulated_Data', os.path.basename(args.path + '_Simulated_Powers.npy')), sim_powers)
        np.save(os.path.join(os.path.dirname(args.path), 'Simulated_Data', os.path.basename(args.path + '_Simulated_freqs.npy')), sim_freqs)
