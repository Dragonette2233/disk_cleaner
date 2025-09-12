import ctypes
from ctypes import wintypes

# Константы
GENERIC_READ  = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ  = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3

# Управляющий код для рескана шины
IOCTL_SCSI_RESCAN_BUS = 0x00041000

# WinAPI
CreateFile = ctypes.windll.kernel32.CreateFileW
DeviceIoControl = ctypes.windll.kernel32.DeviceIoControl
CloseHandle = ctypes.windll.kernel32.CloseHandle

def rescan_scsi_bus():
    # Открываем устройство SCSI контроллера
    hDevice = CreateFile(
        r"\\.\Scsi0:",              # Первый SCSI контроллер (может быть Scsi1:, Scsi2: и т.д.)
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )

    if hDevice == -1:
        return "ERR - SCSI conroller not found"
        # raise OSError("Не удалось открыть SCSI контроллер")

    bytesReturned = wintypes.DWORD()
    success = DeviceIoControl(
        hDevice,
        IOCTL_SCSI_RESCAN_BUS,
        None, 0,      # Входных данных нет
        None, 0,      # Выходных данных нет
        ctypes.byref(bytesReturned),
        None
    )

    CloseHandle(hDevice)

    if not success:
        return "ERR - IOCTL_SCSI_RESCAN_BUS call failed"
    