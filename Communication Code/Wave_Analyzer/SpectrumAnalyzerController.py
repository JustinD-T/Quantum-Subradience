import json
import pyvisa
import time
import numpy as np

class SpectrumAnalyzerController:
    """
    Controls a spectrum analyzer using pyvisa.
    (Version with byte order and synchronization fixes for robust data transfer)
    """
    def __init__(self, config_path: str):
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError as e:
            raise Exception(f"Configuration file not found: {e.filename}")
        
        visa_config = self.config["visa"]
        self.resource_string = visa_config["resource_string"]
        self.resource_manager = pyvisa.ResourceManager(visa_config.get("backend", ""))
        self.instrument = None
        print(f"Controller initialized for device at '{self.resource_string}'.")

    def connect(self) -> bool:
        if self.instrument: return True
        try:
            self.instrument = self.resource_manager.open_resource(self.resource_string)
            self.instrument.timeout = self.config["visa"].get("timeout", 5000)
            print(f"Successfully connected to: {self.query('*IDN?').strip()}")

            # --- FIX: Set the correct byte order for PC (little-endian) ---
            self.write(self.config['commands']['set_byte_order'])
            
            return True
        except pyvisa.errors.VisaIOError as e:
            print(f"--- VISA CONNECTION FAILED --- Error: {e}")
            return False

    def disconnect(self):
        if self.instrument:
            self.instrument.close()
            print("\nInstrument disconnected.")

    def write(self, command: str):
        if not self.instrument: return
        try:
            self.instrument.write(command)
        except pyvisa.errors.VisaIOError as e:
            print(f"Failed to write command '{command}'. Error: {e}")
    
    def query(self, query_str: str) -> str | None:
        if not self.instrument: return None
        try:
            return self.instrument.query(query_str).strip()
        except pyvisa.errors.VisaIOError as e:
            print(f"Failed to execute query '{query_str}'. Error: {e}")
            return None
            
    def set_parameter(self, command_name: str, value: any):
        """Sets a parameter using a command name from the config file."""
        if command_name not in self.config["commands"]:
            print(f"Error: Command '{command_name}' not found in configuration.")
            return
        command_template = self.config["commands"][command_name]
        self.write(command_template.format(value=value))

    def get_reading(self) -> dict | None:
        """
        Gets a full data trace from the analyzer after ensuring the correct data format.
        """
        if not self.instrument: return None

        # --- FIX: Wait for the current operation/sweep to complete before reading ---
        self.query(self.config['commands']['operation_complete_query'])

        self.write(self.config['commands']['set_data_format'])
        time.sleep(0.05) # Small delay for stability

        trace_query = self.config['commands']['query_trace_data']
        
        try:
            # query_binary_values is faster and more reliable
            trace_data = self.instrument.query_binary_values(trace_query, datatype='f', is_big_endian=False)
        except Exception:
             # Fallback to slower ASCII transfer if binary fails
            trace_str = self.query(trace_query)
            if not trace_str: return None
            try:
                trace_data = [float(x) for x in trace_str.split(',')]
            except (ValueError, TypeError):
                 return None

        start_freq_query = self.config['commands']['query_frequency_start']
        stop_freq_query = self.config['commands']['query_frequency_stop']
        
        start_freq = self.query(start_freq_query)
        stop_freq = self.query(stop_freq_query)

        if not all([trace_data, start_freq, stop_freq]):
            return None

        try:
            num_points = len(trace_data)
            frequencies = np.linspace(float(start_freq), float(stop_freq), num_points)
            
            return {
                "frequencies_hz": frequencies.tolist(),
                "amplitudes_dbm": trace_data
            }
        except (ValueError, TypeError) as e:
            print(f"Error processing trace data: {e}")
            return None