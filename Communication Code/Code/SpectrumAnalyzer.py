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
            self.instrument.write(self.commands['set_data_format'].replace('value', config['visa'].get('data_format', 'REAL, 32')))
            self.instrument.write(self.commands['set_byte_order'].replace('value', config['visa'].get('byte_order', 'SWAP')))
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

        # Set number of points
        try:
            num_points = config['visa'].get('num_points', 401)
            self.instrument.write(self.commands['set_num_points'].replace('value', str(num_points)))
        except Exception as e:
            self.log('error', f"Error setting number of points: {e}")

        # Check both auto sweep and specified time are provided
        if int(config['visa'].get('auto_sweep_time', 'N/A')) != 0 and config['visa'].get('sweep_time', None) is not None:
            self.log('error', f'MAJOR ERROR: auto_sweep_time is True while sweep_time is specified! Continuing specified sweep time.')
        
        # Set auto sweep time first 
        try:
            auto_sweep_time = config['visa'].get('auto_sweep_time', 0)
            self.instrument.write(self.commands['set_sweep_time_auto'].replace('value', str(auto_sweep_time)))
            self.auto_sweep = True
        except Exception as e:
            self.log('error', f"Error setting auto_sweep_time to {auto_sweep_time}: {e}")

        # if auto_sweep_time is not true, set specified time
        if config['visa'].get('auto_sweep_time', 0) != 1:
            try:
                sweep_time = config['visa'].get('sweep_time', 100) / 1000 #Convert to ms
                self.instrument.write(self.commands['set_sweep_time'].replace('value', str(sweep_time)))
                self.auto_sweep = False
            except Exception as e:
                self.log('error', f'Error setting sweep_time to {sweep_time}: {e}')
            
        # Set sweep mode 
        try:
            sweep_mode = config['visa'].get('single_sweep_mode', 'OFF')
            self.instrument.write(self.commands['set_sweep_mode'].replace('value', sweep_mode))
        except Exception as e:
            self.log('error', f"Error setting singe_sweep_mode to {sweep_mode}: {e}")

        # Set Display mode
        try:
            display_on = config['visa'].get('display_on', 'ON')
            self.instrument.write(self.commands['set_display_on'].replace('value', display_on))
        except Exception as e:
            self.log('error', f"Error setting display_on to {display_on}: {e}")
        
        # Set detector mode
        try:
            detector_mode = config['visa'].get('detector_mode', 'AVER')
            self.instrument.write(self.commands['set_detector_mode'].replace('value', detector_mode))
        except Exception as e:
            self.log('error', f"Error setting detector_mode to {detector_mode}: {e}")
        
        # Initiate a sweep to apply settings
        try:
            self.instrument.write(self.commands['initiate_sweep'])
            self.instrument.query(self.commands['operation_complete_query'])
            self.instrument.query_binary_values(
                self.commands['query_trace_data'], 
                datatype='f', 
                is_big_endian=False
            )
        except Exception as e:
            self.log('error', f"Error initiating first sweep: {e}")

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
        
        # Initiate a new sweep
        self.instrument.write(self.commands['initiate_sweep'])

        # Wait for operation to complete
        self.instrument.query(self.commands['operation_complete_query'])

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
        N_points = self.instrument.query(self.commands['query_sweep_points']).strip()
        freq_stop = self.instrument.query(self.commands['query_frequency_stop']).strip()
        freq_start = self.instrument.query(self.commands['query_frequency_start']).strip()
        center_freq = self.instrument.query(self.commands['query_center_frequency']).strip()
        ref_level = self.instrument.query(self.commands['query_reference_level']).strip()
        power_unit = self.instrument.query(self.commands['query_power_unit']).strip()
        span = self.instrument.query(self.commands['query_span']).strip()
        if self.auto_sweep is True:
            sweep_time = 'Auto'
        else:
            sweep_time = self.instrument.query(self.commands['query_sweep_time']).strip()
        return {
            "Number of Points": N_points,
            "Span": span,
            "Frequency Start (Hz)": freq_start,
            "Frequency Stop (Hz)": freq_stop,
            "Center Frequency (Hz)": center_freq,
            "Reference Level (dBm)": ref_level,
            "Power Unit": power_unit,
            "Sweep Time (ms)" : sweep_time
        }

    def get_spectral_axis(self):
        return self.spectral_axis
