// Formatação pt-BR/en-US e rótulos. Aqui só se formata: nenhum número é recalculado (tudo vem do analogs.json).
// O idioma ativo (i18n.js) define o formato dos números (1,54 em pt-BR; 1.54 em en-US) e os rótulos.

import { locale, ordinal, t } from './i18n.js';

const formatters = new Map();
function nf(min, max) {
  const key = `${min}-${max}`;
  if (!formatters.has(key)) {
    formatters.set(key, new Intl.NumberFormat(locale, { minimumFractionDigits: min, maximumFractionDigits: max }));
  }
  return formatters.get(key);
}

export const A_MEDIR = t('a medir');

/** Nota com casas fixas (1.5385 → "1,54" em pt-BR, "1.54" em inglês); null/undefined → "a medir", nunca 0. */
export function fmtFixed(value, digits = 2) {
  return value == null ? A_MEDIR : nf(digits, digits).format(value);
}

/** Nota sem zeros à direita (2 → "2"; 0.6667 → "0,67" / "0.67"); null/undefined → "a medir". */
export function fmtNote(value) {
  return value == null ? A_MEDIR : nf(0, 2).format(value);
}

/** "1,54 / 3" ou "1.54 / 3"; sem nota, "a medir". */
export function fmtOutOf3(value, digits = 2) {
  return value == null ? A_MEDIR : `${fmtFixed(value, digits)} / 3`;
}

export function fmtNoteOutOf3(value) {
  return value == null ? A_MEDIR : `${fmtNote(value)} / 3`;
}

/** "1º de 14" em pt-BR; "1st of 14" em inglês. */
export function fmtRank(rank, total) {
  return rank == null ? A_MEDIR : t('{rank} de {total}', { rank: ordinal(rank), total });
}

/** Largura de uma barra a partir do score 0–1 do JSON (o trilho inteiro é a escala 0–3). */
export function barWidth(score) {
  if (score == null) return '0%';
  return `${Math.min(Math.max(score, 0), 1) * 100}%`;
}

export function plural(n, one, many) {
  return n === 1 ? one : many;
}

// Rótulos curtos por corpo celeste (o JSON traz o nome completo do alvo em targets[].name).
const BODY = {
  moon: { short: t('Lua'), of: t('da Lua') },
  mars: { short: t('Marte'), of: t('de Marte') },
};

export function targetShort(target) {
  return BODY[target?.body]?.short ?? target?.name ?? '';
}

/** "da Lua" / "de Marte". */
export function targetOf(target) {
  return BODY[target?.body]?.of ?? t('de {name}', { name: target?.name ?? '' });
}

/** ["lua","marte"] → "da Lua e de Marte" / "for the Moon and for Mars". */
export function targetsOf(ids, targetById) {
  return ids.map((id) => targetOf(targetById.get(id))).join(t(' e '));
}

// Níveis semânticos de aderência. O nível vem pronto do JSON (`level`, etl/config.py › nivel):
// ≥ 2 forte, ≤ 1 fraco, entre os dois parcial, null = a medir. Aqui só há rótulo e classe CSS.
// Os textos já saem traduzidos: quem exibe usa o valor direto.
export const LEVELS = {
  high: { cls: 'lv-high', label: t('Forte'), tag: t('Forte analogia'), range: t('2 a 3') },
  moderate: { cls: 'lv-moderate', label: t('Parcial'), tag: t('Analogia parcial'), range: t('entre 1 e 2') },
  low: { cls: 'lv-low', label: t('Fraca'), tag: t('Baixa aderência'), range: t('0 a 1') },
  none: { cls: 'lv-none', label: t('A medir'), tag: t('A medir'), range: t('sem dado') },
};

export function levelInfo(level) {
  return LEVELS[level] ?? LEVELS.none;
}

/** Valor de uma variável com a unidade: "−16 °C", "13 mm/ano", "3 (escala 0–3)". */
export function fmtValue(value, unit) {
  if (value == null) return A_MEDIR;
  const n = fmtNote(value);
  if (!unit) return n;
  if (isScale(unit)) return `${n} (${unit})`;
  if (unit === '%') return `${n}%`;
  return `${n} ${unit}`;
}

/** Unidade de escala: "escala 0–3" em pt-BR, "0–3 scale" em inglês (o texto vem do dicionário). */
const isScale = (unit) => /(?:^|\s)(escala|scale)\b/i.test(unit ?? '');

/** Faixas do critério: "nota 3 se ≤ −45 °C · 2 se ≤ −25 · 1 se ≤ −10" (null se não houver faixa útil). */
export function fmtThresholds(thresholds, direction, unit) {
  if (!thresholds || thresholds['3'] == null || isScale(unit)) return null;
  const op = direction === 'menor' ? '≤' : '≥';
  const u = unit && unit !== '%' ? ` ${unit}` : unit === '%' ? '%' : '';
  return t('nota 3 se {a} · 2 se {b} · 1 se {c}', {
    a: `${op} ${fmtNote(thresholds['3'])}${u}`,
    b: `${op} ${fmtNote(thresholds['2'])}`,
    c: `${op} ${fmtNote(thresholds['1'])}`,
  });
}

// Classe da fonte (vem pronta do JSON: source_index[id].kind e links[].sources[].kind; etl/config.py › FONTES_CLASSE).
export const SOURCE_KINDS = {
  nasa: { label: 'NASA', title: t('Documento, dado ou página oficial da NASA') },
  nasa_mission: { label: t('Missão NASA'), title: t('Artigo revisado por pares com dados de missão da NASA') },
  peer_reviewed: { label: t('Artigo revisado'), title: t('Artigo científico revisado por pares') },
  agency: { label: t('Órgão público'),
    title: t('Órgão público ou repositório científico (NPS, USGS, SGB, PANGAEA)') },
  team: { label: t('Planilha'), title: t('Planilha da equipe') },
};

export function sourceKind(kind) {
  return SOURCE_KINDS[kind] ?? null;
}
