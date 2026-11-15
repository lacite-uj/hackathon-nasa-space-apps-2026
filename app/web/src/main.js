import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createGlobe, addMarker, createRing, setRing } from './globe.js';
import { createSelection } from './selection.js';
import { createFocus } from './focus.js';
import { createArcLayer, ARC_WIDTH } from './arcs.js';
import { createInteraction } from './interaction.js';
import { createList } from './list.js';
import { createPanel } from './panel.js';
import { isLightboxOpen } from './lightbox.js';
import { createPanelResizers } from './resize-panels.js';
import { el, isMobile } from './dom.js';
import { LEVELS, fmtOutOf3, levelInfo } from './format.js';
import { applyStaticTexts, lang, t, setLang, takeRestore, translateData } from './i18n.js';

// Orquestrador: monta a cena, carrega o JSON e liga os módulos ao estado da seleção (selection.js).
// Lista (list.js), card (panel.js) e cena não se chamam: cada um assina o estado e reage.
// Idioma (i18n.js): os textos fixos do HTML já estão em inglês; applyStaticTexts() aplica o português
// quando é o ativo, loadData() troca os textos do analogs.json pelo dicionário e o botão EN | PT do
// cabeçalho guarda a seleção, troca o idioma e recarrega.

applyStaticTexts();

/** Botão EN | PT: guarda a seleção atual, grava o idioma e recarrega (i18n.js › setLang). */
function wireLanguageSwitch() {
  for (const button of document.querySelectorAll('.lang-btn')) {
    button.setAttribute('aria-pressed', String(button.dataset.lang === lang));
    button.addEventListener('click', () => {
      const state = app?.selection.state;
      setLang(button.dataset.lang, state ? { analogId: state.analogId, targetId: state.targetId } : undefined);
    });
  }
}
wireLanguageSwitch();

// Layout dos globos. Raios e posições configuráveis (ver docs/instrucoes-desenvolvimento.md, seção 5).
// Rotação inicial: yaw para mostrar uma face útil e inclinação para deixar o polo sul lunar visível.
// Um ponto de longitude λ fica de frente para a câmera com yaw = −(90° + λ) (ver latLonToVector3).
// Marte começa com Jezero (λ ≈ 77,6° E, alvo do analogs.json) virado para a câmera.
const yawFacing = (lonDeg) => -THREE.MathUtils.degToRad(90 + lonDeg);
const LAYOUT = {
  earth: { radius: 1.0,  x: 0,    texture: 'textures/earth.jpg', rotation: [0.25, 0, 0] },
  moon:  { radius: 0.4,  x: -2.8, texture: 'textures/moon.jpg',  rotation: [-0.6, -Math.PI / 2, 0] },
  mars:  { radius: 0.55, x: 2.8,  texture: 'textures/mars.jpg',  rotation: [0.2, yawFacing(77.58), 0] },
};
// Meia largura da cena que precisa caber na tela (Marte em x=2,8 + raio + folga).
const SCENE_HALF_WIDTH = 3.6;
const SCENE_HALF_HEIGHT = 1.4;
// Folga em volta da Terra + globo do alvo quando há um local em foco.
const FOCUS_MARGIN = 0.12;
const INITIAL_TARGET = 'marte';
const DIM_OPACITY = 0.15;

// Pontos fáceis de reconhecer para conferir a projeção (ativar com ?debug=1).
const DEBUG_POINTS = [
  { body: 'earth', name: 'Rio de Janeiro', lat: -22.9,  lon: -43.2 },
  { body: 'moon',  name: 'Cratera Tycho',  lat: -43.3,  lon: -11.4 },
  { body: 'mars',  name: 'Olympus Mons',   lat: 18.65,  lon: -133.8 },
];

const params = new URLSearchParams(location.search);
const DEBUG = params.get('debug') === '1';

const canvas = document.getElementById('scene');
const listEl = document.getElementById('site-list');
const panelEl = document.getElementById('panel');
const legendEl = document.getElementById('legend');
const tooltipEl = document.getElementById('tooltip');
const listToggle = document.getElementById('list-toggle');

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x05070d);

const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
camera.position.set(0, 0, 9);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.minDistance = 2.5;
controls.maxDistance = 25;

scene.add(new THREE.AmbientLight(0xffffff, 0.35));
const sun = new THREE.DirectionalLight(0xffffff, 2.2);
sun.position.set(3, 2, 6);
scene.add(sun);

const globes = {};
for (const [id, cfg] of Object.entries(LAYOUT)) {
  const globe = createGlobe({ id, radius: cfg.radius, texture: cfg.texture, renderer });
  globe.position.x = cfg.x;
  globe.rotation.set(...cfg.rotation);
  createRing(globe);
  scene.add(globe);
  globes[id] = globe;
}

if (DEBUG) {
  for (const p of DEBUG_POINTS) addMarker(globes[p.body], p.lat, p.lon, 'debug', { id: `debug-${p.body}`, name: p.name });
}

const focus = createFocus({ camera, controls, canvas });
const arcs = createArcLayer(scene);
let app = null; // { data, selection, targetById, ... } depois que o JSON carrega

/**
 * Área da tela que sobra para os globos (px): à direita da lista e à esquerda do card; no celular,
 * acima da gaveta. A câmera centraliza a cena nessa área com setViewOffset (focus.js).
 */
function freeArea(cardOpen) {
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  let left = 0, right = w, top = 76, bottom = h - 40;
  if (isMobile()) {
    if (cardOpen) bottom = Math.round(h * 0.4); // a gaveta ocupa ~60% da altura
  } else {
    left = listEl.getBoundingClientRect().right;
    if (cardOpen) right = panelEl.getBoundingClientRect().left;
  }
  if (right - left < 120) { left = 0; right = w; }
  if (bottom - top < 80) { top = 0; bottom = h; }
  return { left, right, top, bottom, w, h };
}

/** Enquadramento { position, target, offset } para uma faixa da cena centrada em x = centerX. */
function frameFor(centerX, halfWidth, halfHeight, cardOpen) {
  const area = freeArea(cardOpen);
  const tanHalf = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const aspect = area.w / area.h;
  const dist = Math.max(
    halfWidth / (tanHalf * aspect * ((area.right - area.left) / area.w)),
    halfHeight / (tanHalf * ((area.bottom - area.top) / area.h))
  );
  return {
    position: new THREE.Vector3(centerX, 0, dist),
    target: new THREE.Vector3(centerX, 0, 0),
    offset: { x: area.w / 2 - (area.left + area.right) / 2, y: area.h / 2 - (area.top + area.bottom) / 2 },
  };
}

/** Sem seleção: os três globos. Com seleção: a Terra e o globo do alvo ativo. */
const FOCUS_MIN_RATIO = 0.88;

function currentFrame() {
  const state = app?.selection.state;
  const home = frameFor(0, SCENE_HALF_WIDTH, SCENE_HALF_HEIGHT, false);
  if (!state?.analogId) return home;
  const body = app.targetById.get(state.targetId).body;
  const other = LAYOUT[body];
  const min = Math.min(-LAYOUT.earth.radius, other.x - other.radius);
  const max = Math.max(LAYOUT.earth.radius, other.x + other.radius);
  const frame = frameFor((min + max) / 2, (max - min) / 2 + FOCUS_MARGIN, LAYOUT.earth.radius + FOCUS_MARGIN, true);
  // Com lista e card largos a área livre encolhe e a câmera se afasta o necessário para a Terra e o alvo
  // caberem inteiros (antes ela parava no enquadramento inicial e os globos ficavam sob os painéis).
  // Também não aproxima demais: no máximo FOCUS_MIN_RATIO da distância inicial, para manter os globos e o
  // arco num enquadramento aberto (em telas largas o encaixe exato colava a câmera nos planetas).
  frame.position.z = Math.max(frame.position.z, home.position.z * FOCUS_MIN_RATIO);
  return frame;
}

function resize() {
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  arcs.setResolution(w, h);
  // Afasta a câmera o suficiente para o enquadramento atual caber na área livre.
  focus.jumpTo(currentFrame());
}
window.addEventListener('resize', resize);
resize();

/** Legenda: os patamares da escala (sempre visível) e, com seleção, o que o arco significa. */
function buildLegend() {
  const value = el('span', { class: 'legend-value' });
  const arc = el('div', { class: 'legend-arc', hidden: true },
    el('span', { class: 'legend-title' }, t('Arco:')),
    el('span', { class: 'legend-ramp', 'aria-hidden': 'true', style: `--min:${ARC_WIDTH.min}px;--max:${ARC_WIDTH.max}px` }),
    el('span', {}, t('cor = patamar · espessura = nota')),
    value);
  legendEl.replaceChildren(
    el('div', { class: 'legend-tiers' },
      el('span', { class: 'legend-title' }, t('Aderência (0 a 3):')),
      ['high', 'moderate', 'low', 'none'].map((k) => el('span', { class: `legend-tier ${LEVELS[k].cls}` },
        el('span', { class: 'legend-dot', 'aria-hidden': 'true' }), `${LEVELS[k].label} `,
        el('span', { class: 'legend-range' }, `(${LEVELS[k].range})`)))),
    arc);
  legendEl.hidden = false;
  return { value, arc };
}

/**
 * Dicionário dos textos do analogs.json (português → inglês). Só em inglês: em português o JSON já
 * é o texto original. Falha no dicionário não derruba a página — os textos ficam em português.
 */
async function loadDictionary() {
  if (lang !== 'en') return null;
  try {
    const res = await fetch('data/i18n-en.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Dicionário i18n-en.json indisponível; textos do JSON ficam em português.', err);
    return null;
  }
}

async function loadData() {
  const [res, dictionary] = await Promise.all([fetch('data/analogs.json'), loadDictionary()]);
  if (!res.ok) throw new Error(`Falha ao carregar analogs.json: HTTP ${res.status}`);
  const data = await res.json();
  // Antes de criar marcadores, lista e card: os textos do JSON saem traduzidos uma única vez.
  if (dictionary) translateData(data, dictionary);

  // Alvos (Lua – Shackleton, Marte – Jezero) e os 14 análogos da Terra vêm do ETL (python -m etl build).
  // Os ids dos marcadores são os mesmos de data/processed: alvo_id ('lua', 'marte') e local_id.
  const targetMarkers = new Map();
  const analogMarkers = new Map();
  for (const tgt of data.targets) targetMarkers.set(tgt.id, addMarker(globes[tgt.body], tgt.lat, tgt.lon, 'target', tgt));
  for (const a of data.analogs) analogMarkers.set(a.id, addMarker(globes.earth, a.lat, a.lon, 'analog', a));

  document.getElementById('status').textContent =
    t('{t} alvos · {a} análogos · {l} ligações',
      { t: data.targets.length, a: data.analogs.length, l: data.links.length });

  const targetById = new Map(data.targets.map((tgt) => [tgt.id, tgt]));
  const analogById = new Map(data.analogs.map((a) => [a.id, a]));
  const linkIndex = new Map(data.links.map((l) => [`${l.analog}|${l.target}`, l]));
  const linkOf = (analogId, targetId) => linkIndex.get(`${analogId}|${targetId}`);

  const selection = createSelection({
    analogs: data.analogs,
    targets: data.targets,
    initialTarget: targetById.has(INITIAL_TARGET) ? INITIAL_TARGET : data.targets[0].id,
  });
  // Seleção guardada na troca de idioma (takeRestore a consome; só existe uma vez).
  const restore = takeRestore();
  if (restore?.targetId) selection.setTarget(restore.targetId);
  if (restore?.analogId) selection.selectAnalog(restore.analogId);
  app = { data, selection, targetById, analogById, linkOf, targetMarkers, analogMarkers };

  const closeSheet = () => {
    listEl.classList.remove('is-open');
    listToggle.setAttribute('aria-expanded', 'false');
  };
  listToggle.addEventListener('click', () => {
    const openNow = listEl.classList.toggle('is-open');
    listToggle.setAttribute('aria-expanded', String(openNow));
  });

  // A ordem das assinaturas importa: lista e card primeiro (mudam o layout), cena depois (mede o layout).
  createList({ root: listEl, data, linkOf, selection, onPick: closeSheet });
  createPanel({ root: panelEl, data, linkOf, selection });
  // Bordas arrastáveis da lista e do card: a cada mudança, a câmera reenquadra os globos na área livre
  // (e se afasta o quanto for preciso para eles não saírem de vista).
  createPanelResizers({ listEl, panelEl, onChange: () => focus.jumpTo(currentFrame()) });
  const legend = buildLegend();

  function syncScene(state, prev) {
    const analog = state.analogId ? analogById.get(state.analogId) : null;
    const target = targetById.get(state.targetId);
    const link = analog ? linkOf(analog.id, target.id) : null;
    document.body.classList.toggle('has-selection', Boolean(analog));

    // Esmaece o que não está em foco e põe os anéis no análogo e no alvo.
    for (const [id, marker] of analogMarkers) marker.material.opacity = !analog || id === analog.id ? 1 : DIM_OPACITY;
    for (const [id, marker] of targetMarkers) marker.material.opacity = !analog || id === target.id ? 1 : DIM_OPACITY;
    setRing(globes.earth, analog ? analogMarkers.get(analog.id) : null);
    for (const t of data.targets) setRing(globes[t.body], analog && t.id === target.id ? targetMarkers.get(t.id) : null);

    // Só o arco do link ativo (a rede inteira seria arcs.setLinks com os 28 links).
    arcs.setLinks(link ? [{ score: link.score, level: link.level, from: analogMarkers.get(analog.id), to: targetMarkers.get(target.id) }] : []);
    legend.arc.hidden = !link;
    legend.arc.className = `legend-arc ${levelInfo(link?.level).cls}`;
    if (link) legend.value.textContent = `· ${analog.name} → ${target.short_name}: ${fmtOutOf3(link.adherence)} (${levelInfo(link.level).label.toLowerCase()})`;

    const frame = currentFrame();
    if (analog) {
      focus.rotateGlobeTo(globes.earth, analog.lat, analog.lon, frame.position);
      focus.rotateGlobeTo(globes[target.body], target.lat, target.lon, frame.position);
    }
    if (prev) focus.flyTo(frame); else focus.jumpTo(frame);
  }
  selection.subscribe(syncScene);
  syncScene(selection.state, null);

  // Destaque passageiro: item da lista ↔ marcador no globo.
  selection.subscribeHover((id) => {
    for (const [markerId, marker] of analogMarkers) marker.scale.setScalar(markerId === id ? 1.9 : 1);
  });

  createInteraction({
    canvas, camera, globes, tooltip: tooltipEl,
    markers: [...analogMarkers.values(), ...targetMarkers.values()],
    onHover: (marker) => selection.setHover(marker?.userData.kind === 'analog' ? marker.userData.id : null),
    onClick: (marker) => {
      if (!marker) selection.clear();
      else if (marker.userData.kind === 'analog') selection.selectAnalogFromScene(marker.userData.id);
      else selection.setTarget(marker.userData.id);
    },
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (isLightboxOpen()) return; // o <dialog> da foto fecha sozinho; o card continua aberto
    if (listEl.classList.contains('is-open')) closeSheet();
    else selection.clear();
  });

  Object.assign(window.__app, { data, selection, arcs, focus });
  return data;
}

renderer.setAnimationLoop(() => {
  focus.update();
  if (!focus.cameraBusy) controls.update();
  arcs.update();
  renderer.render(scene, camera);
});

// Exposto para depuração no console.
window.__app = { scene, camera, controls, globes, renderer };

loadData().catch((err) => {
  console.error(err);
  document.getElementById('status').textContent = 'Erro ao carregar os dados. Veja o console.';
});
