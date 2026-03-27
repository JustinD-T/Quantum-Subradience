from PressureSensor import PressureSensor
from SpectrumAnalyzer import SpectrumAnalyzer
from VisualInterface import VisualInterface

from PyQt6 import QtWidgets, QtCore, QtGui


from queue import Queue, Empty
from threading import Thread

from concurrent.futures import ThreadPoolExecutor
import os
import csv
import time
import json
import threading


# ERROR WHERE SOME SETTINGS JS ARE NOT SET, ADD CHECK

class CommunicationMaster():

    def __init__(self, config, args):
        
        self.config = config
        self.logging_path = os.path.join(os.path.curdir, 'ExperimentLogs') if args.logp is None else args.logp
        self.interval = config['program'].get('reading_interval', 1.0)
        self.stop_event = threading.Event()
        self.vis_update_cadence = config['program'].get('visual_update_cycle_interval', 10)

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
                self.fields = ['Timestamp', 'Elapsed Time (s)', 'Cycle Count', 'Absolute Cycle Time (ms)', 'Instrumental Cycle Time (ms)']

                if self.pressure_enabled:
                    #   Add pressure rows to csv
                    self.fields.extend(['Pressure', 'Pressure_Unit'])
                    spec_header_info = {} # Dummy to avoid undefined error below

                if self.spectrum_enabled:
                    self.fields.insert(5, 'Effective Integration (%)')
                    spec_header_info = self.spectrum_analyzer.get_instrument_data()
                    self.spec_sweep_time = float(spec_header_info.get('Sweep Time (ms)', config['spectrum_analyzer']['visa']['sweep_time']))
                    spectral_axis = self.spectrum_analyzer.get_spectral_axis()
                    self.non_freq_fields = self.fields.copy()
                    self.fields.extend([f"{freq} Hz" for freq in spectral_axis])
                    
                # Get CO Concerntration if applicable
                init_CO_conc = 'N/A'
                init_ml = 'N/A'
                CO_bool = input('CO or Acetonitrile? (C/A): ')
                if CO_bool.lower() == 'c':
                    CO = True
                    init_CO_conc = input("Enter initial CO Concentration in ppm (or leave blank to skip): ")
                if CO_bool.lower() == 'a':
                    ACETONITRILE = True
                    init_ml = input("Enter Acetonitrile Volume in mL (or leave blank to skip): ")
                input_gain = input("Enter Effective Gain at Input in dB (or leave blank to skip): ")
                
                # Header info
                header = f"""# Experiment Log ({timestamp})
#    Experiment Description: {input("Enter experiment description (or leave blank): ")}
# Experiment Configuration:
#    logging_enabled: {self.logging_enabled}
#    spectrum_enabled: {self.spectrum_enabled}
#    pressure_enabled: {self.pressure_enabled}
#    visualization_enabled: {self.visualization_enabled}
#    reading_interval (s): {self.interval}
#    visual_update_cycle_interval: {self.vis_update_cadence}
#    Effective Gain at Input (Db) : {input_gain if input_gain != '' else 'N/A'}
#    initial_CO_concentration (ppm): {init_CO_conc if init_CO_conc != '' else 'N/A'}
#    initial_Acetonitrile_volume (mL): {init_ml if init_ml != '' else 'N/A'}
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
#    RBW (Hz): {spec_header_info.get('RBW (Hz)', 'N/A')}
#    VBW (Hz): {spec_header_info.get('VBW (Hz)', 'N/A')}
#    Attenuation (dB): {spec_header_info.get('Attenuation (dB)', 'N/A')}
#    Detector Type: {spec_header_info.get('Detector Type', 'N/A')}
#    Amplitude Space: {spec_header_info.get('Amplitude Space', 'N/A')}
#    Frequency Start (Hz): {spec_header_info.get('Frequency Start (Hz)', 'N/A')}
#    Frequency Stop (Hz): {spec_header_info.get('Frequency Stop (Hz)', 'N/A')}
#    Center Frequency (Hz): {spec_header_info.get('Center Frequency (Hz)', 'N/A')}
#    Reference Level ({spec_header_info.get('Power Unit', 'N/A')}): {spec_header_info.get('Reference Level (dBm)', 'N/A')}
#    Power Unit: {spec_header_info.get('Power Unit', 'N/A')}
# Data Columns:
#    Timestamp: Time of the log entry in ISO 8601 format (measured at start of logging cycle)
#    Elapsed Time (s): Time since the start of logging in seconds (measured at start of logging cycle)
#    Cycle Count: Count of measurement cycle
#    Absolute Cycle Time (ms): Time for a full measurement cycle, measured as time between measurement cycle end and next cycle start
#    Instrumental Cycle Time (ms): Time between sending a measurement request and recieving a measurement from instruments, measures instrumental lag
#    Pressure Sensor Readings (if enabled):
#       Pressure: Pressure reading from the sensor in specified units
#       Pressure_Unit: Unit of the pressure reading
#    Spectrum Analyzer Readings (if enabled):
#       Effective Integration (%): Percentage of a full cycle the Spectrum Analyzer is integrating signal over
#       *amplitudes will be headed as their frequency value in Hz in subsequent columns (eg. 2450000000.0 Hz)*
"""

                # Write header and rows to CSV file
                log_file.write(header)
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
        self.master_callback("message", f"Logging started. Writing to {self.logging_path}")
        
        # 1. Initialize Thread-Safe Queue and Background Writer
        # This prevents Disk I/O from pausing your measurement timing
        self.data_queue = Queue()
        self.writer_stop_event = threading.Event()
        
        # Start the background worker
        writer_thread = threading.Thread(
            target=self._background_csv_writer, 
            args=(self.logging_path, self.non_freq_fields),
            daemon=True
        )
        writer_thread.start()

        start_time = time.time()
        cycle_ct = 0
        prev_elapsed_time = None
        curr_mem = os.path.getsize(self.logging_path)

        try:
            while self.logging_active:
                current_loop_start = time.time()
                elapsed_time = current_loop_start - start_time
                
                # --- PHASE 1: Concurrent Hardware Read ---
                try:
                    futures = {}
                    if self.pressure_enabled:
                        futures['p'] = self.executor.submit(self.pressure_sensor.get_reading)
                    if self.spectrum_enabled:
                        futures['s'] = self.executor.submit(self.spectrum_analyzer.get_amplitudes)
                    
                    p_res = futures['p'].result() if 'p' in futures else None
                    s_res = futures['s'].result() if 's' in futures else None
                except (RuntimeError, KeyError):
                    break

                # --- PHASE 2: Logic & Math (Keep this lean) ---
                cycle_time = elapsed_time - prev_elapsed_time if prev_elapsed_time is not None else 0
                
                p_delta = (p_res['timestamp'] - current_loop_start) * 1000 if p_res else 0
                s_delta = (s_res['Timestamp'] - current_loop_start) * 1000 if s_res else 0
                hw_wait = max(p_delta, s_delta)
                
                eff_int = (self.spec_sweep_time / cycle_time) if (s_res and cycle_time > 0) else 1.0

                # --- PHASE 3: Offload to Background Writer ---
                # We pass the raw data to the queue. 
                # The 6-second delay usually happens during string formatting/writing.
                log_entry = {
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(current_loop_start)),
                    'elapsed': elapsed_time,
                    'cycle_ct': cycle_ct,
                    'cycle_time': cycle_time,
                    'p_res': p_res,
                    's_res': s_res,
                    'eff_int': eff_int,
                    'hw_wait': hw_wait
                }
                self.data_queue.put(log_entry)

                # --- PHASE 4: GUI Update (Throttled) ---
                # Only update GUI if enabled and on your cadence
                if self.visualization_enabled and (cycle_ct % self.vis_update_cadence == 0):
                    gui_data = {
                        'amplitudes': s_res['Amplitudes'] if s_res else None,
                        'pressure': p_res['pressure'] if p_res else 0,
                        'elapsed_time': elapsed_time,
                        'file_size_mb': curr_mem / (1024**2),
                        'gb_hr': (curr_mem / (1e9)) / (elapsed_time / 3600) if elapsed_time > 0 else 0,
                        'cadence': (cycle_ct + 1) / elapsed_time if elapsed_time > 0 else 0,
                        'cycle': cycle_ct,
                        'cycle_time_ms': cycle_time * 1000,
                        'instrumental_time_ms': hw_wait,
                        'integration_efficiency': eff_int * 100
                    }
                    self.gui.data_received.emit(gui_data)

                # Update loop state
                prev_elapsed_time = elapsed_time
                cycle_ct += 1

                # --- PHASE 5: Intelligent Sleep ---
                work_duration = time.time() - current_loop_start
                sleep_time = max(0, interval - work_duration)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except Exception as e:
            self.master_callback("error", f"Fatal error in logging loop: {e}")
        finally:
            self.logging_active = False
            self.writer_stop_event.set() # Tell background thread to finish up
            self.executor.shutdown(wait=False)

    def _background_csv_writer(self, file_path, fields):
        """
        Dedicated method to handle string conversion and disk writes.
        This frees the main loop to keep the analyzer running.
        """
        with open(file_path, mode='a', newline='') as log_file:
            csv_writer = csv.writer(log_file)
            
            while not self.writer_stop_event.is_set() or not self.data_queue.empty():
                try:
                    # Wait for data from the main loop
                    item = self.data_queue.get(timeout=1.0)
                    
                    # Construct the CSV row
                    # This logic replicates your specific 'sorted_data' format
                    data_map = {
                        'Timestamp': item['timestamp'],
                        'Elapsed Time (s)': item['elapsed'],
                        'Cycle Count': item['cycle_ct'],
                        'Absolute Cycle Time (ms)': item['cycle_time'] * 1000,
                        'Instrumental Cycle Time (ms)': item['hw_wait'],
                        'Effective Integration (%)': item['eff_int']
                    }
                    
                    if item['p_res']:
                        data_map.update({
                            'Pressure': item['p_res']['pressure'],
                            'Pressure_Unit': item['p_res']['unit']
                        })

                    # Extract standard fields
                    row = [data_map.get(f, '') for f in fields]
                    
                    # Append spectrum amplitudes if present
                    if item['s_res']:
                        row.extend(item['s_res']['Amplitudes'])
                    
                    # Perform the heavy write operation
                    csv_writer.writerow(row)
                    
                    # Periodic flush for safety
                    if item['cycle_ct'] % 50 == 0:
                        log_file.flush()
                        os.fsync(log_file.fileno())

                    self.data_queue.task_done()
                except Empty:
                    continue
                
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
        config = json.load(config_file
        )
    return config


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Start Communication with Pressure Sensor")
    parser.add_argument('-logp', help='Logging folder path', type=str)
    parser.add_argument('-config', type=str, default=r'Codebase\Communications\Config.json', help='Path to configuration file')
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

