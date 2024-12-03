#include <windows.h>
#include <stdio.h>

#define ATA_PASS_THROUGH (0x85)  // ATA PASS-THROUGH (16)
#define SCSI_IOCTL_DATA_OUT 0    // Команда без передачи данных
#define IOCTL_SCSI_PASS_THROUGH 0x4D004
#define IOCTL_SCSI_PASS_THROUGH_DIRECT 0x4D014

#pragma pack(push, 1)
typedef struct _SCSI_PASS_THROUGH_DIRECT {
    USHORT Length;
    UCHAR ScsiStatus;
    UCHAR PathId;
    UCHAR TargetId;
    UCHAR Lun;
    UCHAR CdbLength;
    UCHAR SenseInfoLength;
    UCHAR DataIn; // 0 = Data-Out
    ULONG DataTransferLength;
    ULONG TimeOutValue;
    PVOID DataBuffer;
    ULONG SenseInfoOffset;
    UCHAR Cdb[16]; // SCSI Command Descriptor Block
} SCSI_PASS_THROUGH_DIRECT;
#pragma pack(pop)

void send_sleep_command(HANDLE device) {
    SCSI_PASS_THROUGH_DIRECT sptd = {0};
    DWORD returned = 0;
    UCHAR sense_buffer[32] = {0};

    // Устанавливаем параметры команды
    sptd.Length = sizeof(SCSI_PASS_THROUGH_DIRECT);
    sptd.CdbLength = 16; // Длина CDB
    sptd.SenseInfoLength = sizeof(sense_buffer);
    sptd.SenseInfoOffset = offsetof(SCSI_PASS_THROUGH_DIRECT, Cdb);
    sptd.DataIn = SCSI_IOCTL_DATA_OUT;
    sptd.TimeOutValue = 2; // Таймаут в секундах

    // Формируем команду ATA PASS-THROUGH
    sptd.Cdb[0] = ATA_PASS_THROUGH; // Команда SCSI
    sptd.Cdb[1] = (1 << 6);         // Бит PROTOCOL = PIO Data Out
    sptd.Cdb[2] = 0;                // Установка FEATURES (0 для SLEEP)
    sptd.Cdb[4] = 0;                // SECTOR_COUNT (0 для SLEEP)
    sptd.Cdb[5] = 0;                // LBA_LOW
    sptd.Cdb[6] = 0;                // LBA_MID
    sptd.Cdb[7] = 0;                // LBA_HIGH
    sptd.Cdb[8] = 0;                // DEVICE
    sptd.Cdb[9] = 0xE6;             // Команда SLEEP
    sptd.Cdb[10] = 0;               // Резерв
    sptd.Cdb[11] = 0;               // Резерв

    // Отправляем команду через DeviceIoControl
    BOOL result = DeviceIoControl(
        device,
        IOCTL_SCSI_PASS_THROUGH_DIRECT,
        &sptd,
        sizeof(SCSI_PASS_THROUGH_DIRECT),
        &sptd,
        sizeof(SCSI_PASS_THROUGH_DIRECT),
        &returned,
        NULL
    );

    if (!result) {
        printf("Ошибка отправки команды SLEEP: %d\n", GetLastError());
    } else {
        printf("Команда SLEEP успешно отправлена.\n");
    }
}

int main() {
    // Открываем диск
    HANDLE device = CreateFile(
        "\\\\.\\PhysicalDrive0",  // Замените на номер вашего устройства
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_EXISTING,
        0,
        NULL
    );

    if (device == INVALID_HANDLE_VALUE) {
        printf("Не удалось открыть устройство: %d\n", GetLastError());
        return 1;
    }

    // Отправляем команду SLEEP
    send_sleep_command(device);

    // Закрываем устройство
    CloseHandle(device);
    return 0;
}