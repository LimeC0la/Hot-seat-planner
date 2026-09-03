import sys
import os

# Ensure required packages are available
for module_name, pip_name in [("dateutil", "python-dateutil"), ("PySide6", "PySide6")]:
    try:
        __import__(module_name)
    except ImportError:
        print(f"Required package '{module_name}' not found. Installing {pip_name}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
        except Exception as e:
            print(f"Error installing {pip_name}: {e}")

from PySide6.QtWidgets import QApplication
from core.state_manager import StateManager
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Initialize state manager
    data_path = os.path.join(os.path.dirname(__file__), "state.json")
    state_manager = StateManager(data_path)
    
    # Create and show window
    window = MainWindow(state_manager)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
