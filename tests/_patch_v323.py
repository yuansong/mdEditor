# -*- coding: utf-8 -*-
"""同步 v3.23 变更导致的陈旧断言，并给「菜单顺序合并」补回归断言。

v3.23 斜杠菜单一级项由 9 项增至 12 项（新增 脚注 / 定义列表 / 上标下标），
smoke13 / smoke14 / smoke23 里基于旧菜单结构的断言需要一起更新。

每处替换都要求「恰好命中 1 次」，否则报错且不写入任何文件，避免误改。
"""
import io
import os

here = os.path.dirname(os.path.abspath(__file__))

EDITS = {}

# ============================== smoke13 ==============================
EDITS["_smoke13.py"] = [
    (
        'check("slash opens with 9 top items", d.get("show") is True and d.get("items") == 9, d)\n'
        'check("slash has 4 submenus (标题/列表/公式/图表)", d.get("subs") == 4, d)',
        '# v3.23 一级菜单 9 → 12 项（新增 脚注 / 定义列表 / 上标下标），带二级的项 4 → 6\n'
        'check("slash opens with 12 top items", d.get("show") is True and d.get("items") == 12, d)\n'
        'check("slash has 6 submenus (标题/列表/图表/公式/脚注/上标下标)", d.get("subs") == 6, d)',
    ),
]

# ============================== smoke14 ==============================
EDITS["_smoke14.py"] = [
    (
        'check("slash no 正文段落", "正文段落" not in lbs, lbs)',
        'check("slash no 正文段落", "正文段落" not in lbs, lbs)\n'
        '# v3.23 新增 脚注 / 定义列表 / 上标下标：位于 图表 之后、公式 之前（公式仍固定在最后）\n'
        'check("slash 含 脚注/定义列表/上标下标 且都在 公式 之前",\n'
        '      bool(lbs) and "脚注" in lbs and "定义列表" in lbs and "上标 / 下标" in lbs\n'
        '      and lbs.index("图表") < lbs.index("脚注") < lbs.index("定义列表")\n'
        '      < lbs.index("上标 / 下标") < lbs.index("公式"), lbs)',
    ),
]

# ============================== smoke23 ==============================
EDITS["_smoke23.py"] = [
    (
        'from mainwindow import MainWindow, SLASH_ORDER_DEFAULT, SLASH_SUB_DEFAULTS',
        'from mainwindow import (MainWindow, SLASH_ORDER_DEFAULT, SLASH_SUB_DEFAULTS,\n'
        '                        merge_slash_order)',
    ),
    (
        'check("slash menu order: 标题 列表 表格 代码块 分割线 引用 图片 图表 公式 (no 链接)",\n'
        '      d.get("items") == ["标题", "列表", "表格", "代码块", "分割线", "引用", "图片", "图表", "公式"],\n'
        '      d)',
        'check("slash menu order: 标题 列表 表格 代码块 分割线 引用 图片 图表 脚注 定义列表 上标下标 公式",\n'
        '      d.get("items") == ["标题", "列表", "表格", "代码块", "分割线", "引用", "图片", "图表",\n'
        '                         "脚注", "定义列表", "上标 / 下标", "公式"],\n'
        '      d)',
    ),
    (
        'open_slash()\n'
        'for _ in range(8):\n'
        '    key("ArrowDown")   # → 公式（最后一项）\n'
        'key("Enter")           # 展开公式二级',
        'open_slash()\n'
        '# 自适应：按菜单里 公式 的实际下标下移，菜单项数变化后断言不会失效\n'
        '_n_math = js("(function(){var m=document.getElementById(\'slashmenu\');"\n'
        '             "var lbs=[].map.call(m.querySelectorAll(\'.si .lb\'),function(x){return x.textContent});"\n'
        '             "return lbs.indexOf(\'公式\')})()")\n'
        'for _ in range(int(_n_math or 0)):\n'
        '    key("ArrowDown")   # → 公式（最后一项）\n'
        'key("Enter")           # 展开公式二级',
    ),
    (
        'check("config: first item 公式, default highlight 表格",\n'
        '      d.get("first") == "公式" and d.get("act") == "表格" and d.get("n") == 9, d)',
        'check("config: 用户顺序生效（公式首位）+ 新增项补齐，共 12 项",\n'
        '      d.get("first") == "公式" and d.get("act") == "表格" and d.get("n") == 12, d)',
    ),
    (
        'check("python set_slash_menu_config pushed to editor (chart first, all 9 kept)",\n'
        '      d.get("first") == "图表" and d.get("n") == 9, d)\n'
        'saved = win._settings.value("slashMenuOrder", "")\n'
        'check("menu order persisted to QSettings", saved == "chart,code,heading,list,table,hr,quote,image,math",\n'
        '      repr(saved))',
        'check("python set_slash_menu_config pushed to editor (chart first, 12 items kept)",\n'
        '      d.get("first") == "图表" and d.get("n") == 12, d)\n'
        'saved = win._settings.value("slashMenuOrder", "")\n'
        '# 用户指定的 chart 仍在首位；未指定项按默认相对位置补齐（紧邻 chart 之后）\n'
        'check("menu order persisted to QSettings",\n'
        '      saved == "chart,footnote,deflist,supsub,math,heading,list,table,code,hr,quote,image",\n'
        '      repr(saved))',
    ),
    (
        '# ---------- 收尾 ----------\n'
        'flush()\n'
        'os._exit(0)',
        '# ---------- 9) 菜单顺序合并 merge_slash_order：老配置升级不丢项、不打乱用户排序 ----------\n'
        '_old9 = [x for x in SLASH_ORDER_DEFAULT if x not in ("footnote", "deflist", "supsub")]\n'
        'check("merge: 老版 9 项顺序升级后 == 当前 12 项默认顺序",\n'
        '      merge_slash_order(_old9) == list(SLASH_ORDER_DEFAULT), merge_slash_order(_old9))\n'
        'check("merge: 从未保存过（空）== 当前默认顺序",\n'
        '      merge_slash_order([]) == list(SLASH_ORDER_DEFAULT), "")\n'
        'check("merge: 传完整默认顺序幂等",\n'
        '      merge_slash_order(list(SLASH_ORDER_DEFAULT)) == list(SLASH_ORDER_DEFAULT), "")\n'
        '_mf = merge_slash_order(["math", "heading", "list", "table", "code", "hr", "quote",\n'
        '                         "image", "chart"])\n'
        'check("merge: 用户拖到首位的 公式 仍是第一项，且补齐为 12 项无重复",\n'
        '      _mf[0] == "math" and len(_mf) == 12 and len(set(_mf)) == 12, _mf)\n'
        'check("merge: 公式仍固定在最后", merge_slash_order(_old9)[-1] == "math",\n'
        '      merge_slash_order(_old9))\n'
        '\n'
        '# ---------- 收尾 ----------\n'
        'flush()\n'
        'os._exit(0)',
    ),
]


def main():
    # 先全部校验命中次数，再统一写入（避免部分文件已改、后面失败）
    planned = []
    for name, edits in EDITS.items():
        path = os.path.join(here, name)
        with io.open(path, "r", encoding="utf-8") as f:
            text = f.read()
        for old, new in edits:
            n = text.count(old)
            if n != 1:
                raise SystemExit("ABORT %s: 命中 %d 次（应为 1）\n---\n%s" % (name, n, old[:120]))
            text = text.replace(old, new, 1)
        planned.append((path, text))
    for path, text in planned:
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print("patched", os.path.basename(path))
    print("ALL PATCHED")


if __name__ == "__main__":
    main()
