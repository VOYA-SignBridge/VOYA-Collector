#!/usr/bin/env python3
"""Đo độ trễ API — bảng chính cho Chương 4.

    python scripts/measure_api_latency.py --base http://127.0.0.1:8020 \
        --token "$TOKEN" -n 1000 --runs 3 --warmup 50 \
        --json docs/00-thesis/MEASUREMENT_api_latency.json

Giao thức
=========
    khởi động   50 lượt, KHÔNG tính
    đo          1000 lượt / điểm cuối / lượt chạy
    đồng thời   1  (đây là độ trễ CƠ SỞ, không phải phép thử tải)
    lặp lại     3 lượt chạy độc lập
    công bố     p50 / p95 / p99 / min / max / trung bình, cho TỪNG lượt,
                rồi lấy trung vị của ba giá trị

Vì sao giữ ba lượt riêng thay vì gộp 3000 mẫu
==============================================
Gộp lại sẽ giấu mất một lượt bất thường. Nếu lượt hai chậm gấp đôi vì máy đang
bận việc khác, tổng mẫu vẫn cho một con số trông hợp lý và không ai biết. Ba giá
trị nằm cạnh nhau thì sự bất thường tự lộ ra, và trung vị của ba thì không bị
một lượt hỏng kéo đi.

Vì sao KHÔNG có "hệ số quy đổi" giữa môi trường test và sản xuất
================================================================
Thời gian đáp ứng không tỉ lệ tuyến tính theo số worker, và các điểm cuối có cấu
trúc xử lý khác nhau: `/health` gần như không chạm CSDL, `/billing/me` chạy tám
câu đếm. Pool kết nối, bộ đệm, bộ lập lịch, tải nền và kích thước dữ liệu đều
khác. Lấy tỉ lệ từ hai điểm cuối rồi nhân cho các điểm cuối khác sẽ biến một phép
ĐO thành một phép ƯỚC LƯỢNG, và không còn cách nào nói cho người đọc biết ranh
giới đó nằm ở đâu.

Nên sản xuất chỉ được dùng để ĐỐI CHIẾU, ở hai đường công khai read-only, và kết
quả chỉ được diễn giải là "khác biệt quan sát được giữa hai môi trường".

Vì sao nới giới hạn tần suất là CẤU HÌNH MÔI TRƯỜNG ĐO, không phải tắt cơ chế
=============================================================================
Backend test đặt trần rất cao để 429 không bào mỏng cỡ mẫu. Điều này phải được
ghi vào artifact như một thuộc tính của môi trường. Nó KHÔNG phải là "tắt rate
limit rồi coi như nó không tồn tại": trần thật vẫn đang chạy trên sản xuất, và
một bảng độ trễ không nói gì về việc hệ thống chịu tải được bao nhiêu.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlsplit
from typing import Optional

#: Ba LỚP đường đi, không trộn vào nhau. Mỗi lớp trả lời một câu khác nhau.
#: Tên đường lấy từ `/openapi.json` của chính máy chủ — xem chú thích ở
#: `adversarial_isolation.kiem_duong_dan` về cái giá của việc đoán theo trí nhớ.
LOP = {
    "cong_khai": [
        "/health",
        "/api/v1/billing/plans",
    ],
    "xac_thuc_doc": [
        "/api/v1/auth/me",
        "/api/v1/billing/me",
    ],
    "theo_tenant": [
        "/api/v1/vocabulary/registry",
        "/api/v1/training/dataset-info",
        "/api/v1/classes/list",
    ],
}


def _bay_gio() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _percentile(da_sap: list[float], q: float) -> float:
    """Nearest-rank trên dãy ĐÃ sắp xếp — luôn trả về một giá trị QUAN SÁT ĐƯỢC."""
    if not da_sap:
        return float("nan")
    k = max(0, min(len(da_sap) - 1, int(round(q * len(da_sap) + 0.5)) - 1))
    return da_sap[k]


class Khach:
    """Khách HTTP TÁI DÙNG KẾT NỐI (keep-alive).

    Vì sao không dùng `urllib.urlopen` mỗi lượt
    -------------------------------------------
    `urlopen` mở một kết nối TCP MỚI cho từng yêu cầu. Giữ kết nối thì gần với
    khách thật hơn — trình duyệt và mọi thư viện HTTP hiện đại đều làm vậy — và
    bỏ được chi phí bắt tay khỏi mỗi lượt đo.

    Đổi lại, con số đo được KHÔNG còn bao gồm chi phí bắt tay TCP. Điều đó phải
    nằm trong phần mô tả giao thức, vì nó đổi Ý NGHĨA của phép đo chứ không chỉ
    đổi giá trị.

    KHÔNG phải để sửa 213 lượt lỗi truyền ngày 15/08/2026
    ------------------------------------------------------
    Giả thuyết đầu tiên là cạn dải cổng tạm trên Windows (`TIME_WAIT` 120 giây,
    dải 16.384 cổng). Giả thuyết ấy **đã bị bác bỏ**: đối chiếu mốc thời gian
    cho thấy 213 lượt hỏng trùng đúng thời điểm container `voya_backend_iso`
    được dựng lại (16:54:14) trong khi lượt đo kết thúc lúc 16:57:37, và toàn bộ
    lỗi rơi vào một lượt chạy duy nhất của điểm cuối đang đo lúc đó.

    Ghi lại ở đây vì hai con số kia *tương thích* với hiện tượng nhưng không
    chứng minh quan hệ nhân quả, và một lời giải nghe hợp lý mà không có bằng
    chứng là thứ khó gỡ nhất về sau. Chốt chặn đúng cho tai nạn ấy là so vân tay
    container trước/sau lượt đo, không phải keep-alive.
    """

    def __init__(self, base: str, token: Optional[str], timeout: float):
        parts = urlsplit(base)
        self._host = parts.hostname or "127.0.0.1"
        self._port = parts.port or (443 if parts.scheme == "https" else 80)
        self._https = parts.scheme == "https"
        self._timeout = timeout
        self._hdr = {"Accept": "*/*", "Connection": "keep-alive"}
        if token:
            self._hdr["Authorization"] = f"Bearer {token}"
        self.so_lan_noi_lai = 0
        self._conn = None
        self._noi()

    def _noi(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        cls = HTTPSConnection if self._https else HTTPConnection
        self._conn = cls(self._host, self._port, timeout=self._timeout)

    def goi(self, path: str) -> tuple[float, int, int]:
        """-> (mili giây, mã HTTP, số byte). Mã 0 = lỗi tầng dưới."""
        bat_dau = time.perf_counter()
        try:
            self._conn.request("GET", path, headers=self._hdr)
            resp = self._conn.getresponse()
            # Đọc HẾT thân trước khi bấm giờ dừng: dừng ngay sau header sẽ bỏ
            # sót phần máy chủ tuần tự hoá kết quả — với `/billing/me` đó là
            # phần đắt nhất. Đọc hết cũng là điều kiện để dùng lại kết nối.
            than = resp.read()
            return (time.perf_counter() - bat_dau) * 1000.0, resp.status, len(than)
        except Exception:
            # Máy chủ có quyền đóng kết nối giữ sẵn bất cứ lúc nào; nối lại rồi
            # tính lượt này là hỏng, KHÔNG thử lại — thử lại sẽ giấu mất tần
            # suất thật của sự cố.
            self.so_lan_noi_lai += 1
            self._noi()
            return (time.perf_counter() - bat_dau) * 1000.0, 0, 0

    def goi_than(self, path: str) -> tuple[int, bytes]:
        """Như `goi` nhưng trả cả THÂN. Chỉ dùng cho preflight, không dùng khi đo."""
        try:
            self._conn.request("GET", path, headers=self._hdr)
            resp = self._conn.getresponse()
            return resp.status, resp.read()
        except Exception:
            self.so_lan_noi_lai += 1
            self._noi()
            return 0, b""

    def dong(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


def mot_luot(base: str, path: str, *, n: int, token: Optional[str],
             timeout: float, warmup: int) -> dict:
    """MỘT lượt chạy độc lập cho MỘT điểm cuối, đồng thời = 1.

    Kết nối được mở MỘT lần cho cả lượt và dùng lại — xem `Khach`.
    """
    khach = Khach(base, token, timeout)

    for _ in range(warmup):
        khach.goi(path)

    ms: list[float] = []
    phan_loai = {"2xx": 0, "4xx_cho_doi": 0, "4xx_bat_ngo": 0, "5xx": 0, "timeout": 0}
    # Đếm theo TỪNG mã bên cạnh phép phân loại. Một lượt chạy 1000 lượt gọi ra
    # đúng một "4xx bất ngờ" thì phép phân loại nói được là có chuyện, nhưng
    # không nói được chuyện gì — mà nguyên tắc công bố lại đòi giải thích được
    # từng lượt hỏng. Không có dòng này thì phải chạy lại cả lượt để đoán.
    ma_dem: dict[str, int] = {}
    byte_cuoi = 0
    for _ in range(n):
        t, ma, sz = khach.goi(path)
        ma_dem[str(ma)] = ma_dem.get(str(ma), 0) + 1
        if 200 <= ma < 300:
            phan_loai["2xx"] += 1
            ms.append(t)
            byte_cuoi = sz
        elif ma == 0:
            phan_loai["timeout"] += 1
        elif ma == 429:
            # 429 là hành vi ĐÚNG của nền tảng nhưng KHÔNG phải một lượt phục
            # vụ; để nó vào dãy độ trễ sẽ đo thời gian bị từ chối.
            phan_loai["4xx_cho_doi"] += 1
        elif 400 <= ma < 500:
            phan_loai["4xx_bat_ngo"] += 1
        elif ma >= 500:
            phan_loai["5xx"] += 1

    khach.dong()
    ms.sort()

    # Một phân vị chỉ có nghĩa khi ĐUÔI của nó có đủ quan sát đứng sau. Yêu cầu
    # tối thiểu 5 quan sát trong đuôi:
    #     p95 -> đuôi 5%  -> cần  100 lượt phục vụ
    #     p99 -> đuôi 1%  -> cần  500 lượt phục vụ
    # Với n = 1000 thì p99 tựa trên 10 quan sát cuối, đủ để công bố. Với 181
    # lượt phục vụ (đường sản xuất bị 429 bào mỏng) thì p99 tựa trên 2 quan sát
    # — in nó ra bảng luận văn là trình bày một con số của gần như một phép đo
    # đơn lẻ như thể nó là một phân vị.
    def _pct(q: float, can: int) -> float:
        return _percentile(ms, q) if len(ms) >= can else float("nan")

    return {
        "n_do": n,
        "n_phuc_vu": len(ms),
        "byte_than": byte_cuoi,
        "phan_loai": phan_loai,
        "ma_dem": ma_dem,
        "so_lan_noi_lai": khach.so_lan_noi_lai,
        "p50": _pct(0.50, 10),
        "p95": _pct(0.95, 100),
        "p99": _pct(0.99, 500),
        "min": ms[0] if ms else float("nan"),
        "max": ms[-1] if ms else float("nan"),
        "trung_binh": st.fmean(ms) if ms else float("nan"),
    }


def van_tay_container(ten: Optional[str]) -> Optional[str]:
    """Vân tay của container phục vụ lượt đo, để so TRƯỚC và SAU.

    Chốt chặn cho đúng tai nạn ngày 15/08/2026: container bị dựng lại GIỮA một
    lượt benchmark, và 213 lượt hỏng đi thẳng vào bảng kết quả như thể là thuộc
    tính của máy chủ. Một container sập rồi lên lại trong 40 giây thì không để
    lại dấu vết nào trong bảng số — trừ khi có người so vân tay.

    Gồm id, thời điểm khởi động, ảnh, vài biến cấu hình quyết định, và lệnh
    chạy. KHÔNG gồm giờ hiện tại: vân tay phải giống nhau khi không có gì đổi.
    """
    if not ten:
        return None
    # Lọc biến môi trường ở PYTHON, không ở Go template: `hasPrefix` không có
    # trong mọi phiên bản `docker inspect`, và một template hỏng trả về chuỗi
    # rỗng — tức "không đọc được vân tay" cho mọi lượt chạy, im lặng.
    try:
        r = subprocess.run(["docker", "inspect", ten], capture_output=True,
                           text=True, timeout=20)
        d = json.loads(r.stdout)[0]
    except Exception:
        return None

    quan_tam = ("DATASET_ROOT=", "DATABASE_URL=", "RATE_LIMIT_CATALOG_PER_HOUR=")
    env = sorted(e for e in (d.get("Config", {}).get("Env") or [])
                 if e.startswith(quan_tam))
    phan = [
        d.get("Id", ""),
        (d.get("State") or {}).get("StartedAt", ""),
        d.get("Image", ""),
        ";".join(env),
        " ".join((d.get("Config") or {}).get("Cmd") or []),
    ]
    return "|".join(phan)


def preflight(base: str, token: Optional[str], paths: list[str],
              timeout: float) -> dict:
    """Chụp QUY MÔ phản hồi trước khi đo.

    `/classes/list` đã từng trả 22 byte (danh mục rỗng) rồi 2.154 byte (bốn lớp)
    trên cùng một URL, chỉ vì một thí nghiệm khác mount cây dataset. Bảng độ trễ
    không hề thay đổi hình dạng. "12 ms" mà không kèm "cho danh sách bao nhiêu
    lớp" là một con số không so sánh được với chính nó ở lượt chạy sau.
    """
    khach = Khach(base, token, timeout)
    ra = {}
    for p in paths:
        ma, than = khach.goi_than(p)
        muc = None
        if 200 <= ma < 300 and than:
            try:
                d = json.loads(than)
                if isinstance(d, list):
                    muc = len(d)
                elif isinstance(d, dict):
                    # `{"count": n, "items": [...]}` và các biến thể quen thuộc.
                    for k in ("count", "total"):
                        if isinstance(d.get(k), int):
                            muc = d[k]
                            break
                    if muc is None:
                        for k in ("items", "results", "data"):
                            if isinstance(d.get(k), list):
                                muc = len(d[k])
                                break
            except Exception:
                muc = None
        ra[p] = {"status": ma, "byte": len(than), "so_muc": muc}
    khach.dong()
    return ra


def moi_truong(base: str, extra: dict) -> dict:
    md = {"base": base, "thoi_diem": _bay_gio()}
    md["git_commit"] = os.environ.get("VOYA_GIT_COMMIT") or None
    if md["git_commit"] is None:
        try:
            md["git_commit"] = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                timeout=10).stdout.strip() or None
        except Exception:
            pass
    md["git_ban"] = os.environ.get("VOYA_GIT_DIRTY") == "1"

    # Cùng khiếm khuyết đã vá ở `adversarial_isolation.py`: chạy trong container
    # thì không có `.git`, cả hai đường lấy phiên bản cùng hụt, và artefact mang
    # `git_commit: null` mà không ai để ý. Ở đây chưa có cờ công bố để hạ, nên
    # ít nhất phải kêu — một dòng cảnh báo còn đọc được, `null` trong tệp JSON
    # thì không.
    if md["git_commit"] is None:
        print("[CANH BAO] khong xac dinh duoc phien ban ma: artefact se mang "
              "git_commit=null va KHONG truy lai duoc luot do nay ung voi ma "
              "nao. Dat VOYA_GIT_COMMIT truoc khi chay.", file=sys.stderr)

    md.update(extra)
    return md


def _ms(v: float) -> str:
    return "     —" if v != v else f"{v:6.1f}"


def main(argv: Optional[list[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="Đo độ trễ API (chỉ đường đọc).")
    # 127.0.0.1 chứ KHÔNG phải localhost: cổng chỉ mở trên IPv4, còn `localhost`
    # phân giải ra `::1` trước và mỗi lượt phải chờ hết hạn rồi mới lùi. Đã đo
    # được p50 = 2063 ms cho `/health` vì lỗi này — gấp 29 lần con số thật.
    ap.add_argument("--base", default="http://127.0.0.1:8020")
    ap.add_argument("--token", default=None)
    ap.add_argument("-n", type=int, default=1000, help="số lượt ĐO mỗi lượt chạy")
    ap.add_argument("--runs", type=int, default=3, help="số lượt chạy độc lập")
    ap.add_argument("--warmup", type=int, default=50)
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--lop", action="append", choices=sorted(LOP), dest="lops")
    ap.add_argument("--endpoint", action="append", dest="endpoints")
    ap.add_argument("--nhan", default="test", help="nhãn môi trường ghi vào artifact")
    ap.add_argument("--mo-ta-moi-truong", default="",
                    help="JSON mô tả môi trường, nhúng nguyên vào artifact")
    ap.add_argument("--container", default=None,
                    help="tên container phục vụ lượt đo; vân tay được so trước "
                         "và sau, khác nhau thì lượt đo bị đánh dấu INVALIDATED")
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    if args.endpoints:
        muc = [("tuy_chon", p) for p in args.endpoints]
    else:
        chon = args.lops or sorted(LOP)
        muc = [(lop, p) for lop in chon for p in LOP[lop]]

    vt_truoc = van_tay_container(args.container)
    pf = preflight(args.base, args.token, [p for _, p in muc], args.timeout)

    print(f"base={args.base}  n={args.n}  runs={args.runs}  warmup={args.warmup}  "
          f"đồng thời=1  keep-alive=bật")
    if args.container:
        print(f"container={args.container}  vân tay={'có' if vt_truoc else 'KHÔNG ĐỌC ĐƯỢC'}")
    print("preflight (quy mô workload):  "
          + "  ".join(f"{p.rsplit('/', 1)[-1] or p}={v['so_muc'] if v['so_muc'] is not None else v['byte']}"
                      + ("" if v["so_muc"] is None else " mục")
                      for p, v in pf.items()))
    print(f"{'lớp':<13}{'điểm cuối':<32}{'lượt':>5}{'phục vụ':>8}"
          f"{'p50':>8}{'p95':>8}{'p99':>8}{'byte':>7}")
    print("-" * 89)

    ket: list[dict] = []
    for lop, path in muc:
        cac_luot = []
        for _ in range(args.runs):
            cac_luot.append(mot_luot(args.base, path, n=args.n, token=args.token,
                                     timeout=args.timeout, warmup=args.warmup))
        # Trung vị của BA giá trị, không phải phân vị của 3000 mẫu gộp.
        #
        # NaN (phân vị bị chặn vì thiếu mẫu) phải LAN RA, không được lặng lẽ bị
        # nuốt: `st.median` sắp xếp, mà NaN phá quan hệ thứ tự nên kết quả tuỳ
        # thuộc vị trí NaN trong danh sách. Một lượt bị chặn thì cả con số gộp
        # cũng không công bố được.
        def _gom(khoa: str) -> float:
            gt = [r[khoa] for r in cac_luot]
            return float("nan") if any(v != v for v in gt) else st.median(gt)

        gom = {k: _gom(k) for k in ("p50", "p95", "p99", "min", "max", "trung_binh")}
        ban_ghi = {"lop": lop, "path": path, "cac_luot": cac_luot, "trung_vi_3_luot": gom}
        ket.append(ban_ghi)
        pv = sum(r["n_phuc_vu"] for r in cac_luot)
        print(f"{lop:<13}{path:<32}{args.n * args.runs:>5}{pv:>8}"
              f"{_ms(gom['p50']):>8}{_ms(gom['p95']):>8}{_ms(gom['p99']):>8}"
              f"{cac_luot[-1]['byte_than']:>7}")

    # Ba loại hỏng, KHÔNG gộp — vì chúng nói về ba thứ khác nhau:
    #
    #   lỗi ỨNG DỤNG   4xx bất ngờ, 5xx. Máy chủ đã nhận yêu cầu và trả lời sai.
    #                  Đây là bằng chứng về hệ thống, và chặn công bố tuyệt đối.
    #   lỗi TRUYỀN     mã 0: kết nối đứt/hết hạn trước khi có phản hồi. Mỗi lượt
    #                  gọi mở một kết nối TCP mới qua cổng chuyển tiếp của
    #                  Docker; một cú đứt trong hai vạn lượt nói về đường mạng
    #                  của MÁY ĐO, không nói gì về máy chủ.
    #   429            trần tần suất — hành vi đúng, chỉ bào mỏng cỡ mẫu.
    #
    # Bản trước gộp cả ba vào một con số "lỗi thật" và chặn công bố vì đúng một
    # cú đứt TCP. Cám dỗ khi đó là chạy lại cho tới khi số đẹp — tức là chọn
    # lượt chạy theo kết quả, cách nhanh nhất để có một bảng số vô nghĩa. Tách
    # ra thì không cần chạy lại lần nào: tỉ lệ lỗi truyền được ghi thẳng vào
    # artifact và người đọc tự thấy nó nhỏ tới đâu.
    loi_ung_dung = sum(r["phan_loai"]["4xx_bat_ngo"] + r["phan_loai"]["5xx"]
                       for b in ket for r in b["cac_luot"])
    loi_truyen = sum(r["phan_loai"]["timeout"] for b in ket for r in b["cac_luot"])
    bi_chan = sum(r["phan_loai"]["4xx_cho_doi"] for b in ket for r in b["cac_luot"])
    tong_luot = args.n * args.runs * len(muc)

    # Vân tay SAU. Khác vân tay trước nghĩa là môi trường đo đã đổi giữa chừng —
    # container dựng lại, cấu hình đổi — và mọi phân vị bên trên nói về một hỗn
    # hợp hai môi trường. Không tổng hợp, đánh dấu INVALIDATED.
    vt_sau = van_tay_container(args.container)
    trang_thai = "OK"
    if args.container:
        if vt_truoc is None or vt_sau is None:
            trang_thai = "KHONG_XAC_MINH_DUOC"
        elif vt_truoc != vt_sau:
            trang_thai = "INVALIDATED"

    print()
    if trang_thai == "INVALIDATED":
        print("INVALIDATED: vân tay container ĐỔI giữa lượt đo.")
        print(f"  trước: {vt_truoc}")
        print(f"  sau  : {vt_sau}")
        print("Không tổng hợp phân vị — bảng trên là hỗn hợp của hai môi trường.")
    elif trang_thai == "KHONG_XAC_MINH_DUOC":
        print("[warn] không đọc được vân tay container — không xác minh được là "
              "môi trường đứng yên suốt lượt đo")
    if bi_chan:
        print(f"429 (giới hạn tần suất): {bi_chan} — hành vi đúng, nhưng bào mỏng cỡ mẫu")
    if loi_truyen:
        print(f"lỗi truyền (mã 0): {loi_truyen}/{tong_luot} "
              f"= {100.0 * loi_truyen / tong_luot:.4f}% — nhiễu phía máy đo, "
              f"KHÔNG phải máy chủ trả lỗi")
    if loi_ung_dung:
        print(f"CẢNH BÁO: {loi_ung_dung} lượt lỗi ỨNG DỤNG (4xx bất ngờ / 5xx) — "
              f"bảng trên chưa dùng được")

    if args.json:
        extra = json.loads(args.mo_ta_moi_truong) if args.mo_ta_moi_truong else {}
        extra["nhan"] = args.nhan
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({
                "moi_truong": moi_truong(args.base, extra),
                "giao_thuc": {
                    "warmup": args.warmup, "n_moi_luot": args.n,
                    "so_luot": args.runs, "dong_thoi": 1,
                    "gom_ket_qua": "trung vị của 3 lượt, KHÔNG gộp mẫu",
                },
                "khong_lam": [
                    "KHÔNG có hệ số quy đổi test→sản xuất: độ trễ không tỉ lệ "
                    "tuyến tính theo số worker và mỗi điểm cuối có cấu trúc xử "
                    "lý khác nhau. Số của hai môi trường chỉ được đặt cạnh nhau.",
                    "KHÔNG phải phép thử cô lập hiệu năng: chứng minh điều đó "
                    "đòi hỏi tạo tải ở tenant A rồi quan sát tenant B.",
                ],
                "measurement_status": trang_thai,
                "container": args.container,
                "van_tay_truoc": vt_truoc,
                "van_tay_sau": vt_sau,
                "keep_alive": True,
                "preflight_workload": pf,
                "ket_qua": ket,
                "tong_luot": tong_luot,
                "loi_ung_dung": loi_ung_dung,
                "loi_truyen": loi_truyen,
                "ty_le_loi_truyen": loi_truyen / tong_luot if tong_luot else 0.0,
                "so_429": bi_chan,
                # Chỉ lỗi ỨNG DỤNG mới chặn công bố. Lỗi truyền được ghi kèm tỉ
                # lệ, không giấu, để người đọc tự đánh giá.
                "cong_bo_duoc": loi_ung_dung == 0 and trang_thai == "OK",
            }, fh, ensure_ascii=False, indent=2)
        print(f"Đã ghi {args.json}")

    if trang_thai == "INVALIDATED":
        return 5
    return 1 if loi_ung_dung else 0


if __name__ == "__main__":
    sys.exit(main())
