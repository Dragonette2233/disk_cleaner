from PyQt5.QtWidgets import (
    QApplication, QWidget, QListWidget, QVBoxLayout, QListWidgetItem, QLabel,
    QHBoxLayout, QPushButton, QCheckBox, QMenu, QFileDialog, QMessageBox
)

from victoria.percentage import get_percentage
from victoria.ui import cycle_victoria_script
from functools import partial
from victoria_open_ctypes import VICTORIA_PATH, CONFIG_PATH
import victoria_open_ctypes
import threading, time, queue, sys, os
from PyQt5.QtCore import QTimer, Qt, QPoint
from PyQt5.QtGui import QIcon
from scsi_start_stop_unit import scsi_sleep_command, is_disk_sleeping
import smart_check
import diskutils as du

class ThreadData:
    def __init__(self):
        self.connected_drives = 0
        self.disk_info = []
        self.cache_part_sequence = ''
        self.cache_connected_drives = 0
        self.is_refresh_require = False
        self.disks_queue = queue.Queue()
        self.smart_queue = queue.Queue()

    def update(self):
        n_connected_drives = 0
        self.disk_info.clear()
        for i in range(10):
            # print(i)
            info = du.get_disk_info(i)
            percentage = get_percentage(i)
            # print(percentage)
            # print(percentage)
            if info == 'OUT':
                self.disk_info.append((i, "! Disconnected !", "", "UL", False, percentage))
            elif isinstance(info, tuple):
                di = list(info)
                di.append(is_disk_sleeping(i))
                di.append(percentage)
                self.disk_info.append(di)
                n_connected_drives += 1
            else:
                self.disk_info.append((i, "Not connected", "", "UL", False, percentage))
            
            # print(self.disk_info[i])

        n_part_sequence = ''.join(str(i[3]) + str(i[-1]) for i in self.disk_info)
        self.is_refresh_require = (
            self.cache_part_sequence != n_part_sequence or
            self.cache_connected_drives != n_connected_drives
        )

        

        if self.is_refresh_require:
            # print(self.disk_info)
            self.disks_queue.put(self.disk_info.copy())
            self.cache_connected_drives = n_connected_drives
            self.cache_part_sequence = n_part_sequence
            return True

class mModel(QLabel):
    def __init__(self, parent, idx):
        super().__init__()
        self.parent_: DiskApp = parent
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        # передаём pos в show_context_menu
        self.customContextMenuRequested.connect(
            lambda pos: self.parent_.show_context_menu(self, idx, pos)
        )



class PersistentToolTip(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip)
        self.setStyleSheet("""
            QLabel {
                background-color: #333;
                color: white;
                border: 1px solid white;
                padding: 5px;
                text-align: justify;
            }
        """)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.hide()
    def show_at(self, text, pos):
        self.setText(text)
        self.adjustSize()
        self.move(pos)
        self.show()

class mPercentage(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("color: #3BF4FA;")
        self.setStyleSheet(f"color: pink;")

class mSmart(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("color: #3BF4FA;")
        self.smart_complex = ""
        self.tooltip = PersistentToolTip(self)
        self.setMouseTracking(True)
    def set_color(self, color='#3BF4FA'):
        self.setStyleSheet(f"color: {color};")
    def enterEvent(self, event):
        if self.smart_complex:
            self.tooltip.show_at(self.smart_complex, event.globalPos() + QPoint(10, 10))
        super().enterEvent(event)
    def leaveEvent(self, event):
        self.tooltip.hide()
        super().leaveEvent(event)
    def d_update(self, text):
        self.smart_complex = text
    def d_reset(self, msg='smart data'):
        self.smart_complex = ""
        self.setStyleSheet("color: #3BF4FA;")
        self.setText(f"[{msg}]")

class mSerial(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("color: #65FA48;")

class mCheckBox(QCheckBox):
    def __init__(self, idx):
        super().__init__()
        self.setFixedSize(20, 20)
        self.setChecked(idx != 0)
        self.setStyleSheet("text-align: end;")

class mMark(QLabel):
    def __init__(self, color):
        super().__init__()
        self.setFixedSize(15, 15)
        self.setStyleSheet(f"background-color: {color}; border-radius: 7.5px;")

class DiskApp(QWidget):
    def __init__(self):
        super().__init__()
        VERSION = open('appversion').read()
        self.setWindowTitle("Storage-Handler v" + VERSION)
        self.setMinimumSize(770, 390)
        self.setWindowIcon(QIcon('hddc.ico'))

        self.disk_list = QListWidget()
        self.disk_labels = {
            'circle': [mMark('red') for _ in range(10)],
            'model': [mModel(self, idx) for idx in range(10)],
            'serial': [mSerial() for _ in range(10)],
            'smart_data': [mSmart() for _ in range(10)],
            'smart_cache': [mSmart() for _ in range(10)],
            'percentage': [mPercentage() for _ in range(10)],
            'checkbox': [mCheckBox(idx) for idx in range(10)]
        }

        self.main_layout = QVBoxLayout()
        self._configure_markers_info()
        self.main_layout.addWidget(self.disk_list)

        # DEBUG
        # self.DEBUG_BTN = QPushButton("DEBUG")
        # self.DEBUG_BTN.clicked.connect()

        self.cleard_button = QPushButton("DP Clear DEFAULT")
        self.clearr_button = QPushButton("DP Clear RESCAN")
        self.eject_button = QPushButton("Sleep (SCSI)")
        # self.victoria_button = QPushButton("Victoria (8 wins)")
        self.victoria_open_button = QPushButton("Victoria (open)")
        self.victoria_write_button = QPushButton("Victoria (WRITE)")
        self.victoria_read_button = QPushButton("Victoria (READ)")
        self.pushsmart_button = QPushButton("Get SMART (smartctl)")
        self.clearsmart_button = QPushButton("Clear SMART cache")

        self.cleard_button.clicked.connect(self.clear_default)
        self.clearr_button.clicked.connect(self.clear_rescan)
        self.eject_button.clicked.connect(self.eject_device)
        # self.victoria_button.clicked.connect(partial(self.victoria_open, 8))
        self.victoria_open_button.clicked.connect(partial(self.victoria_open, 1))
        self.victoria_write_button.clicked.connect(partial(self.start_victoria_script, 'W'))
        self.victoria_read_button.clicked.connect(partial(self.start_victoria_script, 'R'))
        self.pushsmart_button.clicked.connect(self.push_smart)
        self.clearsmart_button.clicked.connect(self.clear_smart_cache)
        # self.victoria_script_button.clicked.connect(self.start_victoria_script)

        clear_layout = QHBoxLayout()
        clear_layout.addWidget(self.cleard_button)
        clear_layout.addWidget(self.clearr_button)
        victoria_layout = QHBoxLayout()
        victoria_layout.addWidget(self.victoria_open_button)
        victoria_layout.addWidget(self.victoria_write_button)
        victoria_layout.addWidget(self.victoria_read_button)
        smart_layout = QHBoxLayout()
        smart_layout.addWidget(self.pushsmart_button)
        smart_layout.addWidget(self.clearsmart_button)

        self.main_layout.addLayout(clear_layout)
        self.main_layout.addLayout(victoria_layout)
        self.main_layout.addLayout(smart_layout)
        self.main_layout.addWidget(self.eject_button)
        self.setLayout(self.main_layout)

        self.setStyleSheet("""
            QWidget { background-color: #2B2F31; color: #FFFFFF; }
            QLabel { font-size: 13px; font-weight: bold; }
        """)
        self.resize(550, 340)

        self.thread_data = ThreadData()
        self.clipboard = QApplication.clipboard()
        self.dtimer = QTimer(); self.dtimer.timeout.connect(self.refresh_disk_info); self.dtimer.start(500)
        self.stimer = QTimer(); self.stimer.timeout.connect(self.refresh_smart_info); self.stimer.start(500)
        self.thread_data.update() 
        self.configure_disk_labels()
        self.refresh_disk_info()

        threading.Thread(target=self.run_update_thread, daemon=True).start()
        self.clearing_thread = None
        self.clr_thr_timer = QTimer(); self.clr_thr_timer.timeout.connect(self.clearing_activity)
        self.scsi_sleep_thread = None
        self.sleep_thr_timer = QTimer(); self.sleep_thr_timer.timeout.connect(self.scsi_sleep_activity)

    def victoria_open(self, connected=8):
        global VICTORIA_PATH, CONFIG_PATH

        l = [i for i, m in enumerate(self.disk_labels['model']) if i != 0 and not m.text().split()[1].strip().startswith(("Not", "! "))]

        if not os.path.exists(VICTORIA_PATH):
            options = QFileDialog.Options() | QFileDialog.ReadOnly
            file_path, _ = QFileDialog.getOpenFileName(self, "Chose Victoria file", "", "Executable (*.exe);;All files (*)", options=options)
            if file_path:
                ini_path = file_path.replace('.exe', '.ini')
                full_path = (file_path + '\n' + ini_path).replace('/', '\\')
                try:
                    if not file_path.endswith(".exe"):
                        raise ValueError("Выберите исполняемый файл (.exe).")
                    with open("victoriapath", "w") as file: file.write(full_path)
                    QMessageBox.information(self, "Done", f"Victoria path saved. Restart required")
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить путь: {e}")
        else:
            # костыль для запуска скрипта
            threading.Thread(target=victoria_open_ctypes.victoria_run, args=(tuple(l), ), daemon=True).start()

    def clearing_activity(self):
        if not self.clearing_thread.is_alive():
            self.clr_thr_timer.stop()
            for b in (self.cleard_button, self.clearr_button): b.setDisabled(False)
            self.cleard_button.setText("DP Clear DEFAULT"); self.clearr_button.setText("DP Clear RESCAN")
            self.cleard_button.setStyleSheet("color: white;"); self.clearr_button.setStyleSheet("color: white;")

    # def script_activity(self, method):
    #     if not self.clearing_thread.is_alive():
    #         self.clr_thr_timer.stop()
    #         for b in (self.cleard_button, self.clearr_button): b.setDisabled(False)
    #         self.cleard_button.setText("DP Clear DEFAULT"); self.clearr_button.setText("DP Clear RESCAN")
    #         self.cleard_button.setStyleSheet("color: white;"); self.clearr_button.setStyleSheet("color: white;")

    def scsi_sleep_activity(self):
        if not self.scsi_sleep_thread.is_alive():
            self.sleep_thr_timer.stop()
            self.eject_button.setDisabled(False)
            self.eject_button.setText("Sleep (SCSI)")
            self.eject_button.setStyleSheet("color: white;")

    def _configure_markers_info(self):
        widget = QWidget(); h_layout = QHBoxLayout(widget)
        marks = [
            (mMark('green'), "w/o parts"),
            (mMark('yellow'), "with parts"),
            (mMark('red'), "not connected"),
            (mMark('grey'), "busy"),
            (mMark('orange'), "err"),
            (mMark('#9500F4'), "sleep")
        ]
        for mark, text in marks:
            h_layout.addWidget(mark); h_layout.addWidget(QLabel(text)); h_layout.addSpacing(10)
        self.main_layout.addWidget(widget)

    def run_update_thread(self):
        while True:
            self.thread_data.update(); time.sleep(1)

    def show_context_menu(self, lb: QLabel, idx=0, pos=None):
        context_menu = QMenu(self)

        actions = {
            "Clear (Default)": lambda: self.clear_default(single_idx=idx),
            "Clear (Rescan)": lambda: self.clear_rescan(single_idx=idx),
            "Send sleep": lambda: threading.Thread(
                target=scsi_sleep_command, args=((idx,),), daemon=True
            ).start(),
            "Copy": lambda: self.clipboard.setText(' '.join(lb.text().split()[1:]).strip()),
            "SMART": lambda: self.clipboard.setText(' '.join(lb.text().split()[1:]).strip())
        }

        # добавляем пункты меню
        for text in actions.keys():
            context_menu.addAction(text)

        # позиция — где кликнули
        global_pos = lb.mapToGlobal(pos) if pos else lb.mapToGlobal(lb.rect().center())
        action = context_menu.exec_(global_pos)

        if action and action.text() in actions:
            actions[action.text()]()



    def configure_disk_labels(self):
        for i in range(10):
            item, widget, h_layout = QListWidgetItem(), QWidget(), QHBoxLayout()
            self.disk_labels['model'][i].setText(f"[{i}]  None")
            self.disk_labels['model'][i].setStyleSheet("color: red;")
            self.disk_labels['smart_data'][i].setText("[smart data]") 
            self.disk_labels['smart_cache'][i].setText("[smart cache]")
            self.disk_labels['percentage'][i].setText("-%")
            self.disk_labels['serial'][i].setText("S/N: 223")

            for key in ('circle','model','serial','smart_data','smart_cache','percentage','checkbox'):
                h_layout.addWidget(self.disk_labels[key][i])

            h_layout.setContentsMargins(0,0,0,0)
            widget.setLayout(h_layout); item.setSizeHint(widget.sizeHint())
            self.disk_list.addItem(item); self.disk_list.setItemWidget(item, widget)

    def reset_smart_button(self):
        self.pushsmart_button.setText('Get SMART (smartctl)'); self.pushsmart_button.setStyleSheet("color: white;")

    def clear_smart_cache(self):
        for i in self.disk_labels['smart_cache']: i.d_reset('smart cache')

    def push_smart(self, disk_num=False):
        self.pushsmart_button.setText("calling SMART..."); self.pushsmart_button.setStyleSheet("color: #DC93CD")
        smarts = smart_check.get_short_smarts(disk_num) if disk_num else smart_check.get_short_smarts()
        self.thread_data.smart_queue.put(smarts)
        self.pushsmart_button.setText("SMART updated."); self.pushsmart_button.setStyleSheet("color: #16F76E;")
        self.smtimer = QTimer(); self.smtimer.setSingleShot(True); self.smtimer.timeout.connect(self.reset_smart_button); self.smtimer.start(1000)

    def refresh_smart_info(self):
        try: short_sm, complex_sm = self.thread_data.smart_queue.get_nowait()
        except queue.Empty: return
        for (i, inf), (i2, inf2) in zip(short_sm, complex_sm):
            curr_smart = self.disk_labels['smart_data'][i].text()
            if curr_smart not in (inf, '[smart data]'):
                self.disk_labels['smart_cache'][i].setText(curr_smart)
                self.disk_labels['smart_cache'][i].smart_complex += curr_smart + '\n'
                self.disk_labels['smart_cache'][i].set_color('#DDE3E3')
            if inf == '!timeout':
                self.disk_labels['smart_data'][i].setStyleSheet("color: #E087CA;"); self.disk_labels['smart_data'][i].setText(inf); continue
            if inf:
                self.disk_labels['smart_data'][i].setText(inf); self.disk_labels['smart_data'][i].d_update(inf2)
                if inf.startswith('wu'):
                    no_errors = inf.replace('wu','_').replace('ru','_') == '_0_0'
                    self.disk_labels['smart_data'][i].setStyleSheet("color: white;" if no_errors else "color: yellow;")
                    if 'malfunction' in inf2:
                        self.disk_labels['smart_data'][i].setStyleSheet("color: #ED321C;")
                    continue
                if 'lf' in inf:
                    self.disk_labels['smart_data'][i].setStyleSheet("color: white;"); continue
                self.disk_labels['smart_data'][i].setStyleSheet("color: #16F76E;")
                if any(d.isdigit() and int(d)>0 for d in inf):
                    self.disk_labels['smart_data'][i].setStyleSheet("color: #F7A116;")

    def refresh_disk_info(self):        
        if self.thread_data.is_refresh_require:
            try:
                disk_info = self.thread_data.disks_queue.get_nowait()
                
            except queue.Empty:
                return

            for i, model, serial, p_info, is_sleep, percentage in disk_info:
                match p_info, model, is_sleep:
                    case p_info, model, 'IO':
                        model = model + ' (I/O)'
                        cclr = 'orange'
                    case p_info, model, 'CONFLICT':
                        model = model + ' (process conflict)'
                        cclr = 'orange'
                    case 'UL' | 'NL' | 'NC', 'Not connected' | "! Disconnected !", False:
                        cclr = 'red'
                        self.disk_labels['smart_data'][i].d_reset(msg='smart data')
                        self.disk_labels['smart_cache'][i].d_reset(msg='smart cache')
                    case 'EL', model, False:
                        cclr = 'yellow'
                    case 'NL', model, False:
                        cclr = 'green'
                    case 'CRC' | 'IO' | 'OUT' as e, model, is_sleep:
                        model = model + f' ({e})'
                        cclr = 'orange'
                    case p_info, model, True:
                         # print(p_info, model, is_sleep)
                        cclr = '#9500F4'
                    case _:
                        cclr = 'grey'

                if serial.startswith('0000'):
                    serial = "..."

                
                if percentage:
                    self.disk_labels['percentage'][i].setText(f"{percentage}%")

                self.disk_labels['circle'][i].setStyleSheet(f"background-color: {cclr}; border-radius: 7.5px;")

                # Создаем метку для модели
                self.disk_labels['model'][i].setText(f"[{i}]  " + model)

                clr_m = "red" if model == 'Not connected' else '#27C4E2'
                self.disk_labels['model'][i].setStyleSheet("color: %s;" % clr_m)  # Установка цвета для модели

                # Создаем метку для серийного номера
                self.disk_labels['serial'][i].setText(serial.strip())

          
 
    def gather_indices(self) -> list:
        selected_indices = []  # Список для хранения индексов выделенных элементов

        for i, cb in enumerate(self.disk_labels['checkbox']):
            if cb.isChecked():
                selected_indices.append(i)  # Добавляем индекс выделенного элемента

        if selected_indices:
            return selected_indices

    def start_victoria_script(self, method):
        selected_indices = self.gather_indices()

        if selected_indices:
            selected_indices.append(method)
            # for device in selected_indices:
            #     run_victoria_script(device, method)



            self.scsi_sleep_thread = threading.Thread(target=cycle_victoria_script, args=(selected_indices, ), daemon=True)
            self.scsi_sleep_thread.start()

    def eject_device(self):
        selected_indices = self.gather_indices()

        if selected_indices:

            self.scsi_sleep_thread = threading.Thread(target=scsi_sleep_command, args=(selected_indices, ), daemon=True)
            self.scsi_sleep_thread.start()
            self.sleep_thr_timer.start(200)
            self.eject_button.setDisabled(True)
            self.eject_button.setText("SENDING SLEEP TO DEVICES...")
            self.eject_button.setStyleSheet("color: #DC93CD")

    def clear_rescan(self, single_idx=False):
        selected_indices = self.gather_indices()

        if single_idx in range(10):
            selected_indices = (single_idx, )

        if selected_indices:
            self.clearing_thread = threading.Thread(target=du.delete_disk_partitions, args=(selected_indices, True,  ), daemon=True)
            self.clearing_thread.start()
            self.clr_thr_timer.start(200)
            self.clearr_button.setDisabled(True)
            self.cleard_button.setDisabled(True)
            self.clearr_button.setText("CLEARING PARTITIONS...")
            self.clearr_button.setStyleSheet("color: #DC93CD")


    def clear_default(self, single_idx=False):
        selected_indices = self.gather_indices()

        if single_idx in range(1, 10):
  
            selected_indices = (single_idx, )

        if selected_indices:
            self.clearing_thread = threading.Thread(target=du.delete_disk_partitions, args=(selected_indices, False, ), daemon=True)
            self.clearing_thread.start()
            self.clr_thr_timer.start(200)
            self.cleard_button.setDisabled(True)
            self.clearr_button.setDisabled(True)
            self.cleard_button.setText("CLEARING PARTITIONS...")
            self.cleard_button.setStyleSheet("color: #DC93CD")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        window = DiskApp()
        window.show()
    except Exception as ex_:
        with open('last_ex.log', 'w+', encoding='utf-8') as file:
            file.write(str(ex_))

    sys.exit(app.exec_())
