# -*- coding: utf-8 -*-
"""v3.47.2（SoloMD 对标）：AI 连接与流式请求核心。

被 ai_pane（问答主面板）、ai_connection（独立连接面板 / 设置页「AI 连接」）复用。

职责：
  · PROVIDERS —— 主流 OpenAI 兼容服务预设（含 Ollama 本地 + 自定义）。
  · AIStreamWorker —— 子线程发起 /chat/completions，支持 stream:true 的 SSE
    增量解析、手动取消（关闭连接）、单 JSON 回退（部分服务不支持流）、
    终态信号（done / cancelled）必达；本地默认超时 120s，避免 60s 整包超时。
  · ai_log / get_ai_log —— 结构化诊断日志（落盘 ai.log + 内存环形缓冲），
    用于排查「显示连接成功但提问无响应」类问题。
  · 连接参数读写助手 —— 统一 QSettings 键 + secretstore 存 Key（不可用时回退）。

设计取舍（修复 v3.46/3.47.1 的已知缺陷）：
  · 模型名用 QLineEdit（可手填），仅以 QCompleter 给出官方目录建议，
    修正 SoloMD「指向 LM Studio 时无法手填本地模型名」的缺陷。
  · 测试连接 ≠ 真实问答链路：测试只验证连通与首包返回；真实问答走同一 worker，
    因此诊断日志在二者共用，便于比对。
"""
import json
import logging
import os
import time
import urllib.request
import urllib.error

from PySide6.QtCore import QThread, Signal

try:
    import secretstore
except Exception:
    secretstore = None

# ===================== 连接参数存储键 =====================
SET_BASE = "ai/baseUrl"
SET_MODEL = "ai/model"
SET_PROVIDER = "ai/provider"        # 选中的 provider id（"custom" 表示自定义）
SET_TEST_OK = "ai/lastTestOk"       # 最近一次测试连接是否成功（bool）
CRED_TARGET = "mdEditor/AI/APIKey"  # Windows 凭据管理器目标名

DEFAULT_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"

# ===================== Ollama 本地预设 =====================
# v3.47.3：AI 连接默认采用本地 Ollama（无需 Key、随装随用）。
OLLAMA_DEFAULT_BASE = "http://localhost:11434/v1"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"

# ===================== Provider 预设 =====================
# 仅纳入「OpenAI 兼容 /chat/completions」形态的服务，确保本模块单一请求路径。
# models 仅作 QCompleter 建议，字段仍允许手填（修正 SoloMD 缺陷）。
PROVIDERS = [
    {"id": "openai", "name": "OpenAI", "base": "https://api.openai.com/v1",
     "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o1-mini", "o3-mini"]},
    {"id": "deepseek", "name": "DeepSeek", "base": "https://api.deepseek.com/v1",
     "models": ["deepseek-chat", "deepseek-reasoner"]},
    {"id": "qwen", "name": "通义千问 Qwen", "base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "models": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen2.5-72b-instruct"]},
    {"id": "glm", "name": "智谱 GLM", "base": "https://open.bigmodel.cn/api/paas/v4",
     "models": ["glm-4-plus", "glm-4-air", "glm-4-flash", "glm-4v"]},
    {"id": "kimi", "name": "Kimi 月之暗面", "base": "https://api.moonshot.cn/v1",
     "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]},
    {"id": "siliconflow", "name": "硅基流动 SiliconFlow", "base": "https://api.siliconflow.cn/v1",
     "models": ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1",
                "Qwen/Qwen2.5-72B-Instruct", "meta-llama/Llama-3.3-70B-Instruct"]},
    {"id": "gemini", "name": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai/",
     "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]},
    {"id": "azure", "name": "Azure OpenAI", "base": "https://<resource>.openai.azure.com/openai",
     "models": ["<deployment-name>"]},
    {"id": "openrouter", "name": "OpenRouter（聚合）", "base": "https://openrouter.ai/api/v1",
     "models": ["openai/gpt-4o", "anthropic/claude-3.5-sonnet", "google/gemini-pro-1.5",
                "meta-llama/llama-3.3-70b-instruct"]},
    {"id": "minimax", "name": "MiniMax", "base": "https://api.minimax.chat/v1",
     "models": ["abab6.5-chat", "abab5.5-chat"]},
    {"id": "baichuan", "name": "百川 Baichuan", "base": "https://api.baichuan-ai.com/v1",
     "models": ["Baichuan4", "Baichuan3-Turbo"]},
    {"id": "mistral", "name": "Mistral", "base": "https://api.mistral.ai/v1",
     "models": ["mistral-large-latest", "mistral-small-latest", "mistral-7b-instruct"]},
    {"id": "together", "name": "Together", "base": "https://api.together.xyz/v1",
     "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"]},
    {"id": "ollama", "name": "Ollama（本地）", "base": "http://localhost:11434/v1",
     "models": ["llama3.1", "llama3.2", "qwen2.5", "deepseek-r1"]},
    {"id": "custom", "name": "自定义 / 其它", "base": "",
     "models": []},
]


def provider_by_id(pid):
    for p in PROVIDERS:
        if p["id"] == pid:
            return p
    return None


def provider_models(pid):
    p = provider_by_id(pid)
    return list(p["models"]) if p else []


# ===================== Ollama 本地检测 =====================
def detect_ollama_models(tags_url=OLLAMA_TAGS_URL, timeout=3):
    """同步：返回已安装的 Ollama 模型名列表；不可达 / 解析失败返回 []。

    用于「模型选择优先级」：优先上次使用的模型，其次为已安装模型。
    也用于判断用户是否已安装 Ollama（据此在连接面板引导安装）。
    """
    try:
        req = urllib.request.Request(tags_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            obj = json.loads(resp.read().decode("utf-8", "replace"))
        return [m.get("name") for m in obj.get("models", []) if m.get("name")]
    except Exception:
        return []


def resolve_ollama_model(settings, installed):
    """按优先级解析默认模型：上次使用的模型（若在已安装列表）> 第一个已安装模型。

    返回 "" 表示既没有上次使用、也没有已安装模型（需引导安装）。
    """
    last = settings.value(SET_MODEL, "", type=str).strip()
    if last and last in installed:
        return last
    if installed:
        return installed[0]
    return ""


class OllamaDetectWorker(QThread):
    """异步检测本地 Ollama 已安装模型。

    result(models:list, reachable:bool)：
      reachable=True  —— Ollama 服务可连通（即使模型数为 0，也代表已安装运行）；
      reachable=False —— 连不上，通常意味着尚未安装 / 未启动 Ollama。
    """
    result = Signal(list, bool)

    def __init__(self, tags_url=OLLAMA_TAGS_URL, timeout=3):
        super().__init__()
        self._url = tags_url
        self._timeout = timeout

    def run(self):
        models = detect_ollama_models(self._url, self._timeout)
        self.result.emit(models, bool(models) or self._reachable_probe())

    def _reachable_probe(self):
        # models 为空也可能只是「未拉取模型」，需区分「已安装无模型」与「完全没装」。
        # 再探一次：能连通 api/tags 即算 reachable（返回空列表也算已安装运行）。
        try:
            req = urllib.request.Request(self._url, method="GET")
            urllib.request.urlopen(req, timeout=self._timeout)
            return True
        except Exception:
            return False


# ===================== 诊断日志 =====================
_LOG_PATH = None
_RING = []          # 内存环形缓冲（最近 300 条）
_RING_MAX = 300


def ai_log_path():
    global _LOG_PATH
    if _LOG_PATH is None:
        from config import LOG_DIR
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
        except Exception:
            pass
        _LOG_PATH = os.path.join(LOG_DIR, "ai.log")
    return _LOG_PATH


def ai_log(event, detail=""):
    """记录一条 AI 诊断日志（落盘 + 内存环形）。

    event 如 "request", "response", "test_ok", "error", "cancel"；
    detail 为附带信息（URL 脱敏、耗时、异常文本等）。
    同时用标准 logging 输出到控制台，便于开发期排查。
    """
    ts = time.strftime("%H:%M:%S")
    line = "[%s] %s%s" % (ts, event, (": " + detail) if detail else "")
    _RING.append(line)
    if len(_RING) > _RING_MAX:
        _RING[:] = _RING[-_RING_MAX:]
    logging.getLogger("ai").info(line)
    try:
        with open(ai_log_path(), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d ") + line + "\n")
    except Exception:
        pass


def get_ai_log():
    """返回内存环形缓冲的日志列表（最新在末尾）。"""
    return list(_RING)


# ===================== 流式请求 Worker =====================
class AIStreamWorker(QThread):
    """在子线程中调用 OpenAI 兼容 /chat/completions。

    信号：
      chunk(str)  —— 增量文本片段（流式）
      reasoning(str) —— v3.48.11（AI-THINK）：思考过程增量（reasoning_content /
        reasoning 字段）实时下发，供 UI「显示思考过程」开关渲染；关闭开关时
        仅累积作兜底（模型只吐思考不吐正文时，用思考内容代替「空回复」报错）。
      done(bool, str) —— 终态：(成功?, 全文或错误信息)
      cancelled() —— 用户主动取消（已关闭连接）

    特性：
      · stream:true + SSE 增量解析；部分服务不支持流时自动回退单 JSON。
      · cancel() 关闭底层连接，正在阻塞读的操作随即抛异常并被捕获为 cancelled。
      · 本地默认超时 120s（逐次读取沉默超时，不中断正常长生成）。
      · v3.48.11（AI-EMPTY3）：reasoning-only 自动重试时，对 Ollama（:11434）
        追加 think:false —— 自然语言「请跳过思考」对 qwen3.5 无效（实测仍思考
        87s 后空回复），禁用思考参数才能直接拿到最终回答。
    """
    chunk = Signal(str)
    reasoning = Signal(str)
    done = Signal(bool, str)
    cancelled = Signal()

    def __init__(self, base_url, api_key, model, messages, timeout=120,
                 auto_retry=True, disable_think=False):
        super().__init__()
        # v3.48.14（AI-NATIVE）：「显示思考过程」关闭时对 Ollama 主请求直接
        # 走原生 /api/chat + think:false（兼容端 /v1 会忽略 think —— 实测
        # qwen3.5 依然思考 88s 后只回 reasoning）。非 Ollama 不受影响。
        self._disable_think = bool(disable_think)
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = model or ""
        self.messages = messages
        self._timeout = timeout
        self._cancel = False
        self._resp = None
        # v3.48.8（AI-RETRY）：思考模型只吐 reasoning 不吐正文时自动重试 1 次
        # （附「直接输出最终回答」追加指令），不再向用户展示 reasoning 提示文案。
        self._retry_left = 1 if auto_retry else 0

    def cancel(self):
        self._cancel = True
        try:
            if self._resp is not None:
                self._resp.close()
        except Exception:
            pass

    def _make_request(self):
        url = self.base_url + "/chat/completions"
        payload = json.dumps({
            "model": self.model,
            "messages": self.messages,
            "stream": True,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", "Bearer " + self.api_key)
        return req, url

    # -------------------- v3.48.14（AI-NATIVE）--------------------
    def _is_ollama(self):
        return ":11434" in self.base_url

    def _native_base(self):
        """OpenAI 兼容 base（…/v1）→ Ollama 原生根（…:11434）。"""
        b = self.base_url
        if b.endswith("/v1"):
            b = b[:-3]
        return b.rstrip("/")

    def _native_chat(self, messages, think=False, emit=False):
        """Ollama 原生 /api/chat（NDJSON 流）。
        think 参数在原生端被可靠支持；/v1 OpenAI 兼容端会忽略 think:false
        （ai.log 实证 qwen3.5 重试依然思考 88s 只回 reasoning）。
        emit=True 时实时下发 chunk / reasoning（打字机效果）。
        返回 (full_list, reasoning_list, err)；err 非空 = 请求失败摘要。"""
        url = self._native_base() + "/api/chat"
        body = {"model": self.model, "messages": messages,
                "stream": True, "think": bool(think)}
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", "Bearer " + self.api_key)
        full, rsn = [], []
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                self._resp = resp
                ctype = resp.headers.get("Content-Type", "") or ""
                ai_log("response", "HTTP %s %s (native)"
                       % (getattr(resp, "status", "?"), ctype[:60]))
                if "text/event-stream" in ctype or "ndjson" not in ctype:
                    # 非 NDJSON（老版整包 JSON / 代理改写）→ 整包解析
                    raw = resp.read()
                    try:
                        obj = json.loads(raw.decode("utf-8", "replace"))
                    except Exception:
                        return full, rsn, "native: non-json response"
                    if isinstance(obj, dict) and obj.get("error"):
                        return full, rsn, self._err_text(obj["error"])
                    msg = (obj.get("message") or {}) if isinstance(obj, dict) else {}
                    c = self._content_text(msg.get("content"))
                    if c:
                        full.append(c)
                        if emit:
                            self.chunk.emit(c)
                    r = self._content_text(msg.get("reasoning"))
                    if r:
                        rsn.append(r)
                        if emit:
                            self.reasoning.emit(r)
                    return full, rsn, ""
                for raw in resp:          # NDJSON：每行一个 JSON 对象
                    if self._cancel:
                        return full, rsn, ""
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line.decode("utf-8", "replace"))
                    except Exception:
                        continue
                    if isinstance(obj, dict) and obj.get("error"):
                        return full, rsn, self._err_text(obj["error"])
                    msg = obj.get("message") or {}
                    c = self._content_text(msg.get("content"))
                    if c:
                        full.append(c)
                        if emit:
                            self.chunk.emit(c)
                    r = self._content_text(msg.get("reasoning"))
                    if r:
                        rsn.append(r)
                        if emit:
                            self.reasoning.emit(r)
                    if obj.get("done"):
                        break
            return full, rsn, ""
        except Exception as e:
            if self._cancel:
                return full, rsn, ""
            return full, rsn, str(e)
        finally:
            self._resp = None

    def run(self):
        t0 = time.time()
        # ---- v3.48.14（AI-NATIVE）：思考开关关闭 + Ollama → 主请求直连
        # 原生端 think:false，跳过思考直接拿最终回答（更快、不再 reasoning-only）。
        if self._is_ollama() and self._disable_think:
            full0, _rsn0, err0 = self._native_chat(
                self.messages, think=False, emit=True)
            if self._cancel:
                self.cancelled.emit()
                return
            text0 = "".join(full0)
            if not err0:
                ai_log("native_think_off", "len=%d" % len(text0))
                self.done.emit(True, text0)
                return
            if text0:
                # 流了一半才断 → 有多少给多少，避免回退重发造成重复
                ai_log("native_partial", "len=%d err=%s" % (len(text0), err0[:120]))
                self.done.emit(True, text0)
                return
            ai_log("native_fallback", err0[:160])
            # 原生端失败（老版本 / 代理拦截）→ 落回 OpenAI 兼容端原流程
        safe_url = self.base_url + "/chat/completions"
        try:
            req, _ = self._make_request()
            ai_log("request", "%s model=%s msgs=%d"
                   % (self._mask(safe_url), self.model, len(self.messages)))
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                self._resp = resp
                ctype = resp.headers.get("Content-Type", "") or ""
                # v3.48.6（AI-EMPTY2）：响应头入日志 —— 排查空回复时先看
                # 服务端到底回了什么形态（SSE / JSON / HTML 错误页）。
                ai_log("response", "HTTP %s %s"
                       % (getattr(resp, "status", "?"), ctype[:80]))
                if "text/event-stream" in ctype:
                    self._read_sse(resp)
                else:
                    # 单 JSON 回退（部分网关 / 代理不支持流式）
                    body = resp.read().decode("utf-8", "replace")
                    self._emit_json(body)
            if self._cancel:
                self.cancelled.emit()
                return
            # _read_sse / _emit_json 内部已 emit done；若因异常跳出则下面补发
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            ai_log("error", "HTTP %s %s" % (e.code, detail[:300]))
            if self._cancel:
                self.cancelled.emit()
            else:
                self.done.emit(False, "HTTP %s: %s" % (e.code, detail[:300]))
        except Exception as e:
            ai_log("error", "%s" % e)
            if self._cancel:
                self.cancelled.emit()
            else:
                self.done.emit(False, str(e))
        finally:
            self._resp = None
            ai_log("done_time", "%.1fs" % (time.time() - t0))

    def _read_sse(self, resp):
        buf = b""
        full = []
        reasoning = []            # v3.48.6：纯 reasoning 流兜底（只吐思考不吐正文）
        all_bytes = bytearray()   # v3.48.3：整包兜底（网关「SSE 头 + JSON 体」）
        finish_reason = None      # v3.48.5：length → 提示「回复被截断」
        err_msg = None            # v3.48.5：200 响应体内的 error 对象（旧版静默吞掉→空白）
        unparsed = 0              # v3.48.5：非 JSON data 行计数（诊断日志用）
        for raw in resp:
            if self._cancel:
                return
            all_bytes += raw
            buf += raw
            # v3.48.3（AI-FIX）：统一 CRLF → LF。部分服务 / 网关用 \r\n\r\n
            # 分隔 SSE 事件，旧实现只按 \n\n 切分 → 永不切分 → 整包丢失
            # （表现为回复空白）或部分块丢失（表现为回复不全）。
            buf = buf.replace(b"\r\n", b"\n")
            while b"\n\n" in buf:
                block, buf = buf.split(b"\n\n", 1)
                for line in block.split(b"\n"):
                    line = line.strip()
                    if not line.startswith(b"data:"):
                        continue
                    data = line[5:].strip()
                    if data == b"[DONE]":
                        self._sse_finish(full, finish_reason, err_msg,
                                         all_bytes, unparsed, reasoning)
                        return
                    try:
                        obj = json.loads(data)
                    except Exception:
                        unparsed += 1        # 注释 / 心跳 / 非 JSON 行
                        continue
                    if isinstance(obj, dict) and obj.get("error"):
                        err_msg = self._err_text(obj["error"])
                        continue
                    piece, fr = self._extract_piece(obj)
                    if fr:
                        finish_reason = fr
                    if piece:
                        full.append(piece)
                        self.chunk.emit(piece)
                    else:
                        # v3.48.6/3.48.7：增量只有思考内容、正文为空（如
                        # deepseek-reasoner / Ollama qwen3 思考阶段）→ 收集备用。
                        # 字段两套命名：reasoning_content（DeepSeek 等）/
                        # reasoning（Ollama OpenAI 兼容端，实测 qwen3.5）。
                        try:
                            d = obj["choices"][0].get("delta") or {}
                            rc = d.get("reasoning_content") or d.get("reasoning")
                        except (KeyError, IndexError, TypeError):
                            rc = None
                        rc = self._content_text(rc)
                        if rc:
                            reasoning.append(rc)
                            # v3.48.11（AI-THINK）：实时下发思考增量
                            self.reasoning.emit(rc)
        self._sse_finish(full, finish_reason, err_msg, all_bytes,
                         unparsed, reasoning)

    def _sse_finish(self, full, finish_reason, err_msg, all_bytes,
                    unparsed=0, reasoning=None):
        """v3.48.5（AI-EMPTY）/ v3.48.6（AI-EMPTY2）：SSE 流收尾统一出口。
        · 200 响应体内嵌 error → done(False, 具体错误)（旧版静默吞掉 → 空白）；
        · finish_reason=content_filter（安全策略拦截）→ 显式报错（旧版成空回复）；
        · 无任何增量 → 整包 JSON 兜底，兼容 message.content / text /
          reasoning_content（推理模型正文可能在后者）/ content 数组形态；
        · 流内只有 reasoning_content 增量 → 兜底展示思考内容并提示；
        · finish_reason=length → 末尾追加截断提示（修「回复不全」无解释）。"""
        if self._cancel:
            return
        if err_msg:
            ai_log("error", "server error: %s" % err_msg)
            self.done.emit(False, "服务端返回错误：%s" % err_msg)
            return
        text = "".join(full)
        if not text:
            content = ""
            try:
                obj = json.loads(all_bytes.decode("utf-8", "replace"))
            except Exception:
                obj = None
            if isinstance(obj, dict) and obj.get("error"):
                self.done.emit(False, "服务端返回错误：%s" % self._err_text(obj["error"]))
                return
            if isinstance(obj, dict):
                try:
                    ch = obj["choices"][0]
                    msg = ch.get("message") or {}
                    content = (self._content_text(msg.get("content"))
                               or self._content_text(ch.get("text"))
                               or self._content_text(msg.get("reasoning_content"))
                               or self._content_text(msg.get("reasoning")))
                except Exception:
                    content = ""
            if content:
                self.chunk.emit(content)
                text = content
        if not text and reasoning:
            # v3.48.8（AI-RETRY）：只有思考、没有正文 → 自动重试 1 次
            # （追加「直接输出最终回答」指令）；重试成功则直接输出最终结果，
            # 仍失败则按普通空回复处理（不展示 reasoning 提示文案）。
            rtext = "".join(reasoning)
            if self._retry_left > 0 and not self._cancel:
                self._retry_left -= 1
                ai_log("reasoning_retry", "think_len=%d" % len(rtext))
                retry_msgs = list(self.messages) + [{
                    "role": "user",
                    "content": ("你上一轮只输出了思考过程、没有最终回答。"
                                "请跳过思考，直接输出最终回答本身。")}]
                if self._is_ollama():
                    # v3.48.14（AI-NATIVE）：/v1 兼容端忽略 think:false（实测
                    # qwen3.5 依然思考 88s 后只回 reasoning）→ 重试改走原生
                    # /api/chat + think:false，可靠拿到最终回答。
                    full2, _rsn2, err2 = self._native_chat(
                        retry_msgs, think=False, emit=True)
                    text2 = "".join(full2)
                    ok2 = not err2
                else:
                    ok2, text2, err2 = self._silent_request(retry_msgs)
                if self._cancel:
                    return
                if ok2 and text2:
                    ai_log("reasoning_retry_ok", "len=%d" % len(text2))
                    if not self._is_ollama():
                        self.chunk.emit(text2)   # 原生路径已在流中 emit
                    self.done.emit(True, text2)
                    return
                ai_log("reasoning_retry_fail",
                       "err=%r text_len=%d" % (str(err2)[:120], len(text2 or "")))
            ai_log("reasoning_only", "len=%d head=%r" % (len(rtext), rtext[:120]))
            self.done.emit(True, "")
            return
        if not text and finish_reason == "content_filter":
            ai_log("content_filter", "finish_reason=content_filter bytes=%d"
                   % len(all_bytes))
            self.done.emit(False,
                           "回复被服务端安全策略拦截（finish_reason=content_filter）。"
                           "请调整提问内容后重试，或更换模型 / 服务商。")
            return
        if not text:
            ai_log("empty_response",
                   "finish=%r unparsed=%d bytes=%d head=%r"
                   % (finish_reason, unparsed, len(all_bytes),
                      bytes(all_bytes[:200])))
        if finish_reason == "length" and text:
            text += "\n\n（提示：回复因模型长度限制被截断，可尝试更换模型或缩短原文。）"
        self.done.emit(True, text)

    def _silent_request(self, messages):
        """v3.48.8（AI-RETRY）：reasoning-only 自动重试用的静默请求。
        不 emit 任何信号，返回 (ok, text, err)；ok=True 时 text 为最终正文
        （可能为空串），ok=False 时 err 为错误摘要。"""
        url = self.base_url + "/chat/completions"
        # v3.48.11（AI-EMPTY3）：Ollama 思考模型重试时禁用思考（think:false）——
        # 自然语言「请跳过思考」对 qwen3.5 无效（ai.log 实证：重试仍思考 87s
        # 后只回 reasoning）；Ollama OpenAI 兼容端支持 think 参数，关闭后直接
        # 产出最终回答。非 Ollama 服务不添加该字段（避免严格网关 400）。
        body = {"model": self.model, "messages": messages, "stream": True}
        if ":11434" in self.base_url:
            body["think"] = False
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", "Bearer " + self.api_key)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                ctype = resp.headers.get("Content-Type", "") or ""
                raw = resp.read()
            if "text/event-stream" in ctype:
                full, err = self._parse_sse_bytes(raw)
                return True, "".join(full), err
            obj = json.loads(raw.decode("utf-8", "replace"))
            if isinstance(obj, dict) and obj.get("error"):
                return False, "", self._err_text(obj["error"])
            content = ""
            try:
                ch = obj["choices"][0]
                msg = ch.get("message") or {}
                content = (self._content_text(msg.get("content"))
                           or self._content_text(ch.get("text"))
                           or self._content_text(msg.get("reasoning_content"))
                           or self._content_text(msg.get("reasoning")))
            except Exception:
                content = ""
            return True, content, ""
        except Exception as e:
            return False, "", str(e)

    def _parse_sse_bytes(self, raw):
        """v3.48.8（AI-RETRY）：整包 SSE 字节 → 增量正文列表（不 emit 信号）。
        返回 (full_list, err)；err 非空表示服务端内嵌 error。"""
        full = []
        text = raw.replace(b"\r\n", b"\n").decode("utf-8", "replace")
        for block in text.split("\n\n"):
            for line in block.split("\n"):
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except Exception:
                    continue
                if isinstance(obj, dict) and obj.get("error"):
                    return full, self._err_text(obj["error"])
                piece, _fr = self._extract_piece(obj)
                if piece:
                    full.append(piece)
        return full, ""

    @staticmethod
    def _extract_piece(obj):
        """v3.48.5：从 SSE data JSON 提取增量文本与 finish_reason。
        兼容：delta.content（标准流式）、message.content（部分网关把整段
        放单事件）、text（旧版 completions 形态）。"""
        try:
            ch = obj["choices"][0]
        except (KeyError, IndexError, TypeError):
            return "", None
        fr = ch.get("finish_reason") or None
        delta = ch.get("delta") or {}
        piece = (AIStreamWorker._content_text(delta.get("content"))
                 or AIStreamWorker._content_text((ch.get("message") or {}).get("content"))
                 or AIStreamWorker._content_text(ch.get("text")))
        return piece, fr

    @staticmethod
    def _content_text(c):
        """content 字段归一：字符串 / 分段数组（[{type:text,text:..}]）/ 其它。"""
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts = []
            for p in c:
                if isinstance(p, str):
                    parts.append(p)
                elif isinstance(p, dict):
                    parts.append(str(p.get("text") or ""))
            return "".join(parts)
        return str(c) if c else ""

    @staticmethod
    def _err_text(err):
        """服务端 error 对象 → 可读文本。"""
        try:
            if isinstance(err, dict):
                return str(err.get("message")
                           or json.dumps(err, ensure_ascii=False))[:300]
        except Exception:
            pass
        return str(err)[:300]

    def _emit_json(self, body):
        """非流式单 JSON 回退（v3.48.5：补 error / text / reasoning_content /
        content 数组形态，旧版只认 message.content → 其它形态全部「解析失败」）。"""
        try:
            obj = json.loads(body)
        except Exception as e:
            self.done.emit(False, "解析响应失败：" + str(e))
            return
        if isinstance(obj, dict) and obj.get("error"):
            self.done.emit(False, "服务端返回错误：%s" % self._err_text(obj["error"]))
            return
        content = ""
        try:
            ch = obj["choices"][0]
            msg = ch.get("message") or {}
            content = (self._content_text(msg.get("content"))
                       or self._content_text(ch.get("text"))
                       or self._content_text(msg.get("reasoning_content"))
                       or self._content_text(msg.get("reasoning")))
        except Exception:
            content = ""
        if content:
            self.chunk.emit(content)
        self.done.emit(True, content)

    @staticmethod
    def _mask(url):
        """脱敏：不回显 query 中的 key 等。当前 URL 不含明文 key，原样返回。"""
        return url


# ===================== 连接配置读写（统一入口） =====================
def read_api_key():
    """从凭据存储读取 API Key；不可用时返回空串。"""
    if secretstore is not None and secretstore.available():
        try:
            v = secretstore.read_cred(CRED_TARGET)
            if v:
                return v
        except Exception:
            pass
    return ""


def save_api_key(key):
    """保存 / 清除 API Key；返回是否成功写入凭据存储。"""
    if secretstore is not None and secretstore.available():
        try:
            if key:
                secretstore.save_cred(CRED_TARGET, key)
            else:
                secretstore.delete_cred(CRED_TARGET)
            return True
        except Exception as e:
            ai_log("key_store_error", str(e))
            return False
    return False


def load_connection(settings):
    """从 QSettings 读取连接配置（不含 Key）。返回 dict。

    v3.47.3：默认采用本地 Ollama（provider 缺省 = "ollama"，Base 缺省 = OLLAMA_DEFAULT_BASE）。
    仅当 provider 显式保存为其它值时才回退对应预设；未保存过则走本地优先策略。
    """
    provider = settings.value(SET_PROVIDER, "ollama", type=str)
    if provider not in [p["id"] for p in PROVIDERS]:
        provider = "custom"
    base = settings.value(SET_BASE, "", type=str).strip()
    model = settings.value(SET_MODEL, "", type=str).strip()
    if not base:
        if provider == "ollama":
            base = OLLAMA_DEFAULT_BASE
        else:
            p = provider_by_id(provider)
            base = p["base"] if p else DEFAULT_BASE
    if not model:
        p = provider_by_id(provider)
        model = (p["models"][0] if p and p["models"] else DEFAULT_MODEL)
    return {"provider": provider, "base": base, "model": model}


def save_connection(settings, provider, base, model):
    """写入连接配置（不含 Key）到 QSettings，并 sync。"""
    settings.setValue(SET_PROVIDER, provider)
    settings.setValue(SET_BASE, (base or "").strip())
    settings.setValue(SET_MODEL, (model or "").strip())
    settings.sync()


def connection_status(settings):
    """计算连接状态，供主面板状态条渲染。

    返回 dict：{configured, tested, level, text, provider, model, base}
      level = "connected" | "configured" | "unconfigured"
        connected   —— 最近一次测试连接成功（绿）
        configured  —— 已填 Base+Model 但未测 / 上次失败（黄）
        unconfigured—— 连 Base/Model 都未配置（红）
    """
    cfg = load_connection(settings)
    tested = bool(settings.value(SET_TEST_OK, False, type=bool))
    has_base = bool(cfg["base"]) and "{" not in cfg["base"] and "<" not in cfg["base"]
    has_model = bool(cfg["model"]) and "<" not in cfg["model"]
    if has_base and has_model and tested:
        level = "connected"
        text = "已连接 · %s / %s" % (cfg["provider"], cfg["model"])
    elif has_base and has_model:
        level = "configured"
        text = "已配置（未测试）· %s" % cfg["model"]
    else:
        level = "unconfigured"
        text = "未配置连接"
    return {"configured": has_base and has_model, "tested": tested,
            "level": level, "text": text,
            "provider": cfg["provider"], "model": cfg["model"], "base": cfg["base"]}


def mask_key(key):
    """脱敏显示 Key（仅首 4 位 + 星号）。"""
    if not key:
        return ""
    if len(key) <= 6:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]
