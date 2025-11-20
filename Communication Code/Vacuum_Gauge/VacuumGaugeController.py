import json
import serial
import time
import argparse
import redis

class TPGController:
    """
    A full-fledged class to control and monitor a Pfeiffer TPG 201 vacuum gauge,
    with support for interval-based logging to a Redis server.
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
        self.ser.baudrate = serial_config.get('baudrate', 9600)
        self.ser.bytesize = serial_config.get('bytesize', 8)
        self.ser.parity = serial_config.get('parity', 'N')
        self.ser.stopbits = serial_config.get('stopbits', 1)
        self.ser.timeout = serial_config.get('timeout', 2)
        
        # Invert the value_map for easy unit name lookup
        self.unit_name_map = {v: k for k, v in self.config['parameters']['unit']['value_map'].items()}
        
        print(f"Controller initialized for device at {self.ser.port}.")

    def connect(self) -> bool:
        """Opens the serial port connection with improved error handling and a delay."""
        if self.ser.is_open: return True
        try:
            self.ser.open()
            time.sleep(0.1) 
            print(f"Serial port {self.ser.port} opened successfully.")
            return True
        except serial.SerialException as e:
            if "Access is denied" in str(e):
                 print(f"\n--- PERMISSION ERROR ---")
                 print(f"Failed to open port '{self.ser.port}': Access is denied.")
                 print("This usually means another program is currently using the port.")
            else:
                 print(f"Failed to open serial port: {e}")
            return False

    def disconnect(self):
        """Closes the serial port connection."""
        if self.ser.is_open:
            self.ser.close()
            print("\nSerial port closed.")

    def _calculate_checksum(self, command_body: str) -> str:
        """Calculates the 3-digit ASCII checksum for a command body."""
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
            self.ser.write(full_command.encode('ascii'))
            response_bytes = self.ser.readline()
            return response_bytes.decode('ascii').strip() if response_bytes else None
        except serial.SerialException as e:
            print(f"SERIAL COMMUNICATION ERROR: {e}")
            return None

    def _build_and_send(self, command_type: str, param_name: str, data: str = "") -> str | None:
        """Builds a command from the config, calculates checksum, and sends it."""
        address = self.config['protocol']['device_address']
        param_num = self.config['parameters'][param_name]['number']
        command_template = self.config['commands'][command_type]['format']
        
        # Special handling for read commands based on our findings
        if command_type == 'read_value':
            data = "=?"
        
        command_body = command_template.format(
            address=address,
            param_num=param_num,
            data_len=f"{len(data):02}",
            data=data
        )
        checksum = self._calculate_checksum(command_body)
        full_command = f"{command_body}{checksum}\r"
        return self._send_command_and_get_response(full_command)

    def _parse_response(self, response: str, param_name: str) -> any:
        """Parses the data payload from a response telegram based on config rules."""
        if not response or any(err in response for err in ["NO DEF", "LOGIC", "RANGE"]):
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
                mantissa = int(data_payload[:4])
                exponent = int(data_payload[4:])
                return (mantissa / 1000.0) * (10 ** (exponent - 20))
            elif response_type == "u_short_int":
                return int(data_payload)
            return data_payload
        except (ValueError, IndexError, TypeError):
            return None

    def read_value(self, param_name: str) -> any:
        """Reads a named parameter from the device."""
        response = self._build_and_send('read_value', param_name)
        return self._parse_response(response, param_name) if response else None

    def set_unit(self, unit_name: str) -> bool:
        """Sets the measurement unit using a human-readable name (e.g., 'Torr')."""
        param_info = self.config['parameters']['unit']
        value_map = param_info['value_map']
        
        if unit_name not in value_map:
            print(f"Error: Invalid unit '{unit_name}'. Must be one of {list(value_map.keys())}")
            return False
            
        unit_code = value_map[unit_name]
        write_format = param_info['write_format']
        data_to_send = write_format.format(int(unit_code))
        
        response = self._build_and_send('set_value', 'unit', data=data_to_send)
        return response is not None and self.config['protocol']['device_address'] in response

    def get_reading(self) -> dict | None:
        """Gets a complete reading (pressure and unit) from the gauge."""
        pressure = self.read_value('pressure')
        unit_code = self.read_value('unit')
        
        if pressure is None or unit_code is None:
            return None
        
        return {
            "pressure": pressure,
            "unit": self.unit_name_map.get(f"{unit_code:03d}", "Unknown")
        }

    def start_logging_to_redis(self, redis_client, interval: float, redis_key: str):
        """Continuously reads from the gauge and writes to Redis."""
        print(f"Starting Redis logging every {interval}s. Press Ctrl+C to stop.")
        try:
            while True:
                reading = self.get_reading()
                if reading:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    reading['timestamp'] = timestamp
                    
                    try:
                        redis_client.set(redis_key, json.dumps(reading))
                        print(f"[{timestamp}] Wrote to Redis: {reading}")
                    except redis.exceptions.RedisError as e:
                        print(f"[{timestamp}] REDIS ERROR: Could not write to server. {e}")
                else:
                    print("Failed to get reading from gauge.")
                
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopping logger.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Control and monitor a Pfeiffer TPG 201 vacuum gauge with Redis logging.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--config', default=r'Communication Code/Vacuum_Gauge/TPG_201_Config.json', help='Path to TPG config file.')
    parser.add_argument('--redis-host', default='localhost', help='Redis server host.')
    parser.add_argument('--redis-port', type=int, default=6379, help='Redis server port.')
    parser.add_argument('--interval', type=float, default=1.0, help='Logging interval in seconds.')
    parser.add_argument('--redis-key', default='tpg201_reading', help='Redis key to store the reading.')

    args = parser.parse_args()

    controller = TPGController(args.config)
    if controller.connect():
        redis_client = redis.Redis(host=args.redis_host, port=args.redis_port, decode_responses=True)
        controller.start_logging_to_redis(redis_client, args.interval, args.redis_key)
        controller.disconnect()