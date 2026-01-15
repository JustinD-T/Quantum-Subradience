import sys
import numpy as np
import pyqtgraph as pg
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import pyqtSignal
from scipy.signal import savgol_filter
from collections import deque

class VisualInterface(QtWidgets.QMainWindow):
    data_received = pyqtSignal(dict)

    def __init__(self, spectral_axis=None):
        super().__init__()
        self.setWindowTitle("Quantum-Subradience Real-Time Monitor")
        self.resize(1400, 950)

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #f5f5f5; }
            QLabel { color: #333; font-weight: bold; font-family: 'Segoe UI', Arial; }
            QFrame#Card { 
                background-color: white; 
                border: 1px solid #ddd; 
                border-radius: 8px; 
            }
        """)

        # Data Buffers
        self.spectral_axis = spectral_axis if spectral_axis is not None else np.linspace(0, 1, 401)
        self.pressure_history = []
        self.spectral_sum = np.zeros_like(np.array(spectral_axis))
        self.spectral_counts = 0
        self.time_history = []
        self.deriv_latest = 0.0
        self.max_history = 200

        # Averaging Buffers for Informational Metrics (Rolling average of last 10 updates)
        self.avg_window = 10
        self.metric_buffers = {
            "pressure": deque(maxlen=self.avg_window),
            "cadence": deque(maxlen=self.avg_window),
            "cycle_time_ms": deque(maxlen=self.avg_window),
            "instrumental_time_ms": deque(maxlen=self.avg_window),
            "integration_efficiency": deque(maxlen=self.avg_window),
            "time_to_1mbar": deque(maxlen=self.avg_window)
        }

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.central_widget)

        self.plot_layout = QtWidgets.QGridLayout()
        self.main_layout.addLayout(self.plot_layout, stretch=10)

        self._init_plots()
        self._init_diagnostic_cards()

        self.data_received.connect(self.process_new_data)

    def _init_plots(self):
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOptions(antialias=True)

        pen_blue = pg.mkPen(color='#0055ff', width=2)
        pen_green = pg.mkPen(color='#00aa00', width=2)
        pen_red = pg.mkPen(color='#cc0000', width=2)
        pen_purple = pg.mkPen(color='#8800ff', width=2)

        def style_plot(pw, title):
            pw.setTitle(title, color="k", size="12pt")
            pw.showGrid(x=True, y=True, alpha=0.3)

        self.plot_power = pg.PlotWidget(); style_plot(self.plot_power, "Power Spectrum (dBm, Hz)")
        self.curve_power = self.plot_power.plot(pen=pen_blue)
        self.plot_layout.addWidget(self.plot_power, 0, 0)

        self.plot_psd = pg.PlotWidget(); style_plot(self.plot_psd, "PSD (dBm/Hz, Hz)")
        self.curve_psd = self.plot_psd.plot(pen=pen_purple)
        self.plot_layout.addWidget(self.plot_psd, 0, 1)

        self.plot_pressure = pg.PlotWidget(); style_plot(self.plot_pressure, "Chamber Pressure (mbar, s)")
        self.plot_pressure.setLogMode(y=True)
        self.curve_pressure = self.plot_pressure.plot(pen=pen_green)
        self.plot_layout.addWidget(self.plot_pressure, 1, 0)

        self.plot_deriv = pg.PlotWidget(); style_plot(self.plot_deriv, "Pressure Derivative (mbar/s, s)")
        self.curve_deriv = self.plot_deriv.plot(pen=pen_red)
        self.plot_layout.addWidget(self.plot_deriv, 1, 1)

    def _init_diagnostic_cards(self):
        self.cards = {}
        
        # Row 1: Science & State
        metrics_row1 = [
            ("pressure", "Pressure", "0.00", "mbar"),
            ("time_to_1mbar", "Time to 1 mbar", "N/A", "min"),
            ("file_size_mb", "File Size", "0.00", "MB"),
            ("est_int_time", "Est. Integration Time", "0.0", "s"),
            ("elapsed_time", "Elapsed Time", "00:00:00", "")
        ]
        # Row 2: Hardware & Performance
        metrics_row2 = [
            ("cycle", "Total Cycles", "0", "ct"),
            ("cadence", "Cadence", "0.00", "Hz"),
            ("cycle_time_ms", "Cycle Time", "0.0", "ms"),
            ("instrumental_time_ms", "Instrument Latency", "0.0", "ms"),
            ("integration_efficiency", "Efficiency", "0.0", "%")
        ]

        for row_metrics in [metrics_row1, metrics_row2]:
            hbox = QtWidgets.QHBoxLayout()
            for key, title, val, unit in row_metrics:
                frame = QtWidgets.QFrame(); frame.setObjectName("Card")
                vbox = QtWidgets.QVBoxLayout(frame)
                
                l_title = QtWidgets.QLabel(title.upper()); l_title.setStyleSheet("font-size: 8pt; color: #777;")
                l_val = QtWidgets.QLabel(val); l_val.setStyleSheet("font-size: 16pt; color: #000;")
                l_unit = QtWidgets.QLabel(unit); l_unit.setStyleSheet("font-size: 8pt; color: #777;")

                vbox.addWidget(l_title, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
                vbox.addWidget(l_val, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
                vbox.addWidget(l_unit, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
                
                hbox.addWidget(frame)
                self.cards[key] = l_val
            self.main_layout.addLayout(hbox, stretch=1)

    def process_new_data(self, data_dict):
        if 'amplitudes' in data_dict: self.update_spectrum(data_dict['amplitudes'])
        if 'pressure' in data_dict: self.update_pressure(data_dict['pressure'], data_dict['elapsed_time'])
        self.update_diagnostics(data_dict)

    def get_avg(self, key, current_val):
        """Helper to store and average values."""
        if key in self.metric_buffers:
            self.metric_buffers[key].append(current_val)
            return sum(self.metric_buffers[key]) / len(self.metric_buffers[key])
        return current_val

    def update_diagnostics(self, data):
        # 1. Science Calculations
        p_raw = data.get('pressure', 0)
        p_avg = self.get_avg("pressure", p_raw)
        self.cards["pressure"].setText(f"{p_avg:.3e}")
        
        # Est. Integration Time: Elapsed Time * Efficiency (0-1)
        elapsed = data.get('elapsed_time', 0)
        efficiency = data.get('integration_efficiency', 0) / 100.0 
        self.cards["est_int_time"].setText(f"{elapsed * efficiency:.1f}")

        # Time to 1 mbar
        if p_raw < 1.0 and self.deriv_latest > 0:
            raw_min = (1.0 - p_raw) / (self.deriv_latest * 60.0)
            avg_min = self.get_avg("time_to_1mbar", raw_min)
            self.cards["time_to_1mbar"].setText(f"{avg_min:.1f}")
        else:
            self.cards["time_to_1mbar"].setText("N/A")

        # 2. Performance Metrics (Averaged)
        self.cards["cadence"].setText(f"{self.get_avg('cadence', data.get('cadence', 0)):.2f}")
        self.cards["cycle_time_ms"].setText(f"{self.get_avg('cycle_time_ms', data.get('cycle_time_ms', 0)):.1f}")
        self.cards["instrumental_time_ms"].setText(f"{self.get_avg('instrumental_time_ms', data.get('instrumental_time_ms', 0)):.1f}")
        self.cards["integration_efficiency"].setText(f"{self.get_avg('integration_efficiency', data.get('integration_efficiency', 0)):.1f}")

        # 3. Non-averaged / Static counters
        self.cards["file_size_mb"].setText(f"{data.get('file_size_mb', 0):.2f}")
        self.cards["cycle"].setText(f"{int(data.get('cycle', 0))}")
        
        hrs, rem = divmod(int(elapsed), 3600)
        mins, secs = divmod(rem, 60)
        self.cards["elapsed_time"].setText(f"{hrs:02d}:{mins:02d}:{secs:02d}")

    def update_spectrum(self, amplitudes):
        
        self.spectral_counts += 1
        amps = np.array(amplitudes)
        self.spectral_sum += amps
        self.curve_power.setData(self.spectral_axis, amps)

        self.curve_psd.setData(self.spectral_axis, self.spectral_sum / self.spectral_counts)

    def update_pressure(self, pressure, elapsed_time):
        precision_p = round(pressure, 13)
        self.pressure_history.append(precision_p)
        self.time_history.append(elapsed_time)

        if len(self.time_history) > self.max_history:
            self.time_history.pop(0); self.pressure_history.pop(0)

        t, p = np.array(self.time_history), np.array(self.pressure_history)
        self.curve_pressure.setData(t, p)

        if len(t) > 5:
            try:
                window = 7 if len(p) >= 7 else 5
                p_smoothed = savgol_filter(p, window, polyorder=2)
                raw_deriv = np.gradient(p_smoothed, t)
                
                # Tightened Dead-band: Filter floating point noise at 1e-12 level
                raw_deriv[np.abs(raw_deriv) < 1e-12] = 0
                
                self.deriv_latest = raw_deriv[-1]
                self.curve_deriv.setData(t, raw_deriv)
            except:
                self.curve_deriv.setData(t, np.gradient(p, t))

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = VisualInterface()
    window.show()
    sys.exit(app.exec())