import ctypes
from ctypes import wintypes, byref
import queue
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
IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x4D014 # SCSI команды
FILE_READ_DATA = 0x0001
OPEN_EXISTING = 3

SCSI_CDB_LENGTH = 16  # Длина CDB команды
SENSE_BUFFER_LENGTH = 32

update_queue = queue.Queue()

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
    handle = open_disk(drive_index)
    try:
        # Настройка структуры SCSI_PASS_THROUGH_DIRECT
        sense_buffer = (ctypes.c_ubyte * SENSE_BUFFER_LENGTH)()
        cdb_command = (ctypes.c_ubyte * SCSI_CDB_LENGTH)()
        cdb_command[0] = 0x1B  # Команда SCSI START STOP UNIT
        cdb_command[4] = 0  # Поле START (1 для START, 0 для STOP)

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

        success = kernel32.DeviceIoControl(
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

        
        # print(f"Команда STOP UNIT успешно отправлена на диск {drive_index}.")
    finally:
        kernel32.CloseHandle(handle)
        
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

        if ctypes.get_last_error() == 55:
            return 'OUT'
        else:
            print(ctypes.get_last_error())
            return 'OUT'

    # Извлекаем информацию о модели и серийнике из буфера
    descriptor = STORAGE_DEVICE_DESCRIPTOR.from_buffer_copy(buffer)
    model = ""
    serial = ""

    if descriptor.ProductIdOffset:
        model = buffer[descriptor.ProductIdOffset:].split(b'\x00', 1)[0].decode()
    if descriptor.SerialNumberOffset:
        serial = buffer[descriptor.SerialNumberOffset:].split(b'\x00', 1)[0].decode()

    partition_info: str = ''

    try:
        partition_info = get_partition_count(disk_index)
    except OSError as e:
        
        s_e = str(e)
        if 'CRC' in s_e:
            partition_info = 'CRC'
        elif 'ввода' in s_e or 'WinError 1117' in s_e:
            partition_info = 'IO'
        elif 'не подключено' in s_e:
            partition_info = 'NC'
        else:
            partition_info = s_e
        # print("pinfo is", partition_info)
    # print(model, serial)
    # update_queue.put([])
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

def delete_disk_partitions(disk_index, rescan):

    rescan_command = ''

    if rescan:
        rescan_command = 'RESCAN'
    
    
    commands = '\n'.join(
        [f"""
    sel dis {i}
    {rescan_command}
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
    
 

    