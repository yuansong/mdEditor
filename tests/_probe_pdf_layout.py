# -*- coding: utf-8 -*-
"""v3.48.34 探针：PDF 导出设置（PDF-LAYOUT）。

A 设置归一 pdf_opts：默认值 / 旧键 margin_mm 兼容 / 非等距保留 / 非法值钳制 / 四边一致覆盖
B QSettings 往返：save_opts → opts_from_settings 一致；旧键 pdf/margin 回退
C QPageLayout 几何：纸张尺寸 / 方向 / 四边独立边距（显式 Millimeter，20mm 必须=20mm）
D 打印期 CSS：缩放 body{zoom} / 行距 line-height / 默认不注入 / 注入点在 </head> 前
E 对话框：默认值回填、四边联动与解锁、result_opts 字段完整
F 真实 printToPdf：A3 横向幅面、40mm 边距下移、150% 行高×1.5、行距 2.5 = 字号×2.5
"""
import sys
import os
import io
import re
import json
import tempfile

os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QT_OPENGL", "software")

from PySide6.QtCore import QSettings, QUrl, QEventLoop, QTimer, QMarginsF
from PySide6.QtWidgets import QApplication

APP = QApplication.instance() or QApplication(sys.argv)

SRC = r"E:\WorkBuddy\md-editor\src"
sys.path.insert(0, SRC)

import bookexport as BE  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(detail) if detail else ""))
    if not cond:
        fails.append(name)


def close(a, b, tol=0.02):
    return abs(float(a) - float(b)) <= tol


def tmp_settings():
    d = tempfile.mkdtemp(prefix="pdfcfg_")
    return QSettings(os.path.join(d, "s.ini"), QSettings.IniFormat)


# ------------------------------------------------------------ A 设置归一
d = BE.pdf_opts()
check("A1_DEFAULT",
      d["paper_size"] == "A4" and d["orientation"] == "portrait"
      and d["margin_uniform"] is True and close(d["margin_top_mm"], 20)
      and close(d["margin_left_mm"], 20) and d["scale_pct"] == 100
      and close(d["line_spacing"], 0.0),
      "paper=%s orient=%s m=%s scale=%s line=%s" % (
          d["paper_size"], d["orientation"], d["margin_top_mm"], d["scale_pct"],
          d["line_spacing"]))

legacy = BE.pdf_opts({"margin_mm": 12.5})
check("A2_LEGACY_MARGIN",
      all(close(legacy[k], 12.5) for k in ("margin_top_mm", "margin_right_mm",
                                           "margin_bottom_mm", "margin_left_mm")),
      "m=%s" % [legacy[k] for k in ("margin_top_mm", "margin_right_mm",
                                    "margin_bottom_mm", "margin_left_mm")])

indep = BE.pdf_opts({"margin_uniform": False, "margin_top_mm": 10,
                     "margin_right_mm": 5, "margin_bottom_mm": 40,
                     "margin_left_mm": 30})
check("A3_INDEPENDENT",
      close(indep["margin_top_mm"], 10) and close(indep["margin_right_mm"], 5)
      and close(indep["margin_bottom_mm"], 40) and close(indep["margin_left_mm"], 30),
      "m=%s" % [indep[k] for k in ("margin_top_mm", "margin_right_mm",
                                   "margin_bottom_mm", "margin_left_mm")])

uni = BE.pdf_opts({"margin_uniform": True, "margin_top_mm": 18,
                   "margin_right_mm": 5, "margin_left_mm": 2})
check("A4_UNIFORM_OVERRIDES",
      close(uni["margin_right_mm"], 18) and close(uni["margin_left_mm"], 18)
      and close(uni["margin_bottom_mm"], 18), "m=%s" % uni["margin_left_mm"])

bad = BE.pdf_opts({"paper_size": "X9", "orientation": "LANDSCAPE",
                   "scale_pct": 5000, "line_spacing": -3,
                   "margin_top_mm": 999, "margin_uniform": False,
                   "margin_left_mm": -8})
check("A5_CLAMP",
      bad["paper_size"] == "A4" and bad["orientation"] == "landscape"
      and bad["scale_pct"] == 400 and close(bad["line_spacing"], 0.0)
      and close(bad["margin_top_mm"], 100) and close(bad["margin_left_mm"], 0),
      "paper=%s scale=%s top=%s left=%s" % (bad["paper_size"], bad["scale_pct"],
                                            bad["margin_top_mm"], bad["margin_left_mm"]))

# ------------------------------------------------------------ B QSettings 往返
st = tmp_settings()
saved = BE.pdf_opts({"paper_size": "B5", "orientation": "landscape",
                     "margin_uniform": False, "margin_top_mm": 12,
                     "margin_right_mm": 8, "margin_bottom_mm": 25,
                     "margin_left_mm": 33, "scale_pct": 135,
                     "line_spacing": 1.65, "font_family": "SimSun",
                     "font_size_pt": 12.5})
BE.save_opts(st, saved)
st.sync()
back = BE.opts_from_settings(QSettings(st.fileName(), QSettings.IniFormat))
keys = ("paper_size", "orientation", "margin_top_mm", "margin_right_mm",
        "margin_bottom_mm", "margin_left_mm", "scale_pct", "line_spacing",
        "font_size_pt", "font_family")
check("B1_ROUNDTRIP",
      all((str(back[k]) == str(saved[k]) if isinstance(saved[k], str)
           else close(back[k], saved[k])) for k in keys),
      "back=%s" % {k: back[k] for k in keys})

st2 = tmp_settings()
st2.setValue("pdf/margin", 15.0)
st2.sync()
leg = BE.opts_from_settings(QSettings(st2.fileName(), QSettings.IniFormat))
check("B2_LEGACY_SETTINGS",
      all(close(leg[k], 15.0) for k in ("margin_top_mm", "margin_right_mm",
                                        "margin_bottom_mm", "margin_left_mm")),
      "m=%s" % leg["margin_top_mm"])

# ------------------------------------------------------------ C QPageLayout 几何
from PySide6.QtGui import QPageLayout, QPageSize  # noqa: E402

l1 = BE.pdf_page_layout({"paper_size": "A4", "orientation": "portrait",
                         "margin_uniform": True, "margin_mm": 20})
m1 = l1.margins(QPageLayout.Millimeter)
check("C1_A4_PORTRAIT_20MM",
      l1.pageSize().id() == QPageSize.A4 and l1.orientation() == QPageLayout.Portrait
      and close(m1.left(), 20, 0.05) and close(m1.top(), 20, 0.05)
      and close(m1.right(), 20, 0.05) and close(m1.bottom(), 20, 0.05),
      "id=%s orient=%s mm=(%.2f,%.2f,%.2f,%.2f)" % (
          l1.pageSize().id(), l1.orientation(), m1.left(), m1.top(),
          m1.right(), m1.bottom()))

l2 = BE.pdf_page_layout({"paper_size": "A4", "orientation": "landscape"})
r2 = l2.fullRect(QPageLayout.Millimeter)
check("C2_LANDSCAPE_SWAPPED",
      l2.orientation() == QPageLayout.Landscape and r2.width() > r2.height()
      and close(r2.width(), 297, 1.5) and close(r2.height(), 210, 1.5),
      "rect=%.1f×%.1f" % (r2.width(), r2.height()))

l3 = BE.pdf_page_layout({"paper_uniform": False, "margin_uniform": False,
                         "margin_top_mm": 10, "margin_right_mm": 5,
                         "margin_bottom_mm": 40, "margin_left_mm": 30})
m3 = l3.margins(QPageLayout.Millimeter)
check("C3_INDEPENDENT_MARGINS",
      close(m3.top(), 10, 0.05) and close(m3.right(), 5, 0.05)
      and close(m3.bottom(), 40, 0.05) and close(m3.left(), 30, 0.05),
      "l/t/r/b=(%.1f,%.1f,%.1f,%.1f)" % (m3.left(), m3.top(), m3.right(), m3.bottom()))

l4 = BE.pdf_page_layout({"paper_size": "A3", "orientation": "portrait"})
r4 = l4.fullRect(QPageLayout.Millimeter)
check("C4_A3_SIZE", l4.pageSize().id() == QPageSize.A3
      and close(r4.width(), 297, 1.5) and close(r4.height(), 420, 1.5),
      "rect=%.1f×%.1f" % (r4.width(), r4.height()))

# ------------------------------------------------------------ D 打印期 CSS
HTML = "<html><head><meta charset='utf-8'></head><body><p>x</p></body></html>"
c1 = BE._apply_pdf_layout_css(HTML, {"scale_pct": 120, "line_spacing": 1.8})
check("D1_CSS_ZOOM_LINE",
      "zoom:1.2000" in c1 and "line-height:1.80" in c1
      and c1.index("mded-pdf-layout") < c1.index("</head>"),
      c1[c1.index("<style id='mded-pdf-layout'"):][:110])

c2 = BE._apply_pdf_layout_css(HTML, {"scale_pct": 100, "line_spacing": 0})
check("D2_NOOP_WHEN_DEFAULT", c2 == HTML, "len=%d" % len(c2))

c3 = BE._apply_pdf_layout_css(HTML, {"scale_pct": 75})
check("D3_ZOOM_ONLY", "zoom:0.7500" in c3 and "line-height" not in c3, c3[:120])

c4 = BE._apply_pdf_layout_css("<html><body>x</body></html>", {"scale_pct": 90})
check("D4_NO_HEAD_APPEND", c4.endswith("</style>") and "zoom:0.9000" in c4,
      c4[-60:])

# ------------------------------------------------------------ E 对话框
import mainwindow as MW  # noqa: E402  （必须在 QApplication 之后）

dlg = MW.PdfExportDialog(None, tmp_settings())
check("E1_DIALOG_DEFAULTS",
      dlg._paper.currentData() == "A4" and dlg._orient.currentData() == "portrait"
      and close(dlg._margins["top"].value(), 20.0)
      and close(dlg._margins["left"].value(), 20.0)
      and dlg._scale.value() == 100 and close(dlg._line.value(), 0.0)
      and dlg._uniform.isChecked(),
      "paper=%s scale=%s line=%s uniform=%s" % (
          dlg._paper.currentData(), dlg._scale.value(), dlg._line.value(),
          dlg._uniform.isChecked()))

# 四边一致：改「上」→ 其余三边联动；且右/下/左 被锁
dlg._margins["top"].setValue(31.0)
locked = (not dlg._margins["right"].isEnabled()
          and not dlg._margins["bottom"].isEnabled()
          and not dlg._margins["left"].isEnabled())
check("E2_UNIFORM_LINK",
      close(dlg._margins["right"].value(), 31.0)
      and close(dlg._margins["bottom"].value(), 31.0)
      and close(dlg._margins["left"].value(), 31.0) and locked,
      "r/b/l=%s/%s/%s locked=%s" % (dlg._margins["right"].value(),
                                    dlg._margins["bottom"].value(),
                                    dlg._margins["left"].value(), locked))

# 取消四边一致 → 解锁并可独立
dlg._uniform.setChecked(False)
dlg._margins["left"].setValue(7.5)
check("E3_UNIFORM_OFF",
      dlg._margins["left"].isEnabled() and close(dlg._margins["left"].value(), 7.5)
      and close(dlg._margins["right"].value(), 31.0),
      "left=%s right=%s" % (dlg._margins["left"].value(),
                            dlg._margins["right"].value()))

dlg._paper.setCurrentIndex(dlg._paper.findData("A5"))
dlg._orient.setCurrentIndex(dlg._orient.findData("landscape"))
dlg._scale.setValue(140)
dlg._line.setValue(1.9)
o = dlg.result_opts()
check("E4_RESULT_OPTS",
      o["paper_size"] == "A5" and o["orientation"] == "landscape"
      and close(o["margin_top_mm"], 31.0) and close(o["margin_left_mm"], 7.5)
      and close(o["margin_mm"], 31.0) and o["margin_uniform"] is False
      and o["scale_pct"] == 140 and close(o["line_spacing"], 1.9)
      and "font_size_pt" in o and "save_default" in o,
      json.dumps(o, ensure_ascii=False))

# 归一后的对话框设置可直接驱动 QPageLayout
lay_d = BE.pdf_page_layout(o)
check("E5_DIALOG_TO_LAYOUT",
      lay_d.pageSize().id() == QPageSize.A5
      and lay_d.orientation() == QPageLayout.Landscape
      and close(lay_d.margins(QPageLayout.Millimeter).left(), 7.5, 0.05),
      "id=%s orient=%s left=%.1f" % (
          lay_d.pageSize().id(), lay_d.orientation(),
          lay_d.margins(QPageLayout.Millimeter).left()))

# 主窗口静态包装与 bookexport 同源（导出链路走的就是这条）
wrapped = MW.MainWindow._apply_pdf_layout_css(HTML, {"scale_pct": 120, "line_spacing": 1.8})
check("E6_MAINWINDOW_WRAPPER", wrapped == c1, "一致=%s" % (wrapped == c1))

dlg.deleteLater()

# ------------------------------------------------------------ F 真实打印
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402
from pypdf import PdfReader  # noqa: E402

BASE_CSS = """
html,body{margin:0;padding:0;background:#fff}
.page{background:#fff;max-width:830px;margin:0 auto;padding:48px 56px}
p{font:14px/24px monospace;margin:0}
"""
LINES = "".join("<p>LINE %03d</p>" % i for i in range(1, 61))


def print_pdf(tag, opts):
    html = ("<html><head><meta charset='utf-8'><style>%s</style></head><body>"
            "<article class='page'>%s</article></body></html>" % (BASE_CSS, LINES))
    html = BE._apply_pdf_layout_css(html, opts)
    path = os.path.join(tempfile.mkdtemp(prefix="pdfe2e_"), tag + ".pdf")
    v = QWebEngineView()
    lp = QEventLoop()
    v.loadFinished.connect(lambda ok: lp.quit())
    v.setHtml(html, QUrl.fromLocalFile(os.path.expanduser("~") + "/"))
    lp.exec()
    done = QEventLoop()
    v.page().pdfPrintingFinished.connect(lambda p, ok: done.quit())
    v.page().printToPdf(path, BE.pdf_page_layout(opts))
    QTimer.singleShot(20000, done.quit)
    done.exec()
    r = PdfReader(path)
    pg = r.pages[0]
    data = pg.get_contents().get_data()
    outer = float(re.search(rb"^([\d.]+) 0 0 -?[\d.]+ 0 ", data).group(1))
    m = re.search(rb"q\s+([\d.]+) 0 0 [\d.]+ ([\d.]+) ([\d.]+) cm", data)
    scale, ty = float(m.group(1)), float(m.group(3))
    ys = {}

    def visit(text, cm, tm, fd_, fs):
        t = text.strip()
        if re.match(r"^LINE 00[1-3]$", t) and t not in ys:
            ys[t] = tm[5]

    pg.extract_text(visitor_text=visit)
    kb = sorted(ys.keys())
    gap = abs(ys[kb[1]] - ys[kb[0]]) * outer * scale if len(kb) >= 2 else -1
    v.deleteLater()
    return {"pages": len(r.pages),
            "w": round(float(pg.mediabox.width), 1),
            "h": round(float(pg.mediabox.height), 1),
            "gap": round(gap, 2),
            "top_pt": round(outer * ty, 1)}


base = print_pdf("base", {"paper_size": "A4", "orientation": "portrait",
                          "margin_uniform": True, "margin_mm": 20})
check("F1_BASE_A4", base["w"] == 595.0 and base["h"] == 841.0 and base["pages"] >= 1,
      base)

a3 = print_pdf("a3l", {"paper_size": "A3", "orientation": "landscape",
                       "margin_uniform": True, "margin_mm": 20})
check("F2_A3_LANDSCAPE", abs(a3["w"] - 1190.6) < 2 and abs(a3["h"] - 841.9) < 2,
      a3)

wide = print_pdf("m40", {"paper_size": "A4", "orientation": "portrait",
                         "margin_uniform": True, "margin_mm": 40})
check("F3_MARGIN_40MM", wide["top_pt"] - base["top_pt"] > 40,
      "20mm top=%.1fpt / 40mm top=%.1fpt (差 %.1fpt)" % (
          base["top_pt"], wide["top_pt"], wide["top_pt"] - base["top_pt"]))

zoom = print_pdf("z150", {"paper_size": "A4", "orientation": "portrait",
                          "margin_uniform": True, "margin_mm": 20,
                          "scale_pct": 150})
check("F4_SCALE_150", abs(zoom["gap"] - base["gap"] * 1.5) <= 1.0,
      "行高 %.2fpt → %.2fpt (期望 %.2f)" % (base["gap"], zoom["gap"],
                                            base["gap"] * 1.5))

lsp = print_pdf("lh25", {"paper_size": "A4", "orientation": "portrait",
                         "margin_uniform": True, "margin_mm": 20,
                         "line_spacing": 2.5})
# 行距是「倍数 × 字号」：14px × 2.5 = 35px = 26.25pt（基线 24px 行高 = 18pt）
check("F5_LINE_SPACING", abs(lsp["gap"] - 26.25) <= 0.6 and lsp["pages"] > base["pages"],
      "行高 %.2fpt（期望 26.25；基准 %.2f）页数 %d→%d" % (
          lsp["gap"], base["gap"], base["pages"], lsp["pages"]))

print("")
print("FAIL_COUNT=%d" % len(fails))
print("RESULT=" + ("OK" if not fails else "FAILED:" + ",".join(fails)))
