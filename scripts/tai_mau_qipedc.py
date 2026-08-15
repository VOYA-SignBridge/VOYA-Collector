# -*- coding: utf-8 -*-
"""Tải mẫu video công khai của từ điển QIPEDC để làm dữ liệu đo.

Từ điển có **hai** tiền tố mã: `D` (776 mục) và `W` (3.586 mục) — tổng 4.362.
Bản đầu của script này dò mù D0001–D0620 nên bỏ sót toàn bộ nhánh `W`.

Script nay lấy danh mục thật qua điểm cuối của chính trang từ điển:

    POST /dictionary/getAll   body: group=20&text=

trả về **toàn bộ** 4.362 mục trong một lượt (trang web phân trang phía trình
duyệt), mỗi mục gồm `_id`, `word`, `description`, `tl` (từ loại). Nhờ đó không
cần Puppeteer và không phải dò 404.

    .venv/Scripts/python.exe scripts/tai_mau_qipedc.py --thu-muc <dir> --gioi-han-mb 2800
    .venv/Scripts/python.exe scripts/tai_mau_qipedc.py --thu-muc <dir> --chi-danh-muc

Chứng chỉ TLS của máy chủ hết hạn 16/07/2026; script GHIM vân tay SHA-256 thay
vì tắt xác minh — bỏ qua đúng phần hạn dùng, giữ nguyên phần danh tính.
"""
import argparse, hashlib, http.client, json, os, ssl, sys, time, urllib.parse

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MAY_CHU = "qipedc.moet.gov.vn"
TEN_DANH_MUC = "qipedc_danhmuc.json"


def van_tay():
    der = ssl.PEM_cert_to_DER_cert(
        ssl.get_server_certificate((MAY_CHU, 443), timeout=20))
    return hashlib.sha256(der).hexdigest()


def ket_noi(vt):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    c = http.client.HTTPSConnection(MAY_CHU, 443, timeout=60, context=ctx)
    c.connect()
    if hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest() != vt:
        c.close()
        raise SystemExit("DỪNG: vân tay chứng chỉ đổi giữa chừng.")
    return c


def lay_danh_muc(vt):
    c = ket_noi(vt)
    try:
        c.request("POST", "/dictionary/getAll",
                  body=urllib.parse.urlencode({"group": "20", "text": ""}),
                  headers={"User-Agent": "CTU-SignBridge thesis measurement",
                           "X-Requested-With": "XMLHttpRequest",
                           "Content-Type":
                               "application/x-www-form-urlencoded; charset=UTF-8"})
        r = c.getresponse()
        d = json.loads(r.read().decode("utf-8"))
    finally:
        c.close()
    return d.get("data", d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thu-muc", required=True)
    ap.add_argument("--gioi-han-mb", type=int, default=2800)
    ap.add_argument("--nghi", type=float, default=0.2)
    ap.add_argument("--tien-to", default=None,
                    help="chỉ tải mã bắt đầu bằng tiền tố này, ví dụ W")
    ap.add_argument("--chi-danh-muc", action="store_true",
                    help="chỉ lấy danh mục, không tải video")
    a = ap.parse_args()
    os.makedirs(a.thu_muc, exist_ok=True)
    han = a.gioi_han_mb * 1024 * 1024

    vt = van_tay()
    print("Vân tay chứng chỉ: %s…" % vt[:24], flush=True)

    dm = lay_danh_muc(vt)
    p_dm = os.path.join(a.thu_muc, TEN_DANH_MUC)
    json.dump(dm, open(p_dm, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Danh mục: %d mục -> %s" % (len(dm), p_dm), flush=True)
    if a.chi_danh_muc:
        return 0

    da_co = {f[:-4] for f in os.listdir(a.thu_muc) if f.endswith(".mp4")}
    tong = sum(os.path.getsize(os.path.join(a.thu_muc, f))
               for f in os.listdir(a.thu_muc) if f.endswith(".mp4"))
    can = [x["_id"] for x in dm if x.get("_id") and x["_id"] not in da_co
           and (not a.tien_to or x["_id"].startswith(a.tien_to))]
    print("Đã có %d tệp (%.1f MB). Cần tải %d. Hạn %d MB."
          % (len(da_co), tong / 1048576, len(can), a.gioi_han_mb), flush=True)

    moi = hong = 0
    for ma in can:
        if tong >= han:
            print("\nChạm hạn %d MB — dừng." % a.gioi_han_mb, flush=True)
            break
        c = None
        try:
            c = ket_noi(vt)
            c.request("GET", "/videos/%s.mp4" % ma,
                      headers={"User-Agent": "CTU-SignBridge thesis measurement"})
            r = c.getresponse()
            data = r.read()
            if r.status == 200 and data[4:8] == b"ftyp":
                with open(os.path.join(a.thu_muc, ma + ".mp4"), "wb") as f:
                    f.write(data)
                da_co.add(ma)
                tong += len(data)
                moi += 1
                if moi % 100 == 0:
                    print("  %4d tệp mới | %7.1f MB | đang ở %s"
                          % (moi, tong / 1048576, ma), flush=True)
            else:
                hong += 1
        except SystemExit:
            raise
        except Exception:
            hong += 1
        finally:
            if c:
                c.close()
        time.sleep(a.nghi)

    print("\nTỔNG: %d tệp, %.1f MB (%d tệp mới, %d không lấy được)"
          % (len(da_co), tong / 1048576, moi, hong))
    return 0


if __name__ == "__main__":
    sys.exit(main())
