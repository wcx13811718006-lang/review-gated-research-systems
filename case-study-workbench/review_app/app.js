const state = {
  items: [],
  filtered: [],
  selectedId: null,
  decisions: new Map(),
};

const routeFilter = document.querySelector("#routeFilter");
const decisionFilter = document.querySelector("#decisionFilter");
const queueList = document.querySelector("#queueList");
const totalCount = document.querySelector("#totalCount");
const blockedCount = document.querySelector("#blockedCount");
const pendingCount = document.querySelector("#pendingCount");

const detailRoute = document.querySelector("#detailRoute");
const detailTitle = document.querySelector("#detailTitle");
const claimText = document.querySelector("#claimText");
const claimId = document.querySelector("#claimId");
const claimClass = document.querySelector("#claimClass");
const locator = document.querySelector("#locator");
const reviewer = document.querySelector("#reviewer");
const sourceList = document.querySelector("#sourceList");
const noteBox = document.querySelector("#noteBox");
const decisionPreview = document.querySelector("#decisionPreview");

const routeLabels = {
  blocked_export: "Blocked export",
  mandatory_full_review: "Mandatory full review",
  targeted_review: "Targeted review",
  random_audit: "Random audit",
};

fetch("./sample_queue.json")
  .then((response) => response.json())
  .then((items) => {
    state.items = items;
    state.selectedId = items[0]?.id ?? null;
    applyFilters();
  });

routeFilter.addEventListener("change", applyFilters);
decisionFilter.addEventListener("change", applyFilters);

document.querySelector("#approveBtn").addEventListener("click", () => setDecision("approved"));
document.querySelector("#changeBtn").addEventListener("click", () => setDecision("changes_requested"));
document.querySelector("#parkBtn").addEventListener("click", () => setDecision("parked"));

function applyFilters() {
  const route = routeFilter.value;
  const decision = decisionFilter.value;
  state.filtered = state.items.filter((item) => {
    const effectiveDecision = state.decisions.get(item.id)?.decision ?? item.decision;
    return (route === "all" || item.route === route) && (decision === "all" || effectiveDecision === decision);
  });
  if (!state.filtered.some((item) => item.id === state.selectedId)) {
    state.selectedId = state.filtered[0]?.id ?? null;
  }
  renderQueue();
  renderDetail();
}

function renderQueue() {
  totalCount.textContent = String(state.items.length);
  blockedCount.textContent = String(state.items.filter((item) => item.route === "blocked_export").length);
  pendingCount.textContent = String(
    state.items.filter((item) => (state.decisions.get(item.id)?.decision ?? item.decision) === "pending").length,
  );

  queueList.innerHTML = "";
  for (const item of state.filtered) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "queue-item";
    button.setAttribute("role", "listitem");
    button.setAttribute("aria-current", item.id === state.selectedId ? "true" : "false");
    button.innerHTML = `
      <span class="queue-title">${escapeHtml(item.case_title)}</span>
      <span class="queue-meta">
        <span>${escapeHtml(routeLabels[item.route] ?? item.route)}</span>
        <span>${escapeHtml(item.claim_class)}</span>
      </span>
    `;
    button.addEventListener("click", () => {
      state.selectedId = item.id;
      renderQueue();
      renderDetail();
    });
    queueList.appendChild(button);
  }
}

function renderDetail() {
  const item = state.items.find((candidate) => candidate.id === state.selectedId);
  if (!item) {
    detailRoute.className = "pill";
    detailRoute.textContent = "No item selected";
    detailTitle.textContent = "Select a claim";
    claimText.textContent = "No claim selected.";
    claimId.textContent = "-";
    claimClass.textContent = "-";
    locator.textContent = "-";
    reviewer.textContent = "-";
    sourceList.innerHTML = "";
    noteBox.value = "";
    decisionPreview.textContent = "Decision history is local to this prototype.";
    return;
  }

  const localDecision = state.decisions.get(item.id);
  detailRoute.className = `pill ${item.route}`;
  detailRoute.textContent = routeLabels[item.route] ?? item.route;
  detailTitle.textContent = item.case_title;
  claimText.textContent = item.claim_text;
  claimId.textContent = item.claim_id;
  claimClass.textContent = item.claim_class;
  locator.textContent = item.locator ?? "-";
  reviewer.textContent = item.reviewer_role;
  noteBox.value = localDecision?.note ?? item.note;
  decisionPreview.textContent = `Current decision: ${localDecision?.decision ?? item.decision}`;
  sourceList.innerHTML = item.source_summaries.map(renderSource).join("");
}

function renderSource(source) {
  return `
    <div class="source-card">
      <strong>${escapeHtml(source.id)}</strong>
      <dl class="meta-grid">
        <div><dt>Owner</dt><dd>${escapeHtml(source.owner)}</dd></div>
        <div><dt>Authority</dt><dd>${escapeHtml(source.authority)}</dd></div>
        <div><dt>Status</dt><dd>${escapeHtml(source.fetch_status)}</dd></div>
        <div><dt>URL</dt><dd><a href="${escapeAttr(source.url)}">${escapeHtml(source.url)}</a></dd></div>
      </dl>
    </div>
  `;
}

function setDecision(decision) {
  if (!state.selectedId) return;
  state.decisions.set(state.selectedId, {
    decision,
    note: noteBox.value,
    updatedAt: new Date().toISOString(),
  });
  applyFilters();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}
