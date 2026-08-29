"use client";

// 3D visualization of the CANONICAL 2D design — trust view only, never
// manufacturing truth. The backend serves the real vector polygons plus
// physical parameters (thickness, mm dimensions, ring bend radius); this
// component extrudes them client-side with Three.js. Nothing rendered
// here can flow back into geometry.

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

interface PolyRing {
  exterior: number[][];
  holes: number[][][];
}

export interface Mesh3DPayload {
  units: string;
  disclaimer: string;
  product_type: string;
  width_mm: number;
  height_mm: number;
  thickness_mm: number;
  polygons: PolyRing[];
  engrave_polygons: PolyRing[];
  inner_engrave_polygons?: PolyRing[];
  ring: {
    size_eu: number;
    band_height_mm: number;
    inner_radius_mm: number;
    length_mm: number;
  } | null;
  weight_estimate_g: Record<string, number>;
}

const MATERIAL_COLORS: Record<string, { color: number; metalness: number; roughness: number }> = {
  "silver-925": { color: 0xd7d7dc, metalness: 1.0, roughness: 0.28 },
  "gold-18k-yellow": { color: 0xdfb95e, metalness: 1.0, roughness: 0.25 },
  "gold-18k-rose": { color: 0xd99a7c, metalness: 1.0, roughness: 0.25 },
  "gold-18k-white": { color: 0xdcdcda, metalness: 1.0, roughness: 0.22 },
  platinum: { color: 0xc9cbcc, metalness: 1.0, roughness: 0.2 },
};

function toShapes(polys: PolyRing[]): THREE.Shape[] {
  return polys.map((poly) => {
    const shape = new THREE.Shape(
      poly.exterior.map(([x, y]) => new THREE.Vector2(x, y))
    );
    for (const hole of poly.holes) {
      shape.holes.push(
        new THREE.Path(hole.map(([x, y]) => new THREE.Vector2(x, y)))
      );
    }
    return shape;
  });
}

// Wrap a flat band strip (built along +X) around a cylinder of radius r:
// x becomes the arc coordinate. Engraving sits at a slightly larger radius
// so it reads on the outer face.
function bendAroundCylinder(geometry: THREE.BufferGeometry, r: number, length: number) {
  const pos = geometry.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i);
    const y = pos.getY(i);
    const z = pos.getZ(i); // extrusion depth 0..thickness
    const theta = ((x - length / 2) / r) * -1;
    const radius = r + z;
    pos.setXYZ(i, radius * Math.sin(theta), y, radius * Math.cos(theta));
  }
  pos.needsUpdate = true;
  geometry.computeVertexNormals();
}

export default function Viewer3D({
  payload,
  material,
}: {
  payload: Mesh3DPayload;
  material: string;
}) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setFailed(true); // WebGL unavailable — the 2D proof remains authoritative
      return;
    }
    const width = mount.clientWidth || 320;
    const height = 320;
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 2000);
    const spec = MATERIAL_COLORS[material] ?? MATERIAL_COLORS["silver-925"];
    const metal = new THREE.MeshStandardMaterial({ ...spec, side: THREE.DoubleSide });
    const engraveMat = new THREE.MeshStandardMaterial({
      color: 0x3a3a3a,
      metalness: 0.6,
      roughness: 0.7,
      side: THREE.DoubleSide,
    });

    const group = new THREE.Group();
    const thickness = payload.thickness_mm;
    const bodyGeoms = toShapes(payload.polygons).map(
      (s) =>
        new THREE.ExtrudeGeometry(s, {
          depth: thickness,
          bevelEnabled: false,
          curveSegments: 10,
        })
    );

    if (payload.ring) {
      const r = payload.ring.inner_radius_mm;
      const L = payload.ring.length_mm;
      for (const g of bodyGeoms) bendAroundCylinder(g, r, L);
      const engraveGeoms = toShapes(payload.engrave_polygons).map(
        (s) =>
          new THREE.ExtrudeGeometry(s, {
            depth: 0.08,
            bevelEnabled: false,
            curveSegments: 8,
          })
      );
      for (const g of engraveGeoms) {
        // Sit the marks just above the outer surface of the bent band.
        g.translate(0, 0, thickness + 0.01);
        bendAroundCylinder(g, r, L);
        group.add(new THREE.Mesh(g, engraveMat));
      }
      // Inner-face engraving (already mirrored in the flat pattern):
      // just inside the inner surface, facing into the ring.
      const innerGeoms = toShapes(payload.inner_engrave_polygons ?? []).map(
        (s) =>
          new THREE.ExtrudeGeometry(s, {
            depth: 0.08,
            bevelEnabled: false,
            curveSegments: 8,
          })
      );
      for (const g of innerGeoms) {
        g.translate(0, 0, -0.09);
        bendAroundCylinder(g, r, L);
        group.add(new THREE.Mesh(g, engraveMat));
      }
    }
    for (const g of bodyGeoms) group.add(new THREE.Mesh(g, metal));

    // Center the piece and frame the camera on its real size.
    const box = new THREE.Box3().setFromObject(group);
    const center = box.getCenter(new THREE.Vector3());
    group.position.sub(center);
    scene.add(group);
    const size = box.getSize(new THREE.Vector3()).length();
    camera.position.set(0, size * 0.15, size * 1.1);

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(40, 60, 80);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xfff2dd, 0.8);
    rim.position.set(-50, -20, -60);
    scene.add(rim);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.autoRotate = true; // 360° presentation by default
    controls.autoRotateSpeed = 2.0;

    let frame = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(frame);
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, [payload, material]);

  if (failed) return null;
  return <div ref={mountRef} data-testid="viewer3d-canvas" className="w-full" />;
}
