import { useMemo, useState } from "react";
import Modal from "./ui/Modal";
import Button from "./ui/Button";
import { useI18n } from "../i18n";
import { useAuth } from "../hooks/useAuth";
import { useVocabularyRegistry } from "../hooks/useVocabularyRegistry";
import { dialectLabel } from "../config/dialectLabels";
import { registerClass, requestClass } from "../api/dataset";
import type { ClassRow } from "../types";
import { friendlyError } from "../lib/errors";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (row: ClassRow) => void;
  initialLanguage?: string;
  initialDialect?: string;
};

/** Shared label creation entry point for live capture and video upload. */
export default function CreateLabelModal({
  isOpen, onClose, onCreated, initialLanguage = "vn", initialDialect = "common",
}: Props) {
  const { t } = useI18n();
  const { isAdmin } = useAuth();
  const { dialects, regions } = useVocabularyRegistry();
  const [value, setValue] = useState("");
  const [language, setLanguage] = useState(initialLanguage);
  const [dialect, setDialect] = useState(initialDialect || "common");
  const [region, setRegion] = useState("unclassified");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const dialectOptions = useMemo(
    () => dialects.filter((d) => d.is_active !== false).map((d) => d.dialect_id),
    [dialects],
  );
  const regionOptions = regions.length ? regions : [{ code: "unclassified", name_vi: t("Chưa phân loại") }];

  const close = () => { if (!saving) { setError(""); onClose(); } };
  const submit = async () => {
    const label = value.trim();
    if (!label) { setError(t("Tên nhãn không được để trống.")); return; }
    setSaving(true); setError("");
    let result: Awaited<ReturnType<typeof requestClass>>;
    try {
      result = isAdmin
        ? await registerClass({ label, language, dialect, region, is_common_language: dialect === "common" })
        : await requestClass({ label, language, dialect, region, is_common_language: dialect === "common" });
    } catch (err) {
      // `registerClass` ném lỗi thay vì trả Result; không bắt thì modal kẹt ở "đang lưu".
      setError(friendlyError(err, t("Không thể tạo nhãn."))); setSaving(false); return;
    }
    if (!result.ok) { setError(result.error || t("Không thể tạo nhãn.")); setSaving(false); return; }
    setValue(""); setSaving(false); onCreated(result.data); onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={close} title={t("Tạo nhãn mới")}>
      <div className="space-y-4">
        <div>
          <label className="mb-2 block text-sm font-medium text-gray-700">{t("Tên nhãn")}</label>
          <input className="input w-full" value={value} onChange={(e) => setValue(e.target.value)} disabled={saving} autoFocus />
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="text-sm font-medium text-gray-700">{t("Ngôn ngữ")}
            <select className="input mt-2 w-full" value={language} onChange={(e) => setLanguage(e.target.value)} disabled={saving}>
              <option value="vn">{t("🇻🇳 Tiếng Việt")}</option><option value="en">{t("🇬🇧 Tiếng Anh")}</option>
            </select>
          </label>
          <label className="text-sm font-medium text-gray-700">{t("Phương ngữ")}
            <select className="input mt-2 w-full" value={dialect} onChange={(e) => setDialect(e.target.value)} disabled={saving}>
              {[...new Set([dialect, ...dialectOptions])].map((d) => <option key={d} value={d}>{dialectLabel(d)}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-gray-700">{t("Vùng miền")}
            <select className="input mt-2 w-full" value={region} onChange={(e) => setRegion(e.target.value)} disabled={saving}>
              {regionOptions.map((r) => <option key={r.code} value={r.code}>{r.name_vi || r.code}</option>)}
            </select>
          </label>
        </div>
        {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        <div className="flex justify-end gap-3 border-t border-gray-100 pt-4">
          <Button variant="ghost" onClick={close} disabled={saving}>{t("Hủy")}</Button>
          <Button variant="primary" onClick={submit} loading={saving}>{t("Tạo nhãn")}</Button>
        </div>
      </div>
    </Modal>
  );
}
