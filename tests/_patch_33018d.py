# -*- coding: utf-8 -*-
"""v3.30.18d 补丁：IMG-2 —— 导出 HTML 时本地相对路径图片内嵌为 data URI。
每处替换恰好命中 1 次，失败即中止。"""
import io, sys

P = r"E:\WorkBuddy\md-editor\src\mainwindow.py"
with io.open(P, "r", encoding="utf-8") as f:
    src = f.read()

def rep(old, new, tag):
    global src
    n = src.count(old)
    if n != 1:
        print("FAIL %s: match count = %d" % (tag, n))
        sys.exit(1)
    src = src.replace(old, new)
    print("ok", tag)

# ---------- 1. export_html 接入图片内嵌 ----------
rep(r'''            self._remember_dir("html", path)
            # v3.30.11（MATH-1）：内嵌本地 katex.min.css（字体转 data URI），
            # 导出 HTML 断网可用，不再依赖 CDN
            html = self._inline_katex_css(html)
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            self.show_status(f"已导出 HTML · {path}")''',
r'''            self._remember_dir("html", path)
            # v3.30.11（MATH-1）：内嵌本地 katex.min.css（字体转 data URI），
            # 导出 HTML 断网可用，不再依赖 CDN
            html = self._inline_katex_css(html)
            # v3.30.18（IMG-2）：本地相对路径图片内嵌为 data URI ——
            # 单文件 HTML 发给别人不再裂图（默认内嵌；失败图片保留原样）
            html, n_img = self._embed_local_images(html)
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            self.show_status(f"已导出 HTML · {path}"
                             + (f"（内嵌 {n_img} 张图片）" if n_img else ""))''', "export-html")

# ---------- 2. 新增 _embed_local_images（挂在 _inline_katex_css 前） ----------
rep(r'''    def _inline_katex_css(self, html):''',
r'''    def _embed_local_images(self, html):
        """v3.30.18（IMG-2）：把导出 HTML 里的本地图片内嵌为 base64 data URI。

        - data: / http(s): 已自包含或远程，不动；
        - file:/// 绝对 URL 与相对路径都按本地文件解析（相对路径相对文档目录）；
        - 文件缺失时保留原样（与既有「找不到则跳过」原则一致）。
        返回 (html, 内嵌张数)。"""
        if not html:
            return html, 0
        import urllib.parse
        doc_dir = os.path.dirname(self.file_path) if self.file_path else ""
        count = 0

        def _repl(m):
            nonlocal count
            src = m.group(1)
            if src.startswith(("data:", "http://", "https://")):
                return m.group(0)
            path = src
            if path.lower().startswith("file:///"):
                path = urllib.parse.unquote(path[len("file:///"):])
            elif path.lower().startswith("file:"):
                path = urllib.parse.unquote(path[5:])
                path = path.lstrip("/") if os.path.isabs(path.lstrip("/")) else path
            if not os.path.isabs(path):
                if not doc_dir:
                    return m.group(0)      # 未保存文档无法解析相对路径
                path = os.path.join(doc_dir, path.replace("/", os.sep))
            try:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
            except OSError:
                return m.group(0)
            ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "gif": "image/gif", "webp": "image/webp",
                    "svg": "image/svg+xml", "bmp": "image/bmp"}.get(ext, "image/png")
            count += 1
            return m.group(0).replace(src, "data:" + mime + ";base64," + b64)

        html = re.sub(r'<img[^>]*\ssrc="([^"]+)"', _repl, html)
        return html, count

    def _inline_katex_css(self, html):''', "embed-fn")

with io.open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("ALL PATCHED")
