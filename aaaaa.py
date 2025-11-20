import pyvisa
import time

# Double check this matches what you set on the physical machine (You said 2)
GPIB_ADDRESS = 2
RESOURCE_STR = f'GPIB0::{GPIB_ADDRESS}::INSTR'

try:
    rm = pyvisa.ResourceManager('@py')
    print(f"1. Opening connection to {RESOURCE_STR}...")
    
    # CRITICAL: This tells PyVISA to automatically append '\n' to every write
    # and expect '\n' at the end of every read.
    inst = rm.open_resource(
        RESOURCE_STR, 
        write_termination='\n', 
        read_termination='\n'
    )
    
    # Set a generous timeout (5 seconds)
    inst.timeout = 5000
    
    # 2. Clear previous errors
    # *CLS wipes the "Unterminated" error from the screen
    print("2. Clearing status (*CLS)...")
    inst.write("*CLS") 
    time.sleep(0.5)

    # 3. The handshake
    print("3. Sending ID Query (*IDN?)...")
    # With write_termination set, this actually sends "*IDN?\n"
    idn = inst.query("*IDN?")
    
    print(f"\nSUCCESS! Instrument ID:\n{idn.strip()}")

except Exception as e:
    print(f"\nERROR: {e}")
    print("\nTroubleshooting:")
    print("1. Does the physical screen still show 'Remote'?")
    print("2. Did you run 'sudo chmod 666 /dev/gpib0'?")