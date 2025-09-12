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
SCSI_CDB_LENGTH = 16
SENSE_BUFFER_LENGTH = 32

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
        ("DataTransferLength", wintypes.ULONG),
        ("TimeOutValue", wintypes.ULONG),
        ("DataBuffer", ctypes.POINTER(ctypes.c_ubyte)),
        ("SenseInfoOffset", wintypes.ULONG),
        ("Cdb", wintypes.BYTE * SCSI_CDB_LENGTH),
    ]

# API kernel32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
CreateFile = kernel32.CreateFileW
CreateFile.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
CreateFile.restype = wintypes.HANDLE

DeviceIoControl = kernel32.DeviceIoControl
DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
DeviceIoControl.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

def get_disk_handle(drive_number):
    drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
    handle = CreateFile(drive_path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if handle == wintypes.HANDLE(-1).value:
        err = ctypes.get_last_error()
        if err == 32:
            return 'CONFLICT'
        elif err in (2, 55):
            return False
        else:
            open('sleep_err.txt', 'w+', encoding='utf-8').write(f'Err: winerror {err}')
            raise ctypes.WinError(err, f"Не удалось открыть диск {drive_path}")
    return handle

def send_scsi_command(drive_number, command, check=False):
    handle = get_disk_handle(drive_number)
    if not handle:
        return handle
    try:
        sense_buffer = (ctypes.c_ubyte * SENSE_BUFFER_LENGTH)()
        cdb_command = (ctypes.c_ubyte * SCSI_CDB_LENGTH)()
        if check:
            cdb_command[0] = 0x00  # TEST UNIT READY
        else:
            cdb_command[0] = 0x1B  # START STOP UNIT
            cdb_command[4] = command

        data_buffer = (ctypes.c_ubyte * SENSE_BUFFER_LENGTH)()
        scsi_command = SCSI_PASS_THROUGH_DIRECT()
        scsi_command.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
        scsi_command.CdbLength = 6
        if check:
            scsi_command.DataIn = 1
            scsi_command.DataTransferLength = len(data_buffer)
            scsi_command.DataBuffer = ctypes.cast(data_buffer, ctypes.POINTER(ctypes.c_ubyte))
        else:
            scsi_command.DataIn = 0
            scsi_command.DataTransferLength = 0
            scsi_command.DataBuffer = None
        scsi_command.TimeOutValue = 5
        scsi_command.SenseInfoOffset = ctypes.addressof(sense_buffer)
        scsi_command.Cdb = cdb_command

        bytes_returned = wintypes.DWORD()
        success = DeviceIoControl(handle, IOCTL_SCSI_PASS_THROUGH_DIRECT, ctypes.byref(scsi_command), ctypes.sizeof(scsi_command), ctypes.byref(data_buffer), len(data_buffer), ctypes.byref(bytes_returned), None)
        if not success:
            if check:
                return 'IO'
            return False
        if check:
            return data_buffer[16] == 0
    finally:
        CloseHandle(handle)

def check_disk_power_state(drive_number):
    handle = get_disk_handle(drive_number)
    if not handle:
        return handle
    try:
        sense_buffer = (ctypes.c_ubyte * SENSE_BUFFER_LENGTH)()
        cdb_command = (ctypes.c_ubyte * SCSI_CDB_LENGTH)()
        cdb_command[0] = 0x00  # TEST UNIT READY

        data_buffer = (ctypes.c_ubyte * SENSE_BUFFER_LENGTH)()
        scsi_command = SCSI_PASS_THROUGH_DIRECT()
        scsi_command.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
        scsi_command.CdbLength = 6
        scsi_command.DataIn = 1
        scsi_command.DataTransferLength = len(data_buffer)
        scsi_command.TimeOutValue = 1
        scsi_command.DataBuffer = ctypes.cast(data_buffer, ctypes.POINTER(ctypes.c_ubyte))
        scsi_command.SenseInfoOffset = ctypes.addressof(sense_buffer)
        scsi_command.Cdb = cdb_command

        bytes_returned = wintypes.DWORD()
        success = DeviceIoControl(handle, IOCTL_SCSI_PASS_THROUGH_DIRECT, ctypes.byref(scsi_command), ctypes.sizeof(scsi_command), ctypes.byref(data_buffer), len(data_buffer), ctypes.byref(bytes_returned), None)
        if not success:
            error_code = ctypes.get_last_error()
            raise ctypes.WinError(error_code, f"Ошибка DeviceIoControl: {error_code}")
        return data_buffer[16] == 0x00
    finally:
        CloseHandle(handle)

def scsi_write_zeros_direct(disk_number, sector_offset, sector_count, sector_size=512):
    h_disk = get_disk_handle(disk_number)
    if not h_disk:
        return h_disk
    try:
        data_length = sector_count * sector_size
        data_buffer = (ctypes.c_ubyte * data_length)()
        buffer_pointer = ctypes.cast(data_buffer, ctypes.POINTER(ctypes.c_ubyte))

        sptd = SCSI_PASS_THROUGH_DIRECT()
        sptd.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
        sptd.CdbLength = 10
        sptd.DataIn = 0
        sptd.DataTransferLength = data_length
        sptd.TimeOutValue = 30
        sptd.DataBuffer = buffer_pointer

        cdb = sptd.Cdb
        cdb[0] = 0x2A  # WRITE(10)
        cdb[2] = (sector_offset >> 24) & 0xFF
        cdb[3] = (sector_offset >> 16) & 0xFF
        cdb[4] = (sector_offset >> 8) & 0xFF
        cdb[5] = sector_offset & 0xFF
        cdb[7] = (sector_count >> 8) & 0xFF
        cdb[8] = sector_count & 0xFF

        bytes_returned = wintypes.DWORD(0)
        success = DeviceIoControl(h_disk, IOCTL_SCSI_PASS_THROUGH_DIRECT, ctypes.byref(sptd), ctypes.sizeof(sptd), None, 0, ctypes.byref(bytes_returned), None)
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())
        print(f"Секторы {sector_offset}–{sector_offset + sector_count - 1} очищены.")
    finally:
        CloseHandle(h_disk)

def scsi_sleep_command(idxs):
    for i in idxs:
        try:
            send_scsi_command(i, 0)
        except FileNotFoundError as ex:
            if "WinError 2" not in str(ex):
                print(ex)

def is_disk_sleeping(drive_number):
    return send_scsi_command(drive_number, 0, check=True)
