from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

from .config import project_root


def _load_system_prompt() -> str:
    p = project_root() / "prompts" / "trading_advisor.txt"
    return p.read_text(encoding="utf-8")


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text


def propose_actions(
    *,
    api_key: str,
    model: str,
    user_payload: dict[str, Any],
) -> dict[str, Any]:
    client = OpenAI(api_key=api_key)
    system = _load_system_prompt()
    user = json.dumps(user_payload, indent=2)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(_strip_json_fence(raw))
