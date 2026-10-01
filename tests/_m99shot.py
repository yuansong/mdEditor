# -*- coding: utf-8 -*-
"""v3.34（MMD-11）图表主题视觉预览生成 + 渲染一致性校验。

对同一份图表文档（流程图 + 时序图）逐套切换六套主题，取出真实渲染的 SVG，
校验每套主题确实按自己的调色板重渲染（描边色命中），并生成一张
side-by-side 对比预览页 docs/图表主题预览-v3.34.html 供人工观感确认。
输出：tests/_m99shot.txt（PASS/FAIL）+ 预览 HTML
"""
import base64
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(HERE, "_m99shot.txt")
HTML_OUT = os.path.join(HERE, "..", "docs", "图表主题预览-v3.34.html")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
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


MD = ("```mermaid\nflowchart TB\n"
      "  subgraph 接入层\n    A[用户请求] --> B{参数校验}\n  end\n"
      "  B -- 通过 --> C[写入数据库]\n  B -- 拒绝 --> D[返回 400]\n"
      "  C --> E[(审计日志)]\n  C --> F([异步通知])\n```\n\n"
      "```mermaid\nsequenceDiagram\n  participant U as 用户\n  participant S as 服务端\n"
      "  U->>S: 提交表单\n  S-->>U: 202 Accepted\n  Note over S: 异步处理\n```\n")

wait(3000)
js("window.setSlashMenuConfig(null)")
js(f"window.setMarkdown({json.dumps(MD)})")
wait(3500)
n = js("document.querySelectorAll('#editor .mermaidblock svg').length")
check("预览：两个图表块渲染出 SVG", int(float(n or 0)) == 2, repr(n))

THEMES = [("azure", "晴空"), ("mint", "薄荷"), ("sepia", "暖沙"),
          ("graphite", "石墨"), ("night", "暗夜"), ("ember", "琥珀")]
panels = []
for tid, label in THEMES:
    js(f"window.setMmdTheme({json.dumps(tid)})")
    wait(1600)
    r = js("(function(){var vs=JSON.parse(window.mmdThemeVars(" + json.dumps(tid) + "));"
           "var els=document.querySelectorAll('#editor .mermaidblock');var out=[];"
           "for(var i=0;i<els.length;i++){var sv=els[i].querySelector('svg');"
           "out.push(sv?sv.outerHTML:'');}"
           "return JSON.stringify({border:vs.primaryBorderColor,bg:vs.background,"
           "text:vs.primaryTextColor,line:vs.lineColor,svgs:out});})()")
    d = json.loads(r or "{}")
    svgs = d.get("svgs") or []
    ok = len(svgs) == 2 and all(d.get("border") in s for s in svgs)
    check(f"预览：{label} 图表按本主题重渲染（描边 {d.get('border')} 命中）", ok,
          "svg_len=%s" % [len(s) for s in svgs])
    panels.append({"id": tid, "label": label, "vars": d, "svgs": svgs})

js("window.setMmdTheme('')")

# ---- 生成对比预览页（内嵌真实 SVG，浅/深分组展示） ----
parts = []
for p in panels:
    v = p["vars"]
    chips = "".join(
        f'<span class="chip"><i style="background:{v[k]}"></i>{label_k}:{v[k]}</span>'
        for label_k, k in (("主体", "border"), ("背景", "bg"),
                           ("连线", "line"), ("文字", "text")))
    body = "".join(f'<div class="svgbox">{s}</div>' for s in p["svgs"] if s)
    parts.append(f"""
  <section class="panel" style="background:{v['bg']};color:{v['text']}">
    <header><h2>{p['label']}</h2><code>{p['id']}</code></header>
    <div class="chips">{chips}</div>
    {body}
  </section>""")

html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>mdEditor 图表主题预览（v3.34 / MMD-11）</title>
<style>
  body {{ margin:0; padding:28px 22px 48px; font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif;
         background:#eef1f5; color:#1f2937; }}
  h1 {{ font-size:20px; margin:0 0 6px; }}
  .lead {{ color:#5b6472; margin:0 0 22px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(360px,1fr)); gap:18px; }}
  .panel {{ border-radius:14px; padding:16px 18px 18px; box-shadow:0 2px 10px rgba(15,23,42,.12);
            border:1px solid rgba(125,125,125,.22); }}
  .panel header {{ display:flex; align-items:baseline; gap:8px; margin-bottom:8px; }}
  .panel h2 {{ font-size:16px; margin:0; }}
  .panel code {{ opacity:.6; font-size:12px; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }}
  .chip {{ font-size:11px; opacity:.75; display:inline-flex; align-items:center; gap:4px; }}
  .chip i {{ width:10px; height:10px; border-radius:3px; display:inline-block;
             border:1px solid rgba(0,0,0,.18); }}
  .svgbox {{ background:transparent; padding:6px 0; overflow:auto; }}
  .svgbox + .svgbox {{ border-top:1px dashed rgba(125,125,125,.28); margin-top:6px; }}
  .svgbox svg {{ max-width:100%; height:auto; }}
</style></head>
<body>
  <h1>mdEditor 图表主题预览 · v3.34（MMD-11）</h1>
  <p class="lead">同一份文档（流程图 + 时序图）在六套主题下的真实渲染结果；主题全部基于
     mermaid <code>theme:'base' + themeVariables'</code> 自定义调色，统一字体与 15px 字号，
     描边 1.5px。可在「设置 → 系统设置 → 外观 → 图表主题」或「图表块右键 → 图表主题」切换。</p>
  <div class="grid">{''.join(parts)}
  </div>
</body></html>
"""

with open(HTML_OUT, "w", encoding="utf-8") as f:
    f.write(html)
check("预览页已生成", os.path.exists(HTML_OUT) and os.path.getsize(HTML_OUT) > 8000,
      str(os.path.getsize(HTML_OUT)))

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print(f"RESULT PASS={sum(1 for x in results if x.startswith('PASS'))} "
      f"FAIL={sum(1 for x in results if x.startswith('FAIL'))}")
