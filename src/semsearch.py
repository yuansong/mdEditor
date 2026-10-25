# -*- coding: utf-8 -*-
"""本地语义搜索（SoloMD 对标 · P1-1 / SEM-1，v3.48.12）。

技术路径参照 SoloMD 的 `.solomd/embeddings.sqlite`：**离线索引 + 本地检索，
内容不外传**。差异在embedding 方案：

- SoloMD 用神经embedding（transformers.js / miniLM 级模型，随包体积大）；
- mdEditor 选 **TF-IDF 稀疏向量 + 倒排索引 + 同义词扩展**（纯标准库实现，
  零新增运行时依赖，打包体积不涨）。中文按二元组（bigram）切词、英文按
  词 + 复数还原，另内置约 50 组中英同义词——查询「搜索」可命中写「检索」
  的段落，查询「pdf」可命中写「PDF 导出」的段落。

索引位置：``%APPDATA%\\mdEditor\\semindex\\index.sqlite``
—— 位于用户数据目录、**不在项目仓库，天然不入 Git**（与 .gitignore 无关）。
增量更新：按 (路径, mtime, size) 判失效；已删除文件的索引自动清出。
环境变量 ``MDEDITOR_SEM_DB`` 可覆盖索引路径（供测试使用）。

纯核心（tokenize / expand_query / chunk_text / SemIndex / run_semantic）
不依赖 Qt，可在无界面环境直接单测；``SemIndexWorker`` 是 Qt 线程封装
（供「查找 → 全局搜索 → 语义搜索」UI 调用，带进度与中断）。
"""
import math
import os
import re
import sqlite3
import time
from datetime import datetime

# ---------------------------------------------------------------- 常量
INDEX_DIR_NAME = "semindex"
DB_NAME = "index.sqlite"
SCHEMA_VERSION = 1
# 与 sidebar.GlobalSearchPanel 一致的扫描上限（保持一致的产品行为）
SEARCH_MAX_FILES = 1500
SEARCH_MAX_SIZE = 1_500_000          # 单文件最大字节数
SEARCH_SKIP_DIRS = {".git", ".svn", "node_modules", "__pycache__", ".idea", ".vscode"}
MD_EXTS = (".md", ".markdown", ".mdown", ".txt")
CHUNK_TARGET = 600                   # 贪心合并段落的目标字符数
CHUNK_MAX_CHARS = 4000               # 单块入库文本上限（展示 + 打分共用）
MAX_CHUNKS_TOTAL = 20000             # 全库块数上限（防超大目录撑爆索引）
DEFAULT_LIMIT = 60                   # 默认返回条数（结果树一屏容量）

# 查询词 → 停用词（无主题信号，避免污染打分）
_STOP = set("""
的 了 是 在 我 你 他 她 它 这 那 和 与 及 等 或 又 也 都 就 还 但 而 被 把 让 从 到 于
之 其 此 该 各 每 为 以 着 过 吗 呢 吧 啊 哦 嗯 请 什么 怎么 怎样 如何 是不是 有没有
the a an of to and or is are was were be been being in on at for with by as it its this
that these those i you he she we they my your his her our their me him us them do does did
""".split())

# 内置同义词组（子串命中查询词即整组扩展，权重 0.85）。覆盖写作 / 检索高频词汇，
# 让"换个说法"的查询有实用召回；不追求语义模型的全覆盖。
_SYN_GROUPS = [
    ["搜索", "查找", "检索", "查询", "search", "find", "query"],
    ["导出", "输出", "另存", "export", "save as"],
    ["导入", "载入", "读取", "加载", "import", "load", "open"],
    ["图片", "图像", "照片", "插图", "配图", "image", "picture", "photo"],
    ["表格", "表单", "table", "sheet"],
    ["快捷键", "热键", "组合键", "shortcut", "hotkey"],
    ["主题", "皮肤", "外观", "界面风格", "theme", "skin"],
    ["备份", "快照", "存档", "backup", "snapshot"],
    ["撤销", "回退", "还原", "undo", "revert"],
    ["重做", "恢复", "redo"],
    ["设置", "配置", "选项", "偏好", "settings", "config", "preferences"],
    ["帮助", "手册", "指南", "教程", "help", "manual", "guide", "tutorial"],
    ["错误", "异常", "故障", "报错", "出错", "error", "bug", "exception", "fail"],
    ["性能", "速度", "卡顿", "流畅", "卡死", "performance", "speed", "lag"],
    ["安装", "部署", "安装包", "install", "setup"],
    ["更新", "升级", "新版", "版本升级", "update", "upgrade"],
    ["删除", "移除", "清除", "清理", "delete", "remove"],
    ["新增", "添加", "创建", "新建", "add", "create", "new"],
    ["修改", "编辑", "更改", "改动", "变更", "edit", "modify", "change"],
    ["邮件", "邮箱", "电子邮件", "email", "mail"],
    ["笔记", "记录", "记事", "note", "notes"],
    ["书籍", "图书", "book"],
    ["目录", "提纲", "大纲", "导航", "toc", "outline", "contents"],
    ["链接", "超链接", "网址", "双链", "link", "url"],
    ["代码", "程序", "脚本", "源码", "code", "script"],
    ["公式", "数学", "数式", " LaTeX", "math", "formula"],
    ["图表", "图形", "绘图", "画图", "chart", "graph", "diagram"],
    ["模板", "样例", "范例", "template", "sample"],
    ["打印", "印刷", "print", "pdf"],
    ["翻译", "转换", "转化", "translate", "convert"],
    ["总结", "摘要", "概述", "概要", "小结", "summary", "abstract"],
    ["问题", "疑问", "问答", "faq", "question", "problem"],
    ["窗口", "面板", "弹窗", "对话框", "window", "panel", "dialog"],
    ["字体", "字号", "字型", "font"],
    ["颜色", "色彩", "配色", "color"],
    ["加密", "密码", "安全", "加密", "encrypt", "password", "security"],
    ["同步", "云同步", "sync", "cloud"],
    ["插件", "扩展", "外挂", "plugin", "extension"],
    ["命令行", "终端", "cli", "terminal", "command"],
    ["测试", "验证", "自测", "验收", "test", "verify"],
    ["文档", "文件", "档案", "document", "doc", "file"],
    ["中文", "汉字", "简体", "chinese", "cjk"],
    ["英文", "英语", "english"],
    ["加粗", "粗体", "bold"],
    ["斜体", "倾斜", "italic"],
    ["高亮", "标记", "荧光笔", "highlight", "mark"],
    ["列表", "清单", "无序", "有序", "list"],
    ["引用", "引述", "quote", "blockquote"],
    ["脚注", "注释", "尾注", "注解", "footnote", "annotation"],
    ["待办", "任务", "复选框", "todo", "task", "checkbox"],
    ["统计", "字数", "计数", "count", "stats", "statistics"],
    ["历史", "版本历史", "历史版本", "history", "version"],
    ["合并", "对比", "差异", "diff", "merge", "compare"],
    ["主题色", "强调色", "accent"],
]

# 分词：英文数字串（允许内部 . _ + ' / -）或 CJK 连续串
_TOKEN_RE = re.compile(
    r"[a-z0-9]+(?:[._+'/\-][a-z0-9]+)*"
    r"|[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")


def _user_data_dir():
    return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "mdEditor")


def tokenize(text):
    """文本 → 词元列表。

    - 中文：连续汉字串切**二元组**（bigram；单字串保留单字）——无分词器
      依赖下对中文检索最稳的折中（「快捷键」→ 快捷 / 捷键）；
    - 英文：小写整词，长词附带复数还原别名（files → file）。
    """
    out = []
    for m in _TOKEN_RE.finditer(str(text or "").lower()):
        tok = m.group(0)
        if tok[0] >= "\u3400":                       # CJK 串
            if len(tok) == 1:
                out.append(tok)
            else:
                out.extend(tok[i:i + 2] for i in range(len(tok) - 1))
        else:
            out.append(tok)
            if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
                out.append(tok[:-1])                 # 复数还原别名
    res = []
    for t in out:
        if t in _STOP:
            continue
        if t.isdigit() and len(t) < 2:               # 单位数字噪声（列表编号等）
            continue
        res.append(t)
    return res


def expand_query(query):
    """查询词 → {词元: 权重}。原词 1.0；同义词组扩展词 0.85。"""
    q = str(query or "").strip()
    weights = {}

    def _add(tok, w):
        if not tok or tok in _STOP:
            return
        if tok.isdigit() and len(tok) < 2:
            return
        if weights.get(tok, 0.0) < w:
            weights[tok] = w

    for t in tokenize(q):
        _add(t, 1.0)
    low = q.lower()
    for group in _SYN_GROUPS:
        if not any(len(m) >= 2 and m.lower() in low for m in group):
            continue
        for m in group:
            for t in tokenize(m):
                _add(t, 0.85)
    return weights


def chunk_text(text, target=CHUNK_TARGET, max_chars=CHUNK_MAX_CHARS):
    """按空行分段，贪心合并到 target 字符数。

    返回 [(起始行号, 块文本)]；单段超长时独占一块（入库截断到 max_chars）。
    起始行号供搜索结果点击跳转。
    """
    lines = str(text or "").split("\n")
    paras = []                                       # [(start_line, para_text)]
    cur, cur_start = [], 1
    for i, ln in enumerate(lines, 1):
        if not cur:
            cur_start = i
        cur.append(ln)
        if ln.strip() == "":
            body = "\n".join(cur)
            if body.strip():
                paras.append((cur_start, body))      # 空段不入块（空文件→0 块）
            cur = []
    if cur:
        body = "\n".join(cur)
        if body.strip():
            paras.append((cur_start, body))

    chunks = []
    buf, buf_start, buf_len = [], 1, 0
    for start, p in paras:
        plen = len(p) + 1
        if buf and buf_len + plen > target:
            chunks.append((buf_start, "\n".join(buf)[:max_chars]))
            buf, buf_len = [], 0
        if not buf:
            buf_start = start
        buf.append(p)
        buf_len += plen
    if buf:
        chunks.append((buf_start, "\n".join(buf)[:max_chars]))
    return chunks


def _read_text(path):
    """读文本文件（UTF-8 BOM / UTF-8 / GBK 依次尝试），失败返回 None。"""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace")
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class SemIndex:
    """TF-IDF 倒排索引（sqlite）。增量更新 + 余弦式打分。

    线程约定：单个实例只在其创建/使用线程内使用（连接不跨线程共享）。
    """

    def __init__(self, db_path=None):
        env = os.environ.get("MDEDITOR_SEM_DB")
        self.db_path = os.path.abspath(db_path or env or
                                       os.path.join(_user_data_dir(), INDEX_DIR_NAME, DB_NAME))
        self._conn = None

    # ---------------- 连接 / 结构 ----------------
    def _connect(self):
        if self._conn is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._conn = conn
            self._ensure_schema(conn)
        return self._conn

    @staticmethod
    def _ensure_schema(conn):
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS meta (
            k TEXT PRIMARY KEY, v TEXT);
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY, root TEXT, mtime REAL, size INTEGER);
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT, idx INTEGER, line INTEGER, text TEXT);
        CREATE INDEX IF NOT EXISTS ix_chunks_path ON chunks(path);
        CREATE TABLE IF NOT EXISTS postings (
            term TEXT, chunk_id INTEGER, w REAL);
        CREATE INDEX IF NOT EXISTS ix_post_term ON postings(term);
        CREATE INDEX IF NOT EXISTS ix_post_chunk ON postings(chunk_id);
        """)
        row = conn.execute("SELECT v FROM meta WHERE k='schema'").fetchone()
        if not row:
            conn.execute("INSERT OR REPLACE INTO meta(k, v) VALUES('schema', ?)",
                         (str(SCHEMA_VERSION),))
            conn.commit()
        elif row[0] != str(SCHEMA_VERSION):
            # 结构版本不匹配：旧索引整体作废重建（代价仅一次全量索引）
            conn.executescript("""
            DELETE FROM postings; DELETE FROM chunks; DELETE FROM files;
            """)
            conn.execute("UPDATE meta SET v=? WHERE k='schema'", (str(SCHEMA_VERSION),))
            conn.commit()

    # ---------------- 扫描 ----------------
    @staticmethod
    def _iter_files(root, ext_filter=""):
        """递归收集可索引文本文件（规则与 GlobalSearchPanel.iter_files 一致）。"""
        count = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if not d.startswith(".")
                           and d not in SEARCH_SKIP_DIRS
                           and not d.lower().endswith(".assets")]
            for name in sorted(filenames):
                if name.startswith("."):
                    continue
                low = name.lower()
                if ext_filter:
                    if not low.endswith(ext_filter):
                        continue
                elif not low.endswith(MD_EXTS):
                    continue
                p = os.path.join(dirpath, name)
                try:
                    if os.path.getsize(p) > SEARCH_MAX_SIZE:
                        continue
                except OSError:
                    continue
                count += 1
                if count > SEARCH_MAX_FILES:
                    return
                yield p

    # ---------------- 索引维护 ----------------
    def update(self, root, ext="", progress=None, should_stop=None):
        """增量更新 root 目录索引。返回统计 dict。

        progress(cur, total) 在工作线程里由 worker 节流后发信号；
        should_stop() 返回 True 时尽快收尾（已完成的文件仍会落库）。
        """
        conn = self._connect()
        root_abs = os.path.abspath(root)
        files = list(self._iter_files(root_abs, ext or ""))
        existing = {r[0]: (r[1], r[2]) for r in
                    conn.execute("SELECT path, mtime, size FROM files WHERE root=?",
                                 (root_abs,)).fetchall()}
        seen, changed, removed, truncated = set(), 0, 0, False
        total = len(files)
        for i, p in enumerate(files):
            if should_stop is not None and should_stop():
                break
            try:
                st = os.stat(p)
            except OSError:
                continue
            key = os.path.abspath(p)
            seen.add(key)
            old = existing.get(key)
            if old and abs(old[0] - st.st_mtime) < 0.01 and int(old[1]) == st.st_size:
                continue                              # 未变化，跳过
            text = _read_text(p)
            if text is None:
                continue
            n_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            if n_chunks >= MAX_CHUNKS_TOTAL:
                truncated = True
                break
            self._index_file(conn, key, root_abs, st.st_mtime, st.st_size, text)
            changed += 1
            if progress is not None and (changed % 10 == 0 or i == total - 1):
                progress(i + 1, total)
        for key in existing:                          # 已删除文件清出索引
            if key not in seen:
                self._remove_file(conn, key)
                removed += 1
        conn.execute("INSERT OR REPLACE INTO meta(k, v) VALUES('updated', ?)",
                     (datetime.now().isoformat(timespec="seconds"),))
        conn.commit()
        n_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        n_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"scanned": total, "changed": changed, "removed": removed,
                "truncated": truncated, "files": n_files, "chunks": n_chunks}

    def _index_file(self, conn, path, root, mtime, size, text):
        conn.execute(
            "DELETE FROM postings WHERE chunk_id IN (SELECT id FROM chunks WHERE path=?)",
            (path,))
        conn.execute("DELETE FROM chunks WHERE path=?", (path,))
        conn.execute("DELETE FROM files WHERE path=?", (path,))
        for idx, (line_no, ctext) in enumerate(chunk_text(text)):
            cur = conn.execute(
                "INSERT INTO chunks(path, idx, line, text) VALUES(?,?,?,?)",
                (path, idx, int(line_no), ctext))
            cid = cur.lastrowid
            tf = {}
            for t in tokenize(ctext):
                tf[t] = tf.get(t, 0) + 1
            rows = [(t, cid, 1.0 + math.log(c)) for t, c in tf.items()]
            if rows:
                conn.executemany(
                    "INSERT INTO postings(term, chunk_id, w) VALUES(?,?,?)", rows)
        conn.execute(
            "INSERT OR REPLACE INTO files(path, root, mtime, size) VALUES(?,?,?,?)",
            (path, root, float(mtime), int(size)))

    def _remove_file(self, conn, path):
        conn.execute(
            "DELETE FROM postings WHERE chunk_id IN (SELECT id FROM chunks WHERE path=?)",
            (path,))
        conn.execute("DELETE FROM chunks WHERE path=?", (path,))
        conn.execute("DELETE FROM files WHERE path=?", (path,))

    def clear(self):
        """清空全部索引（设置页「重建索引」用；下次搜索自动全量重建）。"""
        conn = self._connect()
        conn.executescript("""
        DELETE FROM postings; DELETE FROM chunks; DELETE FROM files;
        """)
        conn.commit()

    # ---------------- 检索 ----------------
    def search(self, query, limit=DEFAULT_LIMIT):
        """语义检索，返回 [{path, line, text, score, pct}]（按相关度降序）。

        打分 = Σ idf(t)² · wq(t) · wd(t)（idf 于查询时按 df 现算，
        存储仅保存 tf 权重，语料变化无需重算存量）；pct 为相对最佳匹配
        的百分比（展示用）。
        """
        conn = self._connect()
        qw = expand_query(query)
        if not qw:
            return []
        n_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if not n_chunks:
            return []
        scores = {}
        for term, w in qw.items():
            rows = conn.execute(
                "SELECT chunk_id, w FROM postings WHERE term=?", (term,)).fetchall()
            if not rows:
                continue
            idf = math.log(1.0 + n_chunks / len(rows))
            coef = idf * idf * w
            for cid, wd in rows:
                scores[cid] = scores.get(cid, 0.0) + coef * wd
        if not scores:
            return []
        top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:max(1, int(limit))]
        best = top[0][1] or 1.0
        out = []
        for cid, s in top:
            if s < best * 0.05:                       # 弱相关尾部截断
                continue
            row = conn.execute(
                "SELECT path, line, text FROM chunks WHERE id=?", (cid,)).fetchone()
            if not row:
                continue
            out.append({"path": row[0], "line": int(row[1] or 1),
                        "text": row[2] or "", "score": s,
                        "pct": int(round(100.0 * s / best))})
        return out

    # ---------------- 状态 ----------------
    def stats(self):
        """索引状态（设置页展示用）。任何异常都退化为空统计，不抛。"""
        info = {"files": 0, "chunks": 0, "updated": "", "db": self.db_path, "size": 0}
        try:
            conn = self._connect()
            info["files"] = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            info["chunks"] = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            row = conn.execute("SELECT v FROM meta WHERE k='updated'").fetchone()
            info["updated"] = row[0] if row else ""
            if os.path.exists(self.db_path):
                info["size"] = os.path.getsize(self.db_path)
        except Exception:                             # noqa: BLE001
            pass
        return info

    def forget_paths(self, paths):
        """从索引中回收失效路径的条目（文件已删除 / 目录已移走）。"""
        try:
            conn = self._connect()
            for p in set(paths):
                conn.execute(
                    "DELETE FROM postings WHERE chunk_id IN "
                    "(SELECT id FROM chunks WHERE path=?)", (p,))
                conn.execute("DELETE FROM chunks WHERE path=?", (p,))
                conn.execute("DELETE FROM files WHERE path=?", (p,))
            conn.commit()
        except Exception:                             # noqa: BLE001
            pass

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:                         # noqa: BLE001
                pass
            self._conn = None


def run_semantic(root, ext, query, limit=DEFAULT_LIMIT, progress=None,
                 should_stop=None, db_path=None):
    """更新索引并检索，返回 (results, info)。worker 与单测共用入口。

    v3.48.16（SEM-FIX2）：结果三重过滤 —— 文件仍存在 / 限定在 root 下 /
    ext 匹配；失效条目顺手从索引回收（防旧目录残留命中与库膨胀）。"""
    idx = SemIndex(db_path=db_path)
    try:
        info = idx.update(root, ext=ext, progress=progress, should_stop=should_stop)
        raw = idx.search(query, limit=limit)
        root_n = os.path.normcase(os.path.normpath(root or ""))
        ext_l = (ext or "").lower()
        results, dead = [], []
        for r in raw:
            p = r.get("path") or ""
            if not os.path.isfile(p):
                dead.append(p)                       # 文件已删/目录已移走
                continue
            if root_n and not os.path.normcase(
                    os.path.normpath(p)).startswith(root_n + os.sep):
                continue                             # 不在本次搜索范围内
            if ext_l and not p.lower().endswith(ext_l):
                continue                             # 扩展名不符
            results.append(r)
        if dead:
            idx.forget_paths(dead)
        info.update(idx.stats())
        return results, info
    finally:
        idx.close()


# ---------------------------------------------------------------- Qt 线程封装
try:
    from PySide6.QtCore import QThread, Signal
    _HAS_QT = True
except Exception:                                     # noqa: BLE001
    _HAS_QT = False


if _HAS_QT:
    class SemIndexWorker(QThread):
        """后台建立 / 更新索引并执行语义检索（UI 不卡死）。"""

        progress = Signal(str)          # 索引进度文本（节流 200ms）
        finished = Signal(list, dict)   # (results, info)
        failed = Signal(str)            # 错误信息（UI 回退普通搜索）

        def __init__(self, root, ext, query, limit=DEFAULT_LIMIT, db_path=None,
                     parent=None):
            super().__init__(parent)
            self._root = root
            self._ext = ext or ""
            self._query = query
            self._limit = limit
            self._db_path = db_path

        def run(self):
            last = [0.0]

            def _cb(cur, total):
                now = time.monotonic()
                if cur < total and now - last[0] < 0.2:
                    return
                last[0] = now
                self.progress.emit(f"正在建立语义索引 {cur}/{total}…")

            try:
                results, info = run_semantic(
                    self._root, self._ext, self._query, limit=self._limit,
                    progress=_cb, should_stop=self.isInterruptionRequested,
                    db_path=self._db_path)
                self.finished.emit(results, info)
            except Exception as e:                     # noqa: BLE001
                self.failed.emit(str(e))
