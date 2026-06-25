(function () {
  var dataEl = document.getElementById("session-data");
  if (!dataEl) return;
  var data = JSON.parse(dataEl.textContent);

  if (data.evaluated) {
    window.location.href = "/api/interview/" + data.sessionId + "/report";
    return;
  }

  var sessionId = data.sessionId;
  var questions = data.questions;
  var answers = data.answers || [];
  var currentIdx = 0;
  var monacoEditor = null;
  var totalQuestions = questions.length;

  var answerMap = {};
  answers.forEach(function (a) {
    answerMap[a.question_id] = a;
  });

  function renderQuestion() {
    if (currentIdx >= totalQuestions) {
      showCompleted();
      return;
    }

    var q = questions[currentIdx];
    var ans = answerMap[q.id] || { answer_text: "", code: "" };

    document.getElementById("question-prompt").textContent = q.prompt;
    document.getElementById("question-context").textContent = q.context || "";
    document.getElementById("time-estimate").textContent =
      "Estimated: ~" + (q.time_estimate_seconds
        ? Math.ceil(q.time_estimate_seconds / 60) + " min"
        : "5 min");

    var badge = document.getElementById("type-badge");
    badge.textContent = q.type.replace(/_/g, " ");
    badge.className = "badge";
    if (q.type === "coding") badge.className += " coding";

    document.getElementById("question-counter").textContent =
      "Question " + (currentIdx + 1) + " / " + totalQuestions;

    var progressPct = Math.round((currentIdx / totalQuestions) * 100);
    document.getElementById("progress-fill").style.width = progressPct + "%";

    document.getElementById("hint-box").classList.remove("visible");
    document.getElementById("hint-text").textContent = q.hint || "";
    var conceptsDiv = document.getElementById("hint-concepts");
    conceptsDiv.innerHTML = "";
    var deepDive = document.getElementById("hint-deep-dive");
    deepDive.style.display = "none";
    if (q.expected_concepts) {
      q.expected_concepts.forEach(function (c) {
        var span = document.createElement("span");
        span.textContent = c;
        conceptsDiv.appendChild(span);
      });
      var dl = document.getElementById("hint-concept-name");
      if (q.expected_concepts[0] && dl) {
        dl.textContent = q.expected_concepts[0];
        deepDive.href = "/prepare-learn?concept=" + encodeURIComponent(q.expected_concepts[0]) + "&session_id=" + sessionId;
        deepDive.style.display = "inline-block";
      }
    }

    document.getElementById("prev-btn").disabled = currentIdx === 0;
    var nextBtn = document.getElementById("next-btn");
    if (currentIdx === totalQuestions - 1) {
      nextBtn.textContent = "Finish →";
    } else {
      nextBtn.textContent = "Next →";
    }

    if (q.type === "coding") {
      document.getElementById("answer-area").style.display = "none";
      document.getElementById("monaco-container").style.display = "block";
      initMonaco(q, ans);
    } else {
      document.getElementById("answer-area").style.display = "block";
      document.getElementById("monaco-container").style.display = "none";
      if (monacoEditor) {
        monacoEditor.dispose();
        monacoEditor = null;
      }
      document.getElementById("answer-textarea").value = ans.answer_text || "";
    }
  }

  function initMonaco(q, ans) {
    function createEditor() {
      var lang = q.language || "javascript";
      var starter = ans.code || q.starter_code || "";
      if (monacoEditor) monacoEditor.dispose();
      monacoEditor = monaco.editor.create(
        document.getElementById("monaco-container"),
        {
          value: starter,
          language: lang,
          theme: "vs-dark",
          minimap: { enabled: false },
          automaticLayout: true,
          fontSize: 13,
          lineNumbers: "on",
          scrollBeyondLastLine: false,
        }
      );
    }

    if (window.__monacoReady) {
      createEditor();
    } else {
      window.__onMonacoReady = function () {
        createEditor();
      };
    }
  }

  function saveCurrentAnswer() {
    var q = questions[currentIdx];
    if (!q) return;
    var answerText = "";
    var code = "";
    if (q.type === "coding" && monacoEditor) {
      code = monacoEditor.getValue();
    } else {
      answerText = document.getElementById("answer-textarea").value;
    }
    answerMap[q.id] = {
      question_id: q.id,
      answer_text: answerText,
      code: code,
    };
    saveToServer(q.id, answerText, code);
  }

  function saveToServer(questionId, answerText, code) {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/interview/" + sessionId + "/answer", true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(
      JSON.stringify({
        question_id: questionId,
        answer_text: answerText,
        code: code,
      })
    );
  }

  function navigate(dir) {
    saveCurrentAnswer();
    currentIdx += dir;
    if (currentIdx >= totalQuestions) {
      showCompleted();
      return;
    }
    if (currentIdx < 0) currentIdx = 0;
    renderQuestion();
  }

  function showCompleted() {
    document.getElementById("app").style.display = "none";
    document.getElementById("completed-section").style.display = "block";
    var answered = Object.keys(answerMap).length;
    document.getElementById("question-counter").textContent =
      answered + " / " + totalQuestions + " answered";
    document.getElementById("progress-fill").style.width = "100%";
  }

  document.getElementById("prev-btn").addEventListener("click", function () {
    navigate(-1);
  });
  document.getElementById("next-btn").addEventListener("click", function () {
    navigate(1);
  });
  document.getElementById("hint-btn").addEventListener("click", function () {
    document.getElementById("hint-box").classList.toggle("visible");
  });
  document.getElementById("submit-btn").addEventListener("click", function () {
    document.getElementById("eval-spinner").classList.add("visible");
    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/interview/" + sessionId + "/evaluate", true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onload = function () {
      if (xhr.status === 200) {
        window.location.href =
          "/api/interview/" + sessionId + "/report";
      } else {
        document.getElementById("eval-spinner").classList.remove("visible");
        alert("Evaluation failed: " + xhr.responseText);
      }
    };
    xhr.onerror = function () {
      document.getElementById("eval-spinner").classList.remove("visible");
      alert("Evaluation failed — server unreachable.");
    };
    xhr.send();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft" && !e.metaKey && !e.ctrlKey && !e.altKey) {
      if (document.getElementById("prev-btn").disabled) return;
      navigate(-1);
    } else if (e.key === "ArrowRight" && !e.metaKey && !e.ctrlKey && !e.altKey) {
      navigate(1);
    }
  });

  renderQuestion();
})();
