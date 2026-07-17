const stateUrl = "/api/demo/state";
const targetAgentUrl = "/api/demo/target-agent";
const gatewayStatusUrl = "/api/demo/gateway-status";

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

async function fetchTargetAgent() {
  const res = await fetch(targetAgentUrl, { cache: "no-store" });
  return res.json();
}

async function fetchGatewayStatus() {
  const res = await fetch(gatewayStatusUrl, { cache: "no-store" });
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
    ? `
      <div class="meta">Enforcement: ${escapeHtml(trace.enforcement_layer || "recorded policy contract")}</div>
      <pre>${escapeHtml(JSON.stringify(trace, null, 2))}</pre>
    `
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

function renderTargetAgent(data) {
  $("target-agent-subtitle").textContent =
    `${data.evo} · ${data.active_defender} · ${data.summary}`;
  const workspace = data.customer_workspace || {};
  $("target-agent-view").innerHTML = [
    renderTargetSummary(data),
    renderToolSurface(data.tools || []),
    renderDataClasses(data.data_classes || []),
    renderCustomers(workspace.customers || []),
    renderOrders(workspace.orders || []),
    renderPayments(workspace.payments || []),
    renderTickets(workspace.tickets || []),
    renderKnowledge(workspace.knowledge || {}, workspace.protected_internal_values || {}),
    renderInvariants(data.active_invariants || []),
    renderWorkflows(data.benign_workflows || []),
  ].join("");
}

function renderTargetSummary(data) {
  const counts = [
    ["Tools", (data.tools || []).length],
    ["Roles", (data.roles || []).length],
    ["Data classes", (data.data_classes || []).length],
    ["Invariants", (data.active_invariants || []).length],
    ["Benign workflows", (data.benign_workflows || []).length],
  ];
  return `
    <section class="target-section wide">
      <div class="target-section-head">
        <h3>Current Subject Snapshot</h3>
        <span>${escapeHtml(data.evo)} protected by ${escapeHtml(data.active_defender)}</span>
      </div>
      <div class="target-fields">
        ${counts.map(([label, value]) => `
          <div class="field">
            <span class="field-label">${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
          </div>
        `).join("")}
      </div>
    </section>
  `;
}

function renderToolSurface(tools) {
  return `
    <section class="target-section">
      <div class="target-section-head">
        <h3>Tool Surface</h3>
        <span>${tools.length} tools</span>
      </div>
      <div class="target-list">
        ${tools.map((tool) => `
          <article class="target-row">
            <div class="target-row-title">
              <span>${escapeHtml(tool.name)}</span>
              <span class="risk-${escapeHtml(tool.risk)}">${escapeHtml(tool.risk)}</span>
            </div>
            <div class="meta">
              ${escapeHtml(tool.generation)} · sink ${escapeHtml(tool.sink || "none")}
            </div>
            <div class="tag-row">
              ${(tool.reads || []).map((d) => `
                <span class="tag">reads ${escapeHtml(d.name)}:${escapeHtml(d.sensitivity)}</span>
              `).join("")}
              ${(tool.produces || []).map((d) => `
                <span class="tag">produces ${escapeHtml(d.name)}:${escapeHtml(d.sensitivity)}</span>
              `).join("")}
            </div>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderDataClasses(rows) {
  return `
    <section class="target-section">
      <div class="target-section-head">
        <h3>Visible Data Classes</h3>
        <span>${rows.length} classes</span>
      </div>
      <div class="target-list">
        ${rows.map((row) => `
          <article class="target-row">
            <div class="target-row-title">
              <span>${escapeHtml(row.name)}</span>
              <span>${escapeHtml(row.sensitivity)}</span>
            </div>
            <div class="meta">
              ${escapeHtml(row.generation)} · tenant scoped ${escapeHtml(row.tenant_scoped)}
            </div>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderCustomers(customers) {
  return renderRecordSection("Customer Records", customers, ["customer_id", "name", "email",
    "phone", "shipping_address", "segment", "risk_score", "account_status", "internal_note"]);
}

function renderOrders(orders) {
  return renderRecordSection("Orders", orders, ["order_id", "customer_id", "customer",
    "amount", "status", "sku", "shipping_address", "note"]);
}

function renderPayments(payments) {
  return renderRecordSection("Payment Profiles", payments, ["customer_id", "last4",
    "billing_zip", "chargeback_count", "lifetime_value"]);
}

function renderTickets(tickets) {
  return renderRecordSection("Support Tickets", tickets, ["ticket_id", "customer_id",
    "subject", "body", "private_note"]);
}

function renderRecordSection(title, rows, keys) {
  return `
    <section class="target-section">
      <div class="target-section-head">
        <h3>${escapeHtml(title)}</h3>
        <span>${rows.length} rows</span>
      </div>
      <div class="target-list">
        ${rows.map((row) => `
          <article class="target-row">
            <div class="target-row-title">
              <span>${escapeHtml(row[keys[0]] || title)}</span>
              <span>${escapeHtml(row[keys[1]] || "")}</span>
            </div>
            <div class="tag-row">
              ${keys.slice(2).map((key) => `
                <span class="tag">${escapeHtml(key)}=${escapeHtml(row[key])}</span>
              `).join("")}
            </div>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderKnowledge(knowledge, protectedValues) {
  const kb = Object.entries(knowledge.kb_articles || {});
  const runbooks = Object.entries(knowledge.runbooks || {});
  const protectedRows = Object.entries(protectedValues || {});
  return `
    <section class="target-section">
      <div class="target-section-head">
        <h3>Knowledge And Internal Values</h3>
        <span>${kb.length + runbooks.length + protectedRows.length} entries</span>
      </div>
      <div class="target-list">
        ${kb.map(([key, value]) => renderKeyValue("kb", key, value)).join("")}
        ${runbooks.map(([key, value]) => renderKeyValue("runbook", key, value)).join("")}
        ${protectedRows.map(([key, value]) => renderKeyValue("protected", key, value)).join("")}
      </div>
    </section>
  `;
}

function renderKeyValue(type, key, value) {
  return `
    <article class="target-row">
      <div class="target-row-title">
        <span>${escapeHtml(key)}</span>
        <span>${escapeHtml(type)}</span>
      </div>
      <div class="meta">${escapeHtml(value)}</div>
    </article>
  `;
}

function renderInvariants(rows) {
  return `
    <section class="target-section">
      <div class="target-section-head">
        <h3>Active Security Invariants</h3>
        <span>${rows.length} invariants</span>
      </div>
      <div class="target-list">
        ${rows.map((row) => `
          <article class="target-row">
            <div class="target-row-title">
              <span>${escapeHtml(row.id)}</span>
              <span>${escapeHtml(row.generation)}</span>
            </div>
            <div class="meta">
              sink ${escapeHtml(row.sink || "none")} · params ${escapeHtml(JSON.stringify(row.params))}
            </div>
            <div class="tag-row">
              ${(row.restricted_data_classes || []).map((name) => `
                <span class="tag">${escapeHtml(name)}</span>
              `).join("")}
            </div>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderWorkflows(rows) {
  return `
    <section class="target-section">
      <div class="target-section-head">
        <h3>Benign Workflows</h3>
        <span>${rows.length} workflows</span>
      </div>
      <div class="target-list">
        ${rows.map((row) => `
          <article class="target-row">
            <div class="target-row-title">
              <span>${escapeHtml(row.workflow_id)}</span>
              <span>${escapeHtml(row.actor_role)}</span>
            </div>
            <div class="meta">${escapeHtml(row.user_goal)}</div>
            <div class="tag-row">
              ${(row.required_tools || []).map((tool) => `
                <span class="tag">${escapeHtml(tool)}</span>
              `).join("")}
            </div>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function openTargetModal() {
  $("target-modal").hidden = false;
}

function closeTargetModal() {
  $("target-modal").hidden = true;
}

async function refresh() {
  const [state, gateway] = await Promise.all([fetchState(), fetchGatewayStatus()]);
  render(state);
  $("gateway-mode").textContent = gateway.label || gateway.mode;
  $("gateway-mode").title = gateway.pomerium_url
    ? `${gateway.pomerium_url} · ${gateway.identity}`
    : gateway.identity;
}

$("start-btn").addEventListener("click", async () => {
  $("start-btn").disabled = true;
  await postJson("/api/demo/start", { pace_seconds: 0.04 });
  await refresh();
  setTimeout(() => { $("start-btn").disabled = false; }, 1200);
});

$("reset-btn").addEventListener("click", async () => {
  await postJson("/api/demo/reset");
  await refresh();
});

$("target-agent-btn").addEventListener("click", async () => {
  $("target-agent-btn").disabled = true;
  renderTargetAgent(await fetchTargetAgent());
  openTargetModal();
  $("target-agent-btn").disabled = false;
});

$("target-close-btn").addEventListener("click", closeTargetModal);

$("target-modal").addEventListener("click", (event) => {
  if (event.target === $("target-modal")) closeTargetModal();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeTargetModal();
});

refresh();
setInterval(refresh, 700);
