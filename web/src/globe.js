import * as THREE from 'three';

/**
 * Converte lat/lon (graus, planetocêntrico, lon positivo para leste, -180..180) em posição local no globo.
 * Com a SphereGeometry padrão e textura equiretangular centrada em lon 0, a longitude 0 fica no eixo +X.
 */
export function latLonToVector3(lat, lon, radius) {
  const φ = THREE.MathUtils.degToRad(lat);
  const λ = THREE.MathUtils.degToRad(lon);
  return new THREE.Vector3(
     radius * Math.cos(φ) * Math.cos(λ),
     radius * Math.sin(φ),
    -radius * Math.cos(φ) * Math.sin(λ)
  );
}

/** Tamanho dos marcadores em unidades da cena: igual nos três globos, para terem o mesmo tamanho na tela. */
export const MARKER_SIZE = 0.028;

export const MARKER_COLORS = {
  moon: 0x9fd3ff,   // alvo na Lua
  mars: 0xff7a45,   // alvo em Marte
  earth: 0x5dffa0,  // análogo na Terra
  debug: 0xff2bd6,  // pontos de teste de posição
};

const textureLoader = new THREE.TextureLoader();

/**
 * Cria um globo: um THREE.Group com a esfera texturizada e um subgrupo para os marcadores.
 * Girar o grupo gira esfera e marcadores juntos.
 */
export function createGlobe({ id, radius, texture, renderer }) {
  const group = new THREE.Group();
  group.name = id;
  group.userData = { id, radius };

  const map = textureLoader.load(texture);
  map.colorSpace = THREE.SRGBColorSpace;
  if (renderer) map.anisotropy = renderer.capabilities.getMaxAnisotropy();

  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(radius, 64, 64),
    new THREE.MeshStandardMaterial({ map, roughness: 1, metalness: 0 })
  );
  sphere.name = `${id}-sphere`;
  group.add(sphere);

  const markers = new THREE.Group();
  markers.name = `${id}-markers`;
  group.add(markers);

  group.userData.sphere = sphere;
  group.userData.markers = markers;
  return group;
}

const targetGeometry = new THREE.SphereGeometry(MARKER_SIZE, 16, 12);
const analogGeometry = new THREE.OctahedronGeometry(MARKER_SIZE * 1.25);
const debugGeometry = new THREE.TorusGeometry(MARKER_SIZE * 1.6, MARKER_SIZE * 0.35, 8, 24);

/**
 * Adiciona um marcador ao globo.
 * kind: 'target' (alvo na Lua/Marte), 'analog' (análogo na Terra) ou 'debug' (ponto de teste).
 * data: objeto do JSON (guardado em userData para a interação nas próximas fases).
 */
export function addMarker(globe, lat, lon, kind, data = {}) {
  const { radius, id: body } = globe.userData;
  const color =
    kind === 'debug' ? MARKER_COLORS.debug :
    kind === 'analog' ? MARKER_COLORS.earth :
    MARKER_COLORS[body];
  const geometry =
    kind === 'debug' ? debugGeometry :
    kind === 'analog' ? analogGeometry :
    targetGeometry;

  const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color, transparent: true }));
  const normal = latLonToVector3(lat, lon, 1);
  mesh.position.copy(normal).multiplyScalar(radius + MARKER_SIZE * 0.5);
  // Orienta o marcador para fora da superfície (o anel de teste fica deitado no chão).
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);
  mesh.name = data.id ?? `${kind}-${lat}-${lon}`;
  mesh.userData = { kind, body, lat, lon, ...data };

  globe.userData.markers.add(mesh);
  return mesh;
}

const ringGeometry = new THREE.RingGeometry(MARKER_SIZE * 2.1, MARKER_SIZE * 2.7, 40);

/** Anel de destaque do globo (um por globo, escondido até haver seleção). */
export function createRing(globe) {
  const ring = new THREE.Mesh(
    ringGeometry,
    new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide, transparent: true, opacity: 0.9 })
  );
  ring.name = `${globe.userData.id}-ring`;
  ring.visible = false;
  globe.add(ring);
  globe.userData.ring = ring;
  return ring;
}

/** Põe o anel do globo em volta de um marcador (ou o esconde, com marker = null). */
export function setRing(globe, marker) {
  const ring = globe.userData.ring;
  if (!ring) return;
  ring.visible = Boolean(marker);
  if (!marker) return;
  ring.position.copy(marker.position);
  ring.quaternion.copy(marker.quaternion);
}
