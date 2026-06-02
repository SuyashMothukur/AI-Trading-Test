"""Global dashboard CSS (injected once via Streamlit markdown)."""

from __future__ import annotations

DASHBOARD_CSS = """
<style>
  :root {
    --bg-deep: #050810;
    --bg-main: #080d18;
    --bg-elevated: #0c1424;
    --bg-card: rgba(14, 22, 40, 0.92);
    --bg-card-soft: rgba(10, 16, 30, 0.88);
    --text-primary: #e8eefc;
    --text-muted: #8b9ab8;
    --text-dim: #6a7a9a;
    --line-soft: rgba(100, 130, 180, 0.18);
    --line-medium: rgba(120, 150, 200, 0.28);
    --accent: #38bdf8;
    --accent-soft: rgba(56, 189, 248, 0.14);
    --good: #34d399;
    --good-bg: rgba(52, 211, 153, 0.1);
    --bad: #fb7185;
    --bad-bg: rgba(251, 113, 133, 0.1);
    --warn: #fbbf24;
    --radius: 12px;
    --radius-sm: 9px;
    --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255,255,255,0.03);
  }
  .stApp {
    background:
      radial-gradient(1000px 480px at 8% -8%, rgba(56, 189, 248, 0.09) 0%, transparent 55%),
      radial-gradient(800px 400px at 92% 0%, rgba(99, 102, 241, 0.06) 0%, transparent 50%),
      linear-gradient(165deg, var(--bg-deep) 0%, var(--bg-main) 42%, #060912 100%) !important;
    color: var(--text-primary);
  }
  .block-container {
    padding-top: 0.75rem !important;
    padding-bottom: 1rem !important;
    max-width: 1520px !important;
    padding-left: 1.1rem !important;
    padding-right: 1.1rem !important;
  }
  div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
    gap: 0.35rem;
  }
  div[data-testid="column"] {
    padding-top: 0.2rem !important;
    padding-bottom: 0.2rem !important;
    gap: 0.35rem;
    min-width: 0 !important;
  }
  div[data-testid="stHorizontalBlock"] {
    gap: 0.35rem !important;
  }
  .dash-brand {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin: 0 0 10px 0;
    flex-wrap: wrap;
  }
  .dash-brand h1 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: #f1f5ff;
  }
  .dash-brand span {
    font-size: 0.72rem;
    color: var(--text-dim);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .pnl-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    margin-bottom: 8px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line-soft);
    background: linear-gradient(155deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.85) 100%);
  }
  .pnl-banner-gain {
    border-color: rgba(34, 197, 94, 0.45);
    box-shadow: 0 0 24px rgba(34, 197, 94, 0.12);
  }
  .pnl-banner-loss {
    border-color: rgba(244, 63, 94, 0.45);
    box-shadow: 0 0 24px rgba(244, 63, 94, 0.12);
  }
  .pnl-banner-flat {
    border-color: rgba(148, 163, 184, 0.35);
  }
  .pnl-banner-state {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 5px 10px;
    border-radius: 999px;
    flex-shrink: 0;
  }
  .pnl-banner-gain .pnl-banner-state {
    color: #86efac;
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.35);
  }
  .pnl-banner-loss .pnl-banner-state {
    color: #fda4af;
    background: rgba(244, 63, 94, 0.15);
    border: 1px solid rgba(244, 63, 94, 0.35);
  }
  .pnl-banner-flat .pnl-banner-state {
    color: #cbd5e1;
    background: rgba(148, 163, 184, 0.12);
    border: 1px solid rgba(148, 163, 184, 0.3);
  }
  .pnl-banner-headline {
    font-size: 0.92rem;
    font-weight: 650;
    color: #e2e8f0;
    line-height: 1.35;
  }
  .metric-strip {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 6px;
  }
  @media (max-width: 1200px) {
    .metric-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  }
  @media (max-width: 640px) {
    .metric-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
  .metric-tile {
    position: relative;
    border: 1px solid var(--line-soft);
    border-radius: var(--radius-sm);
    padding: 10px 12px;
    background: linear-gradient(155deg, var(--bg-card) 0%, var(--bg-card-soft) 100%);
    box-shadow: var(--shadow-card);
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
  }
  .metric-tile:hover {
    border-color: var(--line-medium);
    box-shadow: 0 6px 28px rgba(0,0,0,0.4), 0 0 0 1px rgba(56,189,248,0.08);
  }
  .metric-tile.glow-equity {
    border-color: rgba(56, 189, 248, 0.35);
    box-shadow: 0 0 28px rgba(56, 189, 248, 0.12), var(--shadow-card);
  }
  .metric-tile .k {
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted);
    font-weight: 650;
  }
  .metric-tile .v {
    margin-top: 6px;
    font-size: 1.32rem;
    font-weight: 780;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.01em;
    color: #f8fafc;
    line-height: 1.1;
  }
  .metric-tile .sub {
    margin-top: 4px;
    font-size: 0.68rem;
    color: var(--text-dim);
  }
  .metric-tile .tone-up { color: #6ee7b7 !important; }
  .metric-tile .tone-down { color: #fda4af !important; }
  .metric-tile-pnl-gain {
    border-color: rgba(34, 197, 94, 0.5) !important;
    box-shadow: 0 0 20px rgba(34, 197, 94, 0.14), var(--shadow-card);
  }
  .metric-tile-pnl-loss {
    border-color: rgba(244, 63, 94, 0.5) !important;
    box-shadow: 0 0 20px rgba(244, 63, 94, 0.14), var(--shadow-card);
  }
  .pnl-pct-chip {
    font-size: 0.78rem;
    font-weight: 650;
    opacity: 0.9;
    margin-left: 4px;
  }
  .session-clock {
    text-align: center;
    padding: 6px 12px;
    margin: 0 auto 8px auto;
    max-width: 400px;
    border: 1px solid var(--line-medium);
    border-radius: var(--radius-sm);
    background: rgba(8, 14, 28, 0.75);
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .session-clock-time {
    font-variant-numeric: tabular-nums;
    font-weight: 650;
    color: #e8f0ff;
    font-size: 0.88rem;
  }
  .session-clock-up {
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    color: #c7d9f5;
  }
  .session-clock-sub {
    display: block;
    margin-top: 2px;
    font-size: 0.72rem;
    color: var(--text-dim);
  }
  .panel {
    border: 1px solid var(--line-soft);
    border-radius: var(--radius);
    background: linear-gradient(180deg, var(--bg-card) 0%, rgba(8, 13, 26, 0.95) 100%);
    box-shadow: var(--shadow-card);
    padding: 10px 12px;
    margin-bottom: 6px;
    transition: border-color 0.2s ease;
  }
  .panel:hover { border-color: rgba(120, 150, 200, 0.22); }
  .panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 6px;
  }
  .panel-title {
    margin: 0;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #8b9ab8;
  }
  .panel-sub { font-size: 0.68rem; color: var(--text-dim); }
  /*
    Never wrap st.altair_chart in a separate st.markdown open/only <div> — Streamlit
    mounts the chart as the *next* block, so the div is empty and shows up as a thin
    "pill" bar (border + top glow). Style the real chart node instead.
  */
  /* Modern Streamlit uses stVegaLiteChart; older versions used stAltairChart. */
  div[data-testid="stVegaLiteChart"],
  div[data-testid="stAltairChart"] {
    width: 100% !important;
    max-width: min(100%, 1120px) !important;
    margin-left: auto;
    margin-right: auto;
    overflow: hidden !important;
    position: relative;
    z-index: 0;
    isolation: isolate;
    contain: layout;
    border-radius: var(--radius);
    border: 1px solid rgba(80, 120, 180, 0.22);
    background:
      radial-gradient(900px 280px at 15% 0%, rgba(56, 189, 248, 0.08), transparent 55%),
      radial-gradient(700px 200px at 95% 10%, rgba(99, 102, 241, 0.05), transparent 50%),
      linear-gradient(180deg, rgba(12, 20, 38, 0.95), rgba(5, 8, 16, 0.98));
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 12px 40px rgba(0, 2, 12, 0.45);
    padding: 6px 4px 2px 6px;
    box-sizing: border-box;
    animation: chartReveal 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
  }
  /* Streamlit often sets data-testid and .vega-embed on the SAME node — not a child. */
  div[data-testid="stVegaLiteChart"] .vega-embed,
  div[data-testid="stVegaLiteChart"].vega-embed,
  div[data-testid="stAltairChart"] .vega-embed,
  div[data-testid="stAltairChart"].vega-embed {
    width: 100% !important;
    max-width: 100% !important;
    overflow: hidden !important;
  }
  /* useVegaEmbed uses forceActionsMenu; also hide row toolbar (fullscreen, overflow) above chart. */
  *:has(> [data-testid="stVegaLiteChart"]) [data-testid="stElementToolbar"],
  *:has(> [data-testid="stAltairChart"]) [data-testid="stElementToolbar"] {
    display: none !important;
    width: 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
    padding: 0 !important;
    border: none !important;
  }
  [data-testid="stVegaLiteChart"] details,
  [data-testid="stVegaLiteChart"] details > summary,
  [data-testid="stVegaLiteChart"] .vega-embed details,
  [data-testid="stVegaLiteChart"] .vega-embed details > summary,
  [data-testid="stVegaLiteChart"] details[title="Click to view actions"],
  [data-testid="stAltairChart"] details,
  [data-testid="stAltairChart"] details > summary,
  [data-testid="stAltairChart"] .vega-embed details,
  [data-testid="stAltairChart"] .vega-embed details > summary,
  [data-testid="stAltairChart"] details[title="Click to view actions"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    max-height: 0 !important;
    opacity: 0 !important;
    pointer-events: none !important;
    position: absolute !important;
    left: -9999px !important;
  }
  [data-testid="stVegaLiteChart"] .vega-actions,
  [data-testid="stAltairChart"] .vega-actions,
  [data-testid="stVegaLiteChart"] .vega-embed .vega-actions,
  [data-testid="stAltairChart"] .vega-embed .vega-actions {
    display: none !important;
  }
  .chart-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 6px;
    padding: 0 2px;
  }
  .chart-toolbar .sym {
    font-size: 0.72rem;
    color: var(--text-dim);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  @keyframes chartReveal {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .health-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .health-card {
    border: 1px solid var(--line-soft);
    border-radius: var(--radius-sm);
    padding: 8px 10px;
    background: rgba(8, 14, 26, 0.72);
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: background 0.2s ease, border-color 0.2s ease;
  }
  .health-card:hover {
    background: rgba(12, 20, 36, 0.88);
    border-color: var(--line-medium);
  }
  .health-card .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
  }
  .health-dot {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    flex-shrink: 0;
  }
  .dot-good { background: var(--good); box-shadow: 0 0 8px rgba(52,211,153,0.55); }
  .dot-bad { background: var(--bad); box-shadow: 0 0 8px rgba(251,113,133,0.45); }
  .dot-neutral { background: #94a3b8; }
  .dot-warn { background: var(--warn); box-shadow: 0 0 8px rgba(251,191,36,0.45); }
  .health-k {
    font-size: 0.6rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
    font-weight: 650;
  }
  .health-v {
    font-size: 0.95rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: #eef4ff;
    text-align: right;
  }
  .status-line {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 14px;
    font-size: 0.74rem;
    color: var(--text-muted);
    margin: 8px 0 6px 0;
    padding: 6px 8px;
    border-radius: var(--radius-sm);
    background: rgba(6, 10, 20, 0.55);
    border: 1px solid var(--line-soft);
  }
  .status-line b { color: #dbeafe; font-weight: 650; }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .pill-on { background: var(--good-bg); color: #6ee7b7; border: 1px solid rgba(52,211,153,0.35); }
  .pill-off { background: var(--bad-bg); color: #fda4af; border: 1px solid rgba(251,113,133,0.35); }
  .pill-warn { background: rgba(251, 191, 36, 0.12); color: #fcd34d; border: 1px solid rgba(251,191,36,0.35); }
  .panel.run-health-stack {
    align-self: start;
  }
  .panel-head.run-health-head {
    position: relative;
    z-index: 4;
    margin: -2px -2px 6px -2px;
    padding: 6px 8px;
    border-radius: var(--radius-sm);
    background: linear-gradient(180deg, rgba(14, 22, 42, 0.98), rgba(10, 16, 30, 0.96));
    border: 1px solid rgba(80, 120, 180, 0.2);
  }
  .activity-feed {
    max-height: 200px;
    min-height: 0;
    overflow-y: auto;
    font-size: 0.72rem;
    color: var(--text-muted);
    border: 1px solid var(--line-soft);
    border-radius: var(--radius-sm);
    padding: 6px 8px;
    background: rgba(5, 9, 18, 0.65);
  }
  .activity-feed div {
    padding: 5px 4px;
    border-bottom: 1px solid rgba(80, 100, 140, 0.12);
  }
  .activity-feed div:last-child { border-bottom: none; }
  .activity-feed .t { color: var(--text-dim); font-variant-numeric: tabular-nums; margin-right: 6px; }
  .chart-empty {
    border: 1px dashed rgba(100, 130, 180, 0.35);
    border-radius: var(--radius-sm);
    padding: 20px 14px;
    text-align: center;
    color: var(--text-muted);
    background: rgba(6, 10, 20, 0.5);
    font-size: 0.8rem;
  }
  .table-wrap {
    border: 1px solid var(--line-soft);
    border-radius: var(--radius-sm);
    overflow-x: auto;
    overflow-y: auto;
    max-height: min(42vh, 340px);
    margin-top: 6px;
  }
  table.positions {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  table.positions th {
    text-align: left;
    padding: 7px 8px;
    background: rgba(10, 16, 30, 0.95);
    color: #7c8ca8;
    font-weight: 650;
    font-size: 0.62rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border-bottom: 1px solid rgba(100, 130, 180, 0.2);
  }
  table.positions td {
    padding: 6px 8px;
    border-bottom: 1px solid rgba(80, 110, 150, 0.1);
    color: #dce8ff;
    transition: background 0.15s ease;
  }
  table.positions tbody tr:hover td {
    background: rgba(56, 189, 248, 0.06);
  }
  table.positions tr:last-child td { border-bottom: none; }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .symbol-cell { font-weight: 700; letter-spacing: 0.03em; color: #f1f5ff; }
  .pl-pos { color: #6ee7b7; font-weight: 650; }
  .pl-neg { color: #fda4af; font-weight: 650; }
  .pl-flat { color: #a8b8d8; font-weight: 600; }
  .skel {
    border-radius: var(--radius-sm);
    background: linear-gradient(90deg, rgba(30,40,60,0.35) 25%, rgba(50,65,95,0.45) 50%, rgba(30,40,60,0.35) 75%);
    background-size: 200% 100%;
    animation: skel 1.1s ease-in-out infinite;
    min-height: 120px;
  }
  @keyframes skel {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
  [data-baseweb="tab-list"] {
    gap: 6px;
    padding: 5px;
    background: rgba(8, 14, 26, 0.72);
    border: 1px solid var(--line-soft);
    border-radius: var(--radius-sm);
    margin: 6px 0 10px 0;
  }
  button[role="tab"] {
    border-radius: 8px !important;
    height: 32px !important;
    padding: 0 12px !important;
    color: #8b9ab8 !important;
    border: 1px solid transparent !important;
    background: transparent !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
  }
  button[role="tab"][aria-selected="true"] {
    color: #e8f0ff !important;
    background: var(--accent-soft) !important;
    border-color: rgba(56, 189, 248, 0.4) !important;
  }
  .trace-box {
    border: 1px solid var(--line-soft);
    border-radius: var(--radius-sm);
    padding: 8px 10px;
    background: rgba(8, 14, 26, 0.72);
    margin-bottom: 6px;
    font-size: 0.82rem;
    color: var(--text-muted);
    transition: border-color 0.2s ease, background 0.2s ease;
  }
  .trace-box:hover {
    border-color: var(--line-medium);
    background: rgba(10, 18, 34, 0.88);
  }
  .trace-box b { color: #dbeafe; }
</style>
"""

# Injected at end of ui.py so it wins the cascade over Streamlit theme/embedded rules.
# Covers (1) Streamlit's stElementToolbar row (fullscreen) above Vega-Lite, (2) vega-embed details/⋯
DASHBOARD_CHART_CHROME_LAST = """
<style>
  html body *:has(> [data-testid="stVegaLiteChart"]) [data-testid="stElementToolbar"],
  html body *:has(> [data-testid="stAltairChart"]) [data-testid="stElementToolbar"] {
    display: none !important;
  }
  html body [data-testid="stVegaLiteChart"] details,
  html body [data-testid="stVegaLiteChart"] details > summary,
  html body [data-testid="stVegaLiteChart"] .vega-embed details,
  html body [data-testid="stVegaLiteChart"] .vega-embed details > summary,
  html body [data-testid="stAltairChart"] details,
  html body [data-testid="stAltairChart"] details > summary,
  html body [data-testid="stAltairChart"] .vega-embed details,
  html body [data-testid="stAltairChart"] .vega-embed details > summary {
    display: none !important;
  }
  html body [data-testid="stVegaLiteChart"] .vega-actions,
  html body [data-testid="stAltairChart"] .vega-actions {
    display: none !important;
  }
  html body .stApp .vega-embed > details,
  html body .stApp .vega-embed details,
  html body .stApp .vega-embed > details > summary {
    display: none !important;
    visibility: hidden !important;
  }
</style>
"""


def inject_dashboard_styles() -> None:
    import streamlit as st

    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)


def inject_chart_chrome_last() -> None:
    """Call once at end of the script (after all widgets) so these rules are last in the page."""
    import streamlit as st

    st.markdown(DASHBOARD_CHART_CHROME_LAST, unsafe_allow_html=True)
