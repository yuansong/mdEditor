# -*- coding: utf-8 -*-
"""m75 回归：图片交互（v3.30.16 → v3.30.17 右键菜单化）

1) 图片操作收进右键菜单：「显示图片」→ 应用内大图预览（点击任意处 / Esc 关闭）
2) 右键菜单「复制图片」→ 位图进系统剪贴板（经 Python _img_copy）
（v3.30.17：选中图片不再浮现悬浮按钮条，操作全部走右键菜单）

覆盖：data URL 内嵌图、相对路径图（解析成 file://）、文档不被复制动作改动、
非图片块不出现「复制图片」、Python 侧三种来源（data URL / 本地文件 / 坏数据）。
"""
import json, os, sys, tempfile
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m75.txt")
out = []
FAIL = [0]
TOTAL = [0]

def _png_b64(w=4, h=4, rgb=(0, 82, 217)):
    """程序生成一个合法的最小 PNG（网传的 1x1 base64 常量有 IDAT 校验错误，
    QImage 解不出来，会让剪贴板用例假失败）。"""
    import struct, zlib

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    blob = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))
    return base64.b64encode(blob).decode("ascii")


import base64  # noqa: E402
PNG1 = "data:image/png;base64," + _png_b64()


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def parse(s):
    try:
        return json.loads(s)
    except Exception:
        return {"err": str(s)[:160]}


wait(3000)

# ---------- A. 右键菜单「显示图片」+ 大图预览（v3.30.17：操作收进右键菜单） ----------
js("window.setMarkdown(%s)" % json.dumps("X\n\n![图](%s)" % PNG1))
wait(1000)
CTX_SHOW = """(function(){
  var img=document.querySelectorAll('#editor img')[0];
  if(!img) return JSON.stringify({err:'noimg'});
  img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:200,clientY:200}));
  var bm=document.getElementById('blkmenu');
  var acts=[].map.call(bm.querySelectorAll('.mi'),function(x){return x.getAttribute('data-act')});
  var it=bm.querySelector('.mi[data-act="viewimg"]');
  if(!it) return JSON.stringify({err:'noview', acts:acts});
  it.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
  return JSON.stringify({acts:acts, view: JSON.parse(window.__imgView())});
})()"""
v1 = parse(js(CTX_SHOW))
log("A menu+show = %s" % json.dumps(v1)[:200])
check("A1 右键菜单含「显示图片」", "viewimg" in (v1.get("acts") or []), json.dumps(v1.get("acts")))
check("A2 点「显示图片」打开预览", v1.get("view", {}).get("show") is True, json.dumps(v1.get("view", {}))[:120])
check("A3 预览 src 为图片地址", str(v1.get("view", {}).get("src", "")).startswith("data:image") or "file://" in str(v1.get("view", {}).get("src", "")),
      str(v1.get("view", {}).get("src", ""))[:60])

ESC = """(function(){
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));
  return window.__imgView();
})()"""
v2 = parse(js(ESC))
check("A4 Esc 关闭预览", v2.get("show") is False and v2.get("src") == "", json.dumps(v2)[:100])

CLICK_BG = """(function(){
  window.__imgViewOpen(1);
  var iv=document.getElementById('imgview');
  iv.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));
  return window.__imgView();
})()"""
v3 = parse(js(CLICK_BG))
check("A5 点击遮罩关闭预览", v3.get("show") is False and v3.get("src") == "", json.dumps(v3)[:100])

# 相对路径图：src 应解析为 file:// 且带上文档目录
REL = """(function(){
  window.setMarkdown("X\\n\\n![图](doc.assets/00001_a.png)");
  window.setDocDir("C:/tmpdir");
  return window.__imgViewOpen(1);
})()"""
v4 = parse(js(REL))
wait(600)
log("A rel preview = %s" % json.dumps(v4))
check("A6 相对路径解析为 file://", str(v4.get("src", "")).startswith("file:///C:/tmpdir/"),
      str(v4.get("src", ""))[:80])
js("window.setDocDir('')")

# ---------- B. 右键菜单「复制图片」 ----------
js("window.setMarkdown(%s)" % json.dumps("X\n\n![图](%s)" % PNG1))
wait(1000)

CTX = """(function(){
  var img=document.querySelectorAll('#editor img')[0];
  if(!img) return JSON.stringify({err:'noimg'});
  img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:200,clientY:200}));
  var bm=document.getElementById('blkmenu');
  var it=bm.querySelector('.mi[data-act="copyimg"]');
  var raw0=JSON.parse(window.__raw()).raw.slice(0);
  if(!it) return JSON.stringify({err:'nocopyitem', menu: bm.textContent});
  it.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
  var r=window.__req;
  var raw1=JSON.parse(window.__raw()).raw;
  return JSON.stringify({menu: bm.textContent, act: r?r.act:null,
                         srcLen: r&&r.src?String(r.src).length:0,
                         same: JSON.stringify(raw0)===JSON.stringify(raw1),
                         menuHidden: !bm.classList.contains('show')});
})()"""
b1 = parse(js(CTX))
log("B ctx = %s" % json.dumps(b1)[:300])
check("B1 图片右键菜单含「复制图片」", "复制图片" in str(b1.get("menu", "")), str(b1.get("menu", ""))[:80])
check("B2 点击后发出 imgCopy 请求", b1.get("act") == "imgCopy", str(b1.get("act")))
check("B3 请求带图片数据", (b1.get("srcLen") or 0) > 50, str(b1.get("srcLen")))
check("B4 复制不改动文档", b1.get("same") is True, str(b1.get("same")))
check("B5 复制后菜单关闭", b1.get("menuHidden") is True, str(b1.get("menuHidden")))

# 非图片的特殊块（分割线）不应出现「复制图片」；普通段落保留系统菜单（不弹块菜单）
CTX2 = """(function(){
  window.setMarkdown("X\\n\\n---");
  var blk=document.querySelectorAll('#editor .blk')[1];
  if(!blk) return JSON.stringify({err:'noblk'});
  blk.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:200,clientY:200}));
  var bm=document.getElementById('blkmenu');
  var hr=JSON.stringify({menu: bm.textContent, has: !!bm.querySelector('.mi[data-act="copyimg"]')});
  window.setMarkdown("X\\n\\nplain paragraph");
  var p=document.querySelectorAll('#editor .blk')[1];
  p.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:200,clientY:200}));
  var shown=bm.classList.contains('show');
  return JSON.stringify({hr: JSON.parse(hr), paraShown: shown});
})()"""
b2 = parse(js(CTX2))
log("B non-image ctx = %s" % json.dumps(b2)[:220])
hr = b2.get("hr") or {}
check("B6 分割线块无「复制图片」", hr.get("has") is False, str(hr.get("menu"))[:80])
check("B7 普通段落保留系统菜单（不弹块菜单）", b2.get("paraShown") is False, str(b2.get("paraShown")))

# ---------- C. Python 侧 _img_copy（剪贴板位图） ----------
raw_bytes = base64.b64decode(PNG1.split(",", 1)[1])
win._img_copy(0, PNG1)
im = QGuiApplication.clipboard().image()
check("C1 data URL 复制进剪贴板", (not im.isNull()) and im.width() == 4 and im.height() == 4,
      "%sx%s" % (im.width(), im.height()))

tmp = os.path.join(tempfile.gettempdir(), "_m75_img.png")
with open(tmp, "wb") as f:
    f.write(raw_bytes)
QGuiApplication.clipboard().clear()
win._img_copy(0, tmp.replace("\\", "/"))
im2 = QGuiApplication.clipboard().image()
check("C2 本地文件复制进剪贴板", (not im2.isNull()) and im2.width() == 4,
      "%sx%s" % (im2.width(), im2.height()))

QGuiApplication.clipboard().clear()
win._img_copy(0, "data:image/png;base64,@@@notbase64@@@")
im3 = QGuiApplication.clipboard().image()
check("C3 坏数据不写剪贴板", im3.isNull(), "null=%s" % im3.isNull())

log("SUMMARY TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
os._exit(0)
