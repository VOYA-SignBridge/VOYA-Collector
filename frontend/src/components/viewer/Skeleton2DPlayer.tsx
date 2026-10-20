import { useEffect, useMemo, useRef } from "react";
import {
  handLayout,
  handPoints,
  HAND_CONNECTIONS,
  LANDMARKS_PER_HAND,
  LEFT_COLOR,
  RIGHT_COLOR,
  type FramesData,
  type HandSide,
} from "./handData";

const CANVAS_SIZE = 640; // internal resolution; CSS scales it responsively

interface Skeleton2DPlayerProps {
  data: FramesData;
  frame: number;
}

/**
 * Tier 2: 2D canvas skeleton playback — 42 points/frame, runs on anything.
 * Same drawing scheme as the capture overlay (left orange / right blue).
 */
export default function Skeleton2DPlayer({ data, frame }: Skeleton2DPlayerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  // Layout is decided from the sample, not assumed: wrist-centred recordings
  // put both wrists on the origin and need separate columns, while recordings
  // that kept image coordinates already hold the hands in their true relative
  // position and must be left alone.
  const layout = useMemo(() => handLayout(data.sequence), [data]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    const row = data.sequence[frame];
    if (!canvas || !ctx || !row) return;

    ctx.fillStyle = "#0c161e";
    ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

    const drawHand = (side: HandSide, color: string) => {
      const pts = handPoints(row, side);
      if (!pts) return; // hand not detected this frame — draw nothing

      const fit = layout[side];
      const px: [number, number][] = [];
      for (let i = 0; i < LANDMARKS_PER_HAND; i++) {
        const [ux, uy] = fit.toUnit(pts[i * 3], pts[i * 3 + 1]);
        px.push([ux * CANVAS_SIZE, uy * CANVAS_SIZE]);
      }

      // No per-landmark "is it (0,0,0)?" test. In wrist-centred data the origin
      // IS the wrist, and the API's 5-dp rounding turns its float residue into
      // an exact zero — the old test therefore discarded the wrist and the
      // three palm-base bones in every single frame. handPoints already told us
      // the whole hand is present, so all 21 landmarks are real.
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      for (const [a, b] of HAND_CONNECTIONS) {
        if (!Number.isFinite(px[a][0]) || !Number.isFinite(px[b][0])) continue;
        ctx.beginPath();
        ctx.moveTo(px[a][0], px[a][1]);
        ctx.lineTo(px[b][0], px[b][1]);
        ctx.stroke();
      }

      ctx.fillStyle = color;
      for (let i = 0; i < LANDMARKS_PER_HAND; i++) {
        if (!Number.isFinite(px[i][0]) || !Number.isFinite(px[i][1])) continue;
        ctx.beginPath();
        // The wrist anchors the hand — draw it slightly larger so the palm
        // base reads clearly.
        ctx.arc(px[i][0], px[i][1], i === 0 ? 7 : 5, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    // Faint divider, drawn ONLY in column mode — it is the honest signal that
    // the two hands are shown side by side because the recording did not keep
    // their positions. Drawing it in shared mode would claim a separation that
    // the data does not have.
    //
    // fillRect, not stroke(): the divider is chrome, not anatomy. Counting it
    // as a stroke would inflate the "one stroke per bone" invariant that
    // Skeleton2DPlayer.test.tsx checks, making that assertion meaningless.
    if (layout.mode === "columns") {
      ctx.fillStyle = "rgba(148,163,184,0.18)";
      ctx.fillRect(CANVAS_SIZE / 2 - 0.5, 0, 1, CANVAS_SIZE);
    }

    drawHand("left", LEFT_COLOR);
    drawHand("right", RIGHT_COLOR);
  }, [data, frame, layout]);

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_SIZE}
      height={CANVAS_SIZE}
      className="w-full aspect-square rounded-t-2xl bg-[#0c161e]"
      data-testid="skeleton-2d-canvas"
    />
  );
}
