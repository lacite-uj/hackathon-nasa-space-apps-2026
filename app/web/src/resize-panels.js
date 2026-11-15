import { el, isMobile } from './dom.js';
import { t } from './i18n.js';

// Arrastar a borda interna da lista (esquerda) e do card (direita) para mudar a largura deles.
// A largura vira as variáveis CSS --list-w / --card-w no :root, que a lista, o card e a legenda já usam;
// a cena reenquadra os globos a cada mudança (onChange). Só no desktop: no celular a lista é uma folha e o
// card é uma gaveta. A largura escolhida fica salva no navegador (se o armazenamento estiver disponível).

const STORE_KEY = 'analogos:larguras';
const MIN_FREE = 260; // px que sempre sobram para os globos entre os dois painéis
const LIMITS = { list: { min: 220, max: 520, css: '--list-w' }, card: { min: 340, max: 760, css: '--card-w' } };

function load() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) ?? {}; } catch { return {}; }
}
function save(widths) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(widths)); } catch { /* sem armazenamento: só nesta visita */ }
}

/**
 * @param {object} opts
 * @param {HTMLElement} opts.listEl   #site-list
 * @param {HTMLElement} opts.panelEl  #panel
 * @param {() => void} opts.onChange  chamado a cada mudança de largura (durante o arraste também)
 */
export function createPanelResizers({ listEl, panelEl, onChange }) {
  const root = document.documentElement;
  const widths = load(); // { list?: px, card?: px }; ausente = largura padrão do CSS

  // Largura atual em unidades de --list-w / --card-w (a largura visível + o --gap).
  const gap = () => parseFloat(getComputedStyle(root).getPropertyValue('--gap')) || 0;
  const current = (kind) => {
    const host = kind === 'list' ? listEl : panelEl;
    const w = host.getBoundingClientRect().width;
    if (w) return w + gap();
    return parseFloat(getComputedStyle(host).width) + gap() || LIMITS[kind].min;
  };

  /** Limita a largura para caber na janela e deixar MIN_FREE px para a cena. */
  function clampWidth(kind, px) {
    const other = kind === 'list' ? 'card' : 'list';
    const otherW = widths[other] ?? current(other);
    const max = Math.min(LIMITS[kind].max, window.innerWidth - otherW - MIN_FREE);
    return Math.round(Math.max(LIMITS[kind].min, Math.min(px, max)));
  }

  function apply(kind, px, persist = false) {
    if (px == null) { delete widths[kind]; root.style.removeProperty(LIMITS[kind].css); }
    else { widths[kind] = clampWidth(kind, px); root.style.setProperty(LIMITS[kind].css, `${widths[kind]}px`); }
    handles[kind].setAttribute('aria-valuenow', String(Math.round(widths[kind] ?? current(kind))));
    if (persist) save(widths);
    onChange();
  }

  function makeHandle(kind, host) {
    const label = kind === 'list' ? t('Largura da lista de locais') : t('Largura do card de detalhes');
    const handle = el('div', {
      class: `resizer resizer-${kind}`, role: 'separator', tabindex: '0', 'aria-orientation': 'vertical',
      'aria-label': t('{label} (arraste, ou use as setas; duplo clique volta ao padrão)', { label }),
      'aria-valuemin': String(LIMITS[kind].min), 'aria-valuemax': String(LIMITS[kind].max),
      title: t('Arraste para redimensionar · duplo clique volta ao padrão'),
    });
    // Lista: a borda direita cresce para a direita. Card: a borda esquerda cresce para a esquerda.
    const sign = kind === 'list' ? 1 : -1;
    let start = null;
    handle.addEventListener('pointerdown', (event) => {
      if (event.button !== 0) return;
      start = { x: event.clientX, w: widths[kind] ?? current(kind) };
      handle.setPointerCapture(event.pointerId);
      document.body.classList.add('is-resizing');
      event.preventDefault();
    });
    handle.addEventListener('pointermove', (event) => {
      if (!start) return;
      apply(kind, start.w + sign * (event.clientX - start.x));
    });
    const end = () => {
      if (!start) return;
      start = null;
      document.body.classList.remove('is-resizing');
      save(widths);
    };
    handle.addEventListener('pointerup', end);
    handle.addEventListener('pointercancel', end);
    handle.addEventListener('dblclick', () => apply(kind, null, true));
    handle.addEventListener('keydown', (event) => {
      const step = event.shiftKey ? 64 : 16;
      const delta = { ArrowRight: step * sign, ArrowLeft: -step * sign }[event.key];
      if (delta == null) return;
      apply(kind, (widths[kind] ?? current(kind)) + delta, true);
      event.preventDefault();
    });
    host.append(handle);
    return handle;
  }

  const handles = { list: makeHandle('list', listEl), card: makeHandle('card', panelEl) };

  // Restaura as larguras salvas (limitadas à janela atual) e reaplica o limite quando a janela muda.
  function refit() {
    if (isMobile()) return;
    for (const kind of ['list', 'card']) {
      if (widths[kind] != null) root.style.setProperty(LIMITS[kind].css, `${clampWidth(kind, widths[kind])}px`);
    }
  }
  refit();
  window.addEventListener('resize', () => { refit(); onChange(); });

  return { refit };
}
