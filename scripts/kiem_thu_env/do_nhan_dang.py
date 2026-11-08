"""Đo nhận dạng bằng mẫu thật qua dịch vụ realtime tạm. Chỉ đọc. Kết quả ra JSON.

Số đo, không phải ca đạt/đỏ: nó cho thấy hệ thống đang nhận tốt tới đâu, gồm cả chỗ
biết là chưa tốt (model chưa có lớp từ chối, xem KNOWN_ISSUES).
"""

from __future__ import annotations

import csv
import json
import os
import random
import sys
import urllib.request
from pathlib import Path

import numpy as np

URL = os.environ["REALTIME_URL"] + "/predict"
DATASET = Path("/dataset")
SPLITS = Path("/splits/operational")
MODELS = ("hoa-de", "bang-chu-cai")
HIEN, DOC = 0.6, 0.85

random.seed(1)


def goi(model, khung):
    req = urllib.request.Request(URL, json.dumps({"model_id": model, "frames": khung.tolist()}).encode(),
                                 {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def tho(duong_dan):
    z = np.load(duong_dan, allow_pickle=True)
    if "landmarks_raw" not in z.files:
        return None
    a = np.asarray(z["landmarks_raw"], np.float32)
    a = a.reshape(a.shape[0], -1) if a.ndim == 3 else a
    return a if a.shape == (60, 126) else None


def tap_moi_nhat(dialect):
    ds = sorted((d for d in SPLITS.iterdir() if d.name.startswith(dialect + "-") and (d / "test.csv").exists()),
                key=lambda d: json.loads((d / "split_metadata.json").read_text(encoding="utf-8")).get("generated_at", ""))
    return ds[-1]


def mau_cua(dialect):
    tap = tap_moi_nhat(dialect)
    mau = []
    with open(tap / "test.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if "/aug_" in r["file_path"] and "/aug_000/" not in r["file_path"]:
                continue
            p = DATASET / r["file_path"]
            x = tho(p) if p.exists() else None
            if x is not None:
                mau.append((r, x))
    return tap.name, mau


def dung(o, r):
    return o["label_key"].split("/")[-1].replace("_", "-") == r["slug"] or o["label"] == r["label_original"]


def ty_le_dung(model, mau, tao):
    kq = [dung(goi(model, tao(x)), r) for r, x in mau]
    return {"n": len(kq), "dung": round(float(np.mean(kq)), 4) if kq else None}


def ty_le_lot(model, cac_khung):
    c = np.array([goi(model, f)["confidence"] for f in cac_khung])
    return {"n": len(c), "hien": round(float(np.mean(c >= HIEN)), 4), "doc": round(float(np.mean(c >= DOC)), 4)}


def cua_so(k):
    def tao(x):
        f = np.zeros((60, 126), np.float32)
        f[60 - k:] = x[:k]
        return f
    return tao


def cham(he):
    def tao(x):
        k = int(60 / he)
        f = np.tile(x[0], (60, 1))
        f[60 - k:] = x[np.linspace(0, 59, k).astype(int)]
        return f
    return tao


def main():
    tap = {m: mau_cua(m) for m in MODELS}
    ket_qua = {}
    for m in MODELS:
        ten_tap, mau = tap[m]
        khac = tap[next(x for x in MODELS if x != m)][1]
        tay_yen = []
        for _, x in random.sample(mau, min(40, len(mau))):
            h = next((f for f in x if np.any(f)), x[0])
            tay_yen.append(np.tile(h, (60, 1)))
        ket_qua[m] = {
            "tap_test": ten_tap,
            "du_60_khung": ty_le_dung(m, mau, lambda x: x),
            "cua_so_30_khung": ty_le_dung(m, mau, cua_so(30)),
            "cua_so_15_khung": ty_le_dung(m, mau, cua_so(15)),
            "camera_cham_mot_nua": ty_le_dung(m, mau, cham(2)),
            "tay_dung_yen": ty_le_lot(m, tay_yen),
            "ky_tu_ngoai_model": ty_le_lot(m, [x for _, x in random.sample(khac, min(40, len(khac)))]),
        }
    Path(sys.argv[1]).write_text(json.dumps(ket_qua, ensure_ascii=False, indent=1), encoding="utf-8")
    print("do xong")


if __name__ == "__main__":
    main()
