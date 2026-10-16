import { useCallback, useEffect, useRef, useState } from "react";

export interface PlaybackControls {
  frame: number;
  playing: boolean;
  speed: number;
  /** Live frame pointer for render loops that must not re-render React (3D). */
  frameRef: React.MutableRefObject<number>;
  toggle: () => void;
  seek: (frame: number) => void;
  setSpeed: (speed: number) => void;
}

/**
 * Playback clock for a fixed-fps keypoint sequence.
 *
 * Advances a frame counter on requestAnimationFrame using elapsed wall time
 * (never "one frame per rAF tick" — display refresh rate must not change the
 * playback speed). Loops at the end. Exposes both React state (`frame`, drives
 * the 2D canvas + scrub bar) and a ref (`frameRef`, read by the 3D loop).
 */
export function usePlayback(frameCount: number, fps: number): PlaybackControls {
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);

  const frameRef = useRef(0);
  const positionRef = useRef(0); // fractional frame position
  const speedRef = useRef(speed);
  speedRef.current = speed;

  useEffect(() => {
    // New sequence → rewind.
    positionRef.current = 0;
    frameRef.current = 0;
    setFrame(0);
  }, [frameCount]);

  useEffect(() => {
    if (!playing || frameCount <= 1 || fps <= 0) return;

    let raf = 0;
    let last = performance.now();

    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      positionRef.current = (positionRef.current + dt * fps * speedRef.current) % frameCount;
      const next = Math.floor(positionRef.current);
      if (next !== frameRef.current) {
        frameRef.current = next;
        setFrame(next);
      }
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, frameCount, fps]);

  const toggle = useCallback(() => setPlaying((p) => !p), []);

  const seek = useCallback(
    (target: number) => {
      const clamped = Math.max(0, Math.min(frameCount - 1, Math.round(target)));
      positionRef.current = clamped;
      frameRef.current = clamped;
      setFrame(clamped);
    },
    [frameCount],
  );

  return { frame, playing, speed, frameRef, toggle, seek, setSpeed };
}
