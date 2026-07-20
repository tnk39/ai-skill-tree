const svg = document.querySelector('#graph');
let active = 'all';
let selected = null;
let graphData = { agents: [], goals: [], skills: [], tasks: [], artifacts: [], relations: [], events: [] };

const color = { skill: '#66d9a3', task: '#ffd166', goal: '#85b8ff', agent: '#ed8cff', artifact: '#f58c68' };
const relationNames = { owns: '所有', requires: '必要', depends_on: '依存', advances: '前進', uses: '使用', produces: '生成', demonstrates: '実証', contributes_to: '貢献' };

function nodeData(data) {
  return [
    ...(data.agents || []).map((item) => ({ ...item, kind: 'agent' })),
    ...(data.goals || []).map((item) => ({ ...item, kind: 'goal' })),
    ...(data.skills || []).map((item) => ({ ...item, kind: 'skill' })),
    ...(data.tasks || []).map((item) => ({ ...item, kind: 'task' })),
    ...(data.artifacts || []).map((item) => ({ ...item, kind: 'artifact' })),
  ];
}

function edgeClass(kind) {
  if (kind === 'depends_on') return 'edge dependency';
  if (['requires', 'advances', 'contributes_to'].includes(kind)) return 'edge goal-edge';
  if (['produces', 'demonstrates'].includes(kind)) return 'edge artifact-edge';
  return 'edge';
}

function draw() {
  const width = svg.clientWidth || 800;
  const height = svg.clientHeight || 500;
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.innerHTML = '';
  const nodes = nodeData(graphData).filter((node) => active === 'all' || node.kind === active);
  const ids = new Set(nodes.map((node) => node.id));
  const positions = {};
  nodes.forEach((node, index) => {
    const angle = (Math.PI * 2 * index / Math.max(nodes.length, 1)) - Math.PI / 2;
    const radius = Math.min(width, height) * 0.3;
    positions[node.id] = { x: width / 2 + Math.cos(angle) * radius, y: height / 2 + Math.sin(angle) * radius };
  });
  (graphData.relations || []).filter((edge) => ids.has(edge.from_entity_id) && ids.has(edge.to_entity_id)).forEach((edge) => {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('class', edgeClass(edge.kind));
    line.setAttribute('x1', positions[edge.from_entity_id].x);
    line.setAttribute('y1', positions[edge.from_entity_id].y);
    line.setAttribute('x2', positions[edge.to_entity_id].x);
    line.setAttribute('y2', positions[edge.to_entity_id].y);
    svg.append(line);
  });
  nodes.forEach((node) => {
    const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    group.setAttribute('class', `node ${selected?.id === node.id ? 'selected' : ''}`);
    group.setAttribute('transform', `translate(${positions[node.id].x} ${positions[node.id].y})`);
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('r', node.kind === 'goal' ? 22 : 16);
    circle.setAttribute('fill', color[node.kind]);
    group.append(circle);
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('y', 34);
    text.textContent = node.name || node.title;
    group.append(text);
    group.onclick = () => { selected = node; showDetail(); draw(); };
    svg.append(group);
  });
}

function showDetail() {
  const detail = document.querySelector('#detail');
  if (!selected) { detail.innerHTML = '<p class="muted">ノードを選択してください。</p>'; return; }
  const relations = (graphData.relations || []).filter((item) => item.from_entity_id === selected.id || item.to_entity_id === selected.id).map((item) => relationNames[item.kind]).join('、') || 'なし';
  detail.innerHTML = `<p class="eyebrow">${selected.kind.toUpperCase()}</p><h2 class="detail-title">${selected.name || selected.title}</h2><span class="badge">${selected.status || 'active'}</span><div class="kv"><b>ID</b><span>${selected.id}</span><b>説明</b><span>${selected.description || '—'}</span><b>関係</b><span>${relations}</span><b>信頼度</b><span>${selected.confidence ?? '—'}</span><b>使用回数</b><span>${selected.usage_count ?? '—'}</span></div>`;
}

async function load() {
  graphData = await fetch('/api/graph').then((response) => response.json());
  document.querySelector('#skill').innerHTML = '<option value="">関連スキル（任意）</option>' + graphData.skills.map((skill) => `<option value="${skill.id}">${skill.name}</option>`).join('');
  document.querySelector('#activity-list').innerHTML = graphData.events.slice(0, 10).map((event) => `<li>${event.event_type}<br><span class="muted">${event.timestamp}</span></li>`).join('') || '<li>まだイベントはありません。</li>';
  draw();
}

document.querySelectorAll('[data-filter]').forEach((button) => { button.onclick = () => { active = button.dataset.filter; document.querySelectorAll('[data-filter]').forEach((item) => item.classList.toggle('active', item === button)); draw(); }; });
document.querySelectorAll('[data-tab]').forEach((button) => { button.onclick = () => { document.querySelectorAll('[data-tab],.tab').forEach((item) => item.classList.remove('active')); button.classList.add('active'); document.querySelector(`#${button.dataset.tab}`).classList.add('active'); }; });
document.querySelector('#task-form').onsubmit = async (event) => { event.preventDefault(); const record = await fetch('/api/tasks', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ title: title.value, related_skill_id: skill.value || null }) }).then((response) => response.json()); document.querySelector('#form-result').textContent = `作成済み: ${record.entity_id}`; event.target.reset(); load(); };
window.onresize = draw;
load();
