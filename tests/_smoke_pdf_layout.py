# -*- coding: utf-8 -*-
"""v3.48.34（PDF-LAYOUT）端到端冒烟：真实走「导出 PDF」链路（非单测）。

链路：MainWindow.export_pdf → PdfExportDialog(替换为假实现) → getOutline →
getExportHTML → _export_pdf_html（字体 + 缩放/行距 CSS）→ _print_pdf(QPageLayout)
→ pdfPrintingFinished → _pdf_done。

用 PDF_OPTS_JSON 环境变量覆盖导出设置（缺省 = A5 横向 + 非等距边距 + 150% + 行距 1.4）：
    set PDF_OPTS_JSON={"paper_size":"A4","scale_pct":100}
    python tests/_smoke_pdf_layout.py
断言：幅面与设置一致、多页、正文标记可提取、首行 y 大于上边距。
"""
import faulthandler
import json
import os
import sys
import tempfile

os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QT_OPENGL", "software")
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
LOG = os.path.join(HERE, "_smoke_pdf_layout.txt")
results = []
faulthandler.enable()


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + " | " + name + " | " + str(extra))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(results) + "\n")
    print(results[-1], flush=True)


from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402
from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QPageLayout  # noqa: E402

app = QApplication(sys.argv)
import mainwindow as MW  # noqa: E402
import bookexport as BE  # noqa: E402

OPTS = {
    "paper_size": "A5",
    "orientation": "landscape",
    "margin_uniform": False,
    "margin_top_mm": 12.0,
    "margin_right_mm": 8.0,
    "margin_bottom_mm": 18.0,
    "margin_left_mm": 25.0,
    "margin_mm": 12.0,
    "scale_pct": 150,
    "line_spacing": 1.4,
    "font_family": "",
    "font_size_pt": 11.0,
    "save_default": False,
}
if os.environ.get("PDF_OPTS_JSON"):
    OPTS.update(json.loads(os.environ["PDF_OPTS_JSON"]))


class FakeDialog(object):
    def __init__(self, parent, settings):
        pass

    def exec(self):
        return MW.QDialog.DialogCode.Accepted

    def result_opts(self):
        return dict(OPTS)


OUT_DIR = tempfile.mkdtemp(prefix="smokepdf_")
PDF = os.path.join(OUT_DIR, "out.pdf")
MW.PdfExportDialog = FakeDialog
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (PDF, "PDF 文件 (*.pdf)"))

win = MW.MainWindow()
win.show()


def wait(ms):
    lp = QEventLoop()
    QTimer.singleShot(ms, lp.quit)
    lp.exec()


def js(code):
    box = {"r": None}
    lp = QEventLoop()

    def cb(res):
        box["r"] = res
        lp.quit()

    QTimer.singleShot(15000, lp.quit)
    win._js_active(code, cb)
    lp.exec()
    return box["r"]


try:
    wait(3500)
    nlines = int(os.environ.get("PDF_DOC_LINES", "40"))
    md = "\n\n".join("第 %02d 段 MARKPDF 内容用于导出几何校验，重复填充若干字符。" % i
                     for i in range(1, nlines + 1))
    js("window.setMarkdown(%s)" % json.dumps(md, ensure_ascii=False))
    wait(600)
    nblk = js("document.querySelectorAll('#editor .blk').length") or 0
    check("S1_READY", nblk > 3, "blocks=%s" % nblk)

    win._pdf_opts = dict(OPTS)
    # 「导出完成」是模态弹窗（真实用户会点「完成」），无人值守下会卡死事件循环 ——
    # 唯一需要屏蔽的 UI；_pdf_done 的书签 / 链接后处理仍走真实代码。
    win._export_done = lambda *a, **k: None
    win.export_pdf()

    done = False
    for _ in range(60):
        wait(500)
        if win._pdf_view is None and os.path.exists(PDF) and os.path.getsize(PDF) > 2048:
            done = True
            break
    check("S2_PDF_WRITTEN", done,
          "exists=%s size=%s" % (os.path.exists(PDF),
                                 os.path.getsize(PDF) if os.path.exists(PDF) else -1))

    if done:
        from pypdf import PdfReader
        r = PdfReader(PDF)
        pg = r.pages[0]
        w, h = float(pg.mediabox.width), float(pg.mediabox.height)
        exp = BE.pdf_page_layout(OPTS).fullRect(QPageLayout.Point)
        check("S3_PAPER", abs(w - exp.width()) < 2.5 and abs(h - exp.height()) < 2.5,
              "mediabox=%.1f×%.1f 期望=%.1f×%.1f" % (w, h, exp.width(), exp.height()))
        check("S4_MULTIPAGE", len(r.pages) >= 2, "pages=%d" % len(r.pages))

        txt = pg.extract_text() or ""
        check("S5_CONTENT", "MARKPDF" in txt, "首段含标记=%s" % ("MARKPDF" in txt))

        ys = []

        def visit(t, cm, tm, fd_, fs):
            if "MARKPDF" in t:
                ys.append(tm[5])

        pg.extract_text(visitor_text=visit)
        top_mm = BE.pdf_opts(OPTS)["margin_top_mm"]
        check("S6_TOP_MARGIN", bool(ys) and min(ys) > top_mm * 2.83 * 0.9,
              "首行 tm.y=%s 上边距=%.1fmm" % (round(min(ys), 1) if ys else None, top_mm))
    else:
        for nm in ("S3_PAPER", "S4_MULTIPAGE", "S5_CONTENT", "S6_TOP_MARGIN"):
            check(nm, False, "无 PDF")
finally:
    fails = [x for x in results if x.startswith("FAIL")]
    print("", flush=True)
    print("FAIL_COUNT=%d" % len(fails), flush=True)
    print("RESULT=" + ("OK" if not fails else "FAILED"), flush=True)
    sys.stdout.flush()
    sys.stderr.flush()
    # Qt WebEngine 退出析构在无 GPU 环境会硬崩（与本功能无关），直接终止
    os._exit(0 if not fails else 1)
