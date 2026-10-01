# -*- coding: utf-8 -*-
"""m108：标题内多格式叠加后渲染出现字面 <u>~~…~~</u>（FMT-14 排查）
用户报告：标题里输入 asdfasdf 后不断随机点格式按钮，界面出现 <u>~~asdfasdf~~</u>，
源码为 `### *<u>~~**asdfasdf**~~</u>*`（嵌套本身合法）。
怀疑点：parseInline 的 em 闭合扫描只查 s[j-1]，不查 s[j+1] 是否属于 ** 游程 →
`*<u>~~**x**~~</u>*` 的开头 * 误配到内层 ** 的第一个 *，把 `<u>~~` 切进 em 当字面文本。
（FMT-11 修复前斜体插在 <u> 内侧，这条路径从未被走到。）
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m108.txt")
LINES = []
def log(s): LINES.append(str(s))
def check(name, cond, extra=""):
    LINES.append(("PASS | " if cond else "FAIL | ") + name + ("" if cond else " | " + str(extra)[:400]))

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

SEL_JS = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var host = blk.querySelector('[contenteditable]') || blk;
  host.focus();
  var rg = document.createRange(); rg.selectNodeContents(host);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return 'ok';
})()"""

DUMP = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return '{}';
  var raw = '';
  try { raw = (JSON.parse(window.__raw()).raw || [''])[0]; } catch(e) {}
  return JSON.stringify({raw: raw, isRaw: blk.classList.contains('raw-edit'),
    cls: blk.className, blkHTML: blk.innerHTML});
})()"""

def dump(win):
    try:
        return json.loads(js(win, DUMP) or "{}")
    except Exception:
        return {}

def type_end(win, text):
    code = """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var t = blk.querySelector('[contenteditable]') || blk;
  t.focus();
  var rg = document.createRange(); rg.selectNodeContents(t); rg.collapse(false);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.execCommand('insertText', false, %s);
  return t.textContent;
})()""" % json.dumps(text)
    r = js(win, code)
    wait(420)
    return r

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    # ---------- A：还原用户操作流（标题输入 → 粗→删→下划线→斜体） ----------
    setmd(win, "### ")
    type_end(win, "asfdsafdafd")
    log("[A] 输入后 raw=%s" % json.dumps(md0(win), ensure_ascii=False))
    for act in ("bold", "strike", "underline", "italic"):
        js(win, SEL_JS); wait(120)
        js(win, "window.__applyFloat('%s')" % act); wait(450)
        log("[A] %s 后 raw=%s" % (act, json.dumps(md0(win), ensure_ascii=False)))
    dA = dump(win)
    log("[A] 终态 blkHTML=%s" % json.dumps(dA.get("blkHTML"), ensure_ascii=False))
    rawA = dA.get("raw") or ""
    legalA = ("### **~~<u>*asfdsafdafd*</u>~~**",   # 斜体落 <u> 内侧（合法 LIFO）
              "### *<u>~~**asfdsafdafd**~~</u>*")   # 斜体在最外层（用户报告形态）
    check("A1 标题叠加后 raw 为合法嵌套（无字面交错）",
          rawA in legalA, rawA)
    htmlA = dA.get("blkHTML") or ""
    check("A2 渲染 DOM 无字面标记（无 &lt;u&gt; / 游离 ~~ / 游离 *）",
          "&lt;u&gt;" not in htmlA and "&lt;/u&gt;" not in htmlA
          and "<strong>" in htmlA and "<del>" in htmlA and "<u>" in htmlA and "<em>" in htmlA,
          htmlA[:300])
    check("A3 仍为渲染态", dA.get("isRaw") is False, str(dA.get("isRaw")))

    # ---------- B：直接灌入用户源码 → 标题渲染 ----------
    setmd(win, "### *<u>~~**asdfasdf**~~</u>*")
    dB = dump(win)
    htmlB = dB.get("blkHTML") or ""
    log("[B] 标题 blkHTML=%s" % json.dumps(htmlB, ensure_ascii=False))
    check("B1 标题渲染嵌套正确 em>u>del>strong",
          "<em>" in htmlB and htmlB.find("<em>") < htmlB.find("<u>")
          and htmlB.find("<u>") < htmlB.find("<del>")
          and htmlB.find("<del>") < htmlB.find("<strong>")
          and "asdfasdf" in htmlB,
          htmlB[:300])
    check("B2 无字面标签文本",
          "&lt;u&gt;" not in htmlB and "&lt;/u&gt;" not in htmlB, htmlB[:300])

    # ---------- C：段落同源码 ----------
    setmd(win, "*<u>~~**asdfasdf**~~</u>*")
    dC = dump(win)
    htmlC = dC.get("blkHTML") or ""
    log("[C] 段落 blkHTML=%s" % json.dumps(htmlC, ensure_ascii=False))
    check("C1 段落渲染嵌套正确且无字面标签",
          "<em>" in htmlC and "<u>" in htmlC and "<del>" in htmlC and "<strong>" in htmlC
          and "&lt;u&gt;" not in htmlC, htmlC[:300])

    # ---------- D：列表同源码 ----------
    setmd(win, "- *<u>~~**asdfasdf**~~</u>*")
    dD = dump(win)
    htmlD = dD.get("blkHTML") or ""
    log("[D] 列表 blkHTML=%s" % json.dumps(htmlD, ensure_ascii=False))
    check("D1 列表渲染嵌套正确且无字面标签",
          "<em>" in htmlD and "<u>" in htmlD and "<del>" in htmlD and "<strong>" in htmlD
          and "&lt;u&gt;" not in htmlD, htmlD[:300])

    # ---------- E：em 闭合扫描的既有语义回归 ----------
    setmd(win, "### *a **b** c*")
    dE = dump(win)
    htmlE = dE.get("blkHTML") or ""
    log("[E] *a **b** c* blkHTML=%s" % json.dumps(htmlE, ensure_ascii=False))
    check("E1 空格分隔的嵌套 em+strong 正常",
          htmlE.count("<em>") == 1 and htmlE.count("<strong>") == 1
          and htmlE.find("<strong>") > htmlE.find("<em>"), htmlE[:300])

    setmd(win, "### *斜体*")
    dE2 = dump(win)
    htmlE2 = dE2.get("blkHTML") or ""
    check("E2 纯斜体正常", "<em>斜体</em>" in htmlE2, htmlE2[:300])

    setmd(win, "### **粗体**")
    dE3 = dump(win)
    htmlE3 = dE3.get("blkHTML") or ""
    check("E3 纯粗体正常", "<strong>粗体</strong>" in htmlE3, htmlE3[:300])

    setmd(win, "### **==asdfasdf==**")
    dE4 = dump(win)
    htmlE4 = dE4.get("blkHTML") or ""
    check("E4 粗+高亮正常（v3.37 用户场景回归）",
          "<strong>" in htmlE4 and "<mark>" in htmlE4 and "asdfasdf" in htmlE4
          and "==" not in htmlE4.replace("==", "", 1), htmlE4[:300])

    # ---------- F：下划线 → 斜体 → 再点下划线（用户报告：异常进入源码态） ----------
    setmd(win, "### ")
    type_end(win, "asfdsafdafd")
    js(win, SEL_JS); wait(120)
    js(win, "window.__applyFloat('underline')"); wait(450)
    log("[F] underline 后 raw=%s" % json.dumps(md0(win), ensure_ascii=False))
    js(win, SEL_JS); wait(120)
    js(win, "window.__applyFloat('italic')"); wait(450)
    log("[F] italic 后 raw=%s" % json.dumps(md0(win), ensure_ascii=False))
    js(win, SEL_JS); wait(120)
    js(win, "window.__applyFloat('underline')"); wait(450)
    dF = dump(win)
    dbgF = js(win, "JSON.stringify(window.__fmtDbg||{})")
    log("[F] 2nd underline 后 raw=%s isRaw=%s dbg=%s blkHTML=%s" % (
        json.dumps(dF.get("raw"), ensure_ascii=False), dF.get("isRaw"),
        dbgF, json.dumps((dF.get("blkHTML") or "")[:200], ensure_ascii=False)))
    check("F1 下划线内侧有斜体时再点下划线 = toggle 取消（与粗体行为一致）",
          dF.get("isRaw") is False and (dF.get("raw") or "") == "### *asfdsafdafd*",
          json.dumps({"raw": dF.get("raw"), "isRaw": dF.get("isRaw"), "dbg": dbgF},
                     ensure_ascii=False))
    check("F2 取消后渲染无字面标签",
          "&lt;" not in (dF.get("blkHTML") or "") and "<em>" in (dF.get("blkHTML") or ""),
          (dF.get("blkHTML") or "")[:200])

    # ---------- G：A 流程继续：斜体后再点下划线（深层嵌套 toggle） ----------
    setmd(win, "### ")
    type_end(win, "asfdsafdafd")
    for act in ("bold", "strike", "underline", "italic"):
        js(win, SEL_JS); wait(120)
        js(win, "window.__applyFloat('%s')" % act); wait(400)
    js(win, SEL_JS); wait(120)
    js(win, "window.__applyFloat('underline')"); wait(450)
    dG = dump(win)
    log("[G] 深层嵌套 toggle 后 raw=%s isRaw=%s" % (
        json.dumps(dG.get("raw"), ensure_ascii=False), dG.get("isRaw")))
    check("G1 深层嵌套（**~~<u>*x*</u>~~**）再点下划线 = 只取消 <u>",
          dG.get("isRaw") is False and (dG.get("raw") or "") == "### **~~*asfdsafdafd*~~**",
          json.dumps({"raw": dG.get("raw"), "isRaw": dG.get("isRaw")}, ensure_ascii=False))

    # ---------- H：列表 / 引用块同流程审计 ----------
    for tag, pre in (("list", "- "), ("quote", "> ")):
        setmd(win, pre)
        type_end(win, "asfdsafdafd")
        for act in ("underline", "italic"):
            js(win, SEL_JS); wait(120)
            js(win, "window.__applyFloat('%s')" % act); wait(400)
        js(win, SEL_JS); wait(120)
        js(win, "window.__applyFloat('underline')"); wait(450)
        dH = dump(win)
        rawH = dH.get("raw") or ""
        want = pre + "*asfdsafdafd*"
        check("H %s 下划线→斜体→下划线 = toggle 且保持渲染态" % tag,
              dH.get("isRaw") is False and rawH == want,
              json.dumps({"raw": rawH, "isRaw": dH.get("isRaw")}, ensure_ascii=False))

    with io_open(OUT) as f:
        f.write("\n".join(LINES) + "\n")
    print("DONE m108")

def io_open(p):
    import io
    return io.open(p, "w", encoding="utf-8")

if __name__ == "__main__":
    main()
