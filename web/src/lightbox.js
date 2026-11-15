import { el } from './dom.js';
import { t } from './i18n.js';

// Modal para ver a foto de um local ampliada. Usa <dialog> nativo (showModal): prende o foco, deixa o
// resto da página inerte e fecha com Esc. Fecha também pelo ✕ e com clique fora da imagem.

let dialog;

function ensureDialog() {
  if (dialog) return dialog;
  dialog = el('dialog', { class: 'lightbox', 'aria-label': t('Foto ampliada') });
  dialog.addEventListener('click', (event) => {
    // Clique no fundo (o próprio <dialog> ou a área vazia em volta da imagem) fecha.
    if (event.target === dialog || event.target.classList.contains('lightbox-stage')) dialog.close();
  });
  dialog.addEventListener('close', () => dialog.replaceChildren());
  document.body.append(dialog);
  return dialog;
}

/**
 * Abre a foto ampliada.
 * @param {object} image            analogs[].image
 * @param {string} title            nome do local
 * @param {(image: object) => Node} creditLine  linha de crédito (a mesma do card)
 */
export function openLightbox(image, title, creditLine) {
  const d = ensureDialog();
  const close = el('button', { type: 'button', class: 'icon-btn lightbox-close', 'aria-label': t('Fechar a foto'),
    onclick: () => d.close() }, '✕');
  d.replaceChildren(
    close,
    el('div', { class: 'lightbox-stage' }, el('img', { src: image.src, alt: image.alt, decoding: 'async' })),
    el('div', { class: 'lightbox-caption' },
      el('strong', {}, title), ' — ', image.caption,
      el('div', { class: 'photo-credit' }, creditLine(image))));
  d.showModal();
  close.focus();
}

export const isLightboxOpen = () => !!dialog?.open;
