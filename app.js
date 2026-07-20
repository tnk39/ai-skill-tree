const svg = document.querySelector("#graph");
const cards = document.querySelector("#cards");
const details = document.querySelector("#details");
const summary = document.querySelector("#summary");
const empty = document.querySelector("#graphEmpty");
const svgNamespace = "http://www.w3.org/2000/svg";

const state = { data: null, nodes: [], relationships: [], selectedId: null, scale: 1, x: 0, y: 0, drag: null };
const labels = { agent: "Agent", goal: "Goal", skill: "Skill", task: "Task", artifact: "Artifact" };
const colors = { agent: "#f28bd1", goal: "#85b8ff", skill: "#66d9a3", task: "#ffd166", artifact: "#f58c68" };

function element(name, attributes = {}) {
  const node = document.createElementNS(svgNamespace, name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
  return node;
}

function htmlElement(name, text, className) {
  const node = document.createElement(name);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function graphNodes(data) {
  const groups = [
    ["agents", "agent", "name"],
    ["goals", "goal", "title"],
    ["skills", "skill", "name"],
    ["tasks", "task", "title"],
    ["artifacts", "artifact", "title"]
  ];
  return groups.flatMap(([collection, kind, titleKey]) => (data[collection] || []).map((record) => ({
    ...record,
    kind,
    title: record[titleKey] || labels[kind]
  })));
}

function countSummary(data) {
  const values = [["Agents", data.agents], ["Goals", data.goals], ["Skills", data.skills], ["Tasks", data.tasks], ["Artifacts", data.artifacts]];
  cards.replaceChildren(...values.map(([name, records]) => {
    const card = htmlElement("article", undefined, "card");
    card.append(htmlElement("b", String((records || []).length)), htmlElement("span", name));
    return card;
  }));
}

function nodePositions(nodes, width, height) {
  const positions = new Map();
  const grouped = nodes.reduce((result, node) => {
    (result[node.kind] ||= []).push(node);
    return result;
  }, {});
  const center = { x: width * 0.5, y: height * 0.5 };
  const rings = { agent: 0, goal: Math.min(width, height) * 0.2, skill: Math.min(width, height) * 0.34, task: Math.min(width, height) * 0.45, artifact: Math.min(width, height) * 0.48 };
  const offsets = { agent: -Math.PI / 2, goal: -Math.PI / 2, skill: -0.25, task: 0.65, artifact: 1.25 };

  Object.entries(grouped).forEach(([kind, records]) => {
    records.forEach((record, index) => {
      const radius = rings[kind];
      const angle = offsets[kind] + (Math.PI * 2 * index) / Math.max(records.length, 1);
      positions.set(record.id, radius ? { x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius } : center);
    });
  });
  return positions;
}

function nodeRadius(node, relationCount) {
  if (node.kind === "goal") return 25;
  if (node.kind === "agent") return 23;
  return Math.min(25, 15 + relationCount * 2 + (node.usage_count || 0));
}

function relationStyle(kind) {
  if (kind === "depends_on") return "edge edge-dependency";
  if (["produces", "demonstrates"].includes(kind)) return "edge edge-artifact";
  if (["requires", "advances", "contributes_to"].includes(kind)) return "edge edge-goal";
  if (kind === "uses") return "edge edge-uses";
  return "edge";
}

function renderDetails() {
  details.replaceChildren();
  const selected = state.nodes.find((node) => node.id === state.selectedId);
  if (!selected) {
    details.append(htmlElement("p", "ノードを選択すると、安全な公開情報を表示します。", "muted"));
    return;
  }
  const related = state.relationships.filter((relationship) => relationship.from === selected.id || relationship.to === selected.id).length;
  details.append(htmlElement("h2", selected.title), htmlElement("span", labels[selected.kind], `kind-badge ${selected.kind}`));
  const list = htmlElement("dl", undefined, "detail-list");
  const entries = [["状態", selected.status || "unknown"], ["関連", `${related} 件`]];
  if (selected.category) entries.push(["分野", selected.category]);
  if (typeof selected.confidence === "number") entries.push(["信頼度", `${Math.round(selected.confidence * 100)}%`]);
  if (typeof selected.usage_count === "number") entries.push(["利用回数", `${selected.usage_count}`]);
  entries.forEach(([name, value]) => list.append(htmlElement("dt", name), htmlElement("dd", value)));
  details.append(list);
}

function drawNode(layer, node, position, relationCount) {
  const group = element("g", { class: `node node-${node.kind}${node.id === state.selectedId ? " selected" : ""}`, transform: `translate(${position.x} ${position.y})`, tabindex: "0", role: "button", "aria-label": `${labels[node.kind]} ${node.title}` });
  const radius = nodeRadius(node, relationCount);
  let shape;
  if (node.kind === "goal") shape = element("polygon", { points: `0,-${radius} ${radius},0 0,${radius} -${radius},0` });
  else if (node.kind === "task") shape = element("rect", { x: -radius, y: -radius * 0.7, width: radius * 2, height: radius * 1.4, rx: 7 });
  else if (node.kind === "artifact") shape = element("polygon", { points: `0,-${radius} ${radius * 0.86},-${radius * 0.5} ${radius * 0.86},${radius * 0.5} 0,${radius} -${radius * 0.86},${radius * 0.5} -${radius * 0.86},-${radius * 0.5}` });
  else shape = element("circle", { r: radius });
  shape.setAttribute("fill", colors[node.kind]);
  group.append(shape);
  const title = element("text", { y: radius + 18, "text-anchor": "middle" });
  title.textContent = node.title;
  group.append(title);
  const select = () => { state.selectedId = node.id; render(); };
  group.addEventListener("click", (event) => { event.stopPropagation(); select(); });
  group.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } });
  layer.append(group);
}

function renderView() {
  const viewport = svg.querySelector(".graph-world");
  if (viewport) viewport.setAttribute("transform", `translate(${state.x} ${state.y}) scale(${state.scale})`);
}

function render() {
  const width = Math.max(svg.clientWidth || 0, 720);
  const height = Math.max(svg.clientHeight || 0, 520);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.replaceChildren();
  if (!state.nodes.length) { empty.hidden = false; renderDetails(); return; }
  empty.hidden = true;
  const world = element("g", { class: "graph-world" });
  const positions = nodePositions(state.nodes, width, height);
  const relatedCounts = new Map(state.nodes.map((node) => [node.id, 0]));
  state.relationships.forEach((relationship) => {
    if (relatedCounts.has(relationship.from)) relatedCounts.set(relationship.from, relatedCounts.get(relationship.from) + 1);
    if (relatedCounts.has(relationship.to)) relatedCounts.set(relationship.to, relatedCounts.get(relationship.to) + 1);
    const source = positions.get(relationship.from);
    const target = positions.get(relationship.to);
    if (!source || !target) return;
    world.append(element("line", { class: relationStyle(relationship.kind), x1: source.x, y1: source.y, x2: target.x, y2: target.y }));
  });
  state.nodes.forEach((node) => drawNode(world, node, positions.get(node.id), relatedCounts.get(node.id) || 0));
  svg.append(world);
  renderView();
  renderDetails();
}

function adjustZoom(amount) {
  state.scale = Math.min(2.6, Math.max(0.55, state.scale + amount));
  renderView();
}

function resetView() { state.scale = 1; state.x = 0; state.y = 0; renderView(); }

document.querySelectorAll("[data-action]").forEach((button) => button.addEventListener("click", () => {
  if (button.dataset.action === "zoom-in") adjustZoom(0.18);
  if (button.dataset.action === "zoom-out") adjustZoom(-0.18);
  if (button.dataset.action === "reset-view") resetView();
}));

svg.addEventListener("wheel", (event) => { event.preventDefault(); adjustZoom(event.deltaY < 0 ? 0.12 : -0.12); }, { passive: false });
svg.addEventListener("pointerdown", (event) => {
  if (event.target.closest(".node")) return;
  state.drag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, originX: state.x, originY: state.y };
  svg.setPointerCapture(event.pointerId);
});
svg.addEventListener("pointermove", (event) => {
  if (!state.drag || state.drag.pointerId !== event.pointerId) return;
  state.x = state.drag.originX + event.clientX - state.drag.x;
  state.y = state.drag.originY + event.clientY - state.drag.y;
  renderView();
});
svg.addEventListener("pointerup", () => { state.drag = null; });
window.addEventListener("resize", render);

fetch("public-snapshot.json")
  .then((response) => { if (!response.ok) throw new Error("snapshot request failed"); return response.json(); })
  .then((data) => {
    state.data = data;
    state.nodes = graphNodes(data);
    state.relationships = data.relationships || [];
    countSummary(data);
    summary.textContent = "監査可能な作業記録から生成した、機密情報を含まない読み取り専用の関係グラフです。";
    render();
  })
  .catch(() => { summary.textContent = "公開スナップショットを読み込めませんでした。"; });
