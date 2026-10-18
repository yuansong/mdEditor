# -*- coding: utf-8 -*-
"""界面风格（UI Style）体系 —— v3.39.15（UISTYLE-1）。

「风格」是独立于「主题」的 Qt 层皮肤：
- 主题（styles.THEMES 六套）：同步作用于 Qt 界面与编辑器网页内容；
- 风格（本模块）：仅覆盖 Qt 层控件观感（配色基调 / 字体），编辑器内容不受影响；
  「主界面效果图-PS01（现代经典）」为默认风格，不覆盖任何调色板（= 原有外观）。

结构设计（便于动态增删单个风格而不影响其他功能）：
- 每个风格 = 一个独立 JSON 文件（id/name/desc/locked/palette/qss）；
- 内置风格目录 src/uistyles/，用户风格目录 %APPDATA%/.../uistyles/；
- 注册表每次 list_styles() 时实时扫描目录 —— 拖入 JSON 即新增，
  删除文件即移除，互相之间零耦合；
- 回退逻辑：resolve()/set_active() 保证任何非法或已删除的风格 ID
  自动回退默认风格 ps01（与 apply_theme 的主题回退同构）；
- 渲染管线：完全复用 styles 的 APP/SIDEBAR/DIALOG_QSS_TPL 模板，
  仅将调色板替换为「主题调色板 + 风格覆盖」的合并结果，
  不引入任何新选择器，保证与既有界面渲染一致。
"""

import glob
import json
import os

import config
import styles

DEFAULT_ID = "ps01"

# 内置风格目录（随程序分发，可整目录删除单个 JSON 以移除风格）
BUILTIN_DIR = os.path.join(config.HERE, "uistyles")
# 用户风格目录（拖入 JSON 即新增）
USER_DIR = os.path.join(config.USER_DATA_DIR, "uistyles")

# 当前激活风格（进程级；由 MainWindow 启动/切换时写入，对话框渲染时读取）
_active = DEFAULT_ID


# v3.43.0（LOOK-1）：「外观 → 界面风格」子菜单的固定清单。
#
# 严格取自设计稿 docs/ui-redesign 的 6 套主界面效果图，不新增、不删减；
# 名称保持纯净（不带「01/02」编号与「（PS01 · 01）」之类后缀）——这是刻意与
# 设计稿文案不同的唯一一处：设计稿里带编号是为了对照文档，菜单里不需要。
# 其余内置 / 用户风格（paper / term / fluent / w32 及用户自建）仍在注册表内，
# 由「外观 → 界面风格管理…」统一查看与增删，不占用本菜单。
MENU_STYLES = (
    ("ps01", "现代经典"),
    ("mac", "macOS"),
    ("code", "VS Code 工作台"),
    ("ribbon", "Office 功能区蓝"),
    ("notion", "Notion 轻拟物"),
    ("zen", "极简无界"),
)


def menu_styles():
    """「外观 → 界面风格」子菜单条目：[(id, 名称), ...]（缺失的风格自动跳过）。"""
    return [(sid, name) for sid, name in MENU_STYLES if get_style(sid)]


def menu_style_label(sid):
    """菜单用的纯净风格名（不在菜单清单内时回退 JSON 里的 name）。"""
    for s, name in MENU_STYLES:
        if s == sid:
            return name
    return style_label(sid)


def style_accent(sid, theme_id="light"):
    """风格在当前主题下的强调色（菜单色卡图标用）。"""
    try:
        return merge_palette(theme_id, sid).get("accent") or "#0052d9"
    except Exception:
        return "#0052d9"


def user_style_dir():
    """用户风格目录（不存在则创建）。"""
    os.makedirs(USER_DIR, exist_ok=True)
    return USER_DIR


def _load_file(path):
    """读取单个风格 JSON；非法文件静默跳过（不拖垮其他风格）。"""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        sid = str(data.get("id") or "").strip()
        if not sid:
            return None
        data.setdefault("name", sid)
        data.setdefault("desc", "")
        data.setdefault("locked", False)
        data.setdefault("palette", {})
        data.setdefault("palette_dark", {})  # v3.41.4：深色主题下的同款覆盖（可缺省）
        data.setdefault("qss", "")
        data.setdefault("editor_css", "")        # v3.42.0：编辑器网页内容 CSS（浅色态）
        data.setdefault("editor_css_dark", "")   # v3.42.0：编辑器网页内容 CSS（深色态）
        data.setdefault("layout", "")   # v3.41.0：结构化布局标记
        data.setdefault("suggest_theme", "")
        data["_path"] = path
        data["_user"] = path.startswith(USER_DIR)
        return data
    except Exception:
        return None


def list_styles():
    """扫描全部风格（内置 + 用户），按 id 排序；默认风格恒排最前。"""
    found = {}
    for d in (BUILTIN_DIR, USER_DIR):
        for p in sorted(glob.glob(os.path.join(d, "*.json"))):
            s = _load_file(p)
            if s and s["id"] not in found:
                found[s["id"]] = s
    out = []
    if DEFAULT_ID in found:
        out.append(found.pop(DEFAULT_ID))
    out.extend(sorted(found.values(), key=lambda s: s["id"]))
    return out


def get_style(sid):
    for s in list_styles():
        if s["id"] == sid:
            return s
    return None


def resolve(sid):
    """非法 / 已删除的风格 ID → 回退默认风格。"""
    return sid if get_style(sid) else DEFAULT_ID


def set_active(sid):
    """设置当前激活风格（含回退）；返回实际生效的 ID。"""
    global _active
    _active = resolve(str(sid or DEFAULT_ID))
    return _active


def active():
    return _active


def active_layout():
    """v3.41.0：当前激活风格的结构布局标记（"" = 标准 R7 布局，"mac" = macOS 统一工具栏）。"""
    s = get_style(_active)
    return (s.get("layout") or "") if s else ""


def style_label(sid):
    s = get_style(sid)
    return s["name"] if s else style_label(DEFAULT_ID)


def _luma(hexc):
    """亮度（0~255）：用于判定主题深浅，避免硬编码主题 ID 列表。"""
    c = str(hexc or "").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except Exception:
        return 255
    return 0.299 * r + 0.587 * g + 0.114 * b


def is_dark_theme(theme_id):
    """主题是否为深色（按主题自身 bg 亮度判定：dark / night / panda 等均适用）。"""
    return _luma(styles.palette(theme_id).get("bg", "#ffffff")) < 128


def merge_palette(theme_id, style_id=None):
    """主题调色板 + 风格覆盖（默认风格 ps01 = 纯主题调色板）。

    v3.41.4：风格可给出深浅两套覆盖——`palette`（浅色主题态，也是缺省回退）与
    `palette_dark`（深色主题态）。此前风格只有一份固定覆盖，导致切到 VSCode 之类
    风格后无论选什么主题外壳都一个样（「主题失效」）；现在深浅随主题切换。
    只有写了 `palette_dark` 的风格才受主题影响，单份 palette 的风格行为不变。
    v3.42.0：风格可引入自定义 token（如 seg_bg / status_fg），用于结构 QSS 插值
    ——不再要求 key 必须已存在于主题调色板（多余 token 不影响模板 format）。
    """
    pal = dict(styles.palette(theme_id))
    s = get_style(style_id or _active)
    if s:
        dark = is_dark_theme(theme_id)
        overlay = s.get("palette_dark") if dark else None
        if not overlay:
            overlay = s.get("palette") or {}
        for k, v in overlay.items():
            pal[k] = v
    # v3.42.0：页签选中态 token 缺省回退（主模板 ::tab:selected 改用这两个 token，
    # 风格经 palette 直接表达选中底/字色；ps01 等未覆盖风格 = 原 bg/text 行为不变）
    pal.setdefault("tab_sel_bg", pal.get("bg", "#ffffff"))
    pal.setdefault("tab_sel_text", pal.get("text", "#1f2328"))
    return pal


def _fmt(tpl, theme_id, style_id):
    return tpl.format(**merge_palette(theme_id, style_id))


def _interp(text, theme_id, style_id):
    """风格 QSS / editor_css 的 token 插值：{accent} 等 palette key 原位替换。

    采用整词替换而非 str.format，避免与 CSS 花括号冲突；JSON 内其余
    `{...}` 序列保持原样（安全：palette key 均为 [a-z_]+ 标识符）。
    """
    if not text or "{" not in text:
        return text
    for k, v in merge_palette(theme_id, style_id).items():
        text = text.replace("{%s}" % k, str(v))
    return text


def app_qss(theme_id="light", style_id=None):
    qss = _fmt(styles.APP_QSS_TPL, theme_id, style_id or _active)
    extra = (get_style(style_id or _active) or {}).get("qss") or ""
    extra = _interp(extra, theme_id, style_id or _active)
    return qss + ("\n" + extra if extra else "")


def sidebar_qss(theme_id="light", style_id=None):
    return _fmt(styles.SIDEBAR_QSS_TPL, theme_id, style_id or _active)


def dialog_qss(theme_id="light", style_id=None):
    return _fmt(styles.DIALOG_QSS_TPL, theme_id, style_id or _active)


def editor_css(theme_id="light", style_id=None):
    """v3.42.0：编辑器网页内容级风格 CSS（纸张 / 窄栏等），随深浅主题取对应字段。"""
    s = get_style(style_id or _active)
    if not s:
        return ""
    css = s.get("editor_css_dark") if is_dark_theme(theme_id) else None
    if not css:
        css = s.get("editor_css") or ""
    return _interp(css, theme_id, style_id or _active)


def remove_style(sid):
    """删除风格文件（默认风格 ps01 锁定不可删）。

    返回 (ok: bool, msg: str)。调用方负责：若删除的是激活风格，
    随后调用 MainWindow.set_uistyle(DEFAULT_ID) 完成回退。
    """
    if sid == DEFAULT_ID:
        return False, "默认风格不可删除"
    s = get_style(sid)
    if not s:
        return False, "风格不存在"
    try:
        os.remove(s["_path"])
        return True, f"已删除风格：{s['name']}"
    except Exception as e:
        return False, f"删除失败：{e}"
