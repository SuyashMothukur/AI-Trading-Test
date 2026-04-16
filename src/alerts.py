from __future__ import annotations

import httpx


def send_webhook_alert(webhook_url: str, title: str, message: str) -> None:
    if not webhook_url:
        return
    payload = {"text": f"{title}\n{message}"}
    try:
        httpx.post(webhook_url, json=payload, timeout=10.0)
    except Exception:
        # Alerting must never break trading loop.
        return

