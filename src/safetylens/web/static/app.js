// Draw every chart placeholder (div.chart with a Vega-Lite spec in data-spec), on page load and
// after HTMX swaps in an answer. Specs are built server-side from SQL rows only.
function drawCharts(root) {
  root.querySelectorAll("div.chart:not([data-drawn])").forEach(function (el) {
    el.setAttribute("data-drawn", "1");
    vegaEmbed(el, JSON.parse(el.dataset.spec), { actions: false }).catch(function () {
      el.textContent = "Chart could not be drawn.";
    });
  });
}
document.addEventListener("DOMContentLoaded", function () { drawCharts(document); });
document.body.addEventListener("htmx:afterSwap", function (e) { drawCharts(e.target); });
