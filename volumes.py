import ctypes
import ctypes.wintypes as wintypes
import os

# Определяем константы
GENERIC_WRITE = 0x40000000
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
IOCTL_DISK_DELETE_DRIVE_LAYOUT = 0x0000042E  # Управляющий код

# Загрузка функций из библиотеки kernel32
kernel32 = ctypes.windll.kernel32

def open_disk_by_index(disk_index):
    """Открытие диска по индексу для управления."""
    device_path = f"\\\\.\\PhysicalDrive{disk_index}"
    handle = kernel32.CreateFileW(
        device_path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )
    
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError()
    return handle

def delete_drive_layout(disk_index):
    """Удаление разметки диска с помощью IOCTL_DISK_DELETE_DRIVE_LAYOUT."""
    handle = open_disk_by_index(disk_index)
    bytes_returned = wintypes.DWORD(0)
    
    try:
        result = kernel32.DeviceIoControl(
            handle,
            IOCTL_DISK_DELETE_DRIVE_LAYOUT,
            None,
            0,
            None,
            0,
            ctypes.byref(bytes_returned),
            None
        )
        if not result:
            raise ctypes.WinError()
        print(f"Разделы на диске {disk_index} успешно удалены.")
    except ctypes.WinError as e:
        if e.winerror == 5:  # Ошибка доступа
            print("Ошибка доступа (winerror 5). Запустите скрипт с правами администратора.")
        else:
            print(f"Ошибка: {e}")
    finally:
        kernel32.CloseHandle(handle)

# Пример вызова функции
disk_index = 1  # Индекс целевого диска
delete_drive_layout(disk_index)