import pyvisa
import time
 
 
# Tolerance for floating-point readback comparisons (relative, 0.1%)
_FLOAT_RTOL = 1e-3
 
# Maximum retries per setting before giving up and raising
_MAX_RETRIES = 3
 
# Delay between retries (seconds) — gives the instrument time to settle
_RETRY_DELAY = 2.5
 
 
class SpectrumAnalyzer():
 
    def __init__(self, config, callback):
        self.config   = config
        self.callback = callback
 
        # ── VISA resource manager ──────────────────────────────────────────
        # visa_backend lives at the top of the spectrum_analyzer config block,
        # not inside 'visa' — matching the original SpectrumAnalyzer behaviour.
        try:
            visa_backend = config.get('visa_backend', None) or config['visa'].get('visa_backend', None)
            self.rm = (pyvisa.ResourceManager(visa_backend)
                       if visa_backend else pyvisa.ResourceManager())
        except Exception as e:
            raise ConnectionError(f"Failed to initialize VISA Resource Manager: {e}")
 
        # ── Connect ────────────────────────────────────────────────────────
        try:
            resource_string = config['visa']['resource_string']
            self.instrument = self.rm.open_resource(resource_string)
            self.instrument.timeout = config['visa'].get('timeout', 5000)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Spectrum Analyzer: {e}")
 
        self.commands  = config['commands']
        visa           = config['visa']
 
        # ── Data format & byte order (write-only, no numeric readback) ────
        # These are bus-level formatting commands; the instrument has no
        # corresponding query so we just write-and-OPC each one.
        self._write_opc(
            self.commands['set_data_format'],
            visa.get('data_format', 'REAL, 32'),
            label='data_format'
        )
        self._write_opc(
            self.commands['set_byte_order'],
            visa.get('byte_order', 'SWAP'),
            label='byte_order'
        )
 
        # ── All settings that have a paired query command ──────────────────
        # Each tuple: (config_key, default, set_cmd, query_cmd, value_type)
        # value_type: 'float' → numeric tolerance check
        #             'str'   → case-insensitive string prefix check
        #             'int'   → exact integer check
 
        settings = [
            # (config key,          default,   set cmd key,            query cmd key,             type )
            ('center_frequency',    2.5e9,     'set_center_frequency', 'query_center_frequency',  'float'),
            ('reference_level',     0,         'set_reference_level',  'query_reference_level',   'float'),
            ('span',                1e8,       'set_span',             'query_span',               'float'),
            ('power_unit',          'DBM',     'set_power_unit',       'query_power_unit',         'str'  ),
            ('num_points',          401,       'set_num_points',       'query_sweep_points',       'int'  ),
            ('detector_mode',       'AVER',    'set_detector_mode',    'query_detector_mode',      'str'  ),
            ('attenuation',         20,        'set_attenuation',      'query_attenuation',        'float'),
            ('RBW',                 1e6,       'set_RBW',              'query_RBW',                'float'),
            ('VBW',                 1e5,       'set_VBW',              'query_VBW',                'float'),
            ('amplitude_space',     'LOG',     'set_amplitude_space',  'query_amplitude_space',    'str'  ),
        ]
 
        for cfg_key, default, set_cmd_key, query_cmd_key, vtype in settings:
            desired = visa.get(cfg_key, default)
            self._verified_write(
                set_cmd   = self.commands[set_cmd_key],
                query_cmd = self.commands[query_cmd_key],
                desired   = desired,
                vtype     = vtype,
                label     = cfg_key,
            )
 
        # ── Sweep time (special: auto vs manual) ──────────────────────────
        auto_sweep = int(visa.get('auto_sweep_time', 0))
        manual_sweep_ms = visa.get('sweep_time', None)
 
        if auto_sweep != 0 and manual_sweep_ms is not None:
            self.log('error',
                     'MAJOR ERROR: auto_sweep_time is enabled while sweep_time '
                     'is also specified! Overriding with manual sweep_time.')
 
        # Always write the auto setting first so it is in a known state
        self._write_opc(
            self.commands['set_sweep_time_auto'],
            str(auto_sweep),
            label='auto_sweep_time'
        )
 
        if auto_sweep != 1:
            # Manual sweep time — write, OPC, then readback verify
            sweep_time_s = manual_sweep_ms / 1000.0
            self._verified_write(
                set_cmd   = self.commands['set_sweep_time'],
                query_cmd = self.commands['query_sweep_time'],
                desired   = sweep_time_s,
                vtype     = 'float',
                label     = 'sweep_time',
            )
            self.auto_sweep = False
        else:
            self.auto_sweep = True
 
        # ── Sweep mode (single / continuous) ──────────────────────────────
        # No standard query command for this; write-and-OPC only.
        sweep_mode = visa.get('auto_sweep', 'OFF')
        self._write_opc(
            self.commands['set_sweep_mode'],
            sweep_mode,
            label='auto_sweep'
        )
 
        # ── Display on/off ─────────────────────────────────────────────────
        display_on = visa.get('display_on', 'ON')
        self._write_opc(
            self.commands['set_display_on'],
            display_on,
            label='display_on'
        )
 
        # ── Averaging State ──────────────────────────────────────────
        averaging_state = visa.get('averaging_state', 'OFF')
        self._write_opc(
            self.commands['set_averaging_state'],
            averaging_state,
            label='averaging_state'
        )

        # ── Pre-amp ────────────────────────────────────────────────────────
        pre_amp = visa.get('pre_amp', 'OFF')
        self._write_opc(
            self.commands['set_pre_amp'],
            pre_amp,
            label='pre_amp'
        )
 
        # ── Settling sweep: apply all settings and discard result ──────────
        try:
            self.instrument.write(self.commands['initiate_sweep'])
            self.instrument.query_binary_values(
                self.commands['query_trace_data'],
                datatype='f',
                is_big_endian=False
            )
            print('[SpectrumAnalyzer] Settling sweep complete.')
        except Exception as e:
            self.log('error', f"Error during settling sweep: {e}")
 
        # ── Frequency axis ─────────────────────────────────────────────────
        try:
            self.start_freq       = self.instrument.query(self.commands['query_frequency_start'])
            self.stop_freq        = self.instrument.query(self.commands['query_frequency_stop'])
            self.num_sweep_points = self.instrument.query(self.commands['query_sweep_points'])
        except Exception as e:
            self.log('error', f"Error querying frequency axis: {e}")

        n = int(self.num_sweep_points)
        f0 = float(self.start_freq)
        f1 = float(self.stop_freq)
        self.spectral_axis = [f0 + i * (f1 - f0) / (n - 1) for i in range(n)]

    # ── Verified write helper ──────────────────────────────────────────────────
 
    def _verified_write(self, set_cmd, query_cmd, desired, vtype, label,
                        max_retries=_MAX_RETRIES):
        """
        Write a setting, wait for OPC, read it back, and confirm it matches.
        Retries up to `max_retries` times before logging an error and giving up.
 
        Parameters
        ----------
        set_cmd     : SCPI write command string (contains literal 'value' placeholder)
        query_cmd   : SCPI query command string
        desired     : The value we want to set (Python int/float/str)
        vtype       : 'float' | 'int' | 'str'
        label       : Human-readable name for log messages
        """
        for attempt in range(1, max_retries + 1):
            try:
                # Write
                write_str = set_cmd.replace('value', str(desired))
                self.instrument.write(write_str)
 
                # Wait for operation complete
                while int(self.instrument.query(self.commands['operation_complete_query'])) != 1:
                    time.sleep(0.1)
 
                # Read back
                readback_raw = self.instrument.query(query_cmd).strip()
 
                # Verify
                match = self._check_readback(desired, readback_raw, vtype)
 
                if match:
                    print(f'[SA] {label} = {desired}  ✓  (readback: {readback_raw})')
                    return
                else:
                    self.log('error',
                             f'[SA] {label}: readback mismatch on attempt {attempt}/{max_retries} '
                             f'— wrote {desired!r}, got {readback_raw!r}. Retrying…')
                    time.sleep(_RETRY_DELAY)
 
            except Exception as e:
                self.log('error',
                         f'[SA] {label}: exception on attempt {attempt}/{max_retries}: {e}')
                time.sleep(_RETRY_DELAY)
 
        # All retries exhausted
        self.log('error',
                 f'[SA] {label}: FAILED to verify after {max_retries} attempts. '
                 f'Continuing with potentially incorrect setting.')
 
    def _check_readback(self, desired, readback_raw, vtype):
        """Return True if readback matches desired within tolerance."""
        try:
            if vtype == 'float':
                rb = float(readback_raw)
                d  = float(desired)
                # Relative tolerance; fall back to absolute if desired == 0
                if d == 0:
                    return abs(rb) < 1e-9
                return abs(rb - d) / abs(d) <= _FLOAT_RTOL
            elif vtype == 'int':
                return int(readback_raw) == int(desired)
            elif vtype == 'str':
                # The instrument often returns a longer form of the abbreviation
                # (e.g. we send "AVER", instrument returns "AVERAGE").
                # Accept if either is a prefix of the other, case-insensitive.
                rb = readback_raw.strip().upper()
                d  = str(desired).strip().upper()
                return rb.startswith(d) or d.startswith(rb)
        except (ValueError, TypeError):
            return False
        return False
 
    def _write_opc(self, cmd, value, label):
        """
        Write a setting that has no corresponding query (data format, byte
        order, sweep mode, display, pre-amp).  Waits for OPC only.
        """
        try:
            self.instrument.write(cmd.replace('value', str(value)))
            while int(self.instrument.query(self.commands['operation_complete_query'])) != 1:
                time.sleep(0.1)
            print(f'[SA] {label} = {value}')
        except Exception as e:
            self.log('error', f'[SA] Error setting {label} to {value!r}: {e}')
 
    # ── Runtime methods ────────────────────────────────────────────────────────
 
    def log(self, log_type, message):
        if self.callback:
            self.callback(log_type, message)
    
    def get_amplitudes(self):
            t0 = time.perf_counter()
            try:
                # 1. ATOMIC SWEEP: Tell it to sweep AND wait for completion in one string.
                # This prevents Python from spamming the bus while the instrument is busy.
                self.instrument.query(f"{self.commands['initiate_sweep']};*OPC?")

                # 2. Now that we know for a fact it is done, safely fetch the data.
                amplitudes = self.instrument.query_binary_values(
                    self.commands['query_trace_data'],
                    datatype='f',
                    is_big_endian=False
                )

                t1 = time.perf_counter()
                fetch_ms = (t1 - t0) * 1000

                # 3. We no longer re-arm the sweep here. It will be armed at the 
                # start of the next cycle. This guarantees no dropped commands.

                return {
                    "N_pts":      len(amplitudes),
                    "Amplitudes": amplitudes,
                    "Timestamp":  time.time(),
                    "_diag_fetch_ms": fetch_ms  # The typo is officially fixed!
                }

            except pyvisa.errors.VisaIOError as e:
                # If a timeout DOES happen (e.g., sweep is actually longer than 10s)
                print(f"\n[SA RECOVERY] VISA Timeout! Clearing bus...")
                self.instrument.clear()
                raise RuntimeError(f"Analyzer failed to complete sweep within 10s: {e}")
                         
    def get_instrument_data(self):
        N_points       = self.instrument.query(self.commands['query_sweep_points']).strip()
        freq_stop      = self.instrument.query(self.commands['query_frequency_stop']).strip()
        freq_start     = self.instrument.query(self.commands['query_frequency_start']).strip()
        center_freq    = self.instrument.query(self.commands['query_center_frequency']).strip()
        ref_level      = self.instrument.query(self.commands['query_reference_level']).strip()
        power_unit     = self.instrument.query(self.commands['query_power_unit']).strip()
        amplitude_space= self.instrument.query(self.commands['query_amplitude_space']).strip()
        span           = self.instrument.query(self.commands['query_span']).strip()
        rbw            = self.instrument.query(self.commands['query_RBW']).strip()
        vbw            = self.instrument.query(self.commands['query_VBW']).strip()
        attenuation    = self.instrument.query(self.commands['query_attenuation']).strip()
        detector_type  = self.instrument.query(self.commands['query_detector_mode']).strip()
        if self.auto_sweep:
            sweep_time = 'Auto'
        else:
            # Instrument returns sweep time in seconds; convert to ms to match
            # the original get_instrument_data() contract that callers expect.
            sweep_time_s = self.instrument.query(self.commands['query_sweep_time']).strip()
            try:
                sweep_time = str(float(sweep_time_s) * 1000)
            except ValueError:
                sweep_time = sweep_time_s
        return {
            "Number of Points":      N_points,
            "Span":                  span,
            "Frequency Start (Hz)":  freq_start,
            "Frequency Stop (Hz)":   freq_stop,
            "Center Frequency (Hz)": center_freq,
            "Reference Level (dBm)": ref_level,
            "Power Unit":            power_unit,
            "Sweep Time (ms)":       sweep_time,
            "RBW (Hz)":              rbw,
            "VBW (Hz)":              vbw,
            "Attenuation (dB)":      attenuation,
            "Detector Type":         detector_type,
            "Amplitude Space":       amplitude_space,
        }
 
    def get_spectral_axis(self):
        return self.spectral_axis