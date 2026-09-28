# -*- coding: utf-8 -*-
"""m57 验证探针（v3.30.11 公式优化 MATH-1/2/3/4/5/7）：
P0 纯 Python：MATH-2 exporters.parse_inline 行内 $..$ 降级（去 $、价格误判不触发）
S1 MATH-4 空公式占位：中间空 ```math 块 → .math-empty「空公式」可见（高度>0）
S2 MATH-4 点击空占位 → 源码框重新打开（可管理，不再是幽灵块）
S3 MATH-3 行内公式单击 → 切入源码态，光标落在 $...$ 内容内（段落）
S4 MATH-3 标题内行内公式单击 → 同样定位（raw 含 '# ' 前缀）
S5 MATH-7① 公式「插入示例」非空替换需二次确认（与图表同一标准）
S6 MATH-7② 公式源码框行数上限 14（长公式不再 10 行封顶）
S7 MATH-5 双击单元格公式 → #mathpop 弹层回写 data-tex（干净占位，无 katex 冗余）
S8 MATH-5 弹层留空提交 → 移除该公式
S9 MATH-1 getExportHTML 静态化：无 CDN / 无 script / katex 与 svg 已内联
S10 MATH-1 _inline_katex_css：占位替换为内嵌 css（woff2 data URI）
S11 MATH-1 无公式文档：不输出 __KATEX_CSS__ 占位
注意：js 返回对象必须 JSON.stringify（裸对象经 runJavaScript 回来是 ''）。
"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m57.txt")
out = []
PASS = 0
FAIL = 0


def log(s):
    out.append(str(s)); flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def ck(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; log(f"[PASS] {name} {detail}")
    else: FAIL += 1; log(f"[FAIL] {name} {detail}")


# ==================== P0: MATH-2（纯 Python，先于 GUI） ====================
import exporters
t1 = "".join(t.get("text", "") for t in exporters.parse_inline("值 $a^2+b^2$ 尾"))
ck("P0a 行内公式降级为去 $ 纯文本", t1 == "值 a^2+b^2 尾", repr(t1))
t2 = "".join((t.get("alt", "") if t.get("image") else t.get("text", ""))
             for t in exporters.parse_inline("价格 $5，再 $6 应保持原样"))
ck("P0b 价格文本不误判（$ 保留）", "$5" in t2 and "$6" in t2, repr(t2))
t3 = "".join(t.get("text", "") for t in exporters.parse_inline("码内 `$x$` 不动"))
ck("P0c 行内码内的 $ 原样保留（不被公式分支吞掉）", t3 == "码内 $x$ 不动", repr(t3))

# ==================== GUI ====================
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
    try: return json.loads(r if r not in (None, "") else "null")
    except Exception: return {"_raw": r}


wait(3000)
# G0 页面就绪守卫：js 通道可用后才继续（QWebEngine 偶发 GPU 初始化失败时
# _js_active 静默返回 None，后续断言会全部空转误报）
ready = None
for _ in range(20):
    ready = js("!!window.setMarkdown && !!window.cmd && !!window.__raw")
    if ready is True or ready == "true" or ready == 1:
        break
    wait(1000)
ck("G0 页面就绪（js 通道可用）", bool(ready) and ready != "false", repr(ready))


def setmd(md):
    js(f"window.setMarkdown({json.dumps(md)})")
    wait(700)


def raw0():
    d = jj("window.__raw()")
    if not isinstance(d, dict):
        return ""
    return "\n\n".join(d.get("raw") or [])


CLICK_MB = ("(function(){var mb=document.querySelector('#editor .mathblock');"
            "if(!mb)return 'nomb';"
            "var rc=mb.getBoundingClientRect();"
            "mb.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
            "clientX:rc.left+rc.width/2,clientY:rc.top+rc.height/2}));"
            "return 'ok';})()")

# ---------- S1/S2: MATH-4 空公式占位 ----------
setmd("段落甲\n\n```math\n\n```\n\n段落乙")
d = jj("(function(){var mb=document.querySelector('#editor .mathblock');"
       "if(!mb)return 'nomb';"
       "return JSON.stringify({empty:mb.classList.contains('math-empty'),"
       "txt:mb.textContent,h:mb.offsetHeight});})()")
ck("S1 空公式渲染「空公式」虚框占位", isinstance(d, dict) and d.get("empty") is True
   and d.get("txt") == "空公式" and (d.get("h") or 0) > 10,
   json.dumps(d, ensure_ascii=False) if isinstance(d, dict) else str(d))
d = jj("(function(){var mb=document.querySelector('#editor .mathblock');"
       "if(!mb)return 'nomb';"
       "var rc=mb.getBoundingClientRect();"
       "mb.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
       "clientX:rc.left+rc.width/2,clientY:rc.top+rc.height/2}));"
       "return 'ok';})()"); wait(500)
d = jj("JSON.stringify({ta:!!document.querySelector('.math-src')})")
ck("S2 点击空占位可重新打开源码框", isinstance(d, dict) and d.get("ta") is True, str(d))
js("(function(){var ta=document.querySelector('.math-src');"
   "if(ta)ta.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
   "return 1;})()"); wait(400)

# ---------- S3/S4: MATH-3 行内公式就地编辑 ----------
setmd("前文 $x^{2}+1$ 后文")
d = jj("(function(){var im=document.querySelector('#editor .inlinemath');"
       "if(!im)return 'noim';"
       "var rc=im.getBoundingClientRect();"
       "im.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
       "clientX:rc.left+2,clientY:rc.top+rc.height/2}));"
       "return 'ok';})()"); wait(500)
d = jj("(function(){var el=document.querySelector('#editor .raw-edit');"
       "if(!el)return 'noedit';"
       "var s=getSelection();var off=-1;"
       "if(s.rangeCount>0&&s.anchorNode&&s.anchorNode.nodeType===3)"
       "off=s.anchorOffset;"
       "var txt=el.textContent;var dl=txt.indexOf('$');"
       "return JSON.stringify({txt:txt,off:off,dollar:dl});})()")
ok3 = (isinstance(d, dict) and d.get("dollar", -1) >= 0 and
       (d.get("off") or -1) > d.get("dollar", -1))
ck("S3 行内公式单击切入源码态且光标在 $ 内容内", ok3,
   json.dumps(d, ensure_ascii=False) if isinstance(d, dict) else str(d))
setmd("## 标题 $y=2x$ 尾")
d = jj("(function(){var im=document.querySelector('#editor .inlinemath');"
       "if(!im)return 'noim';"
       "var rc=im.getBoundingClientRect();"
       "im.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
       "clientX:rc.left+2,clientY:rc.top+rc.height/2}));"
       "return 'ok';})()"); wait(500)
d = jj("(function(){var el=document.querySelector('#editor .raw-edit');"
       "return JSON.stringify({edit:!!el,txt:el?el.textContent:''});})()")
ck("S4 标题内行内公式同样定位（raw 保留 # 前缀）",
   isinstance(d, dict) and d.get("edit") is True and d.get("txt") == "## 标题 $y=2x$ 尾",
   json.dumps(d, ensure_ascii=False) if isinstance(d, dict) else str(d))
js("(function(){var el=document.querySelector('#editor .raw-edit');"
   "if(el){el.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));}"
   "return 1;})()"); wait(400)

# ---------- S5/S6: MATH-7① 示例二次确认 + ② 源码框行数 ----------
LONG_TEX = "\n".join(f"E_{{{i}}} = mc^{{{i}}}" for i in range(1, 16))
setmd("```math\n" + LONG_TEX + "\n```")
js(CLICK_MB); wait(500)
d = jj("(function(){var ta=document.querySelector('.math-src');"
       "if(!ta)return 'nota';"
       "return JSON.stringify({rows:ta.rows,lines:ta.value.split('\\n').length});})()")
ck("S6 长公式源码框行数上限放宽到 14",
   isinstance(d, dict) and d.get("rows") == 14 and (d.get("lines") or 0) >= 15,
   json.dumps(d, ensure_ascii=False) if isinstance(d, dict) else str(d))
d = jj("(function(){var ta=document.querySelector('.math-src');"
       "if(!ta)return 'nota';"
       "var before=ta.value;"
       "var btn=document.querySelector('.mmd-ex');"
       "if(!btn)return 'nobtn';"
       "btn.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
       "var armed=btn.textContent;"
       "var mid=ta.value;"
       "btn.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
       "return JSON.stringify({armed:armed,kept:mid===before,"
       "replaced:ta.value.indexOf('qquad')>=0,btnBack:btn.textContent});})()")
ck("S5 公式示例首点=确认态且不覆盖，再点=替换",
   isinstance(d, dict) and d.get("armed") == "再点一次确认替换" and
   d.get("kept") is True and d.get("replaced") is True and
   d.get("btnBack") == "插入示例",
   json.dumps(d, ensure_ascii=False) if isinstance(d, dict) else str(d))
js("(function(){var ta=document.querySelector('.math-src');"
   "if(ta)ta.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
   "return 1;})()"); wait(400)

# ---------- S7/S8: MATH-5 单元格公式编辑 ----------
HT = ('<table class="md-tbl"><thead><tr><th>公式</th></tr></thead>'
      '<tbody><tr><td><span class="cell-math" data-tex="x^{2}"></span></td></tr></tbody></table>')
setmd(HT)
d = jj("JSON.stringify({cm:!!document.querySelector('#editor .b-table .cell-math'),"
       "kx:!!document.querySelector('#editor .b-table .cell-math .katex')})")
ck("S7a cell-math 已由 KaTeX 渲染", isinstance(d, dict) and d.get("cm") is True
   and d.get("kx") is True, json.dumps(d, ensure_ascii=False) if isinstance(d, dict) else str(d))
js("(function(){var sp=document.querySelector('#editor .b-table .cell-math');"
   "if(!sp)return 'nosp';"
   "sp.dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true}));"
   "return 'ok';})()"); wait(500)
d = jj("(function(){var pop=document.getElementById('mathpop');"
       "var inp=document.getElementById('math-tex');"
       "return JSON.stringify({shown:!!(pop&&pop.classList.contains('show')),"
       "val:inp?inp.value:''});})()")
ck("S7b 双击弹出公式编辑层并带原 tex", isinstance(d, dict) and d.get("shown") is True
   and d.get("val") == "x^{2}", json.dumps(d, ensure_ascii=False) if isinstance(d, dict) else str(d))
js("(function(){var inp=document.getElementById('math-tex');"
   "inp.value='y^{3}+1';"
   "document.getElementById('math-ok').click();return 1;})()"); wait(800)
d = jj("(function(){var sp=document.querySelector('#editor .b-table .cell-math');"
       "return JSON.stringify({tex:sp?sp.getAttribute('data-tex'):'',"
       "kx:sp?!!sp.querySelector('.katex'):false});})()")
rw = raw0()
ck("S7c 确定后 data-tex 回写且重新渲染",
   isinstance(d, dict) and d.get("tex") == "y^{3}+1" and d.get("kx") is True,
   json.dumps(d, ensure_ascii=False) if isinstance(d, dict) else str(d))
ck("S7d 存储为干净占位（无 katex 渲染残留）",
   'data-tex="y^{3}+1"' in rw and "katex" not in rw, rw[:120])
js("(function(){var sp=document.querySelector('#editor .b-table .cell-math');"
   "if(!sp)return 'nosp';"
   "sp.dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true}));"
   "return 'ok';})()"); wait(500)
js("(function(){var inp=document.getElementById('math-tex');inp.value='';"
   "document.getElementById('math-ok').click();return 1;})()"); wait(800)
d = jj("JSON.stringify({cm:!!document.querySelector('#editor .b-table .cell-math')})")
rw = raw0()
ck("S8 留空提交 = 移除该公式", isinstance(d, dict) and d.get("cm") is False
   and "cell-math" not in rw, json.dumps(d) + " raw=" + rw[:100])

# ---------- S9/S10/S11: MATH-1 导出静态化 ----------
setmd("正文 $a^{2}$ 与公式：\n\n```math\nE=mc^2\n```\n\n```mermaid\nflowchart TD\n  A --> B\n```")
wait(1200)
h = js("window.getExportHTML()") or ""
ck("S9a 导出无 CDN 引用", "cdn.jsdelivr" not in h)
ck("S9b 导出零 script（全静态）", "<script" not in h)
ck("S9c 公式已静态内联（katex html）", 'class="katex"' in h)
ck("S9d 图表已静态内联（svg）", "<svg" in h)
ck("S9e 含 __KATEX_CSS__ 占位（有公式时）", "__KATEX_CSS__" in h)
h2 = win._inline_katex_css(h) or ""
ck("S10a 占位已替换为内嵌 katex css", "__KATEX_CSS__" not in h2 and "KaTeX" in h2)
ck("S10b 字体已内嵌为 woff2 data URI", "data:font/woff2;base64," in h2)
ck("S10c woff/ttf 字体外链分支已去除", ".woff)" not in h2 and ".ttf)" not in h2)
setmd("普通段落，无公式无图表")
h3 = js("window.getExportHTML()") or ""
ck("S11 无公式文档不输出 css 占位", "__KATEX_CSS__" not in h3 and "cdn.jsdelivr" not in h3)

log(f"SUMMARY PASS={PASS} FAIL={FAIL}")
log("DONE")
flush()
print(f"M57 DONE PASS={PASS} FAIL={FAIL}")
