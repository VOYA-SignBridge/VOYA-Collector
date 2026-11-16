import { useEffect, useState } from "react";
import { useI18n } from "../../i18n";

/**
 * Video có PHỤ ĐỀ và bản chữ.
 *
 * Người dùng chính của hệ thống là người khiếm thính nên phụ đề không phải tuỳ chọn:
 * mỗi video đi kèm hai tệp WebVTT (vi/en) và một bản chữ đọc được ngay dưới video,
 * cho người không bật được phụ đề hoặc dùng trình đọc màn hình. Cả ba lấy từ MỘT tệp
 * nguồn (`<tên>.cues.json`) nên không thể lệch nhau — xem `scripts/make_guide_video.py`.
 *
 * Đường dẫn tương đối (không có `/` đầu) để chạy được cả khi ứng dụng nằm dưới
 * một đường dẫn con như `/voya/`, cùng cách `logo.png` được nạp.
 */

type Cue = { start: number; line: Record<string, string>; heading: Record<string, string> };
type Cues = { title: Record<string, string>; cues: Cue[] };

/** Tên ngôn ngữ viết bằng CHÍNH ngôn ngữ đó (endonym): không dịch, để người đọc nhận ra ngôn ngữ của mình. */
const TRACKS = [
  // i18n-ignore-next-line — tên ngôn ngữ bằng chính ngôn ngữ đó, không dịch.
  { lang: "vi", label: "Tiếng Việt" },
  { lang: "en", label: "English" },
] as const;

function clock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function CaptionedVideo({ name }: { name: string }) {
  const { t, lang } = useI18n();
  const [cues, setCues] = useState<Cues | null>(null);
  const base = `media/${name}`;

  useEffect(() => {
    let cancelled = false;
    fetch(`${base}.cues.json`)
      .then((r) => (r.ok ? (r.json() as Promise<Cues>) : null))
      .then((c) => !cancelled && setCues(c))
      .catch(() => undefined); // không có bản chữ thì video vẫn xem được
    return () => {
      cancelled = true;
    };
  }, [base]);

  const title = cues?.title[lang] ?? cues?.title.vi ?? t("Video hướng dẫn");

  return (
    <figure>
      <video
        controls
        preload="metadata"
        playsInline
        poster={`${base}.poster.jpg`}
        aria-label={title}
        className="aspect-video w-full rounded-2xl bg-slate-900 shadow-sm"
      >
        <source src={`${base}.webm`} type="video/webm" />
        {/* `default` đặt theo ngôn ngữ giao diện; người xem vẫn đổi được trong trình phát. */}
        {TRACKS.map((tr) => (
          <track key={tr.lang} kind="captions" src={`${base}.${tr.lang}.vtt`} srcLang={tr.lang} label={tr.label} default={lang === tr.lang} />
        ))}
        {t("Trình duyệt của bạn không phát được video này. Hãy đọc bản chữ bên dưới.")}
      </video>
      <figcaption className="mt-2 text-sm text-slate-600">
        {title}. {t("Video không có tiếng; mọi nội dung nằm ở phụ đề và bản chữ.")}
      </figcaption>

      {cues && (
        <details className="mt-3 rounded-xl border border-slate-200 bg-white p-4">
          <summary className="cursor-pointer text-sm font-semibold text-ctu-blue">{t("Xem bản chữ của video")}</summary>
          <ol className="mt-3 space-y-3">
            {cues.cues.map((c) => (
              <li key={c.start} className="text-sm">
                <span className="mr-2 font-mono text-xs text-slate-400">{clock(c.start)}</span>
                <span className="font-semibold text-slate-900">{c.heading[lang] ?? c.heading.vi}</span>
                <span className="block text-slate-600">{c.line[lang] ?? c.line.vi}</span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </figure>
  );
}
