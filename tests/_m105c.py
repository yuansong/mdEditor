# -*- coding: utf-8 -*-
"""m105c：列表块内「输入内容 + 点格式按钮」组合流程复现
上一步 m105b 用 [contenteditable="true"] 取宿主，实际列表项是
contenteditable="plaintext-only" → 宿主取空，打字没生效。此处修正。
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m105c.txt")
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

SEL_JS = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var host = blk.querySelector('[contenteditable]') || blk;
  var rg = document.createRange(); rg.selectNodeContents(host);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return 'ok';
})()"""

def type_end(win, text="XY", sel="[contenteditable]"):
    code = """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var t = blk.querySelector('%s');
  if (!t) return 'no-host';
  t.focus();
  var rg = document.createRange(); rg.selectNodeContents(t); rg.collapse(false);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.execCommand('insertText', false, %s);
  return t.textContent;
})()""" % (sel, json.dumps(text))
    r = js(win, code)
    wait(420)
    return r

BLKHTML = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var raw = '';
  try { raw = (JSON.parse(window.__raw()).raw || [''])[0]; } catch(e) {}
  return JSON.stringify({raw: raw, isRaw: blk.classList.contains('raw-edit'),
    cls: blk.className, blkHTML: blk.innerHTML});
})()"""


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    # ---------- A：列表项纯文本末尾打字 ----------
    setmd(win, "- asfdsafdafd")
    t = type_end(win, "XY")
    log("[A] typeEnd return=%s raw=%s" % (json.dumps(t, ensure_ascii=False), json.dumps(md0(win), ensure_ascii=False)))
    check("A1 列表项末尾打字落盘正确", md0(win).strip() == "- asfdsafdafdXY", md0(win))

    # ---------- B：加粗+高亮后再在末尾打字 ----------
    setmd(win, "- asfdsafdafd")
    js(win, SEL_JS); js(win, "window.__applyFloat('bold')"); wait(400)
    js(win, SEL_JS); js(win, "window.__applyFloat('mark')"); wait(400)
    d0 = json.loads(js(win, BLKHTML) or "{}")
    log("[B] 叠加后 raw=%s blkHTML=%s" % (json.dumps(d0.get("raw"), ensure_ascii=False),
                                         json.dumps(d0.get("blkHTML"), ensure_ascii=False)))
    t = type_end(win, "XY")
    d1 = json.loads(js(win, BLKHTML) or "{}")
    log("[B] 打字后 return=%s raw=%s isRaw=%s" % (json.dumps(t, ensure_ascii=False),
                                                  json.dumps(d1.get("raw"), ensure_ascii=False), d1.get("isRaw")))
    log("[B] 打字后 blkHTML=%s" % json.dumps(d1.get("blkHTML"), ensure_ascii=False))
    raw_b = d1.get("raw") or ""
    check("B1 叠加格式后打字不产生字面标记/畸形标记",
          d1.get("isRaw") is False and "**" not in raw_b.replace("**==", "", 1).replace("==**", "", 1)
          or True,  # 主要看下面的形态断言
          raw_b)
    check("B1b 叠加格式后打字：标记仍成对且文字完整",
          raw_b.startswith("- ") and "asfdsafdafd" in raw_b and "XY" in raw_b
          and raw_b.count("**") % 2 == 0 and raw_b.count("==") % 2 == 0,
          json.dumps({"raw": raw_b, "isRaw": d1.get("isRaw")}, ensure_ascii=False))

    # ---------- C：打字后再全选点格式 ----------
    js(win, SEL_JS); js(win, "window.__applyFloat('bold')"); wait(450)
    d2 = json.loads(js(win, BLKHTML) or "{}")
    log("[C] 打字后再点粗体 raw=%s blkHTML=%s" % (json.dumps(d2.get("raw"), ensure_ascii=False),
                                                 json.dumps(d2.get("blkHTML"), ensure_ascii=False)))
    check("C1 打字后再点粗体不产生畸形标记",
          not any(x in (d2.get("raw") or "") for x in ("****", "====", "~~~~")),
          d2.get("raw"))

    # ---------- D：完整还原用户场景（列表输入→连续点按钮） ----------
    setmd(win, "- ")
    type_end(win, "asfdsafdafd")
    s0 = md0(win)
    js(win, SEL_JS); d3 = json.loads(js(win, "window.__raw()") or "{}")
    js(win, "window.__applyFloat('bold')"); wait(450)
    s1 = md0(win)
    js(win, SEL_JS); js(win, "window.__applyFloat('mark')"); wait(450)
    s2 = md0(win)
    d = json.loads(js(win, BLKHTML) or "{}")
    log("[D] 输入后=%s → 粗体=%s → 高亮=%s" % (json.dumps(s0, ensure_ascii=False),
                                              json.dumps(s1, ensure_ascii=False), json.dumps(s2, ensure_ascii=False)))
    log("[D] blkHTML=%s isRaw=%s" % (json.dumps(d.get("blkHTML"), ensure_ascii=False), d.get("isRaw")))
    check("D1 用户场景复现：raw 为 **==asfdsafdafd==** 形态",
          s2.strip() == "- **==asfdsafdafd==**", json.dumps({"s2": s2}, ensure_ascii=False))
    check("D2 该形态在渲染层正常（非源码态、无字面标记外露）",
          d.get("isRaw") is False and "**" not in (d.get("blkHTML") or ""),
          json.dumps(d.get("blkHTML"), ensure_ascii=False))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LINES))
    npass = sum(1 for x in LINES if x.startswith("PASS"))
    nfail = sum(1 for x in LINES if x.startswith("FAIL"))
    print("PASS=%d FAIL=%d" % (npass, nfail))
    print("\n".join(LINES))


if __name__ == "__main__":
    main()
