# -*- coding: utf-8 -*-
"""Đổi khoá trích dẫn trong bản thảo cho khớp SignBridge_Reference.bib.

    python scripts/doi_khoa_trichdan.py                 # chạy thử cả hai chương
    python scripts/doi_khoa_trichdan.py --ghi --gt      # ghi phần giới thiệu
    python scripts/doi_khoa_trichdan.py --ghi --c2      # ghi Chương 2

Tạo bản sao .bak trước khi ghi.

Bản đồ dưới đây gom CẢ BA đời khoá đã từng dùng — khoá đặt tay ban đầu, khoá
dài Zotero tự sinh, và khoá ngắn hiện hành — nên chạy nhiều lần không hại gì.
Đích luôn là bộ khoá ngắn trong `.bib` ngày 14/08/2026 (91 mục).
"""
import io, os, re, sys, shutil

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

os.chdir(r"e:\CTU_ProjectOutside\VOYA-Collector")
GT = "docs/00-thesis/LUANVAN_PHANGIOITHIEU.md"
C2 = "docs/00-thesis/LUANVAN_CHUONG2.md"
BIB = "docs/00-thesis/SignBridge_Reference/SignBridge_Reference.bib"

MAP = {
    # --- văn bản pháp quy: đích là khoá NÓI RÕ SỐ HIỆU ---------------------
    "vietnam_personal_data_protection_law_2025": "quochoi_luat_bvdlcn_2025",
    "quoc_hoi_luat_bvdlcn_2025": "quochoi_luat_bvdlcn_2025",
    "quoc_hoi_nuoc_cong_hoa_xa_hoi_chu_nghia_viet_nam_luat_2025":
        "quochoi_luat_bvdlcn_2025",
    "vietnam_decree_356_2025": "chinhphu_nd356_2025",
    "chinh_phu_nghi_dinh_356_2025": "chinhphu_nd356_2025",
    "chinh_phu_nuoc_cong_hoa_xa_hoi_chu_nghia_viet_nam_nghi_2025":
        "chinhphu_nd356_2025",
    "quoc_hoi_nuoc_cong_hoa_xa_hoi_chu_nghia_viet_nam_luat_2024":
        "quochoi_luat_dulieu_2024",
    "quoc_hoi_nuoc_cong_hoa_xa_hoi_chu_nghia_viet_nam_luat_2025-1":
        "quochoi_luat_shtt_2025",
    "chinh_phu_nuoc_cong_hoa_xa_hoi_chu_nghia_viet_nam_nghi_2025-1":
        "chinhphu_nd165_2025",
    "european_parliament_and_council_of_the_european_union_regulation_2016":
        "eu_gdpr_2016",
    "article29_anonymisation_2014": "wp29_anonymisation_2014",
    "article_29_data_protection_working_party_opinion_2014":
        "wp29_anonymisation_2014",
    # --- PostgreSQL: ba trang, ba khoá ------------------------------------
    "the_postgresql_global_development_group_postgresql_2024": "postgresql_rls_2026",
    "the_postgresql_global_development_group_postgresql_2026": "postgresql_rls_2026",
    "the_postgresql_global_development_group_postgresql_2026-1": "postgresql_set_2026",
    "the_postgresql_global_development_group_postgresql_2026-2":
        "postgresql_configfunc_2026",
    "postgresql_session_settings_2026": "postgresql_set_2026",
    "postgresql_set_2024": "postgresql_set_2026",
    "postgresql_configuration_functions_2026": "postgresql_configfunc_2026",
    # --- NIST -------------------------------------------------------------
    "temoshok_nist_auth_2025": "nist_sp800_63b_2025",
    "temoshok_digital_2025": "nist_sp800_63b_2025",
    "grassi_digital_2017": "nist_sp800_63b_2025",
    "nist_fips_180-4_2015": "nist_fips180_4_2015",
    "national_institute_of_standards_and_technology_secure_2015":
        "nist_fips180_4_2015",
    # --- WLASL: bài báo ≠ giấy phép ---------------------------------------
    "li_word-level_2020": "li_wlasl_baibao_2020",
    "li_wlasl_2020": "li_wlasl_giayphep_2020",
    # --- VSL400: bài dữ liệu ≠ bản thoả thuận -----------------------------
    "nguyen_quoc_vsl400_2025": "nguyenquoc_multiview_2026",
    "nguyen_quoc_multi-view_2026": "nguyenquoc_multiview_2026",
    "nguyen_quoc_vsl400_2026": "nguyenquoc_vsl400_dua_2026",
    # --- từ điển QIPEDC ----------------------------------------------------
    "ministry_of_education_and_training_vietnam_vietnamese_2019":
        "bogddt_qipedc_2019",
    "bo_giao_duc_va_dao_tao_tu_2019": "bogddt_qipedc_2019",
    "bo_khoa_hoc_va_cong_nghe_van_2026": "bokhcn_hopnhat_06_2026",
    "van_phong_quoc_hoi_nuoc_cong_hoa_xa_hoi_chu_nghia_viet_nam_luat_2025":
        "vpqh_hopnhat_shtt_2025",
    "van_phong_quoc_hoi_nuoc_cong_hoa_xa_hoi_chu_nghia_viet_nam_luat_2026":
        "vpqh_hopnhat_gddt_2026",
    # --- giấy phép dữ liệu -------------------------------------------------
    "creative_commons_attribution-noncommercial_2013": "cc_by_nc_4_2013",
    "creative_commons_attribution-noncommercial-sharealike_2013":
        "cc_by_nc_sa_4_2013",
    "creative_commons_frequently_nodate": "cc_faq_dulieu_nodate",
    "mit_laboratory_for_computational_physiology_physionet_nodate":
        "physionet_giayphep_nodate",
    # --- đổi tên đơn thuần -------------------------------------------------
    "bragg_interdisciplinary_2019": "bragg_sign_2019",
    "saltzer_schroeder_1975": "saltzer_protection_1975",
    "jones_jwt_2015": "jones_json_2015",
    "josefsson_eddsa_2017": "josefsson_edwards-curve_2017",
    "hellerstein_calm_2020": "hellerstein_keeping_2020",
    "mell_nist_cloud_2011": "mell_nist_2011",
    "grossman_data_commons_2016": "grossman_case_2016",
    "hess_ostrom_commons_2007": "hess_understanding_2007",
    "hohpe_woolf_eip_2003": "hohpe_enterprise_2003",
    "hu_abac_2014": "hu_guide_2014",
    "hardt_oauth2_2012": "hardt_oauth_2012",
    "hardy_confused_deputy_1988": "hardy_confused_1988",
    "beck_xp_2004": "beck_extreme_2004",
    "kniberg_kanban_scrum_2010": "kniberg_kanban_2010",
    "casbin_rbac_domains_2026": "casbin_authors_rbac_2026",
    "sheffer_jwt_bcp_2020": "sheffer_json_2020",
    "lodderstedt_oauth_security_bcp_2025": "lodderstedt_best_2025",
    "fowler_stranglerfigapplication_2004": "fowler_strangler_2004",
    "celery_contributors_celery_2024": "celery_contributors_celery_2026",
    "redis_ltd_redis_2024": "redis_ltd_redis_2026",
    "minio_inc_minio_2024": "minio_inc_minio_2026",
    "zhang_mediapipe_hands_2020": "zhang_mediapipe_2020",
    "desai_asl_citizen_2023": "desai_asl_2023",
    "pham_vsl_dynamic_2021": "pham_vietnamese_2021",
    "tran_vsl_alphabet_2025": "tran_vietnamese_2025",
    "chu_crossvivit_2025": "chu_cross-attention_2025",
}

# Chưa có mục nào trong .bib — script KHÔNG đụng vào, phải thêm vào Zotero
CHUA_CO = {
    "harris_research_2009": "REDCap 2009 — doi 10.1016/j.jbi.2008.08.010",
    "harris_redcap_2019": "REDCap consortium 2019 — doi 10.1016/j.jbi.2019.103208",
    "crosas_dataverse_2011": "Dataverse — doi 10.1045/january2011-crosas",
    "cern_openaire_zenodo_2013": "Zenodo — doi 10.25495/7GXK-RD71",
    "w3c_wcag22_2023": "WCAG 2.2, W3C Recommendation 05/10/2023",
}


def khoa_trong_bib():
    if not os.path.exists(BIB):
        return set()
    s = io.open(BIB, encoding="utf-8", errors="replace").read()
    return set(re.findall(r"^@\w+\s*\{\s*([^,\s]+)\s*,", s, re.M))


def xu_ly(path, ghi, bib):
    if not os.path.exists(path):
        print("KHONG THAY %s" % path)
        return
    s = io.open(path, encoding="utf-8", newline="").read()
    print("\n=== %s ===" % path)
    # Phần giới thiệu: phụ chú (từ "## A. " trở đi) KHÔNG thuộc quyển và cố ý
    # giữ tên khoá cũ để làm bảng đối chiếu — chỉ đổi trong THÂN.
    duoi = ""
    mm = re.search(r"^## A\. ", s, re.M)
    if mm and path.endswith("PHANGIOITHIEU.md"):
        duoi, s = s[mm.start():], s[:mm.start()]
        print("  (chi doi trong THAN — phu chu tu '## A.' giu nguyen)")
    tong = 0
    for cu, moi in MAP.items():
        pat = r"(?<![\w:.-])" + re.escape(cu) + r"(?![\w-])"
        n = len(re.findall(pat, s))
        if n:
            s = re.sub(pat, moi, s)
            print("  %-56s -> %-32s (%d)" % (cu, moi, n))
            tong += n
    print("  --- %d luot doi" % tong)

    # còn khoá nào không phân giải được?
    dung = set()
    for m in re.finditer(r"cite\{([^}]*)\}", s):
        for k in m.group(1).split(","):
            k = k.strip()
            if k and k not in ("*", "key"):
                dung.add(k)
    thieu = sorted(dung - bib) if bib else []
    if thieu:
        print("  CHUA PHAN GIAI (%d):" % len(thieu))
        for k in thieu:
            print("    - %-30s %s" % (k, CHUA_CO.get(k, "?? doi chieu bang tay")))
    else:
        print("  moi khoa deu phan giai duoc ✓")

    s = s + duoi
    if ghi and tong:
        shutil.copyfile(path, path + ".bak")
        io.open(path, "w", encoding="utf-8", newline="").write(s)
        print("  DA GHI (ban sao: %s.bak)" % os.path.basename(path))


bib = khoa_trong_bib()
print("BIB: %d khoa" % len(bib))
ghi = "--ghi" in sys.argv
chi_gt = "--gt" in sys.argv
chi_c2 = "--c2" in sys.argv
if not chi_c2:
    xu_ly(GT, ghi and not chi_c2, bib)
if not chi_gt:
    xu_ly(C2, ghi and chi_c2, bib)
if not ghi:
    print("\n(chay thu — chua ghi)")
