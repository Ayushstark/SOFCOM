const promptEl = document.querySelector("#prompt");
const generateBtn = document.querySelector("#generate");
const evaluateBtn = document.querySelector("#evaluate");
const jsonEl = document.querySelector("#json");
const validationEl = document.querySelector("#validation");
const validationPanel = document.querySelector("#validationPanel");
const assumptionsEl = document.querySelector("#assumptions");
const assumptionsPanel = document.querySelector("#assumptionsPanel");
const previewLink = document.querySelector("#previewLink");
const previewPanel = document.querySelector("#previewPanel");
const logStreamEl = document.querySelector("#logStream");
const clearLogBtn = document.querySelector("#clearLog");
const stageEls = document.querySelectorAll("#stages .stage");

const metricLatency = document.querySelector("#metricLatency");
const metricRepairs = document.querySelector("#metricRepairs");
const metricIssues = document.querySelector("#metricIssues");
const metricStatus = document.querySelector("#metricStatus");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Fetch and display engine mode on load
async function fetchMode() {
  try {
    const res = await fetch("/health");
    const data = await res.json();
    const modeBadge = document.querySelector("#modeBadge");
    if (modeBadge) {
      modeBadge.textContent = data.mode;
      if (data.mode === "gemini") {
        modeBadge.style.borderColor = "rgba(34, 197, 94, 0.3)";
        modeBadge.style.color = "#22c55e";
      } else {
        modeBadge.style.borderColor = "var(--glass-border)";
        modeBadge.style.color = "var(--muted)";
      }
    }
  } catch (err) {
    console.error("Error fetching mode:", err);
  }
}

function updateStages(activeStageIndex) {
  stageEls.forEach((el, index) => {
    const stageNum = index + 1;
    if (stageNum < activeStageIndex) {
      el.className = "stage done";
    } else if (stageNum === activeStageIndex) {
      el.className = "stage active";
    } else {
      el.className = "stage";
    }
  });
}

function clearMetrics() {
  metricLatency.textContent = "—";
  metricRepairs.textContent = "—";
  metricIssues.textContent = "—";
  metricStatus.textContent = "—";
  metricStatus.className = "metric-value";
}

function appendLog(level, stage, message, details = null) {
  const entry = document.createElement("div");
  entry.className = `log-entry log-${level.toLowerCase()}`;

  const badge = document.createElement("span");
  badge.className = "log-badge";
  badge.textContent = stage.toUpperCase();
  entry.appendChild(badge);

  const container = document.createElement("div");
  container.className = "log-msg-container";

  const msg = document.createElement("span");
  msg.className = "log-msg";
  msg.textContent = message;
  container.appendChild(msg);

  if (details) {
    const detailsDiv = document.createElement("pre");
    detailsDiv.className = "log-details";
    detailsDiv.textContent = typeof details === "object" ? JSON.stringify(details, null, 2) : details;
    container.appendChild(detailsDiv);
  }

  entry.appendChild(container);
  logStreamEl.appendChild(entry);
  logStreamEl.scrollTop = logStreamEl.scrollHeight;
}

function getStageIndex(stageName) {
  const name = stageName.toLowerCase();
  if (name.includes("intent")) return 1;
  if (name.includes("design")) return 2;
  if (name.includes("schema")) return 3;
  if (name.includes("validation")) return 4;
  if (name.includes("repair")) return 4;
  if (name.includes("runtime")) return 5;
  return 5;
}

// Clear log button
clearLogBtn.addEventListener("click", () => {
  logStreamEl.innerHTML = "";
});

// Generate button click
generateBtn.addEventListener("click", async () => {
  const promptValue = promptEl.value.trim();
  if (!promptValue) return;

  generateBtn.disabled = true;
  evaluateBtn.disabled = true;
  generateBtn.innerHTML = `<span class="spinner"></span> Compiling...`;

  // Reset panels & metrics
  validationPanel.style.display = "none";
  validationEl.innerHTML = "";
  assumptionsPanel.style.display = "none";
  assumptionsEl.innerHTML = "";
  previewPanel.style.display = "none";
  previewLink.innerHTML = "";
  clearMetrics();
  
  // Clear and initialize log
  logStreamEl.innerHTML = "";
  appendLog("info", "sys", `Starting compilation pipeline for prompt: "${promptValue.substring(0, 60)}${promptValue.length > 60 ? '...' : ''}"`);
  updateStages(1);

  try {
    const response = await fetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: promptValue }),
    });

    if (!response.ok) {
      throw new Error(`Server returned status ${response.status}`);
    }

    const data = await response.json();
    const config = data.config;
    const logs = data.log || [];

    // Stream the logs to screen with micro-animation delays
    for (const entry of logs) {
      const idx = getStageIndex(entry.stage);
      updateStages(idx);
      appendLog(entry.level, entry.stage, entry.message, entry.details);
      await sleep(150); // micro-delay for cool visual streaming effect
    }

    updateStages(6); // Light up all stages as complete

    // Render Config JSON
    jsonEl.textContent = JSON.stringify(config, null, 2);

    // Update metrics
    if (config.metrics) {
      metricLatency.textContent = `${config.metrics.latency_ms} ms`;
      metricRepairs.textContent = config.metrics.repair_passes;
      metricIssues.textContent = config.metrics.issue_count;
    }
    
    const executable = config.runtime?.executable;
    metricStatus.textContent = executable ? "PASS ✓" : "FAIL ✗";
    metricStatus.className = `metric-value ${executable ? "success" : "error"}`;

    // Render Validation Issues
    const issues = config.validation_report || [];
    if (issues.length > 0) {
      validationPanel.style.display = "block";
      issues.forEach((issue) => {
        const item = document.createElement("div");
        item.className = `issue-item ${issue.severity}`;
        
        const code = document.createElement("span");
        code.className = "issue-code";
        code.textContent = issue.code;
        item.appendChild(code);

        const msg = document.createElement("span");
        msg.className = "issue-msg";
        msg.textContent = `[${issue.layer.toUpperCase()}] ${issue.message}`;
        item.appendChild(msg);

        validationEl.appendChild(item);
      });
    }

    // Render Assumptions & Clarifications
    const assumptions = config.intent?.assumptions || [];
    const questions = config.intent?.clarification_questions || [];
    if (assumptions.length > 0 || questions.length > 0) {
      assumptionsPanel.style.display = "block";
      
      assumptions.forEach((assume) => {
        const item = document.createElement("div");
        item.className = "issue-item assumption";
        
        const badge = document.createElement("span");
        badge.className = "issue-code";
        badge.textContent = "ASSUME";
        item.appendChild(badge);

        const msg = document.createElement("span");
        msg.className = "issue-msg";
        msg.textContent = assume;
        item.appendChild(msg);

        assumptionsEl.appendChild(item);
      });

      questions.forEach((q) => {
        const item = document.createElement("div");
        item.className = "issue-item warning";
        
        const badge = document.createElement("span");
        badge.className = "issue-code";
        badge.textContent = "CLARIFY";
        item.appendChild(badge);

        const msg = document.createElement("span");
        msg.className = "issue-msg";
        msg.textContent = q;
        item.appendChild(msg);

        assumptionsEl.appendChild(item);
      });
    }

    // Render Runtime Preview
    if (executable && config.runtime?.generated_files?.length > 0) {
      previewPanel.style.display = "block";
      previewLink.innerHTML = `<a href="/apps/${config.app_id}/index.html" target="_blank">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style="margin-right: 4px;"><path d="M11.854 4.146a.5.5 0 0 1 .146.354v7a.5.5 0 0 1-.5.5h-7a.5.5 0 0 1-.354-.854L8.5 7.793 4.146 3.438a.5.5 0 1 1 .708-.708L9.207 7.08l2.647-2.934a.5.5 0 0 1 .708 0z"/></svg>
        Open Generated App Runtime Preview
      </a>`;
    }

    appendLog("info", "sys", "Compilation completed successfully.");

  } catch (err) {
    console.error("Compilation failed:", err);
    appendLog("error", "sys", `Compilation failed: ${err.message}`);
    metricStatus.textContent = "ERROR";
    metricStatus.className = "metric-value error";
  } finally {
    generateBtn.disabled = false;
    evaluateBtn.disabled = false;
    generateBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 3l6 5-6 5"/></svg>
      Generate
    `;
  }
});

// Evaluate button click
evaluateBtn.addEventListener("click", async () => {
  evaluateBtn.disabled = true;
  generateBtn.disabled = true;
  evaluateBtn.textContent = "Evaluating (20 prompts)...";

  // Reset metrics & panels
  clearMetrics();
  validationPanel.style.display = "none";
  assumptionsPanel.style.display = "none";
  previewPanel.style.display = "none";

  logStreamEl.innerHTML = "";
  appendLog("info", "sys", "Starting evaluation of all 20 base prompts. This will run each prompt through the compiler. Please wait...");
  updateStages(1);

  try {
    const res = await fetch("/evaluate", { method: "POST" });
    if (!res.ok) {
      throw new Error(`Evaluation failed with status ${res.status}`);
    }

    const data = await res.json();
    updateStages(6);

    // Show evaluation results in the JSON block
    jsonEl.textContent = JSON.stringify(data, null, 2);

    // Update metrics cards with averages
    metricLatency.textContent = `${data.average_latency_ms} ms (avg)`;
    metricRepairs.textContent = `${data.average_repair_passes} (avg)`;
    metricIssues.textContent = `V: ${data.failure_types.validation_error} | R: ${data.failure_types.runtime_failure}`;
    
    const rate = data.success_rate * 100;
    metricStatus.textContent = `${rate.toFixed(0)}%`;
    if (rate >= 90) {
      metricStatus.className = "metric-value success";
    } else if (rate >= 70) {
      metricStatus.className = "metric-value warning";
    } else {
      metricStatus.className = "metric-value error";
    }

    appendLog("info", "sys", `Evaluation finished. Total prompts: ${data.total}, Success: ${data.success_count}, Rate: ${rate.toFixed(1)}%`);

  } catch (err) {
    console.error("Evaluation failed:", err);
    appendLog("error", "sys", `Evaluation failed: ${err.message}`);
    metricStatus.textContent = "ERROR";
    metricStatus.className = "metric-value error";
  } finally {
    evaluateBtn.disabled = false;
    generateBtn.disabled = false;
    evaluateBtn.textContent = "Run Full Eval (20 prompts)";
  }
});

// Initialize on page load
fetchMode();
