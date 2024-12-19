import ctypes
from ctypes import wintypes

# Константы
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3

IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x4D014
SCSI_IOCTL_DATA_OUT = 0  # Указывает, что данные будут отправлены на устройство

# Структура SCSI_PASS_THROUGH_DIRECT
class SCSI_PASS_THROUGH_DIRECT(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("ScsiStatus", wintypes.BYTE),
        ("PathId", wintypes.BYTE),
        ("TargetId", wintypes.BYTE),
        ("Lun", wintypes.BYTE),
        ("CdbLength", wintypes.BYTE),
        ("SenseInfoLength", wintypes.BYTE),
        ("DataIn", wintypes.BYTE),
        ("DataTransferLength", wintypes.DWORD),
        ("TimeOutValue", wintypes.DWORD),
        ("DataBuffer", ctypes.c_void_p),  # Прямой указатель на буфер данных
        ("SenseInfoOffset", wintypes.DWORD),
        ("Cdb", ctypes.c_ubyte * 16),  # SCSI командный блок
    ]


# Определение Windows API функций
CreateFile = ctypes.windll.kernel32.CreateFileW
CreateFile.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE
]
CreateFile.restype = wintypes.HANDLE

DeviceIoControl = ctypes.windll.kernel32.DeviceIoControl
DeviceIoControl.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD)
]
DeviceIoControl.restype = wintypes.BOOL

CloseHandle = ctypes.windll.kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


def scsi_write_zeros_direct(disk_number, sector_offset, sector_count, sector_size=512):
    """Использует IOCTL_SCSI_PASS_THROUGH_DIRECT для записи нулей в указанные сектора."""
    disk_path = f"\\\\.\\PhysicalDrive{disk_number}"

    h_disk = CreateFile(
        disk_path,
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )

    if h_disk == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        # Создаём буфер данных (нулевые байты)
        data_length = sector_count * sector_size
        data_buffer = (ctypes.c_ubyte * data_length)()

        # Указатель на буфер
        buffer_pointer = ctypes.cast(data_buffer, ctypes.c_void_p)

        # Формируем структуру SCSI_PASS_THROUGH_DIRECT
        sptd = SCSI_PASS_THROUGH_DIRECT()
        sptd.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
        sptd.ScsiStatus = 0
        sptd.PathId = 0
        sptd.TargetId = 0
        sptd.Lun = 0
        sptd.CdbLength = 10  # Длина CDB для команды WRITE(10)
        sptd.SenseInfoLength = 0
        sptd.DataIn = SCSI_IOCTL_DATA_OUT
        sptd.DataTransferLength = data_length
        sptd.TimeOutValue = 30  # Таймаут в секундах
        sptd.DataBuffer = buffer_pointer
        sptd.SenseInfoOffset = 0

        # Формируем SCSI команду WRITE(10)
        cdb = sptd.Cdb
        cdb[0] = 0x2A  # WRITE(10)
        cdb[2] = (sector_offset >> 24) & 0xFF
        cdb[3] = (sector_offset >> 16) & 0xFF
        cdb[4] = (sector_offset >> 8) & 0xFF
        cdb[5] = sector_offset & 0xFF
        cdb[7] = (sector_count >> 8) & 0xFF
        cdb[8] = sector_count & 0xFF

        # Выполняем DeviceIoControl
        bytes_returned = wintypes.DWORD(0)
        success = DeviceIoControl(
            h_disk,
            IOCTL_SCSI_PASS_THROUGH_DIRECT,
            ctypes.byref(sptd),
            ctypes.sizeof(sptd),
            None,
            0,
            ctypes.byref(bytes_returned)
        )

        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

        print(f"Секторы с {sector_offset} по {sector_offset + sector_count - 1} успешно очищены.")
    finally:
        CloseHandle(h_disk)

        