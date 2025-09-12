from __future__ import annotations

"""
Refactored qtlayer.py with the following goals:
- Preserve the public API (class names, method signatures, behavior) while improving readability and maintainability.
- Add type hints and lightweight docstrings.
- Remove duplication (styles, repeated logic), extract small helpers, and replace magic numbers with constants.
- Keep UI/UX the same, including colors and text labels.

NOTE: External modules (victoria, victoria_open_ctypes, smart_check, diskutils, scsi_start_stop_unit)
are intentionally left untouched; this layer only orchestrates UI and threading.
"""

import os
import time
import queue
import threading
from datetime import datetime
from functools import partial
from typing import Iterable, List, Optional, Sequence, Tuple

from PyQt5.QtCore import QTimer, Qt, QPoint
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QListWidget,
    QVBoxLayout,
    QListWidgetItem,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
    QMenu,
    QFileDialog,
    QMessageBox,
)

from victoria.percentage import get_percentage
from victoria.ui import cycle_victoria_script, run_victoria_script as singlerun_victoria_script
from victoria_open_ctypes import VICTORIA_PATH, CONFIG_PATH  # noqa: F401  (CONFIG_PATH is used externally)
import victoria_open_ctypes
from scsi_start_stop_unit import scsi_sleep_command, is_disk_sleeping
import smart_check
import diskutils as du

# =====================
# Constants / Styling
# =====================
MAX_DISKS: int = 10
POLL_INTERVAL_MS: int = 500

STYLE_APP = """
QWidget { background-color: #2B2F31; color: #FFFFFF; }
QLabel { font-size: 13px; font-weight: bold; }
"""

HL_YELLOW_BG = "#FFF59D"   # мягкий желтый на темной теме
HL_GREEN_BG  = "#18ff95"   # светло-зеленый на полсекунды
HL_GREY_BG   = "#f0f8ff"   # нейтральный серый фон


COLOR_PRIMARY = "#27C4E2"
COLOR_WHITE = "white"
COLOR_PINK = "pink"
COLOR_GREEN = "green"
COLOR_YELLOW = "yellow"
COLOR_RED = "red"
COLOR_GREY = "grey"
COLOR_ORANGE = "orange"
COLOR_PURPLE_SLEEP = "#9500F4"
COLOR_OK = "#16F76E"
COLOR_WARN = "#F7A116"
COLOR_INFO = "#3BF4FA"
COLOR_ACTION = "#DC93CD"
COLOR_CACHE_TEXT = "#DDE3E3"
COLOR_ERROR = "#ED321C"
COLOR_IO = "orange"

# =====================
# Thread data model
# =====================
class ThreadData:
    """Holds data exchanged between worker thread(s) and UI thread."""

    def __init__(self) -> None:
        self.connected_drives: int = 0
        self.disk_info: List[Tuple[int, str, str, str, bool, Optional[int]]] = []
        self.cache_part_sequence: str = ""
        self.cache_connected_drives: int = 0
        self.is_refresh_require: bool = False
        self.disks_queue: "queue.Queue[List[Tuple[int, str, str, str, bool, Optional[int]]]]" = queue.Queue()
        self.smart_queue: "queue.Queue[Tuple[List[Tuple[int, str]], List[Tuple[int, str]]]]" = queue.Queue()

    def update(self) -> bool:
        """Poll disk state and enqueue when something changed.

        Returns
        -------
        bool
            True if a refresh was enqueued; False otherwise.
        """
        n_connected_drives = 0
        self.disk_info.clear()

        for i in range(MAX_DISKS):
            info = du.get_disk_info(i)
            percentage = get_percentage(i)

            if info == "OUT":
                self.disk_info.append((i, "! Disconnected !", "", "UL", False, percentage))
            elif isinstance(info, tuple):
                di = list(info)
                di.append(is_disk_sleeping(i))
                di.append(percentage)
                # type: ignore[arg-type]
                self.disk_info.append(tuple(di))
                n_connected_drives += 1
            else:
                self.disk_info.append((i, "Not connected", "", "UL", False, percentage))

        n_part_sequence = "".join(str(i[3]) + str(i[-1]) for i in self.disk_info)
        self.is_refresh_require = (
            self.cache_part_sequence != n_part_sequence
            or self.cache_connected_drives != n_connected_drives
        )

        if self.is_refresh_require:
            self.disks_queue.put(self.disk_info.copy())
            self.cache_connected_drives = n_connected_drives
            self.cache_part_sequence = n_part_sequence
            return True
        return False


# =====================
# Small UI widgets
# =====================
class mModel(QLabel):
    def __init__(self, parent: "DiskApp", idx: int) -> None:
        super().__init__()
        self.parent_: DiskApp = parent
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.parent_.show_context_menu(self, idx, pos)
        )


class PersistentToolTip(QLabel):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip)
        self.setStyleSheet(
            """
            QLabel {
                background-color: #333;
                color: white;
                border: 1px solid white;
                padding: 5px;
                text-align: justify;
            }
            """
        )
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.hide()

    def show_at(self, text: str, pos: QPoint) -> None:
        self.setText(text)
        self.adjustSize()
        self.move(pos)
        self.show()


class mPercentage(QLabel):
    def __init__(self) -> None:
        super().__init__()
        # Keep last applied style (original code overwrote with pink)
        self.setStyleSheet(f"color: {COLOR_PINK};")


class mSmart(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet(f"color: {COLOR_INFO};")
        self.smart_complex: str = ""
        self.tooltip = PersistentToolTip(self)
        self.setMouseTracking(True)

    def set_color(self, color: str = COLOR_INFO) -> None:
        self.setStyleSheet(f"color: {color};")

    def enterEvent(self, event):  # type: ignore[override]
        if self.smart_complex:
            self.tooltip.show_at(self.smart_complex, event.globalPos() + QPoint(10, 10))
        super().enterEvent(event)

    def leaveEvent(self, event):  # type: ignore[override]
        self.tooltip.hide()
        super().leaveEvent(event)

    def d_update(self, text: str) -> None:
        self.smart_complex = text

    def d_reset(self, msg: str = "sm_data") -> None:
        self.smart_complex = ""
        self.setStyleSheet(f"color: {COLOR_INFO};")
        self.setText(f"[{msg}]")


# class mSerial(QLabel):
#     def __init__(self) -> None:
#         super().__init__()
#         self.setStyleSheet("color: #65FA48;")

class mSerial(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet("color: #65FA48;")
        self.full_serial: str = ""
        self.tooltip = PersistentToolTip(self)
        self.setMouseTracking(True)

    def set_serial(self, serial: str) -> None:
        """Сохраняет полный серийник и показывает замаскированным (только последние 3 символа)."""
        self.full_serial = serial.strip()
        if len(self.full_serial) > 3:
            masked = "*" + self.full_serial[-3:]
        else:
            masked = self.full_serial  # слишком короткий серийник показываем как есть
        self.setText("S/N: " + masked)

    def enterEvent(self, event):  # type: ignore[override]
        if self.full_serial:
            self.tooltip.show_at(f"S/N: {self.full_serial}", event.globalPos() + QPoint(10, 10))
        super().enterEvent(event)

    def leaveEvent(self, event):  # type: ignore[override]
        self.tooltip.hide()
        super().leaveEvent(event)




class mCheckBox(QCheckBox):
    def __init__(self, idx: int) -> None:
        super().__init__()
        self.setFixedSize(20, 20)
        self.setChecked(idx != 0)
        self.setStyleSheet("text-align: end;")


class mMark(QLabel):
    def __init__(self, color: str) -> None:
        super().__init__()
        self.setFixedSize(15, 15)
        self.setStyleSheet(f"background-color: {color}; border-radius: 7.5px;")


# =====================
# Main application widget
# =====================
class DiskApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        VERSION = open("appversion").read()
        self.setWindowTitle("Storage-Handler v" + VERSION)
        self.setMinimumSize(850, 410)
        self.setWindowIcon(QIcon("hddc.ico"))

        # UI state containers
        self.disk_list = QListWidget()
        self.disk_labels = {
            "circle": [mMark(COLOR_RED) for _ in range(MAX_DISKS)],
            "model": [mModel(self, idx) for idx in range(MAX_DISKS)],
            "serial": [mSerial() for _ in range(MAX_DISKS)],
            "smart_data": [mSmart() for _ in range(MAX_DISKS)],
            "smart_cache": [mSmart() for _ in range(MAX_DISKS)],
            "percentage": [mPercentage() for _ in range(MAX_DISKS)],
            "checkbox": [mCheckBox(idx) for idx in range(MAX_DISKS)],
        }

        # Layout & controls
        self.main_layout = QVBoxLayout()
        self._configure_markers_info()
        self.main_layout.addWidget(self.disk_list)

        self.debug_label = QLabel("Last Action: ...")
        self.debug_label.setStyleSheet(f"color:rgb(0, 0, 0); font-size: 12px; background-color: {HL_GREY_BG}")
        self.main_layout.addWidget(self.debug_label)


        self.cleard_button = QPushButton("DP Clear DEFAULT")
        self.clearr_button = QPushButton("DP Clear RESCAN")
        self.eject_button = QPushButton("Sleep (SCSI)")
        self.victoria_open_button = QPushButton("Victoria (open)")
        self.victoria_write_button = QPushButton("Victoria (WRITE)")
        self.victoria_read_button = QPushButton("Victoria (READ)")
        self.victoria_autowr_button = QPushButton("Victoria (W-R-V)")
        self.pushsmart_button = QPushButton("Get SMART (smartctl)")
        # self.clearsmart_button = QPushButton("Clear SMART cache")

        # Wire up actions
        self.cleard_button.clicked.connect(self.clear_default)
        self.clearr_button.clicked.connect(self.clear_rescan)
        self.eject_button.clicked.connect(self.eject_device)
        self.victoria_open_button.clicked.connect(partial(self.victoria_open, 1))
        self.victoria_write_button.clicked.connect(partial(self.start_victoria_script, "W"))
        self.victoria_read_button.clicked.connect(partial(self.start_victoria_script, "R"))
        self.victoria_autowr_button.clicked.connect(self.start_victoria_autowrite)
        self.pushsmart_button.clicked.connect(self.push_smart)
        # self.clearsmart_button.clicked.connect(self.clear_smart_cache)

        clear_layout = QHBoxLayout()
        clear_layout.addWidget(self.cleard_button)
        clear_layout.addWidget(self.clearr_button)

        victoria_layout = QHBoxLayout()
        victoria_layout.addWidget(self.victoria_open_button)
        victoria_layout.addWidget(self.victoria_write_button)
        victoria_layout.addWidget(self.victoria_read_button)
        victoria_layout.addWidget(self.victoria_autowr_button)

        smart_layout = QHBoxLayout()
        smart_layout.addWidget(self.pushsmart_button)
        # smart_layout.addWidget(self.clearsmart_button)

        self.main_layout.addLayout(clear_layout)
        self.main_layout.addLayout(victoria_layout)
        self.main_layout.addLayout(smart_layout)
        self.main_layout.addWidget(self.eject_button)
        self.setLayout(self.main_layout)

        self.setStyleSheet(STYLE_APP)
        self.resize(550, 340)

        # Runtime state
        self.thread_data = ThreadData()
        self.clipboard = QApplication.clipboard()

        # Timers
        self.dtimer = QTimer(); self.dtimer.timeout.connect(self.refresh_disk_info); self.dtimer.start(POLL_INTERVAL_MS)
        self.stimer = QTimer(); self.stimer.timeout.connect(self.refresh_smart_info); self.stimer.start(POLL_INTERVAL_MS)

        # Initial fill
        self.thread_data.update()
        self.configure_disk_labels()
        self.refresh_disk_info()
        
        # Background workers
        threading.Thread(target=self.run_update_thread, daemon=True).start()
        
        self.clearing_thread: Optional[threading.Thread] = None
        self.clr_thr_timer = QTimer(); self.clr_thr_timer.timeout.connect(self.clearing_activity)
        self.scsi_sleep_thread: Optional[threading.Thread] = None
        self.sleep_thr_timer = QTimer(); self.sleep_thr_timer.timeout.connect(self.scsi_sleep_activity)
        self.smart_thread: Optional[threading.Thread] = None
        self.smart_thr_timer = QTimer(); self.smart_thr_timer.timeout.connect(self.smart_activity)
        print('bbom')
        # self.victoria_thread = Optional[threading.Thread] = None
        print('bbom')
        

        # VICTORIA WRV STATE

        self.victoria_states: dict[int, str] = {}  # ключ = номер диска, значение = "IDLE" | "WRITE" | "READ"
        self.victoria_monitor_thread: Optional[threading.Thread] = None

        
    # from datetime import datetime

    def _set_label_bg(self, label: QLabel, bg: str) -> None:
        """Аккуратно применяет фон к QLabel, не трогая цвет текста."""
        base = self.debug_label.styleSheet().rstrip("; ")
        label.setStyleSheet(f"{base}; background-color: {bg};")

    def log_action(self, action: str, processing=False) -> None:
        
    
        """Записывает последнюю операцию в debug_label с текущим временем."""


        if not processing:
            self._set_label_bg(self.debug_label, HL_GREEN_BG)
            QTimer.singleShot(1000, lambda: self._set_label_bg(self.debug_label, HL_GREY_BG))
        else:
            self._set_label_bg(self.debug_label, HL_YELLOW_BG)

        now = datetime.now().strftime("%H:%M:%S")
        # self.debug_label.setStyleSheet()
        self.debug_label.setText(f"Last Action: {action} [{now}]")

 
    # ------------- helpers -------------
    def _set_button_busy(self, btn: QPushButton) -> None:
        btn.setDisabled(True)

    def _set_button_idle(self, btn: QPushButton) -> None:
        btn.setDisabled(False)

    # ------------- external actions -------------
    def victoria_open(self, connected: int = 8) -> None:  # API preserved
        # Determine indices of actually connected/usable disks
        l = [
            i
            for i, m in enumerate(self.disk_labels["model"]) 
            if i != 0 and not m.text().split()[1].strip().startswith(("Not", "! "))
        ]

        if not os.path.exists(VICTORIA_PATH):
            options = QFileDialog.Options() | QFileDialog.ReadOnly
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Chose Victoria file",
                "",
                "Executable (*.exe);;All files (*)",
                options=options,
            )
            if file_path:
                ini_path = file_path.replace(".exe", ".ini")
                full_path = (file_path + "\n" + ini_path).replace("/", "\\")
                try:
                    if not file_path.endswith(".exe"):
                        raise ValueError("Выберите исполняемый файл (.exe).")
                    with open("victoriapath", "w") as file:
                        file.write(full_path)
                    QMessageBox.information(self, "Done", "Victoria path saved. Restart required")
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить путь: {e}")
        else:
            # Fire-and-forget start via ctypes wrapper
            threading.Thread(target=victoria_open_ctypes.victoria_run, args=(tuple(l),), daemon=True).start()

    def clearing_activity(self) -> None:
        if self.clearing_thread and not self.clearing_thread.is_alive():
            self.clr_thr_timer.stop()
            # self._set_button_idle(self.cleard_button, "DP Clear DEFAULT")

            self.log_action(action="Partition cleared")
            self._set_button_idle(self.cleard_button)
            self._set_button_idle(self.clearr_button)

    def scsi_sleep_activity(self) -> None:
        if self.scsi_sleep_thread and not self.scsi_sleep_thread.is_alive():
            self.sleep_thr_timer.stop()
            self.log_action(action="Sleep sended")
            self._set_button_idle(self.eject_button)

    def smart_activity(self) -> None:
        if self.smart_thread and not self.smart_thread.is_alive():
            self.smart_thr_timer.stop()
            self.log_action("Smart UPDATED")
            self._set_button_idle(self.pushsmart_button)

    def _configure_markers_info(self) -> None:
        widget = QWidget(); h_layout = QHBoxLayout(widget)
        marks = [
            (mMark(COLOR_GREEN), "no parts"),
            (mMark(COLOR_YELLOW), "parts"),
            (mMark(COLOR_RED), "disconnected"),
            (mMark(COLOR_GREY), "BSY"),
            (mMark(COLOR_ORANGE), "ERR"),
            (mMark(COLOR_PURPLE_SLEEP), "SLP"),
        ]
        for mark, text in marks:
            h_layout.addWidget(mark); h_layout.addWidget(QLabel(text)); h_layout.addSpacing(10)
        self.main_layout.addWidget(widget)

    def run_update_thread(self) -> None:
        while True:
            self.thread_data.update()
            time.sleep(1)

    def show_context_menu(self, lb: QLabel, idx: int = 0, pos: Optional[QPoint] = None) -> None:
        context_menu = QMenu(self)
        actions = {
            "Clear (Default)": lambda: self.clear_default(single_idx=idx),
            "Clear (Rescan)": lambda: self.clear_rescan(single_idx=idx),
            "Send sleep": lambda: threading.Thread(target=scsi_sleep_command, args=((idx,),), daemon=True).start(),
            "Copy": lambda: self.clipboard.setText(" ".join(lb.text().split()[1:]).strip()),
            "SMART": lambda: self.clipboard.setText(" ".join(lb.text().split()[1:]).strip()),
        }
        for text in actions.keys():
            context_menu.addAction(text)

        global_pos = lb.mapToGlobal(pos) if pos else lb.mapToGlobal(lb.rect().center())
        action = context_menu.exec_(global_pos)
        if action and action.text() in actions:
            actions[action.text()]()

    # ------------- UI building -------------
    def configure_disk_labels(self) -> None:
        for i in range(MAX_DISKS):
            item, widget, h_layout = QListWidgetItem(), QWidget(), QHBoxLayout()
            self.disk_labels["model"][i].setText(f"[{i}]  None")
            self.disk_labels["model"][i].setStyleSheet(f"color: {COLOR_RED};")
            self.disk_labels["smart_data"][i].setText("[sm_data]")
            self.disk_labels["smart_cache"][i].setText("[sm_cache]")
            self.disk_labels["percentage"][i].setText("-%")
            self.disk_labels["serial"][i].set_serial("...")

            for key in ("circle", "model", "serial", "smart_data", "smart_cache", "percentage", "checkbox"):
                h_layout.addWidget(self.disk_labels[key][i])

            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.setSpacing(2)  # уменьшенный интервал между элементами

            widget.setLayout(h_layout)
            item.setSizeHint(widget.sizeHint())
            self.disk_list.addItem(item)
            self.disk_list.setItemWidget(item, widget)


    # ------------- SMART -------------
    def reset_smart_button(self) -> None:
        self._set_button_idle(self.pushsmart_button)

    def clear_smart_cache(self) -> None:
        for i in self.disk_labels["smart_cache"]:
            i.d_reset("sm_cache")

    def push_smart(self) -> None:
        selected_indices = self.gather_indices()
        if not selected_indices:
            return  # ничего не выбрано

        self._set_button_busy(self.pushsmart_button)
        self.smart_thread = threading.Thread(
            target=self._do_smart_job,
            args=(selected_indices,),
            daemon=True,
        )
        self.smart_thread.start()
        self.smart_thr_timer.start(200)
        self.log_action(f"Smart request for {selected_indices}", processing=True)

    def _do_smart_job(self, indices: List[int]) -> None:
        smarts = smart_check.get_short_smarts(indices)
        self.thread_data.smart_queue.put(smarts)

    # def smart_activity(self) -> None:
    #     if self.smart_thread and not self.smart_thread.is_alive():
    #         self.smart_thr_timer.stop()
    #         self.log_action("Smart UPDATED")
    #         self._set_button_idle(self.pushsmart_button)


    def refresh_smart_info(self) -> None:
        try:
            short_sm, complex_sm = self.thread_data.smart_queue.get_nowait()
        except queue.Empty:
            return

        for (i, inf), (i2, inf2) in zip(short_sm, complex_sm):
            # Maintain cache
            curr_smart = self.disk_labels["smart_data"][i].text()
            if curr_smart not in (inf, "[sm_data]"):
                self.disk_labels["smart_cache"][i].setText(curr_smart)
                self.disk_labels["smart_cache"][i].smart_complex += curr_smart + "\n"
                self.disk_labels["smart_cache"][i].set_color(COLOR_CACHE_TEXT)

            if inf == "!timeout":
                self.disk_labels["smart_data"][i].setStyleSheet("color: #E087CA;")
                self.disk_labels["smart_data"][i].setText(inf)
                continue

            if inf:
                self.disk_labels["smart_data"][i].setText(inf)
                self.disk_labels["smart_data"][i].d_update(inf2)
                if inf.startswith("wu"):
                    no_errors = inf.replace("wu", "_").replace("ru", "_") == "_0_0"
                    self.disk_labels["smart_data"][i].setStyleSheet(f"color: {COLOR_WHITE if no_errors else COLOR_YELLOW};")
                    if "malfunction" in inf2:
                        self.disk_labels["smart_data"][i].setStyleSheet(f"color: {COLOR_ERROR};")
                    continue
                if "lf" in inf:
                    self.disk_labels["smart_data"][i].setStyleSheet(f"color: {COLOR_WHITE};")
                    continue
                self.disk_labels["smart_data"][i].setStyleSheet(f"color: {COLOR_OK};")
                if any(d.isdigit() and int(d) > 0 for d in inf):
                    self.disk_labels["smart_data"][i].setStyleSheet(f"color: {COLOR_WARN};")

    # ------------- Disk state -------------
    def refresh_disk_info(self) -> None:
        if not self.thread_data.is_refresh_require:
            return
        try:
            disk_info = self.thread_data.disks_queue.get_nowait()
        except queue.Empty:
            return

        for i, model, serial, p_info, is_sleep, percentage in disk_info:
            # Color/state rules mirror original logic
            if is_sleep == "IO":
                model = model + " (I/O)"; cclr = COLOR_IO
            elif is_sleep == "CONFLICT":
                model = model + " (process conflict)"; cclr = COLOR_ORANGE
            elif p_info in {"UL", "NL", "NC"} and model in {"Not connected", "! Disconnected !"} and is_sleep is False:
                cclr = COLOR_RED
                self.disk_labels["smart_data"][i].d_reset(msg="sm_data")
                self.disk_labels["smart_cache"][i].d_reset(msg="sm_cache")
            elif p_info == "EL" and not is_sleep:
                cclr = COLOR_YELLOW
            elif p_info == "NL" and not is_sleep:
                cclr = COLOR_GREEN
            elif p_info in {"CRC", "IO", "OUT"}:
                model = model + f" ({p_info})"; cclr = COLOR_ORANGE
            elif is_sleep is True:
                cclr = COLOR_PURPLE_SLEEP
            else:
                cclr = COLOR_GREY

            if serial.startswith("0000"):
                serial = "..."

            if percentage:
                self.disk_labels["percentage"][i].setText(f"{percentage}%")

            self.disk_labels["circle"][i].setStyleSheet(f"background-color: {cclr}; border-radius: 7.5px;")
            self.disk_labels["model"][i].setText(f"[{i}]  " + model)
            clr_m = COLOR_RED if model == "Not connected" else COLOR_PRIMARY
            self.disk_labels["model"][i].setStyleSheet(f"color: {clr_m};")
            self.disk_labels["serial"][i].set_serial(serial.strip())

    # ------------- Selection helpers -------------
    def gather_indices(self) -> Optional[List[int]]:
        selected_indices: List[int] = [i for i, cb in enumerate(self.disk_labels["checkbox"]) if cb.isChecked()]
        return selected_indices if selected_indices else None

    # ------------- Victoria scripts -------------
    def start_victoria_script(self, method: str, single_drive=0) -> None:

        # if single_drive:
        #     selected_indices = [single_drive, ]
        # else:
        selected_indices = self.gather_indices()



        if selected_indices:
            selected_indices.append(method)  # API/behavior preserved
            threading.Thread(
                target=cycle_victoria_script,
                args=(selected_indices,),
                daemon=True,
            ).start()
            # self.victoria_state = "WRITE"
            

    
    def start_victoria_autowrite(self) -> None:

        self.log_action(f"Started autowrite")

        selected_indices = self.gather_indices()
        if not selected_indices:
            return

        
        # for idx in selected_indices:
        for i in selected_indices: 
            if "Not connected" in self.disk_labels["model"][i].text():
                print('no disk in', i)
                continue
            self.victoria_states[i] = "WRITE"
            threading.Thread(
                target=self._monitor_single_drive,
                args=(i,),
                daemon=True,
            ).start()
        # self.victoria_states[idx] = "WRITE"
        # self.log_action(f"Victoria WRITE started for [{selected_indices}]")
        self.start_victoria_script("W")

        # print(f"Started autowrite for: {idx}")
        
    
    def _get_current_percentage(self, drive_idx):
        text = self.disk_labels["percentage"][drive_idx].text()
        if text.endswith("%"):
            try:
                value = float(text.replace("%", ""))
            except ValueError:
                value = 0
            
            return value

    def _monitor_single_drive(self, drive_idx: int) -> None:
        # def _monitor_single_drive(self, drive_idx: int) -> None:
        while self.victoria_states.get(drive_idx) == "WRITE":
            
            perc_value = self._get_current_percentage(drive_idx)

            if perc_value >= 100.0:
                time.sleep(5)
                self.disk_labels["percentage"][drive_idx].setText("-%")
                # переключаем этот диск в READ
                self.victoria_states[drive_idx] = "READ"
                print(f"Started autoread for {drive_idx}")
                # self.log_action(f"Victoria READ started for [{drive_idx}]")
                singlerun_victoria_script("R", drive_id=drive_idx)
                
                break
            time.sleep(1)

        while self.victoria_states.get(drive_idx) == "READ":

            perc_value = self._get_current_percentage(drive_idx)

            if perc_value >= 100.0:
                time.sleep(5)
                # переключаем этот диск в READ
                self.victoria_states[drive_idx] = "VERIFY"
                print(f"Started autoread for {drive_idx}")
                # self.log_action(f"Victoria Verify started for [{drive_idx}]")
                singlerun_victoria_script("V", drive_id=drive_idx)
                break
            time.sleep(1)

        
    # ------------- SCSI sleep / Eject -------------
    def eject_device(self) -> None:
        selected_indices = self.gather_indices()
        if selected_indices:
            self.scsi_sleep_thread = threading.Thread(
                target=scsi_sleep_command, args=(selected_indices,), daemon=True
            )
            self.scsi_sleep_thread.start()
            self.sleep_thr_timer.start(200)
            self.log_action(action=f"Sending sleep {selected_indices}", processing=True)
            self._set_button_busy(self.eject_button)

    # ------------- Clear partitions -------------
    def clear_rescan(self, single_idx: bool | int = False) -> None:
        selected_indices: Optional[Sequence[int]] = self.gather_indices()
        if isinstance(single_idx, int) and single_idx in range(MAX_DISKS):
            selected_indices = (single_idx,)
        if selected_indices:
            self.clearing_thread = threading.Thread(
                target=du.delete_disk_partitions,
                args=(selected_indices, True),
                daemon=True,
            )
            self.clearing_thread.start()
            self.clr_thr_timer.start(200)
            self._set_button_busy(self.clearr_button)
            self.cleard_button.setDisabled(True)

    def clear_default(self, single_idx: bool | int = False) -> None:
        selected_indices: Optional[Sequence[int]] = self.gather_indices()
        if isinstance(single_idx, int) and single_idx in range(1, MAX_DISKS):
            selected_indices = (single_idx,)
        if selected_indices:
            self.clearing_thread = threading.Thread(
                target=du.delete_disk_partitions,
                args=(selected_indices, False),
                daemon=True,
            )
            self.clearing_thread.start()
            self.clr_thr_timer.start(200)
            self.log_action(action=f"Clearing {selected_indices}", processing=True)
            self._set_button_busy(self.cleard_button)
            self._set_button_busy(self.clearr_button)
            # self.clearr_button.setDisabled(True)


# # =====================
# # Entrypoint
# # =====================
# if __name__ == "__main__":
    
