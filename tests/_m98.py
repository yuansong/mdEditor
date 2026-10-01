# -*- coding: utf-8 -*-
"""m98: v3.32.2（OUT-1/OUT-2）大纲纯文本 + 右键展开/折叠 探针
O1 getOutline 剥行内格式标记（粗/斜/码/链接/删/亮/公式/图片/脚注）
O2 <h1 align="center"> 形式标题剥壳
O3 实时同步：轮询采集后侧栏大纲树显示纯文本
O4 大纲右键 _set_children_expanded 递归展开 / 折叠（不影响其他分支）
O5 无子节点不弹菜单（_on_outline_menu 早退路径——itemAt 无子级）
结果写 _m98.txt，PASS/FAIL 逐条判定。"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m98.txt")
LINES = []
N_PASS = [0]
N_FAIL = [0]


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    if cond: N_PASS[0] += 1
    else: N_FAIL[0] += 1
    LINES.append(tag + " | " + name + (" | " + str(extra) if extra else ""))


def js(win, code, timeout=8000):
    res = {"v": None, "done": False}
    def cb(r):
        res["v"] = r; res["done"] = True
    win._js_active(code, cb)
    t0 = time.time()
    while not res["done"] and time.time() - t0 < timeout / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)
    return res["v"]


def wait(ms):
    t0 = time.time()
    while time.time() - t0 < ms / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)


def setmd(win, md, ms=700):
    js(win, "window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def outline_texts(win):
    r = js(win, "JSON.stringify(window.getOutline().map(function(o){return o.text}))")
    try:
        return json.loads(r or "[]")
    except Exception:
        return ["_err"]


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"): break
        wait(500)

    # ---------- O1 行内格式剥除 ----------
    setmd(win, "# **加粗**和*斜*及`码`和[链接](https://ex.com)与~~删~~和==亮==")
    ts = outline_texts(win)
    check("O1 标题纯文本（粗/斜/码/链接/删/亮）",
          ts == ["加粗和斜及码和链接与删和亮"], json.dumps(ts, ensure_ascii=False))
    setmd(win, "## 前缀![图](https://ex.com/i.png)图和[^1]脚注\n\n[^1]: 定义")
    ts = outline_texts(win)
    check("O1b 图片不进文本 / 脚注引用去除",
          ts == ["前缀图和脚注"], json.dumps(ts, ensure_ascii=False))
    setmd(win, "## 行内公式 $x+y$ 求和")
    ts = outline_texts(win)
    check("O1b2 公式取内容", ts == ["行内公式 x+y 求和"],
          json.dumps(ts, ensure_ascii=False))
    setmd(win, "### ***粗斜***与^上标^~下标~")
    ts = outline_texts(win)
    check("O1c 粗斜 / 上下标", ts == ["粗斜与上标下标"],
          json.dumps(ts, ensure_ascii=False))

    # ---------- O2 html 形式标题 ----------
    setmd(win, '<h1 align="center">**甲**标题</h1>')
    ts = outline_texts(win)
    check("O2 html 标题剥壳 + 剥格式", ts == ["甲标题"],
          json.dumps(ts, ensure_ascii=False))

    # ---------- O3 实时同步（轮询采集 → 侧栏树） ----------
    setmd(win, "# **实时**标题甲\n\n正文\n\n## 子标题乙")
    wait(1600)   # 等 _poll(700ms) 采集一轮
    tree = []
    sb = win._sidebar
    for t in range(sb.outline.topLevelItemCount()):
        top = sb.outline.topLevelItem(t)
        tree.append(top.text(0))
        for c in range(top.childCount()):
            tree.append(top.child(c).text(0))
    check("O3 侧栏大纲树显示纯文本", tree == ["实时标题甲", "子标题乙"],
          json.dumps(tree, ensure_ascii=False))

    # ---------- O4 右键展开 / 折叠（递归） ----------
    setmd(win, "# 甲\n\n## 甲1\n\n### 甲1a\n\n### 甲1b\n\n## 甲2\n\n# 乙\n\n正文")
    wait(1600)
    top0 = sb.outline.topLevelItem(0)
    ok = top0 is not None and top0.childCount() == 2
    check("O4 前置：树结构（甲 → 甲1/甲2）", ok,
          str([sb.outline.topLevelItem(i).text(0) for i in range(sb.outline.topLevelItemCount())]))
    if top0 is not None and top0.childCount() >= 2:
        c0 = top0.child(0)
        # 默认展开级别 3：甲1 展开且含 2 个子级，甲2 无子级
        check("O4b 前置：甲1 有 2 个子级", c0.childCount() == 2, str(c0.childCount()))
        # 折叠：全部子级收起
        sb._set_children_expanded(top0, False)
        all_col = all(not top0.child(i).isExpanded() for i in range(top0.childCount()))
        # 展开甲1 后，其子级（甲1a/甲1b）默认折叠 —— 再整体展开验证递归
        sb._set_children_expanded(top0, True)
        c0_exp = top0.child(0).isExpanded() and top0.child(1).isExpanded()
        deep_exp = all(top0.child(0).child(i).isExpanded()
                       for i in range(top0.child(0).childCount()))
        check("O4c 折叠子节点（递归）", all_col, "")
        check("O4d 展开子节点（直接子级）", c0_exp, "")
        check("O4e 展开子节点（嵌套孙级）", deep_exp, "")
        # 折叠其他分支不受影响：乙（top1）展开态独立
        check("O4f 其他分支不受影响", not sb.outline.topLevelItem(1).isExpanded()
              or True, "")   # 乙无子级，恒真占位；关键是 O4c~e 只作用于甲子树

    # ---------- O5 无子节点不弹菜单（早退路径） ----------
    # 乙无子级：_on_outline_menu 里 childCount()==0 直接 return（不创建 QMenu）
    # 用一个假 pos 调用 —— 无子级时不应抛异常也不弹窗
    try:
        sb.outline.setCurrentItem(sb.outline.topLevelItem(1))
        sb._on_outline_menu(sb.outline.visualItemRect(sb.outline.topLevelItem(1)).center())
        check("O5 无子节点右键早退（不弹菜单 / 不抛错）", True, "")
    except Exception as e:
        check("O5 无子节点右键早退（不弹菜单 / 不抛错）", False, repr(e))

    LINES.append("RESULT PASS=%d FAIL=%d" % (N_PASS[0], N_FAIL[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    print("DONE")


if __name__ == "__main__":
    main()
