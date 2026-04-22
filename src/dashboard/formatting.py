"""Shared number formatting for the Streamlit dashboard."""

from __future__ import annotations


def fmt_currency(value: float | int | None) -> str:
    if value is None:
        return "—"
    return f"${float(value):,.2f}"


def fmt_signed_currency(value: float | int | None) -> str:
    if value is None:
        return "—"
    f = float(value)
    return f"+${abs(f):,.2f}" if f >= 0 else f"−${abs(f):,.2f}"


def fmt_percent(value: float | int | None, *, decimals: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:+.{decimals}f}%"


def fmt_percent_plain(value: float | int | None, *, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.{decimals}f}%"
