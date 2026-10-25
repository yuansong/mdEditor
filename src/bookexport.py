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


def _pdf_page_layout(margin_mm):
    return QPageLayout(
        QPageSize(QPageSize.A4), QPageLayout.Portrait,
        QMarginsF(margin_mm, margin_mm, margin_mm, margin_mm))


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
            _mm = self.opts.get("margin_mm") or 0
            page = s["printer"].page()
            if _mm > 0:
                try:
                    page.printToPdf(path, _pdf_page_layout(_mm))
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
