from PyQt5.QtWidgets import (
    QApplication, QWidget, 
    QListWidget, QVBoxLayout, 
    QListWidgetItem, QLabel, 
    QHBoxLayout, QPushButton, 
    QCheckBox)
import threading
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from scsi_start_stop_unit import scsi_sleep_command, is_disk_sleeping
import sys
import diskutils as du
# from diskutils import get_disk_info, get_partition_count, delete_disk_partitions  # Импортируем функцию для получения информации о дисках
        
class ThreadData:
    def __init__(self) -> None:
        self.connected_drives = 0
        self.disk_info = []
        self.cache_part_sequence = ''
        self.cache_connected_drives = 0
        self.is_refresh_require = False
    
    def update(self):
        n_connected_drives = 0

        for i in range(10):  # Предположим, проверяем до 10 дисков
            info = du.get_disk_info(i)  # Получаем информацию о диске
            # partition_info = get_partition_count(i)
            if info:
                self.disk_info.append(list(info))
                self.disk_info[i].append(is_disk_sleeping(i))  # Извлекаем модель и серийный номер
                n_connected_drives += 1
            else:
                self.disk_info.append((i, "Not connected", "", "UL", False))  # Если диск не подключен
        # print(self.disk_info)
        # print(disks_info)

        n_part_sequence = ''.join(i[3] + str(i[-1]) for i in self.disk_info)
        # print(n_part_sequence)
        # print(part_sequence)
        self.is_refresh_require = any([
            self.cache_part_sequence != n_part_sequence,
            self.cache_connected_drives != n_connected_drives
        ])

        if self.is_refresh_require:
            self.cache_connected_drives = n_connected_drives
            self.cache_part_sequence = n_part_sequence
            return True
        
            # self.disk_list.clear()

class DiskApp(QWidget):
    def __init__(self):
        super().__init__()
        # Создаем основной компоновщик
        self.setWindowTitle("HHD-Handler")
        self.layout = QVBoxLayout()
        self.icon = QIcon('lib\\hdd.ico')
        self.setWindowIcon(self.icon)
        # self.layout.setContentsMargins(2, 5, 5, 5)  # Убираем отступы
        
        # Создаем QListWidget
        self.disk_list = QListWidget()
        # self.disk_list.setSpacing(10)
        # self.disk_list.setContentsMargins(0, 0, 0, 0)
        
        # Кнопка для очистки разделов
        self.cleard_button = QPushButton("Clear partitions (DEFAULT)")
        self.clearr_button = QPushButton("Clear partitions (RESCAN)")
        self.eject_button = QPushButton("Send sleep command (SCSI)")
        self.refresh_button = QPushButton("Enable refresh")
        
        self.cleard_button.clicked.connect(self.clear_selected_partitions)
        self.clearr_button.clicked.connect(self.rescan_clear)
        self.eject_button.clicked.connect(self.eject_device)
        self.refresh_button.clicked.connect(self.enable_refresh)
        
 
        
        # sef.green_circle_label = QLabel("GREEN - disk w/o partitions | YELLOW - must be cleared | RED - not connected")
        
        
        self._configure_markers_info()
        

        
        # Устанавливаем компоновщик
        self.layout.addWidget(self.disk_list)
        # self.layout.addWidget(self.green_circle_label)
        self.layout.addWidget(self.cleard_button)
        self.layout.addWidget(self.clearr_button)
        self.layout.addWidget(self.eject_button)
        self.layout.addWidget(self.refresh_button)
        self.setLayout(self.layout)

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

        # Запускаем таймер для обновления информации каждые 2 секунды
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_disk_info)

        # Первая инициализация информации о дисках
        self.connected_drives_cache = 0
        self.partition_sequence = ''
        self.refresh_disk_info()
        
        self.clearing_thread: threading.Thread = None
        self.clr_thr_timer = QTimer()
        self.clr_thr_timer.timeout.connect(self.clearing_activity)

        self.scsi_sleep_thread: threading.Thread = None
        self.sleep_thr_timer = QTimer()
        self.sleep_thr_timer.timeout.connect(self.scsi_sleep_activity)
        
        

    def clearing_activity(self):
        
        if not self.clearing_thread.is_alive():
            self.clr_thr_timer.stop()
            self.cleard_button.setDisabled(False)
            self.clearr_button.setDisabled(False)
            self.cleard_button.setText("Clear partitions (DEFAULT)")
            self.clearr_button.setText("Clear partitions (RESCAN)")
            self.cleard_button.setStyleSheet("color: white;")
            self.clearr_button.setStyleSheet("color: white;")

    def scsi_sleep_activity(self):
        
        if not self.scsi_sleep_thread.is_alive():
            self.sleep_thr_timer.stop()
            self.eject_button.setDisabled(False)
            self.eject_button.setText("Send sleep command (SCSI)")
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
        h_layout.addWidget(QLabel("w/o partitions"))

        h_layout.addSpacing(10)  # Расстояние между кружочками

        h_layout.addWidget(yellow_mrk)
        h_layout.addWidget(QLabel("with partitions"))

        h_layout.addSpacing(10)  # Расстояние между кружочками

        h_layout.addWidget(red_mrk)
        h_layout.addWidget(QLabel("not connected"))

        h_layout.addSpacing(10)  # Расстояние между кружочками

        h_layout.addWidget(grey_mrk)
        h_layout.addWidget(QLabel("busy"))

        h_layout.addSpacing(10)  # Расстояние между кружочками

        h_layout.addWidget(orange_mrk)
        h_layout.addWidget(QLabel("Err"))

        h_layout.addSpacing(10)  # Расстояние между кружочками

        h_layout.addWidget(violet_mark)
        h_layout.addWidget(QLabel("in sleep"))


        # Добавляем компоновщик с цветными кружками и текстом в основной макет окна
        self.layout.addWidget(widget)

    def _colored_marker(self, color):
        mrk = QLabel()
        mrk.setFixedSize(15, 15)  # Устанавливаем размер кружка
        mrk.setStyleSheet(f"background-color: {color}; border-radius: 7.5px;")
        return mrk

    
    def enable_refresh(self):
        if not self.timer.isActive():
            self.timer.start(1000) 
            self.refresh_button.setStyleSheet("color: #41C871;")
        else:
            self.refresh_button.setStyleSheet("color: #FFFFFF;")
            self.timer.stop()
        
    def refresh_disk_info(self):

        self.thread_data.disk_info.clear()
        new_data = self.thread_data.update()


        # print(self.thread_data.cache_part_sequence)

        # # self.disk_list.clear()  # Очищаем список перед обновлением
        # connected_drives = 0
        # disks_info = []
        
        
        # for i in range(10):  # Предположим, проверяем до 10 дисков
        #     info = du.get_disk_info(i)  # Получаем информацию о диске
        #     # partition_info = get_partition_count(i)
        #     if info:
        #         disks_info.append(list(info))
        #         disks_info[i].append(is_disk_sleeping(i))  # Извлекаем модель и серийный номер
        #         connected_drives += 1
        #     else:
        #         disks_info.append((i, "Not connected", "", "UL", False))  # Если диск не подключен
        
        # # print(disks_info)

        # part_sequence = ''.join(i[3] + str(i[-1]) for i in disks_info)
        # # print(part_sequence)
        # refresh_require = [
        #     self.partition_sequence != part_sequence,
        #     self.connected_drives_cache != connected_drives
        # ]

        

        if new_data:
            self.disk_list.clear()
            # print('lst of drives updated')
            # start = time.time()
            
            for i, model, serial, p_info, is_sleep in self.thread_data.disk_info:
                
                # Метка для кружка
                # p_info = get_partition_count(i
                item = QListWidgetItem()  # Создаем элемент списка
                widget = QWidget()  # Создаем виджет для элемента
                h_layout = QHBoxLayout()  # Горизонтальный компоновщик

                # Чекбокс для выбора диска
                checkbox = QCheckBox()
                checkbox.setFixedSize(20, 20)
                checkbox.setChecked(True if i != 0 else False)  # Устанавливаем состояние чекбокса
                checkbox.setStyleSheet("text-align: end;")  # Устанавливаем цвет текста чекбокса

                # Создаем метку для индекса

                match p_info, model, is_sleep:
                    case p_info, model, 'IO':
                        model = model + ' (I/O)'
                        cclr = 'orange'
                    case p_info, model, 'CONFLICT':
                        model = model + ' (process conflict)'
                        cclr = 'orange'
                    case 'UL' | 'NL' | 'NC', 'Not connected', False:
                        cclr = 'red'
                    case 'EL', model, False:
                        cclr = 'yellow'
                    case 'NL', model, False:
                        cclr = 'green'
                    case 'CRC' | 'IO', model, False:
                        if p_info == 'CRC':
                            model = model + ' (CRC Err)'
                        if p_info == 'IO':
                            model = model + ' (I/O Err)'
                        cclr = 'orange'
                    case p_info, model, True:
                         # print(p_info, model, is_sleep)
                        cclr = '#9500F4'
                    case _:
                        cclr = 'grey'

                if serial.startswith('0000'):
                    serial = "..."

                    
                
                
                circle = self._colored_marker(color=cclr)
                # circle = QLabel()
                # circle.setFixedSize(15, 15)  # Устанавливаем размер кружка
                # circle.setStyleSheet("background-color: %s; border-radius: 7.5px;" % cclr)
                
                # Создаем метку для модели
                model_label = QLabel(f"[{i}] " + model)

                clr_m = "red" if model == 'Not connected' else '#27C4E2'
                model_label.setStyleSheet("color: %s;" % clr_m)  # Установка цвета для модели

                # Создаем метку для серийного номера
                serial_label = QLabel("S/N: " + serial.strip())
                serial_label.setStyleSheet("color: #65FA48;")  # Установка цвета для серийного номера
                
                # Добавляем виджеты в горизонтальный компоновщик
                h_layout.addWidget(circle)
                h_layout.addWidget(model_label)
                h_layout.addWidget(serial_label)
                # h_layout.addSpacerItem(QSpacerItem(40, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
                h_layout.addWidget(checkbox)
                
                
                h_layout.setSpacing(1)  # Задайте нужное расстояние в пикселях
                # h_layout.setAlignment()
                h_layout.setContentsMargins(0, 0, 0, 0)  # Убираем отступы

                widget.setLayout(h_layout)  # Устанавливаем компоновщик для виджета
                item.setSizeHint(widget.sizeHint())  # Устанавливаем размер элемента
                self.disk_list.addItem(item)  # Добавляем элемент в QListWidget
                self.disk_list.setItemWidget(item, widget)  # Устанавливаем виджет для элемента
                
                # self.connected_drives_cache = connected_drives
            # print(time.time() - start)
        # else:
        #     print('no updates')

    def eject_device(self):
        selected_indices = []  # Список для хранения индексов выделенных элементов
        for index in range(self.disk_list.count()):
            item = self.disk_list.item(index)
            widget = self.disk_list.itemWidget(item)  # Получаем виджет для элемента
            checkbox = widget.findChild(QCheckBox)  # Находим чекбокс в виджете
            if checkbox.isChecked():
                # delete_disk_partitions(index)
                selected_indices.append(index)  # Добавляем индекс выделенного элемента

        if selected_indices:

            self.scsi_sleep_thread = threading.Thread(target=scsi_sleep_command, args=(selected_indices, ), daemon=True)
            self.scsi_sleep_thread.start()
            self.sleep_thr_timer.start(200)
            self.eject_button.setDisabled(True)
            self.eject_button.setText("SENDING SLEEP TO DEVICES...")
            self.eject_button.setStyleSheet("color: #DC93CD")
            # print("Selected partitions to clear:", selected_indices)


            # for i in selected_indices:
            #     try:
            #         scsi_sleep_command(i)
            #     except FileNotFoundError as ex:
            #         if "WinError 2" in str(ex):
            #             ...
            #         else:
            #             print(ex)
                # du.eject_device(i)
    
    def rescan_clear(self):
        selected_indices = []  # Список для хранения индексов выделенных элементов
        for index in range(self.disk_list.count()):
            item = self.disk_list.item(index)
            widget = self.disk_list.itemWidget(item)  # Получаем виджет для элемента
            checkbox = widget.findChild(QCheckBox)  # Находим чекбокс в виджете
            if checkbox.isChecked():
                # delete_disk_partitions(index)
                selected_indices.append(index)  # Добавляем индекс выделенного элемента

        if selected_indices:
            self.clearing_thread = threading.Thread(target=du.delete_disk_partitions, args=(selected_indices, True,  ), daemon=True)
            self.clearing_thread.start()
            self.clr_thr_timer.start(200)
            self.clearr_button.setDisabled(True)
            self.cleard_button.setDisabled(True)
            self.clearr_button.setText("CLEARING PARTITIONS...")
            self.clearr_button.setStyleSheet("color: #DC93CD")
            print("Selected partitions to clear:", selected_indices)

    def clear_selected_partitions(self, rescan=False):
        selected_indices = []  # Список для хранения индексов выделенных элементов
        for index in range(self.disk_list.count()):
            item = self.disk_list.item(index)
            widget = self.disk_list.itemWidget(item)  # Получаем виджет для элемента
            checkbox = widget.findChild(QCheckBox)  # Находим чекбокс в виджете
            if checkbox.isChecked():
                # delete_disk_partitions(index)
                selected_indices.append(index)  # Добавляем индекс выделенного элемента

        if selected_indices:
            self.clearing_thread = threading.Thread(target=du.delete_disk_partitions, args=(selected_indices, rescan, ), daemon=True)
            self.clearing_thread.start()
            self.clr_thr_timer.start(200)
            self.cleard_button.setDisabled(True)
            self.clearr_button.setDisabled(True)
            self.cleard_button.setText("CLEARING PARTITIONS...")
            self.cleard_button.setStyleSheet("color: #DC93CD")
            print("Selected partitions to clear:", selected_indices)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DiskApp()
    window.show()
    sys.exit(app.exec_())
