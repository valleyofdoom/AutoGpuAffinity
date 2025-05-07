import ctypes
import ctypes.wintypes

SETUPAPI = ctypes.windll.setupapi

DIGCF_ALLCLASSES = 0x4
DIGCF_DEVICEINTERFACE = 0x10

DIF_PROPERTYCHANGE = 0x12

DICS_FLAG_GLOBAL = 0x1

DICS_ENABLE = 0x1
DICS_DISABLE = 0x2


class SP_CLASSINSTALL_HEADER(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("InstallFunction", ctypes.c_int32),
    ]


class SP_PROPCHANGE_PARAMS(ctypes.Structure):
    _fields_ = [
        ("ClassInstallHeader", SP_CLASSINSTALL_HEADER),
        ("StateChange", ctypes.c_ulong),
        ("Scope", ctypes.c_ulong),
        ("HwProfile", ctypes.c_ulong),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("ClassGuid", GUID),
        ("DevInst", ctypes.c_ulong),
        ("Reserved", ctypes.POINTER(ctypes.c_ulong)),
    ]


SetupDiGetClassDevsW = SETUPAPI.SetupDiGetClassDevsW
SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_wchar_p, ctypes.wintypes.HWND, ctypes.wintypes.DWORD]
SetupDiGetClassDevsW.restype = ctypes.wintypes.HWND

SetupDiEnumDeviceInfo = SETUPAPI.SetupDiEnumDeviceInfo
SetupDiEnumDeviceInfo.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
SetupDiEnumDeviceInfo.restype = ctypes.wintypes.BOOL

SetupDiSetClassInstallParamsA = SETUPAPI.SetupDiSetClassInstallParamsA
SetupDiSetClassInstallParamsA.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.POINTER(SP_DEVINFO_DATA),
    ctypes.POINTER(SP_CLASSINSTALL_HEADER),
    ctypes.wintypes.DWORD,
]
SetupDiSetClassInstallParamsA.restype = ctypes.wintypes.BOOL

SetupDiCallClassInstaller = SETUPAPI.SetupDiCallClassInstaller
SetupDiCallClassInstaller.argtypes = [ctypes.c_int32, ctypes.c_ssize_t, ctypes.POINTER(SP_DEVINFO_DATA)]
SetupDiCallClassInstaller.restype = ctypes.wintypes.BOOL
