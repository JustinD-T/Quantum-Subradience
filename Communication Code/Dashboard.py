import sys
import time
import json
import redis
import csv
import os
from collections import deque
import numpy as np

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLineEdit, QLabel, QGridLayout, QGroupBox, QMessageBox)
from PyQt6.QtCore import QThread, QObject, pyqtSignal, QTimer

import pyqtgraph as pg

# Import your existing controller classes
from Vacuum_Gauge.VacuumGaugeController import TPGController
from Wave_Analyzer.SpectrumAnalyzerController import SpectrumAnalyzerController

# --- Worker Threads for Data Acquisition ---

class InstrumentWorker(QObject):
    """
    A generic worker that runs in a QThread to continuously poll an instrument.
    The polling interval can be changed dynamically.
    """
    newData = pyqtSignal(dict)
    connected = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, controller, interval, redis_client, redis_key):
        super().__init__()
        self.controller = controller
        self.interval = interval
        self.redis_client = redis_client
        self.redis_key = redis_key
        self._is_running = True

    def run(self):
        """The main logging loop."""
        if self.controller.connect():
            self.connected.emit()
        else:
            print(f"Worker for {self.controller.__class__.__name__} failed to connect. Stopping thread.")
            self.finished.emit()
            return
        
        while self._is_running:
            reading = self.controller.get_reading() 
            if reading:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                reading['timestamp'] = timestamp
                self.newData.emit(reading)
                
                if self.redis_client:
                    try:
                        # Use HSET for structured data in Redis
                        redis_data = {k: str(v) for k, v in reading.items()}
                        self.redis_client.hset(self.redis_key, mapping=redis_data)
                    except redis.exceptions.RedisError as e:
                        print(f"REDIS ERROR ({self.controller.__class__.__name__}): {e}")
            
            time.sleep(self.interval)
        
        self.controller.disconnect()
        self.finished.emit()

    def stop(self):
        self._is_running = False
        
    def set_interval(self, new_interval: float):
        """Safely updates the polling interval."""
        print(f"Updating {self.controller.__class__.__name__} interval to {new_interval}s")
        self.interval = new_interval

# --- Main Application Window ---

class DashboardWindow(QMainWindow):
    def __init__(self, tpg_controller, sa_controller, redis_client, tpg_interval_initial, sa_interval_initial, sa_defaults_path=r'Communication Code\Wave_Analyzer\Spectrum_Defaults.json'):
        super().__init__()
        self.setWindowTitle("Lab Instrument Dashboard")
        self.setGeometry(100, 100, 1600, 800)

        self.tpg_controller = tpg_controller
        self.sa_controller = sa_controller
        self.redis_client = redis_client
        
        self.tpg_interval = tpg_interval_initial
        self.sa_interval = sa_interval_initial

        self.sa_defaults = {}
        try:
            with open(sa_defaults_path, 'r') as f:
                self.sa_defaults = json.load(f)
            print(f"Successfully loaded SA defaults from {sa_defaults_path}")
        except Exception as e:
            print(f"WARNING: Could not load Spectrum Analyzer defaults. Error: {e}")

        self.pressure_data_x = deque(maxlen=200)
        self.pressure_data_y = deque(maxlen=200)
        
        self.spectrum_sum = None
        self.iteration_count = 0
        self.spectrum_x_axis = None
        
        self.csv_filename = None 

        self._check_redis_connection()
        self._setup_ui()
        self._setup_workers()
        self._setup_csv_saver()

    def _check_redis_connection(self):
        """Checks for a valid Redis connection on startup and shows a warning if it fails."""
        try:
            if self.redis_client and self.redis_client.ping():
                print("Successfully connected to Redis server.")
            else:
                raise redis.exceptions.ConnectionError
        except (redis.exceptions.ConnectionError, TypeError, AttributeError):
            self.redis_client = None 
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setText("Redis Connection Failed")
            msg_box.setInformativeText("Could not connect to the Redis server. Real-time data will not be published.")
            msg_box.setWindowTitle("Redis Warning")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()

    def _setup_ui(self):
        """Initializes all GUI components."""
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        plots_widget = QWidget()
        plots_layout = QVBoxLayout(plots_widget)
        main_layout.addWidget(plots_widget, stretch=3)

        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self.spectrum_plot = pg.PlotWidget(title="Live Spectrum")
        self.spectrum_curve = self.spectrum_plot.plot(pen='b')
        self.spectrum_plot.getAxis('left').setLabel('Amplitude', units='dBm')
        self.spectrum_plot.getAxis('bottom').setLabel('Frequency', units='Hz')
        plots_layout.addWidget(self.spectrum_plot)
        
        self.pressure_plot = pg.PlotWidget(title="Pressure vs. Time")
        self.pressure_plot.setLogMode(y=True)
        self.pressure_plot.getAxis('left').setLabel('Pressure', units='hPa')
        self.pressure_plot.getAxis('bottom').setLabel('Time', units='s')
        self.pressure_curve = self.pressure_plot.plot(pen='r', symbol='o', symbolBrush='r')
        plots_layout.addWidget(self.pressure_plot)

        self.avg_spectrum_plot = pg.PlotWidget(title="Rolling Average Spectrum")
        self.avg_spectrum_curve = self.avg_spectrum_plot.plot(pen='g')
        self.avg_spectrum_plot.getAxis('left').setLabel('Avg. Amplitude', units='dBm')
        self.avg_spectrum_plot.getAxis('bottom').setLabel('Frequency', units='Hz')
        plots_layout.addWidget(self.avg_spectrum_plot)

        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        main_layout.addWidget(controls_widget, stretch=1)
        
        # --- NEW: Live Readings Display ---
        readings_group_box = QGroupBox("Live Readings")
        readings_layout = QVBoxLayout()
        readings_group_box.setLayout(readings_layout)
        self.pressure_label = QLabel("Pressure: N/A")
        self.peak_power_label = QLabel("Power @ Center: N/A")
        readings_layout.addWidget(self.pressure_label)
        readings_layout.addWidget(self.peak_power_label)
        controls_layout.addWidget(readings_group_box)
        
        sa_group_box = QGroupBox("Spectrum Analyzer Controls")
        sa_layout = QGridLayout()
        sa_group_box.setLayout(sa_layout)
        
        default_freq = self.sa_defaults.get("center_frequency", "2.5e9")
        self.sa_freq_input = QLineEdit(str(default_freq))
        sa_freq_btn = QPushButton("Set Center Freq (Hz)")
        sa_freq_btn.clicked.connect(self.set_sa_center_freq)
        sa_layout.addWidget(self.sa_freq_input, 0, 0)
        sa_layout.addWidget(sa_freq_btn, 0, 1)

        default_span = self.sa_defaults.get("span", "100e6")
        self.sa_span_input = QLineEdit(str(default_span))
        sa_span_btn = QPushButton("Set Span (Hz)")
        sa_span_btn.clicked.connect(self.set_sa_span)
        sa_layout.addWidget(self.sa_span_input, 1, 0)
        sa_layout.addWidget(sa_span_btn, 1, 1)
        
        self.sa_interval_input = QLineEdit(str(self.sa_interval))
        sa_interval_btn = QPushButton("Set Read Interval (s)")
        sa_interval_btn.clicked.connect(self.set_sa_interval)
        sa_layout.addWidget(self.sa_interval_input, 2, 0)
        sa_layout.addWidget(sa_interval_btn, 2, 1)
        controls_layout.addWidget(sa_group_box)
        
        tpg_group_box = QGroupBox("Vacuum Gauge Controls")
        tpg_layout = QGridLayout()
        tpg_group_box.setLayout(tpg_layout)
        
        self.tpg_unit_input = QLineEdit("Torr")
        tpg_unit_btn = QPushButton("Set Unit")
        tpg_unit_btn.clicked.connect(self.set_tpg_unit)
        tpg_layout.addWidget(self.tpg_unit_input, 0, 0)
        tpg_layout.addWidget(tpg_unit_btn, 0, 1)

        self.tpg_interval_input = QLineEdit(str(self.tpg_interval))
        tpg_interval_btn = QPushButton("Set Read Interval (s)")
        tpg_interval_btn.clicked.connect(self.set_tpg_interval)
        tpg_layout.addWidget(self.tpg_interval_input, 1, 0)
        tpg_layout.addWidget(tpg_interval_btn, 1, 1)
        controls_layout.addWidget(tpg_group_box)

        controls_layout.addStretch()

    def _setup_workers(self):
        """Creates and starts the data acquisition threads."""
        self.sa_thread = QThread()
        self.sa_worker = InstrumentWorker(self.sa_controller, self.sa_interval, self.redis_client, 'spectrum_analyzer:latest_reading')
        self.sa_worker.moveToThread(self.sa_thread)
        self.sa_thread.started.connect(self.sa_worker.run)
        self.sa_worker.newData.connect(self.update_spectrum_plots)
        self.sa_worker.connected.connect(self.apply_sa_defaults)
        self.sa_worker.finished.connect(self.sa_thread.quit)
        self.sa_thread.start()

        self.tpg_thread = QThread()
        self.tpg_worker = InstrumentWorker(self.tpg_controller, self.tpg_interval, self.redis_client, 'tpg201:latest_reading')
        self.tpg_worker.moveToThread(self.tpg_thread)
        self.tpg_thread.started.connect(self.tpg_worker.run)
        self.tpg_worker.newData.connect(self.update_pressure_plot)
        self.tpg_worker.finished.connect(self.tpg_thread.quit)
        self.tpg_thread.start()
        
    def _setup_csv_saver(self):
        self.csv_timer = QTimer()
        self.csv_timer.timeout.connect(self.save_data_to_csv)
        self.save_path_base = self.sa_defaults.get("save_path", "lab_data/data.csv")
        self.csv_timer.start(5000)

    def update_spectrum_plots(self, data):
        freqs = np.array(data.get('frequencies_hz', []))
        amps = np.array(data.get('amplitudes_dbm', []))
        if freqs.any() and amps.any():
            self.spectrum_x_axis = freqs
            self.spectrum_curve.setData(freqs, amps)

            # Update live power at center frequency
            try:
                center_freq = float(self.sa_freq_input.text())
                center_idx = np.abs(freqs - center_freq).argmin()
                power_at_center = amps[center_idx]
                self.peak_power_label.setText(f"Power @ Center: {power_at_center:.2f} dBm")
            except (ValueError, IndexError):
                self.peak_power_label.setText("Power @ Center: N/A")

            # Update rolling average
            if self.spectrum_sum is None or self.spectrum_sum.shape != amps.shape:
                self.spectrum_sum = amps.copy()
                self.iteration_count = 1
            else:
                self.spectrum_sum += amps
                self.iteration_count += 1
            self.avg_spectrum_curve.setData(freqs, self.spectrum_sum / self.iteration_count)
            
    def update_pressure_plot(self, data):
        pressure = data.get('pressure')
        if pressure is not None and pressure > 0:
            # Update live pressure label
            self.pressure_label.setText(f"Pressure: {pressure:.2e} hPa")

            # Update plot
            self.pressure_data_y.append(pressure)
            self.pressure_data_x.append(time.time())
            display_x = np.array(self.pressure_data_x) - self.pressure_data_x[0]
            self.pressure_curve.setData(display_x, list(self.pressure_data_y))

    def set_sa_center_freq(self):
        self.sa_controller.set_parameter('set_center_frequency', self.sa_freq_input.text())

    def set_sa_span(self):
        self.sa_controller.set_parameter('set_span', self.sa_span_input.text())
        
    def set_tpg_unit(self):
        self.tpg_controller.set_unit(self.tpg_unit_input.text())
        
    def apply_sa_defaults(self):
        print("--- Applying Spectrum Analyzer defaults from file... ---")
        if not self.sa_defaults:
            print("No defaults loaded, skipping.")
            return

        defaults_map = {
            "center_frequency": "set_center_frequency",
            "reference_level": "set_reference_power",
            "span": "set_span",
            "averaging_state": "set_averaging_state",
            "averaging_count": "set_averaging_count"
        }

        for key, command_name in defaults_map.items():
            if key in self.sa_defaults:
                value = self.sa_defaults[key]
                self.sa_controller.set_parameter(command_name, value)
                time.sleep(0.1)

        if "sweep_time" in self.sa_defaults:
            sweep_val = self.sa_defaults["sweep_time"]
            if str(sweep_val).lower() == 'auto':
                self.sa_controller.set_parameter('set_auto_sweep_time', "ON")
            else:
                self.sa_controller.set_parameter('set_sweep_time', sweep_val)
        
        print("--- SA defaults applied successfully. ---")

    def set_sa_interval(self):
        try:
            new_interval = float(self.sa_interval_input.text())
            if new_interval > 0:
                self.sa_worker.set_interval(new_interval)
        except ValueError:
            print("Error: Invalid interval value.")

    def set_tpg_interval(self):
        try:
            new_interval = float(self.tpg_interval_input.text())
            if new_interval > 0:
                self.tpg_worker.set_interval(new_interval)
        except ValueError:
            print("Error: Invalid interval value.")

    def save_data_to_csv(self):
        """--- NEW FORMAT: Appends a single wide row to the CSV. ---"""
        if self.iteration_count > 0 and self.spectrum_x_axis is not None:
            if self.csv_filename is None:
                base, ext = os.path.splitext(self.save_path_base)
                os.makedirs(os.path.dirname(base), exist_ok=True)
                self.csv_filename = f"{base}_{time.strftime('%Y%m%d-%H%M%S')}{ext}"
                print(f"Data will be saved to rolling CSV: {self.csv_filename}")

            file_exists = os.path.isfile(self.csv_filename)
            
            try:
                with open(self.csv_filename, 'a', newline='') as f:
                    writer = csv.writer(f)
                    
                    if not file_exists:
                        num_points = len(self.spectrum_x_axis)
                        power_headers = [f'Power_{i+1}' for i in range(num_points)]
                        freq_headers = [f'Frequency_{i+1}' for i in range(num_points)]
                        writer.writerow(['Timestamp', 'Pressure_hPa'] + power_headers + freq_headers)
                    
                    pressure = self.pressure_data_y[-1] if self.pressure_data_y else 'N/A'
                    avg_spec = (self.spectrum_sum / self.iteration_count).tolist()
                    freqs = self.spectrum_x_axis.tolist()
                    
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    pressure_str = f"{pressure:.4e}" if isinstance(pressure, float) else 'N/A'
                    
                    row_data = [timestamp, pressure_str] + avg_spec + freqs
                    writer.writerow(row_data)

                self.spectrum_sum = None
                self.iteration_count = 0
                print(f"Appended data to {self.csv_filename}. Rolling average reset.")

            except Exception as e:
                print(f"Error saving CSV: {e}")

    def closeEvent(self, event):
        print("Closing dashboard...")
        self.sa_worker.stop()
        self.tpg_worker.stop()
        self.sa_thread.quit()
        self.tpg_thread.quit()
        self.sa_thread.wait()
        self.tpg_thread.wait()
        event.accept()

if __name__ == '__main__':
    SA_DEFAULTS_PATH = r'Communication Code\Wave_Analyzer\Spectrum_Defaults.json'
    app = QApplication(sys.argv)
    
    redis_client = None
    try:
        redis_client = redis.Redis(decode_responses=True)
        redis_client.ping()
    except redis.exceptions.ConnectionError:
        pass

    tpg_controller = TPGController(r'Communication Code\Vacuum_Gauge\TPG_201_Config.json')
    sa_controller = SpectrumAnalyzerController(r'Communication Code\Wave_Analyzer\Spectrum_Analyzer_Config.json')
    window = DashboardWindow(tpg_controller, sa_controller, redis_client, 1.0, 1.0, SA_DEFAULTS_PATH)
    window.show()
    sys.exit(app.exec())
