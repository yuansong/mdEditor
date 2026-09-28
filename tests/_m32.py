# -*- coding: utf-8 -*-
"""v3.30.3 诊断探针：复现「编辑后源码挤在一起」。
模拟典型编辑流程（表格编辑/合并/标注、图片图注、段落输入、代码块、引用内表格），
导出每一步之后 state.raw（源码视图将显示的内容），供人工审查排版问题。
仅诊断，不做 PASS/FAIL 判定（DONE 结尾 + 每步原始输出）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m32.txt")
out = []


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


def dump(tag):
    out.append("===== " + tag + " =====")
    for i, blk in enumerate(raw()):
        out.append(f"--- blk[{i}] ---")
        out.append(blk)
    flush()


wait(2500)

MD = ("# 标题一\n\n这是一段正文，包含 **加粗** 和 *斜体*。\n\n"
      "| 名称 | 数量 | 单价 |\n| --- | --- | --- |\n| 苹果 | 3 | 5.2 |\n| 香蕉 | 12 | 1.8 |\n\n"
      "```python\nprint('hello')\n```\n\n"
      "> 引用一行文字\n\n![图片](images/a.png)\n\n- 列表项甲\n- 列表项乙\n")
js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)
dump("初始载入")

# 1) 管道表格：合并第一行前两格（走 tblOp → HTML 存储）
dims = jj("(function(){var t=document.querySelector('.b-table table');"
          "return JSON.stringify({rows:t.tHead.rows.length+t.tBodies[0].rows.length,"
          "cols:t.tHead.rows[0].cells.length})})()")
js(f"window.__tblSelSet(0, 0, 0, 0, 1)")   # 表头 (0,0)-(0,1)
wait(200)
js("window.__tblOp('merge')")
wait(400)
dump("表头合并(0,0)-(0,1) 后")

# 2) 编辑数据格文字（同步 syncTableCells 路径，htable 存储）
js("(function(){var t=document.querySelector('.b-table table');"
   "var td=t.tBodies[0].rows[0].cells[2];td.focus();"
   "document.execCommand('selectAll',false,null);"
   "document.execCommand('insertText',false,'99');})()")
wait(300)
js("(function(){var t=document.querySelector('.b-table table');"
   "t.tBodies[0].rows[0].cells[2].blur();"
   "if(window.commitEdit)window.commitEdit();})()")
wait(400)
dump("编辑数据格 + blur 后")

# 3) 表格标注
js("window.__tblOp('caption')")
wait(200)
dump("加表格标注后（若弹出层需确认则保持默认）")

# 4) 段落输入（模拟 input 事件流）
js("(function(){var blks=document.querySelectorAll('#editor .blk');"
   "for(var i=0;i<blks.length;i++){if(blks[i].classList.contains('t-p')){"
   "var p=blks[i].querySelector('p');p.focus();"
   "document.execCommand('selectAll',false,null);"
   "document.execCommand('insertText',false,'替换后的第二段：含 中文、English 与 123。');"
   "break;}}})()")
wait(400)
dump("段落改写后")

# 5) 图片加图注 + 尺寸（figure 存储）
js("(function(){var fig=null;var imgs=document.querySelectorAll('#editor img');"
   "if(imgs.length){var b=imgs[0].closest('.blk');if(b)window.__setFig&&window.__setFig(b,"
   "{src:'images/a.png',alt:'图片',style:'width:320px',cap:'图注文字',captop:false});}})()")
wait(300)
r5 = js("window.getMarkdown()")
out.append("===== getMarkdown() 全文 ====="); out.append(r5 or "(null)"); flush()

# 6) 引用内插入表格
js("window.__tblOp&&window.__slashPick?null:null")
wait(100)
out.append("DONE")
flush()
print("done")
