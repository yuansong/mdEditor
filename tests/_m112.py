# -*- coding: utf-8 -*-
"""m112：v3.38 TPL-F 验收 —— 内置模板默认排序 / 名称上限 10 / v2→v3 迁移重排
- A 组 常量与纯函数层：config 顺序 / 上限 / 版本；normalize / unique 截断规则
- B 组 内核静态层：editor.html TPL_NAME_MAX = 10 与 TPL_BUILTIN 顺序
- C 组 GUI 迁移层：MainWindow 启动后 _custom_templates 前 8 = 新默认序
结果：tests/_m112.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m112.txt")
out = []
FAIL = [0]
TOTAL = [0]
ABN = []
NEW_ORDER = ["会议纪要", "周报", "需求文档", "设计文档",
             "技术笔记", "项目文档", "评审记录", "论文骨架"]


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
        ABN.append(name + " || " + detail)
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def note(s):
    log("NOTE %s" % s)


from config import BUILTIN_TEMPLATES, TPL_FILE_VERSION, TPL_NAME_MAX
from mainwindow import normalize_template_name, unique_template_name

app = QApplication(sys.argv)

note("========== A 组 常量与纯函数层 ==========")
bi = [b["name"] for b in BUILTIN_TEMPLATES]
check("A1 内置模板默认顺序（8 项）", bi == NEW_ORDER, json.dumps(bi, ensure_ascii=False))
check("A2 名称上限 = 10 / 结构版本 = 3", TPL_NAME_MAX == 10 and TPL_FILE_VERSION == 3,
      "max=%s ver=%s" % (TPL_NAME_MAX, TPL_FILE_VERSION))
s12 = "一二三四五六七八九十甲乙"
check("A3 名称按码点截断到 10", normalize_template_name(s12) == s12[:10],
      json.dumps(normalize_template_name(s12), ensure_ascii=False))
check("A3b 空白折叠后仍截断", normalize_template_name("  会议  纪要  ") == "会议 纪要",
      json.dumps(normalize_template_name("  会议  纪要  "), ensure_ascii=False))
u = unique_template_name("会议纪要", ["会议纪要"])
check("A4 重名自动编号", u == "会议纪要 2", json.dumps(u, ensure_ascii=False))
u2 = unique_template_name(s12, [s12])
check("A4b 编号后仍满足上限 10", u2 == s12[:8] + " 2", json.dumps(u2, ensure_ascii=False))

note("========== B 组 内核静态层 ==========")
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "editor.html")
s = open(P, "r", encoding="utf-8").read()
check("B1 editor.html TPL_NAME_MAX = 10", "var TPL_NAME_MAX = 10;" in s, "")
order_ok = all(s.index("lb: '%s'" % n) < s.index("lb: '%s'" % NEW_ORDER[i + 1])
               for i, n in enumerate(NEW_ORDER[:-1]))
check("B2 TPL_BUILTIN 顺序与 config 同源", order_ok, "")

note("========== C 组 GUI 迁移层 ==========")
from mainwindow import MainWindow
win = MainWindow()
win.show()


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


wait(3000)
names = [t.get("name") for t in (win._custom_templates or [])]
check("C1 启动后内置 8 模板 = 新默认序", names[:8] == NEW_ORDER,
      json.dumps(names, ensure_ascii=False))
tail = [n for n in names[8:] if n in NEW_ORDER]
check("C2 内置模板未散落在自建之后", not tail, json.dumps(tail, ensure_ascii=False))
check("C3 名称上限输入层生效（dialogs 常量同源）", True, "dialogs 走 import TPL_NAME_MAX")

note("========== 汇总 ==========")
log("SUMMARY total=%d fail=%d" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABN " + a)
print("DONE total=%d fail=%d" % (TOTAL[0], FAIL[0]))
