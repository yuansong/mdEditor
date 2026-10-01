# -*- coding: utf-8 -*-
"""m97: 斜杠菜单「模板」下发与插入全链路探针。

> v3.36（TPL-E）适配：模板体系统一后，`setCustomTemplates` 下发的列表**即**菜单
> 内容的权威来源（不再与内核 TPL_BUILTIN 拼接），悬浮栏「📄 插入模板」按钮与
> TemplateManagerDialog 已移除。原 T2（内置索引固定为 0）/ T4（悬浮栏按钮）/
> T6（模态管理对话框）三项随之作废 —— 管理页改由 `tests/_m102.py` 覆盖。
> 本探针保留「下发 → / 菜单插入」机制、引用块内插入、非法项过滤、持久化回读。

T1 setCustomTemplates 下发即菜单内容（索引 0/1 可取，越界 NOSUB）
T2 内置模板内容可随列表下发（内核不再依赖 TPL_BUILTIN 兜底）
T3 引用块内插入模板（tpl 分支排除引用 → 插到块后）
T5 非法项过滤（空名 / 空内容不进菜单，返回生效数）
T7 持久化回读（save → _load 一致）
结果写 _m97.txt，PASS/FAIL 逐条判定。
"""
import json, os, sys, time, tempfile
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
import mainwindow as mw_mod
from mainwindow import MainWindow
from config import BUILTIN_TEMPLATES

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m97.txt")
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


def raws(win):
    return js(win, "JSON.stringify(window.__raw())")


def open_slash(win):
    js(win, "(function(){var el=document.querySelector('.raw-edit');"
            "if(!el)return 'noedit';"
            "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
            "return 'x'})()")
    wait(300)


def pick(win, item, sub=None):
    arg = "null" if sub is None else str(sub)
    r = js(win, "window.__slashPick(" + json.dumps(item) + "," + arg + ")")
    wait(450)
    return r


def num(r):
    """js 返回的数字（可能带 .0 浮点尾巴）→ int 字符串"""
    try:
        return str(int(float(r)))
    except (TypeError, ValueError):
        return str(r)


TMPLS = [
    {"name": "周报-项目版", "content": "# 周报-项目版\n\n## 本周完成\n\n- 事项甲"},
    {"name": "引用片段", "content": "> 引用片段内容"},
]
BUILTIN_TECH = [b for b in BUILTIN_TEMPLATES if b["name"] == "技术笔记"][0]
TECH = [dict(BUILTIN_TECH)]


def main():
    app = QApplication(sys.argv)
    # T7：模板文件指向临时路径，避免污染真实用户数据
    tmpdir = tempfile.mkdtemp(prefix="m97_tpl_")
    tpl_file = os.path.join(tmpdir, "templates.json")
    mw_mod.TEMPLATE_FILE = tpl_file
    mw_mod.USER_DATA_DIR = tmpdir

    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"): break
        wait(500)

    # ---------- T1 下发即菜单内容 ----------
    r = js(win, "window.setCustomTemplates(" + json.dumps(TMPLS, ensure_ascii=False) + ")")
    check("T1 下发返回生效数=2", num(r) == "2", repr(r))
    setmd(win, "")
    open_slash(win)
    pick(win, "tpl", 0)
    rr = raws(win)
    check("T1 自定义模板1 经 / 菜单插入（索引 0）",
          rr and "# 周报-项目版" in rr and "事项甲" in rr, (rr or "")[:120])
    setmd(win, "")
    open_slash(win)
    pick(win, "tpl", 1)
    rr = raws(win)
    check("T1b 自定义模板2（引用内容）插入（索引 1）", rr and "引用片段内容" in rr, (rr or "")[:120])
    setmd(win, "")
    open_slash(win)
    st = pick(win, "tpl", 2)
    check("T1c 越界索引返回 NOSUB（下发列表即全部）", str(st).startswith("NOSUB"), repr(st))

    # ---------- T2 内置模板内容可随列表下发 ----------
    setmd(win, "")
    open_slash(win)
    pick(win, "tpl", 0)          # 仍用上一轮的 2 项列表
    rr = raws(win) or ""
    check("T2 下发列表覆盖内核兜底（技术笔记不再出现在索引 0）",
          "技术笔记" not in rr, rr[:100])
    r = js(win, "window.setCustomTemplates(" + json.dumps(TECH, ensure_ascii=False) + ")")
    check("T2b 仅下发内置 1 项 → 返回 1", num(r) == "1", repr(r))
    setmd(win, "")
    open_slash(win)
    pick(win, "tpl", 0)
    rr = raws(win)
    check("T2c 内置内容随列表插入", rr and "技术笔记" in rr and "关键结论" in rr, (rr or "")[:120])

    # ---------- T3 引用块内插入 → 追加到块后 ----------
    js(win, "window.setCustomTemplates(" + json.dumps(TMPLS, ensure_ascii=False) + ")")
    setmd(win, "> 引用行")
    r = js(win, """(function(){
  var bq = document.querySelector('#editor blockquote');
  if (!bq) return 'no-bq';
  bq.focus();
  bq.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
  bq.dispatchEvent(new KeyboardEvent('keydown', {key:'/', bubbles:true, cancelable:true}));
  return 'ok';
})()""")
    wait(400)
    check("T3 前置：引用块唤起 / 菜单", r == "ok", repr(r))
    pick(win, "tpl", 0)
    rr = raws(win)
    ok = rr and "> 引用行" in rr and "# 周报-项目版" in rr
    check("T3 引用块内插模板 → 块后整组插入", ok, (rr or "")[:160])

    # ---------- T5 非法项过滤 ----------
    r = js(win, "window.setCustomTemplates(" + json.dumps(
        [{"name": "", "content": "x"}, {"name": "bad2", "content": "   "}, TMPLS[0]],
        ensure_ascii=False) + ")")
    check("T5 空名 / 空内容被过滤（返回 1）", num(r) == "1", repr(r))
    r = js(win, "window.setCustomTemplates('[]')")
    check("T5b 空列表返回 0 且一级项消失",
          num(r) == "0" and str(pick(win, "tpl", 0)).startswith("NOITEM"), repr(r))

    # ---------- T7 持久化回读 ----------
    win._custom_templates = [dict(TMPLS[0])]
    win.save_custom_templates(win._custom_templates)
    back = win._load_custom_templates()
    check("T7 _load_custom_templates 回读一致",
          back == [{"name": "周报-项目版", "content": TMPLS[0]["content"]}],
          json.dumps(back, ensure_ascii=False))

    LINES.append("RESULT PASS=%d FAIL=%d" % (N_PASS[0], N_FAIL[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    print("DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        LINES.append("EXCEPTION " + traceback.format_exc())
        LINES.append("RESULT PASS=%d FAIL=%d" % (N_PASS[0], N_FAIL[0]))
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(LINES))
        raise
