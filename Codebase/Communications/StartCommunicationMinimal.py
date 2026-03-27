"""
StartCommunication.py  –  High-Speed Headless Data Recorder
============================================================
Architecture
------------
                ┌─────────────────────────────────┐
                │   SPECTRUM THREAD (tight loop)   │
                │  initiate → wait OPC → read →    │
                │  push to spec_queue → initiate…  │
                └──────────────┬──────────────────┘
                               │ spec_queue
                ┌──────────────▼──────────────────┐
                │      MAIN / COORDINATOR THREAD   │
                │  pop spectrum result             │
                │  read pressure (inline, fast)    │
                │  compute metrics                 │
                │  push to write_queue             │
                │  print status line               │
                └──────────────┬──────────────────┘
                               │ write_queue
                ┌──────────────▼──────────────────┐
                │     BACKGROUND CSV WRITER        │
                │  format row → append → flush     │
                └─────────────────────────────────┘

Key design decisions
--------------------
* The spectrum thread NEVER sleeps intentionally.  As soon as get_amplitudes()
  returns (which already re-initiates the next sweep internally), it loops back
  and waits for OPC.  This keeps the analyzer integrating continuously.

* Pressure reads happen in the coordinator thread while the spectrum thread is
  busy waiting.  They are NOT run concurrently with the spectrum fetch because
  the pressure serial read is fast (~3 ms) and avoids the overhead of spawning
  futures every cycle.

* CSV writes are fully off the hot path.  The write_queue is unbounded so a
  slow disk never blocks the measurement loop.  The writer flushes + fsyncs
  every N rows so a crash leaves a valid file.

* If the pressure sensor dies mid-run, the coordinator catches the exception,
  flags pressure as failed, and continues recording spectrum data with empty
  pressure columns.

* The CSV format, column order, file prefix (HSReader_), and log folder are
  identical to the original implementation.
"""

from PressureSensor import PressureSensor
from SpectrumAnalyzer import SpectrumAnalyzer

import os
import csv
import time
import json
import threading
import argparse
from queue import Queue, Empty, Full


# ──────────────────────────────────────────────────────────────────────────────
#  Spectrum acquisition thread
#  Runs a tight acquire→queue loop with no unnecessary delays.
# ──────────────────────────────────────────────────────────────────────────────

def _spectrum_thread(analyzer, out_queue, stop_event, err_callback):
    """
    Dedicated spectrum acquisition loop.

    get_amplitudes() blocks until OPC (the sweep that was pre-initiated is
    complete), grabs the data, then immediately re-initiates the next sweep
    before returning.  We call it in a tight loop so there is never a gap
    between sweeps unless something else is slow.
    """
    while not stop_event.is_set():
            try:
                result = analyzer.get_amplitudes()
                out_queue.put(result)
            except Exception as e:
                err_callback(f"[Spectrum Thread ERROR] {e}")
                time.sleep(0.05)

# ──────────────────────────────────────────────────────────────────────────────
#  Background CSV writer thread
# ──────────────────────────────────────────────────────────────────────────────

def _csv_writer_thread(file_path, fields, non_freq_fields, write_queue,
                       stop_event, flush_every, has_spectrum, has_pressure):
    """
    Pops items off write_queue and appends them to the open CSV.
    Never blocks the measurement loop.
    Flushes + fsyncs every `flush_every` rows so a crash leaves valid data.
    """
    row_count = 0
    with open(file_path, mode='a', newline='') as fh:
        writer = csv.writer(fh)

        while not stop_event.is_set() or not write_queue.empty():
            try:
                item = write_queue.get(timeout=0.5)
            except Empty:
                continue

            # Build the scalar portion of the row from the non-freq fields
            data_map = {
                'Timestamp':                item['timestamp'],
                'Elapsed Time (s)':         item['elapsed'],
                'Cycle Count':              item['cycle_ct'],
            }
            if has_spectrum:
                data_map['Effective Integration (%)'] = item['eff_int_pct']
            if has_pressure:
                data_map['Pressure']      = item['pressure']       # float('nan') when absent
                data_map['Pressure_Unit'] = item['pressure_unit']  # 'nan' when absent

            row = [data_map.get(f, '') for f in non_freq_fields]

            # Append amplitude columns (may be empty list if spectrum failed)
            row.extend(item.get('amplitudes', []))

            writer.writerow(row)
            row_count += 1

            if row_count % flush_every == 0:
                fh.flush()
                os.fsync(fh.fileno())

            write_queue.task_done()

        # Final flush on exit
        fh.flush()
        os.fsync(fh.fileno())


# ──────────────────────────────────────────────────────────────────────────────
#  CommunicationMaster
# ──────────────────────────────────────────────────────────────────────────────

class CommunicationMaster:

    def __init__(self, config, args):
        self.config = config
        self.args   = args

        self.logging_path     = (os.path.join(os.path.curdir, 'ExperimentLogs')
                                 if args.logp is None else args.logp)
        self.interval         = config['program'].get('reading_interval', 1.0)
        self.logging_enabled  = not args.nolog
        self.spectrum_enabled = not args.nospectrum
        self.pressure_enabled = not args.nopressure
        self.verbose          = args.verbose

        self._stop_event = threading.Event()

        # ── Instrument initialisation ──────────────────────────────────────
        if self.pressure_enabled:
            try:
                self.pressure_sensor = PressureSensor(
                    config['pressure_sensor'], self._pressure_cb)
            except Exception as e:
                print(f"[WARN] Pressure Sensor init failed (continuing without): {e}")
                self.pressure_enabled = False

        if self.spectrum_enabled:
            try:
                self.spectrum_analyzer = SpectrumAnalyzer(
                    config['spectrum_analyzer'], self._spectrum_cb)
            except Exception as e:
                print(f"[WARN] Spectrum Analyzer init failed (continuing without): {e}")
                self.spectrum_enabled = False

        # ── Logging setup ──────────────────────────────────────────────────
        if self.logging_enabled:
            self._setup_logging()

    # ── Logging / CSV setup ───────────────────────────────────────────────────

    def _setup_logging(self):
        os.makedirs(self.logging_path, exist_ok=True)

        timestamp = time.strftime('%Y%m%d-%H%M%S', time.localtime())
        log_file_path = os.path.join(
            self.logging_path, f'HSReader_{timestamp}.csv')
        self.log_file_path = log_file_path

        # ── Collect instrument info before prompting user ──────────────────
        spec_header_info = {}
        self.spec_sweep_time_ms = None
        spectral_axis = []

        if self.spectrum_enabled:
            spec_header_info  = self.spectrum_analyzer.get_instrument_data()
            self.spec_sweep_time_ms = float(
                spec_header_info.get(
                    'Sweep Time (ms)',
                    self.config['spectrum_analyzer']['visa'].get('sweep_time', 100)
                )
            )
            spectral_axis = self.spectrum_analyzer.get_spectral_axis()

        # ── User prompts (identical to original) ──────────────────────────
        init_CO_conc = 'N/A'
        init_ml      = 'N/A'
        CO_bool = input('CO or Acetonitrile? (C/A): ')
        if CO_bool.lower() == 'c':
            init_CO_conc = input(
                "Enter initial CO Concentration in ppm (or leave blank to skip): ")
        self.gas_correction = None   # applied to display only, never saved
        if CO_bool.lower() == 'a':
            init_ml = input(
                "Enter Acetonitrile Volume in mL (or leave blank to skip): ")
            _gc_raw = input(
                "Enter Acetonitrile gas correction coefficient "
                "(e.g. 0.4 – leave blank to skip): ").strip()
            if _gc_raw:
                try:
                    self.gas_correction = float(_gc_raw)
                    print(f"[INFO] Gas correction coefficient set to "
                          f"{self.gas_correction} "
                          f"(applied to terminal display only).")
                except ValueError:
                    print("[WARN] Invalid gas correction value – ignoring.")
        init_ac_gc  = self.gas_correction if self.gas_correction is not None else 'N/A'
        input_gain  = input(
            "Enter Effective Gain at Input in dB (or leave blank to skip): ")
        description = input("Enter experiment description (or leave blank): ")

        # ── Build field list ───────────────────────────────────────────────
        fields = [
            'Timestamp',
            'Elapsed Time (s)',
            'Cycle Count',
        ]
        if self.pressure_enabled:
            fields.extend(['Pressure', 'Pressure_Unit'])
        if self.spectrum_enabled:
            fields.insert(3, 'Effective Integration (%)')

        self.non_freq_fields = fields.copy()

        if self.spectrum_enabled:
            fields.extend([f"{freq} Hz" for freq in spectral_axis])

        self.fields = fields

        # ── Write file header (identical to original) ─────────────────────
        header = f"""# Experiment Log ({timestamp})
#    Experiment Description: {description}
# Experiment Configuration:
#    logging_enabled: {self.logging_enabled}
#    spectrum_enabled: {self.spectrum_enabled}
#    pressure_enabled: {self.pressure_enabled}
#    visualization_enabled: False
#    reading_interval (s): {self.interval}
#    visual_update_cycle_interval: N/A (headless mode)
#    Effective Gain at Input (Db) : {input_gain if input_gain != '' else 'N/A'}
#    initial_CO_concentration (ppm): {init_CO_conc if init_CO_conc != '' else 'N/A'}
#    initial_Acetonitrile_volume (mL): {init_ml if init_ml != '' else 'N/A'}
#    acetonitrile_gas_correction_coefficient: {init_ac_gc} (NOTE: applied to terminal display only - raw N2-equivalent sensor values are saved)
#       Formula used for display: P_true = P_indicated / correction_factor
# Serial Configuration ({'ENABLED' if self.pressure_enabled else 'DISABLED'}):
#    Port: {self.config['pressure_sensor']['serial'].get('port', 'COM1')}
#    Baudrate: {self.config['pressure_sensor']['serial'].get('baudrate', 9600)}
#    Bytesize: {self.config['pressure_sensor']['serial'].get('bytesize', 8)}
#    Parity: {self.config['pressure_sensor']['serial'].get('parity', 'N')}
#    Stopbits: {self.config['pressure_sensor']['serial'].get('stopbits', 1)}
#    Timeout (ms): {float(self.config['pressure_sensor']['serial'].get('timeout', 3)) * 1000}
# Spectrum Analyzer Configuration ({'ENABLED' if self.spectrum_enabled else 'DISABLED'}):
#    Resource String: {self.config['spectrum_analyzer']['visa'].get('resource_string', 'N/A')}
#    VISA Backend: {self.config['spectrum_analyzer'].get('visa_backend') or self.config['spectrum_analyzer']['visa'].get('visa_backend', 'None Specified')}
#    Timeout (ms): {self.config['spectrum_analyzer']['visa'].get('timeout', 'N/A')}
#    Data Format: {self.config['spectrum_analyzer']['visa'].get('data_format', 'N/A')}
#    Byte Order: {self.config['spectrum_analyzer']['visa'].get('byte_order', 'N/A')}
#    Number of Points: {spec_header_info.get('Number of Points', 'N/A')}
#    Sweep Time (ms): {spec_header_info.get('Sweep Time (ms)', 'N/A')}
#    Span: {spec_header_info.get('Span', 'N/A')}
#    RBW (Hz): {spec_header_info.get('RBW (Hz)', 'N/A')}
#    VBW (Hz): {spec_header_info.get('VBW (Hz)', 'N/A')}
#    Attenuation (dB): {spec_header_info.get('Attenuation (dB)', 'N/A')}
#    Detector Type: {spec_header_info.get('Detector Type', 'N/A')}
#    Amplitude Space: {spec_header_info.get('Amplitude Space', 'N/A')}
#    Frequency Start (Hz): {spec_header_info.get('Frequency Start (Hz)', 'N/A')}
#    Frequency Stop (Hz): {spec_header_info.get('Frequency Stop (Hz)', 'N/A')}
#    Center Frequency (Hz): {spec_header_info.get('Center Frequency (Hz)', 'N/A')}
#    Reference Level ({spec_header_info.get('Power Unit', 'N/A')}): {spec_header_info.get('Reference Level (dBm)', 'N/A')}
#    Power Unit: {spec_header_info.get('Power Unit', 'N/A')}
# Data Columns:
#    Timestamp: Time of the log entry in ISO 8601 format (measured at start of logging cycle)
#    Elapsed Time (s): Time since the start of logging in seconds (measured at start of logging cycle)
#    Cycle Count: Count of measurement cycle
#    Pressure Sensor Readings (if enabled):
#       Pressure: Pressure reading from the sensor in specified units
#       Pressure_Unit: Unit of the pressure reading
#    Spectrum Analyzer Readings (if enabled):
#       Effective Integration (%): Percentage of a full cycle the Spectrum Analyzer is integrating signal over
#       *amplitudes will be headed as their frequency value in Hz in subsequent columns (eg. 2450000000.0 Hz)*
"""
        with open(log_file_path, mode='w', newline='') as fh:
            fh.write(header)
            csv.writer(fh).writerow(self.fields)

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self):
        stop_event   = self._stop_event
        spec_queue   = Queue(maxsize=4)
        write_queue  = Queue()

        # Start Threads (Same as your code)
        spec_thread = None
        if self.spectrum_enabled:
            spec_thread = threading.Thread(
                target=_spectrum_thread,
                args=(self.spectrum_analyzer, spec_queue, stop_event, lambda msg: print(msg)),
                name='SpectrumAcq', daemon=True
            )
            spec_thread.start()

        writer_stop = threading.Event()
        writer_thread = None
        if self.logging_enabled:
            writer_thread = threading.Thread(
                target=_csv_writer_thread,
                args=(self.log_file_path, self.fields, self.non_freq_fields, write_queue,
                      writer_stop, 50, self.spectrum_enabled, self.pressure_enabled),
                name='CSVWriter', daemon=True
            )
            writer_thread.start()

        start_time        = time.time()
        cycle_ct          = 0
        prev_elapsed      = None
        pressure_ok       = self.pressure_enabled 

        print("\n[HSReader] Recording started.  Press Ctrl+C to stop.\n")
        print(f"  {'Cycle':>7}  {'Elapsed':>10}  {'Pressure':>16}  "
              f"{'Eff %':>7}  {'Int Time':>12}")
        print("  " + "-" * 62)

        try:
            while not stop_event.is_set():
                loop_start   = time.time()
                elapsed      = loop_start - start_time

                # ── 1. Grab the next completed spectrum sweep ──────────────
                s_res = None
                if self.spectrum_enabled:
                    try:
                        # Kept at 25s for stability, even though your sweep is faster now
                        s_res = spec_queue.get(timeout=25.0) 
                        spec_queue.task_done()
                    except Empty:
                        print("[WARN] Spectrum queue timeout – skipping cycle "
                              f"{cycle_ct}, row will NOT be written.")
                        continue   

                # ── 2. Read pressure (fast serial, inline) ─────────────────
                p_res = None
                if pressure_ok:
                    try:
                        p_res = self.pressure_sensor.get_reading()
                    except Exception as e:
                        print(f"[ERROR] Pressure Sensor failed: {e}  "
                              f"(continuing spectrum-only recording)")
                        pressure_ok = False
                        try:
                            self.pressure_sensor.disconnect()
                        except Exception:
                            pass

                # ── 3. Metrics ────────────────────────────────────────────
                cycle_time_ms = (
                    (elapsed - prev_elapsed) * 1000
                    if prev_elapsed is not None else 0.0
                )

                eff_int_pct = 0.0
                if s_res and self.spec_sweep_time_ms and cycle_time_ms > 0:
                    eff_int_pct = min(
                        100.0,
                        (self.spec_sweep_time_ms / cycle_time_ms) * 100.0
                    )

                pressure_val  = p_res['pressure'] if p_res else float('nan')
                pressure_unit = p_res['unit']      if p_res else 'nan'

                # ── 4. Terminal status line ────────────────────────────────
                if p_res:
                    p_display_val = (pressure_val / self.gas_correction
                                     if self.gas_correction is not None
                                     else pressure_val)
                    gc_marker = '*' if self.gas_correction is not None else ' '
                    p_display = f"{p_display_val:.3e}{gc_marker}{pressure_unit}"
                else:
                    p_display = "  --   "

                sweep_time_s = (self.spec_sweep_time_ms / 1000.0
                                if self.spec_sweep_time_ms else 0.0)
                int_time_s  = sweep_time_s * (cycle_ct + 1)
                int_display = f"{int_time_s:.1f} s" if self.spectrum_enabled else "  N/A  "

                print(
                    f"  {cycle_ct:>7d}  "
                    f"{elapsed:>10.1f}s  "
                    f"{p_display:>16}  "
                    f"{eff_int_pct:>7.1f}  "
                    f"{int_display:>12}"
                )
                # ── 5. Queue CSV row ───────────────────────────────────────
                if self.logging_enabled:
                    write_queue.put({
                        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(loop_start)),
                        'elapsed': elapsed,
                        'cycle_ct': cycle_ct,
                        'eff_int_pct': eff_int_pct,
                        'pressure': pressure_val,
                        'pressure_unit': pressure_unit,
                        'amplitudes': list(s_res['Amplitudes']) if s_res else [],
                    })

                prev_elapsed = elapsed
                cycle_ct += 1

                # ── 6. Intelligent sleep ───────────────────────────────────
                work_dur = time.time() - loop_start
                sleep_time = max(0.0, self.interval - work_dur)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n[HSReader] Shutdown initiated...")
        finally:
            self._shutdown(stop_event, writer_stop, spec_thread, writer_thread, write_queue)

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def _shutdown(self, stop_event, writer_stop,
                  spec_thread, writer_thread, write_queue):
        print("[HSReader] Stopping threads…")
        stop_event.set()

        if spec_thread and spec_thread.is_alive():
            spec_thread.join(timeout=5)

        # Signal writer to drain and exit
        writer_stop.set()
        if writer_thread and writer_thread.is_alive():
            write_queue.join()          # wait for all queued rows to flush
            writer_thread.join(timeout=10)

        # Disconnect instruments gracefully
        if self.pressure_enabled:
            try:
                self.pressure_sensor.disconnect()
            except Exception:
                pass

        print("[HSReader] Shutdown complete.")

    # ── Instrument callbacks ──────────────────────────────────────────────────

    def _pressure_cb(self, log_type, message):
        if log_type == 'error':
            print(f"[Pressure Sensor ERROR] {message}")
        elif log_type == 'message' and self.verbose:
            print(f"[Pressure Sensor] {message}")

    def _spectrum_cb(self, log_type, message):
        if log_type == 'error':
            print(f"[Spectrum Analyzer ERROR] {message}")
        elif log_type == 'message' and self.verbose:
            print(f"[Spectrum Analyzer] {message}")


# ──────────────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────────────

def load_config(path):
    with open(path, 'r') as fh:
        return json.load(fh)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='HSReader – High-Speed Headless Spectrum + Pressure Recorder')
    parser.add_argument('-logp',   type=str, default=None,
                        help='Logging folder path')
    parser.add_argument('-config', type=str,
                        default=r'Codebase\Communications\Config_HS.json',
                        help='Path to configuration file')
    parser.add_argument('--nolog',      default=False, action='store_true',
                        help='Disable CSV logging')
    parser.add_argument('--nospectrum', default=False, action='store_true',
                        help='Disable spectrum analyzer')
    parser.add_argument('--nopressure', default=False, action='store_true',
                        help='Disable pressure sensor')
    # --novisual and --novisual are accepted but silently ignored
    # (this script is always headless)
    parser.add_argument('--novisual',   default=False, action='store_true',
                        help='(Ignored – this script is always headless)')
    parser.add_argument('--verbose',    default=False, action='store_true',
                        help='Print informational messages from instruments')

    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"FATAL: Could not load config: {e}")
        raise SystemExit(1)

    master = CommunicationMaster(config, args)
    master.run()