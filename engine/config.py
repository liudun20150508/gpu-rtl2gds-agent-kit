# -*- coding: utf-8 -*-
"""引擎配置与 LLM 调用。

三种模式：
  offline —— 纯规则引擎，零网络依赖（默认）
  openai  —— 任意 OpenAI 兼容端点
  ollama  —— 本地 Ollama
"""
import json
import os

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULTS = {
    "mode": "offline",
    "openai": {"base_url": "https://api.openai.com/v1", "api_key": "", "model": "gpt-4o"},
    "ollama": {"base_url": "http://localhost:11434", "model": "qwen2.5-coder:14b"},
    "max_iterations": 5,
    "slack_threshold_ps": 0.0,
}


def load_config(path=None):
    cfg = json.loads(json.dumps(DEFAULTS))
    path = path or os.environ.get("RTL2GDS_ENGINE_CONFIG", DEFAULT_PATH)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def llm_call(cfg, system, user, temperature=0.2):
    """统一 LLM 调用入口；失败时抛异常，由调用方回退规则引擎。"""
    import urllib.request
    mode = cfg.get("mode", "offline")
    if mode == "offline":
        raise RuntimeError("offline 模式未配置 LLM 端点（使用规则引擎）")
    if mode == "openai":
        url = cfg["openai"]["base_url"].rstrip("/") + "/chat/completions"
        key = cfg["openai"].get("api_key") or os.environ.get("OPENAI_API_KEY", "")
        model = cfg["openai"]["model"]
    elif mode == "ollama":
        url = cfg["ollama"]["base_url"].rstrip("/") + "/api/chat"
        key, model = "", cfg["ollama"]["model"]
    else:
        raise RuntimeError(f"未知 mode: {mode}")
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature,
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    if mode == "openai":
        return data["choices"][0]["message"]["content"]
    return data["message"]["content"]
