# -*- coding: utf-8 -*-
"""
theme.py —— 快捷启动器「样式 / 结构分离」主题模块

本模块只负责视觉：颜色、QSS 样式表、线性 SVG 图标、图标渲染。
逻辑结构（quicklauncher.py 中的窗口 / 列表 / 信号槽）保持不变。

极简扁平化设计：
- 浅色：纯白背景、深灰文字、清新蓝主色 #2563eb
- 深色：#111827 背景、亮白文字、蓝色主色 #3b82f6
- 全局圆角、卡片 hover 提升 2px + 柔和阴影
"""

# ---------------------------------------------------------------------------
# 1. 颜色定义（CSS / 结构分离的核心数据）
# ---------------------------------------------------------------------------
LIGHT = {
    "bg": "#ffffff",              # 主窗口背景（--bg-body）
    "bg_alt": "#ffffff",          # 次级背景（顶栏 / 工具栏 / 状态栏）
    "surface": "#ffffff",         # 卡片表面（--bg-card）
    "nav_bg": "#ffffff",          # 左侧导航背景（--bg-nav）
    "text": "#4a4a4a",            # 主文字（--text-primary）
    "text_secondary": "#7a7a7a",  # 次要文字（--text-secondary）
    "text_muted": "#b0b0b0",      # 弱化文字（--text-muted）
    "border": "rgba(187, 222, 214, 0.6)",  # 边框（--border 透明度）
    "primary": "#61c0bf",         # 主色（薄荷绿 --primary）
    "primary_hover": "#4fb0af",
    "primary_pressed": "#3f9a99",
    "accent": "#ffb6b9",          # 强调色（--accent）
    "selected": "rgba(97, 192, 191, 0.20)",  # 选中态底色
    "hover": "#eaf4f3",           # 悬停态底色
    "card_bg": "#ffffff",         # 图标卡片底色
    "scroll": "#61c0bf",          # 滚动条
    "shadow": "rgba(97, 192, 191, 0.20)",    # 阴影（--shadow）
}

DARK = {
    "bg": "#303841",              # 主窗口背景（--bg-body）
    "bg_alt": "#3a4550",          # 次级背景（--bg-card）
    "surface": "#3a4550",
    "nav_bg": "#262e36",          # 左侧导航背景（--bg-nav）
    "text": "#eeeeee",            # 主文字（--text-primary）
    "text_secondary": "#b0b0b0",  # 次要文字（--text-secondary）
    "text_muted": "#7a7a7a",      # 弱化文字（--text-muted）
    "border": "rgba(0, 173, 181, 0.35)",      # 边框（--border 透明度）
    "primary": "#00adb5",         # 主色（深薄荷绿 --primary）
    "primary_hover": "#1ec2ca",
    "primary_pressed": "#00939a",
    "accent": "#ff5722",          # 强调色（--accent）
    "selected": "rgba(0, 173, 181, 0.25)",    # 选中态底色
    "hover": "#3a4550",           # 悬停态底色
    "card_bg": "#3a4550",         # 图标卡片底色
    "scroll": "#00adb5",          # 滚动条
    "shadow": "rgba(0, 0, 0, 0.5)",           # 阴影（--shadow）
}

THEMES = {"light": LIGHT, "dark": DARK}

# 当前激活主题（供 AppCardDelegate 等模块级读取，切换主题时更新）
ACTIVE = dict(LIGHT)


def set_active(name: str) -> None:
    """切换当前激活主题色板（模块级全局，供委托等组件读取）。"""
    global ACTIVE
    ACTIVE = dict(THEMES.get(name, LIGHT))


def colors(name: str = None) -> dict:
    if name is None:
        return ACTIVE
    return THEMES.get(name, LIGHT)


# ---------------------------------------------------------------------------
# 2. 线性 SVG 图标（现代风格，stroke=currentColor，可被 render_icon 着色）
# ---------------------------------------------------------------------------
ICONS = {
    # 打开目录
    "open_dir": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
    # 添加分组
    "add_group": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>',
    # 编辑分组
    "edit_group": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>',
    # 分组排序
    "sort_group": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="8 9 12 5 16 9"/><polyline points="8 15 12 19 16 15"/></svg>',
    # 删除分组
    "delete_group": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>',
    # 清空 URL 缓存
    "clear_cache": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.8-3.4L23 10M1 14l4.7 4.4A9 9 0 0 0 20.5 15"/></svg>',
    # 设置
    "settings": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 0 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H1a2 2 0 0 1 0-4h.1A1.7 1.7 0 0 0 2.6 7a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H7a1.7 1.7 0 0 0 1-1.5V1a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V7a1.7 1.7 0 0 0 1.5 1H23a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
    # 退出
    "quit": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.4 6.6a9 9 0 1 1-12.8 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>',
    # 主题切换（演示用）
    "theme": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.2" y1="4.2" x2="5.6" y2="5.6"/><line x1="18.4" y1="18.4" x2="19.8" y2="19.8"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.2" y1="19.8" x2="5.6" y2="18.4"/><line x1="18.4" y1="5.6" x2="19.8" y2="4.2"/></svg>',
    # 启动日志（侧栏置顶）
    "log": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><path d="M12 7v5l4 2"/></svg>',
    # 分组文件夹
    "folder": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
    # 折叠
    "collapse": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/><line x1="3" y1="3" x2="3" y2="21"/></svg>',
    # 搜索
    "search": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>',
    # 帮助
    "help": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12" y2="17"/></svg>',
}


def render_icon(key: str, color: str, size: int = 20) -> "object":
    """把线性 SVG 图标渲染为 QIcon（按主题色着色）。

    Args:
        key: ICONS 中的图标名
        color: 着色颜色（如 "#374151"）
        size: 像素尺寸
    Returns:
        QIcon；若模块不可用或图标缺失则返回空 QIcon
    """
    svg = ICONS.get(key)
    if not svg:
        from PySide6.QtGui import QIcon
        return QIcon()
    svg = svg.replace("currentColor", color)
    try:
        from PySide6.QtGui import QIcon, QPixmap, QPainter
        from PySide6.QtCore import Qt, QSize
        from PySide6.QtSvg import QSvgRenderer

        renderer = QSvgRenderer(svg.encode("utf-8"))
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter)
        painter.end()
        return QIcon(pm)
    except Exception:
        from PySide6.QtGui import QIcon
        return QIcon()


# ---------------------------------------------------------------------------
# 3. SpinBox 箭头（保持原有文件写入逻辑，但集中到本模块）
# ---------------------------------------------------------------------------
def spin_arrow_css(arrow_dir: str, text_color: str):
    """生成 SpinBox 上下箭头 SVG 文件，返回 (up_url, down_url) 供 QSS 使用。"""
    import os
    os.makedirs(arrow_dir, exist_ok=True)
    up_svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" '
              'viewBox="0 0 10 6"><polygon points="5,0 10,6 0,6" fill="%s"/></svg>' % text_color)
    down_svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" '
                'viewBox="0 0 10 6"><polygon points="5,6 10,0 0,0" fill="%s"/></svg>' % text_color)
    up_path = os.path.join(arrow_dir, "up.svg")
    down_path = os.path.join(arrow_dir, "down.svg")
    with open(up_path, "w", encoding="utf-8") as f:
        f.write(up_svg)
    with open(down_path, "w", encoding="utf-8") as f:
        f.write(down_svg)
    return up_path.replace("\\", "/"), down_path.replace("\\", "/")


# ---------------------------------------------------------------------------
# 4. 样式表生成（结构无关，纯 QSS）
# ---------------------------------------------------------------------------
def build_stylesheet(c: dict, up_url: str = "", down_url: str = "", name: str = None) -> str:
    """根据颜色字典生成完整的 QSS 样式表字符串。"""
    # 仅浅色模式：中间内容区（卡片列表 QListWidget）背景固定为 #a6e3e9
    content_bg = "#a6e3e9" if name == "light" else c["bg"]
    return f"""
    /* ===== 主窗口：标准 Windows 直角边框（实心背景，无圆角） ===== */
    LauncherWindow {{
        background: {c['bg']};
        border: none;
    }}
    #LauncherCentral {{
        background: {c['bg']};
    }}
    LauncherWindow QWidget {{
        color: {c['text']};
        font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    }}

    /* ===== Tab 页签：圆角卡片风格 ===== */
    QTabWidget::pane {{
        background-color: {c['bg']};
        border: 1px solid {c['border']};
        border-radius: 0px;
    }}
    QTabBar::tab {{
        background-color: {c['bg_alt']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-bottom: none;
        padding: 8px 16px;
        margin-right: 4px;
        border-radius: 0px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
    }}
    QTabBar::tab:selected {{
        background-color: {c['bg']};
        border: 1px solid {c['border']};
        border-bottom: 3px solid {c['primary']};
    }}
    QTabBar::tab:hover {{
        background-color: {c['hover']};
    }}

    /* ===== 通用输入框：圆角 ===== */
    QLineEdit {{
        background-color: {c['bg']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 0px;
        padding: 6px 10px;
    }}
    QLineEdit:focus {{
        border: 1px solid {c['primary']};
        background-color: {c['bg']};
    }}
    QLineEdit:hover {{
        border-color: {c['text_secondary']};
    }}

    /* ===== 底部搜索框：白底 + 主色绿聚焦 ===== */
    #SearchInput {{
        background-color: #ffffff;
        color: #4a4a4a;
        border: 1px solid {c['border']};
        border-radius: 0px;
        padding: 8px 14px;
    }}
    #SearchInput:focus {{
        border: 1.5px solid {c['primary']};
    }}

    /* ===== 顶栏（品牌 + 主题键 + 工具栏按钮） ===== */
    #TopBar {{
        background-color: {c['bg_alt']};
        border: none;
        border-bottom: 1px solid {c['border']};
        spacing: 6px;
        padding: 4px 8px;
    }}
    #TopBar QToolButton {{
        background-color: transparent;
        color: {c['text']};
        border: none;
        border-radius: 0px;
        padding: 5px 10px;
    }}
    #TopBar QToolButton:hover {{
        background-color: {c['primary']};
        color: #ffffff;
    }}
    #TopBar QToolButton:pressed {{
        background-color: {c['primary_pressed']};
    }}

    /* ===== 左侧导航 ===== */
    #Sidebar {{
        background-color: {c['nav_bg']};
        border: none;
        border-right: 1px solid {c['border']};
    }}
    #NavTitle {{
        color: {c['text_muted']};
        font-size: 12px;
        padding: 4px 12px;
    }}
    #NavItem {{
        color: {c['text_secondary']};
        background-color: transparent;
        border: none;
        border-left: 3px solid transparent;
        border-radius: 0px;
        padding: 8px 10px;
    }}
    #NavItem:hover {{
        background-color: {c['hover']};
        color: {c['text']};
    }}
    #NavItemActive {{
        background-color: {c['primary']};
        color: #ffffff;
        border-left: 3px solid transparent;
    }}
    #NavItemActive:hover {{
        background-color: {c['primary_hover']};
    }}
    #NavCollapse {{
        color: {c['text_secondary']};
        background-color: transparent;
        border: none;
        border-radius: 0px;
        padding: 4px;
    }}
    #NavCollapse:hover {{
        background-color: {c['hover']};
        color: {c['primary']};
    }}

    /* ===== 底状态栏 ===== */
    #StatusBar {{
        background-color: {c['bg_alt']};
        border: none;
        border-top: 1px solid {c['border']};
        color: {c['text_muted']};
        font-size: 12px;
    }}
    #StatusBar QLabel {{
        color: {c['text_muted']};
        font-size: 12px;
    }}
    #HelpBtn {{
        color: {c['text_muted']};
        background-color: transparent;
        border: none;
        border-radius: 0px;
        padding: 4px 8px;
    }}
    #HelpBtn:hover {{
        color: {c['primary']};
        background-color: {c['hover']};
    }}

    /* ===== 工具栏：扁平圆角 + 线性图标按钮 ===== */
    QToolBar {{
        background-color: {c['bg_alt']};
        border: none;
        border-radius: 0px;
        spacing: 6px;
        padding: 6px;
    }}
    QToolButton {{
        background-color: transparent;
        color: {c['text']};
        border: none;
        border-radius: 0px;
        padding: 6px 10px;
    }}
    QToolButton:hover {{
        background-color: {c['primary']};
        color: #ffffff;
    }}
    QToolButton:pressed {{
        background-color: {c['primary_pressed']};
    }}

    /* ===== 菜单 ===== */
    QMenu {{
        background-color: {c['bg_alt']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 0px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 20px;
        border-radius: 0px;
    }}
    QMenu::item:selected {{
        background-color: {c['primary']};
        color: #ffffff;
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {c['border']};
        margin: 4px 8px;
    }}

    /* ===== 下拉框 / 微调框 ===== */
    QComboBox {{
        background-color: {c['bg']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 0px;
        padding: 6px 10px;
    }}
    QComboBox:focus, QComboBox:hover {{
        border-color: {c['primary']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 18px;
    }}
    QSpinBox {{
        background-color: {c['bg']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 0px;
        padding: 4px 26px 4px 10px;
        min-height: 20px;
    }}
    QSpinBox:focus {{
        border-color: {c['primary']};
    }}
    QSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: right top;
        width: 22px;
        border: none;
        border-left: 1px solid {c['border']};
        background-color: {c['bg_alt']};
        border-top-right-radius: 0px;
    }}
    QSpinBox::up-button:hover {{ background-color: {c['hover']}; }}
    QSpinBox::up-arrow {{ image: url({up_url}); width: 10px; height: 6px; }}
    QSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: right bottom;
        width: 22px;
        border: none;
        border-left: 1px solid {c['border']};
        background-color: {c['bg_alt']};
        border-bottom-right-radius: 0px;
    }}
    QSpinBox::down-button:hover {{ background-color: {c['hover']}; }}
    QSpinBox::down-arrow {{ image: url({down_url}); width: 10px; height: 6px; }}

    /* ===== 列表（图标卡片区） ===== */
    QListWidget {{
        background-color: transparent;
        border: 1px solid {c['border']};
        border-radius: 0px;
        outline: none;
    }}
    /* 选中态背景交由 AppCardDelegate 全权绘制（薄荷绿），避免 Qt 默认选中黑底/黑图标 */
    QListWidget::item {{ background: transparent; }}
    QListWidget::item:selected {{ background: transparent; }}
    QListWidget::item:selected:active {{ background: transparent; }}
    QListWidget::item:selected:!active {{ background: transparent; }}
    QListWidget::item:hover {{ background: transparent; }}
    QListWidget::item:focus {{ background: transparent; }}
    QListWidget::item:focus:selected {{ background: transparent; }}
    QListWidget::item:pressed {{ background: transparent; }}
    QListWidget:focus {{ border-color: {c['primary']}; }}

    /* ===== 启动日志表格 ===== */
    QTableWidget {{
        background-color: {c['bg']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 0px;
        gridline-color: {c['border']};
    }}
    QHeaderView::section {{
        background-color: {c['bg_alt']};
        color: {c['text']};
        border: none;
        border-bottom: 1px solid {c['border']};
        padding: 6px;
    }}
    QTableWidget::item:selected {{
        background-color: {c['selected']};
        color: {c['text']};
    }}

    /* ===== 滚动条 ===== */
    QScrollBar:vertical {{
        background-color: transparent;
        width: 8px;
        margin: 2px 0;
        border: none;
        border-radius: 0px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {c['scroll']};
        min-height: 30px;
        border-radius: 0px;
    }}
    QScrollBar::handle:vertical:hover {{ background-color: {c['text_secondary']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px; border: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QScrollBar:horizontal {{
        background-color: transparent;
        height: 8px;
        margin: 0 2px;
        border: none;
        border-radius: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {c['scroll']};
        min-width: 30px;
        border-radius: 0px;
    }}
    QScrollBar::handle:horizontal:hover {{ background-color: {c['text_secondary']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px; border: none;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
    """


def render_icon_states(key: str, normal_color: str, active_color: str = None, size: int = 20) -> "object":
    """线性 SVG 图标渲染为 QIcon，支持 Normal / Active 双状态着色。

    用于工具栏按钮：常态 normal_color（深灰），hover / 按下时 active_color（白色），
    由 QToolButton 自动按鼠标状态切换对应状态图标。
    """
    svg = ICONS.get(key)
    if not svg:
        from PySide6.QtGui import QIcon
        return QIcon()
    if active_color is None:
        active_color = normal_color
    try:
        from PySide6.QtGui import QIcon, QPixmap, QPainter
        from PySide6.QtCore import Qt
        from PySide6.QtSvg import QSvgRenderer

        def make(color):
            data = svg.replace("currentColor", color)
            renderer = QSvgRenderer(data.encode("utf-8"))
            pm = QPixmap(size, size)
            pm.fill(Qt.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.Antialiasing)
            renderer.render(painter)
            painter.end()
            return pm

        icon = QIcon()
        icon.addPixmap(make(normal_color), QIcon.Normal)
        icon.addPixmap(make(active_color), QIcon.Active)
        icon.addPixmap(make(active_color), QIcon.Selected)
        return icon
    except Exception:
        from PySide6.QtGui import QIcon
        return QIcon()
