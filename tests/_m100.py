# -*- coding: utf-8 -*-
"""m100: v3.35（TPL-D）「设为模板文件」探针
A 名称规则（纯函数）：空白折叠 / 控制字符 / 超长截断 / 空名拒绝 / emoji 码点截断
B 重名自动编号：普通重名 / 满名重名不陷死循环 / 连号推进
C 侧栏文件右键菜单：文件项含「设为模板…」、目录项不含
D make_template_from_file 全链路（QInputDialog 打桩）：正常创建 / 超长截断 /
  重名编号 / 空名拒绝 / 取消 / 空文件 / 超大文件 / 不存在路径
E 落盘与下发：写盘回读一致 / 同名校验在保存层兜底 / 内核菜单末尾可见（悬浮栏 📄）
结果写 _m100.txt，PASS/FAIL 逐条判定。"""
import json, os, sys, time, tempfile
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit
import mainwindow as mw_mod
import sidebar as sb_mod
from mainwindow import MainWindow, normalize_template_name, unique_template_name

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m100.txt")
LINES = []
N_PASS = [0]
N_FAIL = [0]


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    if cond: N_PASS[0] += 1
    else: N_FAIL[0] += 1
    LINES.append(tag + " | " + name + (" | " + str(extra) if extra else ""))


def js(win, code, timeout=8000):
    res = {"v": None, "done": False}
    def cb(r):
        res["v"] = r; res["done"] = True
    win._js_active(code, cb)
    t0 = time.time()
    while not res["done"] and time.time() - t0 < timeout / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)
    return res["v"]


def wait(ms):
    t0 = time.time()
    while time.time() - t0 < ms / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)


def setmd(win, md, ms=700):
    js(win, "window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def num(r):
    try:
        return str(int(float(r)))
    except (TypeError, ValueError):
        return str(r)


# ---------- 打桩：QInputDialog / QMessageBox ----------
class FakeLineEdit(QLineEdit):
    def selectAll(self):
        pass


class FakeInputDialog:
    """替身：记录 label / 初值，可指定返回值与 OK / Cancel。

    preset 非 None 时优先于产品代码写入的默认值（否则 setTextValue 会覆盖测试注入值）。
    """
    last = None

    def __init__(self, _parent=None):
        self.title = self.label = ""
        self.default = ""
        self.preset = None
        self.value = ""
        self.le = FakeLineEdit()
        self.ok = True
        FakeInputDialog.last = self

    def setWindowTitle(self, t): self.title = t
    def setLabelText(self, t): self.label = t

    def setTextValue(self, t):
        self.default = str(t or "")
        self.value = self.default if self.preset is None else self.preset

    def findChild(self, _cls): return self.le
    def textValue(self): return self.value
    def exec(self): return QDialog.Accepted if self.ok else QDialog.Rejected


class FakeMsgBox:
    """替身：记录警告/提问调用，不阻塞。"""
    warns = []
    infos = []

    @classmethod
    def warning(cls, _p, title, text, *a, **k):
        cls.warns.append((title, text)); return 0

    @classmethod
    def information(cls, _p, title, text, *a, **k):
        cls.infos.append((title, text)); return 0


class FakeMenu:
    """替身 QMenu：捕获 addAction 文本与回调，exec 不阻塞。"""
    last = None

    def __init__(self, _parent=None):
        self.items = []       # [(text, callback)]
        self.seps = 0
        FakeMenu.last = self

    def addAction(self, text, cb=None):
        self.items.append((text, cb)); return cb

    def addSeparator(self): self.seps += 1
    def isEmpty(self): return not self.items
    def exec(self, _pos): return None

    def texts(self): return [t for t, _ in self.items]

    def callback(self, text):
        for t, cb in self.items:
            if t == text: return cb
        return None


def ask_name(win, path, text=None, ok=True):
    """以指定返回值调用 make_template_from_file（QInputDialog 打桩）。

    text=None 表示不注入，交给产品代码用默认值（文件名）。
    """
    holder = {}

    def factory(parent=None):
        d = FakeInputDialog(parent)
        d.preset = text
        d.ok = ok
        holder["d"] = d
        return d

    orig = mw_mod.QInputDialog
    mw_mod.QInputDialog = factory
    try:
        win.make_template_from_file(path)
    finally:
        mw_mod.QInputDialog = orig
    return holder.get("d")


def write(p, s, encoding="utf-8"):
    with open(p, "w", encoding=encoding) as f:
        f.write(s)
    return p


def main():
    app = QApplication(sys.argv)
    tmpdir = tempfile.mkdtemp(prefix="m100_")
    tpl_file = os.path.join(tmpdir, "templates.json")
    mw_mod.TEMPLATE_FILE = tpl_file
    mw_mod.QMessageBox = FakeMsgBox
    sb_mod.QMessageBox = FakeMsgBox

    # ================= A 名称规则 =================
    check("A1 首尾空白 + 换行折叠", normalize_template_name("  周报 \n 项目版  ") == "周报 项目版",
          repr(normalize_template_name("  周报 \n 项目版  ")))
    check("A2 制表 / 零宽字符归一为单空格",
          normalize_template_name("a\tb\u200b\u200dc") == "a b c",
          repr(normalize_template_name("a\tb\u200b\u200dc")))
    check("A3 超长截断到 30 字", len(normalize_template_name("长" * 45)) == 30,
          str(len(normalize_template_name("长" * 45))))
    check("A4 恰 30 字不截断", normalize_template_name("字" * 30) == "字" * 30, "")
    check("A5 全空白 → 空串（拒绝）", normalize_template_name("  \t\n ") == "",
          repr(normalize_template_name("  \t\n ")))
    check("A6 None / 非字符串安全", normalize_template_name(None) == "" and
          normalize_template_name(123) == "123", "")
    check("A7 emoji 不切半（码点计）",
          normalize_template_name("😀" * 35) == "😀" * 30,
          str(len(normalize_template_name("😀" * 35))))

    # ================= B 重名编号 =================
    check("B1 不重名原样返回", unique_template_name("周报", ["月报"]) == "周报", "")
    check("B2 重名加 2", unique_template_name("周报", ["周报"]) == "周报 2", "")
    check("B3 连号推进", unique_template_name("周报", ["周报", "周报 2"]) == "周报 3", "")
    full = "字" * 30
    got_full = unique_template_name(full, [full])
    check("B4 满名重名不陷死循环且后缀可见",
          got_full.endswith(" 2") and len(got_full) == 30, repr(got_full))

    # ================= C 侧栏右键菜单 =================
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"): break
        wait(500)

    work = os.path.join(tmpdir, "work")
    os.makedirs(work, exist_ok=True)
    src = write(os.path.join(work, "源文档.md"), "# 源文档\n\n段落 A\n\n段落 B")
    os.makedirs(os.path.join(work, "子目录"), exist_ok=True)
    sb = win._sidebar
    sb._cur_dir = work
    sb._file_mode = "dir"
    sb._refresh_files()
    wait(400)

    orig_menu = sb_mod.QMenu
    sb_mod.QMenu = FakeMenu
    try:
        got = {}
        for row in range(sb.file_list.count()):
            it = sb.file_list.item(row)
            d = it.data(Qt.UserRole)
            if not d:
                continue
            kind, p = d
            rect = sb.file_list.visualItemRect(it)
            FakeMenu.last = None
            sb._on_file_menu(rect.center())
            m = FakeMenu.last
            got[kind] = m.texts() if m else []
        check("C1 文件项右键含「设为模板…」", "设为模板…" in got.get("file", []),
              json.dumps(got.get("file", []), ensure_ascii=False))
        check("C2 文件项原有菜单项保留（打开 / 重命名 / 删除）",
              all(x in got.get("file", []) for x in ("打开", "重命名", "删除（移入回收站）")),
              json.dumps(got.get("file", []), ensure_ascii=False))
        check("C3 目录项不含「设为模板…」", "设为模板…" not in got.get("dir", []),
              json.dumps(got.get("dir", []), ensure_ascii=False))
    finally:
        sb_mod.QMenu = orig_menu

    # ================= D 全链路 =================
    win._custom_templates = []
    d = ask_name(win, src, None)   # 不注入名称：验证默认值取文件名
    check("D1 正常创建：写入列表",
          win._custom_templates == [{"name": "源文档", "content": "# 源文档\n\n段落 A\n\n段落 B"}],
          json.dumps(win._custom_templates, ensure_ascii=False))
    check("D2 输入框硬限 30 字已设置", d is not None and d.le.maxLength() == 30,
          str(d.le.maxLength() if d else None))
    check("D3 默认值为文件名（去扩展名）", d is not None and d.default == "源文档", repr(d.default if d else None))
    check("D3b 输入框提示写明长度上限", d is not None and "30 字" in d.label, repr(d.label if d else None))
    check("D4 状态栏提示已设为模板", "已设为模板" in win._toast.text(), win._toast.text())
    check("D5 写盘 templates.json", os.path.isfile(tpl_file) and
          "源文档" in open(tpl_file, encoding="utf-8").read(), tpl_file)

    # 超长输入 → 截断存储
    ask_name(win, src, "长" * 45)
    check("D6 超长输入截断为 30 字存库",
          win._custom_templates[-1]["name"] == "长" * 30 and len(win._custom_templates[-1]["name"]) == 30,
          str(len(win._custom_templates[-1]["name"])))

    # 重名 → 自动编号
    ask_name(win, src, "源文档")
    check("D7 重名自动编号为「源文档 2」", win._custom_templates[-1]["name"] == "源文档 2",
          json.dumps([t["name"] for t in win._custom_templates], ensure_ascii=False))
    check("D8 提示中说明已编号", "已自动编号" in win._toast.text(), win._toast.text())

    # 空名 → 拒绝
    n_before = len(win._custom_templates)
    ask_name(win, src, "   ")
    check("D9 空名拒绝写入 + 状态提示",
          len(win._custom_templates) == n_before and "名称为空" in win._toast.text(),
          win._toast.text())

    # 取消 → 不写入
    ask_name(win, src, "不落地", ok=False)
    check("D10 取消不写入", len(win._custom_templates) == n_before,
          str(len(win._custom_templates)))

    # 空文件 / 超大文件 / 不存在
    empty = write(os.path.join(work, "空.md"), "   \n")
    n_before = len(win._custom_templates)
    ask_name(win, empty, "空模板")
    check("D11 空文件拒绝", len(win._custom_templates) == n_before and
          any("内容为空" in t for _ti, t in FakeMsgBox.warns), str(FakeMsgBox.warns[-1:]))
    big = os.path.join(work, "大.md")
    write(big, "x" * (mw_mod.TPL_MAX_BYTES + 1024))
    ask_name(win, big, "大文件")
    check("D12 超大文件拒绝（200KB 上限）", len(win._custom_templates) == n_before and
          any("文件过大" in t for _ti, t in FakeMsgBox.warns), str(FakeMsgBox.warns[-1:]))
    ask_name(win, os.path.join(work, "不存在.md"), "幽灵")
    check("D13 路径不存在拒绝", len(win._custom_templates) == n_before and
          any("无法读取" in t for _ti, t in FakeMsgBox.warns), str(FakeMsgBox.warns[-1:]))

    # ================= E 落盘 / 兜底 / 内核可见 =================
    back = win._load_custom_templates()
    check("E1 写盘后回读与内存一致", back == win._custom_templates,
          json.dumps([t["name"] for t in back], ensure_ascii=False))

    ok = win.save_custom_templates([{"name": "  重 复  ", "content": "# a"},
                                    {"name": "重 复", "content": "# b"}])
    check("E2 保存层同名校验兜底（只留一个）",
          ok and [t["name"] for t in win._custom_templates] == ["重 复"],
          json.dumps([t["name"] for t in win._custom_templates], ensure_ascii=False))
    ok = win.save_custom_templates([{"name": "  ", "content": "# a"}, {"name": "有效", "content": " "}])
    check("E3 保存层过滤空名 / 空内容 → 空列表", ok and win._custom_templates == [],
          json.dumps(win._custom_templates, ensure_ascii=False))

    # 内核菜单可见：写两个模板 → 悬浮栏 📄 菜单末两项为自定义名
    win.save_custom_templates([{"name": "甲模板", "content": "# 甲\n\n正文"},
                               {"name": "乙模板", "content": "# 乙\n\n正文"}])
    setmd(win, "普通段落")
    js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var w = document.createTreeWalker(blk, NodeFilter.SHOW_TEXT);
  var sn = null, en = null, n;
  while (n = w.nextNode()) { if (!sn) sn = n; en = n; }
  if (!sn) return 'no-text';
  var rg = document.createRange();
  rg.setStart(sn, 0); rg.setEnd(en, en.nodeValue.length);
  var s = window.getSelection(); s.selectAllChildren(blk); return 'ok';
})()""")
    wait(500)
    js(win, """(function(){
  var btns = document.querySelectorAll('#floatbar button');
  for (var i = 0; i < btns.length; i++) {
    if (btns[i].title && btns[i].title.indexOf('插入模板') === 0) { btns[i].click(); return 'ok'; }
  }
  return 'no-btn';
})()""")
    wait(400)
    cnt = js(win, "document.querySelectorAll('#submenu .si').length")
    check("E4 内核二级菜单 8 项（内置 6 + 自定义 2）", num(cnt) == "8", repr(cnt))
    tail = js(win, """(function(){
  var items = document.querySelectorAll('#submenu .si');
  if (items.length < 2) return 'short';
  return items[items.length-2].textContent + '|' + items[items.length-1].textContent;
})()""")
    check("E5 自定义模板置于菜单末尾且名称正确",
          isinstance(tail, str) and "甲模板" in tail and "乙模板" in tail, repr(tail))

    LINES.append("RESULT PASS=%d FAIL=%d" % (N_PASS[0], N_FAIL[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    print("DONE")


if __name__ == "__main__":
    main()
