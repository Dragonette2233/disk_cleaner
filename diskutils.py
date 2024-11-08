import ctypes
from ctypes import wintypes, byref

# Определения констант
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 0x00000003
IOCTL_STORAGE_QUERY_PROPERTY = 0x2D1400
IOCTL_DISK_DELETE_DRIVE_LAYOUT = 0x0007C0CC
IOCTL_DISK_GET_DRIVE_LAYOUT_EX = 0x00070050
FILE_READ_DATA = 0x0001
OPEN_EXISTING = 3

# Определение структуры для запроса свойств хранения
class STORAGE_PROPERTY_QUERY(ctypes.Structure):
    _fields_ = [
        ("PropertyId", wintypes.DWORD),
        ("QueryType", wintypes.DWORD),
        ("AdditionalParameters", wintypes.BYTE * 1)
    ]

# Структура для получения данных о модели и серийнике диска
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
        ("RawDeviceProperties", wintypes.BYTE * 1)
    ]



# Определение структур
class PARTITION_INFORMATION_EX(ctypes.Structure):
    _fields_ = [
        ("PartitionStyle", wintypes.DWORD),
        ("StartingOffset", ctypes.c_int64),
        ("PartitionLength", ctypes.c_int64),
        ("PartitionNumber", wintypes.DWORD),
        ("RewritePartition", wintypes.BOOL),
        ("PartitionType", ctypes.c_byte * 16),  # Тип GUID для GPT или тип раздела для MBR
        ("BootIndicator", wintypes.BOOL),
        ("RecognizedPartition", wintypes.BOOL),
        ("HiddenSectors", wintypes.DWORD),
        ("PartitionId", ctypes.c_byte * 16)  # Только для GPT, идентификатор раздела
    ]

class DRIVE_LAYOUT_INFORMATION_EX(ctypes.Structure):
    _fields_ = [
        ("PartitionStyle", wintypes.DWORD),
        ("PartitionCount", wintypes.DWORD),
        ("DriveLayoutInformation", ctypes.c_byte * 16),  # Дополнительные данные для стиля
        ("PartitionEntry", PARTITION_INFORMATION_EX * 128)  # Массив для хранения информации о разделах
    ]

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Функция для открытия диска
def open_disk(disk_index):
    device_path = f"\\\\.\\PhysicalDrive{disk_index}"
    return kernel32.CreateFileW(
        device_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )

# Функция для получения модели диска и серийного номера
def get_disk_info(disk_index):
    handle = open_disk(disk_index)
    if handle == -1:
        # error 5 - access denied
        # print(f"Failed to open disk {disk_index}. Error: {ctypes.get_last_error()}")
        return None

    query = STORAGE_PROPERTY_QUERY()
    query.PropertyId = 0  # StorageDeviceProperty
    query.QueryType = 0   # PropertyStandardQuery

    descriptor = STORAGE_DEVICE_DESCRIPTOR()
    descriptor_size = ctypes.sizeof(STORAGE_DEVICE_DESCRIPTOR) + 512  # Дополнительный буфер

    buffer = ctypes.create_string_buffer(descriptor_size)
    bytes_returned = wintypes.DWORD(0)

    result = kernel32.DeviceIoControl(
        handle,
        IOCTL_STORAGE_QUERY_PROPERTY,
        byref(query),
        ctypes.sizeof(query),
        buffer,
        descriptor_size,
        byref(bytes_returned),
        None
    )

    kernel32.CloseHandle(handle)

    if not result:
        print(f"Failed to get disk info for disk {disk_index}. Error: {ctypes.get_last_error()}")
        return None

    # Извлекаем информацию о модели и серийнике из буфера
    descriptor = STORAGE_DEVICE_DESCRIPTOR.from_buffer_copy(buffer)
    model = ""
    serial = ""

    if descriptor.ProductIdOffset:
        model = buffer[descriptor.ProductIdOffset:].split(b'\x00', 1)[0].decode()
    if descriptor.SerialNumberOffset:
        serial = buffer[descriptor.SerialNumberOffset:].split(b'\x00', 1)[0].decode()
    # print(model, serial)
    return model, serial

def get_partition_count(disk_number):
    # def get_drive_layout(disk_number):
    # Создание пути к физическому диску
    path = f"\\\\.\\PhysicalDrive{disk_number}"
    handle = ctypes.windll.kernel32.CreateFileW(
        path,
        FILE_READ_DATA,
        0,
        None,
        OPEN_EXISTING,
        0,
        None
    )
    
    if handle == -1:
        # print(handle)
        # print('hs')
        return 'UL'
            
        raise ctypes.WinError(ctypes.get_last_error())
    
    # Создаем буфер для получения данных
    layout = DRIVE_LAYOUT_INFORMATION_EX()
    bytes_returned = wintypes.DWORD()

    result = ctypes.windll.kernel32.DeviceIoControl(
        handle,
        IOCTL_DISK_GET_DRIVE_LAYOUT_EX,
        None,
        0,
        ctypes.byref(layout),
        ctypes.sizeof(layout),
        ctypes.byref(bytes_returned),
        None
    )

    ctypes.windll.kernel32.CloseHandle(handle)

    if not result:
        raise ctypes.WinError(ctypes.get_last_error())

    # Вывод информации о каждом разделе
    # print(f"Информация о диске PhysicalDrive{disk_number}:")
    if layout.PartitionCount > 0:
        return 'EL'
    else:
        return 'NL'

def delete_disk_partitions(disk_index):
    """Удаление разметки диска с помощью IOCTL_DISK_DELETE_DRIVE_LAYOUT."""
    handle = open_disk(disk_index)
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
        print(result)
        if not result:
            raise ctypes.WinError()
        print(f"Разделы на диске {disk_index} успешно удалены.")
    except OSError as e:
        if e.winerror == 5:  # Ошибка доступа
            print("Ошибка доступа (winerror 5). Запустите скрипт с правами администратора.")
        else:
            print(f"Ошибка: {e}")
    finally:
        kernel32.CloseHandle(handle)

# def delete_disk_partitions(d):
#     # def delete_disk_partitions(disk_index):
#     # print('cl')
#     # return ''
#     handle = open_disk(d)
#     try:
#         result = kernel32.DeviceIoControl(
#             handle,
#             IOCTL_DISK_DELETE_DRIVE_LAYOUT,
#             None,
#             0,
#             None,
#             0,
#             ctypes.byref(wintypes.DWORD()),
#             None
#         )
#         if not result:
#             # print(result)
#             raise ctypes.WinError(ctypes.get_last_error())
#     finally:
#         kernel32.CloseHandle(handle)

    