from __future__ import annotations

from typing import List, Dict
from app.dataset_manager import load_labels, ClassMetadata
from app.tenancy import tenant_id_of

def load_inference_classes(tenant_id: str, language: str,
                           dialect: str) -> List[ClassMetadata]:
    """Bảng lớp cho nhận dạng, TRONG phạm vi một tổ chức.

    Đây là đường REQUEST, không phải đường bảo trì. Bản trước đọc toàn kho,
    nên bảng lớp trả về cho một tổ chức chứa cả nhãn của tổ chức khác — rò dữ
    liệu danh mục, và làm chỉ số lớp lệch so với mô hình đã huấn luyện.
    """
    rows = load_labels(tenant_id)
    out: List[ClassMetadata] = []
    for r in rows:
        lang = r["language"]
        dia = r["dialect"]
        is_global = bool(int(r["is_common_global"]))
        is_lang_common = bool(int(r["is_common_language"]))
        # Include:
        # - Matching language+dialect
        # - Language common for that language
        # - Global common always
        if is_global or (lang == language and (dia == dialect or is_lang_common)):
            out.append(ClassMetadata(
                class_uid=r["class_uid"],
                slug=r["slug"],
                label_original=r["label_original"],
                language=lang,
                dialect=dia,
                is_common_global=is_global,
                is_common_language=is_lang_common,
                tenant_id=tenant_id_of(r),
            ))
    return out

def build_class_map(classes: List[ClassMetadata]) -> Dict[str, Dict[str, str]]:
    return {
        c.class_uid: {
            "slug": c.slug,
            "label_original": c.label_original,
            "language": c.language,
            "dialect": c.dialect,
            "is_common_global": c.is_common_global,
            "is_common_language": c.is_common_language,
        }
        for c in classes
    }
