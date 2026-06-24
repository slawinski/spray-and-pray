(function () {
  function initMonacoEditors() {
    document.querySelectorAll(".editor-container").forEach(function (el) {
      var lang = el.getAttribute("data-language") || "javascript";
      var code = el.getAttribute("data-starter") || el.getAttribute("data-code") || "";
      var isReadonly = el.id && el.id.indexOf("solution-") === 0;

      function create() {
        monaco.editor.create(el, {
          value: code,
          language: lang,
          theme: "vs-dark",
          minimap: { enabled: false },
          automaticLayout: true,
          readOnly: isReadonly,
          fontSize: 13,
          lineNumbers: "on",
          scrollBeyondLastLine: false,
        });
      }

      if (window.__monacoReady) {
        create();
      } else {
        var prev = window.__onMonacoReady;
        window.__onMonacoReady = function () {
          if (prev) prev();
          create();
        };
      }
    });
  }

  function initCharts() {
    var charts = window.__chartsToRender || [];
    charts.forEach(function (c) {
      var ctx = document.getElementById(c.id);
      if (!ctx) return;
      var data = c.config;
      data.datasets.forEach(function (ds) {
        if (!ds.backgroundColor && ds.borderColor) {
          ds.backgroundColor = ds.borderColor + "22";
        }
      });
      new Chart(ctx, { type: c.type, data: data, options: c.options || {} });
    });
  }

  function initWidgets() {
    var widgets = window.__widgetsToInit || [];
    widgets.forEach(function (w) {
      function getControlValue(ctrl) {
        var el = document.getElementById("ctrl-" + ctrl.id);
        if (!el) return ctrl.default;
        if (ctrl.type === "toggle") return el.checked;
        return parseFloat(el.value);
      }

      function recompute() {
        var vars = {};
        w.controls.forEach(function (ctrl) {
          vars[ctrl.id] = getControlValue(ctrl);
          if (ctrl.type === "range") {
            var valEl = document.getElementById("val-" + ctrl.id);
            if (valEl) valEl.textContent = vars[ctrl.id];
          }
        });

        w.outputs.forEach(function (out) {
          var outEl = document.getElementById("out-" + out.id);
          if (!outEl) return;
          try {
            var fn = new Function(
              ...Object.keys(vars),
              '"use strict"; return (' + out.compute + ");"
            );
            var result = fn(...Object.values(vars));
            outEl.textContent = typeof result === "number" ? Math.round(result).toLocaleString() : result;
          } catch (e) {
            outEl.textContent = "—";
          }
        });
      }

      w.controls.forEach(function (ctrl) {
        var el = document.getElementById("ctrl-" + ctrl.id);
        if (!el) return;
        el.addEventListener("input", recompute);
        el.addEventListener("change", recompute);
      });
      recompute();
    });
  }

  window.toggleSolution = function (idx) {
    var block = document.getElementById("solution-" + idx);
    var btn = document.getElementById("solution-btn-" + idx);
    if (!block || !btn) return;
    var isVisible = block.classList.contains("visible");
    if (isVisible) {
      block.classList.remove("visible");
      btn.textContent = "Show Solution";
    } else {
      block.classList.add("visible");
      btn.textContent = "Hide Solution";
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initMonacoEditors();
      initCharts();
      initWidgets();
    });
  } else {
    initMonacoEditors();
    initCharts();
    initWidgets();
  }
})();
