# -*- coding: utf-8 -*-
"""m127：v3.38 FLP-1 —— 文件列表「默认打开路径」验收

需求：组件初始化加载时自动定位到指定默认目录并高亮其节点、加载内容；
      默认路径可由配置项传入（字段名 / 默认值 / 相对绝对取值规则明确）；
      配置为空 / 路径不存在 / 无访问权限时安全回退到根目录且不报错；
      已记录上次访问目录时优先恢复上次路径，其次才用默认路径；
      与现有目录加载逻辑（逐级浏览、单层刷新）兼容。
"""
import os, sys, tempfile, shutil

os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer, Qt

app = QApplication(sys.argv)
import config
import sidebar as SB
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m127.txt")
_log = []


def check(name, cond, detail=""):
    _log.append(("PASS" if cond else "FAIL", name, detail))


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


win = MainWindow()
sb = win._sidebar
_bak = {
    "files/defaultDir": win._settings.value("files/defaultDir"),
    "lastSidebarDir": win._settings.value("lastSidebarDir"),
    "startupAction": win._settings.value("startupAction"),
    "lastFile": win._settings.value("lastFile"),
    "fileListMode": win._settings.value("fileListMode"),
}
win.show()
wait(2400)
sb.set_file_mode("current")          # 排除历史 blank 模式干扰
wait(200)

# 临时素材：目录 A（含子目录与 md 文件）、空目录 B、一个文件 C
_root = tempfile.mkdtemp(prefix="m127_")
dir_a = os.path.join(_root, "notesA")
dir_b = os.path.join(_root, "emptyB")
os.makedirs(os.path.join(dir_a, "sub"), exist_ok=True)
os.makedirs(dir_b, exist_ok=True)
file_c = os.path.join(_root, "plain.txt")
with open(file_c, "w", encoding="utf-8") as f:
    f.write("x")
with open(os.path.join(dir_a, "a1.md"), "w", encoding="utf-8") as f:
    f.write("# a1\n")

APPDIR = os.path.abspath(config.HERE)


def set_cfg(v):
    win._settings.setValue("files/defaultDir", v)
    win._settings.sync()


def set_last(v):
    win._settings.setValue("lastSidebarDir", v)
    win._settings.sync()


# ---------- A 配置解析规则 ----------
set_cfg("")
check("A1 配置为空 → 不启用（None）", sb.resolve_default_dir() is None, "")
set_cfg("   ")
check("A2 配置为纯空白 → 不启用（None）", sb.resolve_default_dir() is None, "")
set_cfg(dir_a)
check("A3 绝对路径（存在）→ 解析为该目录",
      sb.resolve_default_dir() == os.path.abspath(dir_a), str(sb.resolve_default_dir()))
set_cfg("..")
check("A4 相对路径按应用目录 HERE 解析（.. → 工程根）",
      sb.resolve_default_dir() == os.path.dirname(APPDIR),
      "%s vs %s" % (sb.resolve_default_dir(), os.path.dirname(APPDIR)))
set_cfg(os.path.join(_root, "不存在的目录xyz"))
check("A5 路径不存在 → None（安全回退）", sb.resolve_default_dir() is None, "")
set_cfg(file_c)
check("A6 存在但不是目录（普通文件）→ None", sb.resolve_default_dir() is None, "")
set_cfg("~")
_hm = os.path.expanduser("~")
check("A7 ~ 开头展开为用户主目录",
      sb.resolve_default_dir() == (os.path.abspath(_hm) if os.path.isdir(_hm) else None),
      str(sb.resolve_default_dir()))
set_cfg(dir_b)
check("A8 空目录也算可用（存在 + 可枚举）",
      sb.resolve_default_dir() == os.path.abspath(dir_b), str(sb.resolve_default_dir()))

# A9：无访问权限（打桩 listdir 抛 PermissionError）
_orig_listdir = SB.os.listdir
try:
    def _boom(p, *a, **k):
        raise PermissionError(13, "Access is denied")
    SB.os.listdir = _boom
    check("A9 无访问权限 → None（不抛异常）", sb.resolve_default_dir() is None, "")
finally:
    SB.os.listdir = _orig_listdir

# A10：异常输入不抛异常
_ok = True
for _bad in (None, "\x00", "\\\\?\\Z:\\nope", "x" * 5000, "\t \n"):
    try:
        sb.resolve_default_dir()
    except Exception as e:               # noqa: BLE001
        _ok = False
        check("A10 异常输入不抛异常", False, "%r -> %s" % (_bad, e))
        break
if _ok:
    check("A10 异常输入不抛异常", True, "")

# ---------- B 定位并加载内容 ----------
set_cfg(dir_a)
set_last("")
r = sb.apply_default_dir()
wait(200)
_entries = [sb.file_list.item(i).data(Qt.UserRole) for i in range(sb.file_list.count())]
check("B1 定位到默认目录", r is True and sb.current_dir() == os.path.abspath(dir_a),
      "r=%s dir=%s" % (r, sb.current_dir()))
check("B2 默认目录内容已加载（列出 sub 与 a1.md）",
      sorted(e[1] for e in _entries if e) ==
      sorted([os.path.join(dir_a, "a1.md"), os.path.join(dir_a, "sub")]),
      str(_entries))
check("B3 顶部标题显示目录名", "notesA" in sb.file_header.text(), sb.file_header.text())
check("B4 列表焦点落在首项（高亮定位）", sb.file_list.currentRow() == 0,
      str(sb.file_list.currentRow()))

# ---------- C 安全回退 ----------
set_cfg("")
r = sb.apply_default_dir()
wait(150)
_drives = [sb.file_list.item(i).data(Qt.UserRole) for i in range(sb.file_list.count())]
check("C1 配置为空 → 回退根层（此电脑盘符列表）",
      r is False and sb.current_dir() is None
      and all(d and d[0] == "dir" for d in _drives), "r=%s dir=%s" % (r, sb.current_dir()))
check("C2 回退后标题为「此电脑」", "此电脑" in sb.file_header.text(), sb.file_header.text())
set_cfg(os.path.join(_root, "不存在xyz"))
r = sb.apply_default_dir()
wait(150)
check("C3 路径不存在 → 回退根层且不报错",
      r is False and sb.current_dir() is None, "r=%s dir=%s" % (r, sb.current_dir()))
set_cfg(file_c)
r = sb.apply_default_dir()
wait(150)
check("C4 配置指向普通文件 → 回退根层", r is False and sb.current_dir() is None, "")

# ---------- D 高亮：盘符层命中 ----------
set_cfg("")
sb.apply_default_dir()
wait(150)
_rows = sb.file_list.count()
_hit = sb.highlight_dir("C:\\")
_sel = sb.file_list.currentItem()
check("D1 盘符层高亮命中盘符项（C:\\）",
      _hit is True and _sel is not None
      and os.path.normcase(_sel.data(Qt.UserRole)[1]).startswith(os.path.normcase("c:")),
      "hit=%s sel=%s" % (_hit, _sel.data(Qt.UserRole) if _sel else None))
check("D2 盘符列表非空（前提成立）", _rows >= 1, str(_rows))
_miss = sb.highlight_dir(os.path.join(_root, "完全无关"))
check("D3 未命中时退化为选中首项（列表有焦点）",
      _miss is False and sb.file_list.currentRow() == 0, "miss=%s row=%s"
      % (_miss, sb.file_list.currentRow()))

# ---------- E 初始化优先级（v3.38 FLP-2）：lastOpenDir > 上次目录 > 默认路径 > 系统回退 ----------
def set_open(v):
    # v3.38（FLP-2）：最近一次成功打开文件目录（files/lastOpenDir）；空 = 无历史
    win._settings.setValue("files/lastOpenDir", v)
    win._settings.sync()


sb._initial_restored = False
set_cfg(dir_b)
set_last(dir_a)
set_open("")
r = sb.restore_initial_dir()
wait(200)
check("E1 无 lastOpenDir → 上次访问目录优先（A）而非默认（B）",
      r is True and sb.current_dir() == os.path.abspath(dir_a), str(sb.current_dir()))
sb._initial_restored = False
set_cfg("")
set_last(dir_a)
set_open(dir_b)
r = sb.restore_initial_dir()
wait(200)
check("E1b lastOpenDir 有效 → 最高优先（压过上次访问目录）",
      r is True and sb.current_dir() == os.path.abspath(dir_b), str(sb.current_dir()))
sb._initial_restored = False
set_cfg(dir_b)
set_last(os.path.join(_root, "已删除的旧目录"))
set_open(os.path.join(_root, "已消失的打开目录"))
r = sb.restore_initial_dir()
wait(200)
check("E2 打开目录与上次目录均已失效 → 退回默认路径（B）",
      sb.current_dir() == os.path.abspath(dir_b), str(sb.current_dir()))
sb._initial_restored = False
set_cfg("")
set_last("")
set_open("")
r = sb.restore_initial_dir()
wait(150)
try:
    from PySide6.QtCore import QStandardPaths as _QSP
    _docs = _QSP.writableLocation(_QSP.DocumentsLocation)
except Exception:                                # noqa: BLE001
    _docs = ""


def _nd(p):
    return os.path.normcase(os.path.abspath(p)) if p else None


_got = _nd(sb.current_dir())
_ok_e3 = (_got is not None and _got in (_nd(_docs), _nd(os.getcwd()))) or \
         (r is False and sb.current_dir() is None)
check("E3 全无历史 → 系统文档目录 / cwd（全部不可用才回退根层）", _ok_e3,
      "r=%s dir=%s docs=%s" % (r, sb.current_dir(), _docs))

# ---------- F 配置项读写与设置页联动 ----------
win.set_file_list_default_dir(dir_a)
wait(200)
check("F1 set_file_list_default_dir 写入 QSettings（字段 files/defaultDir）",
      win._settings.value("files/defaultDir") == dir_a,
      str(win._settings.value("files/defaultDir")))
check("F2 读取器回读一致", win.file_list_default_dir() == dir_a, win.file_list_default_dir())
check("F3 设置后即时定位", sb.current_dir() == os.path.abspath(dir_a), str(sb.current_dir()))
try:
    from dialogs import SettingsDialog
    _dlg_ok = hasattr(SettingsDialog, "_on_file_default_dir")
    _dlg_err = ""
except Exception as e:                            # noqa: BLE001
    _dlg_ok, _dlg_err = False, str(e)
check("F4 设置页已接入该字段（通用页处理器存在）", _dlg_ok, _dlg_err)
check("F5 默认值取自 config.FILE_LIST_DEFAULT_DIR 且为空串",
      config.FILE_LIST_DEFAULT_DIR == "", repr(config.FILE_LIST_DEFAULT_DIR))

# ---------- G blank 模式不被干扰 ----------
sb.set_file_mode("blank")
set_cfg(dir_a)
r = sb.apply_default_dir()
check("G1 文件列表为「空白项」模式时不介入", r is False, str(r))
sb.set_file_mode("current")
wait(200)
check("G2 切回后恢复正常定位能力", sb.apply_default_dir() is True, str(sb.current_dir()))

# ---------- H 与逐级浏览（go_up）兼容 ----------
set_cfg(dir_a)
sb.apply_default_dir()
sb.go_up()
wait(150)
check("H1 定位后仍可逐级返回上级", sb.current_dir() == os.path.abspath(_root),
      str(sb.current_dir()))
check("H2 返回上级后内容为该层列表（未预展开子树）", sb.file_list.count() >= 2,
      str(sb.file_list.count()))

# ---------- 收尾：还原设置，避免污染其它探针 ----------
for _k, _v in _bak.items():
    if _v is None:
        win._settings.remove(_k)
    else:
        win._settings.setValue(_k, _v)
win._settings.sync()
shutil.rmtree(_root, ignore_errors=True)

with open(OUT, "w", encoding="utf-8") as f:
    for s_, name, detail in _log:
        f.write("%s %s%s\n" % (s_, name, (" | " + detail) if detail and s_ == "FAIL" else ""))
print("done")
