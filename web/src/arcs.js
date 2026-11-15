import * as THREE from 'three';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';

// Arcos entre um marcador na Terra e um marcador no alvo. Hoje a cena mostra só o arco do link ativo,
// mas a camada recebe uma lista: para desenhar a rede inteira basta passar os 28 links em setLinks().

const SEGMENTS = 48;
export const ARC_WIDTH = { min: 1, max: 6 };       // px, para score 0 e score 1
export const ARC_COLORS = { weak: [107, 124, 153], strong: [255, 179, 71] }; // sRGB 0–255

// Cores dos níveis de aderência (iguais aos tokens --lv-* de styles.css). O nível vem do JSON.
export const LEVEL_COLORS = { high: '#4ade80', moderate: '#fbbf24', low: '#f87171', none: '#94a3b8' };
export const levelColor = (level) => LEVEL_COLORS[level] ?? LEVEL_COLORS.none;

/** Cor da rampa (cinza-azulado → amarelo-laranja) para um score 0–1, como string CSS. */
export function scoreColor(score) {
  const k = Math.min(Math.max(score ?? 0, 0), 1);
  const c = ARC_COLORS.weak.map((w, i) => Math.round(w + (ARC_COLORS.strong[i] - w) * k));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

export function scoreWidth(score) {
  const k = Math.min(Math.max(score ?? 0, 0), 1);
  return ARC_WIDTH.min + (ARC_WIDTH.max - ARC_WIDTH.min) * k;
}

const a = new THREE.Vector3();
const b = new THREE.Vector3();
const c1 = new THREE.Vector3();
const c2 = new THREE.Vector3();
const center = new THREE.Vector3();
const p = new THREE.Vector3();

/** Ponto do marcador e ponto de controle afastado da superfície (ao longo da normal), no mundo. */
function endpoint(marker, out, control, lift) {
  marker.getWorldPosition(out);
  marker.parent.parent.getWorldPosition(center); // marcador → grupo de marcadores → globo
  control.copy(out).sub(center).normalize().multiplyScalar(lift).add(out);
  control.y += lift * 0.9; // sobe um pouco, para o arco não virar uma reta quando visto de frente
}

function bezier(t, out) {
  const u = 1 - t;
  out.set(0, 0, 0)
    .addScaledVector(a, u * u * u)
    .addScaledVector(c1, 3 * u * u * t)
    .addScaledVector(c2, 3 * u * t * t)
    .addScaledVector(b, t * t * t);
}

export function createArcLayer(scene) {
  const group = new THREE.Group();
  group.name = 'arcs';
  scene.add(group);
  const resolution = new THREE.Vector2(1, 1);
  const pool = [];   // Line2 reaproveitados
  let active = [];   // { line, from, to }

  function makeLine() {
    const geometry = new LineGeometry();
    geometry.setPositions(new Float32Array((SEGMENTS + 1) * 3));
    const material = new LineMaterial({ color: 0xffffff, linewidth: 1, transparent: true, opacity: 0.95 });
    material.resolution.copy(resolution);
    const line = new Line2(geometry, material);
    line.frustumCulled = false; // as pontas mudam a cada frame; não vale recalcular a esfera envolvente
    group.add(line);
    return line;
  }

  return {
    /**
     * @param {{ score: number, from: THREE.Object3D, to: THREE.Object3D }[]} links
     *   from = marcador do análogo na Terra; to = marcador do alvo.
     */
    setLinks(links) {
      while (pool.length < links.length) pool.push(makeLine());
      active = links.map((link, i) => {
        const line = pool[i];
        line.visible = true;
        line.material.color.set(link.level !== undefined ? levelColor(link.level) : scoreColor(link.score));
        line.material.linewidth = scoreWidth(link.score);
        return { line, from: link.from, to: link.to };
      });
      for (let i = links.length; i < pool.length; i++) pool[i].visible = false;
      this.update();
    },

    /** Recalcula as pontas a partir da posição atual dos marcadores, escrevendo no buffer existente. */
    update() {
      for (const { line, from, to } of active) {
        from.getWorldPosition(a);
        to.getWorldPosition(b);
        const lift = a.distanceTo(b) * 0.35;
        endpoint(from, a, c1, lift);
        endpoint(to, b, c2, lift);
        const buffer = line.geometry.attributes.instanceStart.data; // [início xyz, fim xyz] por segmento
        const arr = buffer.array;
        bezier(0, p);
        for (let i = 0; i < SEGMENTS; i++) {
          arr[i * 6] = p.x; arr[i * 6 + 1] = p.y; arr[i * 6 + 2] = p.z;
          bezier((i + 1) / SEGMENTS, p);
          arr[i * 6 + 3] = p.x; arr[i * 6 + 4] = p.y; arr[i * 6 + 5] = p.z;
        }
        buffer.needsUpdate = true;
      }
    },

    /** Tamanho do canvas em px de CSS; o LineMaterial precisa dele para a largura em pixels. */
    setResolution(width, height) {
      resolution.set(width, height);
      for (const line of pool) line.material.resolution.copy(resolution);
    },
  };
}
