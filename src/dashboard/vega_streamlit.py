"""Vega / Altair options that Streamlit's chart element actually honors."""

from __future__ import annotations

from typing import Any


def disable_vega_embed_actions(chart: Any) -> Any:
    """Set ``usermeta.embedOptions.actions`` (for spec consumers).

    Streamlit's ``ArrowVegaLiteChart`` calls vega-embed with
    ``forceActionsMenu: true``, which overrides this flag, so the UI menu is
    hidden via CSS on ``[data-testid="stVegaLiteChart"]`` in ``styles.py``.
    """
    out = chart.copy()
    prev = dict(out.to_dict().get("usermeta") or {})
    embed = dict(prev.get("embedOptions") or {})
    embed["actions"] = False
    prev["embedOptions"] = embed
    out["usermeta"] = prev
    return out
