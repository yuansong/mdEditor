# -*- coding: utf-8 -*-
"""v3.29 探针：引用块三项改造。
1) 多行选中加粗不再并成一行（autoPair 跨行走 raw 改写）；
2) 空行末行回车 → 退出引用（连续两次回车）；
3) Tab / Shift+Tab 增减嵌套缩进；
4) 嵌套引用渲染为嵌套 blockquote 且输入后标记不丢；
5) 引用内嵌表格（.qblk）展示 + 原文往返。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29b.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
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
    try: return json.loads(r or "{}")
    except Exception: return {"_raw": r}


def raw():
    return jj("window.__raw()").get("raw") or [""]


wait(2500)

# ==================== 1) 多行选中加粗不并行 ====================
Q1 = "> 第一行内容\n> 第二行内容"
js(f"window.setMarkdown({json.dumps(Q1)})")
wait(700)
# 选中整个渲染态引用内容（跨行选区），按 '*' 触发自动配对包裹
js("(function(){var bq=document.querySelector('#editor blockquote');bq.focus();"
   "var sel=getSelection();var rg=document.createRange();"
   "rg.selectNodeContents(bq);sel.removeAllRanges();sel.addRange(rg);return 'sel'})()")
wait(200)
js("(function(){var bq=document.querySelector('#editor blockquote');"
   "bq.dispatchEvent(new KeyboardEvent('keydown',{key:'*',bubbles:true,cancelable:true}));return 'k'})()")
wait(400)
r = raw()[0]
check("跨行选中包符号 → 两行仍在（未并成一行）",
      r.count("\n") >= 1 and "第一行内容" in r and "第二行内容" in r, r[:160])
check("跨行选中包符号 → ** 已按 raw 偏移插入",
      r.count("*") == 2, r[:160])
# 行数保持 2 行
js("(function(){return window.__raw()})()")
lines1 = (r or "").split("\n")
check("加粗后仍为 2 行引用", len(lines1) == 2 and all(x.startswith(">") for x in lines1), str(lines1))

# ==================== 2) 连续两次回车退出引用 ====================
js(f"window.setMarkdown({json.dumps(Q1)})")
wait(700)
# 光标到引用末尾 → 回车（新增空行）→ 再回车（退出引用）。
# v3.29 实测：focus/选区与 dispatch 必须在同一个 js 调用里原子完成，
# 分步调用时选区会在 js 边界被干扰（addRange: range isn't in document）。
js("(function(){var bq=document.querySelector('#editor blockquote');bq.focus();"
   "var sel=getSelection();var rg=document.createRange();rg.selectNodeContents(bq);rg.collapse(false);"
   "sel.removeAllRanges();sel.addRange(rg);"
   "bq.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
   "return 'e1'})()")
wait(500)
r = raw()
check("第一次回车 → 引用内新增空行",
      len(r) > 0 and ("\n> \n" in (r[0] + "\n") or len(r[0].split('\n')) >= 3), r[0][:120])
js("(function(){var bq=document.querySelector('#editor blockquote');if(!bq)return 'nobq';"
   "bq.focus();var sel=getSelection();var rg=document.createRange();rg.selectNodeContents(bq);rg.collapse(false);"
   "sel.removeAllRanges();sel.addRange(rg);"
   "bq.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
   "return 'e2'})()")
wait(500)
r2 = raw()
inEdit = jj("(function(){return JSON.stringify({edit:!!document.querySelector('#editor .raw-edit')})})()")
check("第二次回车 → 退出引用（切回源码态编辑）",
      inEdit.get("edit") is True and len(r2) > 0 and r2[0].startswith("> 第一行") and r2[0].strip().count("\n") == 1, str(inEdit) + " | " + (r2[0] if r2 else "")[:120])

# ==================== 3) Tab / Shift+Tab 缩进 ====================
js(f"window.setMarkdown({json.dumps(Q1)})")
wait(700)
# 光标放第一行末尾 → Tab → 第一行加一层
js("(function(){var bq=document.querySelector('#editor blockquote');bq.focus();"
   "var tn=bq.firstChild;var sel=getSelection();var rg=document.createRange();"
   "var off=tn.textContent.indexOf('第一行内容') + 5;rg.setStart(tn, off);rg.collapse(true);"
   "sel.removeAllRanges();sel.addRange(rg);return 'c'})()")
wait(200)
js("(function(){document.querySelector('#editor blockquote')"
   ".dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));return 't'})()")
wait(500)
r = raw()[0]
check("Tab → 当前行加一层嵌套标记", "> > 第一行内容" in r and "> 第二行内容" in r, r[:160])
nest = jj("(function(){var bq=document.querySelector('#editor blockquote');"
          "return JSON.stringify({nested:!!(bq&&bq.querySelector('blockquote')),"
          "txt:(bq&&bq.querySelector('blockquote'))?bq.querySelector('blockquote').textContent:''})})()")
check("Tab → 渲染为嵌套 blockquote", nest.get("nested") is True and "第一行内容" in (nest.get("txt") or ""), str(nest))
# Shift+Tab → 还原
js("(function(){var bq=document.querySelector('#editor blockquote blockquote');if(!bq)return 'nonest';"
   "bq.focus();var tn=bq.firstChild;var sel=getSelection();var rg=document.createRange();"
   "rg.setStart(tn, Math.min(2, tn.length));rg.collapse(true);"
   "sel.removeAllRanges();sel.addRange(rg);"
   "bq.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true,shiftKey:true}));return 't'})()")
wait(500)
r = raw()[0]
check("Shift+Tab → 嵌套还原为一层", ("​> > 第一行内容" not in r) and "> 第一行内容" in r, r[:160])

# ==================== 4) 嵌套引用输入后标记不丢 ====================
Q4 = "> 外层\n> > 内层"
js(f"window.setMarkdown({json.dumps(Q4)})")
wait(700)
js("(function(){var bq=document.querySelector('#editor blockquote');bq.focus();"
   "var sel=getSelection();var rg=document.createRange();rg.selectNodeContents(bq);rg.collapse(false);"
   "sel.removeAllRanges();sel.addRange(rg);"
   "document.execCommand('insertText',false,'X');return 'x'})()")
wait(500)
r = raw()[0]
check("嵌套引用末尾输入 → 嵌套标记保留", "> 外层" in r and "> > 内层X" in r, r[:160])

# ==================== 5) 引用内嵌表格（.qblk）展示与往返 ====================
Q5 = "> 前文\n> | a | b |\n> | --- | --- |\n> | 1 | 2 |\n> 后文"
js(f"window.setMarkdown({json.dumps(Q5)})")
wait(700)
d5 = jj("(function(){var q=document.querySelector('#editor .b-quote .qblk');"
        "return JSON.stringify({qblk:!!q,table:!!(q&&q.querySelector('table')),"
        "editable:q?q.getAttribute('contenteditable'):null})})()")
check("引用内表格 → .qblk 展示且不可编辑",
      d5.get("qblk") is True and d5.get("table") is True and d5.get("editable") == "false", str(d5))
js("(function(){var bq=document.querySelector('#editor .b-quote blockquote');bq.focus();"
   "var sel=getSelection();var rg=document.createRange();rg.selectNodeContents(bq);rg.collapse(false);"
   "sel.removeAllRanges();sel.addRange(rg);"
   "document.execCommand('insertText',false,'X');return 'x'})()")
wait(500)
r = raw()[0]
check("引用内嵌表格输入后 → 表格行带 > 标记往返",
      "> | a | b |" in r and "> | 1 | 2 |" in r and "后文X" in r, r[:260])

out.append("DONE")
flush()
print("done")
