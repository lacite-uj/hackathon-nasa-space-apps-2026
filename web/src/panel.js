import { el } from './dom.js';
import { openLightbox } from './lightbox.js';
import {
  A_MEDIR, barWidth, fmtNoteOutOf3, fmtOutOf3, fmtRank, fmtThresholds, fmtValue, levelInfo, plural, targetOf,
  targetShort, targetsOf, sourceKind,
} from './format.js';
import { t } from './i18n.js';

// Card de detalhes do local selecionado (direita; gaveta no celular). Não é modal.
// O cabeçalho e as abas são criados uma vez; só o corpo é refeito a cada mudança de seleção.
// Textos visíveis passam por t() (i18n.js); o que vem do analogs.json já chega traduzido.

/**
 * @param {object} opts
 * @param {HTMLElement} opts.root   #panel
 * @param {object} opts.data        analogs.json
 * @param {(analogId: string, targetId: string) => object | undefined} opts.linkOf
 * @param {ReturnType<import('./selection.js').createSelection>} opts.selection
 * @param {() => void} [opts.onLayout]  o card abriu, fechou ou mudou de tamanho
 */
export function createPanel({ root, data, linkOf, selection, onLayout }) {
  const analogById = new Map(data.analogs.map((a) => [a.id, a]));
  const targetById = new Map(data.targets.map((tgt) => [tgt.id, tgt]));
  const total = data.analogs.length;
  // Seções recolhíveis: lembram se o usuário abriu, mesmo trocando de local ou de aba.
  const open = { utilities: false, sources: false };
  // Pontos fortes/fracos abertos pelo usuário (`strength:U06`): continuam abertos ao trocar de aba ou de local.
  const openPoints = new Set();

  const title = el('h2', { id: 'panel-title' });
  const subtitle = el('p', { class: 'card-sub' });
  const approx = el('p', { class: 'card-approx', hidden: true },
    t('≈ Coordenada aproximada: o ponto no globo é só indicativo.'));
  const expand = el('button', { type: 'button', class: 'icon-btn card-expand', 'aria-expanded': 'false',
    onclick: () => {
      const expanded = root.classList.toggle('is-expanded');
      expand.setAttribute('aria-expanded', String(expanded));
      expand.textContent = expanded ? '▾' : '▴';
      expand.setAttribute('aria-label', expanded ? t('Recolher o card') : t('Expandir o card'));
    } }, '▴');
  expand.setAttribute('aria-label', t('Expandir o card'));
  const close = el('button', { type: 'button', class: 'icon-btn', 'aria-label': t('Fechar o card'),
    onclick: () => selection.clear() }, '✕');

  const tabs = new Map();
  const tablist = el('div', { class: 'tabs', role: 'tablist', 'aria-label': t('Alvo da comparação') },
    data.targets.map((tgt) => {
      const badge = el('span', { class: 'tag tag-listed', hidden: true }, t('listado'));
      const tab = el('button', { type: 'button', role: 'tab', class: 'tab', id: `tab-${tgt.id}`,
        'aria-controls': 'panel-body', 'aria-selected': 'false',
        onclick: () => selection.setTarget(tgt.id) }, targetShort(tgt), ' ', badge);
      tabs.set(tgt.id, { tab, badge });
      return tab;
    }));
  tablist.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    const ids = data.targets.map((tgt) => tgt.id);
    const step = event.key === 'ArrowRight' ? 1 : -1;
    const next = ids[(ids.indexOf(selection.state.targetId) + step + ids.length) % ids.length];
    selection.setTarget(next);
    tabs.get(next).tab.focus();
    event.preventDefault();
  });

  const body = el('div', { class: 'card-body', id: 'panel-body', role: 'tabpanel', tabindex: '0' });

  root.removeAttribute('aria-live');
  root.setAttribute('aria-labelledby', 'panel-title');
  root.hidden = true;
  const photo = el('figure', { class: 'card-photo', hidden: true });
  root.replaceChildren(
    photo,
    el('div', { class: 'card-head' },
      el('div', { class: 'card-title' }, title, subtitle, approx),
      el('div', { class: 'card-actions' }, expand, close)),
    tablist, body);

  const section = (heading, attrs, ...children) =>
    el('section', { class: 'sec', ...attrs }, el('h3', {}, heading), ...children);

  /** Uma linha "rótulo · barra · nota · N de M utilidades"; categoria ausente = "a medir". */
  function dimensionRow(dim, value) {
    return el('div', { class: `dim ${levelInfo(value?.level).cls}${value ? '' : ' is-unmeasured'}` },
      el('span', { class: 'dim-label' }, dim.label),
      el('span', { class: 'bar', 'aria-hidden': 'true' }, el('span', { class: 'bar-fill', style: `width:${barWidth(value?.score)}` })),
      el('span', { class: 'dim-note lv-text' }, value ? fmtOutOf3(value.adherence) : A_MEDIR),
      el('span', { class: 'dim-count' },
        value ? t('{n} de {total} {word}', { n: value.evaluated, total: value.total,
          word: t(plural(value.total, 'utilidade', 'utilidades')) }) : t('nenhuma utilidade avaliada')));
  }

  function utilityRow(u) {
    const measured = u.adherence != null && u.status !== 'a_medir';
    return el('li', { class: `util ${levelInfo(u.level).cls}${measured ? '' : ' is-unmeasured'}` },
      el('div', { class: 'util-line' },
        el('span', { class: 'util-id' }, u.id),
        el('span', { class: 'util-name' }, u.name),
        u.best_in_network ? el('span', { class: 'tag tag-best' }, t('melhor da rede')) : null,
        el('span', { class: 'util-note lv-text' }, measured ? fmtNoteOutOf3(u.adherence) : A_MEDIR)),
      u.reading
        ? el('p', { class: 'util-reading' },
            el('span', { class: 'util-reading-label' }, t('Leitura da equipe para esta utilidade (base v1.1): ')), u.reading)
        : null);
  }

  const sourceIndex = data.source_index ?? {};

  /** Chip de fonte: id + referência, com link quando existe. `compact` mostra só o id (referência no title). */
  function sourceChip(id, compact = false) {
    const src = sourceIndex[id];
    const label = compact || !src ? id : `${id} · ${src.label}`;
    const cls = `src-chip${compact ? ' is-compact' : ''}`;
    const kind = sourceKind(src?.kind);
    const title = [src?.label, kind?.label].filter(Boolean).join(' · ');
    return src?.url
      ? el('a', { class: cls, href: src.url, target: '_blank', rel: 'noopener', title }, label)
      : el('span', { class: cls, title }, label);
  }

  /** Uma variável que decidiu a nota: valor no local, nota, faixas, valor no alvo, fontes e dataset. */
  function evidenceRow(e, target) {
    const measured = e.value != null;
    const thresholds = fmtThresholds(e.thresholds, e.direction, e.unit);
    const datasets = [e.dataset_earth && t('Terra: {v}', { v: e.dataset_earth }),
      e.dataset_target && `${targetShort(target)}: ${e.dataset_target}`].filter(Boolean).join(' · ');
    return el('li', { class: `ev ${levelInfo(e.level).cls}` },
      el('div', { class: 'ev-line' },
        el('span', { class: 'ev-var' }, e.variable),
        el('span', { class: 'ev-val' }, measured ? fmtValue(e.value, e.unit) : (e.value_note || A_MEDIR)),
        e.note != null ? el('span', { class: 'ev-note lv-text' }, t('nota {n}', { n: e.note })) : el('span', { class: 'ev-note' },
          e.status === 'sem_faixas' ? t('sem faixa') : A_MEDIR)),
      e.target_value && e.target_value !== '—' ? el('div', { class: 'ev-sub' }, t('No alvo: {v}', { v: e.target_value })) : null,
      thresholds ? el('div', { class: 'ev-sub' }, thresholds) : null,
      e.observation ? el('div', { class: 'ev-sub' }, e.observation) : null,
      // Nos lotes a fonte é a do local; na base, o Catálogo cita fontes por variável (valem para os 3 locais
      // da base), então elas aparecem só pelo id, com a referência no title.
      e.sources?.length
        ? el('div', { class: 'ev-src' },
            el('span', { class: 'ev-k' }, e.sources_scope === 'catalogo'
              ? t('Fontes da variável no Catálogo da base (não só deste local):')
              : t(plural(e.sources.length, 'Fonte:', 'Fontes:'))),
            e.sources.map((id) => sourceChip(id, e.sources_scope === 'catalogo')))
        : null,
      datasets ? el('div', { class: 'ev-sub ev-ds' }, t('Dataset de referência — {v}', { v: datasets })) : null);
  }

  /** Card de um ponto forte ou fraco: nota, o que mede, por que essa nota aqui e de onde vem o dado. */
  function pointCard(pt, utilById, target, side) {
    if (pt.kind === 'reading') {
      return el('div', { class: `point-card is-reading is-${side}` },
        el('div', { class: 'point-head' }, el('span', { class: 'point-title' },
          t('Leitura da equipe — {label}', { label: pt.label }))),
        el('p', {}, pt.text));
    }
    const u = utilById.get(pt.id);
    const lv = levelInfo(pt.level);
    const m = u?.meaning ?? {};
    // Só as variáveis com nota explicam a nota; as que ainda faltam aparecem resumidas.
    const evidence = (u?.evidence ?? []).filter((e) => e.note != null);
    const missing = (u?.evidence ?? []).filter((e) => e.note == null).map((e) => e.variable);
    // Recolhível: o resumo (título, critério curto e nota) fica sempre à vista; o detalhe abre no clique.
    const key = `${side}:${pt.id}`;
    const card = el('details', { class: `point-card is-${side} ${lv.cls}`, open: openPoints.has(key) },
      el('summary', { class: 'point-head' },
        el('span', { class: 'point-chevron', 'aria-hidden': 'true' }),
        el('span', { class: 'point-heading' },
          el('span', { class: 'point-title' }, pt.name),
          el('span', { class: 'point-sub' }, m.purpose && m.purpose !== pt.name ? m.purpose : pt.id)),
        el('span', { class: 'tag tag-status point-score' }, fmtNoteOutOf3(pt.adherence),
          el('span', { class: 'sr-only' }, ` (${lv.label.toLowerCase()})`))),
      el('div', { class: 'point-body' },
        el('section', { class: 'point-block' },
          el('h4', {}, t('O que mede')),
          m.condition ? el('p', {}, el('span', { class: 'point-k' }, t('Em {target}: ', { target: targetShort(target) })),
            m.condition) : null,
          m.criterion ? el('p', {}, el('span', { class: 'point-k' }, t('Critério: ')), m.criterion) : null),
        el('section', { class: 'point-block' },
          el('h4', {}, t('Por que essa nota aqui')),
          evidence.length ? el('ul', { class: 'evidence' }, evidence.map((e) => evidenceRow(e, target)))
            : el('p', { class: 'muted' }, t('Sem variável medida.')),
          missing.length ? el('p', { class: 'muted ev-missing' },
            t('Ainda a medir: {list}.', { list: missing.join('; ') })) : null,
          u?.reading ? el('p', { class: 'util-reading' },
            el('span', { class: 'util-reading-label' }, t('Leitura da equipe (base v1.1): ')), u.reading) : null)));
    card.addEventListener('toggle', () => { if (card.open) openPoints.add(key); else openPoints.delete(key); });
    return card;
  }

  /** Bloco de pontos (fortes ou fracos) com o botão "expandir todos / recolher todos". */
  function pointsSection(title, cls, points, utilById, target, side, empty) {
    const cards = points.map((pt) => pointCard(pt, utilById, target, side));
    const details = cards.filter((c) => c.tagName === 'DETAILS');
    const toggle = details.length > 1
      ? el('button', { type: 'button', class: 'link-btn points-toggle', onclick: () => {
          const openAll = !details.every((d) => d.open);
          for (const d of details) d.open = openAll;
          toggle.textContent = openAll ? t('Recolher todos') : t('Expandir todos');
        } }, details.every((d) => d.open) ? t('Recolher todos') : t('Expandir todos'))
      : null;
    return el('section', { class: `sec points ${cls}` },
      el('div', { class: 'points-head' },
        el('h3', {}, title, ' ', el('span', { class: 'count' }, String(details.length))), toggle),
      cards.length ? el('div', { class: 'point-list' }, cards) : el('p', { class: 'muted' }, empty));
  }

  function renderBody(analog, target, link) {
    const parts = [];

    // Aviso discreto quando o card está num alvo em que a equipe não listou o local.
    const listed = (analog.listed_as ?? []).filter((id) => targetById.has(id));
    if (!link.listed_as_target && listed.length) {
      parts.push(el('p', { class: 'listed-elsewhere' },
        t('A equipe listou este local como análogo {of}. ', { of: targetsOf(listed, targetById) }),
        listed.map((id) => el('button', { type: 'button', class: 'link-btn', onclick: () => selection.setTarget(id) },
          t('Ver {target}', { target: targetShort(targetById.get(id)) })))));
    }

    // 1. Veredito: nota com a cor do nível, selo e posição na rede.
    const best = data.links.find((l) => l.target === target.id && l.rank === 1);
    const bestAnalog = best ? analogById.get(best.analog) : null;
    const n = link.best_in_network_count;
    const lv = levelInfo(link.level);
    parts.push(section(t('Veredito para {name}', { name: target.name }), { class: `sec verdict ${lv.cls}` },
      el('div', { class: 'verdict-row' },
        el('div', { class: 'verdict-main' },
          el('span', { class: 'verdict-value lv-text' }, fmtOutOf3(link.adherence)),
          el('span', { class: 'verdict-cap' }, t('aderência'))),
        el('div', { class: 'verdict-main' },
          el('span', { class: 'verdict-value' }, fmtRank(link.rank, total)),
          el('span', { class: 'verdict-cap' }, t('posição na rede'))),
        el('span', { class: `tag tag-status ${lv.cls}` }, lv.tag)),
      el('span', { class: `bar bar-lg ${lv.cls}`, 'aria-hidden': 'true' }, el('span', { class: 'bar-fill', style: `width:${barWidth(link.score)}` })),
      link.rank_tied
        ? el('p', { class: 'muted' },
            t('Empate: outro local tem a mesma aderência para este alvo; a ordem entre eles segue a da planilha.'))
        : null,
      n ? el('p', {}, t('Melhor da rede em {n} {word}.', { n, word: t(plural(n, 'utilidade', 'utilidades')) })) : null,
      best && bestAnalog
        ? el('p', { class: 'muted' },
            t('Para referência: a escala vai de 0 a 3 e o 1º colocado para {target} ({name}) tem {value}.',
              { target: targetShort(target), name: bestAnalog.name, value: fmtOutOf3(best.adherence) }))
        : null));

    // 2. Por que é análogo: parágrafo curado (etl/config.py › NARRATIVAS) ou a justificativa da planilha.
    parts.push(section(t('Por que é análogo'), {},
      el('p', { class: 'narrative' }, analog.narrative || analog.description || ''),
      analog.narrative && analog.description
        ? el('p', { class: 'kv' }, el('span', { class: 'k' }, t('Na planilha: ')), analog.description) : null,
      analog.clipping ? el('p', { class: 'kv' }, el('span', { class: 'k' }, t('Recorte usado: ')), analog.clipping) : null,
      analog.data_notes ? el('p', { class: 'kv' }, el('span', { class: 'k' }, t('Sobre os dados: ')), analog.data_notes) : null));

    // 3. Pontos fortes e 4. onde a analogia falha (sempre aberta): um card explicativo por ponto.
    const utilById = new Map((link.utilities ?? []).map((u) => [u.id, u]));
    parts.push(pointsSection(t('Pontos fortes da analogia'), 'points-strength', link.strengths ?? [], utilById, target,
      'strength', t('Nenhuma utilidade com nota ≥ 2 para este alvo.')));
    // "Onde a analogia falha" nunca some: o bloco fica sempre aberto e mostra o título e a nota de cada falha.
    parts.push(pointsSection(t('Onde a analogia falha'), 'points-limit limits', link.limits ?? [], utilById, target,
      'limit', t('Nenhuma falha registrada.')));

    // 5. Ainda a medir
    if (link.to_measure?.length) {
      parts.push(section(t('Ainda a medir'), {},
        el('ul', { class: 'chips' }, link.to_measure.map((item) => el('li', { class: 'chip-measure' }, item))),
        el('p', { class: 'muted' }, t('Sem dado ainda: não entram na média e não valem zero.'))));
    }

    // 6. Por categoria
    const inScore = data.dimensions.filter((d) => d.in_score);
    const outOfScore = data.dimensions.filter((d) => !d.in_score);
    parts.push(section(t('Desempenho por categoria'), {},
      el('div', { class: 'dims' }, inScore.map((d) => dimensionRow(d, link.dimensions?.[d.id]))),
      outOfScore.length
        ? el('div', { class: 'dims dims-out' },
            el('p', { class: 'dims-out-title' }, t('Fora da nota')),
            outOfScore.map((d) => dimensionRow(d, link.dimensions?.[d.id])),
            el('p', { class: 'muted' }, t('Não entra na aderência: vale para qualquer lugar da Terra.')))
        : null));

    // 7. Uso na exploração
    if (link.exploration_use) parts.push(section(t('Uso na exploração'), {}, el('p', {}, link.exploration_use)));

    // 8. Utilidades, agrupadas por categoria (auditoria completa)
    const groups = data.dimensions
      .map((d) => ({ dim: d, utils: (link.utilities ?? []).filter((u) => u.category === d.id) }))
      .filter((g) => g.utils.length);
    const utilities = el('details', { class: 'sec fold', open: open.utilities },
      el('summary', {}, el('h3', {}, t('Utilidades')), el('span', { class: 'count' }, String(link.utilities?.length ?? 0))),
      groups.map((g) => el('div', { class: 'util-group' },
        el('h4', {}, g.dim.label, g.dim.in_score ? null : el('span', { class: 'tag' }, t('fora da nota'))),
        el('ul', { class: 'utils' }, g.utils.map(utilityRow)))));
    utilities.addEventListener('toggle', () => { open.utilities = utilities.open; });
    parts.push(utilities);

    // 9. Fontes gerais
    const sources = el('details', { class: 'sec fold', open: open.sources },
      el('summary', {}, el('h3', {}, t('Fontes dos dados deste local')),
        el('span', { class: 'count' }, String(link.sources?.length ?? 0))),
      el('ul', { class: 'sources' }, (link.sources ?? []).map((s) =>
        el('li', {}, el('span', { class: 'src-id' }, s.id), ' ',
          el('a', { href: s.url, target: '_blank', rel: 'noopener' }, s.label),
          sourceKind(s.kind) ? el('span', { class: `src-kind kind-${s.kind}`, title: sourceKind(s.kind).title },
            sourceKind(s.kind).label) : null))));
    sources.addEventListener('toggle', () => { open.sources = sources.open; });
    parts.push(sources);

    body.replaceChildren(...parts);
  }

  /** Foto do local (analogs[].image) no topo do card; sem imagem ou com erro de carga, o card segue sem ela. */
  function renderPhoto(analog) {
    const img = analog.image;
    if (!img) { photo.hidden = true; photo.replaceChildren(); return; }
    const picture = el('img', { src: img.src, alt: img.alt, decoding: 'async', width: '1200', height: '800',
      onerror: () => { photo.hidden = true; } });
    const name = analog.full_name ?? analog.name;
    photo.replaceChildren(
      el('button', { type: 'button', class: 'photo-open', 'aria-label': t('Ampliar a foto: {caption}', { caption: img.caption }),
        title: t('Ampliar a foto'), onclick: () => openLightbox(img, name, creditLine) },
        picture, el('span', { class: 'photo-zoom', 'aria-hidden': 'true' }, '⤢')),
      img.kind === 'satelite' ? el('span', { class: 'photo-kind' }, t('Imagem de satélite')) : null,
      el('figcaption', {},
        el('span', { class: 'photo-caption' }, img.caption),
        el('span', { class: 'photo-credit' }, creditLine(img))));
    photo.hidden = false;
  }

  /** "Foto: autor · licença · fonte", com links; usada no card e no modal. */
  function creditLine(img) {
    const { author, license, license_url: licenseUrl, source_url: sourceUrl } = img.credit;
    const ext = (href, text) => el('a', { href, target: '_blank', rel: 'noopener' }, text);
    const frag = document.createDocumentFragment();
    frag.append(img.kind === 'satelite' ? t('Imagem: ') : t('Foto: '), author, ' · ',
      licenseUrl ? ext(licenseUrl, license) : license, ' · ', ext(sourceUrl, t('fonte')));
    return frag;
  }

  function render(state, prev) {
    const analog = state.analogId ? analogById.get(state.analogId) : null;
    const wasHidden = root.hidden;
    if (!analog) {
      root.hidden = true;
      body.replaceChildren();
      if (!wasHidden) onLayout?.();
      return;
    }
    const target = targetById.get(state.targetId);
    const link = linkOf(analog.id, target.id);

    if (!prev || prev.analogId !== state.analogId) renderPhoto(analog);
    title.textContent = analog.full_name ?? analog.name;
    subtitle.textContent = [analog.country, analog.batch].filter(Boolean).join(' · ');
    approx.hidden = !analog.approximate_coords;
    for (const [id, { tab, badge }] of tabs) {
      const selected = id === state.targetId;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      badge.hidden = !(analog.listed_as ?? []).includes(id);
      badge.title = t('Listado pela equipe como análogo {of}', { of: targetOf(targetById.get(id)) });
    }
    body.setAttribute('aria-labelledby', `tab-${state.targetId}`);

    if (link) renderBody(analog, target, link);
    else body.replaceChildren(el('p', { class: 'muted' },
      t('Sem ligação com {name} nos dados: {v}.', { name: target.name, v: A_MEDIR })));
    if (!prev || prev.analogId !== state.analogId || prev.targetId !== state.targetId) body.scrollTop = 0;

    root.hidden = false;
    if (wasHidden) onLayout?.();
  }

  selection.subscribe(render);
  render(selection.state, null);
  return { root };
}
