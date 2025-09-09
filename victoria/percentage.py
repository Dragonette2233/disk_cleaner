import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

# callback типы
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

# WinAPI функции
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumChildProc, wintypes.LPARAM]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL


def get_window_text(hwnd):
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def get_class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def get_percentage(i):
    """Ищет окно Victoria 5.37 и возвращает значение процента"""
    main_hwnd = None
    win_title = f"Device {i}"

    def enum_windows(hwnd, lparam):
        nonlocal main_hwnd
        title = get_window_text(hwnd)
        if win_title in title:
            main_hwnd = hwnd
            return False  # остановить перебор
        return True

    user32.EnumWindows(EnumWindowsProc(enum_windows), 0)
    if not main_hwnd:
        return None
        raise RuntimeError("Окно 'Victoria 5.37' не найдено")

    elements = []

    def enum_child(hwnd, lparam):
        cls = get_class_name(hwnd)
        text = get_window_text(hwnd)
        elements.append((hwnd, cls, text))
        return True

    user32.EnumChildWindows(main_hwnd, EnumChildProc(enum_child), 0)

    # выбираем все TStaticText
    text_list = [text for _, cls, text in elements if cls == "TStaticText"]

    if len(text_list) < 5:
        return None
    
    try:
        return float(text_list[4])  # возвращаем 5-й элемент
    except:
        return None

