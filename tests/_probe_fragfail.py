# -*- coding: utf-8 -*-
"""v3.48.10 探针：片段替换「未真正修改原文」复现与定位。
路径 A：单块/跨块选中 → 直接 window.aiReplaceSel（裸 JS 链路）；
路径 B：setMarkdown → 选中 → 模态对话框 accept 往返 → aiReplaceSel
        （真实使用路径，验证模态对话框是否导致 execCommand 失焦失败）；
路径 C：execCommand 裸调用返回值探测（判定 offscreen 下是否可用）。
"""
import sys, json, os
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QT_OPENGL", "software")
from PySide6.QtCore import QUrl, QTimer, QEventLoop
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtWebEngineWidgets import QWebEngineView

APP = QApplication.instance() or QApplication(sys.argv)
view = QWebEngineView()
view.resize(1280, 900)
loop = QEventLoop()
view.loadFinished.connect(lambda ok: QTimer.singleShot(2500, loop.quit) if ok else loop.quit())
view.load(QUrl("file:///E:/WorkBuddy/md-editor/src/editor.html"))
loop.exec()

def js(code):
    out = []
    lp = QEventLoop()
    def cb(res):
        out.append(res); lp.quit()
    view.page().runJavaScript(code, 0, cb)
    lp.exec()
    return out[0] if out else None

def setmd(md):
    js("window.setMarkdown(%s);" % json.dumps(md, ensure_ascii=False))

def getmd():
    return js("window.getMarkdown();") or ""

def wait(ms):
    lp = QEventLoop()
    QTimer.singleShot(ms, lp.quit)
    lp.exec()

# 选择辅助：按块索引 + 文本节点偏移构造 Range 并触发 selectionchange
SEL = r"""
window.__selOne = function (bi, a, b) {
  var blks = document.querySelectorAll('#editor .blk');
  var blk = blks[bi]; if (!blk) return 'no-blk';
  var w = document.createTreeWalker(blk, NodeFilter.SHOW_TEXT, null);
  var tn = w.nextNode(); if (!tn) return 'no-text';
  var r = document.createRange();
  r.setStart(tn, a); r.setEnd(tn, b);
  var s = getSelection();
  s.removeAllRanges(); s.addRange(r);
  document.dispatchEvent(new Event('selectionchange'));
  return r.toString();
};
window.__selX = function (bi1, a, bi2, b) {
  var blks = document.querySelectorAll('#editor .blk');
  var b1 = blks[bi1], b2 = blks[bi2];
  if (!b1 || !b2) return 'no-blk';
  var w1 = document.createTreeWalker(b1, NodeFilter.SHOW_TEXT, null);
  var t1 = w1.nextNode();
  var w2 = document.createTreeWalker(b2, NodeFilter.SHOW_TEXT, null);
  var t2 = w2.nextNode();
  var r = document.createRange();
  r.setStart(t1, a); r.setEnd(t2, b);
  var s = getSelection();
  s.removeAllRanges(); s.addRange(r);
  document.dispatchEvent(new Event('selectionchange'));
  return r.toString();
};
"""
js(SEL)

MD = "# 标题\n\n第一段需要润色的原文内容。\n\n第二段保持不变的文字。"
NEW = "第一段润色后的崭新内容。"

fails = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(detail) if detail else ""))
    if not cond:
        fails.append(name)

# ---------- 路径 C：execCommand 裸探测 ----------
setmd(MD); wait(400)
r_c = js("""(function(){
  var blk = document.querySelectorAll('#editor .blk')[1];
  var w = document.createTreeWalker(blk, NodeFilter.SHOW_TEXT, null);
  var tn = w.nextNode();
  var r = document.createRange(); r.setStart(tn, 0); r.setEnd(tn, 2);
  var s = getSelection(); s.removeAllRanges(); s.addRange(r);
  var ok = document.execCommand('insertText', false, 'XX');
  return JSON.stringify({ok: ok, md: getMarkdown()});
})();""")
print("C_EXEC_BARE:", r_c)
try:
    d_c = json.loads(r_c)
    check("C_EXEC_WORKS", d_c.get("ok") and "XX" in d_c.get("md", ""), d_c)
except Exception as e:
    check("C_EXEC_WORKS", False, "%s %r" % (e, r_c))

# ---------- 路径 A1：单块选中 → 直接 aiReplaceSel ----------
setmd(MD); wait(400)
sel_txt = js("__selOne(1, 0, 3)")
orig = js("window.aiSelText();")
res1 = js("window.aiReplaceSel(%s, %s);" % (
    json.dumps(NEW, ensure_ascii=False), json.dumps(orig or "", ensure_ascii=False)))
md_after1 = getmd()
print("A1 sel=%r orig=%r res=%s" % (sel_txt, orig, res1))
print("A1 md_after:", md_after1[:80])
try:
    d1 = json.loads(res1)
    check("A1_OK", d1.get("ok"), d1)
    # 选区为块1 前 3 字「第一段」：替换后应以新文本开头、原「第一段」被替换掉
    check("A1_MD_REPLACED", md_after1.startswith("# 标题\n\n" + NEW)
          and "第一段需要润色" not in md_after1, md_after1[:60])
except Exception as e:
    check("A1_OK", False, "%s %r" % (e, res1))

# ---------- 路径 A2'：选区漂移兜底（AI-RELOC）—— Range 指向块1「第一段」，
#              但 orig 快照是块2 的文本（模拟用户 AI 往返期间点到别处） ----------
setmd(MD); wait(400)
js("__selOne(1, 0, 3)")     # _aiSelRange=块1[0,3)、_aiSelText='第一段'
res_a2 = js("window.aiReplaceSel(%s, %s);" % (
    json.dumps("重新定位后的替换内容", ensure_ascii=False),
    json.dumps("第二段保持不变的文字。", ensure_ascii=False)))
md_after2 = getmd()
print("A2 res=%s" % res_a2)
print("A2 md_after:", md_after2[:100])
try:
    d2 = json.loads(res_a2)
    check("A2_RELOC_OK", d2.get("ok"), d2)
    check("A2_RELOC_MD", "重新定位后的替换内容" in md_after2
          and "第二段保持不变的文字" not in md_after2, md_after2[:80])
except Exception as e:
    check("A2_RELOC_OK", False, "%s %r" % (e, res_a2))

# ---------- 路径 A2b：原文确实被删改 → relocate 失败 → stale-selection ----------
setmd(MD); wait(400)
js("__selOne(1, 0, 3)")
res_a2b = js("window.aiReplaceSel(%s, %s);" % (
    json.dumps("不应写入的内容", ensure_ascii=False),
    json.dumps("这段文字在文档中根本不存在xyz", ensure_ascii=False)))
print("A2b res=%s" % res_a2b)
try:
    # v3.48.31：错误码随版本演进 —— 内核实际返回 not-found / stale-dom，
    # 断言按语义写：必须失败（ok=false）且不得写入任何内容
    d2b = json.loads(res_a2b)
    no_write = "不应写入的内容" not in getmd()
    check("A2B_RELOC_MISS_STALE",
          (not d2b.get("ok")) and d2b.get("err") in ("stale-selection", "not-found")
          and no_write,
          dict(d2b, no_write=no_write))
except Exception as e:
    check("A2B_RELOC_MISS_STALE", False, "%s %r" % (e, res_a2b))

# ---------- 路径 B：模态对话框往返后 ----------
setmd(MD); wait(400)
js("__selOne(1, 0, 3)")
orig3 = js("window.aiSelText();")

class _Dlg(QDialog):
    def __init__(self):
        super().__init__()
        self.resize(300, 200)
QTimer.singleShot(0, lambda: [d.accept() for d in [QDialog()] if False])
dlg = _Dlg()
QTimer.singleShot(50, dlg.accept)
dlg.exec()   # 模态往返一次（开→立即 accept）
wait(200)

res3 = js("window.aiReplaceSel(%s, %s);" % (
    json.dumps("模态往返后的替换内容", ensure_ascii=False),
    json.dumps(orig3 or "", ensure_ascii=False)))
md_after3 = getmd()
print("B orig=%r res=%s" % (orig3, res3))
print("B md_after:", md_after3[:100])
try:
    d3 = json.loads(res3)
    check("B_OK", d3.get("ok"), d3)
    check("B_MD_CHANGED", "模态往返后的替换内容" in md_after3, md_after3[:80])
except Exception as e:
    check("B_OK", False, "%s %r" % (e, res3))

print("FAIL_COUNT=%d" % len(fails))
print("RESULT=%s" % ("OK" if not fails else "FAIL:" + ",".join(fails)))
