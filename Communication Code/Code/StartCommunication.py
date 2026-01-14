from PressureSensor import PressureSensor
from SpectrumAnalyzer import SpectrumAnalyzer
from VisualInterface import VisualInterface

from PyQt6 import QtWidgets, QtCore, QtGui

from concurrent.futures import ThreadPoolExecutor
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
        self.stop_event = threading.Event()

        # Store configuration and arguments
        self.logging_enabled = not args.nolog
        self.spectrum_enabled = not args.nospectrum
        self.pressure_enabled = not args.nopressure
        self.visualization_enabled = not args.novisual
        self.verbose = args.verbose

        # Setup reading threads
        n_workers = 2 if self.pressure_enabled and self.spectrum_enabled else 1
        self.executor = ThreadPoolExecutor(max_workers=n_workers)

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

        if self.visualization_enabled:
            self.app = QtWidgets.QApplication([])
            spectral_axis = self.spectrum_analyzer.get_spectral_axis() if self.spectrum_enabled else None
            self.gui = VisualInterface(spectral_axis=spectral_axis)
            self.gui.show()

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
                    spec_header_info = {} # Dummy to avoid undefined error below

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
#    Sweep Time (ms): {spec_header_info.get('Sweep Time (ms)', 'N/A')}
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
#       Pressure_Read_Time_Delta (ms): Time delta between program read command and write time in miliseconds (i.e. time lost by communication/writing, inclusive of internal measurement time)
#    Spectrum Analyzer Readings (if enabled):
#       Spectrum_Read_Time_Delta (ms): Time delta between program read command and write time in miliseconds (i.e. time lost by communication/writing, inclusive of internal measurement time)
#       *amplitudes will be headed as their frequency value in Hz in subsequent columns (eg. 2450000000.0 Hz)*
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
            start_time = time.time()
            cycle_ct = 0
            self.master_callback("message", f"Logging started. Writing to {self.logging_path}")
            curr_mem = os.path.getsize(self.logging_path)
            try:
                # Keep CSV file open for the duration of the logging session
                with open(self.logging_path, mode='a', newline='') as log_file:
                    csv_writer = csv.writer(log_file)

                    while self.logging_active:
                        current_loop_start = time.time()
                        timestamp = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(current_loop_start))
                        elapsed_time = current_loop_start - start_time

                        data = {'Timestamp': timestamp, 'Elapsed Time (s)': elapsed_time}
                        
                        # 1. Concurrent Hardware Read
                        reading_trigger_time = time.time()
                        try:
                            futures = {}
                            if self.pressure_enabled:
                                futures['p'] = self.executor.submit(self.pressure_sensor.get_reading)
                            if self.spectrum_enabled:
                                futures['s'] = self.executor.submit(self.spectrum_analyzer.get_amplitudes)
                            
                            # Wait for results
                            p_res = futures['p'].result() if 'p' in futures else None
                            s_res = futures['s'].result() if 's' in futures else None
                        except (RuntimeError, KeyError):
                            # Triggered if executor is shutting down
                            break

                        # 2. Process Pressure Data
                        if p_res:
                            p_delta = (p_res['timestamp'] - reading_trigger_time) * 1000
                            data.update({
                                'Pressure': p_res['pressure'],
                                'Pressure_Unit': p_res['unit'],
                                'Pressure_Read_Time_Delta (ms)': p_delta
                            })
                        else:
                            p_delta = 0

                        # 3. Process Spectrum Data
                        if s_res:
                            s_delta = (s_res['Timestamp'] - reading_trigger_time) * 1000
                            data.update({
                                'Spectrum_Read_Time_Delta (ms)': s_delta,
                            })
                        else:
                            s_delta = 0

                        # 4. Prepare and Write CSV Row
                        sorted_data = [data.get(field, '') for field in self.non_freq_fields]
                        if s_res:
                            sorted_data.extend(s_res['Amplitudes'])

                        csv_writer.writerow(sorted_data)

                        # Update current memory usage
                        curr_mem += len(",".join(map(str, sorted_data)).encode('utf-8'))

                        # Safety: Flush to OS every loop, Sync to Physical Disk every 50
                        log_file.flush()
                        if cycle_ct % 50 == 0:
                            os.fsync(log_file.fileno())
                            curr_mem = os.fstat(log_file.fileno()).st_size
                            

                        # 5. Timing Calculations
                        loop_end_time = time.time()
                        
                        # hw_wait is the duration of the slowest instrument response
                        hw_wait = max(p_delta, s_delta) / 1000.0
                        # systematic_time is the overhead of Python/Writing/Formatting
                        systematic_time = (loop_end_time - current_loop_start) - hw_wait
                        
                        if not self.visualization_enabled:
                            print(f"[Cycle {cycle_ct}] HW Wait: {hw_wait*1000:.1f}ms | Overhead: {systematic_time*1000:.1f}ms | Total Est. Memory: {curr_mem / (1000**3):.8f}Gb ; {(curr_mem / (1000**3)) / ((loop_end_time - start_time) / 3600):.4f}Gb/hr | Measurement Cadence: {cycle_ct / (loop_end_time - start_time):.4f} Hz")

                        cycle_ct += 1

                        if cycle_ct % 10 == 0 and self.visualization_enabled:
                            # Prepare data package for the GUI
                            gui_data = {
                                'amplitudes': s_res['Amplitudes'] if s_res else None,
                                'pressure': p_res['pressure'] if p_res else 0,
                                'elapsed_time': elapsed_time,
                                'file_size_mb': curr_mem / (1024**2),
                                'gb_hr': (curr_mem / (1000**3)) / (elapsed_time / 3600) if elapsed_time > 0 else 0,
                                'cadence': cycle_ct / elapsed_time if elapsed_time > 0 else 0
                            }
                            # Emit the signal (Thread-safe)
                            self.gui.data_received.emit(gui_data)

                        # 6. Intelligent Sleep (Subtracts work time from interval)
                        work_duration = time.time() - current_loop_start
                        sleep_time = max(0, interval - work_duration)
                        if sleep_time > 0:
                            time.sleep(sleep_time)

            except Exception as e:
                self.master_callback("error", f"Fatal error in logging loop: {e}")
            finally:
                self.logging_active = False
                self.executor.shutdown(wait=False)

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
    
    def master_callback(self, log_type, message):
        if log_type == "message" and self.verbose:
            print(f"[Master] {message}")
        elif log_type == 'error':
            print(f"[Master ERROR] {message}")

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
    # NOT IMPLEMENTED
    # parser.add_argument('--maxcadence', default=False, action='store_true', help='Enable logging at the speed of the fastest cadence measurement device')

    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"FATAL ERROR: Failed to load configuration file: {e}")
        exit(1)

    master = CommunicationMaster(config, args)
        
    if args.novisual:
        try:
            master.stop_event.wait()
        except KeyboardInterrupt:
            master.stop_logging()
    else:
        # This keeps the Main Thread alive and responsive to the GUI
        import sys
        sys.exit(master.app.exec())

