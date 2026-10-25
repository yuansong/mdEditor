# -*- coding: utf-8 -*-
"""整本书 HTML 站点导出（v3.44.36 / BOOK-5）。

按 mdBook 的组织方式，把每一章渲染为**独立** HTML 页面，另生成：

    <out>/index.html      目录 / 封面页
    <out>/style.css       共享样式
    <out>/NN-章节名.html   每章一页（带侧栏目录 + 上一章 / 下一章导航）
    <out>/images/…        章节引用的本地图片

全部静态、相对链接：既可直接用 file:// 打开，也可交给内置本地 HTTP
服务器（LocalSiteServer）以 http://127.0.0.1:<port>/index.html 访问。

渲染复用 exporters.parse_blocks / _blocks_to_xhtml（与现有 HTML 回退同源），
不依赖 QtWebEngine，离线可用；公式 / Mermaid 未位图化时以源码形式降级
（与单文件 HTML 导出的降级行为一致）。
"""
import functools
import html
import http.server
import os
import re
import shutil
import threading
import mdutil   # v3.45（BOOKLINK-E）：页面主标题锚点 slug 与编辑器同源


_CSS = """
:root{--fg:#1f2328;--muted:#6b7280;--bg:#ffffff;--side:#f7f8fa;
  --border:#e5e7eb;--accent:#0052d9;}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--fg);
  font-family:"Segoe UI","Microsoft YaHei","PingFang SC","Helvetica Neue",Arial,sans-serif;
  font-size:16px;line-height:1.8;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.layout{display:flex;min-height:100vh}
.sidebar{width:282px;flex:0 0 282px;background:var(--side);
  border-right:1px solid var(--border);padding:22px 14px;
  position:sticky;top:0;height:100vh;overflow:auto}
.sidebar .book-title{font-weight:700;font-size:16px;margin:0 6px 14px;
  padding-bottom:10px;border-bottom:1px solid var(--border);word-break:break-word}
.toc{list-style:none;margin:0;padding:0;font-size:13.5px}
.toc li{margin:2px 0}
.toc a{display:block;padding:5px 8px;border-radius:6px;color:var(--fg);opacity:.82}
.toc a:hover{background:#eef2f7;opacity:1;text-decoration:none}
.toc li.cur>a{background:#e3edfd;color:var(--accent);font-weight:600;opacity:1}
.toc li[data-depth="1"]>a{padding-left:20px}
.toc li[data-depth="2"]>a{padding-left:34px}
.toc li[data-depth="3"]>a{padding-left:48px}
.main{flex:1 1 auto;min-width:0;display:flex;justify-content:center;
  padding:42px 30px 90px}
.article{max-width:780px;width:100%}
.article h1{font-size:1.95em;line-height:1.3;margin:.15em 0 .75em;
  padding-bottom:.32em;border-bottom:1px solid var(--border)}
.article h2{font-size:1.45em;line-height:1.35;margin:1.6em 0 .55em}
.article h3{font-size:1.22em;line-height:1.4;margin:1.4em 0 .5em}
.article h4{font-size:1.08em;margin:1.2em 0 .4em}
.article h5,.article h6{font-size:1em;margin:1em 0 .4em}
.article p{margin:.72em 0;word-wrap:break-word}
.article ul,.article ol{margin:.6em 0;padding-left:1.9em}
.article li{margin:.2em 0}
.article blockquote{margin:1em 0;padding:.35em 1em;border-left:4px solid #d0d7de;
  color:var(--muted);background:#fafbfc}
.article pre{background:#f6f8fa;border:1px solid var(--border);border-radius:8px;
  padding:14px 16px;overflow:auto;font-size:13.5px;line-height:1.55}
.article code{font-family:Consolas,Menlo,"Courier New",monospace;background:#f2f3f5;
  border-radius:4px;padding:.12em .35em;font-size:.9em}
.article pre code{background:none;padding:0;font-size:1em}
.article table{border-collapse:collapse;width:100%;margin:1em 0;font-size:14.5px}
.article th,.article td{border:1px solid #d0d7de;padding:.45em .7em;text-align:left}
.article th{background:#f5f6f8;font-weight:600}
.article img{max-width:100%;height:auto}
.article hr{border:none;border-top:1px solid var(--border);margin:1.8em 0}
.article .tip{color:var(--muted);font-style:italic}
.article .mblock{display:block;margin:0 auto}
.article .imath{vertical-align:middle}
.pager{display:flex;justify-content:space-between;gap:16px;margin-top:52px;
  padding-top:20px;border-top:1px solid var(--border);font-size:14px}
.pager a{display:inline-block;padding:8px 16px;border:1px solid var(--border);
  border-radius:8px;color:var(--fg)}
.pager a:hover{border-color:var(--accent);color:var(--accent);text-decoration:none}
.pager .ph{visibility:hidden}
.cover{max-width:740px;margin:9vh auto 6vh;padding:0 28px;text-align:center}
.cover h1{font-size:2.5em;line-height:1.25;margin:.2em 0 .25em}
.cover .sub{color:var(--muted);margin-bottom:2.4em}
.cover .toc-cover{text-align:left;max-width:520px;margin:0 auto;font-size:15px}
@media(max-width:880px){
  .sidebar{display:none}
  .main{padding:26px 18px 64px}
}
"""


def _esc(s):
    return html.escape(str(s or ""))


def _page_name(i, ch):
    """章节文件名：NN-章节名.html（保留中文，去掉路径非法字符）。"""
    base = os.path.splitext(os.path.basename(ch.get("path") or ""))[0]
    base = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff\-]+", "-", base).strip("-")
    if not base:
        base = "chapter"
    return "%02d-%s.html" % (i, base)


def _chapter_title(ch, idx, fallback_h1=None):
    return (fallback_h1 or ch.get("title")
            or os.path.basename(ch.get("path") or "")
            or ("第 %d 章" % (idx + 1)))


def _sidebar(book_title, chapters, files, cur_idx):
    items = []
    for j, ch in enumerate(chapters):
        depth = min(3, max(0, int(ch.get("depth", 0) or 0)))
        cls = ' class="cur"' if j == cur_idx else ""
        title = _chapter_title(ch, j)
        items.append('<li data-depth="%d"%s><a href="%s">%s</a></li>'
                     % (depth, cls, files[j], _esc(title)))
    return ('<aside class="sidebar"><div class="book-title">%s</div>'
            '<ol class="toc">%s</ol></aside>' % (_esc(book_title), "".join(items)))


def _chapter_page(page_title, book_title, sidebar, body, prev_link, next_link):
    prev_a = ('<a class="prev" href="%s">← 上一章</a>' % prev_link
              if prev_link else '<span class="ph"></span>')
    next_a = ('<a class="next" href="%s">下一章 →</a>' % next_link
              if next_link else '<span class="ph"></span>')
    pager = '<nav class="pager">%s%s</nav>' % (prev_a, next_a)
    # v3.45（BOOKLINK-E）：页面主标题写入锚点 id（与章内首标题 slug 同源）
    h1_id = _esc(mdutil.slugify(page_title) or "section")
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>%s · %s</title><link rel="stylesheet" href="style.css"></head>'
        '<body><div class="layout">%s<main class="main"><article class="article">'
        '<h1 id="%s">%s</h1>\n%s\n%s</article></main></div></body></html>'
        % (_esc(page_title), _esc(book_title), sidebar,
           h1_id, _esc(page_title), body, pager))


def _index_page(book_title, chapters, files):
    items = []
    for j, ch in enumerate(chapters):
        depth = min(3, max(0, int(ch.get("depth", 0) or 0)))
        title = _chapter_title(ch, j)
        items.append('<li data-depth="%d"><a href="%s">%s</a></li>'
                     % (depth, files[j], _esc(title)))
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>%s</title><link rel="stylesheet" href="style.css"></head>'
        '<body><main class="cover"><h1>%s</h1>'
        '<div class="sub">共 %d 章</div>'
        '<ol class="toc toc-cover">%s</ol></main></body></html>'
        % (_esc(book_title), _esc(book_title), len(files), "".join(items)))


def _copy_images(images, out_dir):
    if not images:
        return
    idir = os.path.join(out_dir, "images")
    os.makedirs(idir, exist_ok=True)
    for name, src in images.items():
        try:
            if src and os.path.isfile(src):
                shutil.copyfile(src, os.path.join(idir, name))
        except OSError:
            pass


def build_site(info, chapters, out_dir):
    """生成整本书多页 HTML 站点。

    返回 (ok, msg, index_path)。
    """
    from exporters import parse_blocks, _blocks_to_xhtml

    book_title = (info.get("title") or "未命名书籍").strip() or "未命名书籍"
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as e:
        return False, "无法创建输出目录：%s" % e, None

    files = [_page_name(i, ch) for i, ch in enumerate(chapters, 1)]
    # v3.45（BOOKLINK-E）：标题 → 页面文件映射，供 [[双链]] 解析为跨页链接
    link_map = {}
    for j, ch in enumerate(chapters):
        title = _chapter_title(ch, j)
        if title and title not in link_map:
            link_map[title] = files[j]
        base = os.path.splitext(os.path.basename(ch.get("path") or ""))[0]
        if base and base not in link_map:
            link_map[base] = files[j]
    # v3.45.3（EXPORT-LINK）：章节 abs 路径 → 页面文件映射，供正文里的
    # [text](ch2.md) 本地链接改写为站内页面（保留 #fragment）
    file_map = {}
    for j, ch in enumerate(chapters):
        ap = ch.get("abs_path")
        if ap:
            key = os.path.normcase(os.path.abspath(ap)).lower()
            if key not in file_map:
                file_map[key] = files[j]
    all_images = {}
    pages = []          # [(page_title, body)]
    for i, ch in enumerate(chapters, 1):
        try:
            with open(ch["abs_path"], "r", encoding="utf-8") as f:
                md = f.read()
        except OSError:
            md = ""
        blocks = parse_blocks(md)
        fallback_h1 = None
        if blocks and blocks[0].get("kind") == "heading" \
                and blocks[0].get("level") == 1:
            fallback_h1 = blocks[0].get("text") or None
            blocks = blocks[1:]          # 章节标题统一由页面 <h1> 呈现，避免重复
        body = _blocks_to_xhtml(blocks, os.path.dirname(ch["abs_path"]),
                                all_images, None, None, link_map, file_map)
        pages.append((_chapter_title(ch, i - 1, fallback_h1), body))

    try:
        with open(os.path.join(out_dir, "style.css"), "w", encoding="utf-8") as f:
            f.write(_CSS)
        for idx, (page_title, body) in enumerate(pages):
            sidebar = _sidebar(book_title, chapters, files, idx)
            html_text = _chapter_page(
                page_title, book_title, sidebar, body,
                files[idx - 1] if idx > 0 else None,
                files[idx + 1] if idx + 1 < len(files) else None)
            with open(os.path.join(out_dir, files[idx]), "w", encoding="utf-8") as f:
                f.write(html_text)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(_index_page(book_title, chapters, files))
        _copy_images(all_images, out_dir)
    except OSError as e:
        return False, "写入站点文件失败：%s" % e, None

    return True, "已生成 %d 个章节页面" % len(files), \
        os.path.join(out_dir, "index.html")


class LocalSiteServer:
    """把站点目录以 http://127.0.0.1:<随机端口>/ 提供访问（后台线程）。"""

    def __init__(self, directory):
        self.directory = os.path.abspath(directory)
        self.httpd = None
        self.thread = None
        self.port = None

    def start(self):
        directory = self.directory

        class _Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):   # 静默访问日志
                pass

        handler = functools.partial(_Handler, directory=directory)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return "http://127.0.0.1:%d/index.html" % self.port

    def stop(self):
        if self.httpd is not None:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except OSError:
                pass
            self.httpd = None
