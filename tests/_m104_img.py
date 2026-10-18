# -*- coding: utf-8 -*-
"""m104 图片（image）模块操作规范实证：渲染 / 选中 / 浮层 / 右键菜单 / 尺寸 / 图注 / 块操作

用户要求（2026-10-01）：按引用、代码块、列表相同方式排查图片模块 ——
 1) 插入与创建  2) 渲染与选中  3) 尺寸调整  4) 图注  5) 对齐
 6) 复制 / 移动 / 删除  7) 源码 / 双屏模式  8) 常见故障（粘贴、拖入、同步、导出、性能）
衔接：IMG-1~9（v3.30.16/17/19、v3.31.3 已修）
版本：src v3.37（2026-10-01 08:36:05 及之后的快照）
结果：tests/_m104_img.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m104_img.txt")
out = []
FAIL = [0]
TOTAL = [0]
ABN = []


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


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code, timeout=15000):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(timeout, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def jj(code):
    r = js(code)
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


wait(2800)
note("boot hooks=%s" % js("JSON.stringify({sm:typeof window.setMarkdown,rw:typeof window.__raw,"
                          "rz:typeof window.__rzShow,obj:typeof window.__objPick,"
                          "iv:typeof window.__imgView,cp:typeof window.__imgCopy,"
                          "st:typeof window.__imgStatusLabel})"))

PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE"
       "hQGAhKmMIQAAAABJRU5ErkJggg==")
NET = "https://example.com/pic.png"


def rawof():
    try:
        return (json.loads(js("window.__raw()") or "{}").get("raw")) or []
    except Exception:
        return []


def setmd(md, ms=780):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def istate():
    return jj("(function(){var im=document.querySelector('#editor img');"
              "var fig=document.querySelector('#editor figure');"
              "var cap=document.querySelector('#editor figcaption');"
              "var OB=document.getElementById('objbar');"
              "var RZ=document.getElementById('rzframe');"
              "return JSON.stringify({"
              "hasImg:!!im,src:im?(im.getAttribute('src')||'').slice(0,40):'',"
              "imgStyle:im?(im.getAttribute('style')||''):'',"
              "sel:im?im.classList.contains('sel'):null,"
              "broken:im?im.classList.contains('img-broken'):null,"
              "hasFig:!!fig,figCls:fig?fig.className:'',"
              "cap:cap?(cap.textContent||''):'',"
              "brokenTip:(document.querySelector('.img-broken-tip')||{}).textContent||'',"
              "objbarShow:OB?OB.classList.contains('show'):null,"
              "objbarTxt:OB?OB.textContent:'',"
              "rzShow:RZ?(RZ.style.display!=='none'&&RZ.classList.contains('show')):null,"
              "nblk:document.querySelectorAll('#editor .blk').length,"
              "raw:(function(){try{return JSON.parse(window.__raw()||'{}').raw||[]}catch(e){return []}})()"
              "})})()")


def click_img():
    return js("(function(){var im=document.querySelector('#editor img');"
              "if(!im)return 'no-img';"
              "im.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0}));"
              "return 'ok'})()")


def open_blkmenu_via_handle():
    # IMG-13 回归改走右键路径：块手柄绑定 mousedown 且依赖真实 hover 定位 handleIdx，
    # 合成事件无法 hover 会把菜单开到陈旧块上（正文段落）；右键图片是产品主路径
    js("(function(){var im=document.querySelector('#editor img');if(!im)return 'no-img';"
       "var r=im.getBoundingClientRect();"
       "im.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
       "clientX:r.left+2,clientY:r.top+2}));return 'ok'})()")
    wait(560)


def mi_list():
    return jj("(function(){var BM=document.getElementById('blkmenu');"
              "if(!BM)return JSON.stringify({no:1});"
              "return JSON.stringify({show:BM.classList.contains('show'),"
              "cap:(BM.querySelector('.cap')||{}).textContent||'',"
              "items:[].slice.call(BM.querySelectorAll('.mi')).map(function(m){"
              "return m.getAttribute('data-act')+'|'+m.textContent.trim()})})})()")


def mi_click(act):
    js("(function(){var BM=document.getElementById('blkmenu');"
       "var it=BM&&BM.querySelector('.mi[data-act=\"" + act + "\"]');"
       "if(!it)return 'no-item';"
       "it.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(620)


note("========== A 组：渲染形态与块型识别 ==========")
setmd("前段\n\n![图甲](" + PNG + ")\n\n尾段")
s = istate()
check("A1 原生 Markdown 图片渲染为 img（src 保留）",
      s.get("hasImg") is True and str(s.get("src")).startswith("data:image/png"),
      "inf=%s" % json.dumps({k: s.get(k) for k in ("hasImg", "src", "nblk")}, ensure_ascii=False))
open_blkmenu_via_handle()
bm = mi_list()
note("  图片块菜单=%s" % json.dumps(bm, ensure_ascii=False)[:300])
check("A2 块菜单识别为「图片块」（走特殊块分支）",
      "图片块" in str(bm.get("cap", "")), "cap=%s" % bm.get("cap"))

setmd('<figure class="md-fig">\n<img src="' + PNG + '" alt="图乙" style="width:120px">\n'
      '<figcaption>图注甲</figcaption>\n</figure>')
s = istate()
check("A3 figure 形态渲染：尺寸 + 图注均生效",
      s.get("hasFig") is True and "width:120px" in str(s.get("imgStyle")) and s.get("cap") == "图注甲",
      "inf=%s" % json.dumps({k: s.get(k) for k in ("hasFig", "figCls", "imgStyle", "cap")}, ensure_ascii=False))

setmd("![缺失图](nonexistent-file-xyz.png)")
wait(700)
s = istate()
note("  A4 失败图：broken=%s tip=%s" % (s.get("broken"), str(s.get("brokenTip"))[:80]))
check("A4 图片加载失败 → 显示失败占位（含路径提示）",
      s.get("broken") is True and "nonexistent-file-xyz.png" in str(s.get("brokenTip")),
      "broken=%s tip=%s" % (s.get("broken"), str(s.get("brokenTip"))[:80]))

note("========== B 组：选中与浮层 ==========")
setmd("前段\n\n![图甲](" + PNG + ")\n\n尾段")
click_img()
wait(420)
s = istate()
note("  B1 点击后 sel=%s rzShow=%s objbarShow=%s objbarTxt=%s" %
     (s.get("sel"), s.get("rzShow"), s.get("objbarShow"), s.get("objbarTxt")))
check("B1 点击图片 → 进入选中态（蓝框 + 缩放框）",
      s.get("sel") is True and s.get("rzShow") is True,
      "sel=%s rz=%s" % (s.get("sel"), s.get("rzShow")))
check("B2 图片选中不弹对象操作条（操作收在右键菜单，与图表不同）",
      s.get("objbarShow") is False, "objbarShow=%s txt=%s" % (s.get("objbarShow"), s.get("objbarTxt")))

js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
wait(420)
s = istate()
check("B3 Esc → 取消选中（缩放框收起、内容不变）",
      s.get("sel") is False and s.get("nblk") == 3, "sel=%s nblk=%s" % (s.get("sel"), s.get("nblk")))

click_img()
wait(420)
js("(function(){var b=document.querySelector('#editor .blk');"
   "if(!b)return 'no';b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,button:0}));return 'ok'})()")
wait(420)
s = istate()
check("B4 点击其它块 → 取消选中", s.get("sel") is False, "sel=%s" % s.get("sel"))

click_img()
wait(420)
nb0 = istate().get("nblk")
js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true}))")
wait(520)
s = istate()
check("B5 选中后 Delete → 删除整块", s.get("nblk") == nb0 - 1,
      "before=%s after=%s raw=%s" % (nb0, s.get("nblk"), json.dumps(s.get("raw"), ensure_ascii=False)[:120]))

note("========== C 组：右键 / 块菜单操作 ==========")
setmd("![图甲](" + PNG + ")")
click_img()
wait(360)
open_blkmenu_via_handle()
bm = mi_list()
acts = [str(x).split("|")[0] for x in bm.get("items", [])]
labels = [str(x) for x in bm.get("items", [])]
note("  图片菜单项=%s" % json.dumps(labels, ensure_ascii=False))
# v3.39.5（MENU-4）：恢复「省略当前状态项」——默认居中 → 无 imgalign:c
for need in ("edit", "imgreset", "imgsize", "imgalign:l", "imgalign:r",
             "imgreplace", "viewimg", "copyimg", "dup", "up", "down", "del"):
    check("C1 菜单含 %s" % need, need in acts, "acts=%s" % json.dumps(acts))
check("C1b 当前项省略（默认居中无 imgalign:c）", "imgalign:c" not in acts,
      "acts=%s" % json.dumps(acts))

mi_click("imgalign:l")
g = rawof()
s = istate()
check("C2 靠左 → figure class 含 fig-l 并写入存储",
      (g and "fig-l" in str(g[0])) or "fig-l" in str(s.get("figCls")),
      "raw=%s cls=%s" % (json.dumps(g, ensure_ascii=False)[:160], s.get("figCls")))

setmd("![图甲](" + PNG + ")")
click_img()
wait(360)
open_blkmenu_via_handle()
mi_click("edit")
wait(480)
cp = jj("(function(){var CP=document.getElementById('cappop');"
        "var inp=CP?CP.querySelector('input'):null;"
        "return JSON.stringify({show:CP?CP.classList.contains('show'):null,"
        "hasInput:!!inp,title:(document.getElementById('cappop-title')||{}).textContent||''})})()")
note("  C3 图注弹层=%s" % json.dumps(cp, ensure_ascii=False))
js("(function(){var CP=document.getElementById('cappop');"
   "var inp=CP?CP.querySelector('input'):null;if(!inp)return 'no-input';"
   "inp.value='新图注甲';inp.dispatchEvent(new Event('input',{bubbles:true}));return 'ok'})()")
wait(240)
js("(function(){var b=document.getElementById('cap-ok');"
   "if(!b)return 'no-ok';b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(620)
g = rawof()
s = istate()
check("C3 图注写入 → raw 含 figcaption 且渲染可见",
      (g and "新图注甲" in str(g[0])) and s.get("cap") == "新图注甲",
      "raw=%s cap=%s" % (json.dumps(g, ensure_ascii=False)[:200], s.get("cap")))

note("========== D 组：尺寸设置与重置 ==========")
setmd("![图甲](" + PNG + ")")
click_img()
wait(360)
open_blkmenu_via_handle()
mi_click("imgsize")
wait(480)
js("(function(){var w=document.getElementById('imgsize-w');if(!w)return 'no-w';"
   "w.value='180';w.dispatchEvent(new Event('input',{bubbles:true}));"
   "var p=document.getElementById('imgsizepop');"
   "p.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return 'ok'})()")
wait(620)
g = rawof()
s = istate()
check("D1 大小设置只填宽 → 写入 width（等比）",
      g and "width:180px" in str(g[0]), "raw=%s" % json.dumps(g, ensure_ascii=False)[:200])

js("(function(){var w=document.getElementById('imgsize-w'),h=document.getElementById('imgsize-h');"
   "return JSON.stringify({w:!!w,h:!!h})})()")
setmd("![图甲](" + PNG + ")")
click_img()
wait(360)
open_blkmenu_via_handle()
mi_click("imgsize")
wait(480)
js("(function(){var w=document.getElementById('imgsize-w'),h=document.getElementById('imgsize-h');"
   "if(!w||!h)return 'no';w.value='180';h.value='90';"
   "w.dispatchEvent(new Event('input',{bubbles:true}));h.dispatchEvent(new Event('input',{bubbles:true}));"
   "document.getElementById('imgsizepop').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return 'ok'})()")
wait(620)
g = rawof()
check("D2 两维都填 → width + height 同时写入",
      g and "width:180px" in str(g[0]) and "height:90px" in str(g[0]),
      "raw=%s" % json.dumps(g, ensure_ascii=False)[:200])

setmd("![图甲](" + PNG + ")")
click_img()
wait(360)
open_blkmenu_via_handle()
mi_click("imgreset")
wait(620)
g = rawof()
s = istate()
check("D3 重置尺寸 → 无增强属性时回退为原生 Markdown 图片",
      g and str(g[0]).startswith("![") and "figure" not in str(g[0]).lower(),
      "raw=%s" % json.dumps(g, ensure_ascii=False)[:200])

note("========== E 组：块操作（复制 / 移动 / 删除 / 预览 / 复制图片） ==========")
setmd("前段\n\n![图甲](" + PNG + ")\n\n尾段")
click_img()
wait(360)
open_blkmenu_via_handle()
mi_click("dup")
wait(620)
g = rawof()
check("E1 复制块 → 文档内多一份图片块", len(g) == 4 and g[1] == g[2],
      "raw=%s" % json.dumps([x[:30] for x in g], ensure_ascii=False))

setmd("![图甲](" + PNG + ")\n\n尾段")
click_img()
wait(360)
open_blkmenu_via_handle()
bm = mi_list()
dis = jj("(function(){var BM=document.getElementById('blkmenu');"
         "var up=BM.querySelector('.mi[data-act=\"up\"]');"
         "return JSON.stringify({upDis:up?up.classList.contains('dis'):null})})()")
note("  E2 首块上移按钮态=%s" % json.dumps(dis))
check("E2 首块「上移」置灰（边界提示生效）", dis.get("upDis") is True, "dis=%s" % json.dumps(dis))

setmd("前段\n\n![图甲](" + PNG + ")")
click_img()
wait(360)
open_blkmenu_via_handle()
mi_click("del")
wait(620)
g = rawof()
check("E3 删除块 → 图片块移除、其余内容保留",
      len(g) == 1 and g[0] == "前段", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("![图甲](" + PNG + ")")
iv = jj("window.__imgViewOpen(0)")
note("  E4 大图预览=%s" % json.dumps(iv, ensure_ascii=False))
check("E4 「显示图片」→ 应用内大图预览打开", iv.get("show") is True, "iv=%s" % json.dumps(iv))
js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
wait(360)
iv2 = jj("window.__imgView()")
check("E4b Esc 关闭大图预览", iv2.get("show") is False, "iv=%s" % json.dumps(iv2))

cp = jj("window.__imgCopy(0)")
note("  E5 复制图片=%s" % json.dumps(cp, ensure_ascii=False))
check("E5 「复制图片」→ 触发剪贴板请求（act 带出）",
      str(cp.get("act")) not in ("null", "None", ""), "cp=%s" % json.dumps(cp))

note("========== F 组：存储方式与网络图片 ==========")
setmd("![图甲](" + PNG + ")")
st = js("window.__imgStatusLabel(0)")
note("  F1 内嵌图片状态文案=%s" % json.dumps(st, ensure_ascii=False))
setmd("![网络图](" + NET + ")")
click_img()
wait(360)
open_blkmenu_via_handle()
bm = mi_list()
labels = [str(x) for x in bm.get("items", [])]
note("  F2 网络图片菜单项=%s" % json.dumps(labels, ensure_ascii=False))
# IMG-13（v3.38）：存储项统一为「转本地存储」（imglocalall，仅网络图片显示）
check("F2 网络图片菜单出现「转本地存储」",
      any("转本地存储" in x for x in labels), "items=%s" % json.dumps(labels, ensure_ascii=False))
st2 = js("window.__imgStatusLabel(0)")
note("  F2b 网络图片状态文案=%s" % json.dumps(st2, ensure_ascii=False))

note("========== G 组：图片在单元格内 ==========")
setmd("| A | B |\n| --- | --- |\n| ![](" + PNG + ") | 文字 |")
wait(620)
s = jj("(function(){var im=document.querySelector('#editor td img');"
       "return JSON.stringify({hasCellImg:!!im,"
       "sel:im?im.classList.contains('sel'):null})})()")
note("  G1 单元格内图片=%s" % json.dumps(s, ensure_ascii=False))
js("(function(){var im=document.querySelector('#editor td img');"
   "if(!im)return 'no';im.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0}));return 'ok'})()")
wait(420)
s2 = jj("(function(){var im=document.querySelector('#editor td img');"
        "var RZ=document.getElementById('rzframe');"
        "return JSON.stringify({sel:im?im.classList.contains('sel'):null,"
        "rz:RZ?(RZ.classList.contains('show')):null})})()")
note("  G2 点击单元格内图片后=%s" % json.dumps(s2, ensure_ascii=False))
check("G2 单元格内图片可渲染（选中态为观察项）", s.get("hasCellImg") is True,
      "inf=%s" % json.dumps(s, ensure_ascii=False))

log("")
log("========== 汇总：%d 断言，FAIL %d ==========" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
