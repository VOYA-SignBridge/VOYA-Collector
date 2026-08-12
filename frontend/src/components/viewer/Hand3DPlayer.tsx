import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import {
  handDepth,
  handLayout,
  handPoints,
  handWidth,
  HAND_CONNECTIONS,
  LEFT_COLOR,
  RIGHT_COLOR,
  type FramesData,
  type HandSide,
} from "./handData";

/**
 * Tier 1: "flesh" 3D hands.
 *
 * We have 21 landmark POSITIONS per hand per frame (not joint rotations), so
 * instead of retargeting onto a rigged mesh (an IK problem the data can't
 * support faithfully), each hand is BUILT from the positions themselves:
 * skin-toned spheres at the joints + capsule-like segments between them.
 * Everything on screen is real recorded data — nothing is inferred.
 *
 * The render loop reads `frameRef` (not React state) so the 60fps orbit/render
 * cycle never re-renders React; `onFps` feeds the tier monitor that detects
 * thermal throttling as a sustained fps drop.
 */

const WORLD_SIZE = 1.6;
const SKIN_COLOR = 0xe0ac8b;
const BG_COLOR = 0x0c161e;

interface Hand3DPlayerProps {
  data: FramesData;
  frameRef: React.MutableRefObject<number>;
  onFps?: () => void;
}

interface HandRig {
  group: THREE.Group;
  joints: THREE.Mesh[];
  bones: THREE.Mesh[];
  marker: THREE.Mesh;
}

function buildHandRig(
  scene: THREE.Scene,
  accentColor: string,
  sphereGeo: THREE.SphereGeometry,
  boneGeo: THREE.CylinderGeometry,
  skinMat: THREE.MeshStandardMaterial,
): HandRig {
  const group = new THREE.Group();

  const joints: THREE.Mesh[] = [];
  for (let i = 0; i < 21; i++) {
    const mesh = new THREE.Mesh(sphereGeo, skinMat);
    // Wrist biggest, knuckles medium, fingertips smallest — reads as flesh.
    const r = i === 0 ? 2.0 : i % 4 === 0 ? 1.0 : 1.3;
    mesh.scale.setScalar(r);
    mesh.castShadow = true;
    group.add(mesh);
    joints.push(mesh);
  }

  const bones: THREE.Mesh[] = [];
  for (let c = 0; c < HAND_CONNECTIONS.length; c++) {
    const mesh = new THREE.Mesh(boneGeo, skinMat);
    mesh.castShadow = true;
    group.add(mesh);
    bones.push(mesh);
  }

  // Colored wrist marker so reviewers can tell left from right at a glance.
  //
  // It hangs off `group`, NOT off joints[0]: the wrist joint carries
  // scale.setScalar(2.0), and a child inherits its parent's scale, so the
  // marker rendered at r=0.07 — nearly twice the wrist it was meant to label,
  // and the offset doubled with it. That is the oversized ball in the 3D view.
  const marker = new THREE.Mesh(
    new THREE.SphereGeometry(0.035, 16, 12),
    new THREE.MeshStandardMaterial({ color: new THREE.Color(accentColor), roughness: 0.4 }),
  );
  group.add(marker);

  scene.add(group);
  return { group, joints, bones, marker };
}

export default function Hand3DPlayer({ data, frameRef, onFps }: Hand3DPlayerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const onFpsRef = useRef(onFps);
  onFpsRef.current = onFps;

  // Same per-sample decision the 2D player makes: wrist-centred recordings put
  // both wrists on the origin and get one half of the world each; recordings
  // that kept image coordinates already hold the hands apart correctly and are
  // drawn with a single shared fit so their real distance and relative size
  // survive.
  const layout = useMemo(() => handLayout(data.sequence), [data]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(BG_COLOR);

    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 20);
    camera.position.set(0, 0.25, 2.7);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);
    renderer.domElement.classList.add("w-full", "h-full", "rounded-t-2xl");

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 1.2;
    controls.maxDistance = 6;

    // Lighting: soft ambient + one shadow-casting key light.
    scene.add(new THREE.HemisphereLight(0xdfeaff, 0x1a2433, 0.9));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(1.5, 2.5, 2);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    scene.add(key);

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(8, 8),
      new THREE.ShadowMaterial({ opacity: 0.35 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -WORLD_SIZE / 2 - 0.05;
    ground.receiveShadow = true;
    scene.add(ground);

    const grid = new THREE.GridHelper(8, 24, 0x24405a, 0x16283a);
    grid.position.y = ground.position.y + 0.001;
    scene.add(grid);

    // Shared geometry/material — 2 hands × (21 joints + 21 bones) is tiny.
    const sphereGeo = new THREE.SphereGeometry(0.018, 20, 16);
    const boneGeo = new THREE.CylinderGeometry(0.014, 0.017, 1, 10);
    const skinMat = new THREE.MeshStandardMaterial({
      color: SKIN_COLOR,
      roughness: 0.55,
      metalness: 0.05,
    });

    const rigs: Record<HandSide, HandRig> = {
      left: buildHandRig(scene, LEFT_COLOR, sphereGeo, boneGeo, skinMat),
      right: buildHandRig(scene, RIGHT_COLOR, sphereGeo, boneGeo, skinMat),
    };

    const worldPos: THREE.Vector3[] = Array.from({ length: 21 }, () => new THREE.Vector3());
    const tmpDir = new THREE.Vector3();
    const yAxis = new THREE.Vector3(0, 1, 0);

    const applyFrame = (index: number) => {
      const row = data.sequence[index];
      if (!row) return;

      (["left", "right"] as HandSide[]).forEach((side) => {
        const rig = rigs[side];
        const pts = handPoints(row, side);
        rig.group.visible = !!pts;
        if (!pts) return;

        const fit = layout[side];
        // Metric depth when the recording has it. `depth.scale` converts metres
        // into hand-widths, and multiplying by the hand's on-screen width puts
        // it in the same units as the x,y the 2D fit produced — so the depth
        // drawn is the proportion that was recorded, not a guess.
        const depth = handDepth(data.sequence_world?.[index], side);
        const onScreenWidth = handWidth(pts, fit);
        for (let i = 0; i < 21; i++) {
          const [ux, uy] = fit.toUnit(pts[i * 3], pts[i * 3 + 1]);
          worldPos[i].set(
            (ux - 0.5) * WORLD_SIZE,
            (0.5 - uy) * WORLD_SIZE, // image y points down; world y points up
            // Same scale as x and y — the hand keeps its real proportions.
            // A stray *0.5 here squashed depth to half of width, on top of the
            // flattening the stored data already had, which is what made the
            // 3D hands look like cardboard cut-outs.
            depth
              ? -depth.z[i] * depth.scale * onScreenWidth * WORLD_SIZE
              : -pts[i * 3 + 2] * fit.scale * WORLD_SIZE,
          );
          rig.joints[i].position.copy(worldPos[i]);
        }
        // Follows the wrist now that it is no longer parented to it.
        rig.marker.position.copy(worldPos[0]);
        rig.marker.position.y -= 0.06;

        for (let c = 0; c < HAND_CONNECTIONS.length; c++) {
          const [a, b] = HAND_CONNECTIONS[c];
          const bone = rig.bones[c];
          tmpDir.subVectors(worldPos[b], worldPos[a]);
          const length = tmpDir.length();
          bone.visible = length > 1e-5;
          if (!bone.visible) continue;
          bone.position.addVectors(worldPos[a], worldPos[b]).multiplyScalar(0.5);
          bone.quaternion.setFromUnitVectors(yAxis, tmpDir.normalize());
          bone.scale.set(1, length, 1);
        }
      });
    };

    let lastApplied = -1;
    let raf = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      controls.update();
      const current = frameRef.current;
      if (current !== lastApplied) {
        lastApplied = current;
        applyFrame(current);
      }
      renderer.render(scene, camera);
      onFpsRef.current?.();
    };

    const resize = () => {
      const width = container.clientWidth || 640;
      const height = container.clientHeight || width;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);

    applyFrame(frameRef.current);
    loop();

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      controls.dispose();
      scene.traverse((obj) => {
        const mesh = obj as THREE.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
        const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(material)) material.forEach((m) => m.dispose());
        else material?.dispose();
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [data, layout, frameRef]);

  return (
    <div
      ref={containerRef}
      className="w-full aspect-square rounded-t-2xl overflow-hidden bg-[#0c161e]"
      data-testid="hand-3d-container"
    />
  );
}
