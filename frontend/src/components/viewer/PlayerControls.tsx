const SPEEDS = [0.25, 0.5, 1, 1.5, 2];

interface PlayerControlsProps {
  frame: number;
  frameCount: number;
  playing: boolean;
  speed: number;
  onToggle: () => void;
  onSeek: (frame: number) => void;
  onSpeed: (speed: number) => void;
}

export default function PlayerControls({
  frame,
  frameCount,
  playing,
  speed,
  onToggle,
  onSeek,
  onSpeed,
}: PlayerControlsProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-slate-800/95 rounded-b-2xl">
      <button
        type="button"
        onClick={onToggle}
        aria-label={playing ? "Tạm dừng" : "Phát"}
        className="w-9 h-9 flex items-center justify-center rounded-full bg-ctu-blue hover:bg-ctu-blue-light text-white transition-colors shrink-0"
      >
        {playing ? (
          <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
            <rect x="6" y="5" width="4" height="14" rx="1" />
            <rect x="14" y="5" width="4" height="14" rx="1" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" className="w-4 h-4 ml-0.5" fill="currentColor">
            <path d="M8 5.14v13.72c0 .8.87 1.3 1.55.88l10.4-6.86a1.05 1.05 0 0 0 0-1.76L9.55 4.26A1.04 1.04 0 0 0 8 5.14Z" />
          </svg>
        )}
      </button>

      <input
        type="range"
        min={0}
        max={Math.max(0, frameCount - 1)}
        value={frame}
        onChange={(e) => onSeek(Number(e.target.value))}
        aria-label="Tua khung hình"
        className="flex-1 accent-ctu-blue-light cursor-pointer"
      />

      <span className="text-xs text-slate-300 tabular-nums whitespace-nowrap">
        {frame + 1}/{frameCount}
      </span>

      <select
        value={speed}
        onChange={(e) => onSpeed(Number(e.target.value))}
        aria-label="Tốc độ phát"
        className="bg-slate-700 text-slate-100 text-xs rounded-lg px-2 py-1.5 border border-slate-600 cursor-pointer"
      >
        {SPEEDS.map((s) => (
          <option key={s} value={s}>
            {s}×
          </option>
        ))}
      </select>
    </div>
  );
}
