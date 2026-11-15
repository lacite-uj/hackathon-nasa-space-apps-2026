// Criação de elementos sem innerHTML: os textos do JSON entram sempre como texto, nunca como HTML.

/**
 * el('li', { class: 'x', 'aria-selected': 'true', onclick: fn }, 'texto', outroElemento)
 * Atributos com valor null/undefined/false são ignorados; filhos nulos também.
 */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs ?? {})) {
    if (value == null || value === false) continue;
    if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
    else if (key === 'class') node.className = value;
    else if (key === 'style') node.style.cssText = value;
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
export const isMobile = () => window.matchMedia('(max-width: 767px)').matches;
