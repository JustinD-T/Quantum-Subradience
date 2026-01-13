import pyvisa
import time

class SpectrumAnalyzer():
    
    def __init__(self, config, callback):
        self.config = config
        self.callback = callback

        # Initialize VISA resource manager
        try:
            visa_backend = config.get('visa_backend', None)
            if visa_backend:
                self.rm = pyvisa.ResourceManager(visa_backend)
            else:
                self.rm = pyvisa.ResourceManager()
        except Exception as e:
            raise ConnectionError(f"Failed to initialize VISA Resource Manager: {e}")

        # Connect to the instrument
        try:
            resource_string = config['visa']['resource_string']
            self.instrument = self.rm.open_resource(resource_string)
            self.instrument.timeout = config['visa'].get('timeout', 5000)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Spectrum Analyzer: {e}")

        # Configure the instrument
        self.commands = config['commands']
        
        # Set data format
        try:
            self.instrument.write(self.commands['set_data_format'])
            self.instrument.write(self.commands['set_byte_order'])
        except Exception as e:
            self.log('error', f"Error configuring Spectrum Analyzer byte/data format: {e}")

        # Set center frequency
        try:
            center_freq = config['visa'].get('center_frequency', 2.5e9)
            self.instrument.write(self.commands['set_center_frequency'].replace('value', str(center_freq)))
        except Exception as e:
            self.log('error', f"Error setting center frequency: {e}")

        # Set reference level
        try:
            ref_level = config['visa'].get('reference_level', 0)
            self.instrument.write(self.commands['set_reference_level'].replace('value', str(ref_level)))
        except Exception as e:
            self.log('error', f"Error setting reference level: {e}")

        # Set span
        try:
            span = config['visa'].get('span', 1e8)
            self.instrument.write(self.commands['set_span'].replace('value', str(span)))
        except Exception as e:
            self.log('error', f"Error setting span: {e}")

        # Set power unit
        try:
            power_unit = config['visa'].get('power_unit', 'DBM')
            self.instrument.write(self.commands['set_power_unit'].replace('value', power_unit))
        except Exception as e:
            self.log('error', f"Error setting power unit: {e}")

        # Set sweep time to auto
        try:
            auto_sweep_time = config['visa'].get('auto_sweep_time', 1)
            self.instrument.write(self.commands['set_sweep_time_auto'].replace('value', str(auto_sweep_time)))
        except Exception as e:
            self.log('error', f"Error setting sweep time to auto: {e}")
        
        # Determine point frequencies
        try:
            self.start_freq =self.instrument.query(self.commands['query_frequency_start'])
            self.stop_freq = self.instrument.query(self.commands['query_frequency_stop'])
            self.num_sweep_points = self.instrument.query(self.commands['query_sweep_points'])
        except Exception as e:
            self.log('error', f"Error querying frequency points: {e}")

        # Compute x-axis frequency values
        self.spectral_axis = [float(self.start_freq) + i * (float(self.stop_freq) - float(self.start_freq)) / (int(self.num_sweep_points) - 1) for i in range(int(self.num_sweep_points))]

    def log(self, log_type, message):
        if self.callback:
            self.callback(log_type, message)

    def get_amplitudes(self):
        
        # Query trace data
        amplitudes = self.instrument.query_binary_values(
            self.commands['query_trace_data'], 
            datatype='f', 
            is_big_endian=False
        )

        # Get write time
        write_time = time.time()

        # Return as dictionary
        return {"N_pts" : len(amplitudes), "Amplitudes" : amplitudes, "Timestamp" : write_time}

    def get_instrument_data(self):
        N_points = self.instrument.query(self.commands['query_sweep_points'])
        freq_stop = self.instrument.query(self.commands['query_frequency_stop'])
        freq_start = self.instrument.query(self.commands['query_frequency_start'])
        center_freq = self.instrument.query(self.commands['query_center_frequency'])
        ref_level = self.instrument.query(self.commands['query_reference_level'])
        power_unit = self.instrument.query(self.commands['query_power_unit'])
        span = self.instrument.query(self.commands['query_span'])
        return {
            "Number of Points": N_points,
            "Span": span,
            "Frequency Start (Hz)": freq_start,
            "Frequency Stop (Hz)": freq_stop,
            "Center Frequency (Hz)": center_freq,
            "Reference Level (dBm)": ref_level,
            "Power Unit": power_unit
        }

    def get_spectral_axis(self):
        return self.spectral_axis
