import ctypes
from ctypes import wintypes

# Константы
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
OPEN_EXISTING = 3
IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x4D014
SMART_RCV_DRIVE_DATA = 0x7C088  # Команда для получения SMART-данных

# Структуры
class SENDCMDINPARAMS(ctypes.Structure):
    _fields_ = [
        ("cBufferSize", wintypes.DWORD),
        ("irDriveRegs", ctypes.c_ubyte * 8),  # Регистры устройства
        ("bDriveNumber", ctypes.c_ubyte),
        ("reserved", ctypes.c_ubyte * 3),
        ("lpReserved", wintypes.LPVOID),
    ]


class DRIVERSTATUS(ctypes.Structure):
    _fields_ = [
        ("bDriverError", ctypes.c_ubyte),
        ("bIDEStatus", ctypes.c_ubyte),
        ("reserved", ctypes.c_ubyte * 2),
        ("dwReserved", wintypes.DWORD * 2),
    ]


class SENDCMDOUTPARAMS(ctypes.Structure):
    _fields_ = [
        ("cBufferSize", wintypes.DWORD),
        ("DriverStatus", DRIVERSTATUS),
        ("bBuffer", ctypes.c_ubyte * 512),  # Содержит данные SMART
    ]


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

DeviceIoControl = kernel32.DeviceIoControl
DeviceIoControl.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
DeviceIoControl.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


# Функция чтения SMART
def read_smart_attributes(drive_number):
    drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
    
    # Открытие диска
    handle = CreateFile(
        drive_path,
        GENERIC_READ,
        FILE_SHARE_READ,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error(), f"Не удалось открыть диск {drive_path}")

    try:
        # Подготовка входных параметров
        in_params = SENDCMDINPARAMS()
        in_params.cBufferSize = 512
        in_params.bDriveNumber = drive_number
        in_params.irDriveRegs[0] = 0xB0  # Команда SMART
        in_params.irDriveRegs[1] = 0xD0  # Чтение данных SMART

        # Буфер для данных
        out_params = SENDCMDOUTPARAMS()
        bytes_returned = wintypes.DWORD()

        # Отправка команды
        success = DeviceIoControl(
            handle,
            SMART_RCV_DRIVE_DATA,
            ctypes.byref(in_params),
            ctypes.sizeof(in_params),
            ctypes.byref(out_params),
            ctypes.sizeof(out_params),
            ctypes.byref(bytes_returned),
            None,
        )
        if not success:
            raise ctypes.WinError(ctypes.get_last_error(), "Ошибка выполнения DeviceIoControl")

        # Разбор SMART-атрибутов
        smart_data = bytes(out_params.bBuffer)
        attributes = {}
        for i in range(30):  # Всего 30 атрибутов SMART
            attr = smart_data[i * 12 : (i + 1) * 12]
            id = attr[0]
            value = attr[3]
            raw_value = int.from_bytes(attr[5:11], "little")
            attributes[id] = (value, raw_value)

        return {
            "Reallocated Sector Count": attributes.get(5, None),
            "Reallocation Event Count": attributes.get(196, None),
            "Current Pending Sector Count": attributes.get(197, None),
            "Seek Error Rate": attributes.get(7, None),
        }
    finally:
        CloseHandle(handle)


# Использование
drive_number = 1  # Номер диска
try:
    smart_attributes = read_smart_attributes(drive_number)
    print("SMART параметры:")
    for attr, value in smart_attributes.items():
        print(f"{attr}: {value}")
except Exception as e:
    print(f"Ошибка: {e}")