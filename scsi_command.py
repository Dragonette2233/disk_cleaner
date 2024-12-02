import ctypes
from ctypes import wintypes

# Константы Windows API
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 0x3
IOCTL_SCSI_PASS_THROUGH_DIRECT_EX = 0x4D024

# Размеры буферов
SCSI_CDB_LENGTH = 0x10  # 16 байт
SENSE_BUFFER_LENGTH = 0x20  # 32 байта

# Структура SCSI_PASS_THROUGH_DIRECT_EX
class SCSI_PASS_THROUGH_DIRECT_EX(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.ULONG),
        ("Length", wintypes.ULONG),
        ("CdbLength", wintypes.CHAR),
        ("Flags", wintypes.CHAR),
        ("Reserved", wintypes.USHORT),
        ("DataTransferLength", wintypes.ULONG),
        ("TimeOutValue", wintypes.ULONG),
        ("DataBufferOffset", wintypes.ULONG),
        ("SenseInfoOffset", wintypes.ULONG),
        ("Cdb", ctypes.c_ubyte * SCSI_CDB_LENGTH),
    ]

# Загрузка Windows API
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

def send_scsi_sleep_command(drive_number):
    drive_path = f"\\\\.\\PhysicalDrive{drive_number}"

    # Открытие устройства
    handle = CreateFile(
        drive_path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error(), f"Не удалось открыть диск {drive_path}")

    try:
        # Настройка структуры SCSI_PASS_THROUGH_DIRECT_EX
        sense_buffer = (ctypes.c_ubyte * SENSE_BUFFER_LENGTH)()
        cdb_command = (ctypes.c_ubyte * SCSI_CDB_LENGTH)()

        # Команда Standby Immediate (0xE0)
        cdb_command[0] = 0xE0  # SCSI команда

        scsi_command = SCSI_PASS_THROUGH_DIRECT_EX()
        scsi_command.Version = 0x6  # Версия структуры
        scsi_command.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT_EX)
        scsi_command.CdbLength = 0x6  # Длина команды
        scsi_command.Flags = 0x0  # Нет дополнительных флагов
        scsi_command.Reserved = 0x0
        scsi_command.DataTransferLength = 0x0
        scsi_command.TimeOutValue = 0xA  # Таймаут 10 секунд
        scsi_command.DataBufferOffset = 0x0
        scsi_command.SenseInfoOffset = ctypes.addressof(sense_buffer)
        scsi_command.Cdb = cdb_command

        # Выполнение команды
        bytes_returned = wintypes.DWORD()
        print(f"Отправка команды Standby Immediate на диск {drive_number}...")

        success = DeviceIoControl(
            handle,
            IOCTL_SCSI_PASS_THROUGH_DIRECT_EX,
            ctypes.byref(scsi_command),
            ctypes.sizeof(scsi_command),
            None,
            0,
            ctypes.byref(bytes_returned),
            None,
        )

        if not success:
            raise ctypes.WinError(ctypes.get_last_error(), "Ошибка выполнения DeviceIoControl")

        print(f"Команда Standby Immediate успешно отправлена на диск {drive_number}.")
    finally:
        CloseHandle(handle)

# if name == "main":
drive_number = 1  # Номер диска
try:
    send_scsi_sleep_command(drive_number)
except Exception as e:
    print(f"Ошибка: {e}")