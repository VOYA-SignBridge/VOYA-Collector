"""Dựng báo cáo HTML của một lượt kiểm thử từ tệp do các công cụ sinh ra.

    reports/kiem-thu/index.html              các lượt
    reports/kiem-thu/<lượt>/index.html       tổng quan lượt, dọn dẹp, đo nhận dạng
    reports/kiem-thu/<lượt>/ca/<tệp>.html    từng ca: kiểm gì, kết quả trả về

Không phép tính nào ở đây quyết định đạt hay đỏ: chỉ đọc lại thứ công cụ đã ghi.
"""

from __future__ import annotations

import ast
import base64
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "kiem-thu"
h = html.escape

#: Màu trạng thái đã qua validate_palette.js; luôn đi cùng biểu tượng và chữ.
CSS = """
:root{--navy:#1b2a57;--blue:#0e7bc2;--red:#c81e1e;--amber:#e5a800;--ink:#1e293b;--mute:#64748b;--line:#e2e8f0;--bg:#f4f6fa;--card:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Segoe UI",system-ui,sans-serif}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.top{background:var(--navy);color:#fff;padding:12px 0}.top .w{display:flex;justify-content:space-between;align-items:center}
.top b{font-size:15px;letter-spacing:.2px}.top span{color:#c7d2e8;font-size:13px}.top a{color:#c7d2e8}
.w{max-width:1180px;margin:0 auto;padding:0 20px}main.w{padding-top:18px;padding-bottom:40px}
.nav{font-size:13px;color:var(--mute);margin-bottom:10px}
h1{font-size:21px;margin:0;display:flex;align-items:center;gap:10px;flex-wrap:wrap}h1 code{font-size:20px}
details.nhom{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 16px;margin-bottom:8px}details.nhom>summary{cursor:pointer;font-weight:600}details.nhom table{margin-top:8px}
h2{font-size:15px;margin:0 0 10px}.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin-bottom:14px}
.sub{color:var(--mute);font-size:13px}.tile-row{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:12px 0 14px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px}
.tile .n{font-size:22px;white-space:nowrap;font-weight:650;font-variant-numeric:tabular-nums;line-height:1.2}.tile .l{font-size:12px;color:var(--mute)}
.info{display:grid;grid-template-columns:repeat(4,1fr);gap:6px 18px}.info div{min-width:0}.info .l{display:block;font-size:12px;color:var(--mute)}
.info .v{overflow-wrap:anywhere}
table{border-collapse:collapse;width:100%}th{font-size:12px;font-weight:600;color:var(--mute);text-align:left;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}
td{border-bottom:1px solid #eef2f7;padding:7px 8px;vertical-align:top}tr:last-child td{border-bottom:0}
td.so,th.so{text-align:right;font-variant-numeric:tabular-nums}code,pre{font-family:Consolas,"Cascadia Mono",monospace}code{font-size:12.5px}
.badge{display:inline-flex;align-items:center;gap:4px;font-size:12px;font-weight:600;padding:1px 8px;border-radius:999px;white-space:nowrap}
.badge svg{width:12px;height:12px}.b-dat{background:#e1f0fa;color:#0a5f96}.b-do{background:#fde8e8;color:#a31515}.b-bq{background:#fdf3d0;color:#7a5a00}
.bar{display:flex;gap:2px;height:8px;min-width:120px}.bar i{display:block;border-radius:2px;height:8px}.i-dat{background:var(--blue)}.i-do{background:var(--red)}.i-bq{background:var(--amber)}
pre{background:#f6f8fb;border:1px solid var(--line);padding:8px 10px;border-radius:6px;font-size:12px;white-space:pre-wrap;word-break:break-word;margin:4px 0}
.loi{border-left:3px solid var(--red);padding:8px 12px;margin:0 0 10px;background:#fff7f7;border-radius:0 6px 6px 0}
.loi .ten{font-weight:600}.vitri{font-size:12.5px}
details.ca{border-bottom:1px solid #eef2f7}details.ca>summary{cursor:pointer;list-style:none;display:grid;grid-template-columns:46px 84px 1fr 74px 80px;gap:8px;padding:7px 4px;align-items:start}
details.ca>summary::-webkit-details-marker{display:none}details.ca[open]>summary{background:#f6f8fb}
.dau{display:grid;grid-template-columns:46px 84px 1fr 74px 80px;gap:8px;padding:6px 4px;font-size:12px;font-weight:600;color:var(--mute);border-bottom:1px solid var(--line)}
.than{padding:8px 12px 12px 58px}.tieu{font-weight:600;font-size:12.5px;margin-top:10px}.phai{text-align:right;font-variant-numeric:tabular-nums;color:var(--mute);font-size:12.5px}
video,img.anh{max-width:520px;width:100%;border-radius:6px;margin-top:6px;border:1px solid var(--line)}
input,select{font:inherit;padding:6px 8px;border:1px solid #cbd5e1;border-radius:6px;background:#fff}.loc{display:flex;gap:8px;margin-bottom:10px}
@media print{.top,.loc{display:none}}@media(max-width:800px){.tile-row{grid-template-columns:repeat(3,1fr)}.info{grid-template-columns:repeat(2,1fr)}}
"""

#: Nhóm chỉ để đọc cho dễ, xếp theo tên tệp test. Tệp khớp mẫu đầu tiên.
NHOM_TEST = (
    ("Quyền và cách ly tổ chức", r"tenant|rls|isolation|access_gate|authz|role|permission|membership|workspace|boundary"),
    ("Đăng nhập và tài khoản", r"auth|login|cookie|token|otp|password|two_factor|session_life|signup|recover|verification|trial|sudo|account|email"),
    ("Pháp lý và đồng thuận", r"legal|consent"),
    ("Gói, hạn mức, dung lượng", r"plan|quota|billing|subscription|storage|usage|api_key|webhook"),
    ("Huấn luyện và model", r"train|split|manifest|model|checkpoint|promot|registry|realtime|inference|tts|frozen|research|feature|zfix"),
    ("Thu thập và xử lý dữ liệu", r"upload|video|capture|sample|raw|quality|normali|coordinate|augment|label|class|dataset|catalog|moderation|signer"),
    ("Từ vựng", r"vocab|dialect|region|learn"),
    ("Đồng bộ SOT, Drive, Sheets", r"sot|drive|sheet|sync|csv"),
    ("Lược đồ CSDL và migration", r"schema|migrat|db_|init_db|fk|foreign"),
)
NHAN_KQ = {"dat": "Đạt", "do": "ĐỎ", "bo_qua": "Bỏ qua"}
LOP_KQ = {"dat": "dat", "do": "khong", "bo_qua": "bq"}


def _nhom_cua(ten_tep: str) -> str:
    for ten, mau in NHOM_TEST:
        if re.search(mau, ten_tep):
            return ten
    return "Vận hành và phần còn lại"


def _dong_dau(text: str | None) -> str:
    return (text or "").strip().split("\n")[0].strip()


def _doc_jsonl(tep: Path) -> list[dict]:
    if not tep.exists():
        return []
    return [json.loads(d) for d in tep.read_text(encoding="utf-8").splitlines() if d.strip()]


def _mo_ta_pytest() -> tuple[dict, dict]:
    tep_mo_ta: dict = {}
    ham_mo_ta: dict = {}
    for f in (ROOT / "backend/tests").glob("test_*.py"):
        try:
            cay = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        tep_mo_ta[f.stem] = _dong_dau(ast.get_docstring(cay))
        for n in ast.walk(cay):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"):
                ham_mo_ta[(f.stem, n.name)] = _dong_dau(ast.get_docstring(n))
    tai_lieu = ROOT / "docs/08-testing/TESTING.md"
    if tai_lieu.exists():
        for dong in tai_lieu.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\|\s*`(test_\w+)\.py`\s*\|\s*(.+?)\s*\|$", dong)
            if m:
                tep_mo_ta[m.group(1)] = m.group(2)
    return tep_mo_ta, ham_mo_ta


def _ca_pytest(thu_muc: Path) -> list[dict]:
    tep_mo_ta, ham_mo_ta = _mo_ta_pytest()
    ca = []
    for c in _doc_jsonl(thu_muc / "backend-ket-qua.jsonl") + _doc_jsonl(thu_muc / "drive-ket-qua.jsonl"):
        duong, _, ten = c["id"].partition("::")
        ten_tep = Path(duong).stem
        ham = ten.split("::")[-1].split("[")[0]
        gd = c.get("giai_doan", {})
        kq = "do" if "failed" in gd.values() else "bo_qua" if "skipped" in gd.values() else "dat"
        ca.append({
            "nhom": _nhom_cua(ten_tep), "tep": ten_tep, "tep_mo_ta": tep_mo_ta.get(ten_tep, ""),
            "ten": ten, "mo_ta": ham_mo_ta.get((ten_tep, ham), ""), "kq": kq,
            "ly_do": c.get("loi") or c.get("bo_qua") or "", "giay": c.get("giay", 0),
            "so_sanh": [{"tieu_de": x["bieu_thuc"], "gia_tri": x["ket_qua"]} for x in c.get("so_sanh", [])],
            "http": c.get("http", []), "log": c.get("log", ""),
            "luc": c.get("luc", ""), "vi_tri": c.get("vi_tri", ""), "thong_bao": c.get("thong_bao", ""),
        })
    return ca


def _ca_vitest(thu_muc: Path) -> list[dict]:
    tep = thu_muc / "frontend.json"
    if not tep.exists():
        return []
    chi_tiet = {(Path(c["tep"]).name, c["ten"]): c for c in _doc_jsonl(thu_muc / "frontend-ket-qua.jsonl")}
    ca = []
    for s in json.loads(tep.read_text(encoding="utf-8")).get("testResults", []):
        ten_tep = Path(s.get("name", "")).name
        for a in s.get("assertionResults", []):
            trang = a.get("status")
            kq = "dat" if trang == "passed" else "do" if trang == "failed" else "bo_qua"
            ct = chi_tiet.get((ten_tep, a.get("fullName", "")), {})
            ca.append({
                "nhom": "Giao diện", "tep": ten_tep, "tep_mo_ta": "", "ten": a.get("title", ""),
                "mo_ta": " › ".join(a.get("ancestorTitles", [])), "kq": kq,
                "ly_do": " ".join(a.get("failureMessages", []))[:2000], "giay": (a.get("duration") or 0) / 1000,
                "so_sanh": [{"tieu_de": x["kiem"], "gia_tri": f"mong đợi: {x['mong_doi']}\nthực tế: {x['thuc_te']}"}
                            for x in ct.get("so_sanh", [])],
                "so_phep_so": ct.get("so_phep_so"), "http": [], "log": "",
            })
    return ca


def _thong_bao_playwright(van_ban: str) -> str:
    """Dòng lỗi cùng giá trị mong đợi và thực tế, thứ người đọc cần đầu tiên."""
    cac_dong = [d.strip() for d in _bo_ansi(van_ban).splitlines() if d.strip()]
    giu = [d for d in cac_dong if d.startswith(("Expected", "Received"))]
    return " · ".join(cac_dong[:1] + giu)[:400]


def _ca_playwright(thu_muc: Path) -> list[dict]:
    tep = thu_muc / "trinh-duyet.json"
    if not tep.exists():
        return []
    ca = []

    def duyet(suite, ten_tep):
        ten_tep = suite.get("file") or ten_tep
        for spec in suite.get("specs", []):
            for t in spec.get("tests", []):
                kq = (t.get("results") or [{}])[-1]
                tep_dinh = {a.get("name"): a for a in kq.get("attachments", [])}

                def duong(ten):
                    p = (tep_dinh.get(ten) or {}).get("path")
                    return os.path.relpath(p, thu_muc).replace(os.sep, "/") if p else ""

                api = []
                body = (tep_dinh.get("ket-qua-api") or {}).get("body")
                if body:
                    api = json.loads(base64.b64decode(body).decode("utf-8"))
                loi = kq.get("error") or {}
                trang = kq.get("status")
                noi = loi.get("location") or {}
                vi_tri = f"{noi['file']}:{noi['line']}" if noi.get("file") else ""
                luc = ""
                if kq.get("startTime"):
                    luc = datetime.fromisoformat(kq["startTime"].replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
                ca.append({
                    "nhom": "Trình duyệt thật", "tep": Path(ten_tep or "").name, "tep_mo_ta": "",
                    "ten": spec.get("title", ""), "mo_ta": "",
                    "kq": "dat" if spec.get("ok") and trang == "passed" else "bo_qua" if trang == "skipped" else "do",
                    "ly_do": str(loi.get("message") or "")[:2000], "giay": (kq.get("duration") or 0) / 1000,
                    "so_sanh": [], "http": api, "log": "", "luc": luc, "vi_tri": vi_tri,
                    "thong_bao": _thong_bao_playwright(str(loi.get("message") or "")),
                    "video": duong("video"), "anh": duong("screenshot"),
                })
        for con in suite.get("suites", []):
            duyet(con, ten_tep)

    for suite in json.loads(tep.read_text(encoding="utf-8")).get("suites", []):
        duyet(suite, "")
    return ca


ICON = {
    "dat": '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M3 8.5 6.5 12 13 4.5"/></svg>',
    "do": '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>',
    "bo_qua": '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M3.5 8h9"/></svg>',
}
LOP_BADGE = {"dat": "b-dat", "do": "b-do", "bo_qua": "b-bq"}


def _badge(kq: str, nhan: str | None = None) -> str:
    return f'<span class="badge {LOP_BADGE[kq]}">{ICON[kq]}{h(nhan or NHAN_KQ[kq])}</span>'


def _thoi_luong(giay: float) -> str:
    giay = float(giay or 0)
    if giay < 60:
        return f"{giay:.2f} s".replace(".", ",") if giay < 10 else f"{giay:.0f} s"
    return f"{int(giay // 60)} phút {int(giay % 60)} giây"


def _khung(tieu_de: str, than: list[str], ve: str = "") -> str:
    lien_ket = f'<a href="{ve}">Tất cả lượt chạy</a>' if ve else ""
    return (f"<!doctype html><html lang=vi><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{h(tieu_de)}</title><style>{CSS}</style>"
            f'<div class=top><div class=w><b>CTU.SignBridge · Báo cáo kiểm thử</b><span>{lien_ket}</span></div></div>'
            f'<main class=w>{"".join(than)}</main>')


def _bo_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s or "")


def _vi_tri(c: dict) -> tuple[str, str]:
    """(thông báo lỗi, `tệp:dòng`) của một ca đỏ, từ thứ công cụ đã ghi."""
    if c.get("vi_tri"):
        return c.get("thong_bao") or _dong_dau(c["ly_do"]), c["vi_tri"]
    van_ban = _bo_ansi(c["ly_do"])
    cac_dong = [d[1:].strip() for d in van_ban.splitlines() if d.startswith("E ")]
    thong_bao = " ".join(cac_dong[:3]) or _dong_dau(van_ban)
    khop = re.findall(r"([\w./\\:-]+\.(?:py|tsx?|mjs)):(\d+)", van_ban)
    khop = [m for m in khop if "site-packages" not in m[0] and "node_modules" not in m[0]]
    return thong_bao[:400], f"{khop[-1][0]}:{khop[-1][1]}" if khop else ""


def _mo_tep(vi_tri: str) -> str:
    """Liên kết mở đúng dòng trong VS Code."""
    if not vi_tri:
        return '<span class=sub>Không có vị trí</span>'
    duong, _, dong = vi_tri.rpartition(":")
    rel = re.sub(r"^.*?(?=backend/|frontend/|scripts/)", "", duong.replace("\\", "/"))
    if rel.startswith("tests/"):
        rel = "backend/" + rel
    dich = (ROOT / rel).as_posix()
    return f'<a class=vitri href="vscode://file/{h(dich)}:{h(dong)}"><code>{h(rel)}:{h(dong)}</code></a>'


def _the_ca(c: dict, stt: int) -> str:
    than = []
    if c["mo_ta"]:
        than.append(f"<div class=tieu>Mục đích</div>{h(c['mo_ta'])}")
    if c["kq"] == "do":
        thong_bao, vi_tri = _vi_tri(c)
        than.append(f'<div class=tieu>Thông báo lỗi</div><pre>{h(thong_bao)}</pre>'
                    f'<div class=tieu>Vị trí</div>{_mo_tep(vi_tri)}'
                    f'<div class=tieu>Chi tiết</div><pre>{h(_bo_ansi(c["ly_do"]))}</pre>')
    elif c["ly_do"]:
        than.append(f"<div class=tieu>Lý do bỏ qua</div><pre>{h(c['ly_do'])}</pre>")
    if c.get("so_sanh"):
        than.append(f"<div class=tieu>Kết quả từng phép so ({len(c['so_sanh'])})</div>")
        than += [f"<pre><b>{h(x['tieu_de'])}</b>\n{h(x['gia_tri'])}</pre>" for x in c["so_sanh"]]
    elif c.get("so_phep_so"):
        than.append(f"<div class=sub>{c['so_phep_so']} phép so</div>")
    if c.get("http"):
        than.append(f"<div class=tieu>API đã gọi và kết quả trả về ({len(c['http'])})</div>")
        for x in c["http"]:
            gui = f"\ngửi: {x['gui']}" if x.get("gui") else ""
            than.append(f"<pre><b>{h(x['phuong_thuc'])} {h(x['duong_dan'])} → {x['ma']}</b>{h(gui)}\n{h(x.get('tra_ve', ''))}</pre>")
    if c.get("log"):
        than.append(f"<div class=tieu>Log</div><pre>{h(c['log'])}</pre>")
    if c.get("video"):
        than.append(f'<div class=tieu>Video</div><video controls preload=none src="../{h(c["video"])}"></video>')
    if c.get("anh"):
        than.append(f'<div class=tieu>Ảnh cuối</div><img class=anh loading=lazy src="../{h(c["anh"])}">')
    if not than:
        than.append("<div class=sub>Ca này không gọi API và không có phép so nào được ghi.</div>")
    mo = " open" if c["kq"] == "do" else ""
    return (f'<details class=ca id="c{stt}" data-kq={c["kq"]}{mo}><summary><span class=sub>{stt}</span>{_badge(c["kq"])}'
            f'<span><code>{h(c["ten"])}</code></span><span class=phai>{h(c.get("luc", ""))}</span>'
            f'<span class=phai>{_thoi_luong(c["giay"])}</span></summary><div class=than>{"".join(than)}</div></details>')


JS_LOC = """<script>
const o=document.getElementById('loc'),k=document.getElementById('kq');
function loc(){const q=o.value.toLowerCase(),v=k.value;
document.querySelectorAll('details.ca').forEach(r=>{r.hidden=!((!q||r.textContent.toLowerCase().includes(q))&&(!v||r.dataset.kq===v))});}
o.oninput=loc;k.onchange=loc;</script>"""


def _ten_tep_html(tep: str) -> str:
    return re.sub(r"[^\w.-]", "_", tep) + ".html"


def _dem(ds: list[dict]) -> dict:
    return {k: sum(c["kq"] == k for c in ds) for k in NHAN_KQ}


def _thanh(d: dict) -> str:
    tong = max(sum(d.values()), 1)
    return "<div class=bar role=img aria-label='" + f"{d['dat']} đạt, {d['do']} đỏ, {d['bo_qua']} bỏ qua'>" + "".join(
        f'<i class="i-{k}" style="width:{d[n] / tong * 100:.2f}%"></i>'
        for k, n in (("dat", "dat"), ("do", "do"), ("bq", "bo_qua")) if d[n]) + "</div>"


def _trang_tep(thu_muc: Path, tep: str, ds: list[dict], ten_luot: str) -> None:
    d = _dem(ds)
    p = [f'<div class=nav><a href="../index.html">Lượt {h(ten_luot)}</a> / {h(ds[0]["nhom"])}</div>',
         f"<h1><code>{h(tep)}</code></h1>"]
    if ds[0]["tep_mo_ta"]:
        p.append(f"<p class=sub>{h(ds[0]['tep_mo_ta'])}</p>")
    p.append(f'<div class=card><div class=sub>{len(ds)} ca · {d["dat"]} đạt · {d["do"]} đỏ · {d["bo_qua"]} bỏ qua · '
             f'{_thoi_luong(sum(c["giay"] for c in ds))}</div>{_thanh(d)}</div><div class=card>'
             '<div class=loc><input id=loc size=44 placeholder="Tìm trong tệp này..."> <select id=kq>'
             '<option value="">Mọi kết quả</option><option value=dat>Đạt</option><option value=do>Đỏ</option>'
             '<option value=bo_qua>Bỏ qua</option></select></div>'
             '<div class=dau><span>#</span><span>Kết quả</span><span>Ca test</span><span class=phai>Lúc chạy</span><span class=phai>Thời gian</span></div>')
    p += [_the_ca(c, i) for i, c in enumerate(ds, 1)]
    p.append("</div>" + JS_LOC)
    (thu_muc / "ca" / _ten_tep_html(tep)).write_text(_khung(tep, p, "../../index.html"), encoding="utf-8")


def _ty_le(x):
    return "—" if x is None else f"{x:.1%}".replace(".", ",")


def _phan_nhan_dang(thu_muc: Path) -> str:
    tep = thu_muc / "nhan-dang.json"
    if not tep.exists():
        return ""
    d = json.loads(tep.read_text(encoding="utf-8"))
    p = ["<div class=card><h2>Đo nhận dạng bằng mẫu thật</h2><p class=sub>Số đo, không tính vào đạt/đỏ. Phát lại tập test qua "
         "dịch vụ realtime; tập test có thể trùng mẫu model đã học nên số đúng có thể lạc quan.</p><table><tr><th>Tình huống</th>"]
    p += [f"<th class=so>{h(m)}</th>" for m in d]
    p.append("</tr>")
    for nhan, khoa in (("Ký đúng, đủ 60 khung: tỉ lệ đúng", "du_60_khung"), ("Cửa sổ 30 khung: tỉ lệ đúng", "cua_so_30_khung"),
                       ("Cửa sổ 15 khung: tỉ lệ đúng", "cua_so_15_khung"), ("Camera chậm một nửa: tỉ lệ đúng", "camera_cham_mot_nua")):
        p.append(f"<tr><td>{nhan}</td>" + "".join(f"<td class=so>{_ty_le(v[khoa]['dung'])} ({v[khoa]['n']} mẫu)</td>" for v in d.values()) + "</tr>")
    for nhan, khoa in (("Tay đứng yên", "tay_dung_yen"), ("Ký từ ngoài model", "ky_tu_ngoai_model")):
        p.append(f"<tr><td>{nhan}: vẫn hiện / vẫn đọc</td>"
                 + "".join(f"<td class=so>{_ty_le(v[khoa]['hien'])} / {_ty_le(v[khoa]['doc'])}</td>" for v in d.values()) + "</tr>")
    p.append("</table></div>")
    return "".join(p)


def _ca_can_soi(ca: list[dict]) -> list[dict]:
    """Ca đạt mà API từ chối dữ liệu gửi (422) và test không hề nhắc tới 422.

    Dấu hiệu của xanh giả: test gửi sai trường, cả hai vế cùng bị từ chối, và phép
    so "giống nhau" đạt mà đường cần kiểm chưa từng chạy. Là gợi ý để đọc, không phải
    kết luận, nên không làm lượt chạy đỏ.
    """
    ket = []
    for c in ca:
        if c["kq"] != "dat" or not c.get("so_sanh"):
            continue
        co_422 = any(x.get("ma") == 422 for x in c.get("http", []))
        nhac = any("422" in x["tieu_de"] or "422" in x["gia_tri"] for x in c["so_sanh"])
        if co_422 and not nhac:
            ket.append(c)
    return ket


def _trich_loi(c: dict, dan: str = "ca/") -> str:
    thong_bao, vi_tri = _vi_tri(c)
    return (f'<div class=loi><div class=ten><a href="{dan}{_ten_tep_html(c["tep"])}">{h(c["tep"])}</a> › <code>{h(c["ten"])}</code></div>'
            f'<div>{h(thong_bao)}</div><div class=vitri>Vị trí: {_mo_tep(vi_tri)}</div></div>')


def dung_luot(thu_muc: Path, r: dict) -> None:
    ca = _ca_pytest(thu_muc) + _ca_vitest(thu_muc) + _ca_playwright(thu_muc)
    (thu_muc / "ca").mkdir(exist_ok=True)
    theo_nhom: dict = {}
    for c in ca:
        theo_nhom.setdefault(c["nhom"], {}).setdefault(c["tep"], []).append(c)
    tong = _dem(ca)
    so_chay = tong["dat"] + tong["do"]
    ten_luot = thu_muc.name
    trang_thai = _badge("dat", "ĐẠT") if r["dat"] else _badge("do", "KHÔNG ĐẠT")
    p = [f'<div class=nav><a href="../index.html">Các lượt chạy</a> / {h(ten_luot)}</div>',
         f"<h1>Lượt kiểm thử {h(ten_luot)} {trang_thai}</h1>",
         "<div class=tile-row>"]
    for nhan, so in (("Tổng số ca", len(ca)), ("Đạt", tong["dat"]), ("Đỏ", tong["do"]), ("Bỏ qua", tong["bo_qua"]),
                     ("Tỉ lệ đạt", _ty_le(tong["dat"] / so_chay if so_chay else None)), ("Thời lượng", _thoi_luong(r["giay"]))):
        p.append(f"<div class=tile><div class=n>{so}</div><div class=l>{nhan}</div></div>")
    p.append("</div><div class=card><h2>Thông tin lượt chạy</h2><div class=info>")
    for nhan, gt in (("Bắt đầu", r["bat_dau"]), ("Kết thúc", r.get("ket_thuc", "—")), ("Kích hoạt", r.get("kich_hoat", "—")),
                     ("Máy chạy", r.get("may", "—")), ("Nhánh", r.get("nhanh", "—")), ("Commit", r["commit"]),
                     ("Tệp chưa commit", r["tep_chua_commit"]), ("Dịch vụ thật dùng", r.get("dich_vu", "Postgres, Redis, worker, trainer, realtime, Drive sandbox"))):
        p.append(f"<div><span class=l>{nhan}</span><span class=v>{h(str(gt))}</span></div>")
    p.append("</div></div>")

    do = [c for c in ca if c["kq"] == "do"]
    if do:
        p.append(f"<div class=card><h2>Ca đỏ ({len(do)})</h2>" + "".join(_trich_loi(c) for c in do[:100]) + "</div>")

    p.append("<div class=card><h2>Các bước</h2><table><tr><th>Bước</th><th>Công cụ</th><th>Kết quả</th><th class=so>Đạt</th>"
             "<th class=so>Đỏ</th><th class=so>Bỏ qua</th><th class=so>Mã thoát</th><th class=so>Thời gian</th></tr>")
    for b in r["buoc"]:
        nhan = f'<a href="{h(b["bao_cao"])}">{h(b["ten"])}</a>' if b.get("bao_cao") else h(b["ten"])
        kq = _badge("dat", "Qua") if b["ma_thoat"] == 0 else _badge("do", "Không qua")
        so = ("<td class=so colspan=3><span class=sub>không đếm theo ca</span></td>" if b["dat"] + b["do"] + b["bo_qua"] == 0
              else f"<td class=so>{b['dat']}</td><td class=so>{b['do']}</td><td class=so>{b['bo_qua']}</td>")
        p.append(f"<tr><td>{nhan}</td><td>{h(b['cong_cu'])}</td><td>{kq}</td>{so}<td class=so>{b['ma_thoat']}</td>"
                 f"<td class=so>{_thoi_luong(b['giay'])}</td></tr>")
    p.append("</table></div>")

    if r.get("don_dep"):
        p.append("<div class=card><h2>Dọn dẹp sau test</h2><table><tr><th>Hạng mục</th><th>Kết quả</th><th>Ghi chú</th></tr>")
        for x in r["don_dep"]:
            p.append(f"<tr><td>{h(x['viec'])}</td><td>{_badge('dat', 'Sạch') if x['ok'] else _badge('do', 'Còn sót')}</td>"
                     f"<td class=sub>{h(x.get('ghi_chu', ''))}</td></tr>")
        p.append("</table></div>")

    p.append(_phan_nhan_dang(thu_muc))

    soi = _ca_can_soi(ca)
    if soi:
        p.append(f"<div class=card><h2>Ca cần soi ({len(soi)})</h2><p class=sub>Đạt, nhưng API trả 422 mà test không nhắc tới: có thể "
                 "test gửi sai dữ liệu nên chưa kiểm được điều nó nói.</p><table><tr><th>Tệp</th><th>Ca test</th></tr>")
        p += [f'<tr><td><a href="ca/{_ten_tep_html(c["tep"])}"><code>{h(c["tep"])}</code></a></td><td><code>{h(c["ten"])}</code></td></tr>' for c in soi[:60]]
        p.append("</table></div>")

    p.append("<div class=card><h2>Kết quả theo nhóm</h2><table><tr><th>Nhóm</th><th class=so>Tệp</th><th class=so>Đạt</th>"
             "<th class=so>Đỏ</th><th class=so>Bỏ qua</th><th>Tỉ lệ</th></tr>")
    for nhom, cac_tep in sorted(theo_nhom.items(), key=lambda x: x[0]):
        d = _dem([c for ds in cac_tep.values() for c in ds])
        neo = re.sub(r"\W+", "-", nhom)
        p.append(f'<tr><td><a href="#{neo}">{h(nhom)}</a></td><td class=so>{len(cac_tep)}</td><td class=so>{d["dat"]}</td>'
                 f'<td class=so>{d["do"]}</td><td class=so>{d["bo_qua"]}</td><td>{_thanh(d)}</td></tr>')
    p.append("</table></div>")

    cham = sorted(ca, key=lambda c: c["giay"], reverse=True)[:10]
    p.append("<div class=card><h2>10 ca chậm nhất</h2><table><tr><th>Tệp</th><th>Ca test</th><th class=so>Thời gian</th></tr>")
    p += [f'<tr><td><a href="ca/{_ten_tep_html(c["tep"])}"><code>{h(c["tep"])}</code></a></td><td><code>{h(c["ten"])}</code></td>'
          f'<td class=so>{_thoi_luong(c["giay"])}</td></tr>' for c in cham]
    p.append("</table></div>")

    for nhom, cac_tep in sorted(theo_nhom.items(), key=lambda x: x[0]):
        neo = re.sub(r"\W+", "-", nhom)
        dn = _dem([c for ds in cac_tep.values() for c in ds])
        p.append(f'<details class=nhom id="{neo}"{" open" if dn["do"] else ""}><summary>{h(nhom)} '
                 f'<span class=sub>{len(cac_tep)} tệp · {dn["dat"]} đạt · {dn["do"]} đỏ · {dn["bo_qua"]} bỏ qua</span></summary>'
                 "<table><tr><th>Tệp test</th><th>Canh gì</th><th>Kết quả</th>"
                 "<th class=so>Đạt</th><th class=so>Đỏ</th><th class=so>Bỏ qua</th><th class=so>Thời gian</th></tr>")
        for tep, ds in sorted(cac_tep.items()):
            _trang_tep(thu_muc, tep, ds, ten_luot)
            d = _dem(ds)
            kq = _badge("do", "Đỏ") if d["do"] else _badge("dat", "Đạt") if d["dat"] else _badge("bo_qua")
            p.append(f'<tr><td><a href="ca/{_ten_tep_html(tep)}"><code>{h(tep)}</code></a></td><td class=sub>{h(ds[0]["tep_mo_ta"])}</td>'
                     f'<td>{kq}</td><td class=so>{d["dat"]}</td><td class=so>{d["do"]}</td><td class=so>{d["bo_qua"]}</td>'
                     f'<td class=so>{_thoi_luong(sum(c["giay"] for c in ds))}</td></tr>')
        p.append("</table></details>")
    p.append("<script>document.querySelectorAll('a[href^=\"#\"]').forEach(a=>a.onclick=()=>{"
             "const d=document.querySelector(a.getAttribute('href'));if(d)d.open=true})</script>")
    (thu_muc / "index.html").write_text(_khung(f"Lượt {ten_luot}", p, "../index.html"), encoding="utf-8")


def trang_tong_hop() -> Path:
    p = ["<h1>Các lượt kiểm thử</h1><p class=sub>Bấm vào một lượt để xem từng ca test và kết quả trả về. Giữ 10 lượt gần nhất.</p>",
         "<div class=card><table><tr><th>Lượt</th><th>Bắt đầu</th><th>Kết quả</th><th class=so>Đạt</th><th class=so>Đỏ</th>"
         "<th class=so>Bỏ qua</th><th>Tỉ lệ</th><th>Dọn dẹp</th><th>Kích hoạt</th><th>Commit</th><th class=so>Thời lượng</th></tr>"]
    for f in sorted(OUT.glob("*/ket-qua.json"), reverse=True):
        r = json.loads(f.read_text(encoding="utf-8"))
        d = {k: sum(b.get(k, 0) for b in r["buoc"]) for k in ("dat", "do", "bo_qua")}
        don = r.get("don_dep") or []
        o_don = "—" if not don else _badge("dat", "Sạch") if all(x["ok"] for x in don) else _badge("do", "Còn sót")
        kq = _badge("dat", "ĐẠT") if r["dat"] else _badge("do", "KHÔNG ĐẠT")
        p.append(f'<tr><td><a href="{h(f.parent.name)}/index.html"><code>{h(f.parent.name)}</code></a></td><td>{h(r["bat_dau"])}</td>'
                 f'<td>{kq}</td><td class=so>{d["dat"]}</td><td class=so>{d["do"]}</td><td class=so>{d["bo_qua"]}</td><td>{_thanh(d)}</td>'
                 f'<td>{o_don}</td><td>{h(r.get("kich_hoat", "—"))}</td><td><code>{h(r["commit"])}</code></td>'
                 f'<td class=so>{_thoi_luong(r["giay"])}</td></tr>')
    p.append("</table></div>")
    trang = OUT / "index.html"
    trang.write_text(_khung("Kiểm thử CTU.SignBridge", p), encoding="utf-8")
    return trang


if __name__ == "__main__":
    # Dựng lại mọi lượt theo mẫu hiện hành, không chạy lại test.
    for tep in sorted(OUT.glob("*/ket-qua.json")):
        dung_luot(tep.parent, json.loads(tep.read_text(encoding="utf-8")))
    print(trang_tong_hop())
