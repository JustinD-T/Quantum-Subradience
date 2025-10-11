import json
import time
import pyvisa

comms_path = r'Communication Code\Wave Analyzer\WaveCodes.json'
defaults_path = r'Communication Code\Wave Analyzer\Defaults.json'

with open(comms_path, 'r') as f:
    comms = json.load(f)
with open(defaults_path, 'r') as f:
    defaults = json.load(f)

rm = pyvisa.ResourceManager()
instrument = rm.open_resource(defaults['instrument_address'])

center_freq = defaults.get("center_frequency", None)
code = comms['set_center_frequency'].replace('REPLACE_ME', str(center_freq))
span = defaults.get("span", None)
code2 = comms['set_x_span'].replace('REPLACE_ME', str(span))
auto_sweep_time = defaults.get("auto_sweep_time", None)
code3 = comms['set_auto_sweep_time'].replace('REPLACE_ME', str(auto_sweep_time))
averaging_state = defaults.get("averaging_state", None)
code4 = comms['set_averaging_state'].replace('REPLACE_ME', '1')
averaging_count = defaults.get("averaging_count", None)
code5 = comms['set_averaging_count'].replace('REPLACE_ME', '100')
print(code4)
instrument.write(code4)
print(code5)
instrument.write(code5)
print(code3)
instrument.write(code3)
print(code)
instrument.write(code)
print(code2)
instrument.write(code2)
print(instrument.query(":FREQuency:CENTer?"))
print(instrument.query(":SWEep:TIME?"))