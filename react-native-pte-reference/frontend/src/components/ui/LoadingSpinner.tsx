/**
 * Inline wave-bar loader. Renders 5 bouncing bars in the CTU-blue brand colour.
 * Drop this into any card or section that is fetching data — it centres itself
 * and takes up only as much vertical space as needed.
 *
 * Sizes:  sm → 8/20px bars  |  md → 10/28px bars  |  lg → 12/36px bars
 */
export default function LoadingSpinner({
  size = "md",
  className = "",
  label,
}: {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}) {
  const config = {
    sm: { width: "w-1",   minH: "8px",  maxH: "20px", gap: "gap-1",   labelSize: "text-xs" },
    md: { width: "w-1.5", minH: "10px", maxH: "28px", gap: "gap-1.5", labelSize: "text-sm" },
    lg: { width: "w-1.5", minH: "12px", maxH: "36px", gap: "gap-1.5", labelSize: "text-sm" },
  };

  const c = config[size];

  return (
    <div className={`flex flex-col items-center justify-center gap-3 ${className}`}>
      <div className={`flex items-end ${c.gap}`}>
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className={`inline-block ${c.width} rounded-full bg-ctu-blue origin-bottom`}
            style={{
              animation: `waveBar 1s ease-in-out infinite`,
              animationDelay: `${i * 0.12}s`,
              height: c.minH,
            }}
          />
        ))}
      </div>
      {label && (
        <span className={`font-medium tracking-wide text-ctu-blue/70 ${c.labelSize}`}>{label}</span>
      )}
    </div>
  );
}