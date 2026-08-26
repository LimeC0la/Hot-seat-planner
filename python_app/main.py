import sys
import os

# Ensure dateutil is available
try:
    import dateutil.parser
except ImportError:
    print("Installing python-dateutil...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dateutil"])
    import dateutil.parser

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
