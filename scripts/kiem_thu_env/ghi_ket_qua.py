"""Plugin pytest: ghi kết quả trả về của từng ca test ra tệp JSONL cho báo cáo.

Hai nguồn, đều là của công cụ chứ không phải suy đoán:

  * `pytest_assertion_pass` — pytest gọi hook này cho MỖI phép `assert` đã đạt, kèm
    biểu thức và giá trị thật. Cần `-o enable_assertion_pass_hook=true`.
  * `httpx.Client.send` — mọi lượt gọi của `TestClient`: mã trả về và nội dung.

Plugin chỉ quan sát, không đổi kết quả. Nội dung bị cắt ngắn và che bí mật vì báo
cáo là tệp đọc bằng mắt, không phải kho lưu.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

import httpx
import pytest

TOI_DA_SO_SANH = 40
TOI_DA_HTTP = 25
TOI_DA_KY_TU = 600

_BI_MAT = re.compile(
    r"""(?ix)("?(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|csrf|otp|code_hash)[\w-]*"?\s*[:=]\s*)"""
    r"""("[^"]*"|'[^']*'|[^\s,;&}]+)""")
_BCRYPT = re.compile(r"\$2[aby]\$\d+\$[./A-Za-z0-9]{20,}")


def che(text, gioi_han=TOI_DA_KY_TU):
    s = _BCRYPT.sub("***", _BI_MAT.sub(r"\1***", str(text)))
    return s if len(s) <= gioi_han else s[:gioi_han] + f"… (+{len(s) - gioi_han} ký tự)"


_hien_tai = {"id": None}
_ca: dict = {}


def _ban_ghi(nodeid):
    return _ca.setdefault(nodeid, {"id": nodeid, "so_sanh": [], "http": [], "giai_doan": {}})


def _boc_httpx():
    goc = httpx.Client.send

    def send(self, request, **kwargs):
        response = goc(self, request, **kwargs)
        nodeid = _hien_tai["id"]
        if nodeid is not None:
            ds = _ban_ghi(nodeid)["http"]
            if len(ds) < TOI_DA_HTTP:
                loai = response.headers.get("content-type", "")
                than = response.text if ("json" in loai or "text" in loai) else f"<{loai or 'nhị phân'}>"
                ds.append({
                    "phuong_thuc": request.method, "duong_dan": request.url.raw_path.decode("ascii", "replace"),
                    "gui": che(request.content.decode("utf-8", "replace"), 300) if request.content else "",
                    "ma": response.status_code, "tra_ve": che(than),
                })
        return response

    httpx.Client.send = send


def pytest_configure(config):
    _boc_httpx()


def pytest_runtest_logstart(nodeid, location):
    _hien_tai["id"] = nodeid
    _ban_ghi(nodeid)["luc"] = datetime.now().strftime("%H:%M:%S")


def pytest_assertion_pass(item, lineno, orig, expl):
    ds = _ban_ghi(item.nodeid)["so_sanh"]
    if len(ds) < TOI_DA_SO_SANH:
        ds.append({"dong": lineno, "bieu_thuc": che(orig, 300), "ket_qua": che(expl, 500)})


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logreport(report):
    ca = _ban_ghi(report.nodeid)
    ca["giai_doan"][report.when] = report.outcome
    ca["giay"] = ca.get("giay", 0) + report.duration
    if report.failed:
        ca["loi"] = che(report.longreprtext, 4000)
        vet = getattr(report.longrepr, "reprcrash", None)
        if vet is not None:
            ca["thong_bao"] = che(vet.message, 400)
            ca["vi_tri"] = f"{vet.path}:{vet.lineno}"
    if report.skipped:
        ly_do = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
        ca["bo_qua"] = che(ly_do, 300)
    if report.when == "call" or report.failed:
        phan = [f"[{ten}]\n{noi_dung}" for ten, noi_dung in report.sections if noi_dung.strip()]
        if phan:
            ca["log"] = che("\n".join(phan), 2000)
    if report.when == "teardown":
        duong_dan = os.environ.get("KT_KET_QUA")
        if duong_dan:
            with open(duong_dan, "a", encoding="utf-8") as f:
                f.write(json.dumps(_ca.pop(report.nodeid), ensure_ascii=False) + "\n")
        _hien_tai["id"] = None
