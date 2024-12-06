from ctypes import WinError
import ctypes

print(ctypes.get_last_error())

raise ctypes.WinError(ctypes.get_last_error(), f"Не удалось открыть диск")