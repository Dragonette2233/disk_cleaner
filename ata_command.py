import ctypes
from ctypes import wintypes

# Константы Windows API
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
IOCTL_ATA_PASS_THROUGH = 0x4D02C

class ATA_PASS_THROUGH_EX(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("AtaFlags", wintypes.USHORT),
        ("PathId", wintypes.BYTE),
        ("TargetId", wintypes.BYTE),
        ("Lun", wintypes.BYTE),
        ("ReservedAsUchar", wintypes.BYTE),
        ("DataTransferLength", wintypes.ULONG),
        ("TimeOutValue", wintypes.ULONG),
        ("ReservedAsUlong", wintypes.ULONG),
        ("DataBufferOffset", wintypes.ULONG),
        ("PreviousTaskFile", wintypes.BYTE * 8),
        ("CurrentTaskFile", wintypes.BYTE * 8),
    ]

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

def send_standby_immediate(drive_number):
    drive_path = f"\\\\.\\PhysicalDrive{drive_number}"

    print(f"Попытка открыть диск: {drive_path}")
    handle = kernel32.CreateFileW(
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
        ata_command = ATA_PASS_THROUGH_EX()
        ata_command.Length = ctypes.sizeof(ATA_PASS_THROUGH_EX)
        ata_command.AtaFlags = 0x02  # ATA_FLAGS_DRDY_REQUIRED
        ata_command.TimeOutValue = 10
        ata_command.CurrentTaskFile[6] = 0xE0  # Команда Standby Immediate

        bytes_returned = wintypes.DWORD()
        print("Отправка команды Standby Immediate...")

        success = kernel32.DeviceIoControl(
            handle,
            IOCTL_ATA_PASS_THROUGH,
            ctypes.byref(ata_command),
            ctypes.sizeof(ata_command),
            None,
            0,
            ctypes.byref(bytes_returned),
            None,
        )

        if not success:
            raise ctypes.WinError(ctypes.get_last_error(), "Ошибка выполнения DeviceIoControl")

        print(f"Команда Standby Immediate успешно отправлена на диск {drive_number}.")
    finally:
        kernel32.CloseHandle(handle)

try:
    send_standby_immediate(0)  # Замените 0 на номер вашего диска
except Exception as e:
    print(f"Ошибка: {e}")