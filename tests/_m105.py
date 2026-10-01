# -*- coding: utf-8 -*-
"""m105：列表块内「连续点击行内格式按钮」复现与诊断
用户报告：列表菜单里面输入内容，通过不断点击格式化按钮，
会出现 **==asfdsafdaf==** 这种情况（字面标记留在文档里）。

诊断维度：
  A 列表项内选中文字 → 依次点 粗体 / 高亮，看 raw 与渲染 DOM 实况
  B 同一按钮连点两次是否 toggle 取消
  C 渲染层是否把嵌套标记当字面文本显示（用户所见）
  D 段落 / 引用 / 定义列表 同场景对照
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m105.txt")
LINES = []
def log(s): LINES.append(str(s))
def check(name, cond, extra=""):
    LINES.append(("PASS | " if cond else "FAIL | ") + name + ("" if cond else " | " + str(extra)[:300]))

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

def setmd(win, md):
    js(win, "window.setMarkdown(" + json.dumps(md, ensure_ascii=False) + ")")
    wait(450)

def md0(win):
    return js(win, "window.getMarkdown()") or ""

# 在渲染态把「块 0 内第一个可编辑宿主」的纯文本整体选中
SEL_JS = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var host = blk.querySelector('[contenteditable="true"]') || blk;
  /* 只选纯文本节点，避免把 li 的空尾节点也纳入 */
  var rg = document.createRange();
  rg.selectNodeContents(host);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return JSON.stringify({host: host.tagName, txt: rg.toString()});
})()"""

# 渲染层实况：块内 HTML / 纯文本 / 是否含字面标记
DUMP_JS = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var raw = '';
  try { raw = (JSON.parse(window.__raw()).raw || [''])[0]; } catch(e) {}
  var host = blk.querySelector('[contenteditable="true"]');
  return JSON.stringify({
    raw: raw,
    isRaw: blk.classList.contains('raw-edit'),
    cls: blk.className,
    hostHTML: host ? host.innerHTML : null,
    blkHTML: blk.innerHTML,
    text: blk.textContent
  });
})()"""

def _balanced(raw):
    """行内标记成对性检查（替代原先的「**==」子串黑名单 —— ***== 会误命中）。
    要求：** ~~ == <u>/</u> 的出现次数均为偶数，且无「同字符游程 ≥4」的交错残留。"""
    t = raw
    if t.count("**") % 2 or t.count("~~") % 2 or t.count("==") % 2:
        return False
    if t.count("<u>") != t.count("</u>"):
        return False
    for n in (4, 5, 6):
        if ("*" * n) in t or ("~" * n) in t or ("=" * n) in t:
            return False
    return True


def flow(win, label, actions):
    """对当前块 0 依次执行动作，每步后回读"""
    seq = []
    for a in actions:
        sel = js(win, SEL_JS)
        if a:
            js(win, "window.__applyFloat(%s)" % json.dumps(a))
            wait(420)
        d = {}
        try:
            d = json.loads(js(win, DUMP_JS) or "{}")
        except Exception:
            d = {}
        seq.append({"act": a, "sel": sel, "raw": d.get("raw"), "isRaw": d.get("isRaw"),
                    "text": d.get("text"), "hostHTML": d.get("hostHTML")})
    log("===== %s =====" % label)
    for s in seq:
        log("  act=%-8s raw=%s" % (str(s["act"]), json.dumps(s["raw"], ensure_ascii=False)))
        log("            isRaw=%s text=%s" % (s["isRaw"], json.dumps((s["text"] or "")[:60], ensure_ascii=False)))
        log("            hostHTML=%s" % json.dumps((s["hostHTML"] or "")[:160], ensure_ascii=False))
    return seq


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    # ---------- A：列表内 粗体 + 高亮 ----------
    setmd(win, "- asfdsafdafd")
    a = flow(win, "A 列表：粗体→高亮→粗体（再次）", [None, "bold", "mark", "bold"])
    check("A1 列表内加粗落盘正确", a[1]["raw"] == "- **asfdsafdafd**", a[1]["raw"])
    check("A2 列表内再加高亮无字面标记外露",
          a[2]["isRaw"] is False and "**" not in (a[2]["text"] or "") and "==" not in (a[2]["text"] or ""),
          json.dumps({"raw": a[2]["raw"], "text": a[2]["text"], "isRaw": a[2]["isRaw"]}, ensure_ascii=False))
    check("A3 粗体二次点击 toggle 掉外层",
          "**" not in (a[3]["raw"] or ""), a[3]["raw"])

    # ---------- B：列表内 高亮 + 粗体（反向顺序） ----------
    setmd(win, "- asfdsafdafd")
    b = flow(win, "B 列表：高亮→粗体→高亮（再次）", [None, "mark", "bold", "mark"])
    check("B1 列表内高亮落盘正确", b[1]["raw"] == "- ==asfdsafdafd==", b[1]["raw"])
    check("B2 再叠粗体后渲染无字面标记",
          b[2]["isRaw"] is False and "**" not in (b[2]["text"] or "") and "==" not in (b[2]["text"] or ""),
          json.dumps({"raw": b[2]["raw"], "text": b[2]["text"], "isRaw": b[2]["isRaw"]}, ensure_ascii=False))
    check("B3 高亮二次点击 toggle 掉", "==" not in (b[3]["raw"] or ""), b[3]["raw"])

    # ---------- C：同一按钮连点 4 次（toggle 往复） ----------
    setmd(win, "- asfdsafdafd")
    c = flow(win, "C 列表：粗体 x4（toggle 往复）", [None, "bold", "bold", "bold", "bold"])
    rawseq = [x["raw"] for x in c]
    check("C1 连点 4 次粗体在 加粗/取消 间往复，不累加标记",
          rawseq[1] == "- **asfdsafdafd**" and rawseq[2] == "- asfdsafdafd"
          and rawseq[3] == "- **asfdsafdafd**" and rawseq[4] == "- asfdsafdafd",
          json.dumps(rawseq, ensure_ascii=False))

    # ---------- D：三连击不同按钮（用户报告的核心场景） ----------
    setmd(win, "- asfdsafdafd")
    d = flow(win, "D 列表：粗体→斜体→高亮→删除线", [None, "bold", "italic", "mark", "strike"])
    last = d[-1]
    check("D1 四连击后无字面标记外露（渲染态）",
          last["isRaw"] is False and not any(m in (last["text"] or "") for m in ("**", "==", "~~"))
          and last["text"] is not None and "asfdsafdafd" in (last["text"] or ""),
          json.dumps({"raw": last["raw"], "text": last["text"], "isRaw": last["isRaw"]}, ensure_ascii=False))
    check("D2 四连击后 raw 无畸形标记对（游程成对且无交错）",
          not any(x in (last["raw"] or "") for x in ("====", "****", "~~~~"))
          and _balanced(last["raw"] or ""),
          last["raw"])

    # ---------- E：段落 / 引用 / 定义列表 对照 ----------
    for label, md in [("段落", "asfdsafdafd"), ("引用", "> asfdsafdafd"),
                      ("定义列表", "术语\n: asfdsafdafd")]:
        setmd(win, md)
        e = flow(win, "E %s：粗体→高亮" % label, [None, "bold", "mark"])
        last = e[-1]
        check("E1[%s] 叠加后无字面标记外露" % label,
              last["isRaw"] is False and "**" not in (last["text"] or "") and "==" not in (last["text"] or ""),
              json.dumps({"raw": last["raw"], "text": last["text"], "isRaw": last["isRaw"]}, ensure_ascii=False))

    # ---------- F：清除格式 T× 能否一次清干净叠加 ----------
    setmd(win, "- asfdsafdafd")
    js(win, SEL_JS)
    js(win, "window.__applyFloat('bold')"); wait(400)
    js(win, SEL_JS)
    js(win, "window.__applyFloat('mark')"); wait(400)
    f_raw = md0(win)
    js(win, SEL_JS)
    js(win, "window.__applyFloat('clearfmt')"); wait(500)
    f_after = md0(win)
    check("F1 T× 一次清除叠加格式回到裸文本",
          f_after.strip() == "- asfdsafdafd",
          json.dumps({"before": f_raw, "after": f_after}, ensure_ascii=False))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LINES))
    npass = sum(1 for x in LINES if x.startswith("PASS"))
    nfail = sum(1 for x in LINES if x.startswith("FAIL"))
    print("PASS=%d FAIL=%d" % (npass, nfail))
    for x in LINES:
        if x.startswith("FAIL"):
            print(x)


if __name__ == "__main__":
    main()
