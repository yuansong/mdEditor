# -*- coding: utf-8 -*-
"""v3.29 探针：表格合并新交互 —— 多选直接合并、单选无合并/删除按钮、方向合并移除。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m27a.txt")
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


def bar_titles():
    return js("(function(){var b=document.querySelectorAll('#tblbar button');"
              "var a=[];for(var i=0;i<b.length;i++)a.push(b[i].title||'');"
              "return JSON.stringify(a)})()") or "[]"


def has(title):
    t = bar_titles()
    try:
        titles = json.loads(t)
        return any(title in x for x in titles)
    except Exception:
        return title in t


def btn_en(title):
    """v3.29c：按 title 查菜单按钮是否可用（非 .dis）。"""
    return js("(function(){var b=[].filter.call("
              "document.querySelectorAll('#tblbar button'),"
              "function(x){return x.title.indexOf('" + title + "')===0})[0];"
              "return b ? (b.classList.contains('dis') ? 'dis' : 'en') : 'none'})()") == "en"


wait(2500)

TBL = "| 甲 | 乙 | 丙 | 丁 |\n| --- | --- | --- | --- |\n| 1 | 2 | 3 | 4 |\n| 5 | 6 | 7 | 8 |"
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(600)

# 1) 单选中间格 (1,1) → 无合并 / 无删除按钮，还原/拆分不出现
js("window.__tblSelSet(0, 1, 1, 1, 1)")
wait(300)
check("单选格 → 合并按钮置灰（方向合并已移除）",
      not btn_en("合并单元格"), bar_titles())
check("单选格 → 删除行 / 删除列可用（常驻菜单）",
      btn_en("删除行") and btn_en("删除列"))
check("未合并格 → 还原单元格置灰（常驻菜单）", not btn_en("还原单元格"))
check("未合并格 → 拆分单元格出现且可用（v3.29c）", has("拆分单元格") and btn_en("拆分单元格"))
check("单选格 → 保留插列 / 插行 / 对齐",
      has("向右插入列") and has("向上插入行") and has("左对齐"))

# 2) 多选 (1,1)-(1,2) → 出现「合并单元格」，点合并 → colspan=2，内容 "2 3"
js("window.__tblSelSet(0, 1, 1, 1, 2)")
wait(300)
check("多选 1×2 → 出现合并单元格", has("合并单元格"), bar_titles())
js("window.__tblOp('merge')")
wait(400)
r = raw()[0]
check("多选合并 → colspan=2", 'colspan="2"' in r, r[:160])
check("合并内容顺序 2 3", ">2 3<" in r.replace("\n", " "), r[:160])

# 3) 合并后（keepSel 保留矩形选区）→ 右键重建操作条应显示还原 / 拆分（合并后的框支持拆分）
js("window.__tblSelSet(0, 1, 1, 1, 1)")
wait(300)
check("合并格单选 → 出现还原单元格", has("还原单元格"))
check("合并格单选 → 出现拆分单元格", has("拆分单元格"))
check("合并格单选 → 合并按钮置灰（常驻菜单）", not btn_en("合并单元格"))

# 4) 还原单元格 → colspan 消失，回到单格
js("window.__tblOp('unmerge')")
wait(400)
r2 = raw()[0]
check("还原 → colspan 消失", 'colspan="2"' not in r2, r2[:160])
js("window.__tblSelSet(0, 1, 1, 1, 1)")
wait(200)
check("还原后 → 还原按钮置灰（常驻菜单）", not btn_en("还原单元格"))

# 5) 多选 2×1（跨行）合并 → rowspan=2，内容 "2 6"
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(500)
js("window.__tblSelSet(0, 1, 1, 2, 1)")
wait(200)
check("多选 2×1 → 出现合并单元格", has("合并单元格"))
js("window.__tblOp('merge')")
wait(400)
r3 = raw()[0]
check("跨行合并 → rowspan=2", 'rowspan="2"' in r3, r3[:200])
check("跨行合并内容 2 6", ">2 6<" in r3.replace("\n", " "), r3[:200])

# 6) 方向合并操作已移除：__tblOp('mergeRight') 为空操作，raw 不变
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(500)
js("window.__tblSelSet(0, 1, 1, 1, 1)")
wait(200)
before6 = raw()[0]
js("window.__tblOp('mergeRight')")
wait(300)
check("mergeRight 已移除（raw 不变）", raw()[0] == before6, raw()[0][:120])

# 7) 多选 2×2 合并 → colspan=2 且 rowspan=2，内容含 1/2/5/6
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(500)
js("window.__tblSelSet(0, 1, 1, 2, 2)")
wait(200)
check("多选 2×2 → 出现合并单元格", has("合并单元格"))
js("window.__tblOp('merge')")
wait(400)
r4 = raw()[0]
check("2×2 合并 → colspan=2 rowspan=2",
      'colspan="2"' in r4 and 'rowspan="2"' in r4, r4[:200])
check("2×2 合并内容齐（1 2 5 6）",
      all(x in r4 for x in ["1", "2", "5", "6"]), r4[:200])

# 8) 合并后整选区（矩形=合并框）→ 还原/拆分出现在多选分支
js("window.__tblSelSet(0, 1, 1, 2, 2)")
wait(300)
check("选区=合并框 → 出现还原单元格", has("还原单元格"))
check("选区=合并框 → 出现拆分单元格", has("拆分单元格"))
check("选区=合并框 → 合并按钮置灰（常驻菜单）", not btn_en("合并单元格"))

# 9) 部分覆盖合并格的选区 → 不出现合并按钮（partial 保护）
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(500)
js("window.__tblSelSet(0, 1, 1, 2, 2)")
wait(200)
js("window.__tblOp('merge')")
wait(400)
js("window.__tblSelSet(0, 1, 1, 1, 2)")   # 只选合并框上半（partial）
wait(300)
check("部分覆盖合并格 → 合并按钮置灰（partial 保护）", not btn_en("合并单元格"), bar_titles())
check("部分覆盖合并格 → 保留对齐", has("左对齐"))

# 10) 合并后整表横向缩放（拖 RZ 东手柄 +60px）→ 合并保持、列宽均分
def fire_drag(handle_sel, dx, dy):
    code = ("(function(){var rz=document.getElementById('rzframe');"
            "if(!rz)return 'no rz';var h=rz.querySelector('" + handle_sel + "');"
            "if(!h)return 'no handle';var r=h.getBoundingClientRect();"
            "function fire(el,t,x,y){el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,clientX:x,clientY:y}));}"
            "fire(h,'mousedown',r.left,r.top);"
            "fire(document,'mousemove',r.left+" + str(dx) + ",r.top+" + str(dy) + ");"
            "fire(document,'mouseup',r.left+" + str(dx) + ",r.top+" + str(dy) + ");"
            "return 'dragged'})()")
    return js(code)

js(f"window.setMarkdown({json.dumps(TBL)})")
wait(500)
js("window.__tblSelSet(0, 1, 1, 1, 2)")
wait(200)
js("window.__tblOp('merge')")
wait(400)
d = fire_drag('.rz.e', 60, 0)
wait(500)
r9 = raw()[0]
check("整表拖宽 → 调用成功", d == "dragged", str(d))
check("整表拖宽 → 合并保持 colspan=2", 'colspan="2"' in r9, r9[:200])
check("整表拖宽 → 内容 2 3 保留", ">2 3<" in r9.replace("\n", " "), r9[:200])
cw9 = jj("window.__tblColW(0)")
ws9 = cw9.get("w", [])
check("整表拖宽 → colgroup 仍 4 列", cw9.get("cols") == 4, str(cw9))
check("整表拖宽 → 每列宽 >0", all(w and float(w) > 0 for w in ws9) if ws9 else False, str(ws9))
if len(ws9) >= 2:
    a9, b9 = float(ws9[0]), float(ws9[1])
    check("整表拖宽 → 合并两列宽仍均分", abs(a9 - b9) <= max(4, 0.15 * max(a9, b9)), f"a={a9} b={b9}")

# 11) 合并后整表纵向缩放（拖南手柄 +50px）→ rowspan 保持、无幻影列
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(500)
js("window.__tblSelSet(0, 1, 1, 2, 1)")
wait(200)
js("window.__tblOp('merge')")
wait(400)
d10 = fire_drag('.rz.s', 0, 50)
wait(500)
r10 = raw()[0]
check("整表拖高 → 调用成功", d10 == "dragged", str(d10))
check("整表拖高 → 合并保持 rowspan=2", 'rowspan="2"' in r10, r10[:200])
check("整表拖高 → 内容 2 6 保留", ">2 6<" in r10.replace("\n", " "), r10[:200])
check("整表拖高 → 被覆盖格 6 不残留（无幻影列）",
      'rowspan="2">2 6</td>' in r10 and "<td>6</td>" not in r10, r10[:300])

# 12) 合并 → 列边框拖拽（单元格右边界 mousedown +40px）→ 合并保持
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(500)
js("window.__tblSelSet(0, 1, 1, 1, 2)")
wait(200)
js("window.__tblOp('merge')")
wait(400)
code11 = ("(function(){var tbl=document.querySelector('#editor .blk table');"
          "var cell=tbl.tBodies[0].rows[0].cells[0];"
          "var r=cell.getBoundingClientRect();"
          "function fire(el,t,x,y){el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,clientX:x,clientY:y}));}"
          "fire(cell,'mousedown',r.right-1,r.top+r.height/2);"
          "fire(document,'mousemove',r.right+40,r.top+r.height/2);"
          "fire(document,'mouseup',r.right+40,r.top+r.height/2);"
          "return 'ok'})()")
d11 = js(code11)
wait(500)
r11 = raw()[0]
check("列边框拖拽 → 调用成功", d11 == "ok", str(d11))
check("列边框拖拽 → 合并保持 colspan=2", 'colspan="2"' in r11, r11[:200])
check("列边框拖拽 → 内容 2 3 保留", ">2 3<" in r11.replace("\n", " "), r11[:200])
cw11 = jj("window.__tblColW(0)")
ws11 = cw11.get("w", [])
check("列边框拖拽 → colgroup 仍 4 列且宽 >0",
      cw11.get("cols") == 4 and all(w and float(w) > 0 for w in ws11) if ws11 else False, str(cw11))

out.append("DONE")
flush()
print("done")
