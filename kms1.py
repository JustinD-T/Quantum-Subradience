import pyvisa

rm = pyvisa.ResourceManager('@py')

print(f"Scanning GPIB bus using: {rm}")

# Loop through all valid GPIB addresses
for addr in range(1, 31):
    resource_name = f"GPIB0::{addr}::INSTR"
    try:
        # Open resource with a short timeout to speed up the scan
        inst = rm.open_resource(resource_name)
        inst.timeout = 200  # 200ms timeout
        
        # Try to read the ID string
        idn = inst.query("*IDN?")
        print(f"\n✅ FOUND DEVICE AT ADDRESS {addr}:")
        print(f"   ID: {idn.strip()}")
        inst.close()
        
    except Exception:
        # If nobody answers, just print a dot and move on
        print(".", end="", flush=True)

print("\nScan complete.")