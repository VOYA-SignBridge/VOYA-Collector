// ---------------------------------------------------------------------------
// DIEN TRUONG "Accessed" cho 31 muc trong Zotero.
//
// Word lay du lieu tu THU VIEN Zotero, khong tu tep .bib. Kieu IEEE in ngay
// truy cap tu truong Accessed; muc nao trong thi in thieu.
//
// Cach chay:  Zotero > Tools > Developer > Run JavaScript  > dan vao > Run
// Script CHI ghi truong Accessed khi no dang TRONG. Chay lai vo hai.
// ---------------------------------------------------------------------------

const BANG = [
 {
  "key": "nguyenquoc_multiview_2026",
  "doi": "10.5281/zenodo.17943573",
  "title": "amultiviewdatasetforvietnamesewordlevelsignlanguagerecognition",
  "date": "2026-08-13"
 },
 {
  "key": "bogddt_qipedc_2019",
  "doi": "",
  "title": "từđiểnngônngữkýhiệuviệtnamdựánqipedc",
  "date": "2026-08-13"
 },
 {
  "key": "li_wlasl_giayphep_2020",
  "doi": "",
  "title": "wlasldatasetlicenseandusageterms",
  "date": "2026-08-13"
 },
 {
  "key": "nguyenquoc_vsl400_dua_2026",
  "doi": "",
  "title": "vsl400datausageagreement",
  "date": "2026-08-13"
 },
 {
  "key": "fowler_strangler_2004",
  "doi": "",
  "title": "stranglerfigapplication",
  "date": "2026-08-13"
 },
 {
  "key": "postgresql_rls_2026",
  "doi": "",
  "title": "postgresql18documentationrowsecuritypolicies",
  "date": "2026-08-13"
 },
 {
  "key": "casbin_authors_casbin_2024",
  "doi": "",
  "title": "casbinanauthorizationlibrarysupportingaccesscontrolmodelslikeaclrbacabac",
  "date": "2026-08-13"
 },
 {
  "key": "casbin_authors_rbac_2026",
  "doi": "",
  "title": "rbacwithdomains",
  "date": "2026-08-13"
 },
 {
  "key": "postgresql_set_2026",
  "doi": "",
  "title": "postgresql18documentationset",
  "date": "2026-08-13"
 },
 {
  "key": "wiggins_twelve-factor_2017",
  "doi": "",
  "title": "thetwelvefactorapp",
  "date": "2026-08-13"
 },
 {
  "key": "postgresql_configfunc_2026",
  "doi": "",
  "title": "postgresql18documentationconfigurationsettingsfunctions",
  "date": "2026-08-13"
 },
 {
  "key": "celery_contributors_celery_2026",
  "doi": "",
  "title": "celerydocumentation",
  "date": "2026-08-13"
 },
 {
  "key": "redis_ltd_redis_2026",
  "doi": "",
  "title": "redisdocumentation",
  "date": "2026-08-13"
 },
 {
  "key": "minio_inc_minio_2026",
  "doi": "",
  "title": "miniodocumentation",
  "date": "2026-08-13"
 },
 {
  "key": "quochoi_luat_bvdlcn_2025",
  "doi": "",
  "title": "luậtbảovệdữliệucánhânluậtsố912025qh15",
  "date": "2026-08-13"
 },
 {
  "key": "chinhphu_nd356_2025",
  "doi": "",
  "title": "nghịđịnhsố3562025nđcpquyđịnhchitiếtmộtsốđiềuvàbiệnphápthihànhluậtbảovệdữliệucánhân",
  "date": "2026-08-13"
 },
 {
  "key": "quochoi_luat_dulieu_2024",
  "doi": "",
  "title": "luậtdữliệuluậtsố602024qh15",
  "date": "2026-08-13"
 },
 {
  "key": "chinhphu_nd165_2025",
  "doi": "",
  "title": "nghịđịnhsố1652025nđcpquyđịnhchitiếtmộtsốđiềuvàbiệnphápthihànhluậtdữliệu",
  "date": "2026-08-13"
 },
 {
  "key": "vpqh_hopnhat_gddt_2026",
  "doi": "",
  "title": "luậtgiaodịchđiệntửvănbảnhợpnhấtsố36vbhnvpqh",
  "date": "2026-08-13"
 },
 {
  "key": "vpqh_hopnhat_shtt_2025",
  "doi": "",
  "title": "luậtsởhữutrítuệvănbảnhợpnhấtsố155vbhnvpqh",
  "date": "2026-08-13"
 },
 {
  "key": "quochoi_luat_shtt_2025",
  "doi": "",
  "title": "luậtsửađổibổsungmộtsốđiềucủaluậtsởhữutrítuệluậtsố1312025qh15",
  "date": "2026-08-13"
 },
 {
  "key": "bokhcn_hopnhat_06_2026",
  "doi": "",
  "title": "vănbảnhợpnhấtsố06vbhnbkhcnvềquyđịnhchitiếtmộtsốđiềuvàbiệnphápthihànhluậtsởhữutrítuệ",
  "date": "2026-08-13"
 },
 {
  "key": "cc_by_nc_4_2013",
  "doi": "",
  "title": "attributionnoncommercial40internationalccbync40",
  "date": "2026-08-13"
 },
 {
  "key": "cc_by_nc_sa_4_2013",
  "doi": "",
  "title": "attributionnoncommercialsharealike40internationalccbyncsa40",
  "date": "2026-08-13"
 },
 {
  "key": "cc_faq_dulieu_nodate",
  "doi": "",
  "title": "frequentlyaskedquestionsaboutdataandcreativecommonslicenses",
  "date": "2026-08-13"
 },
 {
  "key": "microsoft_computational_nodate",
  "doi": "",
  "title": "computationaluseofdataagreementversion10",
  "date": "2026-08-13"
 },
 {
  "key": "physionet_giayphep_nodate",
  "doi": "",
  "title": "physionetcredentialedhealthdatalicenseversion150",
  "date": "2026-08-13"
 },
 {
  "key": "spdx_workgroup_spdx_2026",
  "doi": "",
  "title": "spdxlicenselist",
  "date": "2026-08-13"
 },
 {
  "key": "kniberg_kanban_2010",
  "doi": "",
  "title": "kanbanandscrummakingthemostofboth",
  "date": "2026-08-13"
 },
 {
  "key": "cern_openaire_zenodo_2013",
  "doi": "10.25495/7gxk-rd71",
  "title": "zenodo",
  "date": "2026-08-13"
 },
 {
  "key": "w3c_wcag22_2023",
  "doi": "",
  "title": "webcontentaccessibilityguidelineswcag22",
  "date": "2026-08-13"
 }
];

const chuanHoa = (t) =>
    (t || "").replace(/[{}\\]/g, "")
             .replace(/[^0-9A-Za-z\u00C0-\u1EF9]+/g, "")
             .toLowerCase();

const theoDoi = new Map(), theoTitle = new Map();
for (const r of BANG) {
    if (r.doi) theoDoi.set(r.doi, r.date);
    if (r.title) theoTitle.set(r.title, r.date);
}

const items = await Zotero.Items.getAll(Zotero.Libraries.userLibraryID);
let dienMoi = 0, daCo = 0, khongHopLe = 0, khongKhop = 0;

for (const item of items) {
    if (!item.isRegularItem()) continue;

    const doi = (item.getField("DOI") || "").toLowerCase().trim();
    let ngay = doi ? theoDoi.get(doi) : undefined;
    if (!ngay) ngay = theoTitle.get(chuanHoa(item.getField("title")));
    if (!ngay) { khongKhop++; continue; }

    if (!Zotero.ItemFields.isValidForType(
            Zotero.ItemFields.getID("accessDate"), item.itemTypeID)) {
        khongHopLe++; continue;
    }
    if ((item.getField("accessDate") || "").trim()) { daCo++; continue; }

    item.setField("accessDate", ngay);
    await item.saveTx();
    dienMoi++;
}

return ["da dien moi        : " + dienMoi,
        "da co san          : " + daCo,
        "kieu muc khong co o Accessed: " + khongHopLe,
        "khong khop trong .bib       : " + khongKhop].join("\n");
