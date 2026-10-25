# -*- coding: utf-8 -*-
"""v3.47.2（SoloMD 对标）：独立 AI 连接面板与连接配置表单。

AIConnectionForm —— 连接配置表单（provider 下拉 / Base URL / 模型 / API Key /
一键测试连接 / 状态点 / 诊断日志）。被两处复用：
  · 独立连接面板 AIConnectionDialog（从 AI 主面板的「连接设置」按钮跳转打开）；
  · 系统设置「AI 连接」页（嵌入 SettingsDialog，作为默认连接参数配置入口）。

两处共享同一 QSettings + secretstore，因此「设置里填的默认连接」与「独立面板
里执行的连接」始终是同一份数据。表单随改随存（编辑完成即落盘），并 emit
connection_changed 通知主面板刷新状态条。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QComboBox, QCompleter, QDialog, QTextEdit,
    QMessageBox, QGroupBox, QSpinBox, QLabel)

import ai_core
from ai_core import (PROVIDERS, load_connection, save_connection, read_api_key,
    save_api_key, connection_status, get_ai_log, ai_log, AIStreamWorker, mask_key,
    OllamaDetectWorker, resolve_ollama_model, OLLAMA_DOWNLOAD_URL)


# 状态点配色
_DOT = {"connected": "#2ecc71", "configured": "#f1c40f",
        "unconfigured": "#e74c3c", "testing": "#3498db", "error": "#e74c3c"}


class AIConnectionForm(QWidget):
    connection_changed = Signal()

    def __init__(self, settings, parent=None, compact=False):
        super().__init__(parent)
        self._settings = settings
        self._worker = None
        self._detect_worker = None
        self._build_ui(compact)
        self._load()

    # ---------------- UI ----------------
    def _build_ui(self, compact):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        if not compact:
            title = QLabel("AI 连接")
            title.setObjectName("pageTitle")
            root.addWidget(title)
            hint = QLabel("配置一个 OpenAI 兼容的模型服务（云端或本地 Ollama 均可）。"
                          "设置将作为默认连接参数保存；AI 主面板的「连接设置」按钮"
                          "也会打开本面板执行连接。")
            hint.setObjectName("pageHint")
            hint.setWordWrap(True)
            root.addWidget(hint)

        # ---- 状态点 + 文本 ----
        strow = QHBoxLayout()
        self._dot = QLabel()
        self._dot.setFixedSize(12, 12)
        self._dot.setStyleSheet("border-radius:6px;background:%s" % _DOT["unconfigured"])
        self._status_text = QLabel("未配置连接")
        self._status_text.setObjectName("aiStatusText")
        strow.addWidget(self._dot)
        strow.addWidget(self._status_text)
        strow.addStretch(1)
        root.addLayout(strow)

        # ---- 表单 ----
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(10)

        self._prov = QComboBox()
        for p in PROVIDERS:
            self._prov.addItem(p["name"], p["id"])
        self._prov.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("服务商", self._prov)

        self._base = QLineEdit()
        self._base.setPlaceholderText("https://api.openai.com/v1")
        self._base.editingFinished.connect(self._on_edit)
        form.addRow("Base URL", self._base)

        self._model = QLineEdit()
        self._model.setPlaceholderText("可手填本地模型名（如 llama3.1）")
        self._model.editingFinished.connect(self._on_edit)
        form.addRow("模型", self._model)

        self._key = QLineEdit()
        self._key.setEchoMode(QLineEdit.Password)
        self._key.setPlaceholderText("API Key（本地 / Ollama 可留空）")
        self._key.editingFinished.connect(self._on_key_edit)
        form.addRow("API Key", self._key)

        root.addLayout(form)

        # ---- 本地 Ollama 引导（仅 Ollama 服务商可见）----
        # v3.47.3：默认本地 Ollama。若用户未安装 / 未配置，在此引导安装，
        # 并提供可点击直接跳转至 Ollama 安装地址的入口；同时可一键检测已安装模型，
        # 据「上次使用的模型 > 已安装模型」优先级自动回填。
        self._ollama_box = QGroupBox("本地 Ollama")
        self._ollama_box.setObjectName("aiOllamaBox")
        ob = QVBoxLayout(self._ollama_box)
        ob.setSpacing(8)
        self._ollama_info = QLabel(
            "AI 默认使用本地 Ollama（免 API Key）。点「检测已安装模型」可自动识别；"
            "若尚未安装，请先点击下方链接下载安装并启动 Ollama。")
        self._ollama_info.setObjectName("pageHint")
        self._ollama_info.setWordWrap(True)
        ob.addWidget(self._ollama_info)
        odrow = QHBoxLayout()
        self._detect_btn = QPushButton("检测已安装模型")
        self._detect_btn.clicked.connect(self._on_detect_ollama)
        self._ollama_link = QLabel(
            '<a href="%s">下载并安装 Ollama ↗</a>' % OLLAMA_DOWNLOAD_URL)
        self._ollama_link.setObjectName("aiLink")
        self._ollama_link.setOpenExternalLinks(True)
        odrow.addWidget(self._detect_btn)
        odrow.addWidget(self._ollama_link)
        odrow.addStretch(1)
        ob.addLayout(odrow)
        root.addWidget(self._ollama_box)

        # ---- v3.48.18（AI-CTX）文档上下文策略 ----
        self._ctx_box = QGroupBox("文档上下文（省 token）")
        self._ctx_box.setObjectName("aiCtxBox")
        cv = QVBoxLayout(self._ctx_box)
        cv.setSpacing(8)
        ctx_hint = QLabel(
            "篇幅不超过阈值时整篇送入模型；超过阈值只送标题、大纲与目标段落"
            "前后相邻段落；书籍模式先给完整目录再定位当前章节。")
        ctx_hint.setObjectName("pageHint")
        ctx_hint.setWordWrap(True)
        cv.addWidget(ctx_hint)
        cf = QFormLayout()
        cf.setContentsMargins(0, 0, 0, 0)
        cf.setVerticalSpacing(8)
        cf.setHorizontalSpacing(10)
        self._ctx_threshold = QSpinBox()
        self._ctx_threshold.setRange(500, 200000)
        self._ctx_threshold.setSingleStep(500)
        self._ctx_threshold.setSuffix(" 字")
        self._ctx_threshold.setToolTip(
            "超过该字数即切换为「大纲 + 目标段落邻域」模式；调大 = 更完整但更耗 token")
        self._ctx_threshold.valueChanged.connect(self._save_ctx)
        cf.addRow("整篇阈值", self._ctx_threshold)
        self._ctx_neighbors = QSpinBox()
        self._ctx_neighbors.setRange(0, 5)
        self._ctx_neighbors.setSuffix(" 段")
        self._ctx_neighbors.setToolTip("大纲模式下目标段落前后各带几段上下文")
        self._ctx_neighbors.valueChanged.connect(self._save_ctx)
        cf.addRow("前后邻段", self._ctx_neighbors)
        cv.addLayout(cf)
        root.addWidget(self._ctx_box)

        # ---- 操作按钮 ----
        brow = QHBoxLayout()
        self._test_btn = QPushButton("测试连接")
        self._test_btn.clicked.connect(self._on_test)
        self._log_btn = QPushButton("诊断日志")
        self._log_btn.clicked.connect(self._on_show_log)
        brow.addWidget(self._test_btn)
        brow.addWidget(self._log_btn)
        brow.addStretch(1)
        root.addLayout(brow)

        if not compact:
            note = QLabel("提示：本地 Ollama 需先运行服务（ollama serve 或桌面端），"
                          "Base URL 填 http://localhost:11434/v1，模型填已 pull 的模型名。")
            note.setObjectName("pageHint")
            note.setWordWrap(True)
            root.addWidget(note)

        root.addStretch(1)
        self._apply_completer()

    def _apply_completer(self):
        pid = self._prov.currentData()
        models = ai_core.provider_models(pid)
        if models:
            self._model.setCompleter(QCompleter(models, self))
        else:
            self._model.setCompleter(None)

    # ---------------- 载入 / 渲染 ----------------
    def _load(self):
        cfg = load_connection(self._settings)
        idx = self._prov.findData(cfg["provider"])
        self._prov.setCurrentIndex(idx if idx >= 0 else 0)
        self._base.setText(cfg["base"])
        self._model.setText(cfg["model"])
        self._key.setText(read_api_key())
        self._apply_completer()
        self._ollama_box.setVisible(cfg["provider"] == "ollama")
        self._render_status()
        self._load_ctx()
        # v3.47.3：本地 Ollama 默认自动检测已安装模型，据优先级回填（不覆盖用户手填的合法模型）
        if cfg["provider"] == "ollama":
            self._on_detect_ollama()

    def _render_status(self, override_level=None, override_text=None):
        st = connection_status(self._settings)
        level = override_level or st["level"]
        text = override_text or st["text"]
        self._dot.setStyleSheet("border-radius:6px;background:%s" % _DOT.get(level, "#95a5a6"))
        self._status_text.setText(text)

    # ---------------- 保存 / 信号 ----------------
    def _save(self):
        save_connection(self._settings, self._prov.currentData(),
                        self._base.text(), self._model.text())
        self._render_status()
        self.connection_changed.emit()

    # ---------------- v3.48.18（AI-CTX）上下文策略 ----------------
    def _load_ctx(self):
        try:
            import ai_context
            cfg = ai_context.load_config(self._settings)
            for w, v in ((self._ctx_threshold, cfg["threshold"]),
                         (self._ctx_neighbors, cfg["neighbors"])):
                w.blockSignals(True)
                w.setValue(v)
                w.blockSignals(False)
        except Exception:      # noqa: BLE001
            pass

    def _save_ctx(self, _v=None):
        try:
            import ai_context
            ai_context.save_config(self._settings,
                                   self._ctx_threshold.value(),
                                   self._ctx_neighbors.value())
        except Exception:      # noqa: BLE001
            pass

    def _on_provider_changed(self, _i):
        pid = self._prov.currentData()
        p = ai_core.provider_by_id(pid)
        # 切换服务商时，若当前 Base 与「上一个默认」相同则自动换为新默认，
        # 避免每次打开都覆盖用户手填；模型同理（仅当为空或仍等于旧默认时填）。
        if p and p["base"]:
            cur = self._base.text().strip()
            if not cur or cur in [pp["base"] for pp in PROVIDERS if pp["base"]]:
                self._base.setText(p["base"])
        if p and p["models"]:
            cur = self._model.text().strip()
            if not cur or cur in [m for pp in PROVIDERS for m in pp["models"]]:
                self._model.setText(p["models"][0])
        self._apply_completer()
        self._ollama_box.setVisible(pid == "ollama")
        self._save()
        # 切到本地 Ollama 时立即尝试检测已安装模型并据优先级回填
        if pid == "ollama":
            self._on_detect_ollama()

    def _on_edit(self):
        self._save()

    # ---------------- 本地 Ollama 检测 / 引导 ----------------
    def _on_detect_ollama(self):
        if self._detect_worker and self._detect_worker.isRunning():
            return
        self._ollama_info.setText("正在检测本地 Ollama 模型…")
        self._detect_worker = OllamaDetectWorker()
        self._detect_worker.result.connect(self._on_ollama_detected)
        self._detect_worker.start()

    def _on_ollama_detected(self, models, reachable):
        if reachable and models:
            self._ollama_info.setText(
                "已检测到 %d 个本地模型：%s"
                % (len(models), "、".join(models[:8])))
            # 模型选择优先级：上次使用的模型（若在已安装列表）> 第一个已安装模型
            chosen = resolve_ollama_model(self._settings, models)
            if chosen:
                self._model.setText(chosen)
                self._save()
        elif reachable:
            self._ollama_info.setText(
                "Ollama 已运行，但尚未安装任何模型。请先在终端执行 "
                "「ollama pull llama3.1」等命令拉取模型，再点「检测已安装模型」。")
        else:
            self._ollama_info.setText(
                "未检测到本地 Ollama 服务。请先点击下方链接下载安装并启动 Ollama，"
                "再点「检测已安装模型」。")

    def _on_key_edit(self):
        save_api_key(self._key.text())
        self._render_status()
        self.connection_changed.emit()

    # ---------------- 测试连接 ----------------
    def _on_test(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            return
        base = self._base.text().strip() or ai_core.DEFAULT_BASE
        model = self._model.text().strip() or ai_core.DEFAULT_MODEL
        key = self._key.text()
        if not key and "openai.com" in base:
            QMessageBox.warning(self, "缺少 API Key",
                "OpenAI 官方接口需要 API Key；本地 / Ollama 服务可留空。")
            return
        self._test_btn.setText("停止")
        self._render_status("testing", "测试中…")
        msgs = [{"role": "user", "content": "hi"}]
        self._worker = AIStreamWorker(base, key, model, msgs)
        self._worker.done.connect(self._on_test_done)
        self._worker.cancelled.connect(lambda: self._render_status())
        self._worker.start()

    def _on_test_done(self, ok, text):
        self._test_btn.setText("测试连接")
        if ok:
            self._settings.setValue(ai_core.SET_TEST_OK, True)
            self._settings.sync()
            self._render_status("connected", "已连接 · 返回 %d 字符" % len(text))
            ai_log("test_ok", "model=%s" % self._model.text())
        else:
            self._settings.setValue(ai_core.SET_TEST_OK, False)
            self._settings.sync()
            self._render_status("error", "连接失败：" + text[:120])
            ai_log("test_fail", text[:200])
        self.connection_changed.emit()

    # ---------------- 诊断日志 ----------------
    def _on_show_log(self):
        dlg = AILogDialog(self)
        dlg.exec()


class AILogDialog(QDialog):
    """查看 / 复制 AI 诊断日志（排查「连接成功却无响应」类问题）。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 诊断日志")
        self.resize(560, 360)
        lay = QVBoxLayout(self)
        self._txt = QTextEdit()
        self._txt.setReadOnly(True)
        lines = get_ai_log()
        self._txt.setPlainText("\n".join(lines) if lines else "（暂无日志）")
        lay.addWidget(self._txt)
        brow = QHBoxLayout()
        copy = QPushButton("复制全部")
        copy.clicked.connect(self._copy)
        close = QPushButton("关闭")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        brow.addStretch(1)
        brow.addWidget(copy)
        brow.addWidget(close)
        lay.addLayout(brow)

    def _copy(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._txt.toPlainText())


class AIConnectionDialog(QDialog):
    """独立 AI 连接面板（从 AI 主面板的「连接设置」按钮跳转打开）。

    仅承载 AIConnectionForm + 关闭按钮；表单随改随存，故无需「保存」按钮。
    connection_changed 通知主窗口刷新主面板状态条。
    """
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 连接设置")
        self.resize(460, 320)
        self.setModal(False)
        lay = QVBoxLayout(self)
        self.form = AIConnectionForm(settings, self, compact=True)
        lay.addWidget(self.form, 1)
        brow = QHBoxLayout()
        brow.addStretch(1)
        close = QPushButton("关闭")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        brow.addWidget(close)
        lay.addLayout(brow)
