/**
 * Full-screen wave-line preloader. Five bars animate in a smooth wave
 * pattern using staggered CSS delays. No logo, no spinner — just a
 * clean, modern wave animation with the brand colour palette.
 *
 * Used for app boot, lazy-route Suspense, and the auth gate.
 */
import { useI18n } from "../i18n";

export default function LoadingScreen({ label }: { label?: string }) {
  const { t } = useI18n();
  // Mặc định nằm trong thân hàm: `t` đến từ hook, chưa có lúc tính tham số.
  const text = label ?? t("Đang tải…");
  return (
    <div className="fixed inset-0 z-[9990] flex flex-col items-center justify-center gap-8 bg-white">
      {/* Wave line bars */}
      <div className="flex items-end gap-1.5">
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className="inline-block w-1.5 rounded-full bg-ctu-blue origin-bottom"
            style={{
              animation: "waveBar 1s ease-in-out infinite",
              animationDelay: `${i * 0.12}s`,
              height: "12px",
            }}
          />
        ))}
      </div>

      <span className="text-sm font-medium tracking-wide text-ctu-blue/70">{text}</span>
    </div>
  );
}
