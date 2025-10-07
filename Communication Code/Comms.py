import pyvisa

class VISAInterface():

    def __init__(self, communication_codes, address, timeout=1e6, visa_backend='@py'):
        
        # Set the address of the instrument
        self.address = address
        self.rm = pyvisa.ResourceManager(visa_backend)
        self.communication_codes = communication_codes

        # Set a timeout (good practice)
        if timeout is not None:
            self.instrument_timeout = timeout
        else:
            self.instrument_timeout = None

        # Try to connect to the instrument
        try:
            self.instrument = self.rm.open_resource(self.address)
            if self.instrument_timeout is not None:
                self.instrument.timeout = self.instrument_timeout
            identity = self.instrument.query('*IDN?')
            print(f"Successfully connected to: {identity}")

        except Exception as e:
            print(f"Failed to connect to instrument at {self.address}: {e}")

    def close(self):
        self.instrument.close()
        self.rm.close()

    def setCenter(self, freq):
        self.center_freq = freq
        comm_code = self.communication_codes.get("setCenter", None)
        if comm_code:
            comm_code = comm_code.replace('FREQ', str(freq))
            self.instrument.write(comm_code)
        else:
            print('WARNING: No communication code found for setting center frequency.')

    def setSpan(self, span):
        self.span = span
        comm_code = self.communication_codes.get("setSpan", None)
        if comm_code:
            comm_code = comm_code.replace('SPAN', str(span))
            self.instrument.write(comm_code)
        else:
            print('WARNING: No communication code found for setting span.')

    def setReferenceLevel(self, ref_level):
        self.ref_level = ref_level
        comm_code = self.communication_codes.get("setReferenceLevel", None)
        if comm_code:
            comm_code = comm_code.replace('REF_LEVEL', str(ref_level))
            self.instrument.write(comm_code)
        else:
            print('WARNING: No communication code found for setting reference level.')



if __name__ == "__main__":
    import json

    with open('setupParams.json', 'r') as f:
        setup_params = json.load(f)
    
    communication_codes = setup_params.get("communication_codes", {})
    default_values = setup_params.get("default_communication_values", {})
    address = setup_params.get("instrument_address", 'GPIB0::18::INSTR')
    timeout = setup_params.get("timeout", 1e6)
    visa_backend = setup_params.get("visa_backend", '@py')

    visa_interface = VISAInterface(communication_codes, address, timeout, visa_backend)