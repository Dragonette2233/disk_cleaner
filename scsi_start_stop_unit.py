import ctypes
from ctypes import wintypes

# Константы Windows API
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x4D014

# Размеры буферов
SCSI_CDB_LENGTH = 16  # Длина CDB команды
SENSE_BUFFER_LENGTH = 32

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
        ("DataIn", wintypes.BYTE),  # 0 = None, 1 = Data In, 2 = Data Out
        ("DataTransferLength", wintypes.ULONG),
        ("TimeOutValue", wintypes.ULONG),
        ("DataBuffer", ctypes.POINTER(ctypes.c_ubyte)),
        ("SenseInfoOffset", wintypes.ULONG),
        ("Cdb", wintypes.BYTE * SCSI_CDB_LENGTH),
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

def send_scsi_command(drive_number, command):
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
        # Настройка структуры SCSI_PASS_THROUGH_DIRECT
        sense_buffer = (ctypes.c_ubyte * SENSE_BUFFER_LENGTH)()
        cdb_command = (ctypes.c_ubyte * SCSI_CDB_LENGTH)()
        cdb_command[0] = 0x1B  # Команда SCSI START STOP UNIT
        cdb_command[4] = command  # Поле START (1 для START, 0 для STOP)

        scsi_command = SCSI_PASS_THROUGH_DIRECT()
        scsi_command.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
        scsi_command.CdbLength = 6  # Длина команды
        scsi_command.DataIn = 0  # Данные не передаются
        scsi_command.DataTransferLength = 0
        scsi_command.TimeOutValue = 10  # Таймаут в секундах
        scsi_command.DataBuffer = None
        scsi_command.SenseInfoOffset = ctypes.addressof(sense_buffer)
        scsi_command.Cdb = cdb_command

        # Выполнение команды
        bytes_returned = wintypes.DWORD()
        print("Отправка команды START/STOP UNIT...")

        success = DeviceIoControl(
            handle,
            IOCTL_SCSI_PASS_THROUGH_DIRECT,
            ctypes.byref(scsi_command),
            ctypes.sizeof(scsi_command),
            None,
            0,
            ctypes.byref(bytes_returned),
            None,
        )

        if not success:
            raise ctypes.WinError(ctypes.get_last_error(), "Ошибка выполнения DeviceIoControl")

        if command == 1:
            print(f"Команда START UNIT успешно отправлена на диск {drive_number}.")
        else:
            print(f"Команда STOP UNIT успешно отправлена на диск {drive_number}.")
    finally:
        CloseHandle(handle)

def scsi_sleep_command(idxs):
    
    for i in idxs:
        try:
            send_scsi_command(i, 0)
        except FileNotFoundError as ex:
            if "WinError 2" not in str(ex):
                print(ex)
                
# # Пример использования
# drive_number = 2  # Номер диска
# try:
#     send_scsi_command(drive_number, 0)  # Отправка команды STOP UNIT
#     # send_scsi_command(drive_number, 1)  # Отправка команды START UNIT
# except Exception as e:
#     print(f"Ошибка: {e}")