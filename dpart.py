import subprocess
import time

class DiskPartSession:
    def __init__(self):
        # Открываем процесс diskpart с постоянным подключением
        self.process = subprocess.Popen(
            ["diskpart"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )

    def send_command(self, command):
        # Отправляем команду в diskpart
        self.process.stdin.write(command + '\n')
        self.process.stdin.flush()
        
        # Пауза для того, чтобы процесс успел обработать команду
        time.sleep(1)
        
        # Читаем результат
        output = []
        while True:
            line = self.process.stdout.readline()
            if line == '':
                break
            output.append(line)
            # Останавливаемся на конце вывода команды
            if "DISKPART>" in line:
                break
        return ''.join(output)

    def delete_partitions(self, disk_index):
        # Команда для удаления всех разделов
        command = f"sel dis {disk_index}\nonline dis\nclean"
        output = self.send_command(command)
        
        # Анализируем вывод
        if "DiskPart succeeded in cleaning the disk" in output:
            print(f"Разделы на диске {disk_index} успешно удалены.")
            return True
        else:
            print(f"Ошибка при удалении разделов на диске {disk_index}: {output}")
            return False

    def close(self):
        # Завершаем сеанс diskpart
        self.process.stdin.write("exit\n")
        self.process.stdin.flush()
        self.process.terminate()


# # Пример использования
# session = DiskPartSession()

# # Удаление разделов по очереди на дисках с индексами 0 и 1
# session.delete_partitions(0)
# session.delete_partitions(1)

# # Закрытие сеанса
# session.close()
