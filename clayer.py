import ctypes
from ctypes import wintypes, byref, Structure

# Определения констант
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 0x00000003
IOCTL_STORAGE_QUERY_PROPERTY = 0x2D1400

# Определение структуры для запроса свойств хранения
class STORAGE_PROPERTY_QUERY(Structure):
    _fields_ = [
        ("PropertyId", wintypes.DWORD),
        ("QueryType", wintypes.DWORD),
        ("AdditionalParameters", wintypes.BYTE * 1)
    ]

# Структура для получения данных о модели и серийнике диска
class STORAGE_DEVICE_DESCRIPTOR(Structure):
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
        print(f"Failed to open disk {disk_index}. Error: {ctypes.get_last_error()}")
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

    return model, serial