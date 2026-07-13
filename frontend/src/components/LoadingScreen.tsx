/**
 * Full-screen brand loader. A dimmed CTU seal sits behind a full-colour copy
 * that fills bottom→top like liquid (see `logoFill` keyframe in index.css),
 * with an indeterminate progress sliver underneath. Used for the app boot,
 * lazy-route Suspense, and the auth gate.
 */
export default function LoadingScreen({ label = "Đang tải…" }: { label?: string }) {
  return (
    <div className="fixed inset-0 z-[9990] flex flex-col items-center justify-center gap-6 bg-white/95 backdrop-blur-sm">
      <div className="relative h-24 w-24">
        {/* Dimmed base */}
        <img
          src="/logo.png"
          alt=""
          aria-hidden
          className="absolute inset-0 h-full w-full object-contain opacity-15 grayscale"
        />
        {/* Colour fill, revealed bottom→top */}
        <img
          src="/logo.png"
          alt="CTU.SignBridge"
          className="absolute inset-0 h-full w-full object-contain animate-logo-fill"
        />
      </div>

      <div className="flex flex-col items-center gap-2.5">
        <span className="text-sm font-medium tracking-wide text-slate-500">{label}</span>
        <span className="block h-1 w-36 overflow-hidden rounded-full bg-slate-100">
          <span className="block h-full w-1/3 rounded-full bg-ctu-blue animate-loader-bar" />
        </span>
      </div>
    </div>
  );
}
