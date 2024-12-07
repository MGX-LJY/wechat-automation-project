from datetime import datetime, timedelta
from . import uiautomation as uia
from PIL import ImageGrab
import win32clipboard
import win32process
import win32gui
import win32api
import win32con
import pyperclip
import ctypes
import psutil
import shutil
import winreg
import logging
import time
import os
import re

ORIVERSION = "3.9.8.15"
VERSION = "3.9.11.17"

def set_cursor_pos(x, y):
    win32api.SetCursorPos((x, y))
    
def Click(rect):
    x = (rect.left + rect.right) // 2
    y = (rect.top + rect.bottom) // 2
    set_cursor_pos(x, y)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
    
def GetPathByHwnd(hwnd):
    try:
        thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(process_id)
        return process.exe()
    except Exception as e:
        print(f"Error: {e}")
        return None

def GetVersionByPath(file_path):
    try:
        info = win32api.GetFileVersionInfo(file_path, '\\')
        version = "{}.{}.{}.{}".format(win32api.HIWORD(info['FileVersionMS']),
                                        win32api.LOWORD(info['FileVersionMS']),
                                        win32api.HIWORD(info['FileVersionLS']),
                                        win32api.LOWORD(info['FileVersionLS']))
    except:
        version = None
    return version


def IsRedPixel(uicontrol):
    rect = uicontrol.BoundingRectangle
    bbox = (rect.left, rect.top, rect.right, rect.bottom)
    img = ImageGrab.grab(bbox=bbox, all_screens=True)
    return any(p[0] > p[1] and p[0] > p[2] for p in img.getdata())

class DROPFILES(ctypes.Structure):
    _fields_ = [
    ("pFiles", ctypes.c_uint),
    ("x", ctypes.c_long),
    ("y", ctypes.c_long),
    ("fNC", ctypes.c_int),
    ("fWide", ctypes.c_bool),
    ]

pDropFiles = DROPFILES()
pDropFiles.pFiles = ctypes.sizeof(DROPFILES)
pDropFiles.fWide = True
matedata = bytes(pDropFiles)

def SetClipboardText(text: str):
    pyperclip.copy(text)
    # if not isinstance(text, str):
    #     raise TypeError(f"参数类型必须为str --> {text}")
    # t0 = time.time()
    # while True:
    #     if time.time() - t0 > 10:
    #         raise TimeoutError(f"设置剪贴板超时！ --> {text}")
    #     try:
    #         win32clipboard.OpenClipboard()
    #         win32clipboard.EmptyClipboard()
    #         win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    #         break
    #     except:
    #         pass
    #     finally:
    #         try:
    #             win32clipboard.CloseClipboard()
    #         except:
    #             pass

try:
    from anytree import Node, RenderTree

    def PrintAllControlTree(ele):
        def findall(ele, n=0, node=None):
            nn = '\n'
            nodename = f"[{ele.ControlTypeName} {n}](\"{ele.ClassName}\", \"{ele.Name.replace(nn, '')}\", \"{''.join([str(i) for i in ele.GetRuntimeId()])}\")"
            if not node:
                node1 = Node(nodename)
            else:
                node1 = Node(nodename, parent=node)
            eles = ele.GetChildren()
            for ele1 in eles:
                findall(ele1, n+1, node1)
            return node1
        tree = RenderTree(findall(ele))
        for pre, fill, node in tree:
            print(f"{pre}{node.name}")
except:
    pass

def FindPid(process_name):
    procs = psutil.process_iter(['pid', 'name'])
    for proc in procs:
        if process_name in proc.info['name']:
            return proc.info['pid']

def transver(ver):
    vers = ver.split('.')
    res = '6' + vers[0]
    for v in vers[1:]:
        res += hex(int(v))[2:].rjust(2, '0')
    return int(res, 16)

def Mver(pid):
    exepath = psutil.Process(pid).exe()
    if GetVersionByPath(exepath) != ORIVERSION:
        Warning(f"该修复方法仅适用于版本号为{ORIVERSION}的微信！")
        return
    if not uia.Control(ClassName='WeChatLoginWndForPC', searchDepth=1).Exists(maxSearchSeconds=2):
        Warning("请先打开微信启动页面再次尝试运行该方法！")
        return
    path = os.path.join(os.path.dirname(__file__), 'a.dll')
    dll = ctypes.WinDLL(path)
    dll.GetDllBaseAddress.argtypes = [ctypes.c_uint, ctypes.c_wchar_p]
    dll.GetDllBaseAddress.restype = ctypes.c_void_p
    dll.WriteMemory.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong]
    dll.WriteMemory.restype = ctypes.c_bool
    dll.GetMemory.argtypes = [ctypes.c_ulong, ctypes.c_void_p]
    dll.GetMemory.restype = ctypes.c_ulong
    mname = 'WeChatWin.dll'
    tar = transver(VERSION)
    base_address = dll.GetDllBaseAddress(pid, mname)
    address = base_address + 64761648
    if dll.GetMemory(pid, address) != tar:
        dll.WriteMemory(pid, address, tar)
    handle = ctypes.c_void_p(dll._handle)
    ctypes.windll.kernel32.FreeLibrary(handle)

def FixVersionError():
    """修复版本低无法登录的问题"""
    pid = FindPid('WeChat.exe')
    if pid:
        Mver(pid)
        return
    else:
        try:
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat", 0, winreg.KEY_READ)
            path, _ = winreg.QueryValueEx(registry_key, "InstallPath")
            winreg.CloseKey(registry_key)
            wxpath = os.path.join(path, "WeChat.exe")
            if os.path.exists(wxpath):
                os.system(f'start "" "{wxpath}"')
                time.sleep(1.5)
                FixVersionError()
            else:
                raise Exception('nof found')
        except WindowsError:
            Warning("未找到微信安装路径，请先打开微信启动页面再次尝试运行该方法！")

def GetAllControlList(ele):
    def findall(ele, n=0, text=[]):
        if ele.Name:
            text.append(ele)
        eles = ele.GetChildren()
        for ele1 in eles:
            text = findall(ele1, n+1, text)
        return text
    text_list = findall(ele)
    return text_list

def GetAllControl(ele):
    def findall(ele, n=0, controls=[]):
        # if ele.Name:
        controls.append(ele)
        eles = ele.GetChildren()
        for ele1 in eles:
            controls = findall(ele1, n+1, controls)
        return controls
    text_list = findall(ele)[1:]
    return text_list

def SetClipboardFiles(paths):
    for file in paths:
        if not os.path.exists(file):
            raise FileNotFoundError(f"file ({file}) not exists!")
    files = ("\0".join(paths)).replace("/", "\\")
    data = files.encode("U16")[2:]+b"\0\0"
    t0 = time.time()
    while True:
        if time.time() - t0 > 10:
            raise TimeoutError(f"设置剪贴板文件超时！ --> {paths}")
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_HDROP, matedata+data)
            break
        except:
            pass
        finally:
            try:
                win32clipboard.CloseClipboard()
            except:
                pass

def PasteFile(folder):
    folder = os.path.realpath(folder)
    if not os.path.exists(folder):
        os.makedirs(folder)

    t0 = time.time()
    while True:
        if time.time() - t0 > 10:
            raise TimeoutError(f"读取剪贴板文件超时！")
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                files = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
                for file in files:
                    filename = os.path.basename(file)
                    dest_file = os.path.join(folder, filename)
                    shutil.copy2(file, dest_file)
                    return True
            else:
                print("剪贴板中没有文件")
                return False
        except:
            pass
        finally:
            win32clipboard.CloseClipboard()

def parse_msg(control: uia.Control):
    if control.ControlTypeName == 'PaneControl':
        return None
    
    info = {}
    # Text
    if control.Name == '':
        info['type'] = 'Text'
        info['sender'] = control.ButtonControl().Name
        info['sender_remark'] = control.GetProgenyControl(4, control_type='TextControl').Name
        info['time'] = control.GetProgenyControl(4, 1, control_type='TextControl').Name
        info['content'] = control.GetProgenyControl(6).Name

    # Image
    elif control.Name == '[图片]':
        info['type'] = 'Image'
        info['sender'] = control.GetProgenyControl(2, control_type='ButtonControl').Name
        info['sender_remark'] = control.GetProgenyControl(4, control_type='TextControl').Name
        info['time'] = control.GetProgenyControl(4, 1, control_type='TextControl').Name
        info['content'] = ""

    # Video
    elif control.Name == '[视频]':
        info['type'] = 'Video'
        info['sender'] = control.GetProgenyControl(2, control_type='ButtonControl').Name
        info['sender_remark'] = control.GetProgenyControl(4, control_type='TextControl').Name
        info['time'] = control.GetProgenyControl(4, 1, control_type='TextControl').Name
        info['content'] = ""

    # Location
    elif control.Name == '[位置]':
        info['type'] = 'Location'
        info['sender'] = control.GetProgenyControl(2, control_type='ButtonControl').Name
        info['sender_remark'] = control.GetProgenyControl(4, control_type='TextControl').Name
        info['time'] = control.GetProgenyControl(4, 1, control_type='TextControl').Name
        info['content'] = control.GetProgenyControl(7, 1, control_type='TextControl').Name + control.GetProgenyControl(7, control_type='TextControl').Name

    # File
    elif control.Name == '[文件]':
        info['type'] = 'File'
        info['sender'] = control.GetProgenyControl(2, control_type='ButtonControl').Name
        info['sender_remark'] = control.GetProgenyControl(4, control_type='TextControl').Name
        info['time'] = control.GetProgenyControl(4, 1, control_type='TextControl').Name
        info['content'] = control.GetProgenyControl(8, control_type='TextControl').Name

    # Voice
    elif control.Name.startswith('[语音]'):
        info['type'] = 'Voice'
        info['sender'] = control.GetProgenyControl(2, control_type='ButtonControl').Name
        info['sender_remark'] = control.GetProgenyControl(4, control_type='TextControl').Name
        info['time'] = control.GetProgenyControl(4, 1, control_type='TextControl').Name
        info['content'] = control.Name

    # Sticker
    elif control.Name == '[动画表情]':
        info['type'] = 'Sticker'
        info['sender'] = control.GetProgenyControl(2, control_type='ButtonControl').Name
        info['sender_remark'] = control.GetProgenyControl(4, control_type='TextControl').Name
        info['time'] = control.GetProgenyControl(4, 1, control_type='TextControl').Name
        info['content'] = ""

    # VideoChannel
    elif control.Name == '[视频号]':
        info['type'] = 'VideoChannel'
        info['source'] = control.GetProgenyControl(8, -1, control_type='TextControl').Name
        info['sender'] = control.GetProgenyControl(2, control_type='ButtonControl').Name
        info['sender_remark'] = control.GetProgenyControl(4, control_type='TextControl').Name
        info['time'] = control.GetProgenyControl(4, 1, control_type='TextControl').Name
        info['content'] = control.Name

    # Link
    elif control.Name == '链接':
        info['type'] = 'Link'
        info['describe'] = control.GetProgenyControl(7, control_type='TextControl').Name
        info['sender'] = control.GetProgenyControl(2, control_type='ButtonControl').Name
        info['sender_remark'] = control.GetProgenyControl(4, control_type='TextControl').Name
        info['time'] = control.GetProgenyControl(4, 1, control_type='TextControl').Name
        info['content'] = control.GetProgenyControl(6, control_type='TextControl').Name

    # Music
    elif control.Name == '[音乐]':
        info['type'] = 'Music'
        info['describe'] = control.GetProgenyControl(8, -1, control_type='TextControl').Name
        info['sender'] = control.GetProgenyControl(2, control_type='ButtonControl').Name
        info['sender_remark'] = control.GetProgenyControl(4, control_type='TextControl').Name
        info['time'] = control.GetProgenyControl(4, 1, control_type='TextControl').Name
        info['content'] = control.GetProgenyControl(8, control_type='TextControl').Name

    else:
        # MiniProgram
        tempcontrol = control.GetProgenyControl(7, -1, control_type='TextControl')
        if tempcontrol and tempcontrol.Name == '小程序':
            info['type'] = 'MiniProgram'
            info['source'] = control.GetProgenyControl(7, control_type='TextControl').Name
            info['sender'] = control.GetProgenyControl(2, control_type='ButtonControl').Name
            info['sender_remark'] = control.GetProgenyControl(4, control_type='TextControl').Name
            info['time'] = control.GetProgenyControl(4, 1, control_type='TextControl').Name
            info['content'] = control.Name
    
        # Advertisement

    return info

def GetText(HWND):
    length = win32gui.SendMessage(HWND, win32con.WM_GETTEXTLENGTH)*2
    buffer = win32gui.PyMakeBuffer(length)
    win32api.SendMessage(HWND, win32con.WM_GETTEXT, length, buffer)
    address, length_ = win32gui.PyGetBufferAddressAndLen(buffer[:-1])
    text = win32gui.PyGetString(address, length_)[:int(length/2)]
    buffer.release()
    return text

def GetAllWindowExs(HWND):
    if not HWND:
        return
    handles = []
    win32gui.EnumChildWindows(
        HWND, lambda hwnd, param: param.append([hwnd, win32gui.GetClassName(hwnd), GetText(hwnd)]),  handles)
    return handles

def FindWindow(classname=None, name=None) -> int:
    return win32gui.FindWindow(classname, name)

def FindWinEx(HWND, classname=None, name=None) -> list:
    hwnds_classname = []
    hwnds_name = []
    def find_classname(hwnd, classname):
        classname_ = win32gui.GetClassName(hwnd)
        if classname_ == classname:
            if hwnd not in hwnds_classname:
                hwnds_classname.append(hwnd)
    def find_name(hwnd, name):
        name_ = GetText(hwnd)
        if name in name_:
            if hwnd not in hwnds_name:
                hwnds_name.append(hwnd)
    if classname:
        win32gui.EnumChildWindows(HWND, find_classname, classname)
    if name:
        win32gui.EnumChildWindows(HWND, find_name, name)
    if classname and name:
        hwnds = [hwnd for hwnd in hwnds_classname if hwnd in hwnds_name]
    else:
        hwnds = hwnds_classname + hwnds_name
    return hwnds

def ClipboardFormats(unit=0, *units):
    units = list(units)
    retry_count = 5
    while retry_count > 0:
        try:
            win32clipboard.OpenClipboard()
            try:
                u = win32clipboard.EnumClipboardFormats(unit)
            finally:
                win32clipboard.CloseClipboard()
            break
        except Exception as e:
            retry_count -= 1
    units.append(u)
    if u:
        units = ClipboardFormats(u, *units)
    return units

def ReadClipboardData():
    Dict = {}
    formats = ClipboardFormats()

    for i in formats:
        if i == 0:
            continue

        retry_count = 5
        while retry_count > 0:
            try:
                win32clipboard.OpenClipboard()
                try:
                    data = win32clipboard.GetClipboardData(i)
                    Dict[str(i)] = data
                finally:
                    win32clipboard.CloseClipboard()
                break
            except Exception as e:
                retry_count -= 1
    return Dict

# def ReadClipboardData():
#     Dict = {}
#     for i in ClipboardFormats():
#         if i == 0:
#             continue
#         win32clipboard.OpenClipboard()
#         try:
#             filenames = win32clipboard.GetClipboardData(i)
#             win32clipboard.CloseClipboard()
#         except:
#             win32clipboard.CloseClipboard()
#             raise ValueError
#         Dict[str(i)] = filenames
#     return Dict

def ParseWeChatTime(time_str):
    """
    时间格式转换函数

    Args:
        time_str: 输入的时间字符串

    Returns:
        转换后的时间字符串
    """
    
    match = re.match(r'^(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$', time_str)
    if match:
        month, day, hour, minute, second = match.groups()
        current_year = datetime.now().year
        return datetime(current_year, int(month), int(day), int(hour), int(minute), int(second)).strftime('%Y-%m-%d %H:%M:%S')
    
    match = re.match(r'^(\d{1,2}):(\d{1,2})$', time_str)
    if match:
        hour, minute = match.groups()
        return datetime.now().strftime('%Y-%m-%d') + f' {hour}:{minute}:00'

    match = re.match(r'^昨天 (\d{1,2}):(\d{1,2})$', time_str)
    if match:
        hour, minute = match.groups()
        yesterday = datetime.now() - timedelta(days=1)
        return yesterday.strftime('%Y-%m-%d') + f' {hour}:{minute}:00'

    match = re.match(r'^星期([一二三四五六日]) (\d{1,2}):(\d{1,2})$', time_str)
    if match:
        weekday, hour, minute = match.groups()
        weekday_num = ['一', '二', '三', '四', '五', '六', '日'].index(weekday)
        today_weekday = datetime.now().weekday()
        delta_days = (today_weekday - weekday_num) % 7
        target_day = datetime.now() - timedelta(days=delta_days)
        return target_day.strftime('%Y-%m-%d') + f' {hour}:{minute}:00'

    match = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日 (\d{1,2}):(\d{1,2})$', time_str)
    if match:
        year, month, day, hour, minute = match.groups()
        return datetime(*[int(i) for i in [year, month, day, hour, minute]]).strftime('%Y-%m-%d %H:%M:%S')
    
    match = re.match(r'^(\d{2})-(\d{2}) (上午|下午) (\d{1,2}):(\d{2})$', time_str)
    if match:
        month, day, period, hour, minute = match.groups()
        current_year = datetime.now().year
        hour = int(hour)
        if period == '下午' and hour != 12:
            hour += 12
        elif period == '上午' and hour == 12:
            hour = 0
        return datetime(current_year, int(month), int(day), hour, int(minute)).strftime('%Y-%m-%d %H:%M:%S')
    
    # all match failed
    return time_str


def RollIntoView(win, ele, equal=False):
    while ele.BoundingRectangle.ycenter() < win.BoundingRectangle.top or ele.BoundingRectangle.ycenter() >= win.BoundingRectangle.bottom:
        if ele.BoundingRectangle.ycenter() < win.BoundingRectangle.top:
            # 上滚动
            while True:
                win.WheelUp(wheelTimes=1)
                time.sleep(0.1)
                if equal:
                    if ele.BoundingRectangle.ycenter() >= win.BoundingRectangle.top:
                        break
                else:
                    if ele.BoundingRectangle.ycenter() > win.BoundingRectangle.top:
                        break

        elif ele.BoundingRectangle.ycenter() >= win.BoundingRectangle.bottom:
            # 下滚动
            while True:
                win.WheelDown(wheelTimes=1)
                time.sleep(0.1)
                if equal:
                    if ele.BoundingRectangle.ycenter() <= win.BoundingRectangle.bottom:
                        break
                else:
                    if ele.BoundingRectangle.ycenter() < win.BoundingRectangle.bottom:
                        break
        time.sleep(0.3)

wxlog = logging.getLogger('wxauto')
wxlog.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s')
console_handler.setFormatter(formatter)
wxlog.addHandler(console_handler)
wxlog.propagate = False

def set_debug(debug: bool):
    if debug:
        wxlog.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.DEBUG)
    else:
        wxlog.setLevel(logging.INFO)
        console_handler.setLevel(logging.INFO)
