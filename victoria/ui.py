import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
EnumChildProc   = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes       = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumChildWindows.argtypes  = [wintypes.HWND, EnumChildProc, wintypes.LPARAM]
user32.GetWindowTextW.argtypes    = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes     = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.argtypes   = [wintypes.HWND]

GetMenu        = user32.GetMenu
GetSubMenu     = user32.GetSubMenu
GetMenuItemID  = user32.GetMenuItemID
SendMessageW   = user32.SendMessageW
PostMessageW   = user32.PostMessageW
SetForegroundWindow = user32.SetForegroundWindow

# --- messages/keys ---
WM_COMMAND      = 0x0111
BM_GETCHECK     = 0x00F0
BM_CLICK        = 0x00F5
BST_CHECKED     = 1
WM_LBUTTONDOWN  = 0x0201
WM_LBUTTONUP    = 0x0202
WM_KEYDOWN      = 0x0100
WM_KEYUP        = 0x0101
VK_RETURN       = 0x0D

# --- helpers ---
def get_window_text(hwnd):
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value

def get_class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value

def click_menu(hwnd, main_index, sub_index=None):
    hMenu = GetMenu(hwnd)
    if not hMenu:
        print("[FAIL] Меню не найдено")
        return
    if sub_index is None:
        item_id = GetMenuItemID(hMenu, main_index)
    else:
        hSub = GetSubMenu(hMenu, main_index)
        item_id = GetMenuItemID(hSub, sub_index)
    if item_id == -1:
        print("[FAIL] Не удалось получить item_id")
        return
    SendMessageW(hwnd, WM_COMMAND, item_id, 0)
    print(f"[OK] Меню {main_index}->{sub_index if sub_index is not None else ''} (id={item_id}) нажато")

def click_hwnd_async(hwnd):
    """Асинхронный клик мышью по центру контрола"""
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    x = (rect.left + rect.right) // 2
    y = (rect.top + rect.bottom) // 2
    pt = wintypes.POINT(x, y)
    user32.ScreenToClient(hwnd, ctypes.byref(pt))
    lparam = (pt.y << 16) | (pt.x & 0xFFFF)
    PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lparam)
    PostMessageW(hwnd, WM_LBUTTONUP,   0, lparam)

def click_hwnd(hwnd):
    SendMessageW(hwnd, BM_CLICK, 0, 0)
    SendMessageW(hwnd, WM_LBUTTONDOWN, 1, 0)
    SendMessageW(hwnd, WM_LBUTTONUP, 0, 0)

def ensure_checkbox_checked(hwnd, label):
    """Убедиться, что чекбокс включён"""
    state = SendMessageW(hwnd, BM_GETCHECK, 0, 0)
    if state == BST_CHECKED:
        print(f"[OK] Чекбокс '{label}' уже активен")
        return True
    print(f"[INFO] Чекбокс '{label}' неактивен, жмём...")
    
    for _ in range(5):
        click_hwnd(hwnd)
        time.sleep(0.5)
        new_state = SendMessageW(hwnd, BM_GETCHECK, 0, 0)
        if new_state == BST_CHECKED:
            print(f"[OK] Чекбокс '{label}' теперь активен")
            return True
        

def send_enter(hwnd):
    try:
        SetForegroundWindow(hwnd)
    except:
        pass
    PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, 0)
    PostMessageW(hwnd, WM_KEYUP,   VK_RETURN, 0)

def wait_dialog_and_press_yes(owner_hwnd, timeout_ms=7000, poll_ms=100):
    """Ждём модальный диалог процесса Victoria и кликаем по кнопке 'Yes'."""
    owner_pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(owner_hwnd, ctypes.byref(owner_pid))
    deadline = time.time() + timeout_ms/1000.0
    dialog_classes = ("#32770", "TMessageForm", "Dialog")

    def is_our_dialog(hwnd):
        if not user32.IsWindowVisible(hwnd):
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != owner_pid.value:
            return False
        return get_class_name(hwnd) in dialog_classes

    def update_dialog_exist():
        dialogs = []
        def enum_top(h, lp):
            if is_our_dialog(h):
                dialogs.append(h)
            return True
        user32.EnumWindows(EnumWindowsProc(enum_top), 0)

        return dialogs

    while time.time() < deadline:
        dialogs = update_dialog_exist()

        if dialogs:
            dlg = dialogs[0]
            print(f"[OK] Найден диалог: class='{get_class_name(dlg)}' title='{get_window_text(dlg)}'")

            # ищем кнопку Yes внутри диалога
            btn_yes = None
            def enum_child(h, lp):
                nonlocal btn_yes
                if get_window_text(h).strip().lower() == "yes":
                    btn_yes = h
                    return False
                return True
            user32.EnumChildWindows(dlg, EnumChildProc(enum_child), 0)

            if btn_yes:
                print(f"[OK] Нашли кнопку 'Yes' (HWND={btn_yes}), кликаем…")
                click_hwnd_async(btn_yes)
                return True
            else:
                print("[WARN] Кнопка 'Yes' не найдена в диалоге, пробуем Enter")

                while True:
                    dialogs = update_dialog_exist()

                    if dialogs:
                        print("Попытка закрыть еще раз")
                        send_enter(dlg)
                        time.sleep(1)
                    else:
                        break
                return True
            
        time.sleep(poll_ms/1000.0)

    print("[WARN] Диалог не найден")
    return False

def cycle_victoria_script(selected_indices):
    print('cycle', selected_indices)
    for i in selected_indices[:-1]:
        run_victoria_script(i, selected_indices[-1])

def run_victoria_script(drive_id: int, method: str):

    if method == 'W':
        targets = [
            ("TRzBitBtn","Stop"),
            ("TRzGroupButton","Write"),
            ("TRzCheckBox","DDD (API)"),
            ("TRzBitBtn","Scan"),
        ]
    elif method == 'R':
        targets = [
            ("TRzGroupButton","Read"),
            ("TRzBitBtn","Scan"),
        ]
    elif method == 'V':
        targets = [
            ("TRzGroupButton","Verify"),
            ("TRzBitBtn","Scan"),
        ]

    """Запускает сценарий на окне Victoria для указанного диска."""
    window_title = f"Victoria 5.37 HDD/SSD | Device {drive_id}"

    # --- ищем окно Victoria ---
    main_hwnd = None
    def enum_windows(hwnd, lparam):
        nonlocal main_hwnd
        if window_title in get_window_text(hwnd):
            main_hwnd = hwnd
            return False
        return True

    user32.EnumWindows(EnumWindowsProc(enum_windows), 0)
    if not main_hwnd:
        return None
        #  SystemExit(f"Окно '{window_title}' не найдено")
    print("Нашли окно:", get_window_text(main_hwnd))

    # --- перечисление дочерних контролов ---
    elements = []
    def refresh_elements():
        nonlocal elements
        elements = []
        def enum_child(hwnd, lparam):
            elements.append((hwnd, get_class_name(hwnd), get_window_text(hwnd)))
            return True
        user32.EnumChildWindows(main_hwnd, EnumChildProc(enum_child), 0)

    def find_control(cls, text=None):
        for h, c, t in elements:
            if c == cls and (text is None or t.strip() == text):
                return h
        return None

    # --- сценарий ---
    if method not in ('V', 'R'):
        click_menu(main_hwnd, main_index=2, sub_index=0)  # Service -> Tests
        time.sleep(1)

    
    # scan_hwnd = find_control("TRzBitBtn", "Scan")
    if method != "W":
        while not find_control("TRzBitBtn", "Scan"):
            refresh_elements()
            print("Waiting for scan button")
            time.sleep(2)

    for cls, text in targets:
        refresh_elements()
        hwnd = find_control(cls, text)
        if not hwnd:
            print(f"[FAIL] Не найдено: {cls} | '{text}'")
            continue

        if cls == "TRzCheckBox":
            ensure_checkbox_checked(hwnd, text)
        else:
            print(f"[OK] Жмём {cls} | '{text}'")
            click_hwnd_async(hwnd)
            if text == "Scan" and method == 'W':
                time.sleep(1)
                wait_dialog_and_press_yes(main_hwnd, timeout_ms=10000, poll_ms=100)
        time.sleep(0.5)
