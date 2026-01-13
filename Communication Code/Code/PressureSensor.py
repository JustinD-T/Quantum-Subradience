import serial
import time

class PressureSensor():

    def __init__(self, config, callback):
        """
        Initializes the PressureSensor with serial communication settings.
        """

        self.config = config
        self.address = self.config['serial'].get('address', '001')
        self.terminator = self.config['serial'].get('terminator', '\r')
        self.unit_name_map = {v: k for k, v in self.config['parameters']['unit']['value_map'].items()}
        self.log_callback = callback

        # Initializes the serial connection
        try:
            self.ser = serial.Serial() 
            self.ser.port = self.config['serial'].get('port', 'COM1')
            self.ser.baudrate = self.config['serial'].get('baudrate', 9600)
            self.ser.bytesize = self.config['serial'].get('bytesize', 8)  
            self.ser.parity = self.config['serial'].get('parity', 'N')
            self.ser.stopbits = self.config['serial'].get('stopbits', 1)
            self.ser.timeout = self.config['serial'].get('timeout', 3)
        except Exception as e:
            raise AttributeError(f"Error initializing serial object: {e}")

        # Connect and start communication
        self.connect()

    def connect(self):
        """ Attempts to open the serial port """
        try:
            self.ser.open()
            time.sleep(0.1) 
            self.log('message', f'Pressure Sensor Successfully Initialized at {self.ser.port}') 
        except serial.SerialException as e:
            raise ConnectionError(f"Failed to open serial port: {e}")

    def disconnect(self):
        """Closes the serial port connection."""
        if self.ser.is_open:
            try:
                self.ser.close()
            except serial.SerialException as e:
                self.log('error', f"Error closing serial port: {e}")
            else:
                self.log("message", "Pressure Sensor Serial port closed.")


    def _calculate_checksum(self, command_body: str) -> str:
        """Calculates the 3-digit ASCII checksum (sum of bytes MOD 256)."""
        checksum = sum(ord(c) for c in command_body) % 256
        return f"{checksum:03}"

    def _send_command_and_get_response(self, full_command: str) -> str | None:
        """Sends a fully formed command and returns the raw string response."""
        if not self.ser.is_open:
            self.log("error", "Serial port is not open.")
            return None
        try:
            self.ser.flushInput()
            self.ser.flushOutput()
            
            command_bytes = full_command.encode('ascii')
            self.ser.write(command_bytes)
            
            response_bytes = self.ser.read_until(self.terminator.encode('ascii'))
            
            return response_bytes.decode('ascii').strip() if response_bytes else None
        except serial.SerialException as e:
            self.log("error", f"SERIAL COMMUNICATION ERROR: {e}")
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
        
        current_time = time.time()

        return {
            "pressure": pressure_raw,
            "unit": unit_name,
            "timestamp": current_time
        }

    def log(self, type, message):
        self.log_callback(type, message)
