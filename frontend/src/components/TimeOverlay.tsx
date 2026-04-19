import { useEffect, useState } from "react";

export default function TimerOverlay({ recording, duration }: { recording: boolean; duration: number }) {
  const [time, setTime] = useState(0);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (recording) {
      setTime(0);
      interval = setInterval(() => setTime((t) => t + 1), 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [recording]);

  const progress = Math.min(time / duration, 1) * 100;

  return (
    <div className="absolute top-2 left-2 bg-black bg-opacity-60 text-white px-3 py-1 rounded">
      <div className="text-sm">⏱ {time}s</div>
      <div className="w-32 bg-gray-700 h-2 rounded mt-1">
        <div className="bg-green-400 h-2 rounded" style={{ width: `${progress}%` }}></div>
      </div>
    </div>
  );
}
