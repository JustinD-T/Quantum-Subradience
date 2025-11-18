import sys
import argparse
import redis
from multiprocessing import Process

from PyQt6.QtWidgets import QApplication

# Import the new Dashboard and the existing controllers
from Dashboard import DashboardWindow
from Vacuum_Gauge.VacuumGaugeController import TPGController
from Wave_Analyzer.SpectrumAnalyzerController import SpectrumAnalyzerController

def run_dashboard(tpg_config, sa_config, redis_host, redis_port, tpg_interval, sa_interval):
    """Target function to run the PyQt Dashboard application."""
    print("--- [Dashboard Process] Starting ---")
    try:
        app = QApplication(sys.argv)
        
        # Instantiate controllers and redis client *within* the process
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        tpg_controller = TPGController(tpg_config)
        sa_controller = SpectrumAnalyzerController(sa_config)
        
        # Pass the intervals to the Dashboard window
        window = DashboardWindow(tpg_controller, sa_controller, redis_client, tpg_interval, sa_interval)
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"--- [Dashboard Process] An error occurred: {e} ---")
    print(f"--- [Dashboard Process] Terminated ---")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Launch the Lab Instrument Dashboard.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # Redis arguments
    parser.add_argument('--host', default='localhost', help='Redis server host.')
    parser.add_argument('--port', type=int, default=6379, help='Redis server port.')
    
    # Config arguments
    parser.add_argument('--tpg-config', default=r'Communication Code\Vacuum_Gauge\TPG_201_Config.json', help='Path to TPG config file.')
    parser.add_argument('--sa-config', default=r'Communication Code\Wave_Analyzer\Spectrum_Analyzer_Config.json', help='Path to Spectrum Analyzer config file.')

    # Interval arguments
    parser.add_argument('--tpg-interval', type=float, default=1.0, help='Initial logging interval for the TPG vacuum gauge in seconds.')
    parser.add_argument('--sa-interval', type=float, default=1.0, help='Initial logging interval for the spectrum analyzer in seconds.')

    args = parser.parse_args()

    print("--- Master Control Script ---")
    print(f"Launching Dashboard. It will manage instrument connections.")
    
    # The dashboard now manages the instrument threads, so we only need to start it.
    # We run it in a separate process to keep the main terminal free.
    dashboard_process = Process(
        target=run_dashboard, 
        args=(args.tpg_config, args.sa_config, args.host, args.port, args.tpg_interval, args.sa_interval)
    )
    dashboard_process.start()

    try:
        # Wait for the dashboard process to finish (e.g., when the user closes the window)
        dashboard_process.join()
    except KeyboardInterrupt:
        print("\n--- [Master Control] Shutdown signal received. Terminating dashboard... ---")
        if dashboard_process.is_alive():
            dashboard_process.terminate()
            dashboard_process.join() # Wait for termination
        print("--- [Master Control] Dashboard terminated. ---")
    
    print("--- Master Control Script Finished ---")

