import ctypes
from ctypes import wintypes

# Константы Windows API
GENERIC_WRITE = 0x40000000
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
SECTOR_SIZE = 1024  # Размер сектора (обычно 512 байт)

# Загрузка API
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CreateFile = kernel32.CreateFileW
CreateFile.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
CreateFile.restype = wintypes.HANDLE

WriteFile = kernel32.WriteFile
WriteFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
WriteFile.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


def clear_partitions(drive_number):
    drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
    
    # Открытие диска
    handle = CreateFile(
        drive_path,
        GENERIC_WRITE,
        FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error(), f"Не удалось открыть диск {drive_path}")

    try:
        # Подготовка буфера нулей
        mbr_buffer = (ctypes.c_ubyte * SECTOR_SIZE)()  # Для MBR: 1 сектор
        gpt_buffer = (ctypes.c_ubyte * (SECTOR_SIZE * 34))()  # Для GPT: 34 сектора
        bytes_written = wintypes.DWORD()

        # Обнуление MBR (LBA 0)
        print("Обнуление MBR...")
        success = WriteFile(
            handle,
            ctypes.byref(mbr_buffer),
            SECTOR_SIZE,
            ctypes.byref(bytes_written),
            None,
        )
        if not success:
            raise ctypes.WinError(ctypes.get_last_error(), "Ошибка записи в MBR")
        print("MBR успешно очищен.")

        # Обнуление GPT (LBA 0–33)
        print("Обнуление GPT...")
        success = WriteFile(
            handle,
            ctypes.byref(gpt_buffer),
            SECTOR_SIZE * 34,
            ctypes.byref(bytes_written),
            None,
        )
        if not success:
            raise ctypes.WinError(ctypes.get_last_error(), "Ошибка записи в GPT")
        print("GPT успешно очищен.")
    finally:
        CloseHandle(handle)


# Использование
drive_number = 2  # Номер диска
try:
    clear_partitions(drive_number)
except Exception as e:
    print(f"Ошибка: {e}")