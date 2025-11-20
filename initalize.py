from gpib_ctypes import make_default_gpib
make_default_gpib()

import pyvisa as pv
import re

def setup_gpib():

    # Find GPIB addresses
    gpib = find_gpib_addr()
    if len(gpib) > 0:
        print("GPIB Devices Found:")
        for i, addr in enumerate(gpib):
            print(f"{i+1} - {addr}")
        gpid_addr = gpib[int(input("Select GPIB Address Number: ")) - 1]
    else:
        print("No GPIB devices found.")
        return False
    
    # Test connection
    idn = test_connection(gpid_addr)
    if "Connection failed" in idn:
        print(idn)
        return False
    else:
        print(f"Connected to device: {idn}")
        return gpid_addr



def find_gpib_addr():
    rm = pv.ResourceManager('@py')
    print("VISA Library:", rm.visalib)
    ports = rm.list_resources()
    gpib_ports = [p for p in ports if re.search(r'GPIB\d+::\d+::INSTR', p)]
    return gpib_ports


def find_ports(usb_only = True):
    rm = pv.ResourceManager('@py')
    print("VISA Library:", rm.visalib)
    ports = rm.list_resources()
    if not usb_only:
        return ports
    else:
        usb_ports = [p for p in ports if re.search(r'(tty(?:USB|ACM)\d+|USB|GPIB\d+::\d+)', p)]
        return usb_ports

def test_connection(address):
    print(f"Testing connection to {address}...")
    rm = pv.ResourceManager('@py')
    # try:
    inst = rm.open_resource(address)
    idn = inst.query('*IDN?')
    print(idn)
    return idn.strip()
    # except Exception as e:
    #     return f"Connection failed: {e}"


if __name__ == '__main__':
    setup_gpib()
    # print(find_ports(False))