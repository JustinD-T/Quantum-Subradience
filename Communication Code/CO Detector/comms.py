import json
import serial
import serial.tools.list_ports
import time

class TPGController:
    """
    A class to control a Pfeiffer TPG 201 vacuum gauge.

    This controller reads a configuration from a JSON file, handles the
    Pfeiffer Vacuum Protocol to construct commands, send them over a serial
    connection, and parse the responses.
    """
    def __init__(self, config_path: str):
        """
        Initializes the TPGController.

        Args:
            config_path (str): The path to the JSON configuration file.
        """
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            raise Exception(f"Configuration file not found at: {config_path}")
        
        self.serial_port = self.config['serial']['port']
        if self.serial_port == "REPLACE_ME":
            raise ValueError("Please replace 'REPLACE_ME' in your config file with the correct serial port.")
            
        self.ser = serial.Serial()
        self.ser.port = self.serial_port
        self.ser.baudrate = self.config['serial']['baudrate']
        self.ser.bytesize = self.config['serial']['bytesize']
        self.ser.parity = self.config['serial']['parity']
        self.ser.stopbits = self.config['serial']['stopbits']
        self.ser.timeout = self.config['serial']['timeout']
        
        print(f"Controller initialized for device at {self.serial_port}")

    def _calculate_checksum(self, command_body: str) -> str:
        """Calculates the checksum for a command."""
        checksum = sum(ord(char) for char in command_body) % 256
        return f"{checksum:03}"

    def _send_command(self, full_command: str) -> str | None:
        """Sends a command to the device and returns the response."""
        try:
            if not self.ser.is_open:
                self.ser.open()
                # Give the port a moment to initialize
                time.sleep(0.1)

            self.ser.write(full_command.encode('ascii'))
            response_bytes = self.ser.readline()
            return response_bytes.decode('ascii').strip()
        
        except serial.SerialException as e:
            print(f"Serial communication error: {e}")
            return None
        finally:
            if self.ser.is_open:
                self.ser.close()

    def _parse_response(self, response: str, param_name: str) -> any:
        """Parses the data payload from a response telegram."""
        if "NO DEF" in response or "LOGIC" in response or "RANGE" in response:
            return f"Error from device: {response}"
        
        try:
            data_len = int(response[7:9])
            data_payload = response[9:9 + data_len]
            param_type = self.config['parameters'][param_name]['type']

            if param_type == "u_expo_new": # Pressure
                mantissa = int(data_payload[:4])
                exponent = int(data_payload[4:])
                return (mantissa / 1000.0) * (10 ** (exponent - 20))
            elif param_type == "string":
                return data_payload
            elif param_type == "u_short_int": # Unit
                return int(data_payload)
            elif param_type == "u_real": # Correction Factor
                return int(data_payload) / 100.0
            elif param_type == "pos_integer":
                return int(data_payload)
            else:
                return data_payload # Return raw for unhandled types
        except (ValueError, IndexError):
            return f"Failed to parse response: '{response}'"

    def read_value(self, param_name: str) -> any:
        """
        Reads a value from the device.

        Args:
            param_name (str): The name of the parameter to read (e.g., 'pressure').

        Returns:
            The parsed value from the device or an error message.
        """
        if param_name not in self.config['parameters']:
            return f"Error: Parameter '{param_name}' not defined in config."
        
        param_info = self.config['parameters'][param_name]
        if 'read' not in param_info['access']:
            return f"Error: Parameter '{param_name}' is not readable."

        address = self.config['protocol']['device_address']
        param_num = param_info['number']
        
        command_body = f"{address}?{param_num}02?"
        checksum = self._calculate_checksum(command_body)
        full_command = f"{command_body}{checksum}\r"
        
        response = self._send_command(full_command)
        if response:
            return self._parse_response(response, param_name)
        return None

    def set_value(self, param_name: str, value: any) -> bool:
        """
        Sets a value on the device.

        Args:
            param_name (str): The name of the parameter to set (e.g., 'unit').
            value: The value to set.

        Returns:
            True if the command was likely successful, False otherwise.
        """
        if param_name not in self.config['parameters']:
            print(f"Error: Parameter '{param_name}' not defined in config.")
            return False
            
        param_info = self.config['parameters'][param_name]
        if 'write' not in param_info['access']:
            print(f"Error: Parameter '{param_name}' is not writable.")
            return False

        # --- Encode the value into the correct string format ---
        param_type = param_info['type']
        if param_type == 'u_short_int': # Unit
            data = f"{int(value):03}"
        elif param_type == 'u_real': # Correction Factor
            data = f"{int(value * 100):06}"
        elif param_type == 'pos_integer': # Logging Interval
            data = f"{int(value):06}"
        else:
            print(f"Error: Setting value for type '{param_type}' is not implemented.")
            return False

        data_len = f"{len(data):02}"
        address = self.config['protocol']['device_address']
        param_num = param_info['number']

        command_body = f"{address}!{param_num}{data_len}{data}"
        checksum = self._calculate_checksum(command_body)
        full_command = f"{command_body}{checksum}\r"
        
        response = self._send_command(full_command)
        
        # A successful response echoes the parameter and data length back
        if response and response.startswith(f"{address}") and param_num in response:
            print(f"Successfully set '{param_name}' to {value}.")
            return True
        else:
            print(f"Failed to set '{param_name}'. Response: {response}")
            return False

def find_serial_ports():
    """Lists available serial ports."""
    ports = serial.tools.list_ports.comports()
    print("Available serial ports:")
    if not ports:
        print("  <None found>")
    for port, desc, hwid in sorted(ports):
        print(f"  {port}: {desc} [{hwid}]")

if __name__ == '__main__':
    # --- Example Usage ---
    
    # 1. Find your serial port
    print("Searching for serial ports...")
    find_serial_ports()
    print("-" * 30)
    
    # 2. IMPORTANT: Edit 'tpg_config.json' and set the correct port.
    
    # 3. Create a controller instance
    # This will fail if you haven't updated the config file.
    try:
        controller = TPGController(r'Communication Code\CO Detector\TPG_201_Config.json')

        # 4. Read some values
        print("\n--- Reading Values ---")
        pressure = controller.read_value('pressure')
        if pressure is not None and isinstance(pressure, float):
             print(f"Current Pressure: {pressure:.2e} hPa")
        else:
            print(f"Could not read pressure. Response: {pressure}")

        unit = controller.read_value('unit')
        print(f"Current Unit Setting: {unit} (0:mbar, 1:Torr, 2:hPa)")
        
        sw_version = controller.read_value('software_version')
        print(f"Software Version: {sw_version}")
        
        # 5. Write a value
        print("\n--- Writing a Value ---")
        print("Attempting to set unit to Torr (1)...")
        success = controller.set_value('unit', 1)
        if success:
            # Verify by reading it back
            time.sleep(0.5) # Give device time to process
            new_unit = controller.read_value('unit')
            print(f"Verified Unit Setting: {new_unit}")

    except (ValueError, Exception) as e:
        print(f"\nAn error occurred: {e}")
        print("Please ensure you have created and correctly edited 'tpg_config.json'.")
