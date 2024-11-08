from qtlayer import DiskApp
from PyQt5.QtWidgets import QApplication
import sys
import ctypes

def run_as_admin():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    else:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit()

run_as_admin()

if __name__ == "__main__":
    run_as_admin()
    app = QApplication(sys.argv)
    # app.setStyle("Fusion")
    window = DiskApp()
    window.show()
    sys.exit(app.exec_())