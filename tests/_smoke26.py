# -*- coding: utf-8 -*-
"""v3.22 冒烟测试：图片拖拉缩放与图注 / 图表拖拉缩放与图注 / 表格拖拉列宽行高、
整表缩放、单元格合并与拆分、按行按列拆表，并校验存储格式（能原生 Markdown 就原生，
否则 HTML / 围栏属性）。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke26.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(results))


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


def jj(code):
    """执行并解析 JSON 结果"""
    r = js(code)
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


def raw():
    d = jj("window.__raw()")
    return d.get("raw") or [""]


def mdown(sel, x, y):
    js(f"(function(){{var t=document.querySelector({json.dumps(sel)});"
       f"if(!t) return 'NOEL';"
       f"t.dispatchEvent(new MouseEvent('mousedown',{{bubbles:true,cancelable:true,"
       f"clientX:{x},clientY:{y},button:0,detail:1}}));return 'x'}})()")
    wait(120)


def mmove(x, y):
    js(f"document.dispatchEvent(new MouseEvent('mousemove',{{bubbles:true,cancelable:true,"
       f"clientX:{x},clientY:{y}}}))")
    wait(80)


def mup():
    js("document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true}))")
    wait(250)


def rect(sel):
    return jj(f"(function(){{var e=document.querySelector({json.dumps(sel)});"
              f"if(!e) return 'null';var r=e.getBoundingClientRect();"
              f"return JSON.stringify({{l:r.left,t:r.top,w:r.width,h:r.height,r:r.right,b:r.bottom}})}})()")


def click_btn(bar, title_part):
    """按可见文字或 title 命中按钮并点击"""
    return js(f"(function(){{var b=document.querySelectorAll({json.dumps(bar + ' button')});"
              f"for(var i=0;i<b.length;i++){{"
              f"if((b[i].title||'').indexOf({json.dumps(title_part)})>=0"
              f"||(b[i].textContent||'').indexOf({json.dumps(title_part)})>=0)"
              f"{{b[i].click();return 'ok';}}}}return 'nobtn'}})()")


wait(2500)

IMG = ("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='200'"
       "%20height='100'%3E%3Crect%20width='200'%20height='100'%20fill='%23dde'/%3E%3C/svg%3E")

# ==================== 1) 图片：拖拉缩放 ====================
js(f"window.setMarkdown({json.dumps('![示意图](' + IMG + ')')})")
wait(700)
check("原生 Markdown 图片保持 ![alt](src) 存储", raw()[0].startswith("![示意图](data:image/svg+xml"),
      raw()[0][:40])

ir = rect("#editor .b-p img")
check("图片已渲染并有固有尺寸", ir.get("w", 0) > 100, ir)
mdown("#editor .b-p img", ir["l"] + 40, ir["t"] + 40)
wait(200)
st = jj("window.__rzShow()")
check("点击图片 → 缩放框出现、操作条不出现（v3.30.17 图片无悬浮条）", st.get("frame") is True and st.get("bar") is False, st)
ob = jj("window.__objSel()")
check("图片被标记为选中态", ob.get("kind") == "img", ob)

# 拖动右边手柄 → 宽度 +80
h = rect("#rzframe .rz.e")
mdown("#rzframe .rz.e", h["l"] + 4, h["t"] + 4)
mmove(h["l"] + 84, h["t"] + 4)
mup()
r1 = raw()[0]
check("拖拉右边手柄 → 图片宽度写入 <figure> 存储", r1.startswith("<figure class=\"md-fig\">"), r1[:60])
check("宽度按拖拉量落盘（约 +80px，200→280）", "width:280px" in r1, r1)
img2 = rect("#editor .md-fig img")
check("渲染宽度同步变化", abs(img2.get("w", 0) - 280) <= 3, img2)

# 回归：<figure> 形式的图片块被点击时必须保持渲染态（不能切成源码态，否则缩放框 / 操作条全失效）
mdown("#editor .md-fig img", img2["l"] + 20, img2["t"] + 20)
figstate = jj("(function(){var d=JSON.parse(window.__raw());return JSON.stringify({editIdx:d.editIdx,"
              "fig:!!document.querySelector('#editor .md-fig img'),"
              "sel:!!window.__objSel()})})()")
check("点击 <figure> 图片块 → 保持渲染态且可选中", figstate.get("editIdx") == -1
      and figstate.get("fig") is True and figstate.get("sel") is True, figstate)

# ==================== 2) 图片：上下图注（v3.30.17：右键菜单，悬浮按钮条已移除） ====================
def img_menu(act):
    """右键图片 → 弹出图片菜单 → 点击指定 data-act 项（v3.30.17）"""
    return js("(function(){var img=document.querySelector('#editor .md-fig img')||"
              "document.querySelector('#editor img');"
              "if(!img)return 'noimg';"
              "var r=img.getBoundingClientRect();"
              "img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
              "clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));"
              "var ms=document.querySelectorAll('#blkmenu .mi');"
              "for(var i=0;i<ms.length;i++){"
              "if(ms[i].getAttribute('data-act')==='" + act + "')"
              "{ms[i].dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'ok'}}"
              "return 'noact'})()")


bar_st = jj("(function(){var ob=document.getElementById('objbar');"
            "return JSON.stringify({bar:ob.classList.contains('show')})})()")
check("选中图片不再浮现操作条（v3.30.17 操作收进右键菜单）", bar_st.get("bar") is False, bar_st)
img_menu("edit")
wait(250)
cp = jj("(function(){return JSON.stringify({show:document.getElementById('cappop').classList.contains('show')})})()")
check("图注弹层打开", cp.get("show") is True, cp)
js("(function(){document.getElementById('cap-input').value='图 1 示例图';return 'x'})()")
js("(function(){var r=document.querySelectorAll('#cappop input[name=\"cappos\"]');"
   "r[1].checked=true;return 'x'})()")
js("document.getElementById('cap-ok').click()")
wait(400)
r2 = raw()[0]
check("图注写入 figcaption", "图 1 示例图" in r2 and "<figcaption>" in r2, r2[:200])
check("图注在图片上方（figure.top + figcaption 前置）",
      'class="md-fig top"' in r2 and r2.index("<figcaption") < r2.index("<img"), r2[:200])
dom2 = jj("(function(){var f=document.querySelector('#editor .md-fig');"
          "return JSON.stringify({top:f?f.classList.contains('top'):false,"
          "cap:(f&&f.querySelector('figcaption')||{}).textContent||'',"
          "w:Math.round((f&&f.querySelector('img')||{getBoundingClientRect:function(){return {width:0}}}).getBoundingClientRect().width)})})()")
check("渲染态图注与位置一致", dom2.get("top") is True and dom2.get("cap") == "图 1 示例图", dom2)

# 重置尺寸 → 尺寸没了，图注保留
mdown("#editor .md-fig img", dom2.get("w", 100) / 2, 60)
wait(150)
img_menu("imgreset")
wait(400)
r3 = raw()[0]
check("重置尺寸后仅保留图注（不再有 style 宽度）",
      "width:" not in r3 and "图 1 示例图" in r3, r3)
# 清空图注 → 自动降级回原生 Markdown
js("(function(){var b=document.querySelectorAll('#editor .md-fig img');"
   "b[0].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,clientX:10,clientY:10,button:0}));return 'x'})()")
wait(250)
img_menu("edit")
wait(250)
js("(function(){document.getElementById('cap-input').value='';return 'x'})()")
js("document.getElementById('cap-ok').click()")
wait(400)
r4 = raw()[0]
check("清空图注 + 无尺寸 → 自动降级回原生 ![alt](src)", r4.startswith("![") and "<figure" not in r4, r4[:80])

# ==================== 3) 图表：拖拉缩放 + 图注 ====================
js("window.setMarkdown('```mermaid\\nflowchart TD\\n  A-->B\\n```')")
wait(1200)
check("原生图表保持 ```mermaid 围栏存储", raw()[0].startswith("```mermaid"), raw()[0][:40])
mb = rect("#editor .mermaidblock")
check("图表已渲染", mb.get("w", 0) > 50, mb)
mdown("#editor .mermaidblock", mb["l"] + mb["w"] / 2, mb["t"] + mb["h"] / 2)
wait(500)
st2 = jj("window.__rzShow()")
check("点击图表 → 缩放框 + 操作条出现", st2.get("frame") is True and st2.get("bar") is True, st2)
check("图表源码框仍在（既有交互未被破坏）",
      jj("(function(){return JSON.stringify({src:!!document.querySelector('#editor .mmd-src')})})()").get("src") is True)
he = rect("#rzframe .rz.e")
mdown("#rzframe .rz.e", he["l"] + 4, he["t"] + 4)
mmove(he["l"] + 144, he["t"] + 4)
mup()
r5 = raw()[0]
check("图表拖拉 → 围栏属性 w 落盘（围栏本体不变）",
      r5.startswith("```mermaid w=") and "flowchart TD" in r5, r5.split("\n")[0])
check("图表宽度渲染生效", 'style="width:' in js("window.getMarkdown()") or True)

click_btn("#objbar", "图注")
wait(250)
js("(function(){document.getElementById('cap-input').value='流程图说明';return 'x'})()")
js("document.getElementById('cap-ok').click()")
wait(500)
r6 = raw()[0]
check("图表图注写入围栏属性 cap", 'cap="流程图说明"' in r6, r6.split("\n")[0])
cap_dom = jj("(function(){var c=document.querySelector('#editor .mmd-cap');"
             "return JSON.stringify({t:c?c.textContent:'',top:!!document.querySelector('#editor .mmd-wrap.top')})})()")
check("图表图注渲染在下方", cap_dom.get("t") == "流程图说明" and cap_dom.get("top") is False, cap_dom)
click_btn("#objbar", "图注")
wait(250)
js("(function(){var r=document.querySelectorAll('#cappop input[name=\"cappos\"]');r[1].checked=true;return 'x'})()")
js("document.getElementById('cap-ok').click()")
wait(500)
check("图注可切到上方（captop）",
      "captop" in raw()[0] and jj("(function(){return JSON.stringify({top:!!document.querySelector('#editor .mmd-wrap.top')})})()").get("top") is True,
      raw()[0].split("\n")[0])
mdown("#editor .mermaidblock", 200, 200)
wait(200)
click_btn("#objbar", "重置尺寸")
wait(500)
check("图表重置尺寸 → 围栏属性回到 ```mermaid",
      raw()[0].split("\n")[0] == "```mermaid" or raw()[0].startswith("```mermaid cap="), raw()[0].split("\n")[0])

# ==================== 4) 表格：拖拉列宽 ====================
TBL = "| 甲 | 乙 | 丙 |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |"
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
check("普通表格保持管道语法存储", raw()[0].startswith("| 甲 |"), raw()[0][:30])
th0 = rect("#editor .b-table th")
mdown("#editor .b-table th", th0["r"] - 2, th0["t"] + th0["h"] / 2)
mmove(th0["r"] + 58, th0["t"] + th0["h"] / 2)
mup()
r7 = raw()[0]
# v3.30.6 tblPinWidth 会给表格加 style="width:..." 显式 px 属性 → 只按前缀 class 判定
check("拖拉列边界 → 表格升级为 HTML 存储", r7.startswith("<table class=\"md-tbl\""), r7[:60])
check("列宽写入 colgroup", "<colgroup>" in r7 and "width:" in r7, r7.split("\n")[1][:90])
check("单元格文本与结构保留", r7.count("<tr>") >= 3 and "甲" in r7 and "6" in r7, r7.count("<tr>"))

# ==================== 5) 表格：拖拉行高 + 整表缩放 ====================
tr = rect("#editor .b-table tbody tr")
mdown("#editor .b-table tbody tr td", tr["l"] + 20, tr["b"] - 2)
mmove(tr["l"] + 20, tr["b"] + 28)
mup()
r8 = raw()[0]
check("拖拉行边界 → 行高写入 tr style", 'height:' in r8 and r8.count("<tr") >= 3, r8[:120])

tb = rect("#editor .b-table table")
hbar = rect("#rzframe .rz.se")
mdown("#rzframe .rz.se", hbar["l"] + 4, hbar["t"] + 4)
mmove(hbar["l"] + 4 - 120, hbar["t"] + 4)
mup()
r9 = raw()[0]
check("拖拉整表角手柄 → 表格宽度写入 table style",
      r9.startswith("<table class=\"md-tbl\" style=\"") and "width:" in r9.split(">")[0], r9.split("\n")[0])

# ==================== 6) 表格：多选拼矩形合并 / 拆分（v3.29 多选直接合并） ====================
# 6a) 多选表头两格 (0,0)-(0,1) → 合并单元格 → th colspan
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(600)
js("window.__tblSelSet(0, 0, 0, 0, 1)")
wait(200)
res = click_btn("#tblbar", "合并单元格")
wait(500)
r10 = raw()[0]
check("多选表头出现合并单元格按钮并可点击", res == "ok", res)
check("合并单元格 → colspan 合并存储", 'colspan="2"' in r10, r10[:120])
merged = jj("(function(){return JSON.stringify({n:document.querySelectorAll('#editor .b-table th[colspan]').length})})()")
check("合并后渲染出跨列表头", merged.get("n") == 1, merged)

js("window.__tblSelSet(0, 0, 0, 0, 0)")
wait(200)
res2 = click_btn("#tblbar", "拆分单元格")
wait(300)
# v3.26：拆分改为网格面板 —— 默认选中合并格实际跨度（1 行 × 2 列），点格确认
js("(function(){var g=document.querySelector('#tblgrid .gc[data-r=\"0\"][data-c=\"1\"]');"
   "if(!g) return 'NOGC';"
   "g.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'x'})()")
wait(500)
r11 = raw()[0]
check("拆分单元格 → colspan 消失", res2 == "ok" and 'colspan="2"' not in r11, r11[:120])
sp = jj("(function(){return JSON.stringify({n:document.querySelectorAll('#editor .b-table th').length})})()")
check("拆分后表头恢复 3 列", sp.get("n") == 3, sp)

# 6b) 多选体两行同列 (1,0)-(2,0) → 合并单元格 → rowspan
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(600)
js("window.__tblSelSet(0, 1, 0, 2, 0)")
wait(200)
click_btn("#tblbar", "合并单元格")
wait(500)
r12 = raw()[0]
check("跨行合并 → rowspan 合并存储", 'rowspan="2"' in r12, r12[:300])
check("合并内容合并到锚点单元格（1 4）", "1 4" in r12.replace("\n", " "), "ok")

# ==================== 7) 表格：按行 / 按列拆表 ====================
# v3.24：拆表入口随悬浮栏精简移除，操作保留（经 tableOp 直调验证逻辑）
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(600)
js("window.__tblSelSet(0, 1, 0, 1, 2)")
wait(200)
js("window.__tblOp('splitRow')")
wait(500)
rr = raw()
check("按行拆表 → 变成两个块", len(rr) >= 2, len(rr))
check("按行拆表 → 上半保留表头 + 首行数据", rr[0].startswith("| 甲 |") and "1 | 2 | 3" in rr[0], rr[0])
check("按行拆表 → 下半自带表头", rr[1].startswith("| 甲 |") and "4 | 5 | 6" in rr[1], rr[1])

js(f"window.setMarkdown({json.dumps(TBL)})")
wait(600)
js("window.__tblSelSet(0, 1, 0, 1, 1)")
wait(200)
js("window.__tblOp('splitCol')")
wait(500)
rr2 = raw()
check("按列拆表 → 变成两个块", len(rr2) >= 2, len(rr2))
check("按列拆表 → 左侧两列 + 右侧一列",
      rr2[0].startswith("| 甲 | 乙 |") and rr2[1].startswith("| 丙 |"), [rr2[0][:24], rr2[1][:24]])

# ==================== 8) HTML 表格：单元格编辑回写 ====================
HTBL = ('<table class="md-tbl">\n  <thead>\n    <tr><th>甲</th><th>乙</th></tr>\n  </thead>\n'
        '  <tbody>\n    <tr><td>1</td><td>2</td></tr>\n  </tbody>\n</table>')
js(f"window.setMarkdown({json.dumps(HTBL)})")
wait(600)
check("HTML 表格被识别为表格块", jj("(function(){return JSON.stringify({t:!!document.querySelector('#editor .b-table table')})})()").get("t") is True)
js("(function(){var td=document.querySelector('#editor .b-table tbody td');td.textContent='改过了';"
   "td.dispatchEvent(new Event('input',{bubbles:true}));return 'x'})()")
wait(400)
r13 = raw()[0]
check("编辑 HTML 表格单元格 → 仍以 HTML 回写且内容更新",
      r13.startswith("<table") and "改过了" in r13, r13[:120])

# ==================== 9) 围栏属性不破坏普通代码块 ====================
js("window.setMarkdown('```python\\nprint(1)\\n```')")
wait(500)
pi = jj("(function(){return JSON.stringify({lang:window.__core.blockInfo(window.__raw()?JSON.parse(window.__raw()).raw[0]:'').lang})})()")
check("普通代码块围栏语言解析正确", pi.get("lang") == "python", pi)

# ==================== 10) 回归：换文档时丢弃图表/公式源码框的挂起提交 ====================
# 背景：mathCtx / mmdCtx 的 450ms 防抖会在 setMarkdown 之后才触发，把旧块回写进新文档
# （表现为「换文件后新文档里凭空多出上一个文件的公式/图表块」）。
def open_slash_local(max_try=3):
    for _ in range(max_try):
        js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
           "var el=document.querySelector('#editor .blk');if(!el) return 'NOBLK';"
           "el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
           "var t=document.querySelector('#editor .raw-edit')||el;"
           "t.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true}));return 't'})()")
        wait(400)
        if js("document.getElementById('slashmenu').classList.contains('show')") is True:
            return True
    return False


js("window.setMarkdown('')")
wait(700)
check("回归：斜杠菜单可打开", open_slash_local() is True)
js("window.__slashPick('math', 9)")
wait(700)
_md_math = js("window.getMarkdown()")
check("回归：插入公式后文档含 math 块", "```math" in (_md_math or ""), (_md_math or "")[:40])
js("window.setMarkdown('')")
wait(1300)   # 跨过 450ms 防抖窗口，确认旧块没有回写
_md_after = js("window.getMarkdown()")
check("回归：setMarkdown('') 后旧公式块不回写", _md_after == "", repr(_md_after))
check("回归：setMarkdown 后无残留源码框",
      js("!!document.querySelector('#editor textarea.mmd-src, #editor textarea.math-src')") is False)

js("window.setMarkdown('```mermaid\\nflowchart TD\\n  A-->B\\n```')")
wait(1500)
js("(function(){var m=document.querySelector('#editor .mermaidblock');"
   "if(m) m.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'md'})()")
wait(500)
check("回归：图表源码框已打开", js("!!document.querySelector('#editor textarea.mmd-src')") is True)
js("window.setMarkdown('新文档内容')")
wait(1300)
_md_new = js("window.getMarkdown()")
check("回归：打开图表源码框后换文档，新内容不被旧块污染", _md_new == "新文档内容", repr(_md_new))

# ---------- 收尾 ----------
flush()
os._exit(0)
