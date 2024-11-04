from qtlayer import DiskInfoApp, qapp
import sys


if __name__ == "__main__":
    app = qapp(sys.argv)
    window = DiskInfoApp()
    window.show()
    sys.exit(app.exec_())