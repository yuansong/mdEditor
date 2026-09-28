# -*- coding: utf-8 -*-
"""v3.29 诊断 N：图片块「编辑」链路排查。v3.30.17：操作入口由悬浮按钮条改为
图片右键菜单（图注 / 重置尺寸 / 存储项按存储方式动态显示）。
1) 选中图片 → 只出蓝框、无操作条；右键菜单项按存储状态动态；
2) 菜单「图注」→ 图注弹层 → 确认 → raw 升级 <figure> 且图注渲染；
3) 菜单「重置尺寸」→ raw 回退原生 Markdown 图片；
4) 右键菜单「图注」→ 弹层打开（二次预填 / 清空回退）；
5) 重命名弹层可开可关；
6) 全程 window.onerror 捕获 JS 异常。
（数据 URL 图片，避免触发 Python 落盘请求）"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29n.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def note(tag, extra):
    out.append(f"NOTE | {tag} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb); loop.exec(); return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def jj(code):
    r = js(code)
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


def raw():
    return jj("window.__raw()").get("raw") or [""]


IMG = ("![shot](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
       "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==)")


def img_menu(sel="#editor img"):
    """右键图片 → 返回 {sel, acts}（选中态 + 菜单 data-act 列表），菜单保持打开"""
    return jj("(function(){var img=document.querySelector('" + sel + "');"
              "if(!img)return JSON.stringify({sel:null});"
              "var r=img.getBoundingClientRect();"
              "img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
              "clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));"
              "var bm=document.getElementById('blkmenu');"
              "return JSON.stringify({sel:JSON.parse(window.__objSel()),"
              "bar:document.getElementById('objbar').classList.contains('show'),"
              "acts:[].map.call(bm.querySelectorAll('.mi'),function(x){return x.getAttribute('data-act')})})})()")


def img_menu_act(act, sel="#editor img"):
    """右键图片 → 点指定 data-act 项"""
    d = img_menu(sel)
    if d.get("acts") is None or act not in d.get("acts", []):
        return "noact:" + json.dumps(d.get("acts"))
    return js("(function(){var bm=document.getElementById('blkmenu');"
              "var it=[].filter.call(bm.querySelectorAll('.mi'),function(x){"
              "return x.getAttribute('data-act')==='" + act + "'})[0];"
              "it.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
              "it.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'ok'})()")


wait(2500)

# 挂全局错误捕获
js("window.__errs=[];window.onerror=function(m,s,l){window.__errs.push(String(m)+'@'+l);return false;}")
js(f"window.setMarkdown({json.dumps(IMG)})")
wait(700)

# ===== 0. 存储模式驱动菜单项显隐（v3.29b 语义 → v3.30.17 菜单化）=====
# 0a) 未保存文档（无 __docDir）+ 内嵌图 → 不显示「转化为相对路径存储」
d = img_menu()
note("0a acts (unsaved+embed)", str(d))
check("未保存文档 + 内嵌图 → 无存储类菜单项",
      d.get("sel", {}).get("kind") == "img" and "imgmode" not in d.get("acts", []), str(d))
js("(function(){document.body.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'x'})()")
wait(200)

# 0b) 未保存文档 + 本地相对路径图 → 无存储类菜单项
js(f"window.setMarkdown({json.dumps('![本地图](笔记.assets/00001_shot.png)')})")
wait(700)
d = img_menu()
note("0b acts (unsaved+local)", str(d))
check("未保存文档 + 本地图 → 无存储类菜单项",
      "imgmode" not in d.get("acts", []) and "imgrename" not in d.get("acts", []), str(d))
js("(function(){document.body.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'x'})()")
wait(200)

# 0c) 已保存文档（setDocDir）+ 内嵌图 → 显示「转化为相对路径存储」
js("window.setDocDir('C:\\\\temp\\\\md29n_probe')")
js(f"window.setMarkdown({json.dumps(IMG)})")
wait(700)
d = img_menu()
note("0c acts (saved+embed)", str(d))
check("已保存文档 + 内嵌图 → 显示「转化为相对路径存储」",
      "imgmode" in d.get("acts", []), str(d))
js("(function(){document.body.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'x'})()")
wait(200)

# ===== 1. 点击图片 → 只出蓝框，操作条不再浮现 =====
d = jj("(function(){var img=document.querySelector('#editor img');"
       "if(!img)return JSON.stringify({img:false});"
       "img.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
       "return JSON.stringify({img:true,sel:JSON.parse(window.__objSel()),"
       "bar:document.getElementById('objbar').classList.contains('show')})})()")
note("1 select", str(d))
check("点击图片 → 选中且不再浮现操作条（v3.30.17）",
      d.get("img") is True and d.get("sel", {}).get("kind") == "img" and d.get("bar") is False, str(d))

# ===== 2. 菜单「图注」→ 弹层 → 确认 =====
r = img_menu_act("edit")
wait(300)
d = jj("(function(){var cp=document.getElementById('cappop');"
       "return JSON.stringify({show:cp.classList.contains('show'),"
       "title:(document.getElementById('cappop-title')||{}).textContent||''})})()")
note("2 cappop", str(d))
check("菜单「图注」→ 图注弹层打开", r == "ok" and d.get("show") is True, str(r) + str(d))
# 填图注并确认
js("(function(){var i=document.getElementById('cap-input')||document.querySelector('#cappop input');"
   "i.value='这是图注';return 'v'})()")
# cap-input id 兜底：直接找 #cappop 内可见文本框
js("(function(){var cp=document.getElementById('cappop');"
   "var i=cp.querySelector('input[type=text],input:not([type])');"
   "if(i)i.value='这是图注';return 'v2'})()")
js("(function(){document.getElementById('cap-ok').click();return 'ok'})()")
wait(400)
r0 = str(raw()[0])
note("2 raw after cap", r0[:120])
d = jj("(function(){var f=document.querySelector('#editor figure');"
       "return JSON.stringify({fig:!!f,cap:f?(f.querySelector('figcaption')||{}).textContent:null})})()")
check("确认图注 → raw 升级 figure 且图注渲染",
      "figcaption" in r0 and d.get("fig") is True and d.get("cap") == "这是图注",
      str(d) + " | " + r0[:80])

# ===== 3. 重置尺寸（含移除图注回退原生）=====
r = img_menu_act("imgreset")
wait(400)
r1 = str(raw()[0])
note("3 raw after reset", r1[:120])
check("重置尺寸 → 保留图注（仅清尺寸样式）",
      r == "ok" and "figcaption" in r1 and "style=" not in r1, r1[:100])

# ===== 4. 右键菜单「图注」=====
d = img_menu()
note("4 blkmenu", str(d))
check("右键图片 → 菜单含「图注」(edit)",
      d.get("acts") is not None and "edit" in d.get("acts", []), str(d))
r = img_menu_act("edit")
wait(300)
d = jj("(function(){var cp=document.getElementById('cappop');"
       "return JSON.stringify({show:cp.classList.contains('show')})})()")
check("菜单「图注」→ 图注弹层打开", r == "ok" and d.get("show") is True, str(d))
# Esc 关闭弹层
js("(function(){var cp=document.getElementById('cappop');"
   "var i=cp.querySelector('input');"
   "i.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 'esc'})()")
wait(200)

# ===== 5. 本地路径图片：菜单含存储项；重命名弹层可开可关 =====
LOCAL = "![本地图](笔记.assets/00001_shot.png)"
js(f"window.setMarkdown({json.dumps(LOCAL)})")
wait(700)
d = img_menu()
note("5 local menu", str(d))
check("本地图片：菜单含存储类项（转内嵌 + 改名）",
      "imgmode" in d.get("acts", []) and "imgrename" in d.get("acts", []), str(d))
# 打开重命名弹层后取消（不触发 Python 落盘请求）
r = img_menu_act("imgrename")
wait(300)
d = jj("(function(){var rp=document.getElementById('renpop');"
       "return JSON.stringify({show:rp.classList.contains('show'),"
       "val:(document.getElementById('ren-input')||{}).value})})()")
note("5 renpop", str(d))
check("「修改图片名称」→ 弹层打开且预填当前名",
      r == "ok" and d.get("show") is True and "00001_shot" in str(d.get("val", "")), str(d))
js("(function(){document.getElementById('ren-cancel').click();return 'x'})()")
wait(200)

# ===== 6. 二次编辑图注：清空图注 → 回退原生 Markdown 图片 =====
js(f"window.setMarkdown({json.dumps(IMG)})")
wait(700)
img_menu_act("edit")
wait(300)
js("(function(){var i=document.getElementById('cap-input');i.value='第二版图注';"
   "document.getElementById('cap-ok').click();return 'ok'})()")
wait(400)
r = img_menu_act("edit")
wait(300)
d = jj("(function(){var i=document.getElementById('cap-input');"
       "return JSON.stringify({cur:i.value})})()")
check("二次编辑图注 → 弹层预填现有图注",
      r == "ok" and d.get("cur") == "第二版图注", str(d))
js("(function(){var i=document.getElementById('cap-input');i.value='';"
   "document.getElementById('cap-ok').click();return 'ok'})()")
wait(400)
r2 = str(raw()[0])
note("6 raw after cap cleared", r2[:120])
check("清空图注 → raw 回退原生 Markdown 图片",
      r2.startswith("![") and "figure" not in r2, r2[:100])

# ===== 7. 全程无 JS 异常 =====
d = jj("JSON.stringify(window.__errs||[])")
errs = d if isinstance(d, list) else d.get("_raw", "[]")
check("全程无 JS 异常", errs in ("[]", []) or str(errs) == "[]", str(errs))

out.append("DONE")
flush()
print("done")
