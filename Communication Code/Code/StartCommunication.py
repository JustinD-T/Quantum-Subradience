from PressureSensor import PressureSensor
from SpectrumAnalyzer import SpectrumAnalyzer

import os
import csv
import time
import json
import threading

class CommunicationMaster():

    def __init__(self, config, args):
        
        self.config = config
        self.logging_path = os.path.join(os.path.curdir, 'ExperimentLogs') if args.logp is None else args.logp
        self.interval = config['program'].get('reading_interval', 1.0)

        # Store configuration and arguments
        self.logging_enabled = not args.nolog
        self.spectrum_enabled = not args.nospectrum
        self.pressure_enabled = not args.nopressure
        self.visualization_enabled = not args.novisual
        self.verbose = args.verbose

        # Initialize Pressure Sensor if enabled
        if self.pressure_enabled:
            
            # Try to connect
            try:
                self.pressure_sensor = PressureSensor(self.config['pressure_sensor'], self.pressure_callback)
            except Exception as e:
                print(f"ERROR: Failed to initialize Pressure Sensor (Continuing without it): {e}")
                self.pressure_enabled = False
        
        if self.spectrum_enabled:

            # Try to connect
            try:
                self.spectrum_analyzer = SpectrumAnalyzer(self.config['spectrum_analyzer'], self.spectrum_callback)
            except Exception as e:
                print(f"ERROR: Failed to initialize Spectrum Analyzer (Continuing without it): {e}")
                self.spectrum_enabled = False

        # Initialize logging on a concurrent thread for continous logging
        if self.logging_enabled:

            # Create csv template
            if os.path.exists(self.logging_path) is False:
                os.makedirs(self.logging_path)

            timestamp = time.strftime('%Y%m%d-%H%M%S', time.localtime())
            self.logging_path = os.path.join(self.logging_path, f'ExperimentLog_{timestamp}.csv')
            
            # Create and write header to log file
            with open(self.logging_path, mode='w', newline='') as log_file:
                csv_writer = csv.writer(log_file)
                self.fields = ['Timestamp', 'Elapsed Time (s)']

                if self.pressure_enabled:
                    #   Add pressure rows to csv
                    self.fields.extend(['Pressure_Read_Time_Delta (ms)', 'Pressure', 'Pressure_Unit'])

                if self.spectrum_enabled:
                    self.fields.insert(2, 'Spectrum_Read_Time_Delta (ms)')
                    spec_header_info = self.spectrum_analyzer.get_instrument_data()
                    spectral_axis = self.spectrum_analyzer.get_spectral_axis()
                    self.non_freq_fields = self.fields.copy()
                    self.fields.extend([f"{freq} Hz" for freq in spectral_axis])
                    
                # Header info
                header = f"""# Experiment Log ({timestamp})
# Experiment Configuration:
#    logging_enabled: {self.logging_enabled}
#    spectrum_enabled: {self.spectrum_enabled}
#    pressure_enabled: {self.pressure_enabled}
#    visualization_enabled: {self.visualization_enabled}
# Serial Configuration ({'ENABLED' if self.pressure_enabled else 'DISABLED'}):
#    Port: {self.config['pressure_sensor']['serial'].get('port', 'COM1')}
#    Baudrate: {self.config['pressure_sensor']['serial'].get('baudrate', 9600)}
#    Bytesize: {self.config['pressure_sensor']['serial'].get('bytesize', 8)}
#    Parity: {self.config['pressure_sensor']['serial'].get('parity', 'N')}
#    Stopbits: {self.config['pressure_sensor']['serial'].get('stopbits', 1)}
#    Timeout (ms): {float(self.config['pressure_sensor']['serial'].get('timeout', 3)) * 1000}
# Spectrum Analyzer Configuration ({'ENABLED' if self.spectrum_enabled else 'DISABLED'}):
#    Resource String: {self.config['spectrum_analyzer']['visa'].get('resource_string', 'N/A')}
#    VISA Backend: {self.config['spectrum_analyzer']['visa'].get('visa_backend', 'None Specified')}
#    Timeout (ms): {self.config['spectrum_analyzer']['visa'].get('timeout', 'N/A')}
#    Data Format: {self.config['spectrum_analyzer']['visa'].get('data_format', 'N/A')}
#    Byte Order: {self.config['spectrum_analyzer']['visa'].get('byte_order', 'N/A')}
#    Number of Points: {spec_header_info.get('Number of Points', 'N/A')}
#    Span: {spec_header_info.get('Span', 'N/A')}
#    Frequency Start (Hz): {spec_header_info.get('Frequency Start (Hz)', 'N/A')}
#    Frequency Stop (Hz): {spec_header_info.get('Frequency Stop (Hz)', 'N/A')}
#    Center Frequency (Hz): {spec_header_info.get('Center Frequency (Hz)', 'N/A')}
#    Reference Level (dBm): {spec_header_info.get('Reference Level (dBm)', 'N/A')}
#    Power Unit: {spec_header_info.get('Power Unit', 'N/A')}
# Data Columns:
#    Timestamp: Time of the log entry in ISO 8601 format (measured at start of logging cycle)
#    Elapsed Time (s): Time since the start of logging in seconds (measured at start of logging cycle)
#    Pressure Sensor Readings (if enabled):
#       Pressure: Pressure reading from the sensor in specified units
#       Pressure_Unit: Unit of the pressure reading
#       Pressure_Read_Time_Delta (ms): Delta between program read command and pressure sensor response time in miliseconds
#    Spectrum Analyzer Readings (if enabled):
#       Spectrum_Read_Time_Delta (ms): Delta between program read command and spectrum analyzer response time in miliseconds
#       *amplitudes will be headed as their frequency value in Hz in subsequent columns*
"""

                # Write header and rows to CSV file
                log_lines = header.strip().split('\n')
                for line in log_lines:
                    csv_writer.writerow([line])
                csv_writer.writerow(self.fields)

            # Start logging thread
            self.logging_active = True
            self.logging_thread = threading.Thread(target=self.start_logging, args=(self.interval,))
            self.logging_thread.start()

    def stop_logging(self):
        """Stops the logging thread."""
        self.logging_active = False
        if hasattr(self, 'logging_thread') and self.logging_thread.is_alive():
            self.logging_thread.join(timeout=5)
        print("Logging stopped.")

    def start_logging(self, interval):
        start_time  = time.time()
        print(f"Logging started. Writing to {self.logging_path}")
        while self.logging_active:
            
            # Get Timestamp
            current_time = time.time()
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(current_time))
            elapsed_time = current_time - start_time

            # Prep data columns
            data = {'Timestamp': timestamp, 'Elapsed Time (s)': elapsed_time}

            # Get Pressure Sensor Data
            if self.pressure_enabled:
                reading_start_time = time.time()
                pressure_sensor_reading = self.pressure_sensor.get_reading()
                pressure_time_delta = (pressure_sensor_reading['timestamp'] - reading_start_time) * 1000  # Convert to milliseconds
                data.update({
                    'Pressure': pressure_sensor_reading['pressure'],
                    'Pressure_Unit': pressure_sensor_reading['unit'],
                    'Pressure_Read_Time_Delta (ms)': pressure_time_delta
                })

            if self.spectrum_enabled:
                reading_start_time = time.time()
                spectrum_data = self.spectrum_analyzer.get_amplitudes()
                spectrum_time_delta = (spectrum_data['Timestamp'] - reading_start_time) * 1000  # Convert to milliseconds
                data.update({
                    'Spectrum_Read_Time_Delta (ms)': spectrum_time_delta,
                })
            
            # Sort data to match header order
            sorted_data = [data.get(field, '') for field in self.non_freq_fields]

            # Append amplitude data if spectrum enabled
            if self.spectrum_enabled:
                sorted_data.extend(spectrum_data['Amplitudes'])

            # Append to CSV file
            with open(self.logging_path, mode='a', newline='') as log_file:
                csv_writer = csv.writer(log_file)
                csv_writer.writerow(sorted_data)

            if self.verbose:
                print(f"[Logging] Logged data at {timestamp}")
            time.sleep(interval)    
                

    def pressure_callback(self, log_type, message):
        if log_type == "message" and self.verbose:
            print(f"[Pressure Sensor] {message}")
        elif log_type == 'error':
            print(f"[Pressure Sensor ERROR] {message}")

    def spectrum_callback(self, log_type, message):
        if log_type == "message" and self.verbose:
            print(f"[Spectrum Analyzer] {message}")
        elif log_type == 'error':
            print(f"[Spectrum Analyzer ERROR] {message}")

def load_config(config_path):
    """Loads configuration from a JSON file."""

    with open(config_path, 'r') as config_file:
        config = json.load(config_file)
    return config


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Start Communication with Pressure Sensor")
    parser.add_argument('-logp', help='Logging folder path', type=str)
    parser.add_argument('-config', type=str, default=r'Communication Code\Code\Config.json', help='Path to configuration file')
    parser.add_argument('--nolog', default=False, action='store_true', help='Disable logging')
    parser.add_argument('--nospectrum', default=False, action='store_true', help='Disable spectrum analyzer reading')
    parser.add_argument('--nopressure', default=False, action='store_true', help='Disable pressure sensor reading')
    parser.add_argument('--novisual', default=False, action='store_true', help='Disable visualization module')
    parser.add_argument('--verbose', default=False, action='store_true', help='Enable verbose logging output')

    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"FATAL ERROR: Failed to load configuration file: {e}")
        exit(1)

    CommunicationMaster(config, args)

    # Initialize master with proper configuration

