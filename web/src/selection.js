// Estado único da seleção: { analogId, targetId }. Lista, card e cena assinam este módulo e nunca
// conversam entre si diretamente. As regras de sincronia estão na seção 5 do doc ("Sincronia").

/**
 * @param {{ analogs: object[], targets: object[], initialTarget: string }} opts
 */
export function createSelection({ analogs, targets, initialTarget }) {
  const analogById = new Map(analogs.map((a) => [a.id, a]));
  const targetIds = new Set(targets.map((t) => t.id));

  let state = { analogId: null, targetId: initialTarget };
  let hoverId = null;
  const subs = new Set();
  const hoverSubs = new Set();

  function set(patch) {
    const next = { ...state, ...patch };
    if (next.analogId === state.analogId && next.targetId === state.targetId) return;
    const prev = state;
    state = next;
    for (const fn of subs) fn(state, prev);
  }

  return {
    get state() { return state; },
    get hoverId() { return hoverId; },

    /** Clique num item da lista: o alvo não muda (o usuário já o escolheu no seletor). */
    selectAnalog(id) {
      if (analogById.has(id)) set({ analogId: id });
    },

    /** Clique num análogo no 3D: vai para o alvo em que a equipe o listou; listado nos dois = não muda. */
    selectAnalogFromScene(id) {
      const analog = analogById.get(id);
      if (!analog) return;
      const listed = (analog.listed_as ?? []).filter((t) => targetIds.has(t));
      set({ analogId: id, targetId: listed.length === 1 ? listed[0] : state.targetId });
    },

    /** Seletor da lista, aba do card ou clique num alvo no 3D. */
    setTarget(id) {
      if (targetIds.has(id)) set({ targetId: id });
    },

    /** Esc, ✕ ou clique no vazio. */
    clear() { set({ analogId: null }); },

    /** Destaque passageiro (mouse ou cursor do teclado); canal separado para não redesenhar lista e card. */
    setHover(id) {
      const next = id && analogById.has(id) ? id : null;
      if (next === hoverId) return;
      hoverId = next;
      for (const fn of hoverSubs) fn(hoverId);
    },

    subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },
    subscribeHover(fn) { hoverSubs.add(fn); return () => hoverSubs.delete(fn); },
  };
}
