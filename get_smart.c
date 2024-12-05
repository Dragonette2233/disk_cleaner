#include <windows.h>
#include <stdio.h>

#define SMART_RCV_DRIVE_DATA 0x7C088

// Структура для входных параметров
#pragma pack(push, 1)
typedef struct {
    DWORD cBufferSize;
    BYTE  irDriveRegs[8];  // Регистры IDE
    BYTE  bDriveNumber;
    BYTE  reserved[3];
    PVOID lpReserved;
} SENDCMDINPARAMS;

// Структура для драйвера
typedef struct {
    BYTE  bDriverError;
    BYTE  bIDEStatus;
    BYTE  reserved[2];
    DWORD dwReserved[2];
} DRIVERSTATUS;

// Структура для выходных данных
typedef struct {
    DWORD cBufferSize;
    DRIVERSTATUS DriverStatus;
    BYTE bBuffer[512];  // Данные S.M.A.R.T.
} SENDCMDOUTPARAMS;
#pragma pack(pop)

// Функция для чтения S.M.A.R.T. атрибутов
void read_smart_attributes(int drive_number) {
    char drive_path[32];
    snprintf(drive_path, sizeof(drive_path), "\\\\.\\PhysicalDrive%d", drive_number);

    // Открытие устройства
    HANDLE hDevice = CreateFileA(
        drive_path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_EXISTING,
        0,
        NULL
    );

    if (hDevice == INVALID_HANDLE_VALUE) {
        printf("Ошибка: Не удалось открыть диск %s. Код ошибки: %lu\n", drive_path, GetLastError());
        return;
    }

    // Подготовка входных параметров
    SENDCMDINPARAMS in_params = { 0 };
    in_params.cBufferSize = 512;
    in_params.irDriveRegs[0] = 0xB0;  // Команда SMART
    in_params.irDriveRegs[1] = 0xD0;  // Чтение данных SMART
    in_params.bDriveNumber = (BYTE)drive_number;

    // Буфер для выхода
    SENDCMDOUTPARAMS out_params = { 0 };
    DWORD bytes_returned = 0;

    // Отправка команды
    BOOL success = DeviceIoControl(
        hDevice,
        SMART_RCV_DRIVE_DATA,
        &in_params,
        sizeof(SENDCMDINPARAMS),
        &out_params,
        sizeof(SENDCMDOUTPARAMS),
        &bytes_returned,
        NULL
    );

    if (!success) {
        printf("Ошибка: DeviceIoControl не удалась. Код ошибки: %lu\n", GetLastError());
        CloseHandle(hDevice);
        return;
    }

    // Разбор данных SMART
    BYTE* smart_data = out_params.bBuffer;
    printf("Атрибуты SMART для диска %d:\n", drive_number);

    for (int i = 0; i < 30; i++) {
        BYTE id = smart_data[i * 12];           // Идентификатор атрибута
        BYTE value = smart_data[i * 12 + 3];   // Текущее значение
        DWORD raw_value = *(DWORD*)&smart_data[i * 12 + 5];  // Сырой параметр

        if (id == 5 || id == 196 || id == 197 || id == 7) {
            const char* attribute_name = NULL;
            switch (id) {
                case 5: attribute_name = "Reallocated Sector Count"; break;
                case 196: attribute_name = "Reallocation Event Count"; break;
                case 197: attribute_name = "Current Pending Sector Count"; break;
                case 7: attribute_name = "Seek Error Rate"; break;
            }

            if (attribute_name) {
                printf("  %s: Value = %d, Raw = %u\n", attribute_name, value, raw_value);
            }
        }
    }

    // Закрытие дескриптора устройства
    CloseHandle(hDevice);
}

int main() {
    int drive_number = 0;  // Укажите номер диска
    read_smart_attributes(drive_number);
    return 0;
}