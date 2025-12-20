import json
import serial
import time
import argparse
import csv
import os

class TPGController:
    """
    A full-fledged class to control and monitor a Pfeiffer TPG 201 vacuum gauge.
    """
    def __init__(self, config_path: str):
        """Initializes the TPGController by loading from a config file."""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            raise Exception(f"Configuration file not found at: {config_path}")
        
        serial_config = self.config['serial']
        self.ser = serial.Serial()
        self.ser.port = serial_config['port']
        # NOTE: Using device address 001 which was found to work.
        self.address = "001" 
        
        # Applying serial settings
        self.ser.baudrate = serial_config.get('baudrate', 9600)
        self.ser.bytesize = serial_config.get('bytesize', 8)
        self.ser.parity = serial_config.get('parity', 'N')
        self.ser.stopbits = serial_config.get('stopbits', 1)
        self.ser.timeout = serial_config.get('timeout', 3) 
        
        self.unit_name_map = {v: k for k, v in self.config['parameters']['unit']['value_map'].items()}
        
        print(f"Controller initialized for device at {self.ser.port} (Address: {self.address}).")

    def connect(self) -> bool:
        """Opens the serial port connection."""
        if self.ser.is_open: return True
        try:
            self.ser.open()
            time.sleep(0.1) 
            print(f"Serial port {self.ser.port} opened successfully.")
            return True
        except serial.SerialException as e:
            print(f"Failed to open serial port: {e}")
            return False

    def disconnect(self):
        """Closes the serial port connection."""
        if self.ser.is_open:
            self.ser.close()
            print("\nSerial port closed.")

    def _calculate_checksum(self, command_body: str) -> str:
        """Calculates the 3-digit ASCII checksum (sum of bytes MOD 256)."""
        checksum = sum(ord(c) for c in command_body) % 256
        return f"{checksum:03}"

    def _send_command_and_get_response(self, full_command: str) -> str | None:
        """Sends a fully formed command and returns the raw string response."""
        if not self.ser.is_open:
            print("Error: Serial port is not open.")
            return None
        try:
            self.ser.flushInput()
            self.ser.flushOutput()
            
            command_bytes = full_command.encode('ascii')
            self.ser.write(command_bytes)
            
            response_bytes = self.ser.readline()
            
            return response_bytes.decode('ascii').strip() if response_bytes else None
        except serial.SerialException as e:
            print(f"SERIAL COMMUNICATION ERROR: {e}")
            return None

    def _build_read_command(self, param_num: str) -> str:
        """
        Builds the Data Query command using the verified structure (1-digit action code).
        """
        action_code = "0"
        data_payload = "02=?"
        
        command_body = f"{self.address}{action_code}{param_num}{data_payload}"
        checksum = self._calculate_checksum(command_body)
        full_command = f"{command_body}{checksum}\r"
        
        return full_command

    def _parse_response(self, response: str, param_name: str) -> any:
        """Parses the data payload from a response telegram."""
        if not response or any(keyword in response for keyword in ["NO DEF", "RANGE", "LOGIC"]):
            return None

        try:
            param_num = self.config['parameters'][param_name]['number']
            param_index = response.find(param_num)
            
            if param_index == -1: return None 
            
            len_start_index = param_index + len(param_num)
            data_len = int(response[len_start_index : len_start_index + 2])
            payload_start_index = len_start_index + 2
            data_payload = response[payload_start_index : payload_start_index + data_len]

            param_info = self.config['parameters'][param_name]
            response_type = param_info.get('response_type')

            if response_type == "u_expo_new":
                if len(data_payload) != 6: return None
                    
                mantissa = int(data_payload[:4])
                exponent = int(data_payload[4:])
                
                if mantissa == 9999: return float('nan')
                
                return (mantissa / 1000.0) * (10 ** (exponent - 20))
                
            elif response_type == "u_short_int":
                return int(data_payload)
            return data_payload
            
        except (ValueError, IndexError, TypeError, ZeroDivisionError):
            return None

    def read_value(self, param_name: str) -> any:
        """Reads a named parameter from the device."""
        param_num = self.config['parameters'][param_name]['number']
        full_command = self._build_read_command(param_num)
        response = self._send_command_and_get_response(full_command)
        return self._parse_response(response, param_name) if response else None

    def get_reading(self) -> dict | None:
        """Gets a complete reading (pressure and unit) from the gauge."""
        pressure_raw = self.read_value('pressure')
        
        # Small delay to allow gauge buffer to clear between commands
        time.sleep(0.05) 
        
        unit_code_raw = self.read_value('unit')
        
        if pressure_raw is None or unit_code_raw is None:
            return None
        
        unit_name = self.unit_name_map.get(f"{unit_code_raw:03d}", "Unknown")
        
        return {
            "pressure": pressure_raw,
            "unit": unit_name
        }

    def start_csv_logging(self, csv_filepath: str, interval: float):
        """Continuously reads from the gauge and appends to a CSV file."""
        is_new_file = not os.path.exists(csv_filepath)
        
        # Use buffering=0 for minimal file buffering on write
        with open(csv_filepath, 'a', newline='', buffering=1) as csvfile:
            fieldnames = ['timestamp', 'pressure', 'unit']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if is_new_file:
                writer.writeheader()
                print(f"Created new CSV file: {csv_filepath}")
            else:
                print(f"Appending to existing CSV file: {csv_filepath}")

            print(f"Starting CSV logging every {interval}s. Press Ctrl+C to stop.")
            try:
                while True:
                    current_time = time.time()
                    reading = self.get_reading()
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))
                    
                    if reading:
                        log_entry = {
                            "timestamp": timestamp,
                            "pressure": reading['pressure'],
                            "unit": reading['unit']
                        }
                        
                        writer.writerow(log_entry)
                        
                        # --- FIX: Force write to disk immediately ---
                        csvfile.flush()
                        os.fsync(csvfile.fileno())
                        # --- END FIX ---
                        
                        print(f"[{timestamp}] Wrote to CSV: {reading['pressure']:.3e} {reading['unit']}")
                    else:
                        print(f"[{timestamp}] Failed to get reading from gauge.")
                    
                    time.sleep(interval - (time.time() - current_time) % interval)
                    
            except KeyboardInterrupt:
                print("\nStopping logger.")
            except Exception as e:
                print(f"\nAn error occurred during logging: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Control and monitor a Pfeiffer TPG 201 vacuum gauge with CSV logging.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--config', default='Communication Code/Vacuum_Gauge/TPG_201_Config.json', help='Path to TPG config file.')
    parser.add_argument('--csv-file', default='vacuum_log.csv', help='Path to the output CSV file.')
    parser.add_argument('--interval', type=float, default=1.0, help='Logging interval in seconds.')

    csv_file = input('Name of run (csv file will be <name>.csv): ')

    args = parser.parse_args()
    
    try:
        controller = TPGController(args.config)
        if controller.connect():
            controller.start_csv_logging(f"{csv_file}.csv", args.interval)
            controller.disconnect()
    except Exception as e:
        print(f"Initialization Error: {e}")