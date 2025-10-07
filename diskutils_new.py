import ctypes
from ctypes import wintypes, byref
import queue
import subprocess

# ------------ Константы ------------
GENERIC_READ  = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ  = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 0x00000003
FILE_READ_DATA = 0x0001

IOCTL_STORAGE_QUERY_PROPERTY   = 0x002D1400
IOCTL_DISK_DELETE_DRIVE_LAYOUT = 0x0007C0CC
IOCTL_DISK_GET_DRIVE_LAYOUT_EX = 0x00070050
IOCTL_STORAGE_EJECT_MEDIA      = 0x002D4808  # Остановка шпинделя

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# Win32 error codes we handle explicitly

DISK_ERRORS = {
    "OK": 0,
    "INVALID_FUNCTION": 1,
    "CRC": 23,
    "NOT_READY": 21,
    "BAD_CMD": 22,
    "GEN_FAIL": 31,
    "IO": 1117,
    "SM_TIMEOUT": 121,
    "DENIED": 5,
    "OUT": 55
}

SEM_ERROS = ("OK",
    "INVALID_FUNCTION",
    "CRC",
    "NOT_READY",
    "BAD_CMD",
    "GEN_FAIL",
    "IO",
    "SM_TIMEOUT",
    "DENIED",
    "OUT")

# SEM_ERROS = DISK_ERRORS.keys()

# ERROR_INVALID_FUNCTION = 1
# ERROR_CRC              = 23
# ERROR_NOT_READY        = 21
# ERROR_BAD_COMMAND      = 22
# ERROR_GEN_FAILURE      = 31
# ERROR_IO_DEVICE        = 1117
# ERROR_SEM_TIMEOUT      = 121
# ERROR_ACCESS_DENIED    = 5
# ERROR_DEV_NOT_EXIST    = 55

# ------------ Очередь обновлений ------------
update_queue = queue.Queue()

# ------------ Структуры ------------
class STORAGE_PROPERTY_QUERY(ctypes.Structure):
    _fields_ = [
        ("PropertyId", wintypes.DWORD),
        ("QueryType", wintypes.DWORD),
        ("AdditionalParameters", wintypes.BYTE * 1),
    ]

class STORAGE_DEVICE_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.DWORD),
        ("Size", wintypes.DWORD),
        ("DeviceType", wintypes.BYTE),
        ("DeviceTypeModifier", wintypes.BYTE),
        ("RemovableMedia", wintypes.BOOLEAN),
        ("CommandQueueing", wintypes.BOOLEAN),
        ("VendorIdOffset", wintypes.DWORD),
        ("ProductIdOffset", wintypes.DWORD),
        ("ProductRevisionOffset", wintypes.DWORD),
        ("SerialNumberOffset", wintypes.DWORD),
        ("BusType", wintypes.DWORD),
        ("RawPropertiesLength", wintypes.DWORD),
        ("RawDeviceProperties", wintypes.BYTE * 1),
    ]

class PARTITION_INFORMATION_EX(ctypes.Structure):
    _fields_ = [
        ("PartitionStyle", wintypes.DWORD),
        ("StartingOffset", ctypes.c_int64),
        ("PartitionLength", ctypes.c_int64),
        ("PartitionNumber", wintypes.DWORD),
        ("RewritePartition", wintypes.BOOL),
        ("PartitionType", ctypes.c_byte * 16),
        ("BootIndicator", wintypes.BOOL),
        ("RecognizedPartition", wintypes.BOOL),
        ("HiddenSectors", wintypes.DWORD),
        ("PartitionId", ctypes.c_byte * 16),
    ]

class DRIVE_LAYOUT_INFORMATION_EX(ctypes.Structure):
    _fields_ = [
        ("PartitionStyle", wintypes.DWORD),
        ("PartitionCount", wintypes.DWORD),
        ("DriveLayoutInformation", ctypes.c_byte * 16),
        ("PartitionEntry", PARTITION_INFORMATION_EX * 128),
    ]

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
cfgmgr32 = ctypes.WinDLL('cfgmgr32', use_last_error=True)

# ------------ Хэлперы ------------
def map_last_error_to_tag(code: int) -> str:
    """Маппинг кодов Win32 в короткие теги без исключений."""
    # print(DISK_ERRORS.values())
    # print(DISK_ERRORS.items())
    # exit(0)
    for err, i in DISK_ERRORS.items():
        if code == i:
            return err
    
    return f"ERR_{code}"

def close_handle_safe(h):
    if h and h != INVALID_HANDLE_VALUE:
        kernel32.CloseHandle(h)

# ------------ Базовые операции ------------
def open_disk(disk_index):
    device_path = f"\\\\.\\PhysicalDrive{disk_index}"
    handle = kernel32.CreateFileW(
        device_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )
    if handle == INVALID_HANDLE_VALUE:
        # Возвращаем None и тэг ошибки
        err = ctypes.get_last_error()
        return None, map_last_error_to_tag(err)
    return handle, 'OK'

def device_io_control(handle, code, in_buf, in_size, out_buf, out_size):
    bytes_returned = wintypes.DWORD(0)
    ok = kernel32.DeviceIoControl(
        handle,
        code,
        in_buf,
        in_size,
        out_buf,
        out_size,
        byref(bytes_returned),
        None
    )
    if not ok:
        # print('lllss')
        return False, map_last_error_to_tag(ctypes.get_last_error())
    return True, 'OK'

# ------------ Функции устройства ------------
def eject_device(drive_index):
    """Пытается «безопасно» отключить устройство через cfgmgr32. Возврат: (True, 'OK') или (False, '<TAG>')."""
    device_instance_id = f"\\\\.\\PhysicalDrive{drive_index}"
    device_instance_id_buffer = ctypes.create_unicode_buffer(device_instance_id)

    result = cfgmgr32.CM_Request_Device_EjectW(
        device_instance_id_buffer,
        None,
        None,
        0,
        0
    )
    # CM_* ошибки не равны Win32, но для простоты пробуем перевести в общий тег
    if result == 0:
        return True, 'OK'
    # вернём обобщённый тэг с кодом CM_
    return False, f'CM_ERR_{result}'

def get_disk_info(disk_index):
    """
    Возвращает:
      - (disk_index, model, serial, partition_info) при успехе;
      - строковый код ошибки ('IO', 'CRC', 'INV_FUNC', 'NOT_READY', 'TIMEOUT', 'GEN_FAIL', 'BAD_CMD', 'OUT', 'ERR_<n>') при неудаче.
    """
    handle, tag = open_disk(disk_index)
    if not handle:
        return tag  # Например 'IO' или 'ERR_5' (доступ запрещён)

    # Запрос дескриптора устройства
    query = STORAGE_PROPERTY_QUERY()
    query.PropertyId = 0  # StorageDeviceProperty
    query.QueryType  = 0  # PropertyStandardQuery

    descriptor_size = ctypes.sizeof(STORAGE_DEVICE_DESCRIPTOR) + 512  # запас
    buffer = ctypes.create_string_buffer(descriptor_size)

    ok, tag = device_io_control(
        handle,
        IOCTL_STORAGE_QUERY_PROPERTY,
        byref(query),
        ctypes.sizeof(query),
        buffer,
        descriptor_size
    )
    close_handle_safe(handle)

    if not ok:
        # если есть конкретный тэг — вернём его (раньше всегда был 'OUT')
        return tag if tag != 'OK' else 'OUT'

    # Разбор модели/серийника
    descriptor = STORAGE_DEVICE_DESCRIPTOR.from_buffer_copy(buffer)
    model = ""
    serial = ""

    if descriptor.ProductIdOffset:
        model = buffer[descriptor.ProductIdOffset:].split(b'\x00', 1)[0].decode(errors='ignore').strip()
    if descriptor.SerialNumberOffset:
        serial = buffer[descriptor.SerialNumberOffset:].split(b'\x00', 1)[0].decode(errors='ignore').strip()

    # Пытаемся получить инфу о разделах
    partition_info = get_partition_count(disk_index)  # уже «мягкая» функция
    return disk_index, model, serial, partition_info

def get_partition_count(disk_number):
    """
    Возвращает:
      'EL' (есть разделы) | 'NL' (нет разделов) | 'UL' (handle не получен) | '<TAG>' (ошибка Win32).
    """
    path = f"\\\\.\\PhysicalDrive{disk_number}"
    handle = kernel32.CreateFileW(
        path,
        FILE_READ_DATA,
        0,              # без шаринга — как было
        None,
        OPEN_EXISTING,
        0,
        None
    )

    if handle == INVALID_HANDLE_VALUE:
        err = ctypes.get_last_error()
        # Старая семантика: 'UL' — недоступен (handle не открыт). Если хотите — можно вернуть точный TAG.
        # Я верну 'UL' для совместимости, НО если нужен точный код — раскомментируйте строку ниже:
        # return map_last_error_to_tag(err)
        return 'UL'

    layout = DRIVE_LAYOUT_INFORMATION_EX()
    ok, tag = device_io_control(
        handle,
        IOCTL_DISK_GET_DRIVE_LAYOUT_EX,
        None,
        0,
        byref(layout),
        ctypes.sizeof(layout)
    )
    close_handle_safe(handle)

    if not ok:
        # Точное кодирование ошибки вместо исключения
        return tag

    # Нормальный разбор
    if layout.PartitionCount > 0:
        return 'EL'
    else:
        return 'NL'

def delete_disk_partitions(disk_index, rescan):
    """
    Безопасная очистка через diskpart (как у вас).
    Возврат: 'OK' (не проверяем вывод diskpart) — оставлено как было.
    """
    rescan_command = 'RESCAN' if rescan else ''
    commands = '\n'.join([f"""
        sel dis {i}
        {rescan_command}
        online dis
        clean
        """ for i in disk_index])

    process = subprocess.Popen(
        ["diskpart"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True
    )
    process.communicate(commands)
    return 'OK'
