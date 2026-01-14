import sys
import numpy as np
import pyqtgraph as pg
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import pyqtSignal

class VisualInterface(QtWidgets.QMainWindow):
    data_received = pyqtSignal(dict)

    def __init__(self, spectral_axis=None):
        super().__init__()
        self.setWindowTitle("Quantum-Subradience Real-Time Monitor")
        self.resize(1280, 900)

        # Set Global Light Theme Stylesheet
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
        self.time_history = []
        self.max_history = 200

        # Central Layout
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.central_widget)

        # 2x2 Grid for Plots
        self.plot_layout = QtWidgets.QGridLayout()
        self.main_layout.addLayout(self.plot_layout, stretch=4)

        self._init_plots()
        self._init_diagnostic_cards()

        self.data_received.connect(self.process_new_data)

    def process_new_data(self, data_dict):
            """This runs safely on the Main Thread."""
            if 'amplitudes' in data_dict:
                self.update_spectrum(data_dict['amplitudes'])
            if 'pressure' in data_dict:
                self.update_pressure(data_dict['pressure'], data_dict['elapsed_time'])
            
            self.update_diagnostics(
                data_dict['pressure'], 
                data_dict['file_size_mb'], 
                data_dict['gb_hr'], 
                data_dict['cadence'], 
                data_dict['elapsed_time']
            )

    def _init_plots(self):
        """Initialize graphs with a light, modern style."""
        # Global pyqtgraph settings for light mode
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOptions(antialias=True)

        # Define custom pens
        pen_blue = pg.mkPen(color='#0055ff', width=2)
        pen_green = pg.mkPen(color='#00aa00', width=2)
        pen_red = pg.mkPen(color='#cc0000', width=2)
        pen_purple = pg.mkPen(color='#8800ff', width=2)

        # Helper to style plots
        def style_plot(pw, title):
            pw.setTitle(title, color="k", size="12pt")
            pw.showGrid(x=True, y=True, alpha=0.3)
            pw.getAxis('left').setPen('k')
            pw.getAxis('bottom').setPen('k')

        # 1. Power Spectrum
        self.plot_power = pg.PlotWidget()
        style_plot(self.plot_power, "Power Spectrum (dBm, Hz)")
        self.curve_power = self.plot_power.plot(pen=pen_blue)
        self.plot_layout.addWidget(self.plot_power, 0, 0)

        # 2. Power Spectral Density
        self.plot_psd = pg.PlotWidget()
        style_plot(self.plot_psd, "PSD (dBm/Hz, Hz)")
        self.curve_psd = self.plot_psd.plot(pen=pen_purple)
        self.plot_layout.addWidget(self.plot_psd, 0, 1)

        # 3. Pressure vs Time
        self.plot_pressure = pg.PlotWidget()
        style_plot(self.plot_pressure, "Chamber Pressure (mbar, s)")
        self.curve_pressure = self.plot_pressure.plot(pen=pen_green)
        self.plot_layout.addWidget(self.plot_pressure, 1, 0)

        # 4. Pressure Derivative
        self.plot_deriv = pg.PlotWidget()
        style_plot(self.plot_deriv, "Pressure Derivative (mbar/s, s)")
        self.curve_deriv = self.plot_deriv.plot(pen=pen_red)
        self.plot_layout.addWidget(self.plot_deriv, 1, 1)

    def _init_diagnostic_cards(self):
        """Replaces the table with a horizontal row of high-visibility diagnostic cards."""
        self.card_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(self.card_layout, stretch=1)

        self.cards = {}
        metrics = [
            ("Current Pressure", "0.00", "mbar"),
            ("Log File Size", "0.00", "MB"),
            ("Data Rate", "0.00", "GB/hr"),
            ("System Cadence", "0.00", "Hz"),
            ("Elapsed Time", "00:00:00", "")
        ]

        for title, val, unit in metrics:
            frame = QtWidgets.QFrame()
            frame.setObjectName("Card")
            vbox = QtWidgets.QVBoxLayout(frame)
            
            title_label = QtWidgets.QLabel(title.upper())
            title_label.setStyleSheet("font-size: 10px; color: #777;")
            
            val_label = QtWidgets.QLabel(val)
            val_label.setStyleSheet("font-size: 22px; color: #000;")
            
            unit_label = QtWidgets.QLabel(unit)
            unit_label.setStyleSheet("font-size: 10px; color: #777;")

            vbox.addWidget(title_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(val_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(unit_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            
            self.card_layout.addWidget(frame)
            self.cards[title] = val_label

    # --- Data Update Methods ---

    def update_diagnostics(self, pressure, file_size_mb, gb_hr, cadence, elapsed_s):
        """Update the diagnostic cards at the bottom."""
        self.cards["Current Pressure"].setText(f"{pressure:.3e}")
        self.cards["Log File Size"].setText(f"{file_size_mb:.2f}")
        self.cards["Data Rate"].setText(f"{gb_hr:.3f}")
        self.cards["System Cadence"].setText(f"{cadence:.2f}")
        
        # Format elapsed time
        hrs, rem = divmod(int(elapsed_s), 3600)
        mins, secs = divmod(rem, 60)
        self.cards["Elapsed Time"].setText(f"{hrs:02d}:{mins:02d}:{secs:02d}")

    def update_spectrum(self, amplitudes):
        """Updates Power and PSD plots."""
        amps = np.array(amplitudes)
        self.curve_power.setData(self.spectral_axis, amps)
        
        # Calculation for visualization (Placeholder RBW=1kHz)
        psd = amps - 10 * np.log10(1000)
        self.curve_psd.setData(self.spectral_axis, psd)

    def update_pressure(self, pressure, elapsed_time):
        """Updates Pressure and Derivative plots."""
        self.pressure_history.append(pressure)
        self.time_history.append(elapsed_time)

        if len(self.time_history) > self.max_history:
            self.time_history.pop(0)
            self.pressure_history.pop(0)

        t = np.array(self.time_history)
        p = np.array(self.pressure_history)
        
        self.curve_pressure.setData(t, p)

        if len(t) > 2:
            deriv = np.gradient(p, t)
            self.curve_deriv.setData(t, deriv)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = VisualInterface()
    window.show()
    sys.exit(app.exec())