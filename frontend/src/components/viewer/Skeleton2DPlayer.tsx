import { useEffect, useMemo, useRef } from "react";
import {
  computeFit,
  handPoints,
  HAND_CONNECTIONS,
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
  const fit = useMemo(() => computeFit(data.sequence), [data]);

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

      const px: [number, number][] = [];
      for (let i = 0; i < 21; i++) {
        const [ux, uy] = fit.toUnit(pts[i * 3], pts[i * 3 + 1]);
        px.push([ux * CANVAS_SIZE, uy * CANVAS_SIZE]);
      }

      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      for (const [a, b] of HAND_CONNECTIONS) {
        const aZero = pts[a * 3] === 0 && pts[a * 3 + 1] === 0 && pts[a * 3 + 2] === 0;
        const bZero = pts[b * 3] === 0 && pts[b * 3 + 1] === 0 && pts[b * 3 + 2] === 0;
        if (aZero || bZero) continue;
        ctx.beginPath();
        ctx.moveTo(px[a][0], px[a][1]);
        ctx.lineTo(px[b][0], px[b][1]);
        ctx.stroke();
      }

      ctx.fillStyle = color;
      for (let i = 0; i < 21; i++) {
        const zero = pts[i * 3] === 0 && pts[i * 3 + 1] === 0 && pts[i * 3 + 2] === 0;
        if (zero) continue;
        ctx.beginPath();
        ctx.arc(px[i][0], px[i][1], 5, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    drawHand("left", LEFT_COLOR);
    drawHand("right", RIGHT_COLOR);
  }, [data, frame, fit]);

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
