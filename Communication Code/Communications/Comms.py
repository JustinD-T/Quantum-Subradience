import pyvisa
import time
import json

class VISAInterface():

    def __init__(self, communication_codes, defaults, address, timeout=1e6, visa_backend='@py'):
        
        # Set the address of the instrument
        self.address = address
        self.rm = pyvisa.ResourceManager(visa_backend)
        self.communication_codes = communication_codes
        self.defaults = defaults

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
            identity = self.instrument.query('*IDN?') # [cite: 105]
            print(f"Successfully connected to: {identity}")

        except Exception as e:
            print(f"Failed to connect to instrument at {self.address}: {e}")

    ###########################################################
    # Wrapper Utilization Functions
    ###########################################################
    
    def setupGeneric(self, save_path):
        # Set default values if they exist
        default_center = self.defaults.get("center_frequency", None)
        default_span = self.defaults.get("span", None)
        default_ref_level = self.defaults.get("reference_level", None)
        print(default_center, default_span, default_ref_level)
        if default_center is not None:
            self.setCenter(default_center)
        if default_span is not None:
            self.setSpan(default_span)
        if default_ref_level is not None:
            self.setReferenceLevel(default_ref_level)

        # Prepare the instrument for data acquisition
        init_code = self.communication_codes.get("init", None)
        if init_code:
            self.instrument.write(init_code) # [cite: 77]
        else:
            print('WARNING: No initialization communication code found.')

        # Save path for data
        self.save_path = save_path
        print(f"Data will be saved to: {self.save_path}")


    ###########################################################
    # Interface Functions
    ###########################################################

    def close(self):
        self.instrument.close()
        self.rm.close()
        print("VISA connection closed.")

    def setCenter(self, freq):
        self.center_freq = freq
        comm_code = self.communication_codes.get("setCenter", None)
        if comm_code:
            comm_code = comm_code.replace('FREQ', str(freq))
            self.instrument.write(comm_code) # [cite: 175]
        else:
            print('WARNING: No communication code found for setting center frequency.')

    def setSpan(self, span):
        self.span = span
        comm_code = self.communication_codes.get("setSpan", None)
        if comm_code:
            comm_code = comm_code.replace('SPAN', str(span))
            self.instrument.write(comm_code) # [cite: 175]
        else:
            print('WARNING: No communication code found for setting span.')

    def setReferenceLevel(self, ref_level):
        self.ref_level = ref_level
        comm_code = self.communication_codes.get("setReferenceLevel", None)
        if comm_code:
            comm_code = comm_code.replace('REF_LEVEL', str(ref_level))
            self.instrument.write(comm_code) # [cite: 128]
        else:
            print('WARNING: No communication code found for setting reference level.')

    def setResolutionBandwidth(self, rbw):
        self.rbw = rbw
        comm_code = self.communication_codes.get("setResolutionBandwidth", None)
        if comm_code:
            comm_code = comm_code.replace('RBW', str(rbw))
            self.instrument.write(comm_code) # [cite: 167]
        else:
            print('WARNING: No communication code found for setting resolution bandwidth.')

    def setVideoBandwidth(self, vbw):
        self.vbw = vbw
        comm_code = self.communication_codes.get("setVideoBandwidth", None)
        if comm_code:
            comm_code = comm_code.replace('VBW', str(vbw))
            self.instrument.write(comm_code) # [cite: 167]
        else:
            print('WARNING: No communication code found for setting video bandwidth.')
            
    def getData(self):
        # Set data format to ASCII for easy parsing
        format_code = self.communication_codes.get("setDataFormat", None)
        if format_code:
            self.instrument.write(format_code) # [cite: 131]
        else:
            print('WARNING: No communication code found for setting data format.')
            return

        # Query for the trace data
        data_code = self.communication_codes.get("getData", None)
        if data_code:
            print("Acquiring trace data...")
            trace_data = self.instrument.query(data_code) # [cite: 160]
            import matplotlib.pyplot as plt

            # Attempt to parse the trace data as a list of floats
            try:
                # Remove any extra whitespace and split by comma or newline
                if ',' in trace_data:
                    data_points = [float(x) for x in trace_data.strip().split(',')]
                else:
                    data_points = [float(x) for x in trace_data.strip().split()]
                
                # Plot the trace data
                plt.figure(figsize=(10, 5))
                plt.plot(data_points)
                plt.title('Instrument Trace Data')
                plt.xlabel('Point Index')
                plt.ylabel('Amplitude')
                plt.grid(True)
                plt.show()
            except Exception as e:
                print(f"Error parsing or plotting trace data: {e}")
            
            # Save the data to the specified file
            try:
                with open(self.save_path, 'w') as f:
                    f.write(trace_data)
                print(f"Data successfully saved to {self.save_path}")
            except Exception as e:
                print(f"Error saving data: {e}")
        else:
            print('WARNING: No communication code found for getting data.')


if __name__ == "__main__":
    # Load parameters from the JSON file
    with open(r'Communication Code\Wave Analyzer\setupParams.json', 'r') as f:
        setup_params = json.load(f)
    
    communication_codes = setup_params.get("communication_codes", {})
    address = setup_params.get("instrument_address", 'GPIB0::1::INSTR')
    timeout = setup_params.get("timeout", 1e6)
    visa_backend = setup_params.get("visa_backend", '@py')
    save_path = setup_params.get("save_path", f'./{time.strftime("%Y%m%d-%H%M%S")}_data.csv')
    defaults = setup_params.get("default_communication_values", {})

    # Initialize the interface
    visa_interface = VISAInterface(communication_codes, defaults, address, timeout, visa_backend)

    # Setup the instrument with default parameters
    visa_interface.setupGeneric(save_path)

    # --- Example Usage ---
    # You can add specific settings here if needed
    # visa_interface.setResolutionBandwidth(1e6) # Set RBW to 1 MHz
    
    # Wait for measurement to complete (adjust as needed)
    print("Waiting for measurement...")
    time.sleep(2) 

    # Get data from the instrument
    visa_interface.getData()
    
    # Close the connection
    visa_interface.close()