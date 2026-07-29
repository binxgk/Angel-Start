"""
angel Start - 应用程序快捷启动工具

这是一个功能强大的应用程序启动器，支持：
- 应用程序快捷方式管理
- 拖拽排序功能  
- 分组管理
- 图标自定义
- 快捷键启动
- 系统托盘支持
- 网络图标缓存

主要功能模块：
1. IconManager: 图标管理器，支持网络图标下载和缓存
2. AppItem: 应用程序数据模型
3. AppListWidget: 自定义列表组件，支持拖拽操作
4. MainWindow: 主窗口，提供完整的用户界面

技术特点：
- 使用PySide6构建现代化GUI界面
- 支持拖拽排序和外部文件拖拽
- 智能图标管理和缓存机制
- 跨平台兼容性
"""

APP_VERSION = "1"

import json
import os
import sys
import ctypes
import ctypes.wintypes
import subprocess
import webbrowser
import threading
import hashlib
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
import random

from PySide6.QtCore import (
    Qt, QTimer, QSize, QUrl, QPoint, QByteArray, QRect, QMargins,
    QAbstractNativeEventFilter, Signal, QObject, 
    QThread, Slot, QLockFile
)
from PySide6.QtGui import QAction, QIcon, QGuiApplication, QClipboard, QKeyEvent, QColor, QPalette, QShortcut, QKeySequence, QPainter, QFont, QBrush, QPen
from PySide6.QtWidgets import QStyle, QLineEdit, QGraphicsDropShadowEffect, QStyledItemDelegate
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QStackedWidget,
    QListWidget,
    QListWidgetItem,
    QToolBar,
    QFileDialog,
    QLineEdit,
    QSystemTrayIcon,
    QMenu,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QComboBox,
    QSpinBox,
    QMessageBox,
    QInputDialog,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QFileInfo
from PySide6.QtWidgets import QFileIconProvider
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

# 极简扁平化主题（样式 / 结构分离）：颜色、QSS、线性 SVG 图标
import theme


# 检测是否在打包环境中运行
def _is_packaged():
    """检测是否在打包环境中运行（PyInstaller, Nuitka, cx_Freeze等）"""
    if hasattr(sys, '_MEIPASS'):
        return True
    if getattr(sys, 'frozen', False):
        return True
    if "__compiled__" in globals():
        return True
    # 兜底：sys.executable 不是python解释器则为打包环境
    exe_name = os.path.basename(sys.executable).lower()
    if not exe_name.startswith('python'):
        return True
    return False

# 确定应用程序目录
def get_app_directory():
    """
    获取应用程序根目录
    
    在开发环境中返回脚本所在目录，
    在PyInstaller打包环境中返回exe所在目录（不是_MEIPASS临时目录）
    在Nuitka打包环境中返回exe所在目录（不是TEMP解压目录）
    
    Returns:
        str: 应用程序目录路径
    """
    if _is_packaged():
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        # Nuitka --onefile 可能将 sys.executable 也指向TEMP解压目录
        # 检测到TEMP目录时回退到 sys.argv[0]（始终为用户启动的原始exe路径）
        temp_dir = os.path.normpath(os.environ.get('TEMP', os.environ.get('TMP', ''))).lower()
        if temp_dir and os.path.normpath(exe_dir).lower().startswith(temp_dir):
            return os.path.dirname(os.path.abspath(sys.argv[0]))
        return exe_dir
    else:
        # 开发环境：返回脚本所在目录
        return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_directory()
DATA_DIR = os.path.join(APP_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
DATA_FILE = os.environ.get("LAUNCHER_DATA_FILE", os.path.join(DATA_DIR, "launcher.json"))
LOG_FILE = os.path.join(DATA_DIR, "launch_log.json")  # 快捷方式启动日志
LOG_MAX_ENTRIES = 1000  # 启动日志最多保留条数（超出自动裁剪最早的记录）

# 中间内容区背景图文件夹（用户自行放入图片，随机轮播）
BACKGROUND_DIR = os.path.join(DATA_DIR, "backgrounds")
BG_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif")


def ensure_dirs():
    for d in [DATA_DIR, CACHE_DIR, BACKGROUND_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)
    # 背景文件夹说明（首次启动写入）
    readme = os.path.join(BACKGROUND_DIR, "说明.txt")
    if not os.path.exists(readme):
        try:
            with open(readme, "w", encoding="utf-8") as f:
                f.write(
                    "把图片放进这个文件夹，启动器中间内容区会自动作为背景图随机轮播。\n"
                    "支持格式：png / jpg / jpeg / bmp / webp / gif\n"
                    "轮换间隔在「设置 → 背景轮播间隔」中调整（单位：秒）。\n"
                    "文件夹为空或没有图片时，背景回退为纯色。\n"
                )
        except Exception:
            pass


def scan_background_images():
    """扫描背景文件夹中的图片，返回绝对路径列表（按文件名排序）。"""
    if not os.path.isdir(BACKGROUND_DIR):
        return []
    files = []
    for fn in os.listdir(BACKGROUND_DIR):
        if fn.lower().endswith(BG_IMAGE_EXTS):
            files.append(os.path.join(BACKGROUND_DIR, fn))
    return sorted(files)


def is_url(s: str) -> bool:
    return s.startswith(("http://", "https://", "file://"))


def get_resource_path(relative_path):
    """
    获取资源的绝对路径，兼容开发环境和打包环境
    
    在PyInstaller打包环境中，配置文件等数据文件在exe目录，
    而程序资源（如图标）在_MEIPASS临时目录中
    在Nuitka打包环境中，优先查找exe目录，再查找解压临时目录
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包环境：资源文件在临时目录；优先用exe同目录的自定义图标
        exe_dir_path = os.path.join(os.path.dirname(sys.executable), relative_path)
        if os.path.exists(exe_dir_path):
            return exe_dir_path
        return os.path.join(sys._MEIPASS, relative_path)
    elif _is_packaged():
        # Nuitka等打包环境：先查exe目录（用户手动放置），再查__file__目录（bundled资源）
        exe_dir_path = os.path.join(os.path.dirname(sys.executable), relative_path)
        if os.path.exists(exe_dir_path):
            return exe_dir_path
        file_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)
        if os.path.exists(file_dir_path):
            return file_dir_path
        return exe_dir_path
    else:
        # 开发环境：所有文件都在APP_DIR
        return os.path.join(APP_DIR, relative_path)


def resolve_shortcut(path: str):
    """
    解析 Windows 快捷方式 (.lnk) 获取真实目标路径和启动参数
    """
    if not path.lower().endswith('.lnk'):
        return path, ""
        
    try:
        # 使用 PowerShell 解析快捷方式
        safe_path = path.replace("'", "''")
        cmd = [
            'powershell', 
            '-NoProfile', 
            '-NonInteractive', 
            '-Command',
            f"$sh=New-Object -ComObject WScript.Shell;$s=$sh.CreateShortcut('{safe_path}');Write-Output ($s.TargetPath + '|||' + $s.Arguments)"
        ]
        
        # 配置启动信息以隐藏窗口
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # 尝试使用 CREATE_NO_WINDOW (Python 3.7+)
        creationflags = 0
        if hasattr(subprocess, 'CREATE_NO_WINDOW'):
            creationflags = subprocess.CREATE_NO_WINDOW
            
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            startupinfo=startupinfo,
            creationflags=creationflags
        )
        
        output = result.stdout.strip()
        parts = output.split('|||', 1)
        target = parts[0].strip()
        arguments = parts[1].strip() if len(parts) > 1 else ""
        if target and os.path.exists(target):
            return target, arguments
            
    except Exception as e:
        print(f"解析快捷方式失败: {e}")
        
    return path, ""


def url_domain(u: str) -> str:
    try:
        parsed = QUrl(u)
        host = parsed.host().lower()
        return host
    except Exception:
        return ""


class IconManager(QObject):
    icon_loaded = Signal(str, QIcon)
    
    def __init__(self):
        super().__init__()
        self.nam = QNetworkAccessManager()
        self.cache = {}
        self.icon_cache = {}
        self.icon_requested = set()

    def get_favicon(self, url: str):
        domain = url_domain(url)
        if not domain:
            return
        
        cache_key = hashlib.md5(domain.encode()).hexdigest()
        if cache_key in self.icon_requested:
            return
        self.icon_requested.add(cache_key)
        
        cache_path = os.path.join(CACHE_DIR, f"{cache_key}.png")
        
        if os.path.exists(cache_path):
            self.icon_loaded.emit(url, QIcon(cache_path))
            self.icon_requested.discard(cache_key)
            return

        fav_url = f"https://{domain}/favicon.ico"
        reply = self.nam.get(QNetworkRequest(QUrl(fav_url)))
        reply.finished.connect(lambda: self._handle_reply(reply, url, cache_path, cache_key))

    def _handle_reply(self, reply: QNetworkReply, original_url: str, cache_path: str, cache_key: str):
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pix = QPixmap()
            if pix.loadFromData(data):
                pix.save(cache_path)
                self.icon_loaded.emit(original_url, QIcon(pix))
        self.icon_requested.discard(cache_key)
        reply.deleteLater()

_ICON_MANAGER = None
def get_icon_manager():
    global _ICON_MANAGER
    if _ICON_MANAGER is None:
        _ICON_MANAGER = IconManager()
    return _ICON_MANAGER


_BROWSER_ICON_CACHE = None
def get_browser_default_icon() -> QIcon:
    """生成蓝色圆角矩形+白色E字母的浏览器默认图标"""
    global _BROWSER_ICON_CACHE
    if _BROWSER_ICON_CACHE is not None:
        return _BROWSER_ICON_CACHE
    pix = QPixmap(48, 48)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QBrush(QColor("#1a73e8")))
    painter.setPen(Qt.NoPen)
    from PySide6.QtCore import QRectF
    painter.drawRoundedRect(QRectF(2, 2, 44, 44), 8, 8)
    painter.setPen(QPen(QColor("#ffffff")))
    font = QFont("Arial", 28, QFont.Bold)
    painter.setFont(font)
    painter.drawText(QRectF(2, 2, 44, 44), Qt.AlignCenter, "E")
    painter.end()
    _BROWSER_ICON_CACHE = QIcon(pix)
    return _BROWSER_ICON_CACHE


def open_properties(path: str):
    try:
        if os.path.isfile(path) or os.path.isdir(path):
            path = os.path.abspath(path)
            
            class SHELLEXECUTEINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_uint32),
                    ("fMask", ctypes.c_uint32),
                    ("hwnd", ctypes.c_void_p),
                    ("lpVerb", ctypes.c_wchar_p),
                    ("lpFile", ctypes.c_wchar_p),
                    ("lpParameters", ctypes.c_wchar_p),
                    ("lpDirectory", ctypes.c_wchar_p),
                    ("nShow", ctypes.c_int),
                    ("hInstApp", ctypes.c_void_p),
                    ("lpIDList", ctypes.c_void_p),
                    ("lpClass", ctypes.c_wchar_p),
                    ("hKeyClass", ctypes.c_void_p),
                    ("dwHotKey", ctypes.c_uint32),
                    ("hIcon", ctypes.c_void_p),
                    ("hProcess", ctypes.c_void_p),
                ]
            
            see_mask_invokeidlist = 0x0000000C
            see_mask_noasync = 0x00000100
            
            info = SHELLEXECUTEINFO()
            info.cbSize = ctypes.sizeof(SHELLEXECUTEINFO)
            info.fMask = see_mask_invokeidlist | see_mask_noasync
            info.hwnd = None
            info.lpVerb = "properties"
            info.lpFile = path
            info.lpParameters = None
            info.lpDirectory = None
            info.nShow = 1
            info.lpIDList = None
            info.lpClass = None
            info.hKeyClass = None
            info.dwHotKey = 0
            info.hIcon = None
            info.hProcess = None
            
            result = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info))
            if not result:
                subprocess.Popen(["explorer", "/select,", path])
        else:
            QMessageBox.warning(None, "属性", "无法打开属性：仅支持文件和文件夹")
    except Exception as e:
        print(f"Open properties error: {e}")
        try:
            subprocess.Popen(["explorer", "/select,", path])
        except:
            QMessageBox.warning(None, "属性", "无法打开属性窗口")


def open_in_explorer(path: str):
    try:
        path = os.path.normpath(path)
        if os.path.isdir(path):
            subprocess.Popen(["explorer", path])
        else:
            subprocess.Popen(["explorer", "/select,", path])
    except Exception:
        QMessageBox.warning(None, "打开文件夹", "无法打开资源管理器")


def launch_target(target: str, work_dir: str = None, launch_args: str = None):
    try:
        if is_url(target):
            webbrowser.open(target)
        else:
            cmd = f'"{target}"'
            if launch_args:
                cmd += f' {launch_args}'
            if work_dir and os.path.exists(work_dir):
                # 如果指定了起始位置，使用 subprocess 启动
                subprocess.Popen(cmd, shell=True, cwd=work_dir)
            else:
                if launch_args:
                    subprocess.Popen(cmd, shell=True)
                else:
                    os.startfile(target)
    except Exception as e:
        print(f"启动失败: {e}")
        # QMessageBox.warning(None, "启动失败", f"无法启动: {target}")

# create_desktop_shortcut definition moved to later in file to avoid NameError
# create_desktop_shortcut code moved to later in file

def log_launch(item, source: str, enabled: bool = True):
    """记录一次快捷方式启动事件到 data/launch_log.json

    Args:
        item: AppItem 实例
        source: 触发来源，如 "双击" / "单击" / "搜索回车" / "热键" / "批量"
        enabled: 是否启用日志（来自设置 enable_launch_log）
    """
    if not enabled:
        return
    try:
        ensure_dirs()
        records = []
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    records = json.load(f)
                if not isinstance(records, list):
                    records = []
            except Exception:
                records = []

        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "name": getattr(item, "name", ""),
            "group": getattr(item, "group", ""),
            "source": source,
            "target": getattr(item, "target", ""),
        }
        records.append(record)

        # 自动裁剪，仅保留最近 LOG_MAX_ENTRIES 条
        if len(records) > LOG_MAX_ENTRIES:
            records = records[-LOG_MAX_ENTRIES:]

        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Log] 写入启动日志失败: {e}")


@dataclass
class AppItem:
    name: str
    target: str
    remarks: str = ""
    group: str = "默认"
    icon_path: str = ""  # 自定义图标
    work_dir: str = ""   # 起始位置
    launch_args: str = "" # 启动参数
    hotkey: str = ""     # 启动热键
    click_count: int = 0 # 点击次数

    def matches(self, text: str) -> bool:
        t = text.lower().strip()
        if not t:
            return True
        name_match = t in self.name.lower()
        remarks_match = t in self.remarks.lower()
        target_match = t in self.target.lower()
        return name_match or remarks_match or target_match


def create_desktop_shortcut(item: AppItem):
    try:
        # 通过注册表获取真实的桌面路径（兼容 OneDrive 等重定向情况）
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
        try:
            desktop = winreg.QueryValueEx(key, "Desktop")[0]
        except Exception:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        finally:
            key.Close()
            
        if not os.path.exists(desktop):
            os.makedirs(desktop)
        
        # Sanitize filename
        safe_name = "".join([c for c in item.name if c not in r'\/:*?"<>|']).strip()
        if not safe_name:
            safe_name = "QuickLauncher_Shortcut"
            
        if is_url(item.target):
            path = os.path.join(desktop, f"{safe_name}.url")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"[InternetShortcut]\nURL={item.target}\n")
        else:
            path = os.path.join(desktop, f"{safe_name}.lnk")
            path = os.path.abspath(path)
            # 确保目标路径是绝对路径
            target = item.target 
            if not is_url(target) and not os.path.isabs(target):
                 # 尝试解析为绝对路径，如果只是命令则保持原样
                 if os.path.exists(target):
                     target = os.path.abspath(target)
            
            vbs_path = path.replace('"', '""')
            vbs_target = target.replace('"', '""')
            vbs_desc = item.remarks.replace('"', '""')
            
            work_dir = item.work_dir if hasattr(item, 'work_dir') and item.work_dir else ""
            if not work_dir and os.path.exists(target) and os.path.isfile(target):
                work_dir = os.path.dirname(target)
            
            vbs_work = os.path.abspath(work_dir).replace('"', '""') if work_dir else ""
            
            script_lines = [
                'Set oWS = WScript.CreateObject("WScript.Shell")',
                f'sLinkFile = "{vbs_path}"',
                'Set oLink = oWS.CreateShortcut(sLinkFile)',
                f'oLink.TargetPath = "{vbs_target}"',
                f'oLink.Description = "{vbs_desc}"'
            ]
            
            if hasattr(item, 'launch_args') and item.launch_args:
                vbs_args = item.launch_args.replace('"', '""')
                script_lines.append(f'oLink.Arguments = "{vbs_args}"')
            if vbs_work:
                script_lines.append(f'oLink.WorkingDirectory = "{vbs_work}"')
            
            if item.icon_path and os.path.exists(item.icon_path):
                 vbs_icon = os.path.abspath(item.icon_path).replace('"', '""')
                 script_lines.append(f'oLink.IconLocation = "{vbs_icon}"')
            
            script_lines.append('oLink.Save')
            
            vbs_content = "\n".join(script_lines)
            
            temp_vbs = os.path.join(os.environ["TEMP"], f"mklink_{os.getpid()}.vbs")
            # Write using system locale (mbcs) for Chinese path support
            with open(temp_vbs, 'w', encoding='mbcs') as f:
                f.write(vbs_content)
                
            subprocess.run(["cscript", "//Nologo", temp_vbs], check=True, shell=True)
            try:
                os.remove(temp_vbs)
            except:
                pass

        QMessageBox.information(None, "成功", f"桌面快捷方式已创建:\n{safe_name}")

    except Exception as e:
        print(f"Shortcut creation error: {e}")
        QMessageBox.warning(None, "错误", f"创建快捷方式失败: {e}")


class LauncherModel:
    def __init__(self):
        self.groups: Dict[str, List[AppItem]] = {}
        self.settings:Dict = {
            "hotkeys": {
                "show_hide": "Ctrl+Alt+Q",
                "opacity_up": "Alt+Up",
                "opacity_down": "Alt+Down",
                "lock": "Ctrl+L",
                "unlock": "Ctrl+U",
                "next_group": "Ctrl+`",
                "prev_group": "Ctrl+1"
            },
            "autostart": False,
            "theme": "light",
            "icon_size": 48,
            "window_size": [800, 500],
            "toolbar_area": Qt.TopToolBarArea.value,
            "sort_order": "default",
            "start_hidden": False,
            "group_sort_order": {},
            "auto_backup": "none",
            "backup_dir": os.path.join(APP_DIR, "bak"),
            "last_backup_time": "",
            "auto_cleanup_backup": True,
            "backup_keep_count": 20,
            "enable_launch_log": True  # 是否记录快捷方式启动日志
        }

    def load(self):
        ensure_dirs()
        if not os.path.exists(DATA_FILE):
            self.groups = {"默认": []}
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 手动处理 AppItem 数据加载，兼容旧版本配置
            self.groups = {}
            valid_fields = {'name', 'target', 'remarks', 'group', 'icon_path', 'work_dir', 'launch_args', 'hotkey', 'click_count'}
            
            for g, items in data.get("groups", {}).items():
                app_items = []
                for item in items:
                    # 过滤掉不认识的字段，防止 TypeError
                    filtered_item = {k: v for k, v in item.items() if k in valid_fields}
                    # work_dir 等新增字段由 dataclass 默认值处理
                    app_items.append(AppItem(**filtered_item))
                self.groups[g] = app_items

            if "settings" in data:
                # 深度更新 settings，防止 window_size 被默认值覆盖
                self.settings.update(data["settings"])
            if not self.groups:
                self.groups = {"默认": []}
        except Exception as e:
            print(f"Error loading config: {e}")
            self.groups = {"默认": []}

    def save(self):
        ensure_dirs()
        data = {
            "groups": {g: [asdict(i) for i in items] for g, items in self.groups.items()},
            "settings": self.settings
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_item(self, item: AppItem):
        self.groups.setdefault(item.group, []).append(item)

    def remove_item(self, group: str, index: int):
        if group in self.groups and 0 <= index < len(self.groups[group]):
            del self.groups[group][index]

    def update_item(self, group: str, index: int, item: AppItem):
        if group in self.groups and 0 <= index < len(self.groups[group]):
            self.groups[group][index] = item
    
    def move_item(self, group: str, from_idx: int, to_idx: int):
        if group in self.groups:
            items = self.groups[group]
            if 0 <= from_idx < len(items) and 0 <= to_idx <= len(items):
                # 允许插入到列表末尾
                item = items.pop(from_idx)
                # 调整目标索引，如果从前面移到后面，需要修正索引
                if from_idx < to_idx:
                    to_idx -= 1
                items.insert(to_idx, item)


class GroupSortDialog(QDialog):
    """分组排序对话框，支持上下移动调整分组顺序和排序数字"""
    def __init__(self, parent=None, group_names: list = None, group_sort_order: dict = None):
        super().__init__(parent)
        self.setWindowTitle("分组排序")
        self.setMinimumWidth(400)
        self.setMinimumHeight(350)
        self._sort_order = dict(group_sort_order) if group_sort_order else {}
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        hint = QLabel("拖拽或使用按钮调整分组顺序，修改排序数字（数字越小越靠前，默认255）：")
        layout.addWidget(hint)
        
        self.list_widget = QListWidget(self)
        self.list_widget.setDragDropMode(QListWidget.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)
        self.list_widget.setMinimumHeight(200)
        for name in (group_names or []):
            self.list_widget.addItem(name)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        layout.addWidget(self.list_widget)
        
        # 排序数字编辑区
        sort_row = QHBoxLayout()
        self.sort_spin = QSpinBox(self)
        self.sort_spin.setRange(0, 999)
        self.sort_spin.setValue(255)
        self.sort_spin.setPrefix("排序: ")
        self.sort_spin.setMinimumHeight(30)
        sort_row.addWidget(self.sort_spin)
        apply_sort_btn = QPushButton("应用到选中分组", self)
        apply_sort_btn.setCursor(Qt.PointingHandCursor)
        apply_sort_btn.setStyleSheet("border: 1px solid #cccccc;  padding: 5px 10px;")
        apply_sort_btn.clicked.connect(self._apply_sort_to_selected)
        sort_row.addWidget(apply_sort_btn)
        layout.addLayout(sort_row)
        
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        
        btn_row = QHBoxLayout()
        up_btn = QPushButton("⬆ 上移", self)
        down_btn = QPushButton("⬇ 下移", self)
        up_btn.clicked.connect(self._move_up)
        down_btn.clicked.connect(self._move_down)
        up_btn.setCursor(Qt.PointingHandCursor)
        down_btn.setCursor(Qt.PointingHandCursor)
        btn_row.addWidget(up_btn)
        btn_row.addWidget(down_btn)
        layout.addLayout(btn_row)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        ok_btn = btns.button(QDialogButtonBox.Ok)
        ok_btn.setText("确定")
        cancel_btn = btns.button(QDialogButtonBox.Cancel)
        cancel_btn.setText("取消")
        for btn in btns.buttons():
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("border: 1px solid #cccccc;  padding: 5px 10px;")
        layout.addWidget(btns)
    
    def _move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            self.list_widget.setCurrentRow(row - 1)
    
    def _move_down(self):
        row = self.list_widget.currentRow()
        if row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            self.list_widget.setCurrentRow(row + 1)
    
    def _on_row_changed(self, row):
        if row >= 0:
            name = self.list_widget.item(row).text()
            self.sort_spin.setValue(self._sort_order.get(name, 255))

    def _apply_sort_to_selected(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            name = self.list_widget.item(row).text()
            self._sort_order[name] = self.sort_spin.value()

    def get_order(self) -> list:
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

    def get_sort_order(self) -> dict:
        return dict(self._sort_order)


class ItemEditor(QDialog):
    def __init__(self, parent=None, item: Optional[AppItem] = None, mode: str = "file", current_index: int = -1):
        super().__init__(parent)
        self.setWindowTitle("编辑应用项")
        self.setMinimumWidth(500)
        self.setMinimumHeight(450)
        self.item = item
        self.current_index = current_index
        
        layout = QFormLayout(self)
        layout.setSpacing(15)  # 增加行间距
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.name_edit = QLineEdit(self)
        self.path_edit = QLineEdit(self)
        self.work_dir_edit = QLineEdit(self) # 起始位置
        self.remarks_edit = QLineEdit(self)
        self.group_edit = QLineEdit(self)
        self.icon_edit = QLineEdit(self)
        self.args_edit = QLineEdit(self) # 启动参数
        self.hotkey_edit = HotkeyInputWidget(self, placeholder="无") # 启动热键
        self.position_spin = QSpinBox(self)

        # 增加输入框高度
        self.name_edit.setMinimumHeight(35)
        self.path_edit.setMinimumHeight(35)
        self.work_dir_edit.setMinimumHeight(35)
        self.remarks_edit.setMinimumHeight(35)
        self.group_edit.setMinimumHeight(35)
        self.icon_edit.setMinimumHeight(35)
        self.args_edit.setMinimumHeight(35)
        self.hotkey_edit.setMinimumHeight(35)
        self.position_spin.setMinimumHeight(35)

        self.name_edit.setPlaceholderText("显示名称")
        self.path_edit.setPlaceholderText("路径、URL 或 命令")
        self.work_dir_edit.setPlaceholderText("起始位置 (可选)")
        self.remarks_edit.setPlaceholderText("备注信息")
        self.group_edit.setPlaceholderText("分组名称")
        self.icon_edit.setPlaceholderText("自定义图标路径（可选）")
        self.args_edit.setPlaceholderText("启动参数 (可选)")

        # 排序序号设置
        if parent and hasattr(parent, 'model') and hasattr(parent, 'current_group'):
            group_items = parent.model.groups.get(parent.current_group(), [])
            if current_index >= 0:
                # 编辑现有项目
                self.position_spin.setRange(1, len(group_items))
                self.position_spin.setValue(current_index + 1)
            else:
                # 添加新项目，位置范围应该是1到len+1（允许插入到末尾）
                self.position_spin.setRange(1, len(group_items) + 1)
                self.position_spin.setValue(len(group_items) + 1)
        else:
            self.position_spin.setRange(1, 999)
            self.position_spin.setValue(1)

        layout.addRow("名称", self.name_edit)
        layout.addRow("目标", self.path_edit)
        
        browse_row = QWidget()
        bh = QVBoxLayout(browse_row)
        bh.setContentsMargins(0,0,0,0)
        
        browse_btn = QLabel("📁 浏览文件/文件夹")
        browse_btn.setStyleSheet("color: #1677ff; cursor: pointer; font-size: 14px;")
        browse_btn.mousePressEvent = lambda e: self._browse(mode)
        bh.addWidget(browse_btn)
        
        layout.addRow("", browse_row)
        self.work_dir_label = QLabel("起始位置")
        layout.addRow(self.work_dir_label, self.work_dir_edit)
        # 文件夹模式下隐藏起始位置
        if mode == "folder":
            self.work_dir_label.setVisible(False)
            self.work_dir_edit.setVisible(False)
        layout.addRow("启动参数", self.args_edit)
        layout.addRow("启动热键", self.hotkey_edit)
        layout.addRow("排序位置", self.position_spin)
        layout.addRow("备注", self.remarks_edit)
        layout.addRow("分组", self.group_edit)
        icon_row = QWidget()
        icon_lay = QHBoxLayout(icon_row)
        icon_lay.setContentsMargins(0, 0, 0, 0)
        icon_lay.addWidget(self.icon_edit)
        icon_browse_btn = QPushButton("📁 浏览图标", self)
        icon_browse_btn.setCursor(Qt.PointingHandCursor)
        icon_browse_btn.setMinimumHeight(35)
        icon_browse_btn.setStyleSheet("border: 1px solid #cccccc;  padding: 5px 10px;")
        icon_browse_btn.clicked.connect(self._browse_icon)
        icon_lay.addWidget(icon_browse_btn)
        layout.addRow("图标路径", icon_row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        btns.setMinimumHeight(40)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        
        for btn in btns.buttons():
            btn.setCursor(Qt.PointingHandCursor)
        
        ok_btn = btns.button(QDialogButtonBox.Ok)
        ok_btn.setText("确定")
        cancel_btn = btns.button(QDialogButtonBox.Cancel)
        cancel_btn.setText("取消")
        if ok_btn and cancel_btn:
            ok_btn.setStyleSheet("border: 1px solid #cccccc;  padding: 5px 10px;")
            cancel_btn.setStyleSheet("border: 1px solid #cccccc;  padding: 5px 10px;")
        
        layout.addRow(btns)

        if item:
            self.name_edit.setText(item.name)
            self.path_edit.setText(item.target)
            self.work_dir_edit.setText(item.work_dir if hasattr(item, 'work_dir') else "")
            self.args_edit.setText(item.launch_args if hasattr(item, 'launch_args') else "")
            self.remarks_edit.setText(item.remarks)
            self.group_edit.setText(item.group)
            self.icon_edit.setText(item.icon_path)
            self.hotkey_edit.set_hotkey_string(item.hotkey if hasattr(item, 'hotkey') else "")

    def _browse(self, mode):
        if mode == "folder":
            path = QFileDialog.getExistingDirectory(self, "选择文件夹", os.path.expanduser("~"))
        else:
            path, _ = QFileDialog.getOpenFileName(self, "选择文件", os.path.expanduser("~"), "所有文件 (*.*)")
        
        if path:
            self.path_edit.setText(path)
            # 自动填充起始位置为文件所在目录
            if mode != "folder" and os.path.exists(path):
                self.work_dir_edit.setText(os.path.dirname(path))
            
            if not self.name_edit.text():
                self.name_edit.setText(os.path.splitext(os.path.basename(path))[0])

    def _browse_icon(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图标文件", os.path.expanduser("~"),
            "图标文件 (*.ico *.png *.jpg *.jpeg *.bmp *.svg);;所有文件 (*.*)"
        )
        if path:
            self.icon_edit.setText(path)

    def get_item(self) -> Optional[AppItem]:
        name = self.name_edit.text().strip()
        target = self.path_edit.text().strip()
        if not name or not target:
            return None
        return {
            'item': AppItem(
                name=name,
                target=target,
                remarks=self.remarks_edit.text().strip(),
                group=self.group_edit.text().strip() or "默认",
                icon_path=self.icon_edit.text().strip(),
                work_dir=self.work_dir_edit.text().strip(),
                launch_args=self.args_edit.text().strip(),
                hotkey=self.hotkey_edit.get_hotkey_string().strip()
            ),
            'position': self.position_spin.value()
        }


class AppCardDelegate(QStyledItemDelegate):
    """图标卡片委托：极简圆角卡片 + hover 提升 2px + 柔和阴影（主题感知）

    使用自定义委托而非纯 QSS，是因为 Qt 样式表不支持 transform / box-shadow，
    而委托可在保留 QListWidget 全部交互（拖拽排序、点击启动、多选）的前提下自绘特效。
    """

    def paint(self, painter, option, index):
        c = theme.ACTIVE
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # 兜底：先覆盖整格底色，盖住 Qt 默认选中/聚焦黑底（IconMode 下易复现）
        painter.setBrush(QColor(c["card_bg"]))
        painter.setPen(Qt.NoPen)
        painter.drawRect(option.rect)

        rect = option.rect.adjusted(5, 5, -5, -5)
        hover = bool(option.state & QStyle.State_MouseOver)
        selected = bool(option.state & QStyle.State_Selected)
        pressed = bool(option.state & QStyle.State_Sunken)

        if hover or pressed:
            rect = rect.translated(0, -2)
            # 柔和阴影：在卡片下方绘制半透明圆角矩形
            shadow = QRect(rect)
            shadow += QMargins(0, 3, 0, 3)
            painter.setBrush(QColor(0, 0, 0, 35))
            painter.setPen(Qt.NoPen)
            painter.drawRect(shadow)

        # 卡片底色
        if selected:
            # 用主色叠整数 alpha（QColor 不支持小数 alpha 的 rgba 字符串，此前导致 INVALID→黑底）
            base = QColor(c["primary"])
            bg = QColor(base.red(), base.green(), base.blue(), 51)
        elif hover:
            bg = QColor(c["hover"])
        else:
            bg = QColor(c["card_bg"])
        painter.setBrush(bg)
        painter.setPen(QPen(QColor(c["border"]), 1))
        painter.drawRect(rect)

        # 图标（居中上方）
        icon = index.data(Qt.DecorationRole)
        if isinstance(icon, QIcon):
            icon.paint(painter, rect.x() + (rect.width() - 48) // 2, rect.y() + 8,
                       48, 48, Qt.AlignCenter, QIcon.Normal)

        # 名称（卡片下方，自动换行 + 省略）
        text = index.data(Qt.DisplayRole) or ""
        painter.setPen(QColor(c["text"]))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        text_rect = QRect(rect.x() + 2, rect.y() + 58, rect.width() - 4, rect.height() - 60)
        painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, text)
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(90, 90)


class BackgroundLabel(QWidget):
    """中间内容区背景层：保持比例裁剪铺满（桌面壁纸「填充」效果）。
    无图时显示回退纯色。绘制在内容栈下层，QListWidget 背景透明后透出。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._fallback = QColor("#a6e3e9")

    def set_pixmap(self, pm):
        self._pixmap = pm
        self.update()

    def set_fallback_color(self, color):
        self._fallback = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        target = self.rect()
        if self._pixmap and not self._pixmap.isNull():
            pm = self._pixmap
            src_ratio = pm.width() / pm.height() if pm.height() else 1.0
            dst_ratio = target.width() / target.height() if target.height() else 1.0
            if src_ratio > dst_ratio:
                # 图片更宽：按高度缩放后裁剪左右
                h = pm.height()
                w = int(round(h * dst_ratio))
                x = (pm.width() - w) // 2
                src = QRect(x, 0, w, h)
            else:
                # 图片更高或更方：按宽度缩放后裁剪上下
                w = pm.width()
                h = int(round(w / dst_ratio))
                y = (pm.height() - h) // 2
                src = QRect(0, y, w, h)
            painter.drawPixmap(target, pm, src)
        else:
            painter.fillRect(target, self._fallback)


class AppListWidget(QListWidget):
    """
    自定义列表组件，提供应用程序图标视图和拖拽功能
    
    这个组件继承自QListWidget，专门用于显示和管理应用程序快捷方式。
    主要特点：
    - 图标模式显示，视觉效果更佳
    - 支持内部拖拽排序
    - 支持外部文件拖拽添加
    - 智能插入位置计算
    - 上下文菜单支持
    """
    
    def __init__(self, parent=None, group_name: str = "默认"):
        """
        初始化应用程序列表组件
        
        Args:
            parent: 父组件
            group_name: 分组名称，用于标识这个列表所属的分组
        """
        super().__init__(parent)
        self.group_name = group_name
        
        # 设置列表显示模式为图标模式
        self.setViewMode(QListWidget.IconMode)
        self.setResizeMode(QListWidget.Adjust)  # 调整大小模式
        self.setIconSize(QSize(48, 48))  # 图标大小为48x48像素
        
        # 设置网格大小，统一单元格大小，包含图标和文字
        self.setGridSize(QSize(90, 90))
        self.setSpacing(10)  # 项目间距
        
        # 设置拖拽模式
        self.setDragDropMode(QListWidget.InternalMove)  # 允许内部移动
        self.setDefaultDropAction(Qt.MoveAction)  # 默认动作为移动
        self.setAcceptDrops(True)  # 接受拖拽
        
        # 允许拖拽，拖拽后自动对齐
        self.setMovement(QListWidget.Snap)
        self.setSelectionMode(QListWidget.ExtendedSelection)  # 多选模式(Ctrl/Shift)
        
        # 连接信号和槽
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemDoubleClicked.connect(self._launch_item)
        self.itemClicked.connect(self._on_item_clicked)
        self.setMouseTracking(True)
        self.itemEntered.connect(self._on_item_entered)
        
        # 连接图标管理器的信号
        im = get_icon_manager()
        im.icon_loaded.connect(self._on_icon_loaded)

        # 使用自定义委托绘制圆角卡片 + hover 特效（保留全部交互）
        self.setItemDelegate(AppCardDelegate(self))

        # 选中态背景完全交由 AppCardDelegate 绘制（薄荷绿），禁用 Qt 原生选中高亮
        # （Windows 原生样式下 IconMode 选中会用 QPalette.Highlight 画黑/深色底，QSS 透明无法完全覆盖）
        _pal = self.palette()
        _pal.setColor(QPalette.Highlight, QColor(0, 0, 0, 0))
        _pal.setColor(QPalette.HighlightedText, QColor(theme.ACTIVE["text"]))
        self.setPalette(_pal)

    def keyPressEvent(self, event):
        """
        键盘按键事件处理
        
        支持回车键和回车键快捷启动选中的项目
        
        Args:
            event: 键盘事件
        """
        # 检查是否按下回车键或回车键
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            item = self.currentItem()
            if item:
                # 启动选中的项目
                self._launch_item(item)
                # 运行后隐藏主窗口（可选，通常符合用户预期）
                if self.window():
                    self.window().hide()
                return  # 事件已处理，不再传递给父类
        super().keyPressEvent(event)

    def _on_icon_loaded(self, url, icon):
        """
        图标加载完成的回调函数
        
        当IconManager异步加载完成网络图标后，会调用此函数来更新
        列表中对应URL的项目图标。
        
        Args:
            url: 目标URL（应用程序链接）
            icon: 加载完成的图标对象
        """
        # 遍历列表中的所有项目
        for i in range(self.count()):
            it = self.item(i)
            app: AppItem = it.data(Qt.UserRole)
            # 找到匹配URL的项目并更新图标
            if app.target == url:
                it.setIcon(icon)

    def populate(self, items: List[AppItem]):
        """
        填充列表数据
        
        清空当前列表并重新填充给定的应用程序项目列表。
        
        Args:
            items: 应用程序项目列表
        """
        # 清空当前列表
        self.clear()
        # 逐个添加项目，序号从1开始
        for index, item in enumerate(items, 1):
            self.add_app_item_with_index(item, index)

    def add_app_item_with_index(self, item: AppItem, index: int):
        """
        添加带序号的应用程序项目
        
        创建一个新的列表项目，包含图标、名称、工具提示和数据。
        
        Args:
            item: 应用程序数据模型
            index: 显示序号（从1开始）
        """
        # 获取项目图标
        icon = self._get_icon(item)
        
        # 限制显示名称长度，防止布局错乱
        display_name = item.name
        if len(display_name) > 8:
            display_name = display_name[:6] + "..."
            
        # 组合显示名称（序号 + 名称）
        # display_name = f"{index}. {display_name}"
            
        # 创建列表项目
        qitem = QListWidgetItem(icon, display_name)
        
        # 设置工具提示，显示完整的项目信息
        qitem.setToolTip(f"{item.name}\n{item.target}\n备注: {item.remarks}")
        
        # 将AppItem数据存储在项目的数据角色中
        qitem.setData(Qt.UserRole, item)
        
        # 添加项目到列表
        self.addItem(qitem)

    def add_app_item(self, item: AppItem):
        """
        添加应用程序项目（不带序号）
        
        用于不需要显示序号的情况，如动态添加项目。
        
        Args:
            item: 应用程序数据模型
        """
        # 获取项目图标
        icon = self._get_icon(item)
        
        # 限制显示名称长度，防止布局错乱
        display_name = item.name
        if len(display_name) > 8:
            display_name = display_name[:6] + "..."
            
        # 创建列表项目
        qitem = QListWidgetItem(icon, display_name)
        
        # 设置工具提示，显示完整的项目信息
        qitem.setToolTip(f"{item.name}\n{item.target}\n备注: {item.remarks}")
        
        # 将AppItem数据存储在项目的数据角色中
        qitem.setData(Qt.UserRole, item)
        
        # 添加项目到列表
        self.addItem(qitem)

    def _get_icon(self, item: AppItem) -> QIcon:
        """
        获取应用程序图标
        
        智能选择最适合的图标，优先级如下：
        1. 自定义图标路径（如果指定且存在）
        2. 网络URL的favicon（异步加载）
        3. 本地文件的系统图标
        4. 默认文件图标
        
        Args:
            item: 应用程序数据模型
            
        Returns:
            QIcon: 获取到的图标对象
        """
        im = get_icon_manager()
        
        # 1. 检查本地图标缓存
        cache_key = item.target
        if cache_key in im.icon_cache:
            return im.icon_cache[cache_key]
        
        # 2. 检查是否有自定义图标路径
        if item.icon_path and os.path.exists(item.icon_path):
            icon = QIcon(item.icon_path)
            im.icon_cache[cache_key] = icon
            return icon
            
        provider = QFileIconProvider()
        
        # 3. 处理网络URL，获取favicon
        if is_url(item.target):
            # 检查缓存文件是否已存在
            domain = url_domain(item.target)
            if domain:
                fav_cache_key = hashlib.md5(domain.encode()).hexdigest()
                cache_path = os.path.join(CACHE_DIR, f"{fav_cache_key}.png")
                if os.path.exists(cache_path):
                    icon = QIcon(cache_path)
                    im.icon_cache[cache_key] = icon
                    return icon
            # 返回E浏览器默认图标作为占位符（不在这里触发下载，由_load_ui首次启动时批量触发）
            icon = get_browser_default_icon()
            im.icon_cache[cache_key] = icon
            return icon
        
        # 4. 处理本地文件，获取系统图标
        if os.path.exists(item.target):
            info = QFileInfo(item.target)
            icon = provider.icon(info)
            im.icon_cache[cache_key] = icon
            return icon
        
        # 5. 返回默认的文件图标
        icon = self.style().standardIcon(QStyle.SP_FileIcon)
        im.icon_cache[cache_key] = icon
        return icon

    def dragEnterEvent(self, event):
        """
        拖拽进入事件处理
        
        检查拖拽的数据类型，决定是否接受拖拽操作。
        接受URL和文本类型的拖拽。
        
        Args:
            event: 拖拽进入事件
        """
        # 检查是否包含URL或文本数据
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """
        拖拽移动事件处理
        
        在拖拽过程中提供实时的视觉反馈：
        - 高亮显示目标插入位置
        - 更新光标样式
        - 滚动到目标位置
        
        Args:
            event: 拖拽移动事件
        """
        # 如果是内部拖拽操作，提供增强的拖拽体验
        if event.source() == self:
            # 获取鼠标位置和当前拖拽项目
            drop_pos = event.pos()
            current_row = self.currentRow()
            
            # 清除之前的拖拽高亮
            for i in range(self.count()):
                self.item(i).setSelected(False)
            
            # 计算插入位置并提供实时视觉反馈
            insert_pos = self._calculate_insert_position(drop_pos, current_row)
            
            # 高亮显示目标插入位置
            if insert_pos >= 0 and insert_pos < self.count():
                target_item = self.item(insert_pos)
                if target_item:
                    target_item.setSelected(True)
                    # 确保目标项目可见
                    self.scrollToItem(target_item)
            
            # 更新拖拽视觉反馈（光标样式等）
            self._update_drag_feedback(drop_pos, insert_pos)
            
            event.acceptProposedAction()
        # 如果是外部文件拖拽，只接受URL或文本
        elif event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        """
        拖拽离开事件处理
        
        当用户拖拽项目离开列表区域时，清除所有项目的高亮显示，
        恢复正常的视觉效果。
        
        Args:
            event: 拖拽离开事件
        """
        # 拖拽离开时，清除拖拽高亮
        for i in range(self.count()):
            self.item(i).setSelected(False)
        super().dragLeaveEvent(event)

    def _calculate_insert_position(self, drop_pos, current_row):
        """
        智能计算拖拽插入位置
        
        这是核心的拖拽算法，通过以下步骤确定最佳的插入位置：
        1. 跳过当前拖拽的项目
        2. 计算鼠标位置与每个项目的距离
        3. 找到最近的项目
        4. 根据鼠标相对于最近项目的位置决定插入方向
        
        Args:
            drop_pos: 鼠标释放位置
            current_row: 当前拖拽项目的行索引
            
        Returns:
            int: 目标插入位置索引，-1表示无效位置
        """
        # 如果当前行无效，返回-1
        if current_row < 0:
            return -1
            
        total_items = self.count()
        # 如果只有一个或没有项目，直接返回0
        if total_items <= 1:
            return 0
            
        # 查找最接近鼠标位置的项目
        closest_item = None
        min_distance = float('inf')
        closest_index = -1
        
        # 遍历所有项目，计算距离
        for i in range(total_items):
            if i == current_row:
                continue  # 跳过当前拖拽的项目
                
            item = self.item(i)
            item_rect = self.visualItemRect(item)
            item_center = item_rect.center()
            
            # 计算鼠标位置到项目中心的欧几里得距离
            distance = (drop_pos.x() - item_center.x()) ** 2 + (drop_pos.y() - item_center.y()) ** 2
            if distance < min_distance:
                min_distance = distance
                closest_item = item
                closest_index = i
        
        # 如果没有找到最近的项目（不应该发生），根据位置计算
        if closest_item is None:
            return min(total_items - 1, max(0, current_row))
        
        # 根据鼠标相对于最近项目的位置决定插入方向
        closest_rect = self.visualItemRect(closest_item)
        mouse_in_upper_half = drop_pos.y() < closest_rect.center().y()
        
        # 如果鼠标在最近项目的上方，插入到该位置之前
        if mouse_in_upper_half:
            return closest_index
        else:
            # 插入到该位置之后
            return min(closest_index + 1, total_items - 1)

    def _update_drag_feedback(self, drop_pos, insert_pos):
        """
        更新拖拽视觉反馈
        
        在拖拽过程中提供视觉反馈，帮助用户了解当前的操作状态：
        - 有效的插入位置显示抓手光标
        - 无效的插入位置显示禁止光标
        
        Args:
            drop_pos: 当前鼠标位置
            insert_pos: 计算出的插入位置
        """
        # 可以在这里添加更多的视觉反馈，比如插入指示线等
        # 目前通过高亮显示目标位置来实现
        
        # 根据插入位置的有效性设置不同的光标样式
        if insert_pos >= 0 and insert_pos < self.count():
            self.setCursor(Qt.ClosedHandCursor)  # 抓手光标，表示可以放置
        else:
            self.setCursor(Qt.ForbiddenCursor)  # 禁止光标，表示不能放置

    def dropEvent(self, event):
        """
        拖拽释放事件处理
        
        处理两种类型的拖拽操作：
        1. 内部拖拽：列表内的项目重新排序
        2. 外部拖拽：从外部拖入文件或链接
        
        Args:
            event: 拖拽释放事件
        """
        # 清除拖拽光标，恢复正常光标
        self.unsetCursor()
        # 清除所有项目的选中状态（高亮）
        for i in range(self.count()):
            self.item(i).setSelected(False)
            
        # 判断是否为内部拖拽（同一个列表内的拖拽）
        if event.source() == self:
            # 记录拖拽开始时的原始位置
            old_idx = self.currentRow()
            
            # 手动执行项目移动操作
            if old_idx >= 0 and old_idx < self.count():
                # 使用改进的算法计算目标位置
                drop_pos = event.pos()
                target_row = self._calculate_insert_position(drop_pos, old_idx)
                
                # 如果插入位置无效，使用备用算法
                if target_row < 0:
                    # 简单的位置判断
                    total_items = self.count()
                    if drop_pos.y() < self.height() / 2:
                        target_row = max(0, min(old_idx, total_items - 1))
                    else:
                        target_row = min(total_items, old_idx + 1)
                
                # 调整目标索引，如果从前面移到后面，需要修正索引
                if old_idx < target_row:
                    target_row -= 1
                
                # 确保目标索引有效
                if target_row < 0:
                    target_row = 0
                elif target_row >= self.count():
                    target_row = self.count() - 1

                
                # 如果位置发生了变化，执行移动操作
                if target_row != old_idx and 0 <= target_row <= self.count():
                    # 在数据模型中执行移动
                    self.window().model.move_item(self.group_name, old_idx, target_row)
                    self.window().model.save()
                    
                    # 重新加载整个UI（重建所有分组页，移动后的顺序即生效）
                    self.window()._load_ui()

                    # 接受事件
                    event.acceptProposedAction()
                    return
            
            # 如果没有移动，仍然接受事件
            event.acceptProposedAction()
            
        # 处理外部拖拽（从外部拖入文件或链接）
        else:
            added = False
            
            # 处理URL拖拽（文件和链接）
            if event.mimeData().hasUrls():
                for url in event.mimeData().urls():
                    path = url.toLocalFile()
                    if path:
                        # 拖入的是本地文件
                        name = os.path.splitext(os.path.basename(path))[0]
                        
                        # 尝试解析快捷方式
                        target_path, launch_args = resolve_shortcut(path)
                        
                        # 自动设置起始位置（文件夹不设置）
                        work_dir = ""
                        if os.path.exists(target_path) and not os.path.isdir(target_path):
                            work_dir = os.path.dirname(target_path)
                        app = AppItem(name=name, target=target_path, group=self.group_name, work_dir=work_dir, launch_args=launch_args)
                    else:
                        # 拖入的是网络链接
                        u = url.toString()
                        name = url_domain(u) or u
                        app = AppItem(name=name, target=u, group=self.group_name)
                    self.window().add_item_to_group(app)
                    added = True
                    
            # 处理文本拖拽（可能是链接或命令）
            elif event.mimeData().hasText():
                u = event.mimeData().text().strip()
                if u:
                    # 根据内容判断是文件路径还是网络链接
                    if not is_url(u):
                        name = os.path.splitext(os.path.basename(u))[0]
                        
                        # 尝试解析快捷方式
                        u, launch_args = resolve_shortcut(u)
                        
                        # 自动设置起始位置（文件夹不设置）
                        work_dir = ""
                        if os.path.exists(u) and not os.path.isdir(u):
                            work_dir = os.path.dirname(u)
                        app = AppItem(name=name, target=u, group=self.group_name, work_dir=work_dir, launch_args=launch_args)
                    else:
                        name = url_domain(u) or u
                        app = AppItem(name=name, target=u, group=self.group_name)
                    self.window().add_item_to_group(app)
                    added = True
                    
            # 如果成功添加了项目，接受事件并由主窗口统一刷新
            if added:
                event.acceptProposedAction()

    def _show_context_menu(self, pos: QPoint):
        """
        显示上下文菜单
        
        根据鼠标位置和选中状态显示相应的上下文菜单：
        - 右键空白处：显示添加菜单
        - 右键选中项目：显示编辑和管理菜单
        - 多选时：显示批量操作菜单
        
        Args:
            pos: 鼠标在列表中的位置
        """
        menu = QMenu(self)
        win = self.window()
        
        # 添加菜单组
        add_menu = menu.addMenu("添加...")
        add_file = add_menu.addAction("📎 添加文件")
        add_dir = add_menu.addAction("📁 添加文件夹")
        add_link = add_menu.addAction("🌐 添加链接")
        add_cmd = add_menu.addAction("🐚 添加 CMD 命令")

        # 获取鼠标位置的项目和所有选中项
        clicked_item = self.itemAt(pos)
        selected_items = self.selectedItems()
        multi_select = len(selected_items) > 1
        
        # 批量操作菜单（多选时）
        batch_del_action = None
        batch_run_action = None
        batch_copy_to_actions = {}
        batch_move_to_actions = {}
        
        if multi_select:
            menu.addSeparator()
            batch_run_action = menu.addAction(f"🚀 批量运行 ({len(selected_items)}项)")
            batch_del_action = menu.addAction(f"🗑️ 批量删除 ({len(selected_items)}项)")
            
            batch_copy_menu = menu.addMenu(f"📋 批量复制到分组 ({len(selected_items)}项)")
            batch_move_menu = menu.addMenu(f"✂️ 批量移动到分组 ({len(selected_items)}项)")
            all_groups = list(win.model.groups.keys())
            for gn in all_groups:
                if gn != self.group_name:
                    ca = batch_copy_menu.addAction(gn)
                    batch_copy_to_actions[ca] = gn
                    ma = batch_move_menu.addAction(gn)
                    batch_move_to_actions[ma] = gn
        
        # 单选操作菜单
        edit_action = None
        del_action = None
        copy_action = None
        open_folder_action = None
        create_shortcut_action = None
        prop_action = None
        single_copy_to_actions = {}
        single_move_to_actions = {}
        
        if clicked_item and not multi_select:
            edit_action = menu.addAction("✏️ 修改")
            del_action = menu.addAction("🗑️ 删除")
            
            menu.addSeparator()
            
            copy_to_menu = menu.addMenu("📋 复制到分组")
            move_to_menu = menu.addMenu("✂️ 移动到分组")
            all_groups = list(win.model.groups.keys())
            for gn in all_groups:
                if gn != self.group_name:
                    ca = copy_to_menu.addAction(gn)
                    single_copy_to_actions[ca] = gn
                    ma = move_to_menu.addAction(gn)
                    single_move_to_actions[ma] = gn
            
            menu.addSeparator()
            
            copy_action = menu.addAction("📋 复制路径")
            open_folder_action = menu.addAction("📂 在资源管理器中打开")
            create_shortcut_action = menu.addAction("🖥️ 生成桌面快捷方式")
            
            item: AppItem = clicked_item.data(Qt.UserRole)
            if item.target.startswith(("http://", "https://")) or " " in item.target and not os.path.exists(item.target):
                pass
            elif os.path.isfile(item.target) or os.path.isdir(item.target):
                prop_action = menu.addAction("ℹ️ 属性")
        
        menu.addSeparator()
        
        # 显示菜单并获取用户选择
        action = menu.exec_(self.mapToGlobal(pos))
        if not action:
            return
        
        # 处理添加菜单
        if action == add_file:
            win.add_item_dialog(self.group_name, mode="file")
        elif action == add_dir:
            win.add_item_dialog(self.group_name, mode="folder")
        elif action == add_link:
            win.add_item_dialog(self.group_name, mode="url")
        elif action == add_cmd:
            win.add_item_dialog(self.group_name, mode="cmd")
        # 批量操作
        elif action == batch_del_action:
            win.batch_delete(self.group_name, selected_items)
        elif action == batch_run_action:
            win.batch_run(selected_items)
        elif action in batch_copy_to_actions:
            win.batch_copy(self.group_name, selected_items, batch_copy_to_actions[action])
        elif action in batch_move_to_actions:
            win.batch_move(self.group_name, selected_items, batch_move_to_actions[action])
        # 单选操作
        elif clicked_item and not multi_select:
            item: AppItem = clicked_item.data(Qt.UserRole)
            index = self.row(clicked_item)
            # 「全部」视图下 self.group_name 是虚拟聚合组，需按 item.group 解析真实分组与索引
            real_group = item.group
            real_items = win.model.groups.get(real_group, [])
            real_index = real_items.index(item) if item in real_items else -1

            if action in single_copy_to_actions:
                if real_index >= 0:
                    win.copy_item_to_group(real_group, real_index, single_copy_to_actions[action])
            elif action in single_move_to_actions:
                if real_index >= 0:
                    win.move_item_to_group(real_group, real_index, single_move_to_actions[action])
            elif action == del_action:
                if real_index >= 0:
                    win.delete_item(real_group, real_index)
                else:
                    QMessageBox.warning(self, "删除失败", "未找到该项所属分组，无法删除。")
            elif action == edit_action:
                if real_index >= 0:
                    win.edit_item(real_group, real_index)
            elif action == copy_action:
                QGuiApplication.clipboard().setText(item.target)
            elif action == open_folder_action:
                open_in_explorer(item.target)
            elif action == create_shortcut_action:
                create_desktop_shortcut(item)
            elif action == prop_action:
                open_properties(item.target)

    def _launch_item(self, list_item: QListWidgetItem, hide_window: bool = True, source: str = "双击"):
        item: AppItem = list_item.data(Qt.UserRole)
        
        # 记录点击次数
        item.click_count = getattr(item, 'click_count', 0) + 1
        main_window = self.window()
        if main_window and hasattr(main_window, 'model'):
            # 同步更新model中的数据
            group_items = main_window.model.groups.get(self.group_name, [])
            idx = self.row(list_item)
            if 0 <= idx < len(group_items):
                group_items[idx].click_count = item.click_count
            main_window.model.save()

        # 记录启动日志
        log_enabled = True
        if main_window and hasattr(main_window, 'model'):
            log_enabled = main_window.model.settings.get("enable_launch_log", True)
        log_launch(item, source, enabled=log_enabled)

        # 点击时重试下载缺失的URL图标
        if is_url(item.target) and not (item.icon_path and os.path.exists(item.icon_path)):
            im = get_icon_manager()
            domain = url_domain(item.target)
            if domain:
                fav_cache_key = hashlib.md5(domain.encode()).hexdigest()
                cache_path = os.path.join(CACHE_DIR, f"{fav_cache_key}.png")
                if not os.path.exists(cache_path):
                    # 清除已请求标记以允许重试
                    im.icon_requested.discard(fav_cache_key)
                    # 清除图标缓存以便更新
                    im.icon_cache.pop(item.target, None)
                    QTimer.singleShot(0, lambda: im.get_favicon(item.target))
        
        # 清除选中态：避免双击/单击启动后 item 停留在 State_Selected，
        # 导致图标被 Qt 默认选中渲染（深色/黑色）。选中态对本启动器无意义（启动即隐藏）。
        self.clearSelection()
        if hide_window and main_window:
            main_window.hide()
        
        target = item.target
        work_dir = item.work_dir if hasattr(item, 'work_dir') else None
        launch_args = item.launch_args if hasattr(item, 'launch_args') else None
        
        def do_launch():
            try:
                if is_url(target):
                    webbrowser.open(target)
                else:
                    launch_target(target, work_dir, launch_args)
            except Exception as e:
                print(f"启动失败: {e}")
        
        threading.Thread(target=do_launch, daemon=True).start()

    def _on_item_clicked(self, list_item: QListWidgetItem):
        """单击项目时启动应用，Ctrl+单击时不隐藏窗口；多选时不启动（由右键批量操作）"""
        selected_count = len(self.selectedItems())
        if selected_count > 1:
            return
        ctrl_held = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        self._launch_item(list_item, hide_window=not ctrl_held, source="单击")

    def _on_item_entered(self, list_item: QListWidgetItem):
        """鼠标悬停时显示手型光标"""
        self.setCursor(Qt.PointingHandCursor)

    def leaveEvent(self, event):
        """鼠标离开列表时恢复默认光标"""
        super().leaveEvent(event)
        self.unsetCursor()


class HotkeyInputWidget(QLineEdit):
    """自定义热键输入组件，能够实时显示格式化的按键组合"""
    
    hotkey_changed = Signal(str)  # 热键改变信号
    
    def __init__(self, parent=None, placeholder="按组合键..."):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setReadOnly(True)  # 只读，用户通过按键输入
        
        # 当前按键状态
        self._current_modifiers = set()
        self._current_key = None
        self._recording = False
        
        # 设置样式
        self.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #000000;
                border: 2px solid #e9ecef;
                
                padding: 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #007bff;
                background-color: #ffffff;
                color: #000000;
            }
            QLineEdit:hover {
                border-color: #adb5bd;
            }
        """)
        
        # 设置上下文菜单策略，禁用默认菜单
        self.setContextMenuPolicy(Qt.NoContextMenu)
        
        # 设置点击时聚焦
        self.setFocusPolicy(Qt.ClickFocus)
    
    def focusInEvent(self, event):
        """获得焦点时的处理"""
        super().focusInEvent(event)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #000000;
                border: 2px solid #007bff;
                
                padding: 8px;
                font-size: 12px;
            }
        """)
    
    def focusOutEvent(self, event):
        """失去焦点时的处理"""
        super().focusOutEvent(event)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #000000;
                border: 2px solid #e9ecef;
                
                padding: 8px;
                font-size: 12px;
            }
            QLineEdit:hover {
                border-color: #adb5bd;
            }
        """)
    
    def keyPressEvent(self, event: QKeyEvent):
        """处理按键事件"""
        if event.isAutoRepeat():
            return
            
        key = event.key()
        key_text = event.text()
        print(f"[DEBUG] Key pressed: key={key}, keyText='{key_text}', keyStr={Qt.Key(key)}, modifiers={event.modifiers()}")
        
        # 忽略修饰键的单独按下
        if key in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta]:
            print(f"[DEBUG] Ignoring modifier key: {key}")
            return
            
        # 处理退格键清除输入
        if key == Qt.Key_Backspace:
            print(f"[DEBUG] Backspace pressed, clearing")
            self.clear()
            self._current_modifiers.clear()
            self._current_key = None
            self.hotkey_changed.emit("")  # 发送空字符串信号
            return
            
        # 处理 Escape 键清除输入
        if key == Qt.Key_Escape:
            print(f"[DEBUG] Escape pressed, clearing")
            self.clear()
            self._current_modifiers.clear()
            self._current_key = None
            self.hotkey_changed.emit("")  # 发送空字符串信号
            return
            
        # 收集修饰键
        modifiers = set()
        if event.modifiers() & Qt.ControlModifier:
            modifiers.add('Ctrl')
            print(f"[DEBUG] Added Ctrl modifier")
        if event.modifiers() & Qt.ShiftModifier:
            modifiers.add('Shift')
            print(f"[DEBUG] Added Shift modifier")
        if event.modifiers() & Qt.AltModifier:
            modifiers.add('Alt')
            print(f"[DEBUG] Added Alt modifier")
        if event.modifiers() & Qt.MetaModifier:
            modifiers.add('Win')
            print(f"[DEBUG] Added Win modifier")
        
        # 获取按键名称，考虑event.text()用于上档字符
        key_name = self._get_key_name(key, key_text)
        
        # 特殊处理减号键和下划线键，确保都能正确识别为减号
        if key in [Qt.Key_Minus, Qt.Key_Underscore]:
            key_name = "-"
            print(f"[DEBUG] Forced minus key: key={key}, key_name='{key_name}'")
        
        print(f"[DEBUG] Got key_name: '{key_name}'")
        if not key_name:
            print(f"[DEBUG] key_name is empty, returning")
            return
            
        # 更新显示
        hotkey_parts = list(modifiers) + [key_name]
        if hotkey_parts:  # 只有当有按键时才显示
            hotkey_text = '+'.join(hotkey_parts)
            self.setText(hotkey_text)
            self._current_modifiers = modifiers
            self._current_key = key_name
            
            # 发送热键改变信号
            self.hotkey_changed.emit(hotkey_text)
            
        # 接受事件
        event.accept()
    
    def keyReleaseEvent(self, event: QKeyEvent):
        """处理按键释放事件"""
        # 忽略修饰键的释放
        if event.key() in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta]:
            return
            
        # 阻止默认处理
        event.ignore()
    
    def _get_key_name(self, key, key_text=""):
        """获取按键的可读名称"""
        print(f"[DEBUG _get_key_name] key={key}, key_text='{key_text}', keyStr={Qt.Key(key)}")
        
        # 特殊处理减号键和下划线键，优先处理
        if key in [Qt.Key_Minus, Qt.Key_Underscore]:
            print(f"[DEBUG _get_key_name] Key is minus/underscore, returning '-'")
            return "-"
        
        # 特殊处理等号键
        if key == Qt.Key_Equal:
            print(f"[DEBUG _get_key_name] Key is equal, returning '='")
            return "="
        
        # 功能键
        if Qt.Key_F1 <= key <= Qt.Key_F12:
            result = f"F{key - Qt.Key_F1 + 1}"
            print(f"[DEBUG _get_key_name] Function key, returning '{result}'")
            return result
        
        # 方向键
        key_names = {
            Qt.Key_Up: "向上",
            Qt.Key_Down: "向下", 
            Qt.Key_Left: "向左",
            Qt.Key_Right: "向右",
            Qt.Key_Home: "Home",
            Qt.Key_End: "End",
            Qt.Key_PageUp: "PageUp",
            Qt.Key_PageDown: "PageDown",
            Qt.Key_Insert: "Insert",
            Qt.Key_Delete: "Delete",
            Qt.Key_Escape: "Esc",
            Qt.Key_Tab: "Tab",
            Qt.Key_Return: "回车",
            Qt.Key_Enter: "回车",
            Qt.Key_Backspace: "退格",
            Qt.Key_Space: "空格"
        }
        
        if key in key_names:
            result = key_names[key]
            print(f"[DEBUG _get_key_name] Direction key, returning '{result}'")
            return result
        
        # 数字键
        if Qt.Key_0 <= key <= Qt.Key_9:
            result = str(key - Qt.Key_0)
            print(f"[DEBUG _get_key_name] Number key, returning '{result}'")
            return result
        
        # 字母键
        if Qt.Key_A <= key <= Qt.Key_Z:
            result = chr(key - Qt.Key_A + ord('A'))
            print(f"[DEBUG _get_key_name] Letter key, returning '{result}'")
            return result
        
        # 优先使用event.text()来处理上档字符
        if key_text and len(key_text) == 1:
            print(f"[DEBUG _get_key_name] Using key_text, returning '{key_text}'")
            # 对于符号键，直接返回显示的字符
            return key_text
        
        # 符号键（兼容 OEM 键）
        symbol_keys = {
            Qt.Key_Minus: "-",
            Qt.Key_Equal: "=", 
            Qt.Key_BracketLeft: "[",
            Qt.Key_BracketRight: "]",
            Qt.Key_Backslash: "\\",
            Qt.Key_Semicolon: ";",
            Qt.Key_Apostrophe: "'",
            Qt.Key_Comma: ",",
            Qt.Key_Period: ".",
            Qt.Key_Slash: "/"
        }
        
        if key in symbol_keys:
            result = symbol_keys[key]
            print(f"[DEBUG _get_key_name] Symbol key, returning '{result}'")
            return result
        
        # 处理反引号键（在不同版本中可能名称不同）
        try:
            symbol_keys[Qt.Key_Grave] = "`"
        except AttributeError:
            # 如果 Key_Grave 不存在，使用 Key_QuoteLeft
            try:
                symbol_keys[Qt.Key_QuoteLeft] = "`"
            except AttributeError:
                # 如果都不存在，则跳过这个键
                pass
        
        if key in symbol_keys:
            return symbol_keys[key]
        
        return None
    
    def get_hotkey_string(self):
        """获取当前设置的热键字符串"""
        return self.text()
    
    def set_hotkey_string(self, hotkey_str):
        """设置热键字符串"""
        self.setText(hotkey_str)
        if hotkey_str:
            self.hotkey_changed.emit(hotkey_str)
        else:
            self.hotkey_changed.emit("")


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings: Dict = None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(480)
        self.setMinimumHeight(420)
        main_layout = QVBoxLayout(self)
        
        # Tab布局
        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget)
        
        # ========== Tab1: 常规配置 ==========
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        general_layout.setSpacing(10)
        general_layout.setContentsMargins(15, 15, 15, 15)
        
        self.autostart_combo = QComboBox(self)
        self.autostart_combo.addItems(["否", "是"])
        self.autostart_combo.setCurrentIndex(1 if settings.get("autostart") else 0)
        general_layout.addRow("开机启动", self.autostart_combo)

        self.icon_size_spin = QSpinBox(self)
        self.icon_size_spin.setRange(16, 128)
        self.icon_size_spin.setValue(settings.get("icon_size", 48))
        self.icon_size_spin.setSuffix(" px")
        self.icon_size_spin.setMinimumWidth(100)
        general_layout.addRow(self._label_with_tip("图标大小", "区间16-128px"), self.icon_size_spin)

        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(["浅色", "深色"])
        self.theme_combo.setCurrentIndex(0 if settings.get("theme", "light") == "light" else 1)
        general_layout.addRow("主题", self.theme_combo)

        self.sort_combo = QComboBox(self)
        self.sort_combo.addItems(["默认排序", "按点击次数排序"])
        self.sort_combo.setCurrentIndex(1 if settings.get("sort_order", "default") == "click_count" else 0)
        general_layout.addRow("排序方式", self.sort_combo)

        self.start_hidden_combo = QComboBox(self)
        self.start_hidden_combo.addItems(["否", "是"])
        self.start_hidden_combo.setCurrentIndex(1 if settings.get("start_hidden", False) else 0)
        general_layout.addRow("启动时隐藏窗口", self.start_hidden_combo)

        self.auto_backup_combo = QComboBox(self)
        self.auto_backup_combo.addItems(["不自动备份", "每次启动备份", "每天备份一次", "每周备份一次", "每月备份一次"])
        backup_map = {"none": 0, "startup": 1, "daily": 2, "weekly": 3, "monthly": 4}
        self.auto_backup_combo.setCurrentIndex(backup_map.get(settings.get("auto_backup", "none"), 0))
        general_layout.addRow("自动备份", self.auto_backup_combo)

        backup_dir_row = QWidget()
        backup_dir_lay = QHBoxLayout(backup_dir_row)
        backup_dir_lay.setContentsMargins(0, 0, 0, 0)
        self.backup_dir_edit = QLineEdit(settings.get("backup_dir", os.path.join(APP_DIR, "bak")), self)
        backup_dir_lay.addWidget(self.backup_dir_edit)
        backup_dir_btn = QPushButton("📁 浏览", self)
        backup_dir_btn.setCursor(Qt.PointingHandCursor)
        backup_dir_btn.setMinimumHeight(35)
        backup_dir_btn.setStyleSheet("border: 1px solid #cccccc;  padding: 5px 10px;")
        backup_dir_btn.clicked.connect(self._browse_backup_dir)
        backup_dir_lay.addWidget(backup_dir_btn)
        general_layout.addRow("备份目录", backup_dir_row)

        self.auto_cleanup_combo = QComboBox(self)
        self.auto_cleanup_combo.addItems(["否", "是"])
        self.auto_cleanup_combo.setCurrentIndex(1 if settings.get("auto_cleanup_backup", True) else 0)
        general_layout.addRow("自动清理旧备份", self.auto_cleanup_combo)

        self.backup_keep_spin = QSpinBox(self)
        self.backup_keep_spin.setRange(1, 999)
        self.backup_keep_spin.setValue(settings.get("backup_keep_count", 20))
        self.backup_keep_spin.setSuffix(" 个")
        general_layout.addRow("保留最近备份数", self.backup_keep_spin)

        self.enable_log_combo = QComboBox(self)
        self.enable_log_combo.addItems(["是", "否"])
        self.enable_log_combo.setCurrentIndex(0 if settings.get("enable_launch_log", True) else 1)
        general_layout.addRow("记录启动日志", self.enable_log_combo)

        self.bg_interval_spin = QSpinBox(self)
        self.bg_interval_spin.setRange(1, 3600)
        self.bg_interval_spin.setValue(settings.get("bg_interval", 30))
        self.bg_interval_spin.setSuffix(" 秒")
        self.bg_interval_spin.setMinimumWidth(100)
        general_layout.addRow(
            self._label_with_tip("背景轮播间隔", "中间背景图自动切换的间隔，单位秒（需放入背景图片才生效）"),
            self.bg_interval_spin
        )

        # 导入导出
        io_row = QWidget()
        io_lay = QVBoxLayout(io_row)
        backup_btn = QLabel("📤 备份到文件")
        backup_btn.setStyleSheet("color: #1677ff; cursor: pointer;")
        backup_btn.mousePressEvent = lambda e: self._backup_to_file()
        restore_btn = QLabel("📥 从文件恢复")
        restore_btn.setStyleSheet("color: #1677ff; cursor: pointer;")
        restore_btn.mousePressEvent = lambda e: self._restore_from_file()
        io_lay.addWidget(backup_btn)
        io_lay.addWidget(restore_btn)
        general_layout.addRow("数据备份", io_row)

        self.tab_widget.addTab(general_tab, "常规配置")
        
        # ========== Tab2: 热键配置 ==========
        hotkey_tab = QWidget()
        hotkey_layout = QFormLayout(hotkey_tab)
        hotkey_layout.setSpacing(10)
        hotkey_layout.setContentsMargins(15, 15, 15, 15)
        
        self.hk_show = HotkeyInputWidget(self, placeholder="按组合键 (如 Ctrl+A)")
        self.hk_opacity_up = HotkeyInputWidget(self, placeholder="按组合键")
        self.hk_opacity_down = HotkeyInputWidget(self, placeholder="按组合键")
        self.hk_lock = HotkeyInputWidget(self, placeholder="按组合键")
        self.hk_unlock = HotkeyInputWidget(self, placeholder="按组合键")
        self.hk_next_group = HotkeyInputWidget(self, placeholder="按组合键")
        self.hk_prev_group = HotkeyInputWidget(self, placeholder="按组合键")
        
        hks = settings.get("hotkeys", {})
        self.hk_show.set_hotkey_string(hks.get("show_hide", "Ctrl+Alt+Q"))
        self.hk_opacity_up.set_hotkey_string(hks.get("opacity_up", "Alt+Up"))
        self.hk_opacity_down.set_hotkey_string(hks.get("opacity_down", "Alt+Down"))
        self.hk_lock.set_hotkey_string(hks.get("lock", "Ctrl+L"))
        self.hk_unlock.set_hotkey_string(hks.get("unlock", "Ctrl+U"))
        self.hk_next_group.set_hotkey_string(hks.get("next_group", "Ctrl+`"))
        self.hk_prev_group.set_hotkey_string(hks.get("prev_group", "Ctrl+1"))

        hotkey_layout.addRow("主热键 (显示/隐藏)", self.hk_show)
        hotkey_layout.addRow(self._label_with_tip("透明度增加热键", "修改当前获得焦点的窗口透明度"), self.hk_opacity_up)
        hotkey_layout.addRow(self._label_with_tip("透明度减少热键", "修改当前获得焦点的窗口透明度"), self.hk_opacity_down)
        hotkey_layout.addRow(self._label_with_tip("窗口锁定热键", "修改当前获得焦点的窗口锁定/解锁"), self.hk_lock)
        hotkey_layout.addRow(self._label_with_tip("窗口解锁热键", "修改当前获得焦点的窗口锁定/解锁"), self.hk_unlock)
        hotkey_layout.addRow("下一个分组", self.hk_next_group)
        hotkey_layout.addRow("上一个分组", self.hk_prev_group)

        self.tab_widget.addTab(hotkey_tab, "热键配置")
        
        # ========== 确定/取消按钮 ==========
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        
        for btn in btns.buttons():
            btn.setCursor(Qt.PointingHandCursor)
        
        ok_btn = btns.button(QDialogButtonBox.Ok)
        ok_btn.setText("确定")
        cancel_btn = btns.button(QDialogButtonBox.Cancel)
        cancel_btn.setText("取消")
        if ok_btn and cancel_btn:
            ok_btn.setStyleSheet("border: 1px solid #cccccc;  padding: 5px 10px;")
            cancel_btn.setStyleSheet("border: 1px solid #cccccc;  padding: 5px 10px;")
        
        main_layout.addWidget(btns)

    def _label_with_tip(self, text, tooltip):
        """创建带问号提示图标的标签"""
        w = QWidget(self)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lbl = QLabel(text, self)
        lay.addWidget(lbl)
        tip = QLabel("❓", self)
        tip.setToolTip(tooltip)
        tip.setStyleSheet("color: #999999; font-size: 12px;")
        tip.setCursor(Qt.WhatsThisCursor)
        lay.addWidget(tip)
        lay.addStretch()
        return w

    def _browse_backup_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择备份目录", self.backup_dir_edit.text())
        if path:
            self.backup_dir_edit.setText(path)

    def _backup_to_file(self):
        try:
            app_dir = get_app_directory()
            default_name = f"quicklauncher_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "备份配置", os.path.join(app_dir, default_name), "JSON文件 (*.json)"
            )
            if file_path:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                QMessageBox.information(self, "成功", f"配置已备份到:\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"备份失败: {e}")

    def _restore_from_file(self):
        try:
            app_dir = get_app_directory()
            file_path, _ = QFileDialog.getOpenFileName(
                self, "恢复配置", app_dir, "JSON文件 (*.json)"
            )
            if file_path:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                json.loads(content)
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    f.write(content)
                parent = self.parent()
                if parent and hasattr(parent, 'model') and hasattr(parent, '_load_ui'):
                    parent.model.load()
                    parent._load_ui()
                    if hasattr(parent, '_apply_theme'):
                        parent._apply_theme()
                    if hasattr(parent, '_apply_all_hotkeys'):
                        parent._apply_all_hotkeys()
                    if hasattr(parent, '_restore_window_size'):
                        parent._restore_window_size()
                    # 恢复工具栏位置
                    if hasattr(parent, 'main_toolbar'):
                        area_val = parent.model.settings.get("toolbar_area", Qt.TopToolBarArea.value)
                        parent.addToolBar(Qt.ToolBarArea(area_val), parent.main_toolbar)
                QMessageBox.information(self, "成功", "配置已恢复，界面已刷新")
                self.reject()
        except json.JSONDecodeError:
            QMessageBox.warning(self, "错误", "文件格式不正确")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"恢复失败: {e}")

    def result_values(self):
        return {
            "hotkeys": {
                "show_hide": self.hk_show.get_hotkey_string().strip(),
                "opacity_up": self.hk_opacity_up.get_hotkey_string().strip(),
                "opacity_down": self.hk_opacity_down.get_hotkey_string().strip(),
                "lock": self.hk_lock.get_hotkey_string().strip(),
                "unlock": self.hk_unlock.get_hotkey_string().strip(),
                "next_group": self.hk_next_group.get_hotkey_string().strip(),
                "prev_group": self.hk_prev_group.get_hotkey_string().strip(),
            },
            "autostart": self.autostart_combo.currentIndex() == 1,
            "icon_size": self.icon_size_spin.value(),
            "theme": "light" if self.theme_combo.currentIndex() == 0 else "dark",
            "sort_order": "click_count" if self.sort_combo.currentIndex() == 1 else "default",
            "start_hidden": self.start_hidden_combo.currentIndex() == 1,
            "auto_backup": ["none", "startup", "daily", "weekly", "monthly"][self.auto_backup_combo.currentIndex()],
            "backup_dir": self.backup_dir_edit.text().strip(),
            "auto_cleanup_backup": self.auto_cleanup_combo.currentIndex() == 1,
            "backup_keep_count": self.backup_keep_spin.value(),
            "enable_launch_log": self.enable_log_combo.currentIndex() == 0,
            "bg_interval": self.bg_interval_spin.value()
        }


class LaunchLogWidget(QWidget):
    """启动日志查看页：表格展示、搜索过滤、清空、导出 CSV"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 顶部工具栏：搜索 + 导出 + 清空
        top = QHBoxLayout()
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("🔍 搜索 名称 / 分组 / 触发方式 / 目标路径")
        self.search_edit.textChanged.connect(self.refresh)
        top.addWidget(self.search_edit, 1)

        self.export_btn = QPushButton("📤 导出CSV", self)
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.clicked.connect(self.export_csv)
        top.addWidget(self.export_btn)

        self.clear_btn = QPushButton("🗑 清空日志", self)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_log)
        top.addWidget(self.clear_btn)
        layout.addLayout(top)

        self.count_label = QLabel(self)
        self.count_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.count_label)

        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["时间", "名称", "分组", "触发方式", "目标路径"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        self.refresh()

    def _load_records(self):
        if not os.path.exists(LOG_FILE):
            return []
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def refresh(self):
        keyword = self.search_edit.text().strip().lower()
        records = self._load_records()
        if keyword:
            records = [
                r for r in records
                if keyword in str(r.get("name", "")).lower()
                or keyword in str(r.get("group", "")).lower()
                or keyword in str(r.get("source", "")).lower()
                or keyword in str(r.get("target", "")).lower()
            ]
        # 倒序展示：最新在最上面
        records = list(reversed(records))
        self.table.setRowCount(len(records))
        for i, r in enumerate(records):
            self.table.setItem(i, 0, QTableWidgetItem(str(r.get("time", ""))))
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("name", ""))))
            self.table.setItem(i, 2, QTableWidgetItem(str(r.get("group", ""))))
            self.table.setItem(i, 3, QTableWidgetItem(str(r.get("source", ""))))
            self.table.setItem(i, 4, QTableWidgetItem(str(r.get("target", ""))))
        self.table.resizeColumnsToContents()
        total = len(self._load_records())
        self.count_label.setText(f"共 {total} 条记录（当前显示 {len(records)} 条）")

    def clear_log(self):
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有启动日志吗？此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                if os.path.exists(LOG_FILE):
                    os.remove(LOG_FILE)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"清空失败: {e}")

    def export_csv(self):
        records = self._load_records()
        if not records:
            QMessageBox.information(self, "提示", "当前没有日志可导出")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出启动日志",
            os.path.join(APP_DIR, "launch_log.csv"),
            "CSV文件 (*.csv)"
        )
        if not path:
            return
        try:
            import csv
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["time", "name", "group", "source", "target"])
                writer.writeheader()
                for r in records:
                    writer.writerow(r)
            QMessageBox.information(self, "成功", f"已导出到:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"导出失败: {e}")


class SidebarWidget(QWidget):
    """左侧导航：启动日志置顶 + 全部 + 各分组；支持折叠为仅图标、右键菜单。"""
    selected = Signal(str)                 # 选中分组名 / "启动日志"
    requestContextMenu = Signal(str, QPoint)  # 右键某分组
    collapsedChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(180)
        self.collapsed = False
        self._current = None
        self._items = []      # (name, widget, label, icon_label, layout, is_log)
        self._title = None

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)

        self._collapse_btn = QPushButton()
        self._collapse_btn.setObjectName("NavCollapse")
        self._collapse_btn.setToolTip("折叠 / 展开导航")
        self._collapse_btn.setCursor(Qt.PointingHandCursor)
        self._collapse_btn.setIcon(theme.render_icon("collapse", theme.ACTIVE["text_secondary"], 18))
        self._collapse_btn.clicked.connect(self.toggle_collapse)
        root.addWidget(self._collapse_btn)

        self._body = QVBoxLayout()
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(2)
        self._body.addStretch(1)
        root.addLayout(self._body)

    def set_groups(self, entries, current):
        """entries: [(name, count, is_log), ...]，顺序即显示顺序。"""
        print(f"[DEBUG set_groups] entries={entries}, current={current}")
        # 清空旧项（takeAt 彻底移除 layout item，避免 deleteLater 残留干扰后续 insertWidget）
        while self._body.count() > 0:
            item = self._body.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._items = []
        self._title = None

        # 底部 stretch（确保分组项始终在 stretch 上方）
        self._body.addStretch(1)

        # 启动日志置顶
        for name, count, is_log in entries:
            if is_log:
                self._add_item(name, count, is_log)
        # 分组标题
        self._title = QLabel("分组")
        self._title.setObjectName("NavTitle")
        self._body.insertWidget(self._body.count() - 1, self._title)
        # 其余（全部 + 各分组）
        for name, count, is_log in entries:
            if not is_log:
                self._add_item(name, count, is_log)
        self._set_current(current)
        # 强制布局重新计算 + 重绘，确保新分组名可见
        self._body.invalidate()
        self._body.activate()
        self.update()
        self.repaint()

    def _add_item(self, name, count, is_log):
        w = QPushButton()
        w.setObjectName("NavItem")
        w.setCursor(Qt.PointingHandCursor)
        w.setFixedHeight(38)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(theme.render_icon("log" if is_log else "folder",
                                         theme.ACTIVE["text_secondary"], 18).pixmap(18, 18))
        label = QLabel(name)
        cnt = QLabel(str(count))
        cnt.setObjectName("NavCount")
        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(cnt)
        w.clicked.connect(lambda _, n=name: self._on_click(n))
        w.setContextMenuPolicy(Qt.CustomContextMenu)
        w.customContextMenuRequested.connect(
            lambda pos, n=name: self.requestContextMenu.emit(n, w.mapToGlobal(pos)))
        self._body.insertWidget(self._body.count() - 1, w)
        self._items.append((name, w, label, icon, layout, is_log))

    def _on_click(self, name):
        self._set_current(name)
        self.selected.emit(name)

    def _set_current(self, name):
        self._current = name
        for nm, w, label, icon, layout, is_log in self._items:
            active = (nm == name)
            w.setObjectName("NavItemActive" if active else "NavItem")
            color = "#ffffff" if active else theme.ACTIVE["text_secondary"]
            icon.setPixmap(theme.render_icon("log" if is_log else "folder", color, 18).pixmap(18, 18))
            w.style().unpolish(w)
            w.style().polish(w)

    def recolor(self):
        """主题切换时重新着色图标与激活态。"""
        self._collapse_btn.setIcon(theme.render_icon("collapse", theme.ACTIVE["text_secondary"], 18))
        self._set_current(self._current)

    def toggle_collapse(self):
        self.collapsed = not self.collapsed
        self.setFixedWidth(56 if self.collapsed else 180)
        for nm, w, label, icon, layout, is_log in self._items:
            label.setVisible(not self.collapsed)
            w.findChild(QLabel, "NavCount").setVisible(not self.collapsed)
            layout.setAlignment(icon, Qt.AlignCenter if self.collapsed else Qt.AlignLeft)
        if self._title is not None:
            self._title.setVisible(not self.collapsed)
        self.collapsedChanged.emit(self.collapsed)


class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"angel Start v{APP_VERSION}")
        self.setObjectName("LauncherWindow")
        # 标准 Windows 窗口：保留原生标题栏（最小化/最大化/关闭），直角边框
        # 注意：必须显式包含 WindowCloseButtonHint，否则在 Windows 上关闭按钮会被禁用变灰
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        self.model = LauncherModel()
        self.model.load()

        # 托盘
        self.tray = QSystemTrayIcon(self)
        icon_path = get_resource_path("app.ico")
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            self.tray.setIcon(app_icon)
        else:
            default_icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
            self.tray.setIcon(default_icon)
        tray_menu = QMenu()
        tray_menu.addAction("显示窗口", self.show_and_raise)
        tray_menu.addAction("🌗 切换主题", self._toggle_theme)
        tray_menu.addAction("设置", self.open_settings)
        tray_menu.addSeparator()
        tray_menu.addAction("退出程序", QApplication.instance().quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(lambda r: self.show_and_raise() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

        # UI 结构：顶栏(品牌+主题键+8按钮) + 主体(左导航+内容栈) + 底状态栏(记录数+居中搜索+帮助)
        # 实例状态
        self.group_list_map = {}      # 分组名 -> AppListWidget
        self.current_group_name = "常用"
        self.current_view = "cards"   # "cards" | "log"
        self._page_names = []          # 卡片页顺序（全部 + 各分组）

        central = QWidget(self)
        central.setObjectName("LauncherCentral")
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 主体：左导航 + 内容栈
        body = QWidget(self)
        bh = QHBoxLayout(body)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(0)
        self.sidebar = SidebarWidget(self)
        self.sidebar.selected.connect(self._on_nav_selected)
        self.sidebar.requestContextMenu.connect(self._on_sidebar_context_menu)
        self.sidebar.collapsedChanged.connect(lambda c: None)
        self.stack = QStackedWidget(self)
        # 中间内容区：背景层（底层）+ 内容栈（上层）重叠放置
        content = QWidget(self)
        cl = QGridLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self.bg_label = BackgroundLabel(content)
        cl.addWidget(self.bg_label, 0, 0)
        cl.addWidget(self.stack, 0, 0)
        bh.addWidget(self.sidebar)
        bh.addWidget(content, 1)
        v.addWidget(body)

        # 底状态栏
        statusbar = QWidget(self)
        statusbar.setObjectName("StatusBar")
        sb_layout = QHBoxLayout(statusbar)
        sb_layout.setContentsMargins(12, 0, 12, 0)
        sb_layout.setSpacing(10)
        self.rec_label = QLabel("共 0 条记录")
        self.rec_label.setObjectName("RecLabel")
        sb_layout.addWidget(self.rec_label)
        sb_layout.addStretch(1)

        self.filter_edit = QLineEdit(self)
        self.filter_edit.setObjectName("SearchInput")
        self.filter_edit.setPlaceholderText("搜索应用、URL 或备注…")
        self.filter_edit.setAlignment(Qt.AlignCenter)
        self.filter_edit.textChanged.connect(self.apply_filter)
        self.filter_edit.returnPressed.connect(self.launch_first_match)
        self.filter_edit.setMinimumWidth(200)
        self.filter_edit.setMaximumWidth(320)
        search_icon = QAction(theme.render_icon("search", "#9aa0a6", 16), "", self)
        self.filter_edit.addAction(search_icon, QLineEdit.LeadingPosition)
        # 发光边框效果
        self._apply_search_glow()
        sb_layout.addWidget(self.filter_edit)
        sb_layout.addStretch(1)

        self.help_btn = QPushButton()
        self.help_btn.setObjectName("HelpBtn")
        self.help_btn.setToolTip("帮助")
        self.help_btn.setCursor(Qt.PointingHandCursor)
        self.help_btn.setIcon(theme.render_icon("help", theme.ACTIVE["text_muted"], 16))
        self.help_btn.clicked.connect(self._show_help)
        sb_layout.addWidget(self.help_btn)
        v.addWidget(statusbar)
        self.setCentralWidget(central)

        # 顶栏：8 工具栏按钮 + 主题切换键（原生标题栏位于标准窗口顶部）
        self.main_toolbar = QToolBar("工具", self)
        self.main_toolbar.setObjectName("TopBar")
        self.main_toolbar.setMovable(False)
        self.main_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # 图标常态色跟随主题主色（薄荷绿），hover/点击由 render_icon_states 的 Active 态变白
        icon_color = theme.ACTIVE["primary"]

        def _add_tool(key, text, slot):
            action = QAction(theme.render_icon_states(key, icon_color, "#ffffff", 20), text, self)
            action.setObjectName(key)  # 供主题切换时重新着色
            action.triggered.connect(slot)
            self.main_toolbar.addAction(action)

        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.main_toolbar.addWidget(spacer)

        _add_tool("open_dir", "打开目录", self._open_app_directory)
        self.main_toolbar.addSeparator()
        _add_tool("add_group", "添加分组", self.add_group)
        _add_tool("edit_group", "编辑分组", self.rename_group)
        _add_tool("sort_group", "分组排序", self.sort_groups)
        _add_tool("delete_group", "删除分组", self.delete_current_group)
        _add_tool("clear_cache", "清空缓存", self._clear_url_cache)
        self.main_toolbar.addSeparator()
        _add_tool("settings", "设置", self.open_settings)
        theme_action = QAction(theme.render_icon_states("theme", icon_color, "#ffffff", 20), "", self)
        theme_action.setObjectName("theme")
        theme_action.setToolTip("切换浅色 / 深色主题")
        theme_action.triggered.connect(self._toggle_theme)
        self.main_toolbar.addAction(theme_action)

        self.addToolBar(self.main_toolbar)

        # 启动日志页（持久实例，_load_ui 会把它加为内容栈的最后一页）
        self.log_view = LaunchLogWidget(self)
        self.stack.currentChanged.connect(self._on_stack_changed)

        self._load_ui()
        self._apply_theme()
        self._init_background()
        self._auto_backup()
        # 必须先 show 一次以确保 winId (HWND) 被创建，然后再 hide
        self.show()
        self.hide()
        
        # 延迟初始化热键系统，确保窗口句柄完全准备好
        QTimer.singleShot(200, self._initialize_hotkeys)
        
        # 延迟恢复窗口大小，确保布局已稳定
        QTimer.singleShot(100, self._restore_window_size)
        if not self.model.settings.get("start_hidden", False):
            QTimer.singleShot(150, self.show_and_raise)

    def _auto_backup(self):
        """根据设置执行自动备份"""
        mode = self.model.settings.get("auto_backup", "none")
        if mode == "none":
            return
        backup_dir = self.model.settings.get("backup_dir", os.path.join(APP_DIR, "bak"))
        last_str = self.model.settings.get("last_backup_time", "")
        now = datetime.now()
        
        need_backup = False
        if mode == "startup":
            need_backup = True
        elif last_str:
            try:
                last_time = datetime.strptime(last_str, "%Y-%m-%d %H:%M:%S")
                delta = now - last_time
                if mode == "daily" and delta.days >= 1:
                    need_backup = True
                elif mode == "weekly" and delta.days >= 7:
                    need_backup = True
                elif mode == "monthly" and delta.days >= 30:
                    need_backup = True
            except ValueError:
                need_backup = True
        else:
            need_backup = True
        
        if not need_backup:
            return
        
        try:
            os.makedirs(backup_dir, exist_ok=True)
            backup_name = f"auto_backup_{now.strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = os.path.join(backup_dir, backup_name)
            if os.path.exists(DATA_FILE):
                import shutil
                shutil.copy2(DATA_FILE, backup_path)
                self.model.settings["last_backup_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
                self.model.save()
                print(f"[Backup] 自动备份完成: {backup_path}")
                
                # 清理旧备份
                auto_cleanup = self.model.settings.get("auto_cleanup_backup", True)
                keep_count = self.model.settings.get("backup_keep_count", 20)
                if not auto_cleanup:
                    return
                backups = sorted(
                    [f for f in os.listdir(backup_dir) if f.startswith("auto_backup_") and f.endswith(".json")],
                    reverse=True
                )
                for old in backups[keep_count:]:
                    try:
                        os.remove(os.path.join(backup_dir, old))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Backup] 自动备份失败: {e}")

    def _clear_url_cache(self):
        """清空URL图标缓存并重新异步下载"""
        import glob
        cache_files = glob.glob(os.path.join(CACHE_DIR, "*.png")) + glob.glob(os.path.join(CACHE_DIR, "*.ico"))
        count = len(cache_files)
        for f in cache_files:
            try:
                os.remove(f)
            except Exception:
                pass
        # 清空内存缓存
        im = get_icon_manager()
        im.icon_cache.clear()
        im.icon_requested.clear()
        # 重新加载UI显示默认图标
        QTimer.singleShot(0, self._load_ui)
        # 异步重新下载
        self._batch_download_favicons()
        print(f"[Cache] 已清空 {count} 个URL缓存，开始重新下载")

    def _open_app_directory(self):
        """打开软件目录"""
        app_dir = get_app_directory()
        subprocess.run(f'explorer "{app_dir}"')

    def _initialize_hotkeys(self):
        """初始化热键系统"""
        try:
            self._hotkey_filter = WindowsHotkeyFilter(self)
            QApplication.instance().installNativeEventFilter(self._hotkey_filter)
            self._apply_all_hotkeys()
            print("[Hotkey] 热键系统初始化完成")
        except Exception as e:
            print(f"[Hotkey] 热键系统初始化失败: {e}")

    def _restore_window_size(self):
        sz = self.model.settings.get("window_size", [800, 500])
        self.resize(sz[0], sz[1])

        # 居中显示
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _on_stack_changed(self, index):
        """切换到启动日志页时刷新内容并更新记录数"""
        w = self.stack.widget(index)
        if w is self.log_view:
            self.log_view.refresh()
            self.current_view = "log"
        else:
            self.current_view = "cards"
        self._update_rec_label()

    def _apply_search_glow(self):
        """底部搜索框：发光边框效果（柔和主色阴影）"""
        glow = QGraphicsDropShadowEffect(self.filter_edit)
        glow.setBlurRadius(12)
        glow.setColor(QColor(theme.ACTIVE["primary"]))
        glow.setOffset(0, 0)
        self.filter_edit.setGraphicsEffect(glow)

    # 圆角已移除：使用标准 Windows 直角边框（原生标题栏），不再自绘窗口背景

    def set_theme(self, name: str):
        """切换主题（浅色/深色）。供设置下拉与托盘菜单调用，作为切换逻辑演示。"""
        if name not in ("light", "dark"):
            return
        self.model.settings["theme"] = name
        self.model.save()
        self._apply_theme()
        self._load_ui()

    def _toggle_theme(self):
        """托盘菜单「切换主题」：在浅色/深色之间切换。"""
        current = self.model.settings.get("theme", "light")
        self.set_theme("dark" if current == "light" else "light")

    def _load_ui(self, stay_on_current_group: bool = True):
        icon_size = self.model.settings.get("icon_size", 48)
        sort_order = self.model.settings.get("sort_order", "default")
        group_sort = self.model.settings.get("group_sort_order", {})

        # 先清空内容栈中旧的分组页（保留 log_view 引用，稍后重新加入）
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
        self.group_list_map = {}

        # 全部 + 各分组（按排序数字排列）
        sorted_groups = sorted(self.model.groups.items(), key=lambda x: group_sort.get(x[0], 255))
        all_items = [it for items in self.model.groups.values() for it in items]
        if sort_order == "click_count":
            all_items = sorted(all_items, key=lambda x: getattr(x, 'click_count', 0), reverse=True)
        pages = [("全部", all_items)]
        # 跳过与导航保留项重名的分组（如数据里误存的「全部」「启动日志」），避免重复显示
        reserved = ("全部", "启动日志")
        for group, items in sorted_groups:
            if group in reserved:
                continue
            if sort_order == "click_count":
                items = sorted(items, key=lambda x: getattr(x, 'click_count', 0), reverse=True)
            pages.append((group, items))

        # 默认选中分组：优先"常用"，否则第一个真实分组
        default_group = "常用" if "常用" in self.model.groups else (sorted_groups[0][0] if sorted_groups else "全部")
        prev = self.current_group_name if hasattr(self, "current_group_name") else None
        if stay_on_current_group and prev is not None and prev in [p[0] for p in pages]:
            target = prev
        else:
            target = default_group

        for name, items in pages:
            lw = AppListWidget(self, group_name=name)
            lw.setIconSize(QSize(icon_size, icon_size))
            lw.setGridSize(QSize(icon_size + 42, icon_size + 42))
            lw.populate(items)
            self.stack.addWidget(lw)
            self.group_list_map[name] = lw
        # 日志页（最后）
        self.stack.addWidget(self.log_view)

        # 侧边栏数据：启动日志置顶 + 全部 + 各分组
        total = len(all_items)
        log_count = len(self.log_view._load_records())
        entries = [("启动日志", log_count, True)]
        for name, items in pages:
            entries.append((name, len(items), False))
        self._page_names = [p[0] for p in pages]
        print(f"[DEBUG _load_ui] 准备刷新侧边栏, entries={entries}")
        self.sidebar.set_groups(entries, target)
        # 侧边栏刷新后强制重绘，确保新分组名可见
        self.sidebar.update()
        self.sidebar.repaint()
        print(f"[DEBUG _load_ui] 侧边栏刷新完成")

        # 显示对应页（延后一帧执行，确保侧边栏 rebuild 先完成 paint 事件）
        if target == "启动日志":
            QTimer.singleShot(0, self._show_log)
        else:
            QTimer.singleShot(0, lambda n=target: self._show_group(n))

        if self.filter_edit.text().strip():
            self.apply_filter()

        # 首次启动时异步批量下载缺失的URL图标
        if not hasattr(self, '_favicon_batch_done'):
            self._favicon_batch_done = True
            self._batch_download_favicons()

    # ---- 视图切换辅助 ----
    def _show_group(self, name):
        lw = self.group_list_map.get(name)
        if lw is None:
            print(f"[DEBUG _show_group] group_list_map 中未找到: {name}, 当前keys={list(self.group_list_map.keys())}")
            return
        self.stack.setCurrentWidget(lw)
        self.current_group_name = name
        self.current_view = "cards"
        self.sidebar._set_current(name)
        self._update_rec_label()

    def _show_log(self):
        self.stack.setCurrentWidget(self.log_view)
        self.current_view = "log"
        self.sidebar._set_current("启动日志")
        self.log_view.refresh()
        self._update_rec_label()

    # ---- 中间内容区背景轮播 ----
    def _bg_fallback_color(self):
        name = self.model.settings.get("theme", "light")
        return "#a6e3e9" if name == "light" else "#303841"

    def _init_background(self):
        """初始化背景轮播：扫描图片、应用回退色、启动定时器。"""
        self.bg_images = scan_background_images()
        self.bg_label.set_fallback_color(self._bg_fallback_color())
        self.bg_timer = QTimer(self)
        self.bg_timer.timeout.connect(self._cycle_background)
        if self.bg_images:
            self._cycle_background()
            interval = max(1, int(self.model.settings.get("bg_interval", 30)))
            self.bg_timer.start(interval * 1000)
        else:
            self.bg_label.set_fallback_color(self._bg_fallback_color())

    def _cycle_background(self):
        if not self.bg_images:
            self.bg_label.set_fallback_color(self._bg_fallback_color())
            return
        path = random.choice(self.bg_images)
        # 多图时尽量避免连续重复
        if len(self.bg_images) > 1 and getattr(self, "_last_bg", None) == path:
            path = random.choice(self.bg_images)
        pm = QPixmap(path)
        if pm.isNull():
            return
        self._last_bg = path
        self.bg_label.set_pixmap(pm)

    def _refresh_background(self):
        """设置变更后重新扫描图片并按新间隔重启轮播。"""
        self.bg_images = scan_background_images()
        if not hasattr(self, "bg_timer"):
            self.bg_timer = QTimer(self)
            self.bg_timer.timeout.connect(self._cycle_background)
        self.bg_timer.stop()
        if self.bg_images:
            self._cycle_background()
            interval = max(1, int(self.model.settings.get("bg_interval", 30)))
            self.bg_timer.start(interval * 1000)
        else:
            self.bg_label.set_fallback_color(self._bg_fallback_color())

    def _on_nav_selected(self, name):
        print(f"[DEBUG _on_nav_selected] 收到信号: name={name}")
        if name == "启动日志":
            self._show_log()
        else:
            self._show_group(name)

    def current_list_widget(self):
        """当前选中分组的 AppListWidget（与视图无关）。"""
        return self.group_list_map.get(self.current_group_name)

    def _update_rec_label(self):
        if self.current_view == "log":
            total = len(self.log_view._load_records())
            self.rec_label.setText(f"共 {total} 条记录")
        else:
            lw = self.current_list_widget()
            n = lw.count() if lw is not None else 0
            # 搜索时显示可见数量
            visible = sum(1 for i in range(n) if not lw.item(i).isHidden()) if lw else 0
            self.rec_label.setText(f"共 {visible} 条记录")

    def _show_help(self):
        QMessageBox.information(
            self, "angel Start v1",
            "· 左键单击 / 双击 启动项目\n"
            "· 底部搜索框按名称 / 分组过滤（在日志页按名称/分组/触发方式过滤）\n"
            "· 左上角 ☰ 可折叠导航为仅图标\n"
            "· 顶栏 🌗 切换浅色 / 深色主题（自动记忆）"
        )

    def _batch_download_favicons(self):
        """异步批量下载所有缺失的URL图标"""
        im = get_icon_manager()
        for group_name, items in self.model.groups.items():
            for item in items:
                if is_url(item.target) and not (item.icon_path and os.path.exists(item.icon_path)):
                    domain = url_domain(item.target)
                    if domain:
                        fav_cache_key = hashlib.md5(domain.encode()).hexdigest()
                        cache_path = os.path.join(CACHE_DIR, f"{fav_cache_key}.png")
                        if not os.path.exists(cache_path):
                            QTimer.singleShot(0, lambda url=item.target: im.get_favicon(url))

    def add_group(self):
        name, ok = self.prompt_text("添加分组", "")
        if ok and name:
            if name in self.model.groups:
                QMessageBox.information(self, "提示", "分组已存在")
                return
            self.model.groups[name] = []
            self.model.save()
            print(f"[DEBUG add_group] 分组已添加: {name}, groups={list(self.model.groups.keys())}")
            QTimer.singleShot(0, self._load_ui)

    def delete_current_group(self):
        group = self.current_group()
        if group and QMessageBox.question(self, "删除分组", f"是否删除分组: {group}") == QMessageBox.Yes:
            if group in self.model.groups:
                del self.model.groups[group]
                if not self.model.groups:
                    self.model.groups["默认"] = []
                self.model.save()
            QTimer.singleShot(0, self._load_ui)

    def _on_sidebar_context_menu(self, group_name: str, global_pos: QPoint):
        if group_name in ("启动日志", "全部"):
            return
        menu = QMenu(self)
        rename_action = menu.addAction("✏️ 重命名分组")
        sort_action = menu.addAction("🔀 分组排序")
        menu.addSeparator()
        delete_action = menu.addAction("❌ 删除分组")
        action = menu.exec_(global_pos)
        if action == rename_action:
            self.rename_group(group_name)
        elif action == sort_action:
            self.sort_groups()
        elif action == delete_action:
            self.delete_current_group()

    def rename_group(self, old_name: str = None):
        group = old_name if old_name else self.current_group()
        if not group:
            return
        new_name, ok = self.prompt_text("重命名分组", group)
        if ok and new_name and new_name != group:
            if new_name in self.model.groups:
                QMessageBox.information(self, "提示", "分组名已存在")
                return
            # 保持字典顺序，替换键名
            new_groups = {}
            for k, v in self.model.groups.items():
                if k == group:
                    new_groups[new_name] = v
                    # 更新所有项目的分组字段
                    for item in v:
                        item.group = new_name
                else:
                    new_groups[k] = v
            self.model.groups = new_groups
            self.model.save()
            QTimer.singleShot(0, self._load_ui)

    def sort_groups(self):
        group_names = list(self.model.groups.keys())
        if len(group_names) < 2:
            QMessageBox.information(self, "提示", "至少需要两个分组才能排序")
            return
        current_sort_order = self.model.settings.get("group_sort_order", {})
        dlg = GroupSortDialog(self, group_names, current_sort_order)
        if dlg.exec_() == QDialog.Accepted:
            new_order = dlg.get_order()
            new_groups = {}
            for name in new_order:
                if name in self.model.groups:
                    new_groups[name] = self.model.groups[name]
            self.model.groups = new_groups
            self.model.settings["group_sort_order"] = dlg.get_sort_order()
            self.model.save()
            QTimer.singleShot(0, lambda: self._load_ui(stay_on_current_group=True))

    def current_group(self) -> str:
        return getattr(self, "current_group_name", "默认")

    def add_item_dialog(self, group: str, mode: str = "file"):
        dlg = ItemEditor(self, mode=mode)
        if dlg.exec_() == QDialog.Accepted:
            result = dlg.get_item()
            if result:
                item = result['item']
                position = result['position'] - 1  # 转换为0基索引
                item.group = group
                
                # 根据用户选择的排序位置插入项目
                items = self.model.groups.get(group, [])
                if position >= len(items):
                    # 如果位置超出范围，添加到末尾
                    items.append(item)
                else:
                    # 插入到指定位置
                    items.insert(position, item)
                
                self.model.groups[group] = items
                self.model.save()
                
                # 添加URL时立即异步下载图标
                if is_url(item.target) and not (item.icon_path and os.path.exists(item.icon_path)):
                    im = get_icon_manager()
                    QTimer.singleShot(0, lambda url=item.target: im.get_favicon(url))
                
                # 重新注册所有热键（包括新添加的的应用热键）
                self._apply_all_hotkeys()
                QTimer.singleShot(0, self._load_ui)  # 重新加载界面

    def add_item_to_group(self, item: AppItem):
        self.model.add_item(item)
        self.model.save()
        # 添加URL时立即异步下载图标
        if is_url(item.target) and not (item.icon_path and os.path.exists(item.icon_path)):
            im = get_icon_manager()
            QTimer.singleShot(0, lambda url=item.target: im.get_favicon(url))
        # 重新注册热键
        self._apply_all_hotkeys()
        QTimer.singleShot(0, self._load_ui)  # 重新加载界面以更新序号

    def delete_item(self, group: str, index: int):
        self.model.remove_item(group, index)
        self.model.save()
        # 重新注册热键
        self._apply_all_hotkeys()
        QTimer.singleShot(0, self._load_ui)  # 重新加载界面以更新序号

    def edit_item(self, group: str, index: int):
        item = self.model.groups.get(group, [])[index]
        dlg = ItemEditor(self, item, current_index=index)
        if dlg.exec_() == QDialog.Accepted:
            result = dlg.get_item()
            if result:
                new_item = result['item']
                new_position = result['position'] - 1  # 转换为0基索引
                new_item.group = group
                
                # 清除旧图标缓存，确保编辑后立即显示新图标
                im = get_icon_manager()
                im.icon_cache.pop(item.target, None)
                im.icon_cache.pop(new_item.target, None)
                
                # 如果位置发生变化，需要重新排序
                if new_position != index:
                    # 获取当前分组的所有项目
                    items = self.model.groups.get(group, [])
                    # 移除原位置的项目
                    items.pop(index)
                    # 插入到新位置
                    items.insert(new_position, new_item)
                    # 更新模型
                    self.model.groups[group] = items
                    self.model.save()
                    # 重新注册热键
                    self._apply_all_hotkeys()
                    QTimer.singleShot(0, self._load_ui)  # 重新加载界面
                else:
                    # 位置未变化，只更新项目信息
                    self.update_item(group, index, new_item)

    def update_item(self, group: str, index: int, item: AppItem):
        self.model.update_item(group, index, item)
        self.model.save()
        # 重新注册热键
        self._apply_all_hotkeys()
        QTimer.singleShot(0, self._load_ui)  # 重新加载界面以更新序号

    def copy_item_to_group(self, source_group: str, index: int, target_group: str):
        """
        复制项目到其他分组
        
        Args:
            source_group: 源分组名称
            index: 项目索引
            target_group: 目标分组名称
        """
        # 获取源项目
        source_items = self.model.groups.get(source_group, [])
        if index < 0 or index >= len(source_items):
            return
        
        source_item = source_items[index]
        
        # 创建项目的副本（更新分组信息）
        copied_item = AppItem(
            name=source_item.name,
            target=source_item.target,
            remarks=source_item.remarks,
            group=target_group,
            icon_path=source_item.icon_path
        )
        
        # 添加到目标分组
        target_items = self.model.groups.get(target_group, [])
        target_items.append(copied_item)
        self.model.groups[target_group] = target_items
        
        # 保存并刷新界面
        self.model.save()
        self._load_ui()

    def move_item_to_group(self, source_group: str, index: int, target_group: str):
        """
        移动项目到其他分组
        
        Args:
            source_group: 源分组名称
            index: 项目索引
            target_group: 目标分组名称
        """
        # 获取源项目
        source_items = self.model.groups.get(source_group, [])
        if index < 0 or index >= len(source_items):
            return
        
        source_item = source_items[index]
        
        # 从源分组中移除项目
        source_items.pop(index)
        self.model.groups[source_group] = source_items
        
        # 更新项目的分组信息
        source_item.group = target_group
        
        # 添加到目标分组
        target_items = self.model.groups.get(target_group, [])
        target_items.append(source_item)
        self.model.groups[target_group] = target_items
        
        # 如果源分组为空，删除该分组（保留默认分组）
        if not source_items and source_group != "默认":
            del self.model.groups[source_group]
        
        # 保存并刷新界面
        self.model.save()
        self._load_ui()

    def batch_delete(self, group: str, selected_items):
        """批量删除选中的项目（按 item.group 解析真实分组，支持「全部」视图）"""
        count = len(selected_items)
        reply = QMessageBox.question(self, "批量删除", f"确定要删除选中的 {count} 个项目吗？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        for list_item in selected_items:
            item = list_item.data(Qt.UserRole)
            g = item.group
            items = self.model.groups.get(g, [])
            if item in items:
                items.remove(item)
                self.model.groups[g] = items
        self.model.save()
        self._apply_all_hotkeys()
        QTimer.singleShot(0, self._load_ui)

    def batch_run(self, selected_items):
        """批量运行选中的项目"""
        for list_item in selected_items:
            item: AppItem = list_item.data(Qt.UserRole)
            target = item.target
            work_dir = item.work_dir if hasattr(item, 'work_dir') else None
            launch_args = item.launch_args if hasattr(item, 'launch_args') else None
            # 记录启动日志
            log_launch(item, "批量", enabled=self.model.settings.get("enable_launch_log", True))
            def do_launch(t=target, wd=work_dir, la=launch_args):
                try:
                    if is_url(t):
                        webbrowser.open(t)
                    else:
                        launch_target(t, wd, la)
                except Exception as e:
                    print(f"批量启动失败: {e}")
            threading.Thread(target=do_launch, daemon=True).start()

    def batch_copy(self, source_group: str, selected_items, target_group: str):
        """批量复制选中的项目到其他分组"""
        target_items = self.model.groups.get(target_group, [])
        for list_item in selected_items:
            item: AppItem = list_item.data(Qt.UserRole)
            copied_item = AppItem(
                name=item.name,
                target=item.target,
                remarks=item.remarks,
                group=target_group,
                icon_path=item.icon_path,
                work_dir=item.work_dir,
                launch_args=item.launch_args,
                hotkey=item.hotkey,
                click_count=item.click_count
            )
            target_items.append(copied_item)
        self.model.groups[target_group] = target_items
        self.model.save()
        self._load_ui()

    def batch_move(self, source_group: str, selected_items, target_group: str):
        """批量移动选中的项目到其他分组（按 item.group 解析真实源分组，支持「全部」视图）"""
        target_items = self.model.groups.get(target_group, [])
        affected_sources = set()
        for list_item in selected_items:
            item = list_item.data(Qt.UserRole)
            g = item.group
            items = self.model.groups.get(g, [])
            if item in items:
                items.remove(item)
                item.group = target_group
                target_items.append(item)
                affected_sources.add(g)
                self.model.groups[g] = items
        self.model.groups[target_group] = target_items
        # 清理已空的源分组（保留默认分组）
        for g in affected_sources:
            if not self.model.groups.get(g) and g != "默认":
                del self.model.groups[g]
        self.model.save()
        self._apply_all_hotkeys()
        self._load_ui()

    def prompt_text(self, title: str, initial: str = ""):
        text, ok = QInputDialog.getText(self, title, "", text=initial)
        return text, ok

    def apply_filter(self):
        t = self.filter_edit.text().strip()
        # 在日志视图时，把底栏搜索驱动到日志页自带搜索
        if self.current_view == "log":
            if self.log_view.search_edit.text() != t:
                self.log_view.search_edit.setText(t)
            else:
                self.log_view.refresh()
            self._update_rec_label()
            return
        # 卡片视图：按名称/分组过滤各分组列表
        for lw in self.group_list_map.values():
            for j in range(lw.count()):
                it = lw.item(j)
                app: AppItem = it.data(Qt.UserRole)
                it.setHidden(not app.matches(t.lower()))
        self._update_rec_label()

    def launch_first_match(self):
        # 优先启动当前已选中的项目
        lw = self.current_list_widget()
        if lw is not None:
            current = lw.currentItem()
            if current and not current.isHidden():
                item = current.data(Qt.UserRole)
                work_dir = item.work_dir if hasattr(item, 'work_dir') else None
                log_launch(item, "搜索回车", enabled=self.model.settings.get("enable_launch_log", True))
                launch_target(item.target, work_dir)
                self.hide()
                return

        t = self.filter_edit.text().strip().lower()
        # 跨所有分组找第一个匹配项
        for lw in self.group_list_map.values():
            for j in range(lw.count()):
                it = lw.item(j)
                if not it.isHidden():
                    item = it.data(Qt.UserRole)
                    work_dir = item.work_dir if hasattr(item, 'work_dir') else None
                    log_launch(item, "搜索回车", enabled=self.model.settings.get("enable_launch_log", True))
                    launch_target(item.target, work_dir)
                    self.hide()
                    return

    def _animate_startup(self):
        lw = self.current_list_widget()
        if lw is None:
            return
        total = lw.count()
        for i in range(total):
            it = lw.item(i)
            it.setHidden(True)

        def reveal_step(step=[0]):
            i = step[0]
            if i >= total:
                return
            lw.item(i).setHidden(False)
            step[0] += 1
            QTimer.singleShot(40, reveal_step)

        QTimer.singleShot(80, reveal_step)

    def show_and_raise(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.filter_edit.clear()
        self.filter_edit.setFocus()

    def closeEvent(self, event):
        # 保存窗口大小和工具栏位置
        self.model.settings["window_size"] = [self.width(), self.height()]
        # 获取工具栏当前停靠区域
        area = self.toolBarArea(self.main_toolbar)
        self.model.settings["toolbar_area"] = area.value
        
        self.model.save()
        event.accept()
        QApplication.instance().quit()

    def toggle_visibility(self):
        # 如果窗口隐藏或者不是当前活动窗口，则显示并置顶
        if self.isHidden() or not self.isActiveWindow():
            self.show_and_raise()
        else:
            self.hide()

    def open_settings(self):
        # 打开设置时注销所有热键
        if hasattr(self, '_hotkey_filter'):
            self._hotkey_filter.unregister_all()
            print("[Hotkey] 已注销所有热键")
            
        dlg = SettingsDialog(self, settings=self.model.settings)
        if dlg.exec_() == QDialog.Accepted:
            res = dlg.result_values()
            old_size = self.model.settings.get("window_size", [800, 500])
            self.model.settings.update(res)
            self.model.save()
            # 背景轮播：按新设置重新扫描图片并重启定时器
            if hasattr(self, "_refresh_background"):
                self._refresh_background()
            
            # 应用窗口大小变化
            new_size = res.get("window_size", old_size)
            if new_size != old_size:
                self.resize(new_size[0], new_size[1])
                # 重新居中
                screen = QGuiApplication.primaryScreen().availableGeometry()
                x = (screen.width() - self.width()) // 2
                y = (screen.height() - self.height()) // 2
                self.move(x, y)
        
        # 无论用户点击确定还是取消，都重新注册热键
        self._apply_all_hotkeys()
        print("[Hotkey] 已重新注册所有热键")
        
        self._apply_autostart(self.model.settings["autostart"])
        self._load_ui() # 实时刷新界面（包括图标大小）
        self._apply_theme()

    def _apply_all_hotkeys(self):
        self._hotkey_filter.unregister_all()
        hks = self.model.settings.get("hotkeys", {})
        # 使用 toggle_visibility 实现同一个热键显示和隐藏
        self._hotkey_filter.register(hks.get("show_hide"), self.toggle_visibility)
        self._hotkey_filter.register(hks.get("opacity_up"), self._on_opacity_up)
        self._hotkey_filter.register(hks.get("opacity_down"), self._on_opacity_down)
        self._hotkey_filter.register(hks.get("lock"), self._on_lock)
        self._hotkey_filter.register(hks.get("unlock"), self._on_unlock)
        self._hotkey_filter.register(hks.get("lock"), self._on_lock)
        self._hotkey_filter.register(hks.get("unlock"), self._on_unlock)
        
        # 分组切换使用本地快捷键，不再注册为全局热键
        self._update_local_shortcuts()

        # 注册应用程序热键
        self._register_app_hotkeys()

    def _register_app_hotkeys(self):
        """注册所有应用程序的启动热键"""
        for group_name, items in self.model.groups.items():
            for item in items:
                if hasattr(item, 'hotkey') and item.hotkey:
                    # 使用闭包捕获当前的 item
                    def make_launcher(app_item):
                        enabled = self.model.settings.get("enable_launch_log", True)
                        def _run():
                            log_launch(app_item, "热键", enabled=enabled)
                            launch_target(app_item.target, app_item.work_dir)
                        return _run
                    
                    print(f"[Hotkey] 注册应用热键: {item.hotkey} -> {item.name}")
                    self._hotkey_filter.register(item.hotkey, make_launcher(item))

    def _get_focus_hwnd(self):
        return ctypes.windll.user32.GetForegroundWindow()

    def _on_opacity_up(self): self._change_opacity(10)
    def _on_opacity_down(self): self._change_opacity(-10)

    def _change_opacity(self, delta):
        """修改当前获得焦点的窗口的透明度"""
        try:
            # 获取当前焦点窗口的句柄
            hwnd = self._get_focus_hwnd()
            if not hwnd: 
                print("[Opacity] 无法获取窗口句柄")
                return
            
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            LWA_ALPHA = 0x2
            
            # 确保窗口支持透明度
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if not (style & WS_EX_LAYERED):
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
                print(f"[Opacity] 启用窗口透明度支持")
            
            # 获取当前透明度
            curr_alpha = ctypes.c_ubyte(255)
            ctypes.windll.user32.GetLayeredWindowAttributes(hwnd, None, ctypes.byref(curr_alpha), None)
            
            # 计算新的透明度
            new_alpha = max(30, min(255, curr_alpha.value + delta))
            
            # 应用新的透明度
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, new_alpha, LWA_ALPHA)
            
            print(f"[Opacity] 透明度调整: {curr_alpha.value} -> {new_alpha}")
            
        except Exception as e:
            print(f"[Opacity] 调整透明度时出错: {e}")

    def _on_lock(self): self._set_lock(True)
    def _on_unlock(self): self._set_lock(False)

    def _update_local_shortcuts(self):
        """更新本地快捷键"""
        # 清除旧的快捷键
        if hasattr(self, '_local_shortcuts'):
            for sc in self._local_shortcuts:
                sc.setEnabled(False)
                sc.setParent(None)
        self._local_shortcuts = []
        
        hks = self.model.settings.get("hotkeys", {})
        
        # 下一个分组
        next_seq = hks.get("next_group", "Ctrl+`")
        if next_seq:
            sc = QShortcut(QKeySequence(next_seq), self)
            sc.activated.connect(self._on_next_group)
            self._local_shortcuts.append(sc)
            
        # 上一个分组
        prev_seq = hks.get("prev_group", "Ctrl+1")
        if prev_seq:
            sc = QShortcut(QKeySequence(prev_seq), self)
            sc.activated.connect(self._on_prev_group)
            self._local_shortcuts.append(sc)
            
    def _on_next_group(self):
        names = self._page_names
        if len(names) > 1:
            idx = names.index(self.current_group_name) if self.current_group_name in names else 0
            self._show_group(names[(idx + 1) % len(names)])
            if self.isHidden():
                self.show_and_raise()

    def _on_prev_group(self):
        names = self._page_names
        if len(names) > 1:
            idx = names.index(self.current_group_name) if self.current_group_name in names else 0
            self._show_group(names[(idx - 1 + len(names)) % len(names)])
            if self.isHidden():
                self.show_and_raise()

    def _set_lock(self, lock):
        hwnd = self._get_focus_hwnd()
        if not hwnd: return
        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x20
        WS_EX_LAYERED = 0x80000
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if lock:
            new_style = style | WS_EX_TRANSPARENT | WS_EX_LAYERED
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            # 锁定时在当前透明度基础上稍微透明
            curr_alpha = ctypes.c_ubyte(255)
            ctypes.windll.user32.GetLayeredWindowAttributes(hwnd, None, ctypes.byref(curr_alpha), None)
            # 降低透明度15个单位，但不低于180
            new_alpha = max(180, curr_alpha.value - 15)
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, new_alpha, 0x2)
            print(f"[Lock] 锁定时透明度调整: {curr_alpha.value} -> {new_alpha}")
        else:
            new_style = style & ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            # 解锁时恢复到不设置透明度的时候
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)
            pass

    def _apply_autostart(self, enabled: bool):
        import winreg
        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "angel Start"
        
        # 检测是否为编译后的程序
        if getattr(sys, 'frozen', False):
            # 如果是编译后的程序（包括PyInstaller、Nuitka等），直接使用可执行文件路径
            cmd = f'"{sys.executable}"'
        elif hasattr(sys, 'nuitka_binary_dir'):
            # Nuitka编译的程序可能设置了这个属性
            cmd = f'"{sys.executable}"'
        else:
            # 如果是脚本形式，使用pythonw.exe以静默运行
            exe_path = sys.executable.replace("python.exe", "pythonw.exe")
            script_path = os.path.abspath(__file__)
            cmd = f'"{exe_path}" "{script_path}"'
        
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_ALL_ACCESS) as key:
                if enabled:
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                    except FileNotFoundError:
                        pass
        except Exception as e:
            print(f"Set autostart failed: {e}")

    def _apply_theme(self):
        name = self.model.settings.get("theme", "light")
        c = theme.colors(name)
        theme.set_active(name)  # 供 AppCardDelegate / 工具栏图标实时读取

        # SpinBox 上下箭头 SVG（沿用文件写入方式，集中到 theme 模块）
        arrow_dir = os.path.join(get_app_directory(), "_arrows")
        up_url, down_url = theme.spin_arrow_css(arrow_dir, c["text"])

        self.setStyleSheet(theme.build_stylesheet(c, up_url, down_url, name))

        # 调色板（兜底，确保原生控件颜色正确）
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(c["bg"]))
        palette.setColor(QPalette.WindowText, QColor(c["text"]))
        palette.setColor(QPalette.Base, QColor(c["bg"]))
        palette.setColor(QPalette.AlternateBase, QColor(c["bg_alt"]))
        palette.setColor(QPalette.ToolTipBase, QColor(c["bg"]))
        palette.setColor(QPalette.ToolTipText, QColor(c["text"]))
        palette.setColor(QPalette.Text, QColor(c["text"]))
        palette.setColor(QPalette.Button, QColor(c["bg_alt"]))
        palette.setColor(QPalette.ButtonText, QColor(c["text"]))
        palette.setColor(QPalette.Highlight, QColor(c["primary"]))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        self.setPalette(palette)

        # 工具栏线性图标按当前主题主色重新着色（切主题时跟随变动）
        tint = c["primary"]
        for a in self.main_toolbar.actions():
            key = a.objectName()
            if key in theme.ICONS:
                a.setIcon(theme.render_icon_states(key, tint, "#ffffff", 20))

        # 提示文案随主题更新颜色（已移除 hint_label，此处跳过）

        # 搜索框发光颜色随主题更新
        glow = self.filter_edit.graphicsEffect()
        if glow is not None:
            glow.setColor(QColor(c["primary"]))

        # 背景层回退色随主题更新（无图时显示对应纯色）
        if hasattr(self, "bg_label"):
            self.bg_label.set_fallback_color(self._bg_fallback_color())

        # 侧栏图标 / 折叠按钮 / 帮助按钮随主题重新着色
        if hasattr(self, "sidebar"):
            self.sidebar.recolor()
        if hasattr(self, "help_btn"):
            self.help_btn.setIcon(theme.render_icon("help", c["text_muted"], 16))

        # 刷新列表（图标卡片委托读取 theme.ACTIVE）
        for i in range(self.stack.count()):
            w = self.stack.widget(i)
            if hasattr(w, "viewport"):
                w.viewport().update()

        # 标准 Windows 标题栏：仅去掉 Win11 圆角（Win10 风格直角边框），不自定义标题栏配色
        self._set_title_bar_color(c["bg"], c["text"])

    def _set_title_bar_color(self, bg_color, text_color):
        """标准 Windows 样式标题栏：仅请求去掉 Win11 圆角（Win10 风格直角边框），
        不自定义标题栏配色，沿用系统默认标题栏。"""
        try:
            hwnd = int(self.winId())
            if not hwnd:
                return
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_DONOTROUND = 1
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(ctypes.c_int(DWMWCP_DONOTROUND)),
                4,
            )
        except Exception:
            # Win10 或无 DWM 环境：无操作，使用系统默认标题栏
            pass

    def nativeEvent(self, eventType, message):
        """处理 Windows 底层消息，直接截获热键"""
        try:
            # PySide6 在 Windows 上 eventType 可能是字节串也要检查
            if eventType == b"windows_generic_MSG" or eventType == "windows_generic_MSG":
                # message 是一个指针，需要转换为整数地址
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == 0x0312:  # WM_HOTKEY
                    atom_id = msg.wParam
                    print(f"[Window] 接收到热键消息，原子ID: {atom_id}")
                    
                    if hasattr(self, '_hotkey_filter') and self._hotkey_filter and atom_id in self._hotkey_filter._hotkeys:
                        print(f"[Window] 调用热键处理器")
                        self._hotkey_filter._hotkeys[atom_id]()
                        print(f"[Window] 热键处理完成")
                        return True, 0  # 表示消息已处理，阻止进一步传播
                    else:
                        print(f"[Window] 未找到对应的热键处理器")
                        print(f"[Window] 当前已注册热键: {list(self._hotkey_filter._hotkeys.keys()) if hasattr(self, '_hotkey_filter') and self._hotkey_filter else '无过滤器'}")
        except Exception as e:
            print(f"[Window] nativeEvent处理出错: {e}")
            
        return super().nativeEvent(eventType, message)


class WindowsHotkeyFilter(QAbstractNativeEventFilter):
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    WM_HOTKEY = 0x0312

    def __init__(self, parent_window=None):
        super().__init__()
        self._window = parent_window
        self._hotkeys = {}  # atom_id -> callback
        self._atoms = {}    # name -> atom_id

    def register(self, shortcut: str, callback):
        if not shortcut: return
        try:
            mods, vk = self._parse_shortcut(shortcut)
            atom_name = f"QuickLauncherHotkey_{shortcut}_{mods}_{vk}"
            atom_id = ctypes.windll.kernel32.GlobalAddAtomW(atom_name)
            
            # 使用窗口句柄进行注册，比全局注册更稳定
            hwnd = int(self._window.winId()) if self._window else None
            
            ctypes.windll.user32.UnregisterHotKey(hwnd, atom_id)
            if ctypes.windll.user32.RegisterHotKey(hwnd, atom_id, mods, vk):
                self._hotkeys[atom_id] = callback
                self._atoms[shortcut] = atom_id
                print(f"[Hotkey] Registered: {shortcut} to HWND {hwnd} (ID: {atom_id})")
            else:
                err = ctypes.windll.kernel32.GetLastError()
                print(f"[Hotkey] Failed to register: {shortcut}, Error: {err}")
        except Exception as e:
            print(f"[Hotkey] Error: {e}")

    def _parse_shortcut(self, hk: str):
        print(f"[DEBUG Hotkey] Parsing shortcut: '{hk}'")
        parts = [p.strip().lower() for p in hk.split('+') if p.strip()]
        print(f"[DEBUG Hotkey] Parsed parts: {parts}")
        mods = 0
        key = None
        for p in parts:
            if p in ("ctrl", "control"): 
                mods |= self.MOD_CONTROL
                print(f"[DEBUG Hotkey] Added MOD_CONTROL")
            elif p == "alt": 
                mods |= self.MOD_ALT
                print(f"[DEBUG Hotkey] Added MOD_ALT")
            elif p == "shift": 
                mods |= self.MOD_SHIFT
                print(f"[DEBUG Hotkey] Added MOD_SHIFT")
            elif p in ("win", "meta"): 
                mods |= self.MOD_WIN
                print(f"[DEBUG Hotkey] Added MOD_WIN")
            else: 
                key = p
                print(f"[DEBUG Hotkey] Found key: '{key}'")
        
        vk = self._key_to_vk(key or "q")
        print(f"[DEBUG Hotkey] Final mods: {mods}, vk: {vk}")
        return mods, vk

    def _key_to_vk(self, k: str):
        print(f"[DEBUG Hotkey] Converting key '{k}' to VK")
        k = k.lower()
        
        # 特殊字符的 OEM 键码映射
        special_keys = {
            '=': 0xBB,    # VK_OEM_PLUS (=+ 键)
            '+': 0xBB,    # VK_OEM_PLUS (=+ 键)
            '-': 0xBD,    # VK_OEM_MINUS (-_ 键)
            '_': 0xBD,    # VK_OEM_MINUS (-_ 键)
            '[': 0xDB,    # VK_OEM_4 ([{ 键)
            '{': 0xDB,    # VK_OEM_4 ([{ 键)
            ']': 0xDD,    # VK_OEM_6 (]} 键)
            '}': 0xDD,    # VK_OEM_6 (]} 键)
            ';': 0xBA,    # VK_OEM_1 (:; 键)
            ':': 0xBA,    # VK_OEM_1 (:; 键)
            '\'': 0xDE,   # VK_OEM_7 ('" 键)
            '"': 0xDE,    # VK_OEM_7 ('" 键)
            ',': 0xBC,    # VK_OEM_COMMA (<, 键)
            '<': 0xBC,    # VK_OEM_COMMA (<, 键)
            '.': 0xBE,    # VK_OEM_PERIOD (>. 键)
            '>': 0xBE,    # VK_OEM_PERIOD (>. 键)
            '/': 0xBF,    # VK_OEM_2 (/? 键)
            '?': 0xBF,    # VK_OEM_2 (/? 键)
            '`': 0xC0,    # VK_OEM_3 (`~ 键)
            '~': 0xC0,    # VK_OEM_3 (`~ 键)
        }
        
        if len(k) == 1:
            # 优先检查特殊字符
            if k in special_keys:
                return special_keys[k]
            # 然后检查普通 ASCII 字符
            return ord(k.upper())
            
        # 功能键映射
        mapping = {
            'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74, 'f6': 0x75,
            'f7': 0x76, 'f8': 0x77, 'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
            'escape': 0x1B, 'esc': 0x1B, 'space': 0x20, '空格': 0x20, 'tab': 0x09, 
            'enter': 0x0D, '回车': 0x0D, 'return': 0x0D,
            'up': 0x26, '向上': 0x26, 'down': 0x28, '向下': 0x28,
            'left': 0x25, '向左': 0x25, 'right': 0x27, '向右': 0x27,
            'backspace': 0x08, '退格': 0x08, 'delete': 0x2E, '删除': 0x2E
        }
        return mapping.get(k, ord('Q'))

    def unregister_all(self):
        hwnd = int(self._window.winId()) if self._window else None
        for atom_id in list(self._hotkeys.keys()):
            ctypes.windll.user32.UnregisterHotKey(hwnd, atom_id)
            ctypes.windll.kernel32.GlobalDeleteAtom(atom_id)
        self._hotkeys.clear()
        self._atoms.clear()

    def nativeEventFilter(self, eventType: bytes, message: int):
        if sys.platform != 'win32':
            return False, 0
        try:
            msg = ctypes.wintypes.MSG.from_address(message)
            if msg.message == self.WM_HOTKEY:
                atom_id = msg.wParam
                if atom_id in self._hotkeys:
                    # 如果窗口 nativeEvent 没截获到（例如窗口未激活），这里作为兜底
                    self._hotkeys[atom_id]()
                    return True, 0
        except Exception:
            pass
        return False, 0


def selftest():
    os.environ["LAUNCHER_DATA_FILE"] = os.path.join(DATA_DIR, "test_launcher.json")
    ensure_dirs()
    m = LauncherModel()
    m.load()
    m.groups = {"默认": []}
    a1 = AppItem(name="记事本", target=r"C:\Windows\System32\notepad.exe", remarks="notepad", group="默认")
    a2 = AppItem(name="主页", target="https://www.example.com", remarks="ex", group="默认")
    m.add_item(a1)
    m.add_item(a2)
    m.save()
    m2 = LauncherModel()
    m2.load()
    assert len(m2.groups.get("默认", [])) == 2
    assert m2.groups["默认"][0].matches("note")
    assert m2.groups["默认"][1].matches("example")
    app = QApplication(sys.argv)
    w = LauncherWindow()
    w._apply_hotkey("Ctrl+Alt+Q")
    w._apply_autostart(False)
    print("SELFTEST_OK")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
        return
    ensure_dirs()
    
    app = QApplication(sys.argv)
    
    # 全局设置应用图标，这会影响标题栏及任务栏图标
    icon_path = get_resource_path("app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    app.setQuitOnLastWindowClosed(False)  # 托盘程序必须设为 False

    # 1. 单实例检测
    lock_path = os.path.join(DATA_DIR, "app.lock")
    lock = QLockFile(lock_path)
    if not lock.tryLock(100):
        # 尝试通过窗口标题找到已存在的进程并唤醒
        hwnd = ctypes.windll.user32.FindWindowW(None, f"angel Start v{APP_VERSION}")
        if hwnd:
            # 尝试多种方式唤醒隐藏窗口
            ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
            ctypes.windll.user32.ShowWindow(hwnd, 5) # SW_SHOW
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        else:
            QMessageBox.warning(None, "程序已在运行", "QuickLauncher 已经在后台运行，请检查托盘。")
        sys.exit(0)

    # 保持 lock 对象存活
    app._instance_lock = lock

    w = LauncherWindow()
    # 移除强制 resize，允许 LauncherWindow 在 __init__ 中恢复保存的尺寸
    # w.resize(800, 500) 
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()