const stateUrl = "/api/demo/state";

const $ = (id) => document.getElementById(id);

async function postJson(url, body = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function fetchState() {
  const res = await fetch(stateUrl, { cache: "no-store" });
  return res.json();
}

function pct(value) {
  if (value === undefined || value === null) return "0%";
  return `${Math.round(Number(value) * 100)}%`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function render(state) {
  const run = state.run || {};
  $("current-evo").textContent = run.current_evo || "evo0";
  $("active-defender").textContent = run.active_defender || "def-v0";
  $("phase").textContent = run.current_phase || "idle";
  $("run-status").textContent = run.status || "idle";
  $("run-subtitle").textContent = run.run_id ? `run ${run.run_id}` : "persistent co-evolution loop";

  renderAttempts(state.attempts || []);
  renderTrace(state.traces || []);
  renderBundles(state.attack_bundles || [], state.defender_bundles || []);
  renderMetrics(state.latest_metrics || null);
  renderHistory(state.generation_history || []);
  renderEvents(state.events || []);
}

function renderAttempts(attempts) {
  $("attempt-count").textContent = `${attempts.length} attempts`;
  $("attempts").innerHTML = attempts.slice().reverse().map((a) => {
    const status = a.success ? "success" : "blocked";
    const label = a.success ? "succeeded" : "blocked";
    return `
      <article class="item">
        <div class="item-title">
          <span>${escapeHtml(a.family)}</span>
          <span class="${status}">${label}</span>
        </div>
        <div class="meta">${escapeHtml(a.attempt_id)} · ${escapeHtml(a.defender_version)} · ${escapeHtml(a.violated_invariant || "no violation")}</div>
        <div class="meta">${escapeHtml(a.objective)}</div>
        <div class="path">${escapeHtml(a.target_path)}</div>
      </article>
    `;
  }).join("");
}

function renderTrace(traces) {
  const trace = traces.at(-1);
  $("trace-label").textContent = trace ? trace.trace_id : "latest";
  $("trace").innerHTML = trace
    ? `<pre>${escapeHtml(JSON.stringify(trace, null, 2))}</pre>`
    : `<pre>Press Start Demo.</pre>`;
}

function renderBundles(attacker, defender) {
  $("attacker-bundle-count").textContent = String(attacker.length);
  $("defender-bundle-count").textContent = String(defender.length);
  $("attacker-bundles").innerHTML = attacker.map((b) => `
    <article class="bundle">
      <div class="bundle-title">
        <span>${escapeHtml(b.family)}</span>
        <span>${escapeHtml(b.evo)}</span>
      </div>
      <div class="meta">${escapeHtml(b.objective)}</div>
      <div class="path">${escapeHtml((b.source_to_sink_path || []).join(" -> "))}</div>
    </article>
  `).join("");
  $("defender-bundles").innerHTML = defender.map((b) => {
    const decisionClass = b.promotion_decision === "promoted"
      ? "promoted"
      : (b.promotion_decision === "rejected" ? "rejected" : "");
    return `
      <article class="bundle">
        <div class="bundle-title">
          <span>${escapeHtml(b.control_layer)}</span>
          <span class="${decisionClass}">${escapeHtml(b.promotion_decision)}</span>
        </div>
        <div class="meta">${escapeHtml(b.defender_version)} · ${escapeHtml(b.policy_diff_summary)}</div>
      </article>
    `;
  }).join("");
}

function renderMetrics(m) {
  $("metric-defender").textContent = m ? m.defender_version : "no data";
  if (!m) {
    $("metrics").innerHTML = "";
    return;
  }
  const metrics = [
    ["Attack success", pct(m.attack_success_rate)],
    ["Benign success", pct(m.benign_success_rate)],
    ["Holdout success", pct(m.hidden_holdout_attack_success)],
    ["Blocked attacks", m.blocked_attack_count],
    ["Attacker bundles", m.attacker_bundle_size],
    ["Defender bundles", m.defender_bundle_size],
  ];
  $("metrics").innerHTML = metrics.map(([label, value]) => `
    <div class="metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `).join("");
}

function renderHistory(rows) {
  $("history-count").textContent = `${rows.length} rows`;
  $("history").innerHTML = rows.map((r) => {
    const decisionClass = r.promotion_decision === "promoted"
      ? "promoted"
      : (r.promotion_decision === "rejected" ? "rejected" : "success");
    return `
      <tr>
        <td>${escapeHtml(r.evo)}</td>
        <td>${escapeHtml(r.defender_version)}</td>
        <td>${escapeHtml(r.attack_family)}</td>
        <td>${pct(r.frontier_attack_success)}</td>
        <td>${pct(r.benign_success)}</td>
        <td>${escapeHtml(r.policy_diff_summary)}</td>
        <td class="${decisionClass}">${escapeHtml(r.promotion_decision)}</td>
      </tr>
    `;
  }).join("");
}

function renderEvents(events) {
  $("event-count").textContent = `${events.length} events`;
  $("events").innerHTML = events.slice().reverse().map((e) => `
    <article class="event">
      <div class="event-title">
        <span>${escapeHtml(e.type)}</span>
        <span>${escapeHtml(e.evo)} · ${escapeHtml(e.defender_version)}</span>
      </div>
      <div class="event-summary">${escapeHtml(e.summary)}</div>
    </article>
  `).join("");
}

async function refresh() {
  render(await fetchState());
}

$("start-btn").addEventListener("click", async () => {
  $("start-btn").disabled = true;
  await postJson("/api/demo/start", { pace_seconds: 0.35 });
  await refresh();
  setTimeout(() => { $("start-btn").disabled = false; }, 1200);
});

$("reset-btn").addEventListener("click", async () => {
  await postJson("/api/demo/reset");
  await refresh();
});

refresh();
setInterval(refresh, 700);
