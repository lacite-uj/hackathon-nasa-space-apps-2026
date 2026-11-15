import { el, prefersReducedMotion } from './dom.js';
import { barWidth, fmtFixed, levelInfo, targetOf, targetShort } from './format.js';
import { ordinal, t } from './i18n.js';

// Painel lateral: seletor de alvo e lista dos análogos, ordenada pelo rank do link com o alvo ativo.
// É também a lista acessível do projeto: tudo o que o clique no 3D faz, ela faz pelo teclado.
// Textos visíveis passam por t() (i18n.js); os nomes e países vêm já traduzidos do analogs.json.

/**
 * @param {object} opts
 * @param {HTMLElement} opts.root         #site-list
 * @param {object} opts.data              analogs.json
 * @param {(analogId: string, targetId: string) => object | undefined} opts.linkOf
 * @param {ReturnType<import('./selection.js').createSelection>} opts.selection
 * @param {() => void} [opts.onPick]      chamado depois de escolher um item (fecha a folha no celular)
 */
export function createList({ root, data, linkOf, selection, onPick }) {
  const targetById = new Map(data.targets.map((tgt) => [tgt.id, tgt]));
  const items = new Map(); // analogId → { li, rank, tied, fill, adherence, listed }
  let cursorId = null;     // item sob o cursor do teclado (aria-activedescendant)

  const targetButtons = new Map();
  const switcher = el('div', { class: 'seg', role: 'group', 'aria-label': t('Alvo da comparação') },
    data.targets.map((tgt) => {
      const button = el('button', { type: 'button', class: 'seg-btn', 'aria-pressed': 'false',
        onclick: () => selection.setTarget(tgt.id) }, targetShort(tgt));
      targetButtons.set(tgt.id, button);
      return button;
    }));
  const hint = el('p', { class: 'list-hint', id: 'site-list-hint' });
  const listbox = el('ul', { class: 'sites', role: 'listbox', tabindex: '0', 'aria-labelledby': 'site-list-title',
    'aria-describedby': 'site-list-hint' });

  for (const analog of data.analogs) {
    const rank = el('span', { class: 'site-rank' });
    const tied = el('span', { class: 'sr-only', hidden: true }, t(' (empate)'));
    const listed = el('span', { class: 'tag tag-listed', hidden: true }, t('listado'));
    const approx = analog.approximate_coords
      ? el('span', { class: 'tag tag-approx', title: t('Coordenada aproximada') }, t('≈ aprox.'),
          el('span', { class: 'sr-only' }, t(' (coordenada aproximada)')))
      : null;
    const fill = el('span', { class: 'bar-fill' });
    const adherence = el('span', { class: 'site-adh lv-text' });
    const status = el('span', { class: 'tag tag-status tag-sm' });
    const score = el('span', { class: 'site-score' },
      el('span', { class: 'bar', 'aria-hidden': 'true' }, fill),
      el('span', { class: 'sr-only' }, t('aderência '), adherence, status));
    const li = el('li', { class: 'site', role: 'option', id: `site-opt-${analog.id}`, 'data-id': analog.id,
      'aria-selected': 'false' },
      el('span', { class: 'site-rank-cell' }, rank, tied),
      el('span', { class: 'site-main' },
        el('span', { class: 'site-name' }, analog.name, ' ', listed, approx),
        el('span', { class: 'site-country' }, analog.country)),
      score);
    li.addEventListener('click', () => { setCursor(analog.id); selection.selectAnalog(analog.id); onPick?.(); });
    li.addEventListener('pointerenter', (e) => { if (e.pointerType !== 'touch') selection.setHover(analog.id); });
    li.addEventListener('pointerleave', () => selection.setHover(null));
    items.set(analog.id, { li, rank, tied, fill, adherence, listed, score, status });
  }

  root.replaceChildren(
    el('div', { class: 'list-head' },
      el('h2', { id: 'site-list-title' }, t('Locais análogos na Terra')),
      switcher, hint),
    listbox);

  function orderedIds(targetId) {
    // A ordem é o rank do JSON; o front só ordena pelo número que recebeu.
    return data.analogs
      .map((a) => ({ id: a.id, rank: linkOf(a.id, targetId)?.rank ?? Infinity }))
      .sort((x, y) => x.rank - y.rank)
      .map((x) => x.id);
  }

  function setCursor(id) {
    if (cursorId) items.get(cursorId)?.li.classList.remove('is-cursor');
    cursorId = id;
    if (id) {
      const { li } = items.get(id);
      li.classList.add('is-cursor');
      listbox.setAttribute('aria-activedescendant', li.id);
      li.scrollIntoView({ block: 'nearest' });
    } else {
      listbox.removeAttribute('aria-activedescendant');
    }
  }

  function render(state, prev) {
    const target = targetById.get(state.targetId);
    const targetChanged = !prev || prev.targetId !== state.targetId;

    for (const [id, button] of targetButtons) button.setAttribute('aria-pressed', String(id === state.targetId));
    hint.textContent = t('Ordenados pela aderência a {name}. Nota de 0 a 3.', { name: target.name });

    if (targetChanged) {
      const animate = prev && !prefersReducedMotion();
      const before = new Map();
      if (animate) for (const [id, { li }] of items) before.set(id, li.offsetTop);

      for (const id of orderedIds(state.targetId)) {
        const item = items.get(id);
        const link = linkOf(id, state.targetId);
        item.rank.textContent = link?.rank != null ? ordinal(link.rank) : '–';
        // Empate vem pronto do ETL (rank_tied); o front só mostra a marca.
        item.rank.classList.toggle('is-tied', Boolean(link?.rank_tied));
        item.rank.title = link?.rank_tied ? t('Empate: outro local tem a mesma aderência') : '';
        item.tied.hidden = !link?.rank_tied;
        item.fill.style.width = barWidth(link?.score);
        item.adherence.textContent = fmtFixed(link?.adherence, 2);
        const lv = levelInfo(link?.level);
        item.score.className = `site-score ${lv.cls}`;
        item.status.textContent = lv.label;
        item.listed.hidden = !link?.listed_as_target;
        item.listed.title = t('Listado pela equipe como análogo {of}', { of: targetOf(target) });
        listbox.append(item.li);
      }

      // Rola até o selecionado antes de animar (offsetTop não depende da rolagem).
      if (state.analogId) items.get(state.analogId).li.scrollIntoView({ block: 'nearest' });

      if (animate) {
        // FLIP: cada item parte da posição antiga e desliza até a nova.
        for (const [id, { li }] of items) {
          const delta = before.get(id) - li.offsetTop;
          if (!delta) continue;
          li.style.transition = 'none';
          li.style.transform = `translateY(${delta}px)`;
        }
        listbox.getBoundingClientRect(); // força o layout com a posição antiga
        for (const { li } of items.values()) {
          li.style.transition = '';
          li.style.transform = '';
        }
      }
    }

    if (!prev || prev.analogId !== state.analogId) {
      for (const [id, { li }] of items) li.setAttribute('aria-selected', String(id === state.analogId));
      if (state.analogId && !targetChanged) items.get(state.analogId).li.scrollIntoView({ block: 'nearest' });
    }
  }

  listbox.addEventListener('keydown', (event) => {
    const ids = orderedIds(selection.state.targetId);
    const current = ids.indexOf(cursorId ?? selection.state.analogId);
    let next = null;
    switch (event.key) {
      case 'ArrowDown': next = ids[Math.min(current + 1, ids.length - 1)]; break;
      case 'ArrowUp': next = ids[Math.max(current - 1, 0)]; break;
      case 'Home': next = ids[0]; break;
      case 'End': next = ids[ids.length - 1]; break;
      case 'Enter':
      case ' ':
        if (cursorId) { selection.selectAnalog(cursorId); onPick?.(); }
        event.preventDefault();
        return;
      default: return; // Esc é tratado no documento (main.js)
    }
    event.preventDefault();
    setCursor(next);
    selection.setHover(next);
  });
  listbox.addEventListener('focus', () => {
    if (!cursorId) setCursor(selection.state.analogId ?? orderedIds(selection.state.targetId)[0]);
  });
  listbox.addEventListener('blur', () => selection.setHover(null));

  selection.subscribe(render);
  selection.subscribeHover((id) => {
    for (const [itemId, { li }] of items) li.classList.toggle('is-hover', itemId === id);
  });
  render(selection.state, null);

  return { focus: () => listbox.focus() };
}
