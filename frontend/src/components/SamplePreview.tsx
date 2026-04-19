import { useEffect, useRef } from "react";

interface Props {
  keypoints: number[][]; // mảng [frame][dim]
  onClose: () => void;
}

export default function SamplePreview({ keypoints, onClose }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let frame = 0;
    const fps = 6;
    const interval = 1000 / fps;

    const draw = () => {
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // ví dụ: giả định keypoints là 21 điểm bàn tay (x,y)
      const kp = keypoints[frame];
      ctx.fillStyle = "blue";
      for (let i = 0; i < kp.length; i += 2) {
        const x = kp[i] * canvas.width;
        const y = kp[i + 1] * canvas.height;
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, 2 * Math.PI);
        ctx.fill();
      }

      frame = (frame + 1) % keypoints.length;
    };

    const timer = setInterval(draw, interval);
    return () => clearInterval(timer);
  }, [keypoints]);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
      <div className="bg-white p-4 rounded shadow-lg">
        <button
          onClick={onClose}
          className="mb-2 px-3 py-1 bg-red-500 text-white rounded"
        >
          Close
        </button>
        <canvas ref={canvasRef} width={400} height={400} className="border" />
      </div>
    </div>
  );
}
