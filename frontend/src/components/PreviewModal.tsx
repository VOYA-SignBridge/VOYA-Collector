/**
 * Modal wrapper around SamplePreview.
 *
 * Two uses it is built for:
 *  - reviewing a sample already in the library, read-only (omit the callbacks);
 *  - reviewing a take right after recording, before it is uploaded (pass
 *    onConfirm/onDiscard). That flow does not exist yet — today a capture is
 *    sent straight to the server and the contributor only learns the sample was
 *    unusable when the quality gate answers 422 — but the piece it needs is
 *    here and self-contained.
 *
 * Takes a raw `sequence` rather than a FramesData so a caller that has just
 * recorded frames does not have to fabricate class_uid/session_id it has not
 * been given yet.
 */

import { useEffect, useMemo } from "react";
import SamplePreview from "./SamplePreview";
import { FRAME_DIM, type FramesData } from "./viewer/handData";
import { useI18n } from "../i18n";

interface PreviewModalProps {
  /** (frames x 126) landmark matrix. */
  sequence: number[][];
  fps?: number;
  title?: string;
  onClose: () => void;
  /** Supply both to turn this into a confirm/discard review step. */
  onConfirm?: () => void;
  onDiscard?: () => void;
  confirmLabel?: string;
  discardLabel?: string;
}

export default function PreviewModal({
  sequence,
  fps = 15,
  title,
  onClose,
  onConfirm,
  onDiscard,
  confirmLabel,
  discardLabel,
}: PreviewModalProps) {
  const { t } = useI18n();
  // Mặc định phải nằm TRONG thân hàm, không ở danh sách tham số: `t` đến từ
  // hook nên chưa tồn tại lúc tham số mặc định được tính.
  const titleText = title ?? t("Xem lại mẫu");
  const confirmText = confirmLabel ?? t("Xác nhận & Tải lên");
  const discardText = discardLabel ?? t("Bỏ, quay lại");
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const data = useMemo<FramesData>(
    () => ({
      class_uid: "",
      session_id: "",
      sample_uid: "",
      frames: sequence.length,
      dim: FRAME_DIM,
      fps,
      sequence,
    }),
    [sequence, fps]
  );

  const isReview = Boolean(onConfirm && onDiscard);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label={titleText}
    >
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative w-full max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-2xl bg-white shadow-2xl sm:max-w-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <h2 className="text-base font-semibold text-slate-900">{titleText}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("Đóng")}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <SamplePreview data={data} />

        {isReview && (
          <div className="flex flex-col-reverse gap-2 border-t border-slate-200 p-4 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={onDiscard}
              className="w-full rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 sm:w-auto"
            >
              {discardText}
            </button>
            <button
              type="button"
              onClick={onConfirm}
              className="w-full rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 sm:w-auto"
            >
              {confirmText}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
