import ctypes
from ctypes import wintypes, byref
import subprocess

# Определения констант
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 0x00000003
IOCTL_STORAGE_QUERY_PROPERTY = 0x2D1400
IOCTL_DISK_DELETE_DRIVE_LAYOUT = 0x0007C0CC
IOCTL_DISK_GET_DRIVE_LAYOUT_EX = 0x00070050
IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808  # Остановка шпинделя
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
cfgmgr32 = ctypes.WinDLL("cfgmgr32", use_last_error=True)

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

def stop_spindle(drive_index):
    h_device = open_disk(drive_index)
    try:
        result = kernel32.DeviceIoControl(
            h_device,
            IOCTL_STORAGE_EJECT_MEDIA,
            None,
            0,
            None,
            0,
            ctypes.byref(wintypes.DWORD(0)),
            None,
        )
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        print(f"Шпиндель устройства PhysicalDrive{drive_index} успешно остановлен.")
    finally:
        kernel32.CloseHandle(h_device)
        
def eject_device(drive_index):
    # Получаем идентификатор устройства
    device_instance_id = f"\\\\.\\PhysicalDrive{drive_index}"
    device_instance_id_buffer = ctypes.create_unicode_buffer(device_instance_id)

    # Отключаем устройство
    result = cfgmgr32.CM_Request_Device_EjectW(
        device_instance_id_buffer,
        None,  # Указатель на выходной параметр (не требуется)
        None,  # Контекст (не требуется)
        0,     # Флаги
        0      # Зарезервировано
    )
    if result == 0:
        print(f"Устройство PhysicalDrive{drive_index} успешно отключено от системы.")
    else:
        raise ctypes.WinError(result)

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

    partition_info = get_partition_count(disk_index)

    # print(model, serial)
    return disk_index, model, serial, partition_info

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
    # print(layout.PartitionCount)
    # print(layout.DriveLayoutInformation[0:])
    # print(layout.PartitionStyle)
    if layout.PartitionCount > 0:
        return 'EL'
    else:
        return 'NL'

def delete_disk_partitions(disk_index):
    
    commands = '\n'.join(
        [f"""
    sel dis {i}
    online dis
    clean
    """ for i in disk_index ]
    )
    
    process = subprocess.Popen(
        ["diskpart"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True
    )
    # Отправляем команды diskpart и получаем вывод
    process.communicate(commands)
    
 

    