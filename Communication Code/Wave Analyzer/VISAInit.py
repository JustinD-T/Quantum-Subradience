# import gpib_ctypes
# gpib_ctypes.gpib.gpib._load_lib(r'C:\Windows\System32\agvisa32.dll')
import pyvisa

# Initialize the VISA resource manager
rm = pyvisa.ResourceManager()

# List all connected instruments (useful for finding the address)
print("Connected instruments:")
print(rm.list_resources())
# pyvisa.util.get_debug_info()

# Replace with the actual address you found in Step 1
instrument_address = 'GPIB0::1::INSTR' 

try:
    # Connect to the spectrum analyzer
    spec_an = rm.open_resource(instrument_address)
    
    # Set a timeout (good practice)
    spec_an.timeout = 5000 # 5 seconds

    # Ask the instrument for its identification string
    identity = spec_an.query('*IDN?')
    
    print(f"Successfully connected to: {identity}")

    # Close the connection
    spec_an.close()

except pyvisa.errors.VisaIOError as e:
    print(f"Error connecting to the instrument: {e}")