"""A simple setup script to create an executable using PyQt5. This also
demonstrates the method for creating a Windows executable that does not have
an associated console.

test_pyqt5.py is a very simple type of PyQt5 application

Run the build process by running the command 'python setup.py build'

If everything works well you should find a subdirectory in the build
subdirectory that contains the files needed to run the application
"""

from __future__ import annotations

from cx_Freeze import Executable, setup
import os
import pywin32_system32

try:
    from cx_Freeze.hooks import get_qt_plugins_paths
except ImportError:
    get_qt_plugins_paths = None

include_files = [
    os.path.join("C:\py-wf\disk_cleaner\.env\Lib\site-packages\pywin32_system32", "pywintypes312.dll"),
    'victoriapath'
]
if get_qt_plugins_paths:
    # Inclusion of extra plugins (since cx_Freeze 6.8b2)
    # cx_Freeze automatically imports the following plugins depending on the
    # module used, but suppose we need the following:
    include_files += get_qt_plugins_paths("PyQt5", "multimedia")

build_exe_options = {
    # exclude packages that are not really needed
    "excludes": ["tkinter", "unittest", "email", "http", "xml", "pydoc"],
    "includes": ["win32gui"],
    "include_files": include_files,
    "include_msvcr": True,
}

bdist_mac_options = {
    "bundle_name": "Test",
}

bdist_dmg_options = {
    "volume_label": "TEST",
}

executables = [Executable("main.py", base="gui", icon="hddc.ico", target_name='hddc')]

setup(
    name="HDD-Handler",
    version="1.35.1",
    description="HDD-Handler",
    options={
        "build_exe": build_exe_options,
       #  "bdist_mac": bdist_mac_options,
       #  "bdist_dmg": bdist_dmg_options,
    },
    executables=executables,
)