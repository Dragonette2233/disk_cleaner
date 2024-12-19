import os
import subprocess
import time
import win32gui
import win32process
import win32con

# Путь к программе Victoria
VICTORIA_PATH = r"C:\\Users\\DSP\\Desktop\\Victoria537\\Victoria.exe"

# Проверка существования программы
if not os.path.exists(VICTORIA_PATH):
    raise FileNotFoundError(f"Программа не найдена по пути: {VICTORIA_PATH}")

# Открытие 8 экземпляров программы
processes = []
for _ in range(3):
    proc = subprocess.Popen(VICTORIA_PATH)
    processes.append(proc)
    time.sleep(1)  # Небольшая задержка для запуска экземпляра

# Функция для получения окна по PID и заголовку
def get_window_by_pid_and_title(pid, expected_title="Victoria"):
    def callback(hwnd, hwnd_pid):
        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        # Проверяем PID, видимость окна и его заголовок
        if (
            found_pid == pid 
            and win32gui.IsWindowVisible(hwnd)
            and expected_title.lower() in win32gui.GetWindowText(hwnd).lower()
        ):
            hwnd_pid.append(hwnd)
        return True

    hwnd_pid = []
    win32gui.EnumWindows(callback, hwnd_pid)
    return hwnd_pid[0] if hwnd_pid else None

# Начальные координаты и шаг
START_X, START_Y = 100, 100
STEP_X, STEP_Y = 50, 50

time.sleep(4)

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
        win32gui.MoveWindow(hwnd, x, y, width, height, True)
    else:
        print(f"Не удалось найти окно для процесса PID {proc.pid}")

print("Все окна размещены.")
