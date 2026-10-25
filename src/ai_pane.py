# -*- coding: utf-8 -*-
"""AI 助手问答主面板。

演进：
  · v3.47.5：修复 `_bubble_html` 用 `%` 拼接被 CSS 百分号误读为格式符导致的提交崩溃，
    改用 `.format()`；Ollama 未装/未启动做即时引导。
  · v3.47.6（REQ2/3/4/5）：AI 回答以自写 `_md_to_html` 渲染为富文本（不引入外部依赖）；
    用户提问右对齐 + 浅色背景，AI 回答浅色背景并在答案下方以 `cmd://copy|insert/{idx}`
    锚点链接提供「复制 / 插入」；移除持久化复制/插入/停止按钮，生成中按 **ESC** 中止；
    placeholder 补充 ESC 提示。聊天区改用 `QTextBrowser`（`setOpenLinks(False)`）以
    支持 `anchorClicked` 路由。
  · v3.47.7：新增「清空内容」按钮（顶部状态条），带二次确认；清空后恢复初始空状态
    （含系统就绪提示），并兜底异常提示。
  · 问答仍走 ai_core.AIStreamWorker（流式增量、可中途停止、终态信号必达）；默认连接
    本地 Ollama（免 Key），模型优先级沿用 v3.47.3。
  · v3.47.9（BUBBLE-BG）：修复用户提问气泡「背景框不连续」——Qt 的 QTextBrowser 不支持
    display:inline-block，气泡退化为行内元素，而行内元素背景按「每行片段」分别绘制，
    长提问换行时行间露出白缝。改用 <table align> 承载气泡（单元格背景为单一矩形，跨行
    连续），短文本仍自然收缩并右/左对齐。
"""
import difflib
import re
import time
from datetime import datetime
from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QTextBrowser, QPushButton, QLabel, QPlainTextEdit, QMessageBox, QSplitter,
    QApplication, QDialog, QMenu, QStackedWidget, QListWidget, QListWidgetItem,
    QProgressBar, QComboBox, QRadioButton, QGroupBox, QAbstractItemView)

import ai_core
import ai_context as _ai_ctx
from ai_core import (AIStreamWorker, load_connection, read_api_key,
    connection_status, ai_log, save_connection, detect_ollama_models,
    resolve_ollama_model)
from styles import palette

# 状态点配色（与主面板一致）
_DOT = {"connected": "#2ecc71", "configured": "#f1c40f",
        "unconfigured": "#e74c3c"}


def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _now():
    return datetime.now().strftime("%H:%M")


# v3.48.18（AI-CTX）：上下文 system 提示词 —— 明确「只依据给定上下文」，
# 防止大纲模式下模型臆造未提供的段落内容。
_CTX_SYS = ("你是编辑器内置的 Markdown 写作助手。下面是当前文档的上下文，"
            "请严格依据该上下文作答与改写；上下文未提供的细节不要臆造，"
            "如需更多内容请说明你缺少哪一部分。")


def _md_to_html(text):
    """Markdown → HTML（聚焦聊天回答常见语法）。

    v3.47.8：改由共享模块 mdrender.md_to_html 渲染（含代码差异高亮，
    满足「明显高亮代码差异」需求）；本函数保留为兼容别名。"""
    from mdrender import md_to_html as _impl
    return _impl(text)


def _colors(theme):
    """返回气泡渲染所需主题色（深色主题走暗调，浅/蓝/sepia 走亮调）。"""
    p = palette(theme)
    dark = theme in ("dark", "night", "panda")
    err_bg = "#3a2222" if dark else "#fde8e8"
    err_bd = "#5c2f2f" if dark else "#f5c4b3"
    err_tx = "#ff9a9a" if dark else "#c0392b"
    # 气泡统一浅底（亮/暗主题皆然），文字用深色素以保证在浅底上的可读性；
    # 用户气泡用浅蓝、AI 气泡用中性浅灰，便于区分。
    return {
        "accent": p.get("accent", "#0052d9"),
        "text": p.get("text", "#1f2328"),
        "muted": p.get("text_muted", "#8a9099"),
        "user_bg": "#e9f1fb",
        "ai_bg": p.get("bg_soft", "#f1f3f5"),
        "ai_bd": p.get("border", "#e2e6ea"),
        "err_bg": err_bg, "err_bd": err_bd, "err_tx": err_tx,
    }


# v3.48.0（F3-b）：右键「AI」子菜单的预设提示词。
# 每个改写类操作一份独立提示词；翻译按选中文本语种动态生成（见 _translate_prompt）。
AI_PRESET_PROMPTS = {
    "polish": (
        "请对下面的文本进行润色，使其更通顺、专业、自然，保持原意与信息不变。"
        "只输出润色后的文本本身，不要附加任何解释、引号或前后缀。"),
    "condense": (
        "请精简下面的文本，去除冗余表述，保留核心信息，使其更简洁有力。"
        "只输出精简后的文本本身，不要附加任何解释、引号或前后缀。"),
    "expand": (
        "请扩写下面的文本，补充必要的细节、背景或例证，使内容更丰富完整，"
        "但不要偏离原意。只输出扩写后的文本本身，不要附加任何解释、引号或前后缀。"),
    "correct": (
        "请纠正下面文本中的错别字、语法错误和标点使用问题，保持原意与风格不变。"
        "只输出纠错后的文本本身，不要附加任何解释、引号或前后缀。"),
    "tone": (
        "请改写下面文本的语气与风格，使其更得体、更贴合表达场景"
        "（在正式与口语化之间权衡，必要时可调整句式），保持原意。"
        "只输出改写后的文本本身，不要附加任何解释、引号或前后缀。"),
}


class AIPane(QWidget):
    def __init__(self, bridge):
        super().__init__()
        self.setObjectName("aiPane")
        self.bridge = bridge  # 提供 settings() / get_selection() / replace_selection() /
                              # insert_at_caret() / open_connection() / connection_status()
        self._worker = None
        self._last_reply = ""
        self._history = []            # 多轮对话历史（最多保留 10 条，供 API）
        self._render_msgs = []        # 渲染用消息列表（{role,text,time}）
        self._stream_msg = None       # 正在流式渲染的 AI 消息（暂未定稿）
        self._streaming = False
        self._pending_transform = None   # v3.48.0（F3-c）：待挂「片段替换」的原文
        # v3.48.6（AI-LAG）：Ollama 模型列表缓存 —— 旧版每次发送都同步探测
        # （urllib timeout=3s，阻塞 UI 线程），Ollama 未运行时表现为
        # 「回车后消息迟迟不出现」。30s 内复用缓存；探测失败回退上次结果。
        self._ollama_cache = None
        self._ollama_cache_ts = 0.0
        # v3.48.10（AI-PROGRESS）：回答进度显示 —— 请求发起即显示「正在
        # 回答…」占位气泡，500ms tick 刷新「已等待/已收字数/速率」统计。
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(500)
        self._tick_timer.timeout.connect(self._on_tick)
        self._dot_n = 0
        self._stream_t0 = None
        # v3.48.11（AI-THINK）：思考过程（reasoning）—— 流式期间累积，
        # 「显示思考过程」开关开启时随气泡渲染；关闭时仅作 reasoning-only
        # 兜底（模型只吐思考不吐正文 → 用思考内容代替「空回复」报错）。
        self._stream_reasoning = ""
        self._show_think = False
        self._build_ui()
        self.refresh_status()
        # v3.47.4（REQ2）：首屏给一句就绪提示，避免空白对话区
        self._render_msgs.append({
            "role": "system",
            "text": "AI 助手已就绪。默认连接本地 Ollama，直接提问即可。",
            "time": _now()})
        self._render()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)   # v3.48.14：上下边距压缩
        root.setSpacing(10)

        # ---- 主体：上方对话区（聊天气泡，从顶端铺满）/ 下方输入区 ----
        # v3.48.11（AI-LAYOUT）：按用户要求「AI助手和输入信息框都往下移」——
        # 状态条从顶部下移至输入区上方，对话区从顶端开始铺满，控制类元素
        # （状态 / 思考开关 / 清空 / 连接 / 输入 / 发送）集中到底部。
        split = QSplitter(Qt.Vertical, self)
        split.setObjectName("aiSplit")
        split.setChildrenCollapsible(False)
        split.setHandleWidth(6)

        self._chat = QTextBrowser()
        self._chat.setObjectName("aiChat")
        self._chat.setReadOnly(True)
        # 关闭自动导航：点击锚点仅发射 anchorClicked（由 _on_anchor 按消息索引路由），
        # 不再尝试打开 cmd:// 链接（QTextBrowser 默认会尝试 setSource 跳转）。
        self._chat.setOpenLinks(False)
        split.addWidget(self._chat)

        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(5)   # v3.48.14：底部区纵向间距压缩

        # ---- 状态条：状态点 + 文本 + 「显示思考过程」开关 + 清空/连接 ----
        strow = QHBoxLayout()
        strow.setSpacing(8)
        self._dot = QLabel()
        self._dot.setFixedSize(11, 11)
        self._dot.setStyleSheet("border-radius:5.5px;background:%s" % _DOT["unconfigured"])
        self._status_text = QLabel("未配置连接")
        self._status_text.setObjectName("aiStatusText")
        self._clear_btn = QPushButton("清空内容")
        self._clear_btn.setObjectName("aiClearBtn")
        self._clear_btn.clicked.connect(self._on_clear)
        self._conn_btn = QPushButton("连接设置")
        self._conn_btn.setObjectName("aiConnBtn")
        self._conn_btn.clicked.connect(lambda: self.bridge.open_connection())
        # v3.48.11（AI-THINK）：「显示思考过程」开关 —— 位于进度/状态文本后。
        # 开启：流式期间与定稿气泡均渲染 💭 思考过程块（reasoning 实时增量）；
        # 关闭：仅当模型未产出最终回答时，用思考内容兜底（不再显示空回复报错）。
        self._think_btn = QPushButton("显示思考过程")
        self._think_btn.setObjectName("aiThinkBtn")
        self._think_btn.setCheckable(True)
        self._think_btn.setChecked(False)
        self._think_btn.setToolTip(
            "开启后实时显示模型的思考过程（reasoning）。\n"
            "关闭（默认）：请求本地模型时直接跳过思考，更快拿到最终回答。")
        self._think_btn.toggled.connect(self._on_think_toggled)
        strow.addWidget(self._dot)
        strow.addWidget(self._status_text)
        strow.addWidget(self._think_btn)
        strow.addStretch(1)
        # v3.48.14（AI-BATCH）：可审查的批量操作入口（全文 / 选中文本，先审后应用）
        self._batch_btn = QPushButton("批量处理")
        self._batch_btn.setObjectName("aiBatchBtn")
        self._batch_btn.setToolTip(
            "对整篇或选中内容按同一提示词逐块处理，先预览差异再决定是否应用"
            "（应用后 Ctrl+Z 可撤销）")
        self._batch_btn.clicked.connect(self._open_batch)
        strow.addWidget(self._batch_btn)
        strow.addWidget(self._clear_btn)
        strow.addWidget(self._conn_btn)
        bl.addLayout(strow)

        self._input = QPlainTextEdit()
        self._input.setObjectName("aiInput")
        # v3.47.6（REQ5）：在 Shift+Enter 换行提示之后补充 ESC 终止生成说明
        self._input.setPlaceholderText(
            "输入问题或指令…（Enter 发送，Shift+Enter 换行，Esc 中止生成）")
        self._input.setMinimumHeight(80)    # v3.48.14：默认高度再降 1/5（100→80），
        self._input.setMaximumHeight(180)   # 给聊天窗口让出更多空间
        self._input.installEventFilter(self)
        bl.addWidget(self._input, 1)

        # 发送行（仅「发送」；中止改由 ESC 键，见 eventFilter）
        ibrow = QHBoxLayout()
        ibrow.setSpacing(5)   # v3.48.14
        ibrow.addStretch(1)
        self._send_btn = QPushButton("发送")
        self._send_btn.setObjectName("aiSendBtn")
        self._send_btn.setDefault(True)
        ibrow.addWidget(self._send_btn)
        bl.addLayout(ibrow)
        split.addWidget(bottom)

        split.setStretchFactor(0, 3)   # 对话显示区
        split.setStretchFactor(1, 2)   # 输入区（协调比例）
        root.addWidget(split, 1)

        # v3.47.6（REQ3/REQ4）：每条 AI 答案下方以 anchor 链接提供「复制 / 插入」，
        # 取代原先持久化的按钮；锚点点击交由 _on_anchor 按消息索引路由。
        self._chat.anchorClicked.connect(self._on_anchor)
        self._send_btn.clicked.connect(self._on_send)

    def _open_batch(self):
        """v3.48.14（AI-BATCH）：打开可审查的批量操作对话框。

        先异步取当前选中文本（作为「选中文本」范围的口径），再建对话框——
        对话框非模态，构造时选中态已确定，无需后续补同步。
        """
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "提示",
                "请等待上一次请求完成（或按 Esc 中止生成）。")
            return
        self.bridge.get_selection(self._open_batch_with_sel)

    def _open_batch_with_sel(self, sel):
        dlg = AIBatchDialog(self, self.bridge, sel_text=sel or "")
        dlg.show()

    def _on_think_toggled(self, on):
        """v3.48.11（AI-THINK）：「显示思考过程」开关 —— 切换后整体重渲染，
        历史消息中已携带 reasoning 的会一并显示 / 隐藏。"""
        self._show_think = bool(on)
        self._render()

    # Enter 发送 / Shift+Enter 换行 / Esc 中止生成
    def eventFilter(self, obj, ev):
        if obj is self._input and ev.type() == QEvent.KeyPress:
            if ev.key() in (Qt.Key_Return, Qt.Key_Enter) \
                    and not (ev.modifiers() & Qt.ShiftModifier):
                self._on_send()
                return True
            # v3.47.6（REQ4）：生成过程中按 ESC 中止（取代「停止」按钮）
            if ev.key() == Qt.Key_Escape and self._worker \
                    and self._worker.isRunning():
                self._worker.cancel()
                return True
        return super().eventFilter(obj, ev)

    # ---------------- 状态条 ----------------
    def refresh_status(self):
        st = self.bridge.connection_status()
        self._dot.setStyleSheet(
            "border-radius:5.5px;background:%s" % _DOT.get(st["level"], "#95a5a6"))
        self._status_text.setText(st["text"])

    # ---------------- 聊天气泡渲染 ----------------
    def _think_html(self, reasoning, muted_bd, muted_bg, muted_tx):
        """v3.48.11（AI-THINK）：💭 思考过程块（弱化样式，位于气泡顶部）。"""
        if not (reasoning or "").strip():
            return ""
        return (
            '<div style="margin:0 0 8px 0;padding:6px 9px;'
            'border-left:3px solid {bd};background:{bg};border-radius:4px;'
            'font-size:12px;line-height:1.5;color:{tx};">'
            '<b>💭 思考过程</b>'
            '<div style="white-space:pre-wrap;margin-top:2px;">{r}</div>'
            '</div>').format(bd=muted_bd, bg=muted_bg, tx=muted_tx,
                             r=_esc(reasoning))

    def _bubble_html(self, role, text, time, idx=None, transform=False,
                     pending=False, reasoning="", reasoning_only=False):
        c = _colors(getattr(getattr(self.bridge, "_mw", None), "_theme", "light")
                    if hasattr(self.bridge, "_mw") else "light")
        esc = _esc(text)
        # v3.48.10（AI-PROGRESS）：请求中 / 流式进行中的占位气泡 ——
        # 无增量时显示「正在回答…」（点点点动画），有增量时显示内容，
        # 两种形态都附「已等待/已收字数/速率」统计行。
        # v3.48.11（AI-THINK）：开关开启且已收到思考增量时，气泡顶部先渲染
        # 💭 思考过程块（实时滚动），正文区显示「正在整理回答…」。
        if role == "assistant" and pending:
            think = (self._think_html(reasoning, c["ai_bd"], c["ai_bg"],
                                      c["muted"])
                     if self._show_think else "")
            body = _md_to_html(text) if text.strip() else ""
            if not body:
                lead = "正在整理回答" if think else "正在回答"
                body = ('<span style="color:{muted};">{lead}{dots}</span>'
                        ).format(muted=c["muted"],
                                 lead=lead, dots="." * (self._dot_n % 3 + 1))
            stats = self._stream_stats_html(c["muted"])
            return (
                '<table align="left" cellpadding="0" cellspacing="0" '
                'style="margin:8px 0;border:none;background:transparent;">'
                '<tr><td style="background:{ai_bg};border:1px solid {ai_bd};'
                'border-radius:14px;padding:10px 13px;font-size:14px;'
                'line-height:1.6;color:#1f2328;">{think}{body}{stats}</td></tr></table>'
                '<div style="text-align:left;font-size:10px;color:{muted};'
                'margin:0 0 6px 4px;">AI · {time}</div>'
            ).format(ai_bg=c["ai_bg"], ai_bd=c["ai_bd"], think=think,
                     body=body, stats=stats, muted=c["muted"], time=time)
        # 注意：CSS 内含百分号，绝不能用 % 运算符格式化（会触发
        #「unsupported format character ';'」并中断 _render → 提交后界面无响应）。
        # 统一改用 .format()，百分号为字面量安全无虞。
        #
        # v3.47.9（BUBBLE-BG）：气泡改用 <table align> 承载，不再依赖
        # display:inline-block。根因：Qt 的 QTextBrowser 不支持 inline-block，
        # 会退化为行内元素，而行内元素的背景按「每行片段」分别绘制 → 长提问
        # 换行时背景被切成多条、行间露出白缝（即用户反馈的「背景框不连续」）。
        # 表格单元格的背景是单一矩形，跨行连续；align=right/left 亦能可靠实现
        # 左右对齐，且短文本时表格自然收缩、贴合文字。
        if role == "user":
            # 用户提问：右对齐 + 浅色背景；浅底配深文字保证可读性
            return (
                '<table align="right" cellpadding="0" cellspacing="0" '
                'style="margin:8px 0;border:none;background:transparent;">'
                '<tr><td style="background:{user_bg};color:#1f2328;'
                'border:1px solid {ai_bd};border-radius:14px;'
                'padding:10px 13px;font-size:14px;line-height:1.6;'
                'white-space:pre-wrap;text-align:left;">{esc}</td></tr></table>'
                '<div style="text-align:right;font-size:10px;color:{muted};'
                'margin:0 4px 6px 0;">{time}</div>'
            ).format(user_bg=c["user_bg"], ai_bd=c["ai_bd"],
                     esc=esc, muted=c["muted"], time=time)
        if role == "assistant":
            # 以渲染后的富文本展示（Markdown→HTML），气泡下方 anchor「复制 / 插入」
            # v3.48.11（AI-THINK）：reasoning_only=模型只吐思考未吐正文 —— 顶部
            # 给警示行，且不提供「插入 / 片段替换」（思考内容不宜写回文档）；
            # 开关开启时正常消息在正文上方渲染 💭 思考过程块。
            warn = ""
            if reasoning_only:
                warn = ('<div style="margin:0 0 6px 0;font-size:12px;'
                        'color:{tx};">⚠ 该模型只返回了思考过程、未生成最终回答，'
                        '以下为其思考内容。</div>').format(tx=c["err_tx"])
            think = ""
            if not warn and self._show_think:
                think = self._think_html(reasoning, c["ai_bd"], c["ai_bg"],
                                         c["muted"])
            body = _md_to_html(text)
            anchors = ""
            if idx is not None:
                links = ['<a href="cmd://copy/{idx}">复制</a>'.format(idx=idx)]
                if not warn:
                    links.append('<a href="cmd://insert/{idx}">插入</a>'.format(idx=idx))
                    # v3.48.0（F3-c）：改写类结果额外提供「片段替换」—— 选取回复片段
                    # 与原文对比后替换原文选区（而非整段插入）。
                    if transform:
                        links.append(
                            ' · <a href="cmd://fragreplace/{idx}">片段替换</a>'
                            .format(idx=idx))
                anchors = ('<div style="margin:4px 0 0 4px;font-size:12px;">'
                           '{links}</div>').format(links=" · ".join(links))
            return (
                '<table align="left" cellpadding="0" cellspacing="0" '
                'style="margin:8px 0;border:none;background:transparent;">'
                '<tr><td style="background:{ai_bg};border:1px solid {ai_bd};'
                'border-radius:14px;padding:10px 13px;font-size:14px;'
                'line-height:1.6;color:#1f2328;">{warn}{think}{body}</td></tr></table>'
                '{anchors}'
                '<div style="text-align:left;font-size:10px;color:{muted};'
                'margin:0 0 6px 4px;">AI · {time}</div>'
            ).format(ai_bg=c["ai_bg"], ai_bd=c["ai_bd"], warn=warn,
                     think=think, body=body, anchors=anchors,
                     muted=c["muted"], time=time)
        if role == "system":
            return ('<div style="text-align:center;margin:6px 0;">'
                    '<span style="font-size:11px;color:{muted};">{esc}</span></div>'
                    ).format(muted=c["muted"], esc=esc)
        # error
        return (
            '<table align="left" cellpadding="0" cellspacing="0" '
            'style="margin:8px 0;border:none;background:transparent;">'
            '<tr><td style="background:{err_bg};border:1px solid {err_bd};'
            'border-radius:14px;padding:10px 13px;font-size:14px;'
            'line-height:1.6;color:{err_tx};white-space:pre-wrap;">'
            '{esc}</td></tr></table>'
        ).format(err_bg=c["err_bg"], err_bd=c["err_bd"],
                 err_tx=c["err_tx"], esc=esc)

    def _render(self):
        msgs = list(self._render_msgs)
        if self._stream_msg is not None:
            msgs.append(self._stream_msg)
        parts = ['<div style="font-family:\'Microsoft YaHei\',sans-serif;'
                 'font-size:14px;">']
        for idx, m in enumerate(msgs):
            # 仅已定稿的 assistant 消息挂「复制 / 插入 / 片段替换」锚点（流式消息尚未落库）
            aidx = idx if (m["role"] == "assistant"
                          and idx < len(self._render_msgs)) else None
            parts.append(self._bubble_html(
                m["role"], m["text"], m["time"], aidx,
                m.get("transform", False), m.get("pending", False),
                m.get("reasoning", ""), m.get("reasoning_only", False)))
        parts.append("</div>")
        self._chat.setHtml("".join(parts))
        self._chat.moveCursor(QTextCursor.End)

    # ---------------- 请求编排（流式） ----------------
    def _set_busy(self, b):
        self._send_btn.setEnabled(not b)

    def _connection(self):
        """读取当前连接参数（Base / Model / Key）。"""
        cfg = load_connection(self.bridge.settings())
        return cfg["base"], cfg["model"], read_api_key()

    def _get_ollama_models(self):
        """v3.48.6（AI-LAG）：带缓存的 Ollama 模型探测（替代每次发送的同步探测）。
        缓存 30s；探测失败时回退上次成功结果（避免 Ollama 未响应时每次发送
        都阻塞 UI 最长 3 秒）。"""
        now = time.time()
        if self._ollama_cache is not None and now - self._ollama_cache_ts < 30:
            return self._ollama_cache
        models = detect_ollama_models()
        if models:
            self._ollama_cache = list(models)
            self._ollama_cache_ts = now
        elif self._ollama_cache is not None:
            return self._ollama_cache
        return models

    def _run(self, messages, transform=False, orig_text="", ctx=""):
        """发起一次流式请求。

        v3.48.0（F3-c）：transform=True 时把 orig_text 暂存到 _pending_transform，
        待本次助手消息定稿后挂上「片段替换」锚点（供选取回复片段替换原文选区）。
        v3.48.18（AI-CTX）：ctx 为自适应裁剪后的文档上下文，作为 system 消息
        置于对话之前（不进 _history，避免多轮重复膨胀）。"""
        self._pending_transform = orig_text if transform else None
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "提示",
                "请等待上一次请求完成（或按 Esc 中止生成）。")
            return False
        base, model, key = self._connection()
        cfg = load_connection(self.bridge.settings())
        # 本地 Ollama：未安装 / 未启动任何模型时即时引导，避免发起注定失败的连接
        # （否则会卡在 120s 超时、界面长时间无任何反馈，表现为「提交无响应」）。
        if cfg["provider"] == "ollama":
            installed = self._get_ollama_models()
            if not installed:
                QMessageBox.warning(self, "未检测到本地模型",
                    "尚未检测到已安装的本地模型。请先下载安装 Ollama 并拉取模型"
                    "（例如 llama3.2），或在面板内「连接设置」中选择其它服务商。")
                return False
            if not model or model not in installed:
                model = resolve_ollama_model(self.bridge.settings(), installed)
                if model:
                    save_connection(self.bridge.settings(), cfg["provider"],
                                    cfg["base"], model)
        if not base or not model:
            QMessageBox.warning(self, "未配置连接",
                "尚未配置可用的服务地址与模型。请点「连接设置」打开连接面板，"
                "选择服务商并填写模型（本地 Ollama 需先安装并启动）。")
            return False
        if not key and "openai.com" in base:
            QMessageBox.warning(self, "缺少 API Key",
                "OpenAI 官方接口需要 API Key；本地 / Ollama 服务可留空。")
            return False
        self._streaming = False
        # v3.48.10（AI-PROGRESS）：请求发起即放入「正在回答…」占位消息 ——
        # 用户回车后立刻看到进度（旧版要等模型首个增量才出现气泡）。
        self._stream_msg = {"role": "assistant", "text": "", "time": _now(),
                            "pending": True}
        self._dot_n = 0
        self._stream_t0 = time.monotonic()
        self._stream_reasoning = ""   # v3.48.11（AI-THINK）：思考增量累积清零
        self._set_busy(True)
        # v3.48.14（AI-NATIVE）：「显示思考过程」关闭时对 Ollama 直接
        # think:false 主请求（原生 /api/chat），不再浪费 90s 思考。
        # v3.48.18（AI-CTX）：上下文前置为 system 消息（只作用于本次请求）
        payload = list(messages)
        if ctx:
            payload = ([{"role": "system",
                         "content": _CTX_SYS + "\n\n" + ctx}] + payload)
        self._ctx_last = ctx
        self._worker = AIStreamWorker(base, key, model, payload,
                                      disable_think=not self._think_btn.isChecked())
        self._worker.chunk.connect(self._on_chunk)
        # v3.48.11（AI-THINK）：思考过程实时增量（reasoning_content / reasoning）
        self._worker.reasoning.connect(self._on_reasoning)
        self._worker.done.connect(self._on_done)
        self._worker.cancelled.connect(self._on_cancelled)
        ai_log("chat_start", "msgs=%d" % len(messages))
        self._worker.start()
        self._tick_timer.start()
        self._render()
        # v3.48.10（AI-PROGRESS）：状态条同步显示「正在回答…」。
        # 注意：勿调用 self._set_status()——该类无此方法（会抛 AttributeError，
        # 经 sys.excepthook 记日志后虽不致界面卡死，但每次请求都记一条崩溃日志，
        # 且状态条不更新）；完成/取消时由 _on_done→refresh_status /
        # _on_cancelled→setText("已停止生成") 恢复。
        self._status_text.setText("正在回答…")
        return True

    # ---------------- v3.48.18（AI-CTX）自适应上下文 ----------------
    def _compose_ctx(self, info, target=""):
        """按文档体量 / 书籍模式生成上下文；返回 (ctx_text, meta)。

        失败一律静默降级为空上下文 —— 上下文是「省 token 的优化」，
        绝不能因为它取不到而阻断正常问答。"""
        try:
            info = info or {}
            md = info.get("md") or ""
            if not md.strip():
                return "", None
            cfg = _ai_ctx.load_config(self.bridge.settings())
            book = info.get("book") or None
            ctx, meta = _ai_ctx.build_context(
                md,
                target_text=(target or info.get("selText") or ""),
                caret_block=info.get("block"),
                threshold=cfg["threshold"],
                neighbors=cfg["neighbors"],
                book=book)
            try:
                ai_log("ctx", "%s chars %d->%d saved=%d%% book=%s"
                       % (meta.get("mode"), meta.get("chars_in", 0),
                          meta.get("chars_out", 0), meta.get("saved_pct", 0),
                          bool(book)))
            except Exception:      # noqa: BLE001
                pass
            self._ctx_meta = meta
            try:
                self._status_text.setToolTip(_ai_ctx.summarize(meta))
            except Exception:      # noqa: BLE001
                pass
            return ctx, meta
        except Exception:          # noqa: BLE001
            return "", None

    def _start_request(self, messages, transform=False, orig_text="",
                       target=""):
        """取文档上下文 → 组包 → 发起请求。

        bridge 未提供 get_document_context 时（测试桩 / 旧桥）直接走原路径，
        保证向后兼容。"""
        getter = getattr(self.bridge, "get_document_context", None)
        if getter is None:
            self._run(messages, transform=transform, orig_text=orig_text)
            return
        state = {"done": False}

        def _cb(info):
            if state["done"]:
                return
            state["done"] = True
            ctx, _meta = self._compose_ctx(info, target)
            self._run(messages, transform=transform, orig_text=orig_text,
                      ctx=ctx)

        try:
            getter(_cb)
        except Exception:          # noqa: BLE001
            self._run(messages, transform=transform, orig_text=orig_text)

    def _on_tick(self):
        """v3.48.10（AI-PROGRESS）：500ms 刷新进度气泡（点点点动画 + 统计）。"""
        self._dot_n += 1
        self._render()

    def _stream_stats_html(self, muted):
        """v3.48.10（AI-PROGRESS）：进度统计行 —— 已等待时长 / 已收字数 /
        估算速率（字每秒）。速率让用户对「还要等多久」有直观判断。"""
        if self._stream_t0 is None:
            return ""
        el = max(0.0, time.monotonic() - self._stream_t0)
        chars = len(self._stream_msg.get("text", "")) if self._stream_msg else 0
        rate = (chars / el) if el > 0.5 else 0.0
        parts = ["已等待 %ds" % int(el)]
        if chars:
            parts.append("已收 %d 字" % chars)
            if rate >= 0.5:
                parts.append("约 %d 字/秒" % round(rate))
        return ('<div style="font-size:11px;color:{muted};margin-top:6px;">'
                '{t}</div>').format(muted=muted, t=" · ".join(parts))

    def _on_chunk(self, delta):
        if not self._streaming:
            self._streaming = True
        self._stream_msg["text"] += delta
        self._render()

    def _on_reasoning(self, delta):
        """v3.48.11（AI-THINK）：模型思考增量（reasoning_content / reasoning）。
        累积到 _stream_reasoning 并挂到流式消息上；仅开关开启时才重渲染
        （关闭时静默累积，供 reasoning-only 兜底使用）。"""
        if not delta:
            return
        self._stream_reasoning += delta
        if self._stream_msg is not None:
            self._stream_msg["reasoning"] = self._stream_reasoning
        if self._show_think:
            self._render()

    def _on_done(self, ok, text):
        self._set_busy(False)
        self._tick_timer.stop()
        self.refresh_status()
        if ok:
            if self._stream_msg is not None:
                _m = self._stream_msg
                _m.pop("pending", None)
                # v3.48.6（AI-EMPTY2）：流式气泡为空白（增量全是空白字符等）时
                # 用终态全文（或空回复提示）校正；终态全文比气泡长（如 length
                # 截断提示只加在 done 全文上）时以终态为准，避免提示丢失。
                # v3.48.11（AI-EMPTY3）：正文为空但模型吐了思考过程
                # （reasoning-only，qwen3.5 实测 13850 字思考后无正文）→
                # 用思考内容兜底作为正文，并打 reasoning_only 标记，不再
                # 显示「模型返回了空回复」。
                if not _m["text"].strip():
                    if self._stream_reasoning.strip():
                        _m["text"] = self._stream_reasoning
                        _m["reasoning_only"] = True
                        _m["reasoning"] = ""
                    else:
                        _m["text"] = text or (
                            "（模型返回了空回复：可能该模型不支持流式输出、"
                            "回复被安全策略拦截，或网络中断。请重试，"
                            "必要时更换模型 / 服务商；若持续出现，"
                            "请把数据目录 logs/ai.log 反馈以便定位。）")
                elif text and len(text) > len(_m["text"]):
                    _m["text"] = text
                # v3.48.11（AI-THINK）：定稿消息携带本次思考过程（开关开启时展示）
                if not _m.get("reasoning_only"):
                    _m["reasoning"] = self._stream_reasoning
            else:
                _m = {"role": "assistant",
                      "text": text or "（模型返回了空回复：可能该模型不支持流式输出、"
                                      "回复被安全策略拦截，或网络中断。请重试，"
                                      "必要时更换模型 / 服务商；若持续出现，"
                                      "请把数据目录 logs/ai.log 反馈以便定位。）",
                      "time": _now()}
            # v3.48.0（F3-c）：改写类结果挂「片段替换」锚点（orig_text 记原文选区）
            if self._pending_transform:
                _m["transform"] = True
                _m["orig_text"] = self._pending_transform
                self._pending_transform = None
            self._render_msgs.append(_m)
            self._stream_msg = None
            self._last_reply = _m["text"]
            # v3.48.11（AI-EMPTY3）：reasoning-only 兜底后补一条系统说明
            if _m.get("reasoning_only"):
                self._render_msgs.append({
                    "role": "system",
                    "text": ("该模型只返回了思考过程、未生成最终回答，已展示其思考"
                             "内容。可开启「显示思考过程」实时查看思考过程，或"
                             "重试 / 更换模型。"),
                    "time": _now()})
            # v3.47.6（REQ3/REQ4）：不再显形持久按钮 —— 「复制 / 插入」改为每条
            # AI 答案下方的 anchor 链接（见 _bubble_html / _on_anchor）。
            self._history.append({"role": "assistant", "content": text})
            self._history = self._history[-10:]
            self._render()
            ai_log("chat_done", "len=%d" % len(text))
        else:
            msg = ("（请求中断）错误：" + text) if self._streaming else ("错误：" + text)
            self._render_msgs.append({"role": "error", "text": msg, "time": _now()})
            self._stream_msg = None
            self._render()
            ai_log("chat_error", text[:200])

    def _on_cancelled(self):
        self._set_busy(False)
        self._tick_timer.stop()
        self._status_text.setText("已停止生成")
        if self._stream_msg is not None:
            self._stream_msg.pop("pending", None)
        self._render_msgs.append({"role": "system", "text": "已停止生成。", "time": _now()})
        self._stream_msg = None
        self._render()

    # ---------------- 交互入口 ----------------
    def _on_send(self):
        q = self._input.toPlainText().strip()
        if not q:
            return
        # 先判忙，再清理输入 —— 修复 v3.47.1「先 clear/append 再 guarded return」
        # 导致的吞请求（worker 运行中再次发送被静默丢弃、连错误都不显示）
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "提示",
                "请等待上一次请求完成（或按 Esc 中止生成）。")
            return
        self._pending_transform = None   # v3.48.0（F3-c）：普通发送不作片段替换
        self._input.clear()
        self._render_msgs.append({"role": "user", "text": q, "time": _now()})
        self._render()
        self._history.append({"role": "user", "content": q})
        self._history = self._history[-10:]
        # v3.48.6（AI-LAG）：请求编排延后一拍（QTimer.singleShot(0)）——
        # 先让 setHtml 的重绘走完，用户消息立即可见；`_run` 内部的
        # 连接检查 / 模型探测不再挡在渲染前面。
        QTimer.singleShot(
            0, lambda: self._start_request(list(self._history)))

    def _on_anchor(self, url):
        """v3.47.6（REQ3/REQ4）：答案下方「复制 / 插入」锚点路由。

        url 形如 cmd://copy/3 或 cmd://insert/3，数字为消息在 _render_msgs 的索引。"""
        try:
            s = url.toString() if hasattr(url, "toString") else str(url)
        except Exception:
            s = str(url)
        s = s.replace("cmd://", "")
        parts = s.split("/")
        if len(parts) < 2:
            return
        act, idx_s = parts[0], parts[1]
        try:
            idx = int(idx_s)
        except ValueError:
            return
        if idx < 0 or idx >= len(self._render_msgs):
            return
        msg = self._render_msgs[idx]
        if msg["role"] != "assistant":
            return
        if act == "copy":
            QApplication.clipboard().setText(msg["text"])
            self._render_msgs.append(
                {"role": "system", "text": "已复制该条 AI 回复。", "time": _now()})
            self._render()
        elif act == "insert":
            # v3.48.11（AI-INS）：一键直达插入 —— 按用户要求「更简单易用」，
            # 去掉原 get_insert_plan → 预览对话框 → 确认的繁琐链路；直接调
            # window.aiInsertAtCaret（execCommand insertText，天然可撤销）。
            def _ins(ok, err):
                self._render_msgs.append(
                    {"role": "system",
                     "text": ("已插入到光标处（Ctrl+Z 可撤销）。" if ok else
                              "插入失败（%s）：请把光标放到正文编辑区内再点「插入」。"
                              % (err or "unknown")),
                     "time": _now()})
                self._render()
            self.bridge.insert_at_caret(msg["text"], _ins)
        elif act == "fragreplace":
            # v3.48.0（F3-c）：选取 AI 回复片段与原文对比，确认后替换原文选区
            self._fragment_replace(msg)

    def _on_clear(self):
        """v3.47.7：清空当前会话内容（带二次确认，防误删）。"""
        # 若正在生成，先终止，避免残留流式消息
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
        r = QMessageBox.question(
            self, "清空对话",
            "确定要清空当前会话的全部消息吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            self._render_msgs = []
            self._stream_msg = None
            self._streaming = False
            self._tick_timer.stop()
            self._last_reply = ""
            self._history = []
            # 恢复初始空状态：重新加入系统就绪提示（与 __init__ 一致）
            self._render_msgs.append({
                "role": "system",
                "text": "AI 助手已就绪。默认连接本地 Ollama，直接提问即可。",
                "time": _now()})
            self._render()
        except Exception as e:  # 清空异常兜底，避免界面假死
            QMessageBox.critical(self, "清空失败",
                "清空对话内容时发生错误：%s" % e)

    # v3.47.1（AI-BYOK）：选中即问 —— 把选中文本作为上下文预填输入区
    def ask_about_selection(self, text):
        if text:
            self._input.setPlainText(
                "以下是选中的文本：\n\"\"\"\n%s\n\"\"\"\n\n"
                "请基于以上内容回答我的问题：" % text)
            self._input.setFocus()
            self._input.moveCursor(QTextCursor.End)
        else:
            # 菜单 / 快捷键路径：编辑器侧选中需经 bridge 取回
            self.bridge.get_selection(self._got_selection_for_ask)

    def _got_selection_for_ask(self, text):
        if not text:
            self._render_msgs.append(
                {"role": "system",
                 "text": "未检测到选中文本，请先在编辑器中选中内容再问 AI。",
                 "time": _now()})
            self._render()
            return
        self.ask_about_selection(text)

    # v3.48.0（F3-b）：右键「AI」子菜单预设操作（润色/精简/扩写/纠错/翻译/改语气）
    def ai_action(self, action_key, sel_text):
        """按预设提示词把选中文本提交给 AI 改写；翻译按语种动态生成提示词。"""
        if not sel_text or not sel_text.strip():
            self._render_msgs.append(
                {"role": "system",
                 "text": "未检测到选中文本，请先在编辑器中选中内容，再使用右键「AI」操作。",
                 "time": _now()})
            self._render()
            return
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "提示",
                "请等待上一次请求完成（或按 Esc 中止生成）。")
            return
        if action_key == "translate":
            prompt = self._translate_prompt(sel_text)
        else:
            prompt = AI_PRESET_PROMPTS.get(action_key)
            if not prompt:
                self.ask_about_selection(sel_text)
                return
        user_msg = prompt + "\n\n\"\"\"\n" + sel_text + "\n\"\"\""
        self._render_msgs.append({"role": "user", "text": user_msg, "time": _now()})
        self._render()
        self._history.append({"role": "user", "content": user_msg})
        self._history = self._history[-10:]
        # transform=True：本次助手消息定稿后挂「片段替换」锚点（orig_text=原文选区）
        # v3.48.6（AI-LAG）：同 _on_send —— 渲染先行、请求延后一拍。
        QTimer.singleShot(
            0, lambda: self._start_request(list(self._history),
                                           transform=True,
                                           orig_text=sel_text,
                                           target=sel_text))

    @staticmethod
    def _translate_prompt(text):
        """v3.48.0（F3-b）：按选中文本语种决定翻译方向（中→英 / 英→中）。"""
        cjk = sum(1 for _ch in text if "一" <= _ch <= "鿿")
        if cjk > len(text.strip()) * 0.3:
            return ("请将下面的中文文本翻译成英文，要求准确、自然、符合英文表达习惯。"
                    "只输出译文本身，不要附加任何解释、引号或前后缀。")
        return ("请将下面的英文文本翻译成中文，要求准确、自然、通顺。"
                "只输出译文本身，不要附加任何解释、引号或前后缀。")

    # v3.48.0（F3-c）：片段对比替换
    def _fragment_replace(self, msg):
        if msg.get("role") != "assistant":
            return
        orig = msg.get("orig_text", "")
        reply = msg.get("text", "")
        # v3.48.11（AI-MERGE2）：MergeDialog 式双栏差异合并对话框（replace only）
        dlg = AIFragmentDialog(self, self.bridge,
                               orig_text=orig, reply_text=reply)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_text = dlg.get_result_text()
            if not new_text.strip():
                self._render_msgs.append(
                    {"role": "system",
                     "text": "已取消：合并结果为空，未替换原文。", "time": _now()})
                self._render()
                return

            # v3.48.5（AI-REDESIGN）：带 orig 快照交 JS 预检（AI 往返期间原文
            # 被改 → stale-selection），并按错误码细分提示，不再笼统报失败。
            def _done(ok, err=""):
                # v3.48.18（FRAG-MSG）：错误码细分 —— 每类失败都给「下一步怎么做」
                # 的明确回退提示，不再笼统一句「替换失败」。
                if ok:
                    tip = "已用所选 AI 片段替换原文选区（Ctrl+Z 可撤销）。"
                elif err in ("not-found", "stale-selection"):
                    tip = ("替换未执行：未能在当前文档中定位到原文片段。"
                           "常见原因：原文在生成期间被修改，或选区含源码态格式标记。"
                           "回退建议：① 在编辑器中重新选中目标段落后再点「片段替换」；"
                           "② 或直接点该条回复下方的「插入」，把结果插入光标处。")
                elif err == "stale-dom":
                    tip = ("替换未执行：原选区所在的文档结构已变动（例如切换了视图）。"
                           "回退建议：重新选中原文后重试，或改用「插入」。")
                elif err in ("no-caret", "no-host"):
                    tip = ("替换未执行：未定位到可编辑正文区。"
                           "回退建议：先点击正文进入编辑状态，再重试。")
                elif err == "bad-order":
                    tip = ("替换未执行：选区跨越了非连续的文档块（可能含表格 / 嵌套块）。"
                           "回退建议：缩小选区范围，或分多次替换。")
                elif err == "empty":
                    tip = "替换未执行：合并结果为空。请在下方结果框补充内容后再确认。"
                else:
                    tip = ("替换失败（%s）：可重试；若反复失败，请重新选中原文"
                           "后再点「片段替换」，或改用「插入」。" % (err or "unknown"))
                self._render_msgs.append(
                    {"role": "system", "text": tip, "time": _now()})
                self._render()

            self.bridge.replace_selection(new_text, _done, orig_text=orig)



class AIFragmentDialog(QDialog):
    """v3.48.11（AI-MERGE2）：「AI 片段替换」—— 参照历史版本「合并两个版本」
    （MergeDialog）的双栏差异合并交互（用户要求按既有方式实现）。

    左栏=原文选区（A=旧，差异行红底），右栏=AI 回复（B=新，差异行绿底）；
    行级 diff（difflib）分段渲染，每段内容包进 cmd://seg/{idx}/{side} 锚点，
    双击 / 右键经 anchorAt 反查段索引（与文档块结构无关，杜绝块号漂移）。
    交互（作用于差异段）：
      · **双击**某侧差异行 → 采用该侧该段（选中多行后双击则整组采纳）；
      · 选中若干行 → **右键「采用所选」**；
      · 右键「恢复默认」→ 该段回到默认取舍（采用 AI 回复）。
    下方合并结果**默认为 AI 回复全文**：未裁决差异段黄底（默认取 AI）、
    采用左侧（原文）红底、采用右侧（AI）绿底；可直接手动编辑，采纳操作
    按段原位替换、不影响其余手工修改。
    「确认替换」经 bridge.replace_selection 写回（原文一致性预检 +
    v3.48.10 全文重新定位兜底，杜绝「替换失败、没有真正修改原文」）。
    v3.48.11：insert 模式取消（AI 插入改一键直达，见 AIPane._on_anchor），
    本对话框只服务片段替换；「选中片段」按钮 / 送入下方交互全部移除。"""

    def __init__(self, parent, bridge, orig_text="", reply_text=""):
        super().__init__(parent)
        self.setObjectName("aiFragDlg")
        self.setWindowTitle("AI 片段替换")
        self._bridge = bridge
        self._orig_text = orig_text or ""
        self._reply_text = reply_text or ""
        self._segs = []
        self._same = 0            # 相同行数（状态行展示用）
        self._seg_cur = []        # 各段起点游标（末位=文档尾哨兵），采纳时原位替换
        self._press_seg = None    # 鼠标按下时所在差异段
        self._press_sel = None    # 鼠标按下时的选区范围（多行选择）
        self.setModal(True)
        self.resize(940, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(8)

        tip = QLabel(
            "将用「下方合并结果」替换你选中的原文。左为原文选区、右为 AI 回复，"
            "双击某侧差异行即采用该侧内容；右键「采用所选 / 恢复默认」。"
            "合并结果可直接编辑，确认后替换原文选区。", self)
        tip.setObjectName("pageHint")
        tip.setWordWrap(True)
        root.addWidget(tip)

        # ---- 栏目标题（与左右对比框对齐）----
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        la = QLabel("原文选区（A）", self)
        la.setObjectName("pageHint")
        lb = QLabel("AI 回复（B）", self)
        lb.setObjectName("pageHint")
        hdr.addWidget(la, 1)
        hdr.addWidget(lb, 1)
        root.addLayout(hdr)

        # ---- 上方：左右两个对比框（A=原文红底 / B=AI 绿底），行级比较视图 ----
        self.pane_a = QTextBrowser(self)
        self.pane_a.setObjectName("aiFragPaneA")
        self.pane_a.setReadOnly(True)
        self.pane_a.setOpenLinks(False)
        self.pane_b = QTextBrowser(self)
        self.pane_b.setObjectName("aiFragPaneB")
        self.pane_b.setReadOnly(True)
        self.pane_b.setOpenLinks(False)
        # v3.48.3（F1 修）：QTextBrowser 是 QAbstractScrollArea，鼠标 / 右键
        # 事件实际投递给 viewport()（装在 pane 本体上收不到，表现为无反应）
        self.pane_a.viewport().installEventFilter(self)
        self.pane_b.viewport().installEventFilter(self)
        top = QSplitter(Qt.Horizontal, self)
        top.setHandleWidth(6)
        top.setChildrenCollapsible(False)
        top.addWidget(self.pane_a)
        top.addWidget(self.pane_b)
        top.setStretchFactor(0, 1)
        top.setStretchFactor(1, 1)
        root.addWidget(top, 3)

        # ---- 状态行 ----
        self._stat = QLabel("", self)
        self._stat.setObjectName("pageHint")
        self._stat.setWordWrap(True)
        root.addWidget(self._stat)

        # ---- 下方：合并结果（默认 AI 回复，可编辑，差异按背景色标记）----
        mh = QLabel(
            "合并结果（默认 AI 回复 · 可编辑）：黄底=未裁决差异（默认取 AI），"
            "红底=采用左侧（原文），绿底=采用右侧（AI）。", self)
        mh.setObjectName("pageHint")
        mh.setWordWrap(True)
        root.addWidget(mh)
        self.pane_merge = QTextEdit(self)
        self.pane_merge.setObjectName("aiFragMerge")
        self.pane_merge.setAcceptRichText(False)
        root.addWidget(self.pane_merge, 2)

        # ---- 按钮行 ----
        brow = QHBoxLayout()
        brow.addStretch(1)
        self.b_all_left = QPushButton("全部采用左(原文)", self)
        self.b_all_right = QPushButton("全部采用右(AI)", self)
        b_cancel = QPushButton("取消", self)
        b_ok = QPushButton("确认替换", self)
        b_ok.setObjectName("primaryBtn")
        b_ok.setDefault(True)
        self.b_all_left.clicked.connect(
            lambda _=False: self._adopt("A", range(len(self._segs))))
        self.b_all_right.clicked.connect(
            lambda _=False: self._adopt("B", range(len(self._segs))))
        b_cancel.clicked.connect(self.reject)
        b_ok.clicked.connect(self.accept)
        for b in (self.b_all_left, self.b_all_right, b_cancel, b_ok):
            brow.addWidget(b)
        root.addLayout(brow)

        self._prepare_diff()

    def get_result_text(self):
        """确认写回所用文本（合并结果框当前内容）。"""
        return self.pane_merge.toPlainText().rstrip("\n")

    # ---------- 段拆分（2-way，行级，Markdown 容错）----------
    @staticmethod
    def _md_key(line):
        """行级归一键：剥离 Markdown 标记与全部空白。

        v3.48.18（FRAG-MD）：渲染态选区文本不含 ** / ` / # 等标记，而 AI 回复
        通常带标记；直接逐字 diff 会把「仅格式不同」的行全判为差异 ——
        用户看到的是一片红绿、且默认全部取 AI 侧，等价于「整段覆盖」，
        反复采纳还会出现重复内容。改为按可见文本比较，格式差异收敛为
        相同的 equal 段（输出统一取 B=AI 侧，保留其 Markdown 格式）。"""
        from mdrender import md_to_plain
        return re.sub(r"\s+", "", md_to_plain(line or ""))

    @classmethod
    def _build_segs(cls, a_lines, b_lines):
        """返回 (段列表, 相同行数, 差异块数)。段：
        · kind=equal：两版**可见内容**一致（可能 Markdown 标记不同）；
          text 取 B（AI）侧，text_a / text_b 保留两侧原文备查。
        · kind=diff：a / b 两侧文本与当前取舍 choice —— 初始一律 None
          （未裁决）：结果框默认取 AI 回复(B)，B 无内容（仅原文有的行）
          则默认排除。"""
        a_keys = [cls._md_key(l) for l in a_lines]
        b_keys = [cls._md_key(l) for l in b_lines]
        sm = difflib.SequenceMatcher(a=a_keys, b=b_keys, autojunk=False)
        segs, same, conflicts = [], 0, 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                segs.append({
                    "kind": "equal",
                    "text": "\n".join(b_lines[j1:j2]),
                    "text_a": "\n".join(a_lines[i1:i2]),
                    "text_b": "\n".join(b_lines[j1:j2]),
                })
                same += i2 - i1
            else:
                a_txt = "\n".join(a_lines[i1:i2])
                b_txt = "\n".join(b_lines[j1:j2])
                segs.append({"kind": "diff", "a": a_txt, "b": b_txt,
                             "choice": None})
                conflicts += 1
        return segs, same, conflicts

    def _prepare_diff(self):
        a_lines = self._orig_text.split("\n")
        b_lines = self._reply_text.split("\n")
        self._segs, self._same, conflicts = self._build_segs(a_lines, b_lines)
        self._render_panes()
        self._refresh_result()
        self._update_stat()

    @staticmethod
    def _esc_block(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))

    def _seg_at(self, obj, pos):
        """把文档内位置映射到段索引（按块号收敛；仅作 anchorAt 失效时的
        回退 —— 块号与段索引在空 equal 段 / 多行段下不保证对齐）。"""
        blk = obj.document().findBlock(pos)
        i = blk.blockNumber() if blk.isValid() else 0
        if i < 0:
            i = 0
        if i >= len(self._segs):
            i = len(self._segs) - 1
        return i

    def _seg_from_pos(self, pane, pos):
        """viewport 坐标 → 段索引。优先 anchorAt 反查该段渲染时埋下的
        cmd://seg/{idx}/{side} href（与块结构无关，绝对可靠）；无锚点时
        回退块号映射。"""
        try:
            href = pane.anchorAt(pos)
        except Exception:
            href = ""
        if href and href.startswith("cmd://seg/"):
            try:
                return int(href[len("cmd://seg/"):].split("/")[0])
            except (ValueError, IndexError):
                pass
        try:
            return self._seg_at(pane, pane.cursorForPosition(pos).position())
        except Exception:
            return 0

    def _render_panes(self):
        """Beyond Compare 式行级比较视图 —— 左（A=原文）差异行红底、
        右（B=AI）差异行绿底、空白侧灰底占位；当前采用的侧打 ✓。
        段内换行用 <br> 折行。每段内容包进 cmd://seg/{idx}/{side} 锚点，
        点击 / 右键经 anchorAt 反查段索引（块号映射在「空 equal 段不产块」
        「<br> 产块数≠段数」时必然漂移）；空 equal 段渲染 &nbsp; 占位。"""
        for side, pane in (("A", self.pane_a), ("B", self.pane_b)):
            parts = ['<div style="font-family:Microsoft YaHei,sans-serif;'
                     'font-size:13px;line-height:1.55;">']
            for idx, s in enumerate(self._segs):
                href = "cmd://seg/%d/%s" % (idx, side)
                if s["kind"] == "equal":
                    body = (self._esc_block(s["text"]).replace("\n", "<br>")
                            if s["text"] else "&nbsp;")
                    parts.append(
                        '<div style="padding:1px 8px;margin:0;'
                        'white-space:pre-wrap;">'
                        '<a href="%s" style="text-decoration:none;'
                        'color:#1f2328;">%s</a></div>' % (href, body))
                    continue
                txt = s["a"] if side == "A" else s["b"]
                chosen = (s["choice"] == side)
                if txt:
                    bg = "#ffe5e5" if side == "A" else "#e6ffec"
                    bd = "#cf222e" if side == "A" else "#1a7f37"
                    color = "#1f2328"
                    style = ""
                else:
                    bg, bd = "#f2f4f7", "#d0d7de"
                    txt = "（此侧无内容）"
                    color, style = "#8c959f", "font-style:italic;"
                mark = (' <span style="color:#1a7f37;font-weight:bold;">\u2713</span>'
                        if chosen else "")
                parts.append(
                    '<div style="padding:2px 8px;margin:1px 0;'
                    'border-left:3px solid %s;background:%s;'
                    'white-space:pre-wrap;%s">'
                    '<a href="%s" style="text-decoration:none;color:%s;">%s%s</a></div>'
                    % (bd, bg, style, href, color,
                       self._esc_block(txt).replace("\n", "<br>"), mark))
            parts.append("</div>")
            pane.setHtml("".join(parts))

    def _adopt(self, side, segs):
        """把 segs 中各差异段的取舍置为 side，并按段原位替换结果框内容
        （QTextCursor 锚点随编辑自动平移，其余段的手工修改不受影响）。"""
        changed = []
        for k in segs:
            if not (0 <= k < len(self._segs)):
                continue
            s = self._segs[k]
            if s["kind"] != "diff":
                continue
            if s["choice"] != side:
                s["choice"] = side
                changed.append(k)
        if changed:
            self._render_panes()
            for k in changed:
                self._replace_result_seg(k)
            self._update_stat()

    def _reset_seg(self, k):
        """右键「恢复默认」：该段回到默认取舍（采用 AI 回复）。"""
        if not (0 <= k < len(self._segs)):
            return
        s = self._segs[k]
        if s["kind"] != "diff" or s["choice"] is None:
            return
        s["choice"] = None
        self._render_panes()
        self._replace_result_seg(k)
        self._update_stat()

    def _segs_from_selection(self, obj):
        """当前选区覆盖到的段索引列表；无选区返回 None。
        选区两端经 cursorRect 定位后走 anchorAt 反查，不依赖块号。"""
        cur = obj.textCursor()
        if not cur.hasSelection():
            return None
        c1 = QTextCursor(cur)
        c1.setPosition(cur.selectionStart())
        c2 = QTextCursor(cur)
        c2.setPosition(cur.selectionEnd())
        lo = self._seg_from_pos(obj, obj.cursorRect(c1).center())
        hi = self._seg_from_pos(obj, obj.cursorRect(c2).center())
        if lo > hi:
            lo, hi = hi, lo
        return list(range(lo, hi + 1))

    def _segs_from_event(self, obj):
        """右键 / 双击目标段：有选区取选区覆盖段，否则取按下位置所在段。"""
        sel = self._segs_from_selection(obj)
        if sel:
            return sel
        return [self._press_seg] if self._press_seg is not None else []

    def _ctx_menu(self, obj, side, ev):
        """对比框右键菜单 ——「采用所选（该侧）/ 恢复默认（采用 AI）」。"""
        gpos = (ev.globalPos() if hasattr(ev, "globalPos")
                else ev.globalPosition().toPoint())
        menu = QMenu(self)
        act_adopt = menu.addAction(
            "采用所选（%s）" % ("左侧=原文" if side == "A" else "右侧=AI"))
        act_reset = menu.addAction("恢复默认（采用 AI）")
        chosen = menu.exec(gpos)
        if chosen is act_adopt:
            self._adopt(side, self._segs_from_event(obj))
        elif chosen is act_reset:
            for k in self._segs_from_event(obj):
                self._reset_seg(k)

    def _update_stat(self):
        diffs = [s for s in self._segs if s["kind"] == "diff"]
        n = len(diffs)
        resolved = sum(1 for s in diffs if s["choice"] is not None)
        if n == 0:
            txt = "原文与 AI 回复内容完全一致，无需合并。"
        else:
            txt = ("相同 %d 行 · 差异 %d 处（已裁决 %d）　—　"
                   "双击左/右差异行采用该侧；或选中多行右键「采用所选」。"
                   % (self._same, n, resolved))
        if not self._orig_text.strip():
            txt += ("　⚠ 未捕获到原文选区：确认替换时会要求你重新选中原文。")
        self._stat.setText(txt)

    def _replace_result_seg(self, k):
        """按段原位替换结果框内容：红底=采用左、绿底=采用右、黄底=未裁决
        （默认 AI）。段外手工内容不受影响。QTextCursor 在插入点会被推着走
        （且被删区间内的游标会收敛到区间起点），故编辑后按旧位置显式复位
        所有段游标。"""
        if not (0 <= k < len(self._segs)) or not self._seg_cur:
            return
        s = self._segs[k]
        if s["kind"] != "diff":
            return
        if s["choice"] == "A":
            txt, bg = s["a"], "#ffe5e5"
        elif s["choice"] == "B":
            txt, bg = s["b"], "#e6ffec"
        else:
            txt, bg = s["b"], "#fff3cd"   # 未裁决：默认取 AI(B)
        doc = self.pane_merge.document()
        old_pos = [c.position() for c in self._seg_cur]
        start = old_pos[k]
        end = old_pos[k + 1] if k + 1 < len(self._seg_cur) else doc.characterCount()
        cur = QTextCursor(doc)
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.KeepAnchor)
        if txt:
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(bg))
            cur.insertText(txt + "\n", fmt)
        else:
            cur.removeSelectedText()
        # 复位段游标：k → start；k 之后各段 → start + 新长度 + (旧位置 - end)
        newlen = (len(txt) + 1) if txt else 0
        for j in range(k, len(self._seg_cur)):
            if j == k:
                self._seg_cur[j].setPosition(start)
            else:
                self._seg_cur[j].setPosition(
                    start + newlen + max(0, old_pos[j] - end))

    # ---------- 合并结果框（默认 AI 回复 + 按段背景色标记）----------
    def _refresh_result(self):
        """结果框初始即 AI 回复全文 —— 相同段原样（无底色）；差异段按取舍
        写入并标色（黄=未裁决/默认 AI，红=采用左，绿=采用右）。
        先 setPlainText 写入纯文本全文，再按段区间 setCharFormat 精确着色，
        杜绝 QTextEdit insertText 的格式继承染色（v3.48.3 修）。每段记录
        起点游标（末位=文档尾哨兵），供采纳时按段原位替换。"""
        doc = self.pane_merge.document()
        starts = []      # 各段起点（纯字符位置）
        colors = []      # 与 starts 对齐的底色（None=相同段不着色）
        pos = 0
        parts = []
        for s in self._segs:
            starts.append(pos)
            if s["kind"] == "equal":
                txt, bg = s["text"], None
            elif s["choice"] == "A":
                txt, bg = s["a"], "#ffe5e5"
            elif s["choice"] == "B":
                txt, bg = s["b"], "#e6ffec"
            else:
                txt, bg = s["b"], "#fff3cd"   # 未裁决：默认取 AI(B)
            colors.append(bg)
            if txt:
                parts.append(txt + "\n")
                pos += len(txt) + 1
        doc.setPlainText("".join(parts))   # 全文纯文本写入（零格式继承）
        cur = QTextCursor(doc)
        for i, bg in enumerate(colors):
            if not bg:
                continue
            # 该段写入长度 = 下一非空段起点 - 本段起点（空段与下段同起点）
            j = i + 1
            while j < len(starts) and starts[j] == starts[i]:
                j += 1
            end = starts[j] if j < len(starts) else doc.characterCount()
            cur.setPosition(starts[i])
            cur.setPosition(end, QTextCursor.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(bg))
            cur.setCharFormat(fmt)
        # 段起点游标（末位哨兵 = 文档尾），随后续编辑自动平移
        self._seg_cur = []
        for p in starts:
            c = QTextCursor(doc)
            c.setPosition(min(p, doc.characterCount()))
            self._seg_cur.append(c)
        c = QTextCursor(doc)
        c.movePosition(QTextCursor.End)
        self._seg_cur.append(c)

    # ---------- 事件过滤：双击采纳 / 右键菜单 ----------
    def eventFilter(self, obj, ev):
        """左键双击差异行=采用该侧；右键弹「采用所选 / 恢复默认」。
        事件经 viewport() 投递（QAbstractScrollArea），obj 比对 viewport。"""
        pa, pb = self.pane_a.viewport(), self.pane_b.viewport()
        if obj is pa or obj is pb:
            side = "A" if obj is pa else "B"
            pane = self.pane_a if obj is pa else self.pane_b
            if ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton:
                self._press_seg = self._seg_from_pos(pane, ev.position().toPoint())
                sel = pane.textCursor()
                self._press_sel = ((sel.selectionStart(), sel.selectionEnd())
                                   if sel.hasSelection() else None)
                return False
            if ev.type() == QEvent.MouseButtonDblClick and ev.button() == Qt.LeftButton:
                self._adopt(side, self._segs_from_event(pane))
                self._press_sel = None
                return True
            if ev.type() == QEvent.ContextMenu:
                self._ctx_menu(pane, side, ev)
                return True
        return super().eventFilter(obj, ev)


# ================= v3.48.14（AI-BATCH）：可审查的批量操作 =================
BATCH_MAX_BLOCKS = 60

# 批量处理预设（复用右键「AI」子菜单的提示词，保证口径一致）
_BATCH_PRESETS = [
    ("润色（更通顺专业）", "polish"),
    ("精简（去除冗余）", "condense"),
    ("扩写（补充细节）", "expand"),
    ("纠错（错别字 / 标点）", "correct"),
    ("改语气（更得体）", "tone"),
]

# 空行分隔符（保留原分隔符文本，应用时可原样拼回，避免改动文档空行风格）
_BATCH_SEP = re.compile(r"(\n[ \t]*\n)")


def _batch_split_blocks(text):
    """把 Markdown 按空行切成 [内容, 分隔符, 内容, ...]（偶数下标为内容）。

    返回 (parts, candidates)：candidates = 需要送模型的内容下标。
    跳过：围栏代码块内部（``` / ~~~，成对切换）、去空白后不足 8 字的块。
    分隔符原样保留在奇数下标，重组时 "".join(parts) 即得新全文。
    """
    parts = _BATCH_SEP.split(text)

    def _has_fence(body):
        return any(l.lstrip().startswith(("```", "~~~")) for l in body.split("\n"))

    candidates = []
    in_fence = False
    for i in range(0, len(parts), 2):
        body = parts[i]
        if _has_fence(body):
            in_fence = not in_fence      # 开围栏 / 闭围栏成对切换
            continue
        if in_fence:
            continue
        if len(body.strip()) < 8:
            continue
        candidates.append(i)
    return parts, candidates


def _batch_diff_html(a, b):
    """行级 diff → HTML（只读预览用）。删行红底 / 增行绿底，与片段替换同口径。"""
    la, lb = a.split("\n"), b.split("\n")
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, la, lb).get_opcodes():
        if tag == "equal":
            for l in la[i1:i2]:
                out.append('<div>%s</div>' % _esc(l))
            continue
        for l in la[i1:i2]:
            out.append('<div style="background:#fdecea;color:#a33;">- %s</div>'
                       % _esc(l))
        for l in lb[j1:j2]:
            out.append('<div style="background:#eaf7ee;color:#1d7a3a;">+ %s</div>'
                       % _esc(l))
    return "".join(out) or '<div style="color:#888;">（无内容）</div>'


class AIBatchDialog(QDialog):
    """v3.48.14（AI-BATCH，SoloMD 对标 P2-1）：可审查的 AI 批量操作。

    三页栈：配置 → 执行 → 审查。执行页逐块复用 AIStreamWorker（与问答同一条
    流式链路，可中止）；审查页只列「有变化」的块，勾选后经
    bridge.apply_ai_insert 写回（快照压栈，Ctrl+Z 可撤销）。
    """

    def __init__(self, parent, bridge, sel_text=""):
        super().__init__(parent)
        self.bridge = bridge
        self.setObjectName("aiBatchDlg")
        self.setWindowTitle("AI 批量处理")
        self.setModal(False)
        self.resize(780, 620)

        self._sel_text = sel_text or ""
        self._parts = []        # 分片（偶数=内容，奇数=分隔符）
        self._cands = []        # 待处理内容下标
        self._items = []        # 有变化的块 [{idx, orig, new}]
        self._cur = 0           # 已处理到 _cands 的第几个
        self._worker = None
        self._stopped = False
        self._chars = 0         # 当前块已收字符数（流式进度）
        self._same_n = 0        # 与原文相同的块数
        self._fail_n = 0        # 失败的块数
        self._scope_full = True

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(8)
        self.stack = QStackedWidget(self)
        root.addWidget(self.stack, 1)
        self._build_p0()
        self._build_p1()
        self._build_p2()
        self.stack.setCurrentIndex(0)

    # ---------------- 页 0：配置 ----------------
    def _build_p0(self):
        p = QWidget(self)
        f = QVBoxLayout(p)
        f.setContentsMargins(16, 14, 16, 12)
        f.setSpacing(10)
        tip = QLabel(
            "对整篇（或选中）内容按空行分块，逐块送同一模型处理；"
            "结果先审查再应用，应用后 Ctrl+Z 可撤销。代码块与过短块自动跳过。", p)
        tip.setObjectName("pageHint")
        tip.setWordWrap(True)
        f.addWidget(tip)

        f.addWidget(QLabel("提示词（对所有块生效）", p))
        self._prompt_box = QComboBox(p)
        self._prompt_box.setEditable(True)
        for label, key in _BATCH_PRESETS:
            self._prompt_box.addItem(label, AI_PRESET_PROMPTS[key])
        self._prompt_box.addItem("自定义指令…", "")
        self._prompt_box.setCurrentIndex(0)
        f.addWidget(self._prompt_box)

        grp = QGroupBox("处理范围", p)
        gl = QVBoxLayout(grp)
        self._rb_full = QRadioButton("整篇文档", grp)
        self._rb_sel = QRadioButton("选中文本", grp)
        self._rb_full.setChecked(True)
        if not self._sel_text.strip():
            self._rb_sel.setEnabled(False)
            self._rb_sel.setToolTip("编辑器中当前没有选中文本")
        gl.addWidget(self._rb_full)
        gl.addWidget(self._rb_sel)
        f.addWidget(grp)

        self._p0_info = QLabel(p)
        self._p0_info.setObjectName("pageHint")
        self._p0_info.setWordWrap(True)
        f.addWidget(self._p0_info)
        f.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        self._start_btn = QPushButton("开始处理", p)
        self._start_btn.setDefault(True)
        self._start_btn.clicked.connect(self._on_start)
        cancel = QPushButton("取消", p)
        cancel.clicked.connect(self.reject)
        row.addWidget(self._start_btn)
        row.addWidget(cancel)
        f.addLayout(row)
        self.stack.addWidget(p)

    # ---------------- 页 1：执行 ----------------
    def _build_p1(self):
        p = QWidget(self)
        g = QVBoxLayout(p)
        g.setContentsMargins(16, 16, 16, 14)
        g.setSpacing(10)
        g.addWidget(QLabel("正在逐块处理…", p))
        self._bar = QProgressBar(p)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        g.addWidget(self._bar)
        self._run_info = QLabel(p)
        self._run_info.setObjectName("pageHint")
        self._run_info.setWordWrap(True)
        g.addWidget(self._run_info)
        g.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        self._stop_btn = QPushButton("中止", p)
        self._stop_btn.clicked.connect(self._on_stop)
        row.addWidget(self._stop_btn)
        g.addLayout(row)
        self.stack.addWidget(p)

    # ---------------- 页 2：审查 ----------------
    def _build_p2(self):
        p = QWidget(self)
        h = QVBoxLayout(p)
        h.setContentsMargins(16, 14, 16, 12)
        h.setSpacing(8)
        self._sum = QLabel(p)
        self._sum.setWordWrap(True)
        h.addWidget(self._sum)
        self._list = QListWidget(p)
        self._list.setObjectName("aiBatchList")
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.itemDoubleClicked.connect(self._preview_item)
        h.addWidget(self._list, 1)
        row = QHBoxLayout()
        b_all = QPushButton("全选", p)
        b_all.clicked.connect(lambda: self._set_all(True))
        b_none = QPushButton("全不选", p)
        b_none.clicked.connect(lambda: self._set_all(False))
        b_prev = QPushButton("预览所选…", p)
        b_prev.clicked.connect(self._preview_current)
        row.addWidget(b_all)
        row.addWidget(b_none)
        row.addWidget(b_prev)
        row.addStretch(1)
        self._apply_btn = QPushButton("应用", p)
        self._apply_btn.setDefault(True)
        self._apply_btn.clicked.connect(self._do_apply)
        b_quit = QPushButton("放弃", p)
        b_quit.clicked.connect(self.reject)
        row.addWidget(self._apply_btn)
        row.addWidget(b_quit)
        h.addLayout(row)
        self.stack.addWidget(p)

    # ---------------- 连接参数（复用面板缓存与 Ollama 解析） ----------------
    def _conn(self):
        pane = self.parent()
        if pane is None or not hasattr(pane, "_connection"):
            return "", "", ""
        base, model, key = pane._connection()
        cfg = load_connection(self.bridge.settings())
        if cfg.get("provider") == "ollama" and not model:
            inst = []
            getter = getattr(pane, "_get_ollama_models", None)
            if getter is not None:
                try:
                    inst = getter() or []
                except Exception:
                    inst = []
            model = resolve_ollama_model(self.bridge.settings(), inst) or model
        return base, model, key

    def _effective_prompt(self):
        i = self._prompt_box.currentIndex()
        data = self._prompt_box.itemData(i)
        if isinstance(data, str) and data.strip() \
                and self._prompt_box.currentText() == self._prompt_box.itemText(i):
            return data          # 未编辑的预设行 → 用预设提示词
        return self._prompt_box.currentText().strip()

    # ---------------- 开始处理 ----------------
    def _on_start(self):
        prompt = self._effective_prompt()
        if not prompt:
            QMessageBox.information(self, "提示", "请先填写提示词。")
            return
        base, model, key = self._conn()
        if not base or not model:
            QMessageBox.warning(self, "未配置连接",
                "尚未配置可用的服务地址与模型。请点 AI 面板的「连接设置」"
                "选择服务商并填写模型（本地 Ollama 需先安装并启动）。")
            return
        self._scope_full = self._rb_full.isChecked()
        if self._scope_full:
            self._p0_info.setText("正在读取文档全文…")
            self.bridge.get_markdown(self._begin)
        else:
            self._begin(self._sel_text)

    def _begin(self, text):
        if not (text or "").strip():
            QMessageBox.information(self, "提示", "没有可处理的内容。")
            self.stack.setCurrentIndex(0)
            return
        self._parts, cands = _batch_split_blocks(text)
        self._cands = cands[:BATCH_MAX_BLOCKS]
        if not self._cands:
            QMessageBox.information(self, "提示",
                "没有找到可处理的文本块（代码块与过短块会被跳过）。")
            self.stack.setCurrentIndex(0)
            return
        self._items = []
        self._cur = 0
        self._same_n = 0
        self._fail_n = 0
        self._stopped = False
        self._bar.setRange(0, len(self._cands))
        self._bar.setValue(0)
        extra = ("（共 %d 块，超出 %d 上限，仅处理前 %d 块）"
                 % (len(cands), BATCH_MAX_BLOCKS, BATCH_MAX_BLOCKS)) \
            if len(cands) > BATCH_MAX_BLOCKS else ""
        self._run_info.setText("共 %d 块待处理%s" % (len(self._cands), extra))
        self.stack.setCurrentIndex(1)
        self._start_next()

    def _start_next(self):
        if self._stopped:
            return
        if self._cur >= len(self._cands):
            self._finish()
            return
        idx = self._cands[self._cur]
        orig = self._parts[idx]
        base, model, key = self._conn()
        if not base or not model:
            self._fail_n += len(self._cands) - self._cur
            self._finish()
            return
        user_msg = (self._effective_prompt() + "\n\n\"\"\"\n"
                    + orig.strip() + "\n\"\"\"")
        messages = [
            {"role": "system",
             "content": "你是 Markdown 文档编辑助手。按用户指令处理给定的文本块，"
                        "只输出处理后的文本本身，不要附加任何解释、引号或前后缀，"
                        "并保持原有的 Markdown 结构。"},
            {"role": "user", "content": user_msg},
        ]
        self._chars = 0
        self._run_info.setText("第 %d/%d 块 · 正在请求…" % (
            self._cur + 1, len(self._cands)))
        self._worker = AIStreamWorker(base, key, model, messages)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.done.connect(self._on_block_done)
        self._worker.start()

    def _on_chunk(self, delta):
        self._chars += len(delta or "")
        self._run_info.setText("第 %d/%d 块 · 已收 %d 字" % (
            self._cur + 1, len(self._cands), self._chars))

    def _on_block_done(self, ok, text):
        self._worker = None
        if self._stopped:
            return
        idx = self._cands[self._cur]
        orig = self._parts[idx]
        if ok and (text or "").strip():
            new = text.strip()
            if new != orig.strip():
                self._items.append({"idx": idx, "orig": orig, "new": new})
            else:
                self._same_n += 1
        else:
            self._fail_n += 1
        self._cur += 1
        self._bar.setValue(self._cur)
        self._start_next()

    def _on_stop(self):
        self._stopped = True
        if self._worker is not None:
            self._worker.cancel()
        self._run_info.setText("已中止，正在汇总已完成的结果…")

    # ---------------- 收尾：审查页 ----------------
    def _finish(self):
        self._list.clear()
        n = len(self._items)
        self._sum.setText(
            "共 %d 块有变化（默认全部勾选）；%d 块与原文相同，%d 块失败。"
            "双击某行可查看逐行差异，确认后只应用勾选的修改。"
            % (n, self._same_n, self._fail_n))
        for i, rec in enumerate(self._items):
            o = rec["orig"].strip().replace("\n", " ")
            nw = rec["new"].strip().replace("\n", " ")
            if len(o) > 46:
                o = o[:46] + "…"
            if len(nw) > 46:
                nw = nw[:46] + "…"
            it = QListWidgetItem("第 %d 块\n  原：%s\n  新：%s" % (i + 1, o, nw))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            it.setData(Qt.UserRole, i)
            it.setToolTip("原文 %d 字 → 新文 %d 字" % (
                len(rec["orig"]), len(rec["new"])))
            self._list.addItem(it)
        self._apply_btn.setText("应用采纳的 %d 处" % n)
        self._apply_btn.setEnabled(n > 0)
        self.stack.setCurrentIndex(2)

    def _set_all(self, on):
        st = Qt.Checked if on else Qt.Unchecked
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(st)

    def _checked_count(self):
        return sum(1 for i in range(self._list.count())
                   if self._list.item(i).checkState() == Qt.Checked)

    def _preview_current(self):
        it = self._list.currentItem()
        if it is not None:
            self._preview_item(it)

    def _preview_item(self, item):
        """只读行级差异预览（自绘，不复用带「确认替换」的 AIFragmentDialog）。"""
        if item is None:
            return
        rec = self._items[item.data(Qt.UserRole)]
        dlg = QDialog(self)
        dlg.setObjectName("aiBatchDiff")
        dlg.setWindowTitle("差异预览 · 第 %d 块" % (item.data(Qt.UserRole) + 1))
        dlg.resize(860, 560)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(12, 12, 12, 10)
        lay.setSpacing(6)
        view = QTextBrowser(dlg)
        view.setObjectName("aiBatchDiffView")
        view.setReadOnly(True)
        view.setOpenLinks(False)
        view.setHtml('<div style="font-family:Consolas,monospace;font-size:13px;'
                     'line-height:1.55;">%s</div>'
                     % _batch_diff_html(rec["orig"], rec["new"]))
        lay.addWidget(view, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        ok = QPushButton("关闭", dlg)
        ok.clicked.connect(dlg.accept)
        row.addWidget(ok)
        lay.addLayout(row)
        dlg.exec()

    # ---------------- 应用 ----------------
    def _do_apply(self):
        n = self._checked_count()
        if n == 0:
            QMessageBox.information(self, "提示", "没有采纳任何修改，未写回文档。")
            return
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it.checkState() == Qt.Checked:
                rec = self._items[it.data(Qt.UserRole)]
                self._parts[rec["idx"]] = rec["new"]
        new_text = "".join(self._parts)
        if self._scope_full:
            self.bridge.apply_ai_insert(
                new_text,
                msg="已应用 AI 批量处理 %d 处 · Ctrl+Z 可撤销 · Ctrl+S 保存" % n)
        else:
            self.bridge.replace_selection(new_text, orig_text=self._sel_text)
        self.accept()
