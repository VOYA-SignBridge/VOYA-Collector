import { useEffect, useRef } from "react";

export default function PreviewModal({ frames, onConfirm, onDiscard }: { frames: number[][]; onConfirm: () => void; onDiscard: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let frame = 0;
    const ctx = canvasRef.current?.getContext("2d");
    const timer = setInterval(() => {
      if (!ctx) return;
      ctx.clearRect(0, 0, 400, 400);

      const kp = frames[frame];
      ctx.fillStyle = "blue";
      for (let i = 0; i < kp.length; i += 2) {
        ctx.beginPath();
        ctx.arc(kp[i] * 400, kp[i + 1] * 400, 4, 0, Math.PI * 2);
        ctx.fill();
      }
      frame = (frame + 1) % frames.length;
    }, 100);

    return () => clearInterval(timer);
  }, [frames]);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center">
      <div className="bg-white p-6 rounded shadow-lg w-[500px]">
        <h2 className="text-xl font-bold mb-3">Preview Recording</h2>
        <canvas ref={canvasRef} width={400} height={400} className="border mb-3" />
        <div className="flex justify-end space-x-2">
          <button className="bg-red-500 text-white px-4 py-2 rounded" onClick={onDiscard}>
            Discard
          </button>
          <button className="bg-green-600 text-white px-4 py-2 rounded" onClick={onConfirm}>
            Confirm & Upload
          </button>
        </div>
      </div>
    </div>
  );
}
