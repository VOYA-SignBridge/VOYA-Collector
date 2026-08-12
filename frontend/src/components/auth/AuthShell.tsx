import type { ReactNode } from "react";
import { useI18n } from "../../i18n";

interface AuthShellProps {
  title: string;
  children: ReactNode;
  footer: ReactNode;
}

/**
 * Shared visual shell for Login/Register: full-bleed campus photo,
 * centered glass card carrying the real CTU seal.
 */
export default function AuthShell({ title, children, footer }: AuthShellProps) {
  const { t } = useI18n();
  return (
    <div className="relative min-h-dvh bg-ctu-navy font-display">
      <div className="absolute inset-0 overflow-hidden">
        <img
          src="background.png"
          alt=""
          aria-hidden="true"
          className="h-full w-full scale-105 object-cover blur-[2px] saturate-[1.05]"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-ctu-navy/85 via-ctu-navy/60 to-ctu-navy/90" />
      </div>

      <div className="relative flex min-h-dvh items-center justify-center px-4 py-8 sm:py-10">
        <div className="w-full max-w-md motion-safe:animate-auth-rise">
          <div className="overflow-hidden rounded-[1.75rem] border border-white/60 bg-white/95 shadow-[0_30px_80px_rgba(9,16,38,0.45)] backdrop-blur-xl">
            <div className="px-6 pb-5 pt-7 sm:px-10 sm:pb-6 sm:pt-8">
              <div className="flex flex-col items-center text-center">
                <img
                  src="logo.png"
                  alt={t("Đại học Cần Thơ")}
                  className="h-16 w-16 sm:h-20 sm:w-20 object-contain drop-shadow-sm"
                />
                <p className="mt-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-ctu-blue">
                  {t("Đại học Cần Thơ")}
                </p>
                <h1 className="mt-1 font-display text-2xl font-bold tracking-tight text-ctu-blue sm:text-[1.75rem]">
                  CTU<span className="text-ctu-blue-light">.SignBridge</span>
                </h1>
                <p className="mt-1 text-xs text-slate-500 sm:text-sm">
                  {t("Nền tảng AI về Ngôn ngữ Ký hiệu Việt Nam")}
                </p>

                <h2 className="mt-4 text-lg font-semibold text-slate-900 sm:text-xl">{title}</h2>
              </div>

              <div className="mt-6 sm:mt-7">{children}</div>
            </div>

            <div className="border-t border-slate-100 bg-slate-50/70 px-6 py-4 sm:px-10">{footer}</div>
          </div>

          <p className="mt-6 text-center text-xs text-white/70">
            © {new Date().getFullYear()} Đại học Cần Thơ · CTU.SignBridge
          </p>
        </div>
      </div>
    </div>
  );
}
