# -*- coding: utf-8 -*-
"""整本书 PDF 导出引擎（v3.44.35 / BOOK-3）。

设计要点：
- 复用编辑器内核（editor.html + KaTeX）做逐章全保真渲染，再用 QWebEngineView.printToPdf
  把每章栅格化为独立 PDF；
- 有界并发（默认 3 个内核/打印视图槽）并行渲染，显著快于逐章串行；
- 全部章节 PDF 用 pypdf 合并，并按「章节起始页偏移」写入层级书签（精确，不靠文本检索）；
- 合并后用 fpdf2 给每页底部居中盖页码（静音灰）。

无头渲染必须走原生 windows 平台（offscreen 仅 2 字体族 → 中文/几何字形豆腐块），
因此本模块仅在 GUI 进程内（已加载 editor.html 的同一应用）使用。
"""
import json
import logging
import os
import tempfile

from PySide6.QtCore import QTimer, QUrl, QMarginsF
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtGui import QPageLayout, QPageSize

from exporters import linkify_pdf_links, merge_book_pdfs, stamp_page_numbers

_log = logging.getLogger(__name__)


def _js(s):
    """把 Python 字符串安全转成 JS 字符串字面量（JSON 编码）。"""
    return json.dumps(s, ensure_ascii=False)


# v3.44.36（BOOK-4）：整书本导出——把整页底色统一为纸张色（--card），
# 并将 .page 卡片透明化，避免章末空白处露出画布灰（--canvas）造成背景不一致。
_BOOK_BG_STYLE = (
    "<style>"
    "html,body{background:var(--card,#ffffff)!important;}"
    ".page{background:transparent!important;box-shadow:none!important;border:none!important;}"
    "@media print{html,body{background:var(--card,#ffffff)!important;}}"
    "</style>"
)


def _unify_page_background(html):
    """在导出 HTML 的 </head> 前注入统一背景样式；无 </head> 时原样返回。"""
    if "</head>" in html:
        return html.replace("</head>", _BOOK_BG_STYLE + "</head>", 1)
    return html


# v3.47.1（PDF-SET）：整本书 PDF 也支持用户设定的字体 / 字号（覆盖默认 16px）
def _apply_pdf_font_css(html, font_family, font_size_pt):
    fam = (font_family or "").strip()
    if not fam:
        fam = '"Microsoft YaHei", "PingFang SC", sans-serif'
    style = (
        "<style id='mded-pdf-font'>"
        "body,.page,#editor{font-family:%s!important;"
        "font-size:%.1fpt!important;}"
        "@media print{body{font-size:%.1fpt!important;}}"
        "</style>"
        % (fam, font_size_pt, font_size_pt))
    if "</head>" in html:
        return html.replace("</head>", style + "</head>", 1)
    return html + style


# v3.48.34（PDF-LAYOUT）：导出设置 —— 纸张尺寸 / 方向 / 四边独立边距 / 缩放 / 行间距。
# 说明：printToPdf 只接受 QPageLayout（纸张 / 方向 / 边距）；缩放与行距不是原生参数，
# 必须在打印期注入 CSS（body{zoom} / line-height），两条路径（单文档 / 整本书）共用本模块。
PAPER_SIZES = [("A4", "A4"), ("A3", "A3"), ("A5", "A5"), ("B4", "B4"),
               ("B5", "B5"), ("Letter", "Letter"), ("Legal", "Legal")]

# v3.48.38（PDF-DEF）：PDF 导出最佳默认参数（美观大方、贴合中文阅读习惯）。
# · 纸张 A4 纵向、四边 20mm 等距 —— 标准且舒展；
# · 行间距 1.6（= 行高倍数 line-height，覆盖模板基准 1.8 为更紧凑精炼的中文正文）；
#   注入时强制下限 1.0，避免任意极小值导致中文行重叠（见 _apply_pdf_layout_css）。
# · 字体留空 = 跟随界面字体（Microsoft YaHei / PingFang SC，中文优先）；字号 11pt 舒适。
# · 缩放 100%（不放大缩小，页边距恒定）。
PDF_DEFAULT_OPTS = {
    "paper_size": "A4",
    "orientation": "portrait",
    "margin_top_mm": 20.0,
    "margin_right_mm": 20.0,
    "margin_bottom_mm": 20.0,
    "margin_left_mm": 20.0,
    "margin_uniform": True,
    "scale_pct": 100,
    "line_spacing": 1.6,
    "font_family": "",
    "font_size_pt": 11.0,
}

_PAPER_ENUM = {
    "A4": QPageSize.A4, "A3": QPageSize.A3, "A5": QPageSize.A5,
    "B4": QPageSize.B4, "B5": QPageSize.B5,
    "Letter": QPageSize.Letter, "Legal": QPageSize.Legal,
}


def _as_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_bool(value, default=True):
    if isinstance(value, bool):
        return value
    txt = str(value).strip().lower()
    if txt == "":
        return bool(default)
    return txt not in ("0", "false", "no", "off")


def pdf_opts(opts=None):
    """把任意来源的 opts 归一成完整设置：补默认值 + 兼容旧键 + 范围钳制。"""
    o = dict(PDF_DEFAULT_OPTS)
    if opts:
        o.update({k: v for k, v in dict(opts).items() if v is not None})
    # 兼容 v3.47.1~v3.48.33 的单一页边距键 margin_mm（四边等距）
    if opts and "margin_mm" in dict(opts) and "margin_top_mm" not in dict(opts):
        legacy = _as_float(dict(opts).get("margin_mm"), 20.0)
        for k in ("margin_top_mm", "margin_right_mm",
                  "margin_bottom_mm", "margin_left_mm"):
            o[k] = legacy
    o["paper_size"] = str(o.get("paper_size") or "A4")
    if o["paper_size"] not in _PAPER_ENUM:
        o["paper_size"] = "A4"
    o["orientation"] = ("landscape" if str(o.get("orientation")).strip().lower()
                        in ("landscape", "横向") else "portrait")
    for k in ("margin_top_mm", "margin_right_mm", "margin_bottom_mm", "margin_left_mm"):
        o[k] = max(0.0, min(100.0, _as_float(o.get(k), 20.0)))
    o["margin_uniform"] = _as_bool(o.get("margin_uniform"), True)
    if o["margin_uniform"]:
        for k in ("margin_right_mm", "margin_bottom_mm", "margin_left_mm"):
            o[k] = o["margin_top_mm"]
    o["scale_pct"] = int(round(max(25.0, min(400.0, _as_float(o.get("scale_pct"), 100.0)))))
    o["line_spacing"] = max(0.0, min(4.0, _as_float(o.get("line_spacing"), 0.0)))
    o["font_size_pt"] = max(4.0, min(72.0, _as_float(o.get("font_size_pt"), 11.0)))
    o["font_family"] = str(o.get("font_family") or "")
    return o


def opts_from_settings(settings):
    """从 QSettings 读取已保存的导出默认值（旧键 pdf/margin 作为四边回退）。"""
    legacy = _as_float(settings.value("pdf/margin", 20.0), 20.0)
    return pdf_opts({
        "paper_size": settings.value("pdf/paperSize", "A4"),
        "orientation": settings.value("pdf/orientation", "portrait"),
        "margin_top_mm": settings.value("pdf/marginTop", legacy),
        "margin_right_mm": settings.value("pdf/marginRight", legacy),
        "margin_bottom_mm": settings.value("pdf/marginBottom", legacy),
        "margin_left_mm": settings.value("pdf/marginLeft", legacy),
        "margin_uniform": settings.value("pdf/marginUniform", True),
        "scale_pct": settings.value("pdf/scalePct", 100),
        "line_spacing": settings.value("pdf/lineSpacing", PDF_DEFAULT_OPTS["line_spacing"]),
        "font_family": settings.value("pdf/fontFamily", ""),
        "font_size_pt": settings.value("pdf/fontSize", 11.0),
    })


def save_opts(settings, opts):
    """把导出设置写回 QSettings（调用方需已确认「保存为默认」）。"""
    o = pdf_opts(opts)
    settings.setValue("pdf/paperSize", o["paper_size"])
    settings.setValue("pdf/orientation", o["orientation"])
    settings.setValue("pdf/marginTop", o["margin_top_mm"])
    settings.setValue("pdf/marginRight", o["margin_right_mm"])
    settings.setValue("pdf/marginBottom", o["margin_bottom_mm"])
    settings.setValue("pdf/marginLeft", o["margin_left_mm"])
    settings.setValue("pdf/marginUniform", o["margin_uniform"])
    settings.setValue("pdf/margin", o["margin_top_mm"])   # 旧键：向后兼容
    settings.setValue("pdf/scalePct", o["scale_pct"])
    settings.setValue("pdf/lineSpacing", o["line_spacing"])
    settings.setValue("pdf/fontFamily", o["font_family"])
    settings.setValue("pdf/fontSize", o["font_size_pt"])


def pdf_page_layout(opts=None):
    """按设置构造 QPageLayout（纸张 / 方向 / 四边独立边距）。

    v3.48.34 实测坑：QPageLayout 构造的 units 参数若省略，边距会被当成 point
    处理（传 20 实际只有 7.1mm）；必须显式传 QPageLayout.Millimeter。
    """
    o = pdf_opts(opts)
    margins = QMarginsF(o["margin_left_mm"], o["margin_top_mm"],
                        o["margin_right_mm"], o["margin_bottom_mm"])
    orient = (QPageLayout.Landscape if o["orientation"] == "landscape"
              else QPageLayout.Portrait)
    return QPageLayout(QPageSize(_PAPER_ENUM[o["paper_size"]]), orient, margins,
                       QPageLayout.Millimeter)


def _pdf_page_layout(opts):
    """兼容旧签名：数字 = 四边等距毫米；dict = 完整设置。"""
    if isinstance(opts, (int, float)):
        opts = {"margin_mm": float(opts), "margin_uniform": True}
    return pdf_page_layout(opts)


def _apply_pdf_layout_css(html, opts=None):
    """打印期注入缩放 / 行距（printToPdf 无此原生参数）。

    缩放落在 body 上（实测：落在 html 上会连带缩放页边距，落在 body/.page 上
    页边距保持不变、行高严格按比例变化）。仅在 @media print 内生效。
    """
    o = pdf_opts(opts)
    rules = []
    if abs(o["scale_pct"] - 100) >= 1:
        rules.append("body{zoom:%.4f;}" % (o["scale_pct"] / 100.0))
    if o["line_spacing"] > 0:
        # 安全下限 1.0：任意极小值（如 0.1）会致中文行重叠「看不见」，
        # 强制钳到 ≥1.0 保证可读（v3.48.38）。
        _lh = max(1.0, float(o["line_spacing"]))
        rules.append("body,#editor,.page,p,li,td,th,blockquote,.blk{"
                     "line-height:%.2f!important;}" % _lh)
    if not rules:
        return html
    style = ("<style id='mded-pdf-layout'>@media print{%s}</style>"
             % "".join(rules))
    if "</head>" in html:
        return html.replace("</head>", style + "</head>", 1)
    return html + style


class BookPdfExporter:
    """有界并发的整本书 PDF 渲染器。

    用法：
        exp = BookPdfExporter(parent, EditorPage, editor_html_path, max_slots=3,
                             on_done=cb, on_progress=cb)
        exp.start(chapters, summary_dir, out_path)
    chapters: [{"abs_path","title","path","depth"}, ...]（文档顺序）。
    on_done(out_path_or_None, msg)：完成 / 失败回调。
    on_progress(done, total)：每章渲染完成回调。
    """

    def __init__(self, parent, editor_page_cls, editor_html_path, max_slots=3,
                 on_done=None, on_progress=None, opts=None):
        self.parent = parent
        self.EditorPage = editor_page_cls
        self.editor_html = editor_html_path
        self.max_slots = max(1, int(max_slots))
        self.on_done = on_done
        self.on_progress = on_progress
        # v3.47.1（PDF-SET）：页边距 / 字体 / 字号（缺省 = 不改动原渲染）
        self.opts = opts or {}

        self.chapters = []
        self.queue = []
        self.results = {}          # index -> (temp_pdf_path, page_count)
        self.slots = []
        self.finished = False
        self._total = 0
        self._done_count = 0
        self._broken = 0
        self._out_path = None
        self._timer = None

    # ----------------------------- 入口 -----------------------------
    def start(self, chapters, summary_dir, out_path):
        self._out_path = out_path
        self.summary_dir = summary_dir
        self.chapters = []
        for i, ch in enumerate(chapters):
            try:
                with open(ch["abs_path"], "r", encoding="utf-8") as f:
                    md = f.read()
            except OSError:
                md = ""
            self.chapters.append({
                "index": i,
                "abs_path": ch["abs_path"],
                "title": ch.get("title") or "",
                "path": ch.get("path") or "",
                "depth": ch.get("depth", 0),
                "base": os.path.dirname(ch["abs_path"]),
                "md": md,
            })
        self._total = len(self.chapters)
        self._done_count = 0
        self._broken = 0
        self.queue = list(range(self._total))
        self.results = {}
        if self._total == 0:
            self._finalize_error("没有可导出的章节")
            return
        n = min(self.max_slots, self._total)
        self.slots = [self._make_slot(k) for k in range(n)]
        self._timer = QTimer(self.parent)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._finalize_timeout)
        self._timer.start(10 * 60 * 1000)   # 10 分钟超时兜底（防死锁）
        for s in self.slots:
            self._load_kernel(s)

    # --------------------------- 槽构建 ---------------------------
    def _make_slot(self, k):
        kernel = QWebEngineView(self.parent)
        kernel.hide()
        kernel.setPage(self.EditorPage(kernel, self.parent))
        kset = kernel.settings()
        kset.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        kset.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        printer = QWebEngineView(self.parent)
        printer.hide()
        printer.setPage(self.EditorPage(printer, self.parent))
        pset = printer.settings()
        pset.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        pset.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        s = {"kernel": kernel, "printer": printer, "busy": False,
             "loaded": False, "broken": False, "current": None, "printer_path": None}
        kernel.loadFinished.connect(lambda ok, s=s: self._on_kernel_loaded(ok, s))
        printer.loadFinished.connect(lambda ok, s=s: self._on_printer_loaded(ok, s))
        printer.page().pdfPrintingFinished.connect(
            lambda p, ok, s=s: self._on_pdf_done(p, ok, s))
        return s

    def _load_kernel(self, s):
        s["kernel"].load(QUrl.fromLocalFile(self.editor_html))

    def _on_kernel_loaded(self, ok, s):
        if not ok:
            s["broken"] = True
            self._broken += 1
            if self._broken >= len(self.slots) and not self.finished:
                self._finalize_error("所有渲染内核加载失败，无法导出 PDF")
            return
        s["loaded"] = True
        self._pump()

    # --------------------------- 调度 ---------------------------
    def _pump(self):
        if self.finished:
            return
        for s in self.slots:
            if s["busy"] or not s["loaded"] or s.get("broken"):
                continue
            if self.queue:
                idx = self.queue.pop(0)
                self._render_chapter(s, self.chapters[idx])
            else:
                break
        # 队列非空但已无可用槽（全部损坏）→ 报错兜底
        if self.queue and all(s.get("broken") for s in self.slots) and not self.finished:
            self._finalize_error("渲染内核不可用，无法完成导出")

    def _render_chapter(self, s, ch):
        s["busy"] = True
        s["current"] = ch["index"]
        # v3.45.3（EXPORT-LINK）：渲染前注入本书链接映射 + 文档目录 ——
        # 导出 HTML 里的 [[双链]] 据此生成可点击 href（章节相对路径），
        # setDocDir 同时让相对图片路径可换算；二者缺一不可。
        links = [{"title": c["title"], "path": c["abs_path"]}
                 for c in self.chapters if c.get("abs_path")]
        code = ("window.__bookLinks = %s; window.setDocDir(%s); "
                "window.setMarkdown(%s); window.getExportHTML()"
                % (json.dumps(links, ensure_ascii=False),
                   json.dumps(ch["base"], ensure_ascii=False), _js(ch["md"])))
        # setMarkdown 同步重建后紧接 getExportHTML（同一 JS 执行上下文中取值）
        self.parent._js_view(s["kernel"], code,
                             lambda html: self._on_chapter_html(s, ch, html))

    def _on_chapter_html(self, s, ch, html):
        if self.finished:
            return
        if not isinstance(html, str) or "<html" not in html.lower():
            # 渲染失败：记一次完成，释放槽，继续
            self._fail_slot(s)
            return
        html = self.parent._inline_katex_css(html)
        # v3.44.36（BOOK-4）：整本书每页底色统一为「纸张色」（--card）。
        # 导出模板默认 html/body=画布灰（--canvas）、.page=白色卡片；章节内容较短时，
        # 章末半页在卡片之下露出画布灰 → 整本书背景忽白忽灰。统一为卡片色后，
        # 空白区与正文同底色，全书一致。
        html = _unify_page_background(html)
        # v3.47.1（PDF-SET）：应用用户设定的字体 / 字号
        _sz = self.opts.get("font_size_pt") or 0
        if _sz:
            html = _apply_pdf_font_css(
                html, self.opts.get("font_family", ""), _sz)
        # v3.48.34（PDF-LAYOUT）：缩放 / 行距（打印期 CSS）
        html = _apply_pdf_layout_css(html, self.opts)
        fd, tmp = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        s["printer_path"] = tmp
        base = QUrl.fromLocalFile(ch["base"] + "/")
        s["printer"].setHtml(html, base)

    def _on_printer_loaded(self, ok, s):
        if s.get("current") is None:
            return
        if not ok:
            self._fail_slot(s)
            return
        path = s["printer_path"]
        # v3.48.9（BOOK-PDF-FIX）：printToPdf 调用整体兜底 —— 旧版
        # `pageLayout=` 关键字在 PySide6 6.11 抛 AttributeError（不是
        # TypeError/ValueError，v3.48.4 单文档导出已修，此处漏改），
        # 异常从 Qt 槽静默逃逸 → pdfPrintingFinished 永不触发 → 全部
        # 渲染槽卡死 → 整本书导出无报错、无文件。改为位置传参 +
        # Exception 兜底；且任何 print 异常都只降级该章（_fail_slot），
        # 不再拖死整本导出。
        try:
            page = s["printer"].page()
            if self.opts:
                # v3.48.34（PDF-LAYOUT）：纸张 / 方向 / 四边独立边距
                try:
                    page.printToPdf(path, pdf_page_layout(self.opts))
                except Exception:
                    page.printToPdf(path)
            else:
                page.printToPdf(path)
        except Exception:
            _log.exception("printToPdf 调用失败（章节 %s）", s.get("current"))
            self._fail_slot(s)

    def _on_pdf_done(self, path, ok, s):
        idx = s["current"]
        s["busy"] = False
        s["current"] = None
        if ok and path and os.path.exists(path):
            try:
                from pypdf import PdfReader
                pc = len(PdfReader(path).pages)
            except Exception:
                pc = 0
            self.results[idx] = (path, pc)
        # 无论成败都计一次完成
        self._count_done()
        if not self.finished:
            self._pump()

    def _fail_slot(self, s):
        s["busy"] = False
        s["current"] = None
        self._count_done()
        if not self.finished:
            self._pump()

    def _count_done(self):
        self._done_count += 1
        if self.on_progress:
            try:
                self.on_progress(self._done_count, self._total)
            except Exception:
                pass
        if self._done_count >= self._total and not self.finished:
            self._finalize()

    # --------------------------- 收尾 ---------------------------
    def _finalize_timeout(self):
        # 超时：以已有结果尽力合并（可能不完整）
        self._finalize(partial=True)

    def _finalize(self, partial=False):
        if self.finished:
            return
        self.finished = True
        if self._timer:
            self._timer.stop()
        if not self.results:
            self._finalize_error("未能渲染任何章节，导出失败")
            return
        ordered_idx = sorted(self.results.keys())
        ordered = [self.results[i] for i in ordered_idx]
        # 每章起始页偏移
        offsets = []
        cur = 0
        for (_, pc) in ordered:
            offsets.append(cur)
            cur += pc
        # 层级书签（按章节 depth）
        bms = []
        for i, idx in enumerate(ordered_idx):
            ch = self.chapters[idx]
            title = ch["title"] or ("第 %d 章" % (idx + 1))
            bms.append((title, ch.get("depth", 0) + 1, offsets[i]))
        try:
            from pypdf import PdfReader
            n, msg = merge_book_pdfs(ordered, self._out_path, bms)
            # v3.45.3（EXPORT-LINK）：页码盖印改为保书签实现（clone_from），
            # 不再冲掉合并时写入的层级书签
            stamp_page_numbers(self._out_path)
            # 跨章 file:// 链接 → PDF 内部页跳转（阅读器不再「点了没反应」）
            page_map = {}
            for i, idx in enumerate(ordered_idx):
                ap = self.chapters[idx].get("abs_path")
                if ap:
                    key = os.path.normcase(os.path.abspath(ap)).lower()
                    if key not in page_map:
                        page_map[key] = offsets[i]
            m = linkify_pdf_links(self._out_path, page_map,
                                  out_dir=os.path.dirname(os.path.abspath(self._out_path)))
            if m:
                msg += "，%d 条链接转为可点击（页内跳转 / 相对 .html）" % m
            if partial:
                msg += "（超时，仅合并已渲染的 %d/%d 章）" % (len(ordered), self._total)
            if self.on_done:
                self.on_done(self._out_path, msg)
        except Exception as e:
            _log.exception("整书 PDF 合并失败")
            if self.on_done:
                self.on_done(None, "整书 PDF 合并失败：%s" % e)
        finally:
            self._cleanup()

    def _finalize_error(self, msg):
        if self.finished:
            return
        self.finished = True
        if self._timer:
            self._timer.stop()
        if self.on_done:
            self.on_done(None, msg)
        self._cleanup()

    def _cleanup(self):
        for s in self.slots:
            for key in ("kernel", "printer"):
                v = s.get(key)
                if v is not None:
                    try:
                        v.deleteLater()
                    except Exception:
                        pass
        self.slots = []
