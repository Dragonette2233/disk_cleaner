import sys
from cx_Freeze import setup, Executable
import PyQt5
import os

# Определите имя вашего основного скрипта
script_name = "main.py"

# Определите зависимости (если у вас есть дополнительные модули, которые нужно включить)
build_exe_options = {
    "packages": ["ctypes", 'PyQt5'],
    "includes": [],
}

# Укажите необходимые QML файлы
include_files = []
qml_path = os.path.join(os.path.dirname(PyQt5.__file__), 'Qt', 'qml')

# Укажите дополнительные параметры, если нужно
base = None
# if sys.platform == "win32":
#     base = "Win32GUI"  # Используйте "Win32GUI" для GUI приложений без консольного окна

setup(
    name="DiskInfo",
    version="0.1",
    description="Disk Information Viewer",
    options={"build_exe": build_exe_options},
    executables=[Executable(script_name, base=base)],
)
