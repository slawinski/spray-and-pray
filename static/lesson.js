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
    if (typeof Chart === "undefined") {
      console.warn("Chart.js not loaded — charts will not render");
      return;
    }
    var charts = window.__chartsToRender || [];
    if (!charts.length) return;
    charts.forEach(function (c) {
      var ctx = document.getElementById(c.id);
      if (!ctx) return;
      var data = c.config;
      if (data.datasets) {
        data.datasets.forEach(function (ds) {
          if (!ds.backgroundColor && ds.borderColor) {
            ds.backgroundColor = ds.borderColor + "22";
          }
        });
      }
      try {
        new Chart(ctx, { type: c.type, data: data, options: c.options || {} });
      } catch (e) {
        console.error("Chart render failed for " + c.id + ":", e);
      }
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
            var expr = out.compute;
            Object.keys(vars).forEach(function (key) {
              expr = expr.replace(new RegExp("\\b" + key + "\\b", "g"), vars[key]);
            });
            var result = eval(expr);
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

  window.initSingleWidget = initWidgets;

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

  window.runCode = function (idx) {
    var consolePane = document.getElementById("console-" + idx);
    var outputEl = document.getElementById("console-output-" + idx);
    var timeEl = document.getElementById("exec-time-" + idx);
    var btn = document.getElementById("run-btn-" + idx);
    if (!consolePane || !outputEl || !btn) return;

    // Find the Monaco editor by looking for the container
    var editorContainer = document.getElementById("editor-" + idx);
    if (!editorContainer) return;

    // Get the editor model for this container
    var models = monaco.editor.getModels();
    var code = "";
    for (var i = 0; i < models.length; i++) {
      var uri = models[i].uri;
      var editor = monaco.editor.getEditors().find(function (e) {
        return e.getModel() && e.getModel().uri.toString() === uri.toString();
      });
      if (editor && editor.getDomNode() && editorContainer.contains(editor.getDomNode())) {
        code = editor.getValue();
        break;
      }
    }

    if (!code) {
      outputEl.innerHTML = '<span class="error">No code found in editor.</span>';
      consolePane.classList.add("visible");
      return;
    }

    // Strip import/export statements and prepare the code for sandbox execution
    var stripped = code
      .replace(/^\s*import\s+.*$/gm, "")
      .replace(/^\s*export\s+(default\s+)?/gm, "")
      .trim();

    btn.classList.add("running");
    btn.textContent = "⟳ Running...";
    consolePane.classList.add("visible");
    outputEl.innerHTML = "";
    timeEl.textContent = "";

    var startTime = performance.now();
    var logs = [];
    var timedOut = false;

    // Web Worker sandbox with React mock stubs
    var workerCode = [
      "var __logs = [];",
      "var __console = {",
      "  log: function() { __logs.push({type:'log', msg: Array.from(arguments).join(' ') }); },",
      "  warn: function() { __logs.push({type:'warn', msg: Array.from(arguments).join(' ') }); },",
      "  error: function() { __logs.push({type:'error', msg: Array.from(arguments).join(' ') }); },",
      "  info: function() { __logs.push({type:'info', msg: Array.from(arguments).join(' ') }); },",
      "};",
      // React mock stubs
      "var useRef = function(v) { return { current: v }; };",
      "var useState = function(v) { return [v, function(nv) { return nv; }]; };",
      "var useEffect = function(fn, deps) { try { fn(); } catch(e) {} };",
      "var useCallback = function(fn) { return fn; };",
      "var useMemo = function(fn) { return fn(); };",
      "var useReducer = function(r, i) { return [i, function(a) { return r(i, a); }]; };",
      "var useContext = function() { return {}; };",
      "self.onmessage = function(e) {",
      "  try {",
      "    var fn = new Function('console', e.data.code);",
      "    fn(__console);",
      "    self.postMessage({ type: 'done', logs: __logs });",
      "  } catch(err) {",
      "    __logs.push({type:'error', msg: err.toString() });",
      "    self.postMessage({ type: 'done', logs: __logs });",
      "  }",
      "};",
    ].join("\n");

    var blob = new Blob([workerCode], { type: "application/javascript" });
    var worker = new Worker(URL.createObjectURL(blob));

    var timeout = setTimeout(function () {
      timedOut = true;
      worker.terminate();
      finish();
    }, 5000);

    function finish() {
      var elapsed = Math.round(performance.now() - startTime);
      clearTimeout(timeout);
      btn.classList.remove("running");
      btn.textContent = "▶ Run";
      timeEl.textContent = elapsed + "ms";

      if (timedOut) {
        logs.push({ type: "error", msg: "Execution timed out (5s limit). Check for infinite loops." });
      }

      if (logs.length === 0) {
        outputEl.innerHTML = '<span class="info">Code ran with no output.</span>';
        return;
      }

      outputEl.innerHTML = logs
        .map(function (l) {
          return '<span class="' + l.type + '">&gt; ' + escapeHtml(l.msg) + "</span>";
        })
        .join("\n");
    }

    worker.onmessage = function (e) {
      if (e.data.type === "done") {
        logs = e.data.logs;
        worker.terminate();
        finish();
      }
    };

    worker.onerror = function (e) {
      logs.push({ type: "error", msg: "Worker error: " + (e.message || "unknown") });
      worker.terminate();
      finish();
    };

    worker.postMessage({ code: stripped });
  };

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }

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
