import os

from Utilities import loadData, subtractBaseline

import numpy as np
import matplotlib.pyplot as plt
from scipy import constants as const

# I_V =
# PHI_D = 3.56e-5 # sterradians
# A_P = 0.21 # cm^2
# DELTA_V = 5 #GhZ

# Multyply signal by teh gain (gain/10)*10 (JUST SUM IN THE GAIN + IMPEDENCE)
# DO NOT INCLUDE THE GAIN OF THE PREAMPLIFIER
# TAKE IN THE LOSS OF THE DETECTOR INTO ACCOUNT
    # LOOK INTO THE CONVERSION LOSS OF THE DATASHEET, APPLY TO TEH INPUT SIGNAL

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
<<<<<<< HEAD
=======
        self.CO_POWER = constants['CO_POWER']
        self.CO_BANDWIDTH_ATM = constants['CO_BANDWIDTH_ATM']
        self.ATM_PRESSURE = constants['ATM_PRESSURE']
>>>>>>> c8b7f361a115e60e0c68b6e131050071c911656d
        self.NOISE_STD = constants['NOISE_STD']
        self.BASELINE_COEFFS = constants['BASELINE_COEFFS']
        self.GAIN = 10 ** (constants['GAIN'] / 10) # convert from dB to linear
        self.RBW = constants['RBW']
        
        self.Q = constants['Q']
        self.T = constants['T']
        self.A_eg = constants['A_eg'] 
        self.nu = constants['nu']
        self.L = constants['L'] * 0.01 # convert from cm to m
        self.PHI_D = constants['PHI_D']
        self.A_p = constants['A_p'] * 0.0001 # convert from cm^2 to m^2

    def COPower(self, co_ppm, pressure, CO_bandwidth):
        # Gives the expected power for a given concentration (per measurement)
<<<<<<< HEAD
        pressure_pa = pressure * 100 # convert from mbar to Pa
        n_e = (pressure_pa / const.k * self.T) * (co_ppm / 1e6) * np.exp(-33.2 / self.T) / self.Q 
=======
        n_e = (pressure / const.k * self.T) * (co_ppm / 1e6) * np.exp(-33.2 / self.T) / self.Q 
>>>>>>> c8b7f361a115e60e0c68b6e131050071c911656d
        I_v = (3 / (8 * np.pi * CO_bandwidth)) * n_e * const.h * self.nu * self.A_eg * self.L
        P_v = I_v * CO_bandwidth * self.PHI_D * self.A_p
        return P_v 
    
    def COBandwidth(self, pressure):
        # Gives the expected bandwidth at a given pressure
<<<<<<< HEAD
        return 363e3 * (pressure / 0.1) 
=======
        return 363e3 * (pressure / 0.1)
>>>>>>> c8b7f361a115e60e0c68b6e131050071c911656d
    
    def COPowerAtFreq(self, co_ppm, pressure, freq):
        # Gives the power at a given frequency
        CO_bandwidth = self.COBandwidth(pressure)
        CO_power = self.COPower(co_ppm, pressure, CO_bandwidth)
        distribution = self.gaussian_normalized(freq, self.CENTER_FREQ, CO_bandwidth)
        sampled_power = CO_power * distribution * self.RBW
        return self.GAIN * sampled_power
    
    def gaussian_normalized(self, x, mu, sigma):
        normalization = 1 / (sigma * np.sqrt(2 * np.pi))
        return normalization * np.exp(-((x - mu)**2) / (2 * sigma**2))
    
    def generateCOSignal(self, pressure, co_ppm):
        freqs = np.linspace(self.CENTER_FREQ - self.SPAN/2, self.CENTER_FREQ + self.SPAN/2, self.N_PTS)
        signal = self.COPowerAtFreq(co_ppm, pressure, freqs)
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
    
    def generateMeasurement(self, pressure, co_ppm):
        
        if self.CO_SIGNAL is True:
<<<<<<< HEAD
            signal = self.generateCOSignal(pressure, co_ppm) 
=======
            signal = self.generateCOSignal(pressure, co_ppm) * (1 + np.random.normal(-0.1, 0.1)) # add some variability to the signal power
>>>>>>> c8b7f361a115e60e0c68b6e131050071c911656d
        else:
            signal = np.zeros(self.N_PTS)

        noise = self.generateNoise()

        measurement = self.addBaseline(signal + noise)

        return measurement
    
    def simulateFullRun(self):
        simulated_data = np.zeros((self.N_PTS, self.N_MEAS))

        for i in range(self.N_MEAS):
            print(f'Simulating measurement {i+1}/{self.N_MEAS}', end='\r')
            pressure = self.pressures[i]
            co_ppm = float(self.meta['initial_CO_concentration (ppm)'].replace('>', '').replace('<', '')) * (self.pressures[i] / self.pressures[0]) # Assuming concentration scales linearly with pressure
            simulated_data[:, i] = self.generateMeasurement(pressure, co_ppm)

        return simulated_data
    
    def getSpectralAxis(self):
        return np.linspace(self.CENTER_FREQ - self.SPAN/2, self.CENTER_FREQ + self.SPAN/2, self.N_PTS)

    def simulateExample(self):
        # Plots CO signal, noise, baseline on seperate graphs, then their combiend sum on the last
        pressure = self.pressures[len(self.pressures) // 2]
        co_ppm = float(self.meta['initial_CO_concentration (ppm)'].replace('>', '').replace('<', '')) * (self.pressures[0] / pressure)
        
        # Get data
        signal = self.generateCOSignal(pressure, co_ppm)
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
<<<<<<< HEAD
        'ROI_SIGMA': 1e6,
        'BASELINE_DEG': 3,
        'CO_SIGNAL': sim_co,
        'N_PTS': int(meta['Number of Points']),
        'N_MEAS': powers.shape[1],
        'CENTER_FREQ': float(meta['Center Frequency (Hz)']),
        'SPAN': float(meta['Span']),
        'SWEEP_TIME': float(meta['Sweep Time (ms)']),
        'RBW' : float(meta['RBW (Hz)']),
        'GAIN' : float(meta['Effective Gain at Input (Db)']),
        'Q' : 108, # partition function for CO at room temperature
        'T' : 298, # K, room temperature
        'A_eg' : 2.5e-6, # s^-1, Einstein A coefficient for the transition
        'nu' : 345.796e9, #Ghz, transition wavelength
        'L' : 100, #cm, length of chamber,
        'A_p' : 0.21, # cm^2, area of photodetector,
        'PHI_D' : 3.56e-5 # sterradians, solid angle subtended by photodetector
=======
    'ROI_SIGMA': 1e6,
    'BASELINE_DEG': 3,
    'CO_SIGNAL': sim_co,
    'N_PTS': int(meta['Number of Points']),
    'N_MEAS': powers.shape[1],
    'CENTER_FREQ': float(meta['Center Frequency (Hz)']),
    'SPAN': float(meta['Span']),
    'SWEEP_TIME': float(meta['Sweep Time (ms)']),
    'RBW' : float(meta['RBW (Hz)']),
    'GAIN' : float(meta['Effective Gain at Input (Db)']),
    'CO_POWER': 1e-16,
    'CO_BANDWIDTH_ATM': 3.5e9,
    'ATM_PRESSURE': 1012.25,
    'Q' : 108, # partition function for CO at room temperature
    'T' : 298, # K, room temperature
    'A_eg' : 2.5e-6, # s^-1, Einstein A coefficient for the transition
    'nu' : 345.796e9, #GhX, transition wavelength
    'L' : 100, #cm, length of chamber,
    'A_p' : 0.21, # cm^2, area of photodetector,
    'PHI_D' : 3.56e-5 # sterradians, solid angle subtended by photodetector
>>>>>>> c8b7f361a115e60e0c68b6e131050071c911656d
    }

    NOISE_STD, BASELINE_COEFFS = compute_noise_std(powers, freqs, constants)
    constants['NOISE_STD'] = NOISE_STD
    constants['BASELINE_COEFFS'] = BASELINE_COEFFS


    sim = SignalSim(meta, pressures, constants)
    sim_powers = sim.simulateFullRun()
    sim_freqs = sim.getSpectralAxis()

    return sim_powers, sim_freqs

def interpolatePressures(pressures, target_length, sweep_time):
    # assume a linear depressurization

    time_axis = np.arange(0, len(pressures)*sweep_time, sweep_time)
    pressures_mask = np.isnan(pressures)
    masked_pressures = pressures[~pressures_mask].astype(float)
    masked_time_axis = time_axis[~pressures_mask].astype(float)
<<<<<<< HEAD
=======

>>>>>>> c8b7f361a115e60e0c68b6e131050071c911656d
    coeffs = np.polyfit(masked_time_axis, masked_pressures, 2)

    return np.polyval(coeffs, time_axis)
    

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str, required=True)
    parser.add_argument('--SIM_CO', action='store_true', help='Run CO signal simulation')
    parser.add_argument('--ex', action='store_true', help='Run example simulation with separate signal/noise/baseline plots', default=False)
    args = parser.parse_args()

    powers, freqs, pressures, meta = loadData(args.path)

    if np.isnan(pressures).any():
        print('Pressures contain NaN values, interpolating pressures for simulation...')
        pressures = interpolatePressures(pressures, powers.shape[1], float(meta.get('Sweep Time (ms)', 4)))

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
<<<<<<< HEAD
=======
        'CO_POWER': 1e-16,
        'CO_BANDWIDTH_ATM': 3.5e9,
        'ATM_PRESSURE': 1012.25,
>>>>>>> c8b7f361a115e60e0c68b6e131050071c911656d
        'RBW' : float(meta['RBW (Hz)']),
        'GAIN' : float(meta['Effective Gain at Input (Db)']),
        'Q' : 108, # partition function for CO at room temperature
        'T' : 298, # K, room temperature
        'A_eg' : 2.5e-6, # s^-1, Einstein A coefficient for the transition
<<<<<<< HEAD
        'nu' : 345.796e9, #Ghz, transition wavelength
=======
        'nu' : 345.796e9, #GhX, transition wavelength
>>>>>>> c8b7f361a115e60e0c68b6e131050071c911656d
        'L' : 100, #cm, length of chamber,
        'A_p' : 0.21, # cm^2, area of photodetector,
        'PHI_D' : 3.56e-5 # sterradians, solid angle subtended by photodetector
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
