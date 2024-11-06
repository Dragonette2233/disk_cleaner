from qtlayer import DiskApp
from PyQt5.QtWidgets import QApplication
import sys


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # app.setStyle("Fusion")
    window = DiskApp()
    window.show()
    sys.exit(app.exec_())