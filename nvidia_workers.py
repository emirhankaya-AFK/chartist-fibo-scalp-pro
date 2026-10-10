"""NVIDIA Nemotron worker bridge.

Local development can read the user's private TXT file. Cloud deployments
must provide NVIDIA_API_KEY (or separate worker keys) as secret environment
variables. Secrets are never returned by the API.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
ULTRA_MODEL = os.getenv("NVIDIA_ULTRA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
SUPER_MODEL = os.getenv("NVIDIA_SUPER_MODEL", "nvidia/nemotron-3-super-120b-a12b")
KEY_FILE = Path(os.getenv("NVIDIA_KEY_FILE", str(Path(__file__).resolve().parent / "New Text Document.txt")))
_log: list[dict] = []


def _keys_from_file() -> list[str]:
    if not KEY_FILE.exists():
        return []
    text = KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    return re.findall(r"nvapi-[A-Za-z0-9_-]+", text)


def _key_for(worker: str) -> str:
    specific = os.getenv("NVIDIA_ULTRA_API_KEY" if worker == "ultra" else "NVIDIA_SUPER_API_KEY", "").strip()
    if specific:
        return specific
    shared = os.getenv("NVIDIA_API_KEY", "").strip()
    if shared:
        return shared
    keys = _keys_from_file()
    if worker == "ultra" and len(keys) >= 2:
        return keys[1]
    return keys[0] if keys else ""


def worker_status() -> dict:
    return {
        "status": "ready" if (_key_for("ultra") and _key_for("super")) else "missing_key",
        "endpoint": BASE_URL,
        "workers": {
            "ultra": {"model": ULTRA_MODEL, "configured": bool(_key_for("ultra"))},
            "super": {"model": SUPER_MODEL, "configured": bool(_key_for("super"))},
        },
        "requests": len(_log),
    }


def ask_worker(worker: str, prompt: str, max_tokens: int = 1024) -> dict:
    worker = worker.lower().strip()
    if worker not in {"ultra", "super"}:
        raise ValueError("worker ultra veya super olmalı")
    if not prompt.strip():
        raise ValueError("prompt boş olamaz")
    key = _key_for(worker)
    if not key:
        raise RuntimeError("NVIDIA API anahtarı bulunamadı")
    model = ULTRA_MODEL if worker == "ultra" else SUPER_MODEL
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Türkçe cevap ver. Demo işlem kararını gerekçelendir; kesin kazanç iddiası yapma."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": max(64, min(int(max_tokens), 4096)),
        "stream": False,
    }
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))
    usage = result.get("usage") or {}
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "worker": worker,
        "model": model,
        "prompt": prompt,
        "response": result.get("choices", [{}])[0].get("message", {}).get("content", ""),
        "usage": usage,
    }
    _log.append(record)
    return record


def worker_log() -> list[dict]:
    return list(_log)
