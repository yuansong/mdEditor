# -*- coding: utf-8 -*-
"""统一风格的线性图标（QPainter 矢量绘制）。

所有图标使用同一套规范：
- 24x24 视窗，逻辑尺寸 20px
- 线宽 1.8、圆头圆角连接
- 描边色 #4b5563（与 QToolButton 文字色一致）
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_STROKE = QColor("#4b5563")
_VIEW = 24.0


def _painter(size: int) -> tuple:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(_STROKE)
    # 统一线宽：按视窗等比缩放（size=20 时线宽 1.8）
    pen.setWidthF(1.8 * size / 20)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.scale(size / _VIEW, size / _VIEW)
    return pm, p


def _path(coords, close=False):
    """把折线坐标列表转成 QPainterPath。coords: [(x, y), ...]"""
    pa = QPainterPath()
    pa.moveTo(QPointF(*coords[0]))
    for pt in coords[1:]:
        pa.lineTo(QPointF(*pt))
    if close:
        pa.closeSubpath()
    return pa


def icon_new(size: int = 20) -> QIcon:
    """新建：纸张 + 左下角加号。"""
    pm, p = _painter(size)
    p.drawPath(_path([(6, 3), (14.5, 3), (18.5, 7), (18.5, 21), (6, 21)], True))
    p.drawPath(_path([(14.5, 3), (14.5, 7), (18.5, 7)]))
    p.drawPath(_path([(9, 13.5), (15, 13.5)]))
    p.drawPath(_path([(12, 10.5), (12, 16.5)]))
    p.end()
    return QIcon(pm)


def icon_open(size: int = 20) -> QIcon:
    """打开：文件夹。"""
    pm, p = _painter(size)
    p.drawPath(_path([(3, 19.5), (3, 5.5), (9, 5.5), (11, 8), (19, 8), (19, 10.5)]))
    p.drawPath(_path([(3, 19.5), (5.5, 10.5), (21.5, 10.5), (19, 19.5), (3, 19.5)]))
    p.end()
    return QIcon(pm)


def icon_save(size: int = 20) -> QIcon:
    """保存：软盘。"""
    pm, p = _painter(size)
    p.drawPath(_path([(4, 4), (16.5, 4), (20, 7.5), (20, 20), (4, 20)], True))
    p.drawPath(_path([(8, 4), (8, 9), (16, 9), (16, 4)]))
    p.drawRect(QRectF(8, 13.5, 8, 6.5))
    p.end()
    return QIcon(pm)


def icon_find(size: int = 20) -> QIcon:
    """查找：放大镜。"""
    pm, p = _painter(size)
    p.drawEllipse(QRectF(4.5, 4.5, 11, 11))
    p.drawPath(_path([(14.2, 14.2), (20, 20)]))
    p.end()
    return QIcon(pm)


def icon_search_all(size: int = 20) -> QIcon:
    """全局搜索（跨文件）：放大镜 + 结果列表线，区别于仅文档内的「查找」。"""
    pm, p = _painter(size)
    p.drawEllipse(QRectF(3.5, 3.5, 10.5, 10.5))
    p.drawPath(_path([(11.6, 11.6), (15.8, 15.8)]))
    p.drawPath(_path([(14.8, 16.6), (20.4, 16.6)]))
    p.drawPath(_path([(14.8, 20.2), (18.6, 20.2)]))
    p.end()
    return QIcon(pm)


def icon_write(size: int = 20) -> QIcon:
    """写作模式：铅笔。"""
    pm, p = _painter(size)
    p.drawPath(_path([(4, 20), (6.2, 14.8), (16.2, 4.8), (19.2, 7.8), (9.2, 17.8), (4, 20)]))
    p.drawPath(_path([(13.9, 7.1), (16.9, 10.1)]))
    p.drawPath(_path([(4, 20), (8, 18.4)]))
    p.end()
    return QIcon(pm)


def icon_code(size: int = 20) -> QIcon:
    """源码模式：尖括号。"""
    pm, p = _painter(size)
    p.drawPath(_path([(8.5, 7), (3.5, 12), (8.5, 17)]))
    p.drawPath(_path([(15.5, 7), (20.5, 12), (15.5, 17)]))
    p.drawPath(_path([(13.5, 5), (10.5, 19)]))
    p.end()
    return QIcon(pm)


def icon_split(size: int = 20) -> QIcon:
    """分屏模式：矩形 + 中缝 + 左右两点。"""
    pm, p = _painter(size)
    p.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
    p.drawPath(_path([(12, 5), (12, 19)]))
    p.drawPath(_path([(6, 12), (9, 12)]))
    p.drawPath(_path([(15, 12), (18, 12)]))
    p.end()
    return QIcon(pm)


def icon_undo(size: int = 20) -> QIcon:
    """撤销：左弯箭头。"""
    pm, p = _painter(size)
    p.drawPath(_path([(7, 6), (3.5, 9.5), (7, 13)]))
    p.drawPath(_path([(3.5, 9.5), (13, 9.5), (13, 9.5)]))
    p.drawPath(_path([(13, 9.5), (16.5, 11.5), (17.5, 14.5), (16, 17.5), (13, 19)]))
    p.end()
    return QIcon(pm)


def icon_redo(size: int = 20) -> QIcon:
    """重做：右弯箭头（撤销的镜像）。"""
    pm, p = _painter(size)
    p.drawPath(_path([(17, 6), (20.5, 9.5), (17, 13)]))
    p.drawPath(_path([(20.5, 9.5), (11, 9.5), (11, 9.5)]))
    p.drawPath(_path([(11, 9.5), (7.5, 11.5), (6.5, 14.5), (8, 17.5), (11, 19)]))
    p.end()
    return QIcon(pm)


def icon_settings(size: int = 20) -> QIcon:
    """设置：齿轮（外圈齿 + 中心圆）。"""
    import math
    pm, p = _painter(size)
    cx, cy, r_out, r_in = 12.0, 12.0, 8.2, 5.6
    teeth = 8
    outer = []
    for k in range(teeth * 2):
        ang = math.pi * k / teeth - math.pi / 2
        r = r_out if k % 2 == 0 else r_in
        outer.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    p.drawPath(_path(outer, True))
    p.drawEllipse(QPointF(cx, cy), 2.6, 2.6)
    p.end()
    return QIcon(pm)


def icon_history(size: int = 20) -> QIcon:
    """历史版本：时钟（圆盘 + 分针时针）——R7 UI-SPEC 左工具栏「历史版本」钮。"""
    pm, p = _painter(size)
    p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
    p.drawPath(_path([(12, 7.5), (12, 12), (15.5, 14)]))
    p.end()
    return QIcon(pm)


def icon_sidepanel(size: int = 20, collapsed: bool = False) -> QIcon:
    """侧栏面板（R3.5：统一为线性面板图标，替代「«/»」文本钮）。

    collapsed=False：左列着色（面板展开态）；collapsed=True：左列仅描边（收起态）。
    """
    pm, p = _painter(size)
    p.drawRoundedRect(QRectF(3.5, 5, 17, 14), 2, 2)
    p.drawPath(_path([(9.5, 5), (9.5, 19)]))
    if not collapsed:
        p.setBrush(QColor(_STROKE))
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(4.6, 6.1, 3.8, 11.8))
        p.setPen(QPen(_STROKE))
    p.end()
    return QIcon(pm)


def icon_toolbar_expand(size: int = 16) -> QIcon:
    """工具条展开钮（左缘常驻，工具条隐藏时显形）：双右指箭头（»）线性矢量，
    替代旧式文字「»」钮，与整体线性图标风格（_painter 线宽/圆头/描边色）一致。
    点击展开被隐藏的左侧工具条。"""
    pm, p = _painter(size)
    p.drawPath(_path([(8.0, 7.0), (14.0, 12.0), (8.0, 17.0)]))
    p.drawPath(_path([(13.0, 7.0), (19.0, 12.0), (13.0, 17.0)]))
    p.end()
    return QIcon(pm)


def _fill_painter(size: int) -> tuple:
    """生成透明底 Pixmap + 已缩放画笔（用于主题色填充图标，无描边）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / _VIEW, size / _VIEW)
    return pm, p


def icon_folder(color: str = "#0052d9", size: int = 16) -> QIcon:
    """文件列表文件夹：主题强调色填充（对齐设计01 .ficon 语义，随主题变色）。

    - 24 视窗内绘制单路径文件夹轮廓（含顶部标签凸起），纯填充；
    - color 默认取浅色主题 accent，运行时由 sidebar.set_folder_theme 按主题重填。
    """
    pm, p = _fill_painter(size)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawPath(_path([
        (2.4, 5.4), (9.0, 5.4), (11.1, 7.65), (20.9, 7.65),
        (20.9, 18.0), (2.4, 18.0),
    ], close=True))
    p.end()
    return QIcon(pm)


def icon_file(color: str = "#6b7280", size: int = 16) -> QIcon:
    """文件列表文件项（md / 其他）：中性灰描边文档图标，与文件夹主题色区分。

    仅描边、不填充，视觉上比文件夹图标更「轻」，避免与强调色文件夹争夺注意力。
    """
    pm, p = _painter(size)
    p.setPen(QPen(QColor(color)))
    p.drawPath(_path([(6, 3), (13, 3), (18, 8), (18, 21), (6, 21)], True))
    p.drawPath(_path([(13, 3), (13, 8), (18, 8)]))
    p.end()
    return QIcon(pm)


def icon_up(size: int = 16) -> QIcon:
    """面包屑「返回上一级目录」：上箭头（替代可能缺字形的 ↑ 文本）。"""
    pm, p = _painter(size)
    p.drawPath(_path([(12, 16), (12, 9)]))
    p.drawPath(_path([(8, 12.5), (12, 9), (16, 12.5)]))
    p.end()
    return QIcon(pm)


# 便捷映射：config.MODES 中的图标名 -> 绘制函数
MODE_ICONS = {
    "write": icon_write,
    "code": icon_code,
    "split": icon_split,
}
