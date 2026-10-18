# -*- coding: utf-8 -*-
"""v3.30.3 探针：粘贴为 Markdown（修「粘贴后整块挤成一行」+ X2）。
A) htmlToMd 单元：标题/行内标记/链接图片/嵌套列表/引用/围栏/表格/HR/任务框；
B) 渲染态粘贴上下文：标题拆块、列表项并入、代码区保留换行、单元格压单行、
   引用行模型；raw-edit 粘贴富文本转 Markdown；纯文本多行拆块回归。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m33.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + " | " + name + (" | " + str(extra) if extra else ""))
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


def check_js():
    d = jj("(function(){return JSON.stringify({err: window.__jsErrors || null})})()")
    return d.get("err")


wait(2500)

# ---------- A) htmlToMd 单元测试 ----------
H2M = [
    ("<h1>大标题</h1><p>正文一段</p>", "# 大标题\n\n正文一段"),
    ("<p><b>粗</b><i>斜</i><s>删</s><code>码</code></p>", "**粗***斜*~~删~~`码`"),
    ("<p>看<a href='https://a.b'>链接</a>和<img src='x.png' alt='图'></p>",
     "看[链接](https://a.b)和![图](x.png)"),
    ("<ul><li>甲<ul><li>甲1</li></ul></li><li>乙</li></ul>", "- 甲\n  - 甲1\n- 乙"),
    ("<ol><li>一</li><li>二</li></ol>", "1. 一\n2. 二"),
    ("<blockquote><p>引用行</p></blockquote>", "> 引用行"),
    ("<pre><code class='language-python'>print(1)\nprint(2)</code></pre>",
     "```python\nprint(1)\nprint(2)\n```"),
    ("<table><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td>1</td><td>2</td></tr></tbody></table>",
     "| A | B |\n| --- | --- |\n| 1 | 2 |"),
    ("<p>前</p><hr><p>后</p>", "前\n\n---\n\n后"),
    ("<ul><li><input type='checkbox' checked>做完</li><li><input type='checkbox'>没做</li></ul>",
     "- [x] 做完\n- [ ] 没做"),
]
for i, (src, want) in enumerate(H2M):
    code = ("(function(){var r=window.__htmlToMd(" + json.dumps(src) + ");"
            "return JSON.stringify({md:r});})()")
    d = jj(code)
    md = d.get("md") or ""
    check(f"A{i+1} htmlToMd", md == want, "got=" + json.dumps(md, ensure_ascii=False))

# ---------- B) 渲染态粘贴 ----------
def paste(sel, html, text, off):
    call = "(function(){return (function(sel, html, text, off){var el=document.querySelector(sel);if(!el)return 'no-el';el.focus();var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT,null);var n,rem=(off==null?1e9:off),pos=null;while((n=w.nextNode())){if(n.nodeValue.length>=rem){pos={node:n,off:rem};break;}rem-=n.nodeValue.length;}var r=document.createRange();if(pos)r.setStart(pos.node,pos.off);else{r.selectNodeContents(el);r.collapse(false);}r.collapse(true);var s=getSelection();s.removeAllRanges();s.addRange(r);var dt=new DataTransfer();if(html)dt.setData('text/html',html);if(text)dt.setData('text/plain',text);var ev=new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:dt});el.dispatchEvent(ev);return ev.defaultPrevented?'prevented':'not-prevented';})(" + json.dumps(sel) + "," + (json.dumps(html) if html else "null") + "," + (json.dumps(text) if text else "null") + "," + str(off) + ")})()"
    return js(call)

# B1 标题：多行纯文本 → 首行进标题，其余拆块
js("window.setMarkdown('# 测试标题\\n\\n尾段')"); wait(600)
r = paste("h1", None, "行甲\n行乙", 5)
wait(300)
rr = raw()
check("B1 标题粘贴 preventDefault", r == "prevented", r)
check("B1 标题首行就地", rr[0] == "# 测试标题行甲", json.dumps(rr, ensure_ascii=False))
check("B1 其余拆新块", len(rr) >= 2 and rr[1] == "行乙", json.dumps(rr, ensure_ascii=False))

# B2 列表项：纯文本两行 → 接在当前项后并带同前缀
js("window.setMarkdown('- 甲项\\n- 乙项\\n- 丙项')"); wait(600)
r = paste("#editor li[data-line='1']", None, "新增一\n新增二", 3)
wait(300)
rr = raw()
check("B2 列表普通行带前缀", len(rr) == 1 and "- 甲项\n- 乙项新增一\n- 新增二\n- 丙项" == rr[0],
      json.dumps(rr, ensure_ascii=False))

# B3 列表项：列表语法行 → 原样插入为新项
js("window.setMarkdown('- 甲项\\n- 乙项')"); wait(600)
r = paste("#editor li[data-line='0']", None, "- 插入A\n- 插入B", 1)
wait(300)
rr = raw()
check("B3 列表语法原样插入", len(rr) == 1 and "- 甲项\n- 插入A\n- 插入B\n- 乙项" == rr[0],
      json.dumps(rr, ensure_ascii=False))

# B4 代码区：多行文本保留换行
js("window.setMarkdown('```python\\nprint(1)\\n```')"); wait(600)
r = paste("#editor .codeblock code", None, "x = 1\ny = 2", 8)
wait(300)
rr = raw()
check("B4 代码区保留换行", len(rr) == 1 and "x = 1\ny = 2" in rr[0], json.dumps(rr, ensure_ascii=False))

# B5 表格单元格：多行压成单行
js("window.setMarkdown('| A | B |\\n| --- | --- |\\n| 1 | 2 |')"); wait(600)
r = paste("#editor td", None, "甲\n乙", 1)
wait(300)
rr = raw()
check("B5 单元格压单行", len(rr) == 1 and "| 1甲 乙 | 2 |" in rr[0].replace("  ", " "),
      json.dumps(rr, ensure_ascii=False))

# B6 引用：多行走 <br> 行模型还原 '> ' 行
js("window.setMarkdown('> 原有行')"); wait(600)
r = paste("#editor blockquote", None, "粘贴一\n粘贴二", 4)
wait(400)
rr = raw()
check("B6 引用多行还原", len(rr) == 1 and "> 原有行粘贴一" in rr[0] and "> 粘贴二" in rr[0],
      json.dumps(rr, ensure_ascii=False))

# B7 渲染态粘贴富文本 HTML → Markdown（v3.38 PARA-WYS 后段落不再经 raw-edit，
#     mousedown 即进源码态的旧入口已移除 —— 粘贴管线在渲染态宿主上验证）
js("window.setMarkdown('第一段\\n\\n第二段')"); wait(600)
r = paste("#editor .blk p[contenteditable]", "<h2>网页标题</h2><p><b>加粗</b>正文</p>", None, 3)
wait(400)
rr = raw()
check("B7 富文本转 Markdown（渲染态 p）", "## 网页标题" in rr and "**加粗**正文" in rr,
      json.dumps(rr, ensure_ascii=False))

# B8 渲染态粘贴：纯文本多行拆块（回归）
js("window.setMarkdown('唯一段')"); wait(600)
r = paste("#editor .blk p[contenteditable]", None, "行一\n行二", 3)
wait(300)
rr = raw()
check("B8 纯文本拆块回归（渲染态 p）", rr[0] == "唯一段行一" and rr[1] == "行二", json.dumps(rr, ensure_ascii=False))

out.append("DONE")
flush()
print("done")
