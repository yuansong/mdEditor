# -*- coding: utf-8 -*-
"""m102: v3.36（TPL-E）模板体系统一探针（需求 #4）。

#4 内置模板并入「模板」统一列表；「模板」提升为系统设置一级页（与外观/编辑器/通用同级）；
   新增「需求文档模板」「设计文档模板」。

T1 内置模板表 config.BUILTIN_TEMPLATES（名称 / 顺序 / 内容要点）
T2 templates.json 载入与迁移：缺失→初始化；v1 纯数组→并入 + 写回 v2；
   v2→原样；损坏→初始化；同名保留用户版本；超长名归一
T3 save_custom_templates 过滤（空名 / 空内容 / 重名去重）+ ic 保留 + 落盘 v2
T4 / 菜单「模板」二级 = 下发列表（索引 4/5 = 需求 / 设计文档；空列表不进一级菜单）
T5 设置面板一级页「模板」+ select_page 直达 + open_template_manager 入口
T6 TemplatePage：列表回读 / 改内容即落盘 / 恢复内置 / 新建 / 删除 / 上移
T7 src/ 内「模版」错别字零残留

结果写 _m102.txt，PASS/FAIL 逐条判定。
"""
import json
import os
import sys
import tempfile
import time

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
import mainwindow as mw_mod
from mainwindow import MainWindow
from dialogs import SettingsDialog, TemplatePage
from config import BUILTIN_TEMPLATES, TPL_FILE_VERSION, TPL_NAME_MAX

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m102.txt")
LINES = []
N_PASS = [0]
N_FAIL = [0]
BI = [b["name"] for b in BUILTIN_TEMPLATES]


def log(s):
    LINES.append(str(s))


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    if cond:
        N_PASS[0] += 1
    else:
        N_FAIL[0] += 1
    log(tag + " | " + name + (" | " + str(extra) if extra else ""))


def flush():
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))


def js(win, code, timeout=8000):
    res = {"v": None, "done": False}

    def cb(r):
        res["v"] = r
        res["done"] = True
    win._js_active(code, cb)
    t0 = time.time()
    while not res["done"] and time.time() - t0 < timeout / 1000.0:
        QApplication.processEvents()
        time.sleep(0.02)
    return res["v"]


def wait(ms):
    t0 = time.time()
    while time.time() - t0 < ms / 1000.0:
        QApplication.processEvents()
        time.sleep(0.02)


def setmd(win, md, ms=700):
    js(win, "window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def raws(win):
    return js(win, "JSON.stringify(window.__raw())")


def open_slash(win):
    js(win, "(function(){var el=document.querySelector('.raw-edit');"
            "if(!el)return 'noedit';"
            "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
            "return 'x'})()")
    wait(300)


def pick(win, item, sub=None):
    arg = "null" if sub is None else str(sub)
    r = js(win, "window.__slashPick(" + json.dumps(item) + "," + arg + ")")
    wait(450)
    return r


def num(r):
    try:
        return str(int(float(r)))
    except (TypeError, ValueError):
        return str(r)


def wfile(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f, ensure_ascii=False)


def rfile(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def names_of(items):
    return [t.get("name") for t in items or []]


def main():
    app = QApplication(sys.argv)
    tmpdir = tempfile.mkdtemp(prefix="m102_tpl_")
    tpl_file = os.path.join(tmpdir, "templates.json")
    mw_mod.TEMPLATE_FILE = tpl_file
    mw_mod.USER_DATA_DIR = tmpdir

    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    # ==================== T1 内置模板表 ====================
    log("---------- T1 内置模板表 ----------")
    check("T1a 内置模板 8 个", len(BUILTIN_TEMPLATES) == 8, str(len(BUILTIN_TEMPLATES)))
    want_order = ["会议纪要", "周报", "需求文档", "设计文档",
                  "技术笔记", "项目文档", "评审记录", "论文骨架"]   # v3.38（TPL-F）默认序
    check("T1b 顺序与预期一致", BI == want_order, json.dumps(BI, ensure_ascii=False))
    check("T1c 新增「需求文档」「设计文档」",
          "需求文档" in BI and "设计文档" in BI, json.dumps(BI, ensure_ascii=False))
    check("T1d 名称唯一且均有内容 / 图标",
          len(set(BI)) == 8 and
          all(b["content"].strip() and b.get("ic") for b in BUILTIN_TEMPLATES),
          "uniq=%d" % len(set(BI)))
    d_req = [b for b in BUILTIN_TEMPLATES if b["name"] == "需求文档"][0]["content"]
    d_des = [b for b in BUILTIN_TEMPLATES if b["name"] == "设计文档"][0]["content"]
    check("T1e 需求文档模板要点齐全",
          all(k in d_req for k in ("需求编号", "用户场景", "功能需求", "验收标准", "非功能需求")),
          repr(d_req[:60]))
    check("T1f 设计文档模板要点齐全",
          all(k in d_des for k in ("目标与约束", "总体设计", "模块设计", "mermaid", "测试要点")),
          repr(d_des[:60]))

    # ==================== T2 载入与迁移 ====================
    log("---------- T2 templates.json 载入与迁移 ----------")

    # T2a 缺失 → 初始化 8 内置，并落盘 v2
    try:
        os.remove(tpl_file)
    except OSError:
        pass
    items = win._load_custom_templates()
    check("T2a 文件缺失 → 初始化 8 个内置",
          len(items) == 8 and set(names_of(items)) == set(BI),
          json.dumps(names_of(items), ensure_ascii=False))
    fl = rfile(tpl_file) if os.path.isfile(tpl_file) else None
    check("T2b 初始化结果写盘为 v2", isinstance(fl, dict) and fl.get("v") == TPL_FILE_VERSION
          and len(fl.get("templates") or []) == 8, json.dumps(fl)[:120] if fl else "no-file")

    # T2c v1 纯数组 → 并入内置 + 写回 v2（用户顺序在前）
    wfile(tpl_file, [{"name": "我的模板", "content": "# 我的模板"}])
    items = win._load_custom_templates()
    # v3.38（TPL-F）：迁移统一「内置默认序在前、自建保持相对顺序随后」
    check("T2c v1 迁移：内置默认序在前 + 自建随后",
          names_of(items) == BI + ["我的模板"], json.dumps(names_of(items), ensure_ascii=False))
    fl = rfile(tpl_file)
    check("T2d v1 迁移后写回 v2（9 项）",
          fl.get("v") == TPL_FILE_VERSION and len(fl.get("templates") or []) == 9,
          "v=%s n=%s" % (fl.get("v"), len(fl.get("templates") or [])))

    # T2e v2 → v3 迁移（TPL-F）：并入内置（默认序）+ 用户项随后，写回 v3
    wfile(tpl_file, {"v": 2, "templates": [{"name": "仅一个", "content": "x"}]})
    items = win._load_custom_templates()
    check("T2e v2→v3 迁移：内置默认序 + 用户项随后（不重复）",
          names_of(items) == BI + ["仅一个"], json.dumps(names_of(items), ensure_ascii=False))

    # T2f v1 中与内置同名 → 保留用户版本，不重复追加
    wfile(tpl_file, [{"name": "周报", "content": "# 我的周报"}])
    items = win._load_custom_templates()
    zhou = [t for t in items if t["name"] == "周报"]
    check("T2f 同名保留用户版本（内容不覆盖 / 位置按默认序）",
          len(items) == 8 and len(zhou) == 1 and zhou[0]["content"] == "# 我的周报"
          and names_of(items)[BI.index("周报")] == "周报",
          json.dumps(names_of(items), ensure_ascii=False))

    # T2g 损坏文件 → 按首次运行初始化
    wfile(tpl_file, "{这不是合法 json")
    items = win._load_custom_templates()
    check("T2g 文件损坏 → 初始化 8 内置",
          len(items) == 8 and set(names_of(items)) == set(BI),
          json.dumps(names_of(items), ensure_ascii=False))

    # T2h 超长名称归一（v2 手改 json）
    wfile(tpl_file, {"v": 2, "templates": [{"name": "字" * 40, "content": "x"}]})
    items = win._load_custom_templates()
    lng = [t for t in items if t["name"].startswith("字")]
    check("T2h 超长名称收回到上限 %d" % TPL_NAME_MAX,
          len(lng) == 1 and len(lng[0]["name"]) == TPL_NAME_MAX,
          str(len(lng[0]["name"])) if lng else "missing")

    # ==================== T3 保存过滤 ====================
    log("---------- T3 save_custom_templates ----------")
    ok = win.save_custom_templates([
        {"name": "A", "content": "1"},
        {"name": "A", "content": "2"},          # 重名 → 丢弃
        {"name": "", "content": "x"},           # 空名 → 丢弃
        {"name": "B", "content": "   "},        # 空内容 → 丢弃
        {"name": "C", "content": "3", "ic": "🎯"},
    ])
    check("T3a 过滤后仅 A / C", ok is True and names_of(win._custom_templates) == ["A", "C"],
          json.dumps(win._custom_templates, ensure_ascii=False))
    cc = [t for t in win._custom_templates if t["name"] == "C"]
    check("T3b ic 保留", bool(cc) and cc[0].get("ic") == "🎯",
          json.dumps(cc, ensure_ascii=False))
    fl = rfile(tpl_file)
    check("T3c 落盘 v2 且内容一致",
          fl.get("v") == TPL_FILE_VERSION and names_of(fl["templates"]) == ["A", "C"],
          json.dumps(fl, ensure_ascii=False)[:140])

    # ==================== T4 / 菜单「模板」二级 ====================
    log("---------- T4 / 菜单「模板」二级 ----------")
    allt = [dict(b) for b in BUILTIN_TEMPLATES] + [{"name": "我的自建", "content": "# 我的自建\n\n内容"}]
    win.save_custom_templates(allt)
    r = js(win, "window.setCustomTemplates(" + win._custom_templates_js() + ")")
    check("T4a 下发 9 项（内置 8 + 自建 1）", num(r) == "9", repr(r))

    setmd(win, "")
    open_slash(win)
    st = pick(win, "tpl", 2)
    rr = raws(win)
    check("T4b 索引 2 = 需求文档模板", st == "OK" and rr and "需求编号" in rr, "%s | %s" % (st, (rr or "")[:80]))
    setmd(win, "")
    open_slash(win)
    st = pick(win, "tpl", 3)
    rr = raws(win)
    check("T4c 索引 3 = 设计文档模板", st == "OK" and rr and "flowchart LR" in rr, "%s | %s" % (st, (rr or "")[:80]))
    setmd(win, "")
    open_slash(win)
    st = pick(win, "tpl", 8)
    rr = raws(win)
    check("T4d 索引 8 = 自建模板", st == "OK" and rr and "我的自建" in rr, "%s | %s" % (st, (rr or "")[:80]))
    setmd(win, "")
    open_slash(win)
    st = pick(win, "tpl", 7)
    check("T4e 内置末项（论文骨架）可取", st == "OK", repr(st))

    # 边界：越界索引
    setmd(win, "")
    open_slash(win)
    st = pick(win, "tpl", 9)
    check("T4f 越界索引返回 NOSUB", str(st).startswith("NOSUB"), repr(st))

    # 空列表 → 一级菜单不含「模板」
    r0 = js(win, "window.setCustomTemplates('[]')")
    check("T4g 空列表下发返回 0", num(r0) == "0", repr(r0))
    setmd(win, "")
    open_slash(win)
    st = pick(win, "tpl", 0)
    check("T4h 模板清空后一级菜单移除「模板」", str(st).startswith("NOITEM"), repr(st))
    # 还原
    win.save_custom_templates(allt)

    # ==================== T5 设置面板一级页 ====================
    log("---------- T5 设置面板「模板」页 ----------")
    win.show_settings("模板")
    wait(500)
    dlg = win._set_dlg
    texts = [dlg.nav.item(i).text() for i in range(dlg.nav.count())]
    check("T5a 一级页 4 个且「模板」为同级末位",
          texts == ["外观", "编辑器", "通用", "模板"], json.dumps(texts, ensure_ascii=False))
    check("T5b 第 4 页是 TemplatePage",
          isinstance(dlg.pages.widget(3), TemplatePage) and dlg.pages.count() == 4,
          "count=%d" % dlg.pages.count())
    check("T5c show_settings('模板') 直达索引 3", dlg.pages.currentIndex() == 3,
          str(dlg.pages.currentIndex()))
    check("T5d select_page 命中 / 未命中",
          dlg.select_page("通用") is True and dlg.select_page("不存在") is False,
          "row=%d" % dlg.nav.currentRow())
    win.open_template_manager()
    wait(300)
    check("T5e open_template_manager 仍直达「模板」页",
          win._set_dlg.pages.currentIndex() == 3, str(win._set_dlg.pages.currentIndex()))

    # ==================== T6 TemplatePage 操作 ====================
    log("---------- T6 TemplatePage 操作 ----------")
    win.save_custom_templates([dict(b) for b in BUILTIN_TEMPLATES])
    tp = win._set_dlg.pages.widget(3)
    tp.reload()
    check("T6a 列表回读 8 项", tp.list_w.count() == 8, str(tp.list_w.count()))
    check("T6b 列表项 = 图标 + 名称",
          tp.list_w.item(2).text() == "📋 需求文档" and tp.list_w.item(3).text() == "🎨 设计文档",
          json.dumps([tp.list_w.item(i).text() for i in range(8)], ensure_ascii=False))

    # 改内容 → 400ms 防抖后落盘
    tp.list_w.setCurrentRow(0)
    wait(200)
    check("T6c 选中项回填编辑框",
          tp.name_edit.text() == "会议纪要" and tp.content_edit.toPlainText().startswith("# 会议纪要"),
          repr(tp.name_edit.text()))
    tp.content_edit.setPlainText("# 改过了")
    wait(900)
    fl = rfile(tpl_file)
    hit = [t for t in fl["templates"] if t["name"] == "会议纪要"]
    check("T6d 文本改动防抖后即时落盘",
          bool(hit) and hit[0]["content"] == "# 改过了",
          json.dumps(hit, ensure_ascii=False)[:120])

    # 恢复内置 → 内容写回原始
    tp._on_restore()
    wait(400)
    fl = rfile(tpl_file)
    hit = [t for t in fl["templates"] if t["name"] == "会议纪要"]
    orig = [b for b in BUILTIN_TEMPLATES if b["name"] == "会议纪要"][0]
    check("T6e 恢复内置写回原始内容",
          bool(hit) and hit[0]["content"] == orig["content"],
          json.dumps(hit, ensure_ascii=False)[:120])
    check("T6f 恢复内置后数量不变（无重复）", tp.list_w.count() == 8, str(tp.list_w.count()))

    # 新建 / 删除
    tp._on_new()
    wait(500)
    check("T6g 新建 → 9 项且名为「新模板」",
          tp.list_w.count() == 9 and tp.name_edit.text() == "新模板",
          "%d / %s" % (tp.list_w.count(), tp.name_edit.text()))
    fl = rfile(tpl_file)
    check("T6h 新建已落盘", names_of(fl["templates"]).count("新模板") == 1,
          json.dumps(names_of(fl["templates"]), ensure_ascii=False))
    tp._on_del()
    wait(500)
    fl = rfile(tpl_file)
    check("T6i 删除 → 回到 8 项且无「新模板」",
          tp.list_w.count() == 8 and "新模板" not in names_of(fl["templates"]),
          "%d | %s" % (tp.list_w.count(), json.dumps(names_of(fl["templates"]), ensure_ascii=False)))

    # 上移 / 下移
    before = names_of(rfile(tpl_file)["templates"])
    tp.list_w.setCurrentRow(1)
    wait(200)
    tp._on_move(-1)
    wait(400)
    after = names_of(rfile(tpl_file)["templates"])
    check("T6j 上移生效（前两项互换）",
          after[0] == before[1] and after[1] == before[0], json.dumps(after, ensure_ascii=False))
    tp._on_move(1)
    wait(400)
    back = names_of(rfile(tpl_file)["templates"])
    check("T6k 下移还原", back == before, json.dumps(back, ensure_ascii=False))
    tp.list_w.setCurrentRow(0)
    wait(200)
    tp._on_move(-1)
    wait(300)
    check("T6l 边界（首项上移无效）",
          names_of(rfile(tpl_file)["templates"]) == before,
          json.dumps(names_of(rfile(tpl_file)["templates"]), ensure_ascii=False))

    # ==================== T7 「模版」错别字 ====================
    log("---------- T7 错别字 ----------")
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "..", "src")
    bad = []
    for root, _dirs, files in os.walk(src):
        for fn in files:
            if not fn.endswith((".py", ".html", ".qss", ".css", ".json")):
                continue
            p = os.path.join(root, fn)
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
            except OSError:
                continue
            n = txt.count("模版")
            if n:
                bad.append("%s(%d)" % (fn, n))
    check("T7a src/ 无「模版」残留", not bad, " / ".join(bad) or "clean")

    log("RESULT PASS=%d FAIL=%d" % (N_PASS[0], N_FAIL[0]))
    flush()
    print("DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        log("EXCEPTION " + traceback.format_exc())
        log("RESULT PASS=%d FAIL=%d" % (N_PASS[0], N_FAIL[0]))
        flush()
        raise
