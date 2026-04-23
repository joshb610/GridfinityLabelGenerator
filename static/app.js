import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ─────────────────────────────────────────────────────────────────────────────
// Fragment definitions — categories and param forms
// ─────────────────────────────────────────────────────────────────────────────

const FRAG_CATEGORIES = [
  {
    id: 'hardware', label: 'Hardware',
    frags: [
      { name: 'bolt',           label: 'Bolt',             desc: 'Variable-length bolt' },
      { name: 'cullbolt',       label: 'Detailed Bolt',    desc: 'Bolt with thread profile' },
      { name: 'head',           label: 'Screw Head',       desc: 'Top-down screw head' },
      { name: 'hexhead',        label: 'Hex Head',         desc: 'Hex socket top-down' },
      { name: 'nut',            label: 'Hex Nut',          desc: 'Top-down hex nut' },
      { name: 'nut_profile',    label: 'Nut Profile',      desc: 'Side-profile nut' },
      { name: 'locknut',        label: 'Lock Nut',         desc: 'Side-profile lock nut' },
      { name: 'washer',         label: 'Washer',           desc: 'Flat washer' },
      { name: 'oring',          label: 'O-Ring',           desc: 'Thin circular seal' },
      { name: 'lockwasher',     label: 'Lock Washer',      desc: 'Split lock washer' },
      { name: 'ball_bearing',   label: 'Ball Bearing',     desc: 'Ball bearing symbol' },
      { name: 'threaded_insert',label: 'Thread Insert',    desc: 'Threaded brass insert' },
      { name: 'squarenut',      label: 'Square Nut',       desc: 'Top-down square nut' },
    ],
  },
  {
    id: 'electrical', label: 'Electrical',
    frags: [
      { name: 'symbol',            label: 'EE Symbol',         desc: 'Electronic schematic symbol' },
      { name: 'variable_resistor', label: 'Var. Resistor',     desc: 'Variable resistor symbol' },
    ],
  },
  {
    id: 'layout', label: 'Layout',
    frags: [
      { name: '...',     label: 'Spacer',          desc: 'Expands to fill space' },
      { name: '|',       label: 'Column Split',    desc: 'Split label into columns' },
      { name: 'measure', label: 'Dimension',       desc: 'Shows available width' },
    ],
  },
  {
    id: 'shapes', label: 'Shapes',
    frags: [
      { name: 'circle',  label: 'Circle',    desc: 'Filled circle' },
      { name: 'box',     label: 'Box',       desc: 'Rectangle of given size' },
      { name: 'magnet',  label: 'Magnet',    desc: 'Horseshoe magnet symbol' },
    ],
  },
];

// Fragments that need parameter forms before inserting
const FRAG_PARAMS = {
  bolt: {
    title: 'Bolt',
    fields: [
      { id: 'length', label: 'Length (mm)', type: 'number', default: '16', min: 1, step: 1 },
      { id: 'head',   label: 'Head Type',   type: 'select', options: ['pan','socket','countersunk','round'], default: 'pan' },
      { id: 'drive',  label: 'Drive',       type: 'select', options: ['(none)','hex','phillips','pozidrive','slot','torx','square','triangle','cross','phillipsslot'], default: '(none)' },
      { id: 'flip',      label: 'Flip direction',  type: 'checkbox', default: false },
      { id: 'tapping',   label: 'Self-tapping',    type: 'checkbox', default: false },
      { id: 'partial',   label: 'Partial thread',  type: 'checkbox', default: false },
      { id: 'flanged',   label: 'Flanged head',    type: 'checkbox', default: false },
      { id: 'slotted',   label: 'Slotted head',    type: 'checkbox', default: false },
    ],
    build(v) {
      const parts = [v.length];
      if (v.head !== 'pan') parts.push(v.head);
      if (v.drive !== '(none)') parts.push(v.drive);
      ['flip','tapping','partial','flanged','slotted'].forEach(m => { if (v[m]) parts.push(m); });
      return `{bolt(${parts.join(', ')})}`;
    },
  },
  cullbolt: {
    title: 'Detailed Bolt',
    fields: [
      { id: 'head',  label: 'Head Type', type: 'select', options: ['pan','socket','countersunk','round'], default: 'pan' },
      { id: 'drive', label: 'Drive',     type: 'select', options: ['(none)','hex','phillips','pozidrive','slot','torx','square','triangle'], default: 'hex' },
      { id: 'flip',    label: 'Flip direction', type: 'checkbox', default: false },
      { id: 'tapping', label: 'Self-tapping',   type: 'checkbox', default: false },
      { id: 'partial', label: 'Partial thread', type: 'checkbox', default: false },
    ],
    build(v) {
      const parts = [];
      if (v.head !== 'pan') parts.push(v.head);
      if (v.drive !== '(none)') parts.push(v.drive);
      ['flip','tapping','partial'].forEach(m => { if (v[m]) parts.push(m); });
      return parts.length ? `{cullbolt(${parts.join(', ')})}` : '{cullbolt}';
    },
  },
  head: {
    title: 'Screw Head',
    fields: [
      { id: 'drive', label: 'Drive', type: 'select', options: ['hex','phillips','pozidrive','slot','torx','square','triangle','cross','phillipsslot','security'], default: 'hex' },
    ],
    build: v => `{head(${v.drive})}`,
  },
  hexhead: {
    title: 'Hex Head',
    fields: [
      { id: 'drive', label: 'Drive (optional)', type: 'select', options: ['(none)','hex','phillips','pozidrive','slot','torx'], default: '(none)' },
    ],
    build: v => v.drive === '(none)' ? '{hexhead}' : `{hexhead(${v.drive})}`,
  },
  symbol: {
    title: 'Electronic Symbol',
    fields: [
      { id: 'name', label: 'Symbol name or category', type: 'text', default: 'resistor', placeholder: 'e.g. resistor, capacitor, LED' },
    ],
    build: v => `{symbol(${v.name})}`,
  },
  box: {
    title: 'Box',
    fields: [
      { id: 'width',  label: 'Width (mm)',            type: 'number', default: '10',  min: 0.5, step: 0.5 },
      { id: 'height', label: 'Height (mm, optional)', type: 'number', default: '',    min: 0.5, step: 0.5, placeholder: 'row height' },
    ],
    build: v => v.height ? `{box(${v.width}, ${v.height})}` : `{box(${v.width})}`,
  },
  '|': {
    title: 'Column Split',
    fields: [
      { id: 'left',  label: 'Left proportion',  type: 'number', default: '1', min: 0.1, step: 0.1 },
      { id: 'right', label: 'Right proportion', type: 'number', default: '1', min: 0.1, step: 0.1 },
    ],
    build: v => `{${v.left}|${v.right}}`,
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// App state
// ─────────────────────────────────────────────────────────────────────────────

let labels = [];
let activeId = null;
let nextId = 1;
let lastFocusedTextarea = null;   // track which textarea gets fragment insertions
let activeFragCategory = 'hardware';
let pendingFragName = null;       // fragment name being configured in param panel
let dragSrcId = null;             // label id being dragged for reorder
let previewedLabelId = null;      // id of the label currently shown in 3D preview
let previewedConfigJSON = null;   // serialised config at time of last preview

function newConfig() {
  return {
    id: nextId++,
    name: `Label ${labels.length + 1}`,
    nameIsAuto: true,
    base: 'pred', width: 1, width_unit: 'u', height: null, depth: 0.4, body_depth: null,
    divisions: 1, labels: [''],
    font: null, font_style: 'bold', font_size: null, font_size_maximum: null,
    margin: null, style: 'embossed', label_gap: 2.0, column_gap: 0.4,
    no_overheight: false, version: 'latest', multimaterial: 'none', output_format: 'step',
  };
}

function autoNameFromLabels(labelTexts) {
  const parts = labelTexts
    .map(t => t.replace(/\{[^}]*\}/g, '').trim())   // strip {fragments}
    .filter(Boolean)
    .map(t => t.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').replace(/[^a-zA-Z0-9_. ]/g, '').trim())
    .filter(Boolean);
  if (!parts.length) return null;
  return parts.join(' ').replace(/\s+/g, ' ').trim().substring(0, 50) || null;
}

function getFilenames(cfg) {
  const base = cfg.name.trim().replace(/\s+/g, '_');
  const fmt = cfg.output_format;
  if (cfg.multimaterial && cfg.multimaterial !== 'none') return [`${base}_body.${fmt}`, `${base}_text.${fmt}`];
  return [`${base}.${fmt}`];
}

// ─────────────────────────────────────────────────────────────────────────────
// Three.js preview
// ─────────────────────────────────────────────────────────────────────────────

let threeScene, threeCamera, threeRenderer, threeControls;
let labelGroup = null;  // Group holding all current label meshes

const MAT_BODY = new THREE.MeshPhongMaterial({ color: 0x5b8af0, specular: 0x2a3f7a, shininess: 60, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });
const MAT_TEXT = new THREE.MeshPhongMaterial({ color: 0xf0a05b, specular: 0x7a4a1a, shininess: 60, side: THREE.DoubleSide });

function initThree() {
  const canvas = document.getElementById('preview-canvas');
  const body   = document.getElementById('preview-body');

  threeRenderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  threeRenderer.setPixelRatio(window.devicePixelRatio);
  threeRenderer.setClearColor(0x111115, 1);

  threeScene  = new THREE.Scene();
  const { clientWidth: w, clientHeight: h } = body;
  threeCamera = new THREE.PerspectiveCamera(45, w / h, 0.01, 2000);
  threeCamera.position.set(60, 40, 60);

  threeControls = new OrbitControls(threeCamera, canvas);
  threeControls.enableDamping = true;
  threeControls.dampingFactor = 0.08;
  threeControls.mouseButtons = {
    LEFT:   THREE.MOUSE.ROTATE,
    MIDDLE: THREE.MOUSE.PAN,
    RIGHT:  THREE.MOUSE.PAN,
  };

  threeScene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const d1 = new THREE.DirectionalLight(0xffffff, 0.8);
  d1.position.set(80, 120, 60);
  threeScene.add(d1);
  const d2 = new THREE.DirectionalLight(0x8899ff, 0.3);
  d2.position.set(-60, -40, -40);
  threeScene.add(d2);
  threeScene.add(new THREE.GridHelper(200, 40, 0x222228, 0x222228));

  resizeRenderer();
  new ResizeObserver(resizeRenderer).observe(body);

  (function animate() {
    requestAnimationFrame(animate);
    threeControls.update();
    threeRenderer.render(threeScene, threeCamera);
  })();
}

function resizeRenderer() {
  const body = document.getElementById('preview-body');
  const w = body.clientWidth, h = body.clientHeight;
  if (!w || !h) return;
  threeRenderer.setSize(w, h);
  threeCamera.aspect = w / h;
  threeCamera.updateProjectionMatrix();
}

function clearLabelMeshes() {
  if (labelGroup) {
    threeScene.remove(labelGroup);
    labelGroup.traverse(obj => { if (obj.geometry) obj.geometry.dispose(); });
    labelGroup = null;
  }
}

function base64ToArrayBuffer(b64) {
  const bin = atob(b64);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  return buf.buffer;
}

function stlToMesh(arrayBuffer, mat) {
  const geo = new STLLoader().parse(arrayBuffer);
  geo.computeVertexNormals();
  return new THREE.Mesh(geo, mat);
}

function placeLabelGroup(group) {
  // Rotate so label lies flat on the grid (label is in XY plane, extrude in Z → rotate -90° around X)
  group.rotation.x = -Math.PI / 2;
  group.updateMatrixWorld(true);

  // Lift so bottom edge sits on Y=0
  const box = new THREE.Box3().setFromObject(group);
  group.position.y = -box.min.y;

  // Center on XZ plane
  const center = box.getCenter(new THREE.Vector3());
  group.position.x = -center.x;
  group.position.z = -center.z;

  threeScene.add(group);
  labelGroup = group;

  // Fit camera
  group.updateMatrixWorld(true);
  const box2 = new THREE.Box3().setFromObject(group);
  const center2 = box2.getCenter(new THREE.Vector3());
  const size = box2.getSize(new THREE.Vector3());
  // maxDim based on the label's face dimensions (x and z), not the thin depth (y)
  const faceDim = Math.max(size.x, size.z);
  const dist = faceDim * 1.8;
  threeCamera.position.set(dist * 0.6, dist, dist * 0.75);
  threeCamera.near = faceDim * 0.001;
  threeCamera.far  = faceDim * 200;
  threeCamera.updateProjectionMatrix();
  threeControls.target.copy(center2);
  threeControls.update();
}

function loadSTLIntoScene(arrayBuffer) {
  clearLabelMeshes();
  const group = new THREE.Group();
  group.add(stlToMesh(arrayBuffer, MAT_BODY));
  placeLabelGroup(group);
}

function loadMultiMaterialSTLs(bodyBuf, textBuf) {
  clearLabelMeshes();
  const group = new THREE.Group();
  group.add(stlToMesh(bodyBuf, MAT_BODY));
  group.add(stlToMesh(textBuf, MAT_TEXT));
  placeLabelGroup(group);
}

document.getElementById('reset-cam-btn').addEventListener('click', () => {
  if (!labelGroup) return;
  labelGroup.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(labelGroup);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const faceDim = Math.max(size.x, size.z);
  const dist = faceDim * 1.8;
  threeCamera.position.set(dist * 0.6, dist, dist * 0.75);
  threeControls.target.copy(center);
  threeControls.update();
});

// ─────────────────────────────────────────────────────────────────────────────
// Resize handle drag
// ─────────────────────────────────────────────────────────────────────────────

(function initResizeHandle() {
  const handle = document.getElementById('resize-handle');
  const layout = document.querySelector('.layout');
  let dragging = false;
  let startX = 0;
  let startRight = 0;

  handle.addEventListener('mousedown', e => {
    e.preventDefault();
    dragging = true;
    startX = e.clientX;
    const cols = getComputedStyle(layout).gridTemplateColumns.split(' ');
    // cols[3] is the right panel width
    startRight = parseFloat(cols[3]);
    handle.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  });

  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const delta = startX - e.clientX;  // dragging left = bigger right panel
    const newRight = Math.max(180, Math.min(700, startRight + delta));
    layout.style.gridTemplateColumns = `220px 1fr 4px ${newRight}px`;
    resizeRenderer();
  });

  document.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
})();

// ─────────────────────────────────────────────────────────────────────────────
// Preview keyboard / pan controls
// ─────────────────────────────────────────────────────────────────────────────

function panView(dx, dy) {
  const d = threeCamera.position.distanceTo(threeControls.target);
  const speed = d * 0.015;
  const right = new THREE.Vector3().setFromMatrixColumn(threeCamera.matrix, 0);
  const up    = new THREE.Vector3().setFromMatrixColumn(threeCamera.matrix, 1);
  const delta = new THREE.Vector3()
    .addScaledVector(right, -dx * speed)
    .addScaledVector(up,     dy * speed);
  threeCamera.position.add(delta);
  threeControls.target.add(delta);
  threeControls.update();
}

window.addEventListener('keydown', e => {
  // Ctrl/Cmd+S: save & preview current label
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault();
    const btn = document.getElementById('save-label-btn');
    if (btn && btn.offsetParent !== null) btn.click();
    return;
  }
  // Don't steal keys from form fields
  const tag = document.activeElement?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
  if (!labelGroup) return;
  switch (e.key) {
    case 'w': case 'W': case 'ArrowUp':    e.preventDefault(); panView( 0,  1); break;
    case 's': case 'S': case 'ArrowDown':  e.preventDefault(); panView( 0, -1); break;
    case 'a': case 'A': case 'ArrowLeft':  e.preventDefault(); panView(-1,  0); break;
    case 'd': case 'D': case 'ArrowRight': e.preventDefault(); panView( 1,  0); break;
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Toast
// ─────────────────────────────────────────────────────────────────────────────

let toastTimer;
function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `visible ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = ''; }, 3200);
}

// ─────────────────────────────────────────────────────────────────────────────
// Fragment Picker
// ─────────────────────────────────────────────────────────────────────────────

function buildFragPicker() {
  // Category tabs
  const tabs = document.getElementById('frag-tabs');
  tabs.innerHTML = '';
  FRAG_CATEGORIES.forEach(cat => {
    const btn = document.createElement('button');
    btn.className = 'frag-tab' + (cat.id === activeFragCategory ? ' active' : '');
    btn.textContent = cat.label;
    btn.addEventListener('click', () => {
      activeFragCategory = cat.id;
      closeParamPanel();
      buildFragPicker();
    });
    tabs.appendChild(btn);
  });

  // Fragment grid
  const grid = document.getElementById('frag-grid');
  grid.innerHTML = '';
  const cat = FRAG_CATEGORIES.find(c => c.id === activeFragCategory);
  if (!cat) return;
  cat.frags.forEach(frag => {
    const btn = document.createElement('button');
    btn.className = 'frag-btn' + (pendingFragName === frag.name ? ' selected' : '');
    btn.title = frag.desc;
    btn.innerHTML = `<span class="frag-btn-label">${escHtml(frag.label)}</span>`;
    btn.addEventListener('click', () => selectFrag(frag.name));
    grid.appendChild(btn);
  });
}

function selectFrag(name) {
  const paramDef = FRAG_PARAMS[name];
  if (!paramDef) {
    // No params — insert directly
    insertText(`{${name}}`);
    pendingFragName = null;
    closeParamPanel();
    buildFragPicker();
    return;
  }
  // Show param panel
  pendingFragName = name;
  buildFragPicker(); // re-render to highlight selected
  openParamPanel(name, paramDef);
}

function openParamPanel(name, def) {
  const panel = document.getElementById('frag-param-panel');
  document.getElementById('frag-param-title').textContent = def.title;

  const fields = document.getElementById('frag-param-fields');
  fields.innerHTML = '';

  def.fields.forEach(f => {
    const row = document.createElement('div');
    row.className = 'param-field';

    if (f.type === 'checkbox') {
      row.innerHTML = `<label class="param-check-label">
        <input type="checkbox" id="pp-${f.id}" ${f.default ? 'checked' : ''}>
        <span>${escHtml(f.label)}</span>
      </label>`;
    } else if (f.type === 'select') {
      const opts = f.options.map(o => `<option value="${escHtml(o)}" ${o === f.default ? 'selected' : ''}>${escHtml(o)}</option>`).join('');
      row.innerHTML = `<label>${escHtml(f.label)}<select id="pp-${f.id}">${opts}</select></label>`;
    } else {
      row.innerHTML = `<label>${escHtml(f.label)}
        <input type="${f.type}" id="pp-${f.id}" value="${escHtml(f.default || '')}"
          ${f.min !== undefined ? `min="${f.min}"` : ''}
          ${f.step !== undefined ? `step="${f.step}"` : ''}
          ${f.placeholder ? `placeholder="${escHtml(f.placeholder)}"` : ''}>
      </label>`;
    }
    fields.appendChild(row);
  });

  // Live preview
  const updatePreview = () => {
    document.getElementById('frag-param-preview').textContent = buildFragment(name, def);
  };
  fields.querySelectorAll('input,select').forEach(el => el.addEventListener('input', updatePreview));
  updatePreview();

  panel.style.display = '';
}

function buildFragment(name, def) {
  const vals = {};
  def.fields.forEach(f => {
    const el = document.getElementById(`pp-${f.id}`);
    if (!el) return;
    vals[f.id] = f.type === 'checkbox' ? el.checked : el.value;
  });
  return def.build(vals);
}

function closeParamPanel() {
  document.getElementById('frag-param-panel').style.display = 'none';
  pendingFragName = null;
}

document.getElementById('frag-param-cancel').addEventListener('click', () => {
  closeParamPanel();
  buildFragPicker();
});

document.getElementById('frag-param-insert').addEventListener('click', () => {
  if (!pendingFragName) return;
  const def = FRAG_PARAMS[pendingFragName];
  insertText(buildFragment(pendingFragName, def));
  closeParamPanel();
  buildFragPicker();
});

// Insert text at the last-focused textarea cursor position
function insertText(text) {
  const ta = lastFocusedTextarea;
  if (!ta) { toast('Click inside a label field first', 'error'); return; }
  const s = ta.selectionStart, e = ta.selectionEnd;
  ta.value = ta.value.slice(0, s) + text + ta.value.slice(e);
  ta.selectionStart = ta.selectionEnd = s + text.length;
  ta.focus();
  document.getElementById('frag-target-hint').textContent = '→ ' + (ta.dataset.hint || 'label field');
  updateAutoName();
}

// Track last focused textarea
document.addEventListener('focusin', e => {
  if (e.target.classList.contains('division-textarea')) {
    lastFocusedTextarea = e.target;
    document.getElementById('frag-target-hint').textContent = '→ ' + (e.target.dataset.hint || 'label field');
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Label list rendering
// ─────────────────────────────────────────────────────────────────────────────

function renderLabelList() {
  const list = document.getElementById('label-list');
  list.innerHTML = '';
  labels.forEach(cfg => {
    const div = document.createElement('div');
    div.className = 'label-item' + (cfg.id === activeId ? ' active' : '');
    div.dataset.id = cfg.id;
    div.setAttribute('draggable', 'true');
    const meta = `${cfg.width}${cfg.width_unit} · ${cfg.base} · div ${cfg.divisions}`;
    const filenames = getFilenames(cfg).map(escHtml).join(' · ');
    div.innerHTML = `
      <div class="drag-handle" title="Drag to reorder">⠿</div>
      <div class="item-info">
        <div class="item-name">${escHtml(cfg.name)}</div>
        <div class="item-meta">${escHtml(meta)}</div>
        <div class="item-filename">${filenames}</div>
      </div>
      <div class="item-actions">
        <button class="icon-btn" data-action="duplicate" title="Duplicate this label">⧉</button>
        <button class="icon-btn danger" data-action="delete" title="Delete this label">✕</button>
      </div>`;
    div.addEventListener('click', e => {
      const action = e.target.closest('[data-action]')?.dataset?.action;
      if (action === 'delete')    { deleteLabel(cfg.id); return; }
      if (action === 'duplicate') { duplicateLabel(cfg.id); return; }
      if (e.target.classList.contains('drag-handle')) return;
      selectLabel(cfg.id);
    });
    // Drag-to-reorder
    div.addEventListener('dragstart', e => {
      dragSrcId = cfg.id;
      div.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    div.addEventListener('dragend', () => {
      div.classList.remove('dragging');
      document.querySelectorAll('.label-item').forEach(d => d.classList.remove('drag-over'));
    });
    div.addEventListener('dragover', e => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      document.querySelectorAll('.label-item').forEach(d => d.classList.remove('drag-over'));
      if (dragSrcId !== cfg.id) div.classList.add('drag-over');
    });
    div.addEventListener('drop', e => {
      e.preventDefault();
      if (dragSrcId == null || dragSrcId === cfg.id) return;
      const srcIdx = labels.findIndex(l => l.id === dragSrcId);
      const dstIdx = labels.findIndex(l => l.id === cfg.id);
      if (srcIdx === -1 || dstIdx === -1) return;
      const [moved] = labels.splice(srcIdx, 1);
      labels.splice(dstIdx, 0, moved);
      dragSrcId = null;
      renderLabelList();
    });
    list.appendChild(div);
  });
  document.getElementById('label-count').textContent = labels.length;
  updateGenerateBar();
  saveToLocalStorage();
}

function updateGenerateBar() {
  const btn = document.getElementById('generate-btn');
  const summary = document.getElementById('generate-summary');
  if (labels.length === 0) {
    btn.disabled = true;
    summary.textContent = 'No labels in queue';
  } else {
    btn.disabled = false;
    const mm = labels.filter(l => l.multimaterial && l.multimaterial !== 'none').length;
    summary.textContent = `${labels.length} label${labels.length !== 1 ? 's' : ''} ready${mm ? ` (${mm} multi-material)` : ''}`;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Label CRUD
// ─────────────────────────────────────────────────────────────────────────────

function addLabel() {
  // Autosave current label before switching away
  if (activeId) readEditorIntoConfig();
  const cfg = newConfig();
  if (labels.length > 0) {
    const prev = labels[labels.length - 1];
    const inherit = ['base', 'style', 'font', 'font_style', 'font_size', 'font_size_maximum',
      'multimaterial', 'output_format', 'version', 'label_gap', 'column_gap',
      'no_overheight', 'margin', 'depth', 'body_depth'];
    for (const k of inherit) cfg[k] = prev[k];
  }
  labels.push(cfg);
  renderLabelList();
  selectLabel(cfg.id);
}

function deleteLabel(id) {
  labels = labels.filter(l => l.id !== id);
  if (activeId === id) {
    activeId = labels.length ? labels[labels.length - 1].id : null;
    activeId ? selectLabel(activeId) : clearEditor();
  }
  renderLabelList();
}

function duplicateLabel(id) {
  const src = labels.find(l => l.id === id);
  if (!src) return;
  const copy = JSON.parse(JSON.stringify(src));
  copy.id = nextId++;
  copy.name += '_copy';
  copy.nameIsAuto = false;  // user-named copy
  labels.push(copy);
  renderLabelList();
  selectLabel(copy.id);
}

function selectLabel(id) {
  // Autosave the currently open label before switching to a different one
  if (activeId && activeId !== id) readEditorIntoConfig();
  activeId = id;
  renderLabelList();
  loadLabelIntoEditor(id);
}

function clearEditor() {
  document.getElementById('empty-state').style.display = '';
  document.getElementById('editor-form').style.display = 'none';
  document.getElementById('editor-footer').style.display = 'none';
  document.getElementById('editing-label-name').textContent = '';
}

function loadLabelIntoEditor(id) {
  const cfg = labels.find(l => l.id === id);
  if (!cfg) { clearEditor(); return; }

  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('editor-form').style.display = 'flex';
  document.getElementById('editor-footer').style.display = '';
  document.getElementById('editing-label-name').textContent = cfg.name;

  document.getElementById('f-name').value           = cfg.name;
  document.getElementById('f-base').value           = cfg.base;
  document.getElementById('f-width').value          = cfg.width;
  document.getElementById('f-width-unit').value     = cfg.width_unit;
  document.getElementById('f-height').value         = cfg.height ?? '';
  document.getElementById('f-depth').value          = cfg.depth;
  document.getElementById('f-divisions').value      = cfg.divisions;
  document.getElementById('f-format').value         = cfg.output_format;
  document.getElementById('f-font-style').value     = cfg.font_style;
  document.getElementById('f-font').value           = cfg.font ?? '';
  document.getElementById('f-font-size').value      = cfg.font_size ?? '';
  document.getElementById('f-font-size-max').value  = cfg.font_size_maximum ?? '';
  document.getElementById('f-margin').value         = cfg.margin ?? '';
  document.getElementById('f-label-gap').value      = cfg.label_gap;
  document.getElementById('f-col-gap').value        = cfg.column_gap;
  document.getElementById('f-no-overheight').checked = cfg.no_overheight;
  document.getElementById('f-body-depth').value     = cfg.body_depth ?? '';
  updateMultimaterialOptions(cfg.base);
  document.getElementById('f-multimaterial').value = cfg.multimaterial || 'none';
  updateMmNote(cfg.multimaterial || 'none');
  document.querySelectorAll('input[name="style"]').forEach(r => { r.checked = r.value === cfg.style; });
  toggleVersionField(cfg.base);
  renderDivisionInputs(cfg.divisions, cfg.labels);
  updatePreviewStaleness();
}

// ─────────────────────────────────────────────────────────────────────────────
// localStorage persistence
// ─────────────────────────────────────────────────────────────────────────────

function saveToLocalStorage() {
  try { localStorage.setItem('gridfinity_session', JSON.stringify({ labels, nextId })); } catch (_) {}
}

function loadFromLocalStorage() {
  try {
    const data = JSON.parse(localStorage.getItem('gridfinity_session'));
    if (!Array.isArray(data?.labels) || !data.labels.length) return false;
    labels = data.labels;
    nextId = data.nextId ?? (Math.max(...labels.map(l => l.id)) + 1);
    return true;
  } catch (_) { return false; }
}

// ─────────────────────────────────────────────────────────────────────────────
// Stale preview indicator
// ─────────────────────────────────────────────────────────────────────────────

function updatePreviewStaleness() {
  const el = document.getElementById('preview-stale');
  if (!el || previewedLabelId === null) { if (el) el.style.display = 'none'; return; }
  if (activeId !== previewedLabelId) { el.style.display = ''; return; }
  const cfg = labels.find(l => l.id === activeId);
  el.style.display = (cfg && JSON.stringify(configToRequest(cfg)) !== previewedConfigJSON) ? '' : 'none';
}

// ─────────────────────────────────────────────────────────────────────────────
// Multimaterial options — split/background only available for pred base
// ─────────────────────────────────────────────────────────────────────────────

const PRED_ONLY_MM = [
  { value: 'split',           text: 'Split at face — base below / rim+text above' },
  { value: 'background',      text: 'Background — bg face slab, text fills body' },
  { value: 'background_full', text: 'Background (filled) — bg fills body, text is rim' },
];

function updateMultimaterialOptions(base) {
  const select = document.getElementById('f-multimaterial');
  const isPred = base === 'pred';
  // Remove pred-only options
  PRED_ONLY_MM.forEach(({ value }) => select.querySelector(`option[value="${value}"]`)?.remove());
  // Re-add if pred
  if (isPred) {
    PRED_ONLY_MM.forEach(({ value, text }) => {
      const opt = document.createElement('option');
      opt.value = value; opt.textContent = text;
      select.appendChild(opt);
    });
  }
  // If current value is no longer valid, reset
  if (!isPred && PRED_ONLY_MM.some(o => o.value === select.value)) {
    select.value = 'none';
    updateMmNote('none');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Editor load / save
// ─────────────────────────────────────────────────────────────────────────────

function readEditorIntoConfig() {
  const cfg = labels.find(l => l.id === activeId);
  if (!cfg) return null;

  cfg.name            = document.getElementById('f-name').value.trim() || cfg.name;
  cfg.base            = document.getElementById('f-base').value;
  cfg.width           = parseFloat(document.getElementById('f-width').value) || 1;
  cfg.width_unit      = document.getElementById('f-width-unit').value;
  cfg.height          = parseFloat(document.getElementById('f-height').value) || null;
  cfg.depth           = parseFloat(document.getElementById('f-depth').value) || 0.4;
  cfg.divisions       = parseInt(document.getElementById('f-divisions').value) || 1;
  cfg.output_format   = document.getElementById('f-format').value;
  cfg.font_style      = document.getElementById('f-font-style').value;
  cfg.font            = document.getElementById('f-font').value.trim() || null;
  cfg.font_size       = parseFloat(document.getElementById('f-font-size').value) || null;
  cfg.font_size_maximum = parseFloat(document.getElementById('f-font-size-max').value) || null;
  cfg.margin          = parseFloat(document.getElementById('f-margin').value) || null;
  cfg.label_gap       = parseFloat(document.getElementById('f-label-gap').value) ?? 2;
  cfg.column_gap      = parseFloat(document.getElementById('f-col-gap').value) ?? 0.4;
  cfg.no_overheight   = document.getElementById('f-no-overheight').checked;
  cfg.body_depth      = parseFloat(document.getElementById('f-body-depth').value) || null;
  cfg.multimaterial   = document.getElementById('f-multimaterial').value;
  cfg.style           = document.querySelector('input[name="style"]:checked')?.value ?? 'embossed';
  cfg.version         = document.getElementById('f-version').value;
  cfg.labels          = [...document.querySelectorAll('.division-textarea')].map(t => t.value);
  while (cfg.labels.length < cfg.divisions) cfg.labels.push('');
  saveToLocalStorage();
  updatePreviewStaleness();
  return cfg;
}

// When user manually edits the name field, stop auto-naming
document.getElementById('f-name').addEventListener('input', () => {
  const cfg = labels.find(l => l.id === activeId);
  if (cfg) cfg.nameIsAuto = false;
});

document.getElementById('save-label-btn').addEventListener('click', () => {
  const cfg = readEditorIntoConfig();
  if (!cfg) return;
  renderLabelList();
  document.getElementById('editing-label-name').textContent = cfg.name;
  toast('Label saved', 'success');
});

document.getElementById('f-divisions').addEventListener('change', () => {
  const n = parseInt(document.getElementById('f-divisions').value) || 1;
  const existing = [...document.querySelectorAll('.division-textarea')].map(t => t.value);
  renderDivisionInputs(n, existing);
});

document.getElementById('f-base').addEventListener('change', e => {
  toggleVersionField(e.target.value);
  updateMultimaterialOptions(e.target.value);
});
const MM_NOTES = {
  none:             '',
  text:             'body.step = full base (flat face), text.step = raised text only',
  split:            'body.step = base below label face, text.step = raised rim + text',
  background:       'body.step = bg face slab only, text.step = structure + text (text color fills body)',
  background_full:  'body.step = bg fills full body depth, text.step = outer rim + text (rim visible on bottom edges)',
};

function updateMmNote(mode) {
  const note = document.getElementById('mm-note');
  note.textContent = MM_NOTES[mode] || '';
  note.style.display = (mode && mode !== 'none') ? '' : 'none';
}

document.getElementById('f-multimaterial').addEventListener('change', e => {
  updateMmNote(e.target.value);
});

function toggleVersionField(base) {
  document.getElementById('version-field').style.display = base === 'cullenect' ? '' : 'none';
}

function updateAutoName() {
  const cfg = labels.find(l => l.id === activeId);
  if (!cfg || !cfg.nameIsAuto) return;
  const texts = [...document.querySelectorAll('.division-textarea')].map(t => t.value);
  const generated = autoNameFromLabels(texts);
  if (!generated) return;
  const nameInput = document.getElementById('f-name');
  nameInput.value = generated;
  cfg.name = generated;
  document.getElementById('editing-label-name').textContent = generated;
  renderLabelList();
}

function insertDivisionAfter(afterIndex) {
  const textareas = [...document.querySelectorAll('.division-textarea')];
  const values = textareas.map(t => t.value);
  values.splice(afterIndex + 1, 0, '');
  const newCount = values.length;
  document.getElementById('f-divisions').value = newCount;
  renderDivisionInputs(newCount, values);
  // Focus the newly added textarea
  const newTextareas = document.querySelectorAll('.division-textarea');
  newTextareas[afterIndex + 1]?.focus();
  if (activeId) readEditorIntoConfig();
}

function removeDivision(index) {
  const textareas = [...document.querySelectorAll('.division-textarea')];
  if (textareas.length <= 1) return;
  const values = textareas.map(t => t.value);
  values.splice(index, 1);
  const newCount = values.length;
  document.getElementById('f-divisions').value = newCount;
  renderDivisionInputs(newCount, values);
  const newTextareas = document.querySelectorAll('.division-textarea');
  newTextareas[Math.min(index, newCount - 1)]?.focus();
  if (activeId) readEditorIntoConfig();
}

function renderDivisionInputs(count, existing = []) {
  const container = document.getElementById('divisions-container');
  container.innerHTML = '';
  for (let i = 0; i < count; i++) {
    const wrap = document.createElement('div');
    wrap.className = 'division-input';
    const hint = count > 1 ? `Div ${i + 1}` : 'Content';
    // Convert legacy literal \n sequences to real newlines when loading
    const val = (existing[i] ?? '').replace(/\\n/g, '\n');
    wrap.innerHTML = `
      <div class="div-header">
        <label class="div-label">${escHtml(hint)}</label>
        <div class="div-actions">
          <button type="button" class="div-btn div-add-btn" title="Add division after this one (Tab)">+</button>
          ${count > 1 ? '<button type="button" class="div-btn div-remove-btn" title="Remove this division">×</button>' : ''}
        </div>
      </div>
      <textarea class="division-textarea" rows="3"
        data-hint="${escHtml(hint)}"
        placeholder="${count > 1 ? `Division ${i + 1} — e.g. {bolt(16)}\nM3x16` : 'Label content — e.g. {bolt(16)}\nM3x16'}"
      >${escHtml(val)}</textarea>
      <span class="div-hint">Enter = new line · Tab = add division</span>`;
    container.appendChild(wrap);
    wrap.querySelector('.div-add-btn').addEventListener('click', () => insertDivisionAfter(i));
    wrap.querySelector('.div-remove-btn')?.addEventListener('click', () => removeDivision(i));
  }
  // Re-assign focus tracking and auto-name on input
  container.querySelectorAll('.division-textarea').forEach((ta, i, all) => {
    ta.addEventListener('focus', () => {
      lastFocusedTextarea = ta;
      document.getElementById('frag-target-hint').textContent = '→ ' + ta.dataset.hint;
    });
    ta.addEventListener('input', updateAutoName);
    ta.addEventListener('keydown', e => {
      if (e.key === 'Tab' && !e.shiftKey) {
        // Tab from any textarea: if it's the last one, add a new division
        // If not the last, let normal Tab move focus to the next textarea
        if (i === all.length - 1) {
          e.preventDefault();
          insertDivisionAfter(i);
        }
        // else: allow default Tab to move to next division textarea naturally
      }
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Preview
// ─────────────────────────────────────────────────────────────────────────────

document.getElementById('preview-btn').addEventListener('click', async () => {
  const cfg = readEditorIntoConfig();
  if (!cfg) return;

  const overlay = document.getElementById('preview-overlay');
  overlay.innerHTML = `<div class="spinner"></div><span class="preview-status">Generating 3D model…</span>`;
  overlay.classList.remove('hidden');

  try {
    const res = await fetch('/api/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configToRequest(cfg)),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }

    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      const data = await res.json();
      if (data.multimaterial) {
        loadMultiMaterialSTLs(
          base64ToArrayBuffer(data.body),
          base64ToArrayBuffer(data.text),
        );
      } else {
        throw new Error('Unexpected JSON response from preview');
      }
    } else {
      loadSTLIntoScene(await res.arrayBuffer());
    }

    overlay.classList.add('hidden');
    document.getElementById('preview-label-name').textContent = cfg.name;
    previewedLabelId = cfg.id;
    previewedConfigJSON = JSON.stringify(configToRequest(cfg));
    updatePreviewStaleness();
  } catch (e) {
    overlay.innerHTML = `<div style="color:var(--danger);font-size:12px;padding:16px;text-align:center;max-width:220px">Error: ${escHtml(e.message)}</div>`;
    toast('Preview failed: ' + e.message, 'error');
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Generate / Download
// ─────────────────────────────────────────────────────────────────────────────

document.getElementById('generate-btn').addEventListener('click', async () => {
  if (!labels.length) return;
  // Predbox validation — only 4u/5u/6u/7u supported
  const badPredbox = labels.filter(l => l.base === 'predbox' && l.width_unit === 'u' && ![4,5,6,7].includes(l.width));
  if (badPredbox.length) {
    toast(`Pred Box only supports 4u, 5u, 6u, 7u — check: ${badPredbox.map(l => l.name).join(', ')}`, 'error');
    return;
  }
  const btn = document.getElementById('generate-btn');
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:2px"></span> Generating…';

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ configs: labels.map(configToRequest) }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    triggerDownload(await res.blob(), 'labels.zip');
    toast(`Downloaded ${labels.length} label${labels.length !== 1 ? 's' : ''}`, 'success');
  } catch (e) {
    toast('Generation failed: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
    updateGenerateBar();
  }
});

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement('a'), { href: url, download: filename }).click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

// ─────────────────────────────────────────────────────────────────────────────
// Config serialisation
// ─────────────────────────────────────────────────────────────────────────────

function configToRequest(cfg) {
  return {
    name: cfg.name, base: cfg.base,
    width: cfg.width, width_unit: cfg.width_unit, height: cfg.height, depth: cfg.depth,
    body_depth: cfg.body_depth ?? null,
    divisions: cfg.divisions, labels: cfg.labels.slice(0, cfg.divisions),
    font: cfg.font, font_style: cfg.font_style, font_size: cfg.font_size,
    font_size_maximum: cfg.font_size_maximum, margin: cfg.margin,
    style: cfg.style, label_gap: cfg.label_gap, column_gap: cfg.column_gap,
    no_overheight: cfg.no_overheight, version: cfg.version,
    multimaterial: cfg.multimaterial, output_format: cfg.output_format,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Import / Export session
// ─────────────────────────────────────────────────────────────────────────────

document.getElementById('export-btn').addEventListener('click', () => {
  triggerDownload(new Blob([JSON.stringify({ labels }, null, 2)], { type: 'application/json' }), 'label_session.json');
});

document.getElementById('import-btn').addEventListener('click', () => document.getElementById('file-input').click());

document.getElementById('file-input').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    try {
      const data = JSON.parse(ev.target.result);
      if (!Array.isArray(data.labels)) throw new Error('Invalid session file');
      labels = data.labels;
      nextId = Math.max(...labels.map(l => l.id), 0) + 1;
      activeId = null;
      clearEditor();
      renderLabelList();
      toast(`Imported ${labels.length} label${labels.length !== 1 ? 's' : ''}`, 'success');
    } catch (err) { toast('Import failed: ' + err.message, 'error'); }
  };
  reader.readAsText(file);
  e.target.value = '';
});

// ─────────────────────────────────────────────────────────────────────────────
// Clear all, delete
// ─────────────────────────────────────────────────────────────────────────────

document.getElementById('clear-all-btn').addEventListener('click', () => {
  if (!labels.length || !confirm(`Delete all ${labels.length} labels?`)) return;
  labels = []; activeId = null; nextId = 1;
  clearEditor(); renderLabelList();
  try { localStorage.removeItem('gridfinity_session'); } catch (_) {}
});

// ── Bulk overrides ─────────────────────────────────────────────────────────────

document.getElementById('bulk-base').addEventListener('change', e => {
  const val = e.target.value;
  if (!val || !labels.length) { e.target.value = ''; return; }
  labels.forEach(l => l.base = val);
  if (activeId) loadLabelIntoEditor(activeId);
  renderLabelList();
  toast(`All ${labels.length} labels → ${val} base`, 'success');
  e.target.value = '';
});

document.getElementById('bulk-format').addEventListener('change', e => {
  const val = e.target.value;
  if (!val || !labels.length) { e.target.value = ''; return; }
  labels.forEach(l => l.output_format = val);
  if (activeId) loadLabelIntoEditor(activeId);
  renderLabelList();
  toast(`All ${labels.length} labels → ${val.toUpperCase()}`, 'success');
  e.target.value = '';
});

document.getElementById('bulk-multimaterial').addEventListener('change', e => {
  const val = e.target.value;
  if (!val || !labels.length) { e.target.value = ''; return; }
  const predOnly = PRED_ONLY_MM.some(o => o.value === val);
  let count = 0, skipped = 0;
  labels.forEach(l => {
    if (predOnly && l.base !== 'pred') { skipped++; return; }
    l.multimaterial = val; count++;
  });
  if (activeId) loadLabelIntoEditor(activeId);
  renderLabelList();
  const msg = skipped ? `${count} labels → ${val} (${skipped} skipped — non-pred)` : `All ${count} labels → ${val}`;
  toast(msg, 'success');
  e.target.value = '';
});

document.getElementById('delete-label-btn').addEventListener('click', () => {
  if (activeId) deleteLabel(activeId);
});

document.getElementById('add-label-btn').addEventListener('click', addLabel);
document.getElementById('empty-add-btn').addEventListener('click', addLabel);

// ─────────────────────────────────────────────────────────────────────────────
// Live autosave — persist every form change immediately so switching labels,
// clicking download, or any other action always sees the latest values.
// Programmatic .value assignments don't fire these events, so loading a label
// into the form never triggers a spurious save.
// ─────────────────────────────────────────────────────────────────────────────

document.getElementById('editor-form').addEventListener('input',  () => { if (activeId) readEditorIntoConfig(); });
document.getElementById('editor-form').addEventListener('change', () => { if (activeId) readEditorIntoConfig(); });

// ─────────────────────────────────────────────────────────────────────────────
// Collapsible sections
// ─────────────────────────────────────────────────────────────────────────────

document.querySelectorAll('.collapsible-header').forEach(header => {
  header.addEventListener('click', () => {
    const body = document.getElementById(header.dataset.target);
    header.classList.toggle('collapsed');
    body.classList.toggle('collapsed');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Utility
// ─────────────────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ─────────────────────────────────────────────────────────────────────────────
// Init
// ─────────────────────────────────────────────────────────────────────────────

initThree();
buildFragPicker();
if (loadFromLocalStorage()) {
  renderLabelList();
  selectLabel(labels[0].id);
} else {
  renderLabelList();
}
