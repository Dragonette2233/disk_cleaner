import os
import subprocess
import time
import ctypes
from ctypes import wintypes
import psutil
import win32gui

# Путь к программе Victoria
VICTORIA_PATH = r"C:\\Users\\DSP\\Desktop\\Victoria537\\Victoria.exe"
CONFIG_PATH = r"C:\\Users\\DSP\\Desktop\\Victoria537\\Victoria.ini"

# Определение ctypes функций Windows API
user32 = ctypes.WinDLL('user32', use_last_error=True)

HWND = wintypes.HWND
DWORD = wintypes.DWORD
BOOL = wintypes.BOOL
LPVOID = wintypes.LPVOID
LONG = ctypes.c_long
LPWSTR = wintypes.LPWSTR

user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(BOOL, HWND, LPVOID), LPVOID]
user32.EnumWindows.restype = BOOL
user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
user32.GetWindowThreadProcessId.restype = DWORD
user32.IsWindowVisible.argtypes = [HWND]
user32.IsWindowVisible.restype = BOOL
user32.GetWindowTextW.argtypes = [HWND, LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.MoveWindow.argtypes = [HWND, LONG, LONG, LONG, LONG, BOOL]
user32.MoveWindow.restype = BOOL

# Функция для получения заголовка окна
def get_window_title(hwnd):
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buffer, 512)
    return buffer.value

# Функция для получения окна по PID и заголовку
def get_window_by_pid_and_title(pid, expected_title="Victoria"):
    found_hwnd = ctypes.c_void_p()  # Указатель для хранения найденного HWND

    @ctypes.WINFUNCTYPE(BOOL, HWND, LPVOID)
    def callback(hwnd, lParam):
        # Получение PID окна
        wnd_pid = DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wnd_pid))
        # Проверка PID, видимости окна и заголовка
        if (
            wnd_pid.value == pid
            and user32.IsWindowVisible(hwnd)
            and expected_title.lower() in get_window_title(hwnd).lower()
        ):
            found_hwnd.value = hwnd
            return False  # Прерываем обход, если окно найдено
        return True

    # print('s')
    user32.EnumWindows(callback, None)
    return found_hwnd.value if found_hwnd.value else None

def update_last_api_device(value):
    # Читаем содержимое файла
    with open(CONFIG_PATH, 'r') as file:
        lines = file.readlines()

    # Перебираем строки и ищем строку с Last API device
    for i, line in enumerate(lines):
        if line.strip().startswith("Last API device"):
            # Меняем значение Last API device
            lines[i] = f"Last API device={value}\n"
            break

    # Записываем обратно в файл
    with open(CONFIG_PATH, 'w') as file:
        file.writelines(lines)

def count_of_victoria_wins():
    count = 0
    def callback(hwnd, strings):
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd)
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            if window_title and right-left and bottom-top:
                strings.append('0x{:08x}: "{}"'.format(hwnd, window_title))
        return True
    win_list = []  # list of strings containing win handles and window titles
    win32gui.EnumWindows(callback, win_list)  # populate list

    for window in win_list:  # print results
        if window.split('"')[1].startswith(" Victoria 5.37 HDD/SSD"):
            count += 1

    return count

def victoria_run():
    # Проверка существования программы
    if not os.path.exists(VICTORIA_PATH):
        raise FileNotFoundError(f"Программа не найдена по пути: {VICTORIA_PATH}")

    # Открытие 8 экземпляров программы
    processes = []
    for i in range(1, 9):
        update_last_api_device(i)
        proc = subprocess.Popen(VICTORIA_PATH)
        while count_of_victoria_wins() < i:
            time.sleep(0.1)
        processes.append(proc)
        time.sleep(1)  # Небольшая задержка для запуска экземпляра


        # Начальные координаты и шаг
    START_X, START_Y = 50, 25
    STEP_X, STEP_Y = 24, 71

    time.sleep(2)
    update_last_api_device(1)
    # Перемещение окон
    for i, proc in enumerate(processes):
        hwnd = None
        for _ in range(20):  # Попытка найти окно
            hwnd = get_window_by_pid_and_title(proc.pid)
            if hwnd:
                break
            time.sleep(0.1)

        if hwnd:
            x = START_X + STEP_X * i
            y = START_Y + STEP_Y * i
            width, height = 800, 600  # Размер окна
            success = user32.MoveWindow(hwnd, x, y, width, height, True)
            if not success:
                print(f"Не удалось переместить окно PID {proc.pid}, HWND {hwnd}")
        else:
            print(f"Окно не найдено для процесса PID {proc.pid}")



# print("Все окна размещены.")
