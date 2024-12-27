from PyQt5.QtWidgets import (
    QApplication, QWidget, 
    QListWidget, QVBoxLayout, 
    QListWidgetItem, QLabel, 
    QHBoxLayout, QPushButton, 
    QCheckBox, QMenu,
    QFileDialog, QMessageBox,)
from functools import partial
from victoria_open_ctypes import VICTORIA_PATH, CONFIG_PATH
import victoria_open_ctypes
import threading
import time
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon
from scsi_start_stop_unit import scsi_sleep_command, is_disk_sleeping
import queue
import sys
import diskutils as du
import os
        
class ThreadData:
    def __init__(self) -> None:
        self.connected_drives = 0
        self.disk_info = []
        self.cache_part_sequence = ''
        self.cache_connected_drives = 0
        self.is_refresh_require = False
        self.queue = queue.Queue()
    
    def update(self):
        n_connected_drives = 0
        self.disk_info.clear()

        for i in range(10):  # Предположим, проверяем до 10 дисков
            info = du.get_disk_info(i)  # Получаем информацию о диске
            #  print(info)
            if info == 'OUT':
                self.disk_info.append((i, "! Disconnected !", "", "UL", False))  # Если диск не подключен
            elif isinstance(info, tuple): # if info is tuple, not 'OUT
                self.disk_info.append(list(info))
                self.disk_info[i].append(is_disk_sleeping(i))  # Извлекаем модель и серийный номер
                n_connected_drives += 1
            else:
                self.disk_info.append((i, "Not connected", "", "UL", False))  # Если диск не подключен


        n_part_sequence = ''.join(str(i[3]) + str(i[-1]) for i in self.disk_info)
        self.is_refresh_require = any([
            self.cache_part_sequence != n_part_sequence,
            self.cache_connected_drives != n_connected_drives
        ])

        if self.is_refresh_require:
            self.queue.put(self.disk_info.copy())
            self.cache_connected_drives = n_connected_drives
            self.cache_part_sequence = n_part_sequence
            return True

class mModel(QLabel):
    def __init__(self, parent, idx):
        self.parent_: DiskApp = parent
        # self.parent = parent
        super().__init__()
        self.setContextMenuPolicy(Qt.CustomContextMenu)  # Включаем поддержку пользовательского контекстного меню
        self.customContextMenuRequested.connect(lambda: self.parent_.show_context_menu(self, idx))
    
class mSerial(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("color: #65FA48;")

class mCheckBox(QCheckBox):
    def __init__(self, idx):
        super().__init__()
        self.setFixedSize(20, 20)
        self.setChecked(True if idx != 0 else False)  # Устанавливаем состояние чекбокса
        self.setStyleSheet("text-align: end;")  # Устанавливаем цвет текста чекбокса

class DiskApp(QWidget):
    def __init__(self):
        super().__init__()
        # Создаем основной компоновщик
        self.setWindowTitle("HDD-Handler")
        self.setMinimumSize(600, 360)
        # self.layout = QVBoxLayout()
        self.icon = QIcon('hddc.ico')
        self.setWindowIcon(self.icon)

        # Создаем QListWidget
        self.disk_list = QListWidget()
        self.disk_labels = {
            'model': [mModel(self, idx) for idx in range(10)],
            'serial': [mSerial() for _ in range(10)],
            'checkbox': [mCheckBox(idx) for idx in range(10)]
        }

         # Основной вертикальный компоновщик
        self.main_layout = QVBoxLayout()
        

        # Добавляем лейбл "Refresh activity" в верхней части окна
        
        
        self._configure_markers_info()
        # Горизонтальный компоновщик для верхней части
        

        # Добавляем верхний лейаут в основной
        

        # Создаем QListWidget
        self.disk_list = QListWidget()
        self.main_layout.addWidget(self.disk_list)

        # Кнопка для очистки разделов
        self.cleard_button = QPushButton("DP Clear DEFAULT")
        self.clearr_button = QPushButton("DP Clear RESCAN")
        self.eject_button = QPushButton("Sleep (SCSI)")
        # self.refresh_button = QPushButton("Refresh")
        self.victoria_button = QPushButton("Victoria (8 wins)")
        self.victoria_close_button = QPushButton("Victoria (avaliable disks)")

        # Подключаем события к кнопкам
        self.cleard_button.clicked.connect(self.clear_default)
        self.clearr_button.clicked.connect(self.clear_rescan)
        self.eject_button.clicked.connect(self.eject_device)
        # self.refresh_button.clicked.connect(self.enable_refresh)
        self.victoria_button.clicked.connect(partial(self.victoria_open, 8))
        self.victoria_close_button.clicked.connect(partial(self.victoria_open, 1))

        # Создаем горизонтальный компоновщик для кнопок Clear
        clear_layout = QHBoxLayout()
        clear_layout.addWidget(self.cleard_button)
        clear_layout.addWidget(self.clearr_button)

        # Создаем горизонтальный компоновщик для кнопок Victoria
        victoria_layout = QHBoxLayout()
        victoria_layout.addWidget(self.victoria_button)
        victoria_layout.addWidget(self.victoria_close_button)

        # Добавляем компоновки кнопок в основной вертикальный компоновщик
        self.main_layout.addLayout(clear_layout)
        self.main_layout.addLayout(victoria_layout)

        # Остальные кнопки добавляем ниже
        self.main_layout.addWidget(self.eject_button)
        # self.main_layout.addWidget(self.refresh_button)

        # # Добавляем лейбл "Refresh activity" внизу
        # self.refresh_label = QLabel("Refresh activity")
        # self.refresh_label.setAlignment(Qt.AlignCenter)
        # self.refresh_label.setStyleSheet("font-size: 10px; background-color: #555; color: #FFF;")
        # self.main_layout.addWidget(self.refresh_label)
        # self.is_refresh_highlighted = False  # Флаг состояния цвета лейбла

        # self.refresh_label = QLabel("R")
        # self.refresh_label.setFixedSize(20, 20)  # Размер круга 20x20
        # self.refresh_label.setStyleSheet("""
        #     background-color: #2652D6;
        #     border-radius: 10px;  /* Делает лейбл круглым */
        #     border: 1px solid #333;
        # """)
        # self.is_refresh_highlighted = False

        # top_layout = QHBoxLayout()
        # top_layout.addWidget(self.refresh_label, alignment=Qt.AlignLeft)  # Лейбл выравнен влево
        # top_layout.addStretch()  # Добавляем пространство для выравнивания
        # self.main_layout.addLayout(top_layout)

        # Устанавливаем основной компоновщик
        self.setLayout(self.main_layout)

        # Устанавливаем заголовок и размеры окна
        
        self.setStyleSheet("""
            QWidget {
                background-color: #2B2F31;  /* Цвет фона */
                color: #FFFFFF;  /* Цвет текста */
            }
            QLabel {
                font-size: 13px;  /* Размер шрифта */
                font-weight: bold;
            }
        """)
        self.resize(550, 340)

        self.thread_data = ThreadData()
        self.clipboard = QApplication.clipboard()

        # Запускаем таймер для обновления информации каждые 2 секунды
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_disk_info)
        self.timer.start(500)

        # Первая инициализация информации о дисках
        self.thread_data.update()
        self.refresh_disk_info()
        # self.enable_refresh()
        
        self.update_thread = threading.Thread(target=self.run_update_thread, daemon=True).start()
        self.clearing_thread: threading.Thread = None
        self.clr_thr_timer = QTimer()
        self.clr_thr_timer.timeout.connect(self.clearing_activity)

        self.scsi_sleep_thread: threading.Thread = None
        self.sleep_thr_timer = QTimer()
        self.sleep_thr_timer.timeout.connect(self.scsi_sleep_activity)

        # self.victoriaa_thread = threading>ThreadData(target=self.victoria_open)
        
    def victoria_open(self, connected=8):
        global VICTORIA_PATH, CONFIG_PATH

        if connected == 8:
            l = range(1, 9)
        elif connected == 1:
            l = []
            for i, m in enumerate(self.disk_labels['model']):
                # print(i)
                if i != 0:
                    model: str = m.text().split()[1].strip()
                    if not model.startswith(("Not", "! ")):
                        l.append(i)
                
            l = tuple(l)
        
        print(l)

        if not os.path.exists(VICTORIA_PATH):
            print(VICTORIA_PATH)
            options = QFileDialog.Options()
            options |= QFileDialog.ReadOnly
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Chose Victoria file",
                "",
                "Executable (*.exe);;All files (*)",
                options=options
            )
            # print(file_path)
            if file_path:
                ini_path = file_path.replace('.exe', '.ini')
                full_path = (file_path + '\n' + ini_path).replace('/', '\\')
                try:
                    # Проверка, что выбран файл с расширением .exe
                    if not file_path.endswith(".exe"):
                        raise ValueError("Выберите исполняемый файл (.exe).")

                    # Сохранение пути в файл
                    config_path = "victoriapath"  # Укажите путь к файлу для сохранения пути
                    with open(config_path, "w") as file:
                        file.write(full_path)


                    # print('cfg and exe', VICTORIA_PATH + CONFIG_PATH)

                    QMessageBox.information(self, "Done", f"Victoria path saved.\n{full_path}\n\nRestart required")
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить путь: {str(e)}")

        else:
            print('victoria found. Running')
            threading.Thread(target=victoria_open_ctypes.victoria_run, args=(l, ), daemon=True).start()
        # return



        # options = QFileDialog.Options()
        # options |= QFileDialog.ReadOnly
        # file_path, _ = QFileDialog.getOpenFileName(
        #     self,
        #     "Выберите файл Victoria",
        #     "",
        #     "Исполняемые файлы (*.exe);;Все файлы (*)",
        #     options=options
        # )

        # if file_path:
        #     try:
        #         # Проверка, что выбран файл с расширением .exe
        #         if not file_path.endswith(".exe"):
        #             raise ValueError("Выберите исполняемый файл (.exe).")

        #         # Сохранение пути в файл
        #         config_path = "victoriapath"  # Укажите путь к файлу для сохранения пути
        #         with open(config_path, "w") as file:
        #             file.write(file_path)

        #         QMessageBox.information(self, "Успех", f"Путь к Victoria сохранён:\n{file_path}")
        #     except Exception as e:
        #         QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить путь: {str(e)}")

        # threading.Thread(target=victoria_open_ctypes.victoria_run, args=(l, ), daemon=True).start()
    
    def victoria_close(self):
        ...

    def clearing_activity(self):
        
        if not self.clearing_thread.is_alive():
            self.clr_thr_timer.stop()
            self.cleard_button.setDisabled(False)
            self.clearr_button.setDisabled(False)
            self.cleard_button.setText("Clear DEFAULT")
            self.clearr_button.setText("Clear RESCAN")
            self.cleard_button.setStyleSheet("color: white;")
            self.clearr_button.setStyleSheet("color: white;")

    def scsi_sleep_activity(self):
        
        if not self.scsi_sleep_thread.is_alive():
            self.sleep_thr_timer.stop()
            self.eject_button.setDisabled(False)
            self.eject_button.setText("Sleep (SCSI)")
            self.eject_button.setStyleSheet("color: white;")

    def _configure_markers_info(self):
        widget = QWidget()  # Создаем виджет для элемента
        h_layout = QHBoxLayout(widget)  # Используем компоновщик внутри этого виджета

        # Создаем цветные метки-кружочки и поясняющий текст
        green_mrk = self._colored_marker('green')
        yellow_mrk = self._colored_marker('yellow')
        red_mrk = self._colored_marker('red')
        grey_mrk = self._colored_marker('grey')
        orange_mrk = self._colored_marker('orange')
        violet_mark = self._colored_marker('#9500F4')

        
        
        # Добавляем кружочки и текст к каждому индикатору
        h_layout.addWidget(green_mrk)
        h_layout.addWidget(QLabel("w/o parts"))

        h_layout.addSpacing(10)  # Расстояние между кружочками

        h_layout.addWidget(yellow_mrk)
        h_layout.addWidget(QLabel("with parts"))

        h_layout.addSpacing(10)  # Расстояние между кружочками

        h_layout.addWidget(red_mrk)
        h_layout.addWidget(QLabel("not connected"))

        h_layout.addSpacing(10)  # Расстояние между кружочками

        h_layout.addWidget(grey_mrk)
        h_layout.addWidget(QLabel("busy"))

        h_layout.addSpacing(10)  # Расстояние между кружочками

        h_layout.addWidget(orange_mrk)
        h_layout.addWidget(QLabel("err"))

        h_layout.addSpacing(10)  # Расстояние между кружочками

        h_layout.addWidget(violet_mark)
        h_layout.addWidget(QLabel("sleep"))


        # Добавляем компоновщик с цветными кружками и текстом в основной макет окна
        self.main_layout.addWidget(widget)

    def _colored_marker(self, color):
        mrk = QLabel()
        mrk.setFixedSize(15, 15)  # Устанавливаем размер кружка
        mrk.setStyleSheet(f"background-color: {color}; border-radius: 7.5px;")
        return mrk

    
    # def enable_refresh(self):
    #     if not self.timer.isActive():
    #         self.timer.start(500)
    #         # self.refresh_button.setStyleSheet("color: #41C871;")
    #     else:
    #         # self.refresh_button.setStyleSheet("color: #FFFFFF;")
    #         self.timer.stop()
    
    def run_update_thread(self):

        while True:
            self.thread_data.update()
            time.sleep(1)
    
    def show_context_menu(self, lb: QLabel, idx=0):
        # Создаем контекстное меню
        context_menu = QMenu(self)
        position = lb.pos()

        # Добавляем пункты меню
        action_clear_d = context_menu.addAction("Clear (Default)")
        action_clear_r = context_menu.addAction("Clear (Rescan)")
        action_sleep = context_menu.addAction("Send sleep")
        action_copy = context_menu.addAction("Copy")

        # Отображаем меню в позиции курсора
        action = context_menu.exec_(lb.mapToGlobal(position))

        # Обработка выбранного действия
        if action == action_clear_d:
            self.clear_default(single_idx=idx)
        elif action == action_clear_r:
            self.clear_rescan(single_idx=idx)
        elif action == action_sleep:
            threading.Thread(target=scsi_sleep_command, args=((idx, ), ), daemon=True).start()
        elif action == action_copy:
            disk_model = ' '.join(lb.text().split()[1:]).strip()
            self.clipboard.setText(disk_model)


    def refresh_disk_info(self):
            # if self.is_refresh_highlighted:
            #     self.refresh_label.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #2652D6; color: #2652D6;")
            # else:
            #     self.refresh_label.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #5C65D6; color: #5C65D6;")
            # self.is_refresh_highlighted = not self.is_refresh_highlighted

        if self.thread_data.is_refresh_require:
            try:
                disk_info = self.thread_data.queue.get_nowait()
            except queue.Empty:
                return
            
            self.disk_list.clear()

            for i, model, serial, p_info, is_sleep in disk_info:
                
                # Метка для кружка
                item = QListWidgetItem()  # Создаем элемент списка
                widget = QWidget()  # Создаем виджет для элемента
                h_layout = QHBoxLayout()  # Горизонтальный компоновщик


                # Создаем метку для индекса

                match p_info, model, is_sleep:
                    case p_info, model, 'IO':
                        model = model + ' (I/O)'
                        cclr = 'orange'
                    case p_info, model, 'CONFLICT':
                        model = model + ' (process conflict)'
                        cclr = 'orange'
                    case 'UL' | 'NL' | 'NC', 'Not connected' | "! Disconnected !", False:
                        cclr = 'red'
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

                circle = self._colored_marker(color=cclr)
        
                # Создаем метку для модели
                self.disk_labels['model'][i].setText(f"[{i}]  " + model)

                clr_m = "red" if model == 'Not connected' else '#27C4E2'
                self.disk_labels['model'][i].setStyleSheet("color: %s;" % clr_m)  # Установка цвета для модели

                # Создаем метку для серийного номера
                self.disk_labels['serial'][i].setText("S/N: " + serial.strip())

                # Добавляем виджеты в горизонтальный компоновщик
                h_layout.addWidget(circle)
                h_layout.addWidget(self.disk_labels['model'][i])
                h_layout.addWidget(self.disk_labels['serial'][i])
                h_layout.addWidget(self.disk_labels['checkbox'][i])
                h_layout.setContentsMargins(0, 0, 0, 0)  # Убираем отступы

                widget.setLayout(h_layout)  # Устанавливаем компоновщик для виджета
                item.setSizeHint(widget.sizeHint())  # Устанавливаем размер элемента
                self.disk_list.addItem(item)  # Добавляем элемент в QListWidget
                self.disk_list.setItemWidget(item, widget)  # Устанавливаем виджет для элемента
 
    def gather_indices(self) -> list:
        selected_indices = []  # Список для хранения индексов выделенных элементов

        for i, cb in enumerate(self.disk_labels['checkbox']):
            if cb.isChecked():
                selected_indices.append(i)  # Добавляем индекс выделенного элемента

        if selected_indices:
            return selected_indices

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
            print("Selected partitions to clear:", selected_indices)

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
            print("Selected partitions to clear:", selected_indices)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        window = DiskApp()
        window.show()
    except Exception as ex_:
        with open('last_ex.log', 'w+', encoding='utf-8') as file:
            file.write(str(ex_))

    sys.exit(app.exec_())
