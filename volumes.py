import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QLabel, QMenu, QVBoxLayout, QWidget


class ContextMenuExample(QWidget):
    def init(self):
        super().init()

        # Устанавливаем основной интерфейс
        self.setWindowTitle("Пример контекстного меню на QLabel")
        self.resize(300, 200)

        # Создаем QLabel
        self.label = QLabel("Нажмите ПКМ на этом тексте", self)
        self.label.setContextMenuPolicy(Qt.CustomContextMenu)  # Включаем поддержку пользовательского контекстного меню
        self.label.customContextMenuRequested.connect(self.show_context_menu)

        # Настройка интерфейса
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        """
        label = QLabel("Нажмите ПКМ на этом тексте", self)
        label.setContextMenuPolicy(Qt.CustomContextMenu)  # Включаем поддержку пользовательского контекстного меню
        label.customContextMenuRequested.connect(lambda: self.show_context_menu(QCursor.pos))
        """

    def show_context_menu(self, position):
        # Создаем контекстное меню
        context_menu = QMenu(self)

        # Добавляем пункты меню
        action_1 = context_menu.addAction("Действие 1")
        action_2 = context_menu.addAction("Действие 2")
        action_3 = context_menu.addAction("Действие 3")

        # Отображаем меню в позиции курсора
        action = context_menu.exec_(self.label.mapToGlobal(position))

        # Обработка выбранного действия
        if action == action_1:
            print("Вы выбрали Действие 1")
        elif action == action_2:
            print("Вы выбрали Действие 2")
        elif action == action_3:
            print("Вы выбрали Действие 3")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ContextMenuExample()
    window.show()
    sys.exit(app.exec_())