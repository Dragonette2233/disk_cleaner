import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QListWidget, QPushButton, QListWidgetItem
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from clayer import get_disk_info

qapp = QApplication

class DiskInfoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Disk Information Viewer")
        self.setGeometry(100, 100, 400, 250)

        self.layout = QVBoxLayout()

        self.label = QLabel("Connected Disks:")
        self.layout.addWidget(self.label)

        self.disk_list = QListWidget()
        self.layout.addWidget(self.disk_list)

        self.refresh_button = QPushButton("Refresh Disk Info")
        self.refresh_button.clicked.connect(self.refresh_disk_info)
        self.layout.addWidget(self.refresh_button)

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

        self.refresh_disk_info()

    def refresh_disk_info(self):
        self.disk_list.clear()
        for i in range(10):  # Проверяем до 10 дисков
            info = get_disk_info(i)
            if info:
                model, serial = info
                self.add_disk_item(i, model, serial)

    def add_disk_item(self, index, model, serial):
        item = QListWidgetItem(f"Disk {index}:")
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        self.disk_list.addItem(item)

        model_item = QListWidgetItem(f" Model: {model}")
        model_item.setForeground(QColor('blue'))
        model_item.setFlags(Qt.ItemIsEnabled)  # Only enabled, not checkable
        self.disk_list.addItem(model_item)

        serial_item = QListWidgetItem(f" Serial: {serial}")
        serial_item.setForeground(QColor('green'))
        serial_item.setFlags(Qt.ItemIsEnabled)  # Only enabled, not checkable
        self.disk_list.addItem(serial_item)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DiskInfoApp()
    window.show()
    sys.exit(app.exec_())
