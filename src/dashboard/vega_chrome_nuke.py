"""Remove Vega-Lite embed actions (⋯) and chart toolbar; CSS alone is often not enough."""

from __future__ import annotations

# Runs in the component iframe, manipulates the parent (main app) document — same origin.
_VEGA_NUKE_HTML = """
<div style="height:0;width:0;overflow:hidden" aria-hidden="true"> </div>
<script>
(function () {
  var r = window.parent.document;
  function nuke() {
    try {
      r.querySelectorAll(
        ".stApp .vega-embed > details, .stApp [data-testid='stVegaLiteChart'] > details, " +
        ".stApp [data-testid='stAltairChart'] > details, " +
        ".stApp [data-testid='stVegaLiteChart'] details, " +
        ".stApp [data-testid='stAltairChart'] details"
      ).forEach(function (n) { n.remove(); });
      r.querySelectorAll(".stApp .vega-embed .vega-actions").forEach(function (n) { n.remove(); });
      r.querySelectorAll("[data-testid='stVegaLiteChart'],[data-testid='stAltairChart']").forEach(function (ch) {
        var s = ch.previousElementSibling;
        var k = 0;
        while (s && k++ < 5) {
          if (s.getAttribute && s.getAttribute("data-testid") === "stElementToolbar") s.remove();
          s = s.previousElementSibling;
        }
      });
    } catch (e) {}
  }
  nuke();
  var t = setInterval(nuke, 400);
  var app = r.querySelector(".stApp");
  if (app) {
    new MutationObserver(function () { nuke(); }).observe(app, { subtree: true, childList: true });
  }
  window.addEventListener("load", nuke);
})();
</script>
"""


def inject_vega_chrome_nuke() -> None:
    import streamlit.components.v1 as components

    components.html(_VEGA_NUKE_HTML, height=1, scrolling=False)
