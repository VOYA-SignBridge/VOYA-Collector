import { useState, useRef, useEffect } from 'react';
import { proposeDialect, type SlugTakenError } from '../api/vocabulary';
import { useI18n } from "../i18n";

/**
 * Propose a new dialect.
 *
 * This used to be purely local: it pushed the typed name into a React array and
 * nothing else, so the "new dialect" vanished on reload and never reached the
 * server. It now calls POST /vocabulary/dialects, which files the dialect as
 * PENDING for an admin to approve — that is why the copy says the choice is
 * usable straight away but stays under review.
 *
 * The user types a human name; the slug is derived here and shown before
 * submitting, because the slug is what ends up in samples.csv, in the sample
 * folder names and in the realtime model id — the user should see the string
 * they are actually creating.
 */

interface AddDialectModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Called with the SLUG once the server has accepted the proposal. */
  onAdd: (dialectId: string) => void;
}

/**
 * Vietnamese-aware slug: strip diacritics, đ -> d, non-alphanumerics -> "-".
 * "Hòa Đê" -> "hoa-de", matching the ids already in the registry.
 */
export function slugifyDialect(input: string): string {
  return input
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export default function AddDialectModal({ isOpen, onClose, onAdd }: AddDialectModalProps) {
  const { t } = useI18n();
  const [dialectName, setDialectName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taken, setTaken] = useState<SlugTakenError | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const slug = slugifyDialect(dialectName);

  useEffect(() => {
    if (isOpen && inputRef.current) inputRef.current.focus();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      setDialectName('');
      setError(null);
      setTaken(null);
      setSubmitting(false);
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = dialectName.trim();
    if (!name || !slug || submitting) return;

    setSubmitting(true);
    setError(null);
    setTaken(null);

    const res = await proposeDialect({ dialect_id: slug, display_name: name });
    setSubmitting(false);

    if (res.ok) {
      onAdd(res.data?.dialect?.dialect_id || slug);
      onClose();
      return;
    }
    // 409: the slug exists. Offer to just use it rather than making the user
    // invent a different name for a dialect that is already there.
    if (res.slugTaken) {
      setTaken(res.slugTaken);
      return;
    }
    setError(res.error);
  };

  const useExisting = () => {
    if (!taken) return;
    onAdd(taken.dialect_id);
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4">
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative bg-white rounded-xl shadow-2xl w-full max-w-[calc(100vw-1.5rem)] sm:max-w-md overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
        tabIndex={0}
      >
        <div className="bg-gradient-to-r from-indigo-500 to-cyan-500 px-4 sm:px-6 py-4">
          <h3 className="text-lg font-semibold text-white">{t("Đề xuất phương ngữ mới")}</h3>
          <p className="text-sm text-indigo-100 mt-1">
            {t("Bạn dùng được ngay, quản trị viên sẽ duyệt sau.")}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="p-4 sm:p-6 space-y-4">
          <div>
            <label htmlFor="dialect-name" className="block text-sm font-medium text-gray-700 mb-2">
              {t("Tên phương ngữ")}
            </label>
            <input
              id="dialect-name"
              ref={inputRef}
              type="text"
              value={dialectName}
              onChange={(e) => setDialectName(e.target.value)}
              placeholder={t("Ví dụ: Cần Thơ, Miền núi, v.v.")}
              disabled={submitting}
              className="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all disabled:opacity-60"
            />
            {slug && (
              <p className="mt-2 text-xs text-gray-500">
                {t("Mã sẽ tạo:")}{' '}
                <code className="px-1.5 py-0.5 bg-gray-100 rounded font-mono text-gray-800">
                  {slug}
                </code>{' '}
                — đây là chuỗi xuất hiện trong dữ liệu và tên thư mục mẫu.
              </p>
            )}
          </div>

          {taken && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
              <p className="text-amber-900">
                {t("Mã")} <code className="font-mono">{taken.dialect_id}</code> đã tồn tại
                {taken.existing_display_name ? ` (${taken.existing_display_name})` : ''}.
              </p>
              <button
                type="button"
                onClick={useExisting}
                className="mt-2 text-sm font-medium text-amber-900 underline underline-offset-2 hover:text-amber-700"
              >
                {t("Dùng phương ngữ có sẵn này")}
              </button>
            </div>
          )}

          {error && (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </p>
          )}

          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="w-full sm:w-auto px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:ring-2 focus:ring-gray-500 transition-all"
            >
              {t("Hủy")}
            </button>
            <button
              type="submit"
              disabled={!slug || submitting}
              className="w-full sm:w-auto px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-indigo-500 to-cyan-500 rounded-lg hover:from-indigo-600 hover:to-cyan-600 focus:ring-2 focus:ring-indigo-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? t('Đang gửi…') : t('Đề xuất')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
