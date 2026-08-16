#!/usr/bin/env python3
"""Bộ kiểm đối kháng — CTIVR / UASR / SVSR / TCBVR cho Chương 4.

    python scripts/adversarial_isolation.py \
        --base http://localhost:8000 \
        --token-a "$TOKEN_A" --tenant-a ten_a \
        --token-b "$TOKEN_B" --tenant-b ten_b \
        --json ket_qua.json

CHƯA CHẠY LẦN NÀO. Và cố ý KHÔNG nằm dưới `backend/tests/`
==========================================================
Đặt tệp này thành một test sẽ khiến mỗi lượt chạy suite bắn 500 yêu cầu đối
kháng vào API — chậm, ồn trong nhật ký kiểm toán, và trộn một phép ĐO vào một
phép KIỂM. Hai thứ đó khác nhau: bộ test trả lời "có hồi quy không", bộ này trả
lời "tỉ lệ vi phạm là bao nhiêu". Chỉ cái thứ hai mới lên bảng trong quyển.

Ba nhóm, ba chỉ số — tên phải khớp thứ nó đo
============================================
    A  đúng tenant, SAI QUYỀN        -> UASR   (Casbin phải chặn)
    B  đúng quyền, SAI TENANT        -> CTIVR  (RLS/ranh giới phải chặn)
    C  sai quyền VÀ sai tenant       -> cả hai, không lớp nào được fail-open

    SVSR = tổng vi phạm / tổng lần thử   (con số gộp DUY NHẤT được phép)

Gộp nhóm A vào một chỉ số tên "Cross-Tenant…" là làm chính cái tên nói sai — xem
`docs/TENANT_ISOLATION_AND_AUTHZ.md` §6.2.

Ba kết cục, không phải hai
==========================
    CHẶN      401/403/404          -> đúng
    VI PHẠM   2xx                  -> hệ thống cho qua một thao tác trái phép
    MỜ        5xx, timeout, lỗi kết nối

**5xx KHÔNG được tính là chặn.** Một lỗi máy chủ có thể xảy ra SAU khi tác dụng
phụ đã ghi xuống đĩa; đếm nó thành "đã chặn" là cách dễ nhất để báo cáo
CTIVR = 0 cho một hệ thống đang rò. Mọi ca MỜ phải được điều tra từng cái trước
khi công bố bất kỳ con số nào — script thoát khác 0 khi còn ca mờ.

Chuẩn bị trước khi chạy
=======================
Cần hai tenant thật, mỗi tenant một tài khoản, và ít nhất một tài nguyên mỗi bên:

    1. tạo tenant A và B (giao diện quản trị hoặc `tenant_admin`)
    2. mỗi tenant một người dùng; lấy token đăng nhập
    3. mỗi tenant tạo một lớp và một mẫu; ghi lại `class_uid` / `sample_uid`
    4. truyền chúng vào bằng --resource-a / --resource-b

Script KHÔNG tự tạo dữ liệu: một bộ đo mà tự dựng fixture bằng quyền quản trị sẽ
phải chạy dưới một tài khoản mạnh hơn tài khoản đang bị thử, và khi đó không còn
biết kết quả đến từ đâu.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Optional

CHAN = "CHAN"
VI_PHAM = "VI_PHAM"
MO = "MO"


@dataclass
class Op:
    """Một thao tác đối kháng và kết cục mong đợi."""
    nhom: str                 # "A" | "B" | "C"
    method: str
    path: str
    token: Optional[str]
    mo_ta: str
    body: Optional[dict] = None


@dataclass
class KetQua:
    op: Op
    status: int
    ket_cuc: str
    than: str = ""


@dataclass
class Bo:
    """Sinh ma trận thao tác. Mỗi mục lặp `--repeat` lần để có cỡ mẫu."""
    tenant_a: str
    tenant_b: str
    token_a: str
    token_b: str
    class_b: str
    sample_b: str
    class_a: str
    sample_a: str = ""
    workspace_b: str = ""
    project_b: str = ""
    #: Đối tượng RIÊNG cho đối chứng dương có tác dụng phụ. Không dùng chung với
    #: `class_a`/`sample_a`: một lượt xoá thành công sẽ phá mất chính mục tiêu
    #: mà đối chứng đọc đang dùng, và mọi lượt lặp sau đó trả 404 — trông như
    #: đối chứng trượt, trong khi nó vừa thành công.
    class_upd_a: str = ""
    class_del_a: str = ""
    sample_del_a: str = ""
    ops: list[Op] = field(default_factory=list)

    def dung(self, repeat: int) -> list[Op]:
        A, B = self.token_a, self.token_b
        fake = uuid.uuid4().hex[:16]

        # --- Nhóm B: đúng quyền, sai tenant ------------------------------
        # Người gọi là quản trị viên hợp lệ CỦA A, nhắm vào tài nguyên CỦA B.
        nhom_b = [
            # Động từ lấy từ `/openapi.json`, KHÔNG suy đoán theo lối REST quen
            # thuộc. Bản đầu dùng `GET /classes/{id}` và `PATCH /classes/{id}`:
            # đường đó chỉ nhận DELETE và PUT. `GET /dataset/samples/{id}` cũng
            # không có — đọc nội dung mẫu là `.../data`.
            Op("B", "GET",    f"/api/v1/classes/{self.class_b}/sessions", A,
               "đọc phiên thu của lớp B"),
            Op("B", "GET",    f"/api/v1/dataset/samples/{self.sample_b}/data", A,
               "đọc dữ liệu mẫu của B"),
            Op("B", "PUT",    f"/api/v1/classes/{self.class_b}",  A, "sửa lớp của B",
               {"label_original": "bi sua boi A"}),
            Op("B", "DELETE", f"/api/v1/dataset/samples/{self.sample_b}", A, "xoá mẫu của B"),
            Op("B", "GET",    f"/api/v1/tenants/{self.tenant_b}", A, "đọc hồ sơ tenant B"),
            Op("B", "GET",    f"/api/v1/tenants/{self.tenant_b}/members", A, "liệt kê thành viên B"),
            # Ghi với tenant_id của người khác trong THÂN yêu cầu: đây là ca mà
            # WITH CHECK phải bắt, khác hẳn ca đọc mà USING bắt.
            Op("B", "POST",   "/api/v1/classes/register", A, "tạo lớp mang tenant_id của B",
               {"slug": f"xuyen-{fake}", "label_original": "x", "tenant_id": self.tenant_b}),
        ]

        # --- Nhóm A: đúng tenant, sai quyền ------------------------------
        # Người gọi thuộc đúng tenant mình, nhưng vai không có quyền đó.
        nhom_a = [
            Op("A", "DELETE", f"/api/v1/classes/{self.class_a}", A, "xoá lớp khi vai không có quyền xoá"),
            # Sửa lớp CỦA CHÍNH đơn vị mình. Nằm ở nhóm này chứ không ở đối
            # chứng dương, vì thao tác gác sau quyền quản trị NỀN TẢNG chứ không
            # sau vai trong đơn vị: một tổ chức không sửa được lớp của chính nó.
            # Bị từ chối ở đây là kết cục ĐÚNG, và nó đo đúng thứ nhóm A đo —
            # đúng đơn vị, sai quyền.
            Op("A", "PUT", f"/api/v1/classes/{self.class_upd_a or self.class_a}", A,
               "sửa lớp của chính đơn vị mình (đòi quản trị nền tảng)",
               {"label_original": "thu sua bang vai don vi"}),
            Op("A", "PATCH",  f"/api/v1/billing/tenants/{self.tenant_a}/plan", A,
               "tự nâng gói (đòi sudo nền tảng)", {"plan_code": "pro"}),
            Op("A", "GET",    "/api/v1/billing/platform-usage", A, "đọc mức dùng toàn nền tảng"),
            Op("A", "GET",    "/api/v1/tenants", A, "liệt kê mọi tenant"),
            Op("A", "POST",   "/api/v1/tenants", A, "tạo tenant mới",
               {"tenant_id": f"leo{fake}", "display_name": "leo thang"}),
        ]

        # --- Nhóm C: sai quyền VÀ sai tenant ------------------------------
        nhom_c = [
            Op("C", "PATCH",  f"/api/v1/tenants/{self.tenant_b}", A, "sửa hồ sơ tenant B",
               {"display_name": "bi doi ten"}),
            Op("C", "DELETE", f"/api/v1/tenants/{self.tenant_b}", A, "xoá tenant B"),
            Op("C", "PATCH",  f"/api/v1/billing/tenants/{self.tenant_b}/status", A,
               "treo tenant B", {"billing_status": "suspended"}),
        ]

        # --- Đoán định danh của B -----------------------------------------
        # Cách ly không được phép dựa vào "không ai biết mã". Nếu đoán trúng mà
        # đọc được thì hệ thống đang bảo mật bằng sự khó đoán, không bằng cách
        # ly. Mã giả ở đây KHÔNG tồn tại, nên kết quả mong đợi giống hệt ca thật
        # — và chính sự giống hệt đó là điều §6.6 đòi hỏi.
        doan_dinh_danh = [
            Op("B", "GET", f"/api/v1/classes/{uuid.uuid4().hex[:16]}/sessions", A,
               "đoán mã lớp không tồn tại"),
            Op("B", "GET", f"/api/v1/dataset/samples/{uuid.uuid4().hex[:10]}/data", A,
               "đoán mã mẫu không tồn tại"),
        ]

        # --- Đổi phạm vi workspace/project sang của B ----------------------
        doi_pham_vi = []
        if self.workspace_b:
            doi_pham_vi.append(
                Op("B", "GET", f"/api/v1/workspaces/{self.workspace_b}", A,
                   "đọc workspace của B"))
        if self.project_b:
            doi_pham_vi.append(
                Op("B", "GET", f"/api/v1/projects/{self.project_b}", A,
                   "đọc project của B"))

        # --- Không có / sai ngữ cảnh tenant --------------------------------
        # Hai ca KHÁC NHAU và hay bị gộp làm một:
        #   * chưa đăng nhập      -> không có danh tính nào để suy ra tenant
        #   * token hỏng/giả      -> có header nhưng không giải mã được
        # Cả hai phải fail-CLOSED. Ca thứ hai là ca mà một hệ fail-open sẽ lộ
        # ra: nếu tenant không xác định được mà truy vấn vẫn chạy, RLS so với
        # một GUC rỗng và khớp 0 dòng — nhìn giống "không có gì", không giống
        # một lỗi. Xem `rls-fail-open-identity-plane`.
        khong_ngu_canh = [
            Op("B", "GET", f"/api/v1/classes/{self.class_b}/sessions", None,
               "đọc lớp khi chưa đăng nhập"),
            Op("B", "GET", f"/api/v1/dataset/samples/{self.sample_b}/data", None,
               "đọc mẫu khi chưa đăng nhập"),
            Op("B", "GET", f"/api/v1/classes/{self.class_b}/sessions", "khong-phai-mot-token",
               "đọc lớp bằng token rác"),
            Op("B", "GET", "/api/v1/auth/me", "khong-phai-mot-token",
               "hỏi danh tính bằng token rác"),
        ]

        ops: list[Op] = []
        for bo in (nhom_b, nhom_a, nhom_c, doan_dinh_danh, doi_pham_vi, khong_ngu_canh):
            for op in bo:
                ops.extend([op] * repeat)
        return ops

    def doi_chung_duong(self) -> list[Op]:
        """A đọc tài nguyên CỦA CHÍNH A qua API. Phải THÀNH CÔNG.

        Đây là vế thiếu của phép đo, và thiếu nó thì mọi con số ở trên vô nghĩa.
        Kết quả "A không đọc được dữ liệu của B" có hai nguyên nhân hoàn toàn
        khác nhau và bộ đo âm không phân định được:

            * cô lập tenant hoạt động đúng, HOẶC
            * tài khoản A vốn đã không đọc được gì cả

        Ngày 15/08/2026 khả năng thứ hai là CÓ THẬT, không phải giả định: ba tài
        khoản fixture được gieo với `users.tenant_id` nhưng KHÔNG có dòng
        `memberships` nào, và đường phân quyền của hệ thống đi qua
        `User -> TenantMembership -> EffectiveScope -> AccessDecision`. Một tài
        khoản thiếu vế thứ hai bị coi là "không phải thành viên" ở mọi phép kiểm
        quyền. Lượt đo đầu tiên vì thế bị NHIỄU: 480 ca bị chặn có thể chỉ đang
        đo việc ba tài khoản ấy không có tư cách gì.

        Khẳng định trong kịch bản gieo không bắt được điều này, vì nó đọc bằng
        SQL trực tiếp dưới `tenant_scope` — tức đi vòng qua đúng mặt phẳng phân
        quyền đang cần kiểm.

        Nhóm này chạy QUA API, bằng chính token dùng cho các nhóm đối kháng.
        Một ca trượt ở đây làm VÔ HIỆU cả lượt đo, không phải giảm điểm.
        """
        A = self.token_a
        ops = [
            Op("P", "GET", "/api/v1/auth/me", A, "A đọc danh tính của chính mình"),
            Op("P", "GET", f"/api/v1/classes/{self.class_a}/sessions", A,
               "A đọc phiên thu của lớp CỦA CHÍNH A"),
        ]
        if self.sample_a:
            ops.append(Op("P", "GET", f"/api/v1/dataset/samples/{self.sample_a}/data",
                          A, "A đọc dữ liệu mẫu CỦA CHÍNH A"))
        return ops

    def doi_chung_duong_ghi(self) -> list[Op]:
        """A SỬA và XOÁ tài nguyên của chính A. Phải THÀNH CÔNG. Chạy MỘT LẦN.

        Vì sao tách khỏi nhóm đọc
        -------------------------
        Nhóm đọc lặp `--repeat` lần để có cỡ mẫu. Hai thao tác dưới đây có tác
        dụng phụ, nên lặp chúng là tự phá:

            lần 1   DELETE mẫu -> 2xx, đúng
            lần 2+  DELETE mẫu -> 404, chấm thành TRƯỢT

        Một đối chứng dương trượt làm VÔ HIỆU cả lượt đo. Nên nhóm này chạy đúng
        một lần, và nhắm vào hai đối tượng RIÊNG mà cây fixture dựng sẵn cho nó.

        Vì sao vế ghi là bắt buộc, không phải cho đủ bộ
        -----------------------------------------------
        Nhóm đối kháng khẳng định A **không sửa/xoá được** tài nguyên của B. Chỉ
        có đối chứng đọc thì kết luận ấy vẫn treo: có thể A không sửa/xoá được
        BẤT CỨ THỨ GÌ — vì thiếu quyền, vì cổng CSRF, vì token chỉ đọc. Khi đó
        "đã chặn" không nói gì về cách ly tenant cả.

        Chỉ khi A sửa/xoá được của chính mình mà KHÔNG sửa/xoá được của B thì
        hiệu số hai kết quả mới quy được cho ranh giới tenant.
        """
        A = self.token_a
        ops: list[Op] = []
        # `PUT /classes/{uid}` KHÔNG nằm ở đây, và đó là kết luận của phép đo
        # ngày 16/08/2026 chứ không phải một chỗ bỏ sót.
        #
        # Thao tác ấy gác sau quyền quản trị NỀN TẢNG, không phải vai trong đơn
        # vị. Một tài khoản đơn vị thường bị từ chối — đúng thiết kế. Đặt nó vào
        # đối chứng dương thì lượt từ chối ấy bị chấm thành TRƯỢT, và cả lượt đo
        # bị tuyên vô hiệu vì một hành vi hoàn toàn đúng.
        #
        # Nó thuộc nhóm "đúng đơn vị, SAI QUYỀN", nơi bị từ chối là kết cục
        # ĐÚNG. Xem docs/10-issues/FINDING_P0B_platform_admin_crosses_tenants.md
        #
        # Dùng tài khoản mang cờ quản trị nền tảng để lượt này "đạt" là cách
        # sai: cùng cờ ấy cũng cho phép xoá đơn vị khác, nên toàn bộ ma trận
        # xuyên đơn vị sẽ đo năng lực quản trị nền tảng thay vì đo cách ly.
        if self.sample_del_a:
            ops.append(Op("P", "DELETE", f"/api/v1/dataset/samples/{self.sample_del_a}",
                          A, "A xoá mẫu CỦA CHÍNH A"))
        return ops

    def ngoai_le_cong_khai(self) -> list[Op]:
        """Các đường CÔNG KHAI / cộng đồng — kiểm RIÊNG, không tính vào CTIVR.

        Bất biến của hệ thống là: chéo-tenant mặc định bị cấm, còn công khai và
        cộng đồng là NGOẠI LỆ TƯỜNG MINH. Nhét chúng vào cùng một mẫu số sẽ tạo
        ra vi phạm giả — một danh mục cộng đồng đọc được từ tenant khác là đúng
        thiết kế, không phải lỗ hổng. Nhưng cũng không được im lặng bỏ qua:
        nếu một ngoại lệ NGỪNG hoạt động thì đó là hồi quy chức năng, nên vẫn
        chạy và vẫn báo, chỉ là báo ở bảng khác.
        """
        return [
            Op("X", "GET", "/api/v1/billing/plans", self.token_a, "bảng giá công khai"),
            # `/vocabulary/catalog` TỪNG nằm ở đây và đó là phân loại sai: nó
            # trả "Admin privileges required". Một endpoint quản trị bị xếp vào
            # nhóm ngoại lệ công khai sẽ báo HỎNG mỗi lượt chạy, và cách "sửa"
            # hiển nhiên nhất — nới quyền cho nó — là mở một lỗ thật để làm im
            # một cảnh báo giả. Kiểm bằng người dùng thường trước khi xếp nhóm.
            Op("X", "GET", "/api/v1/legal/documents", self.token_a, "văn bản pháp lý"),
            Op("X", "GET", "/api/v1/classes/community-stats", self.token_a,
               "thống kê cộng đồng"),
        ]


def kiem_duong_dan(base: str, ops: list[Op], token: str, timeout: float) -> list[str]:
    """Mọi đường trong bộ thử PHẢI có thật trong sơ đồ OpenAPI. Trả danh sách sai.

    Vì sao đây là chốt chặn bắt buộc chứ không phải tiện ích
    -------------------------------------------------------
    `goi()` tính 404 là CHẶN, và điều đó đúng: hệ thống cách ly tốt thường trả
    404 thay vì 403 để không tiết lộ rằng tài nguyên có tồn tại (§6.6, tính
    không phân biệt được). Nhưng một đường dẫn GÕ SAI cũng trả 404.

    Hai thứ đó không phân biệt được từ phía khách, nên bộ đo sẽ chấm điểm tuyệt
    đối cho chính lỗi của mình. Bản đầu của tệp này nhắm vào `/api/v1/samples/…`
    và `POST /api/v1/classes` — cả hai đều KHÔNG TỒN TẠI (đường thật là
    `/api/v1/dataset/samples/…` và `/api/v1/classes/register`). Bốn trên mười
    lăm phép thử sẽ báo "đã chặn" mà chưa từng chạm tới một lớp cách ly nào, và
    CTIVR = 0 in ra trông y hệt một kết quả tốt.

    Một phép đo mà chế ra được đúng kết quả người đo mong muốn thì vô giá trị.
    """
    import re

    req = urllib.request.Request(base.rstrip("/") + "/openapi.json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        schema = json.loads(resp.read().decode("utf-8"))
    khai_bao = schema.get("paths", {})

    # `/api/v1/classes/abc123` phải khớp khuôn `/api/v1/classes/{class_uid}`.
    khuon = [(p, re.compile("^" + re.sub(r"\\\{[^}]+\\\}", r"[^/]+", re.escape(p)) + "$"))
             for p in khai_bao]

    thieu = []
    for op in ops:
        duong = op.path.split("?")[0]
        mo_ta_duong = khai_bao.get(duong)
        if mo_ta_duong is None:
            for p, rx in khuon:
                if rx.match(duong):
                    mo_ta_duong = khai_bao[p]
                    break

        if mo_ta_duong is None:
            ly_do = "đường không tồn tại"
        elif op.method.lower() not in mo_ta_duong:
            # Đường CÓ nhưng động từ thì KHÔNG. FastAPI trả 405 cho ca này,
            # và 405 rơi vào nhóm KHÔNG KẾT LUẬN ĐƯỢC — nên nó không thổi phồng
            # điểm số như 404, nhưng vẫn làm hỏng phép đo theo kiểu khác: mọi
            # lượt lặp của thao tác đó thành ca mờ, và nguyên tắc "chỉ công bố
            # khi số ca mờ bằng 0" sẽ chặn cả báo cáo. Bắt ở đây rẻ hơn nhiều.
            ly_do = (f"đường có nhưng không nhận {op.method} "
                     f"(có: {', '.join(sorted(k.upper() for k in mo_ta_duong if k in ('get','post','put','patch','delete')))})")
        else:
            continue

        nhan = f"{op.method} {op.path}  — {ly_do}"
        if nhan not in thieu:
            thieu.append(nhan)
    return thieu


def goi(base: str, op: Op, timeout: float) -> KetQua:
    url = base.rstrip("/") + op.path
    data = json.dumps(op.body).encode() if op.body is not None else None
    req = urllib.request.Request(url, data=data, method=op.method)
    if op.token:
        req.add_header("Authorization", f"Bearer {op.token}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            than = resp.read(400).decode("utf-8", "replace")
            return KetQua(op, resp.status, VI_PHAM, than)
    except urllib.error.HTTPError as exc:
        than = exc.read(400).decode("utf-8", "replace")
        if exc.code in (401, 403, 404):
            return KetQua(op, exc.code, CHAN, than)
        if 200 <= exc.code < 300:
            return KetQua(op, exc.code, VI_PHAM, than)
        # 400/409/422 = bị từ chối vì lý do KHÁC (thân sai, xung đột). Không phải
        # bằng chứng của cách ly, nên không được tính là CHẶN.
        return KetQua(op, exc.code, MO, than)
    except Exception as exc:                        # timeout, lỗi kết nối
        return KetQua(op, 0, MO, f"{type(exc).__name__}: {exc}")


def kiem_tra_khong_phan_biet(base: str, token: str, class_b: str, timeout: float) -> dict:
    """Tài nguyên CỦA NGƯỜI KHÁC và tài nguyên KHÔNG TỒN TẠI phải quan sát như nhau.

    Trả 403 cho cái đầu và 404 cho cái sau biến API thành máy trả lời câu hỏi
    "tài nguyên này có tồn tại không" cho tenant khác — rò siêu dữ liệu mà không
    rò lấy một byte nội dung nào.
    """
    that = goi(base, Op("B", "GET", f"/api/v1/classes/{class_b}/sessions", token, "lạ"),
               timeout)
    gia = goi(base, Op("B", "GET", f"/api/v1/classes/{uuid.uuid4().hex[:16]}/sessions",
                       token, "không tồn tại"), timeout)
    return {
        "ma_tai_nguyen_la": that.status,
        "ma_tai_nguyen_khong_ton_tai": gia.status,
        "tuong_duong": that.status == gia.status,
    }


def _doc_fixture_dataset(duong: str) -> dict:
    """Đọc cây fixture do bộ gieo xuyên-kho sinh ra, chuẩn hoá về một hình dạng.

    Vì sao cần một lớp chuyển đổi
    -----------------------------
    Bộ gieo và bộ đo được viết ở hai thời điểm và mô tả CÙNG một fixture bằng hai
    hình dạng khác nhau:

        bộ gieo   `doi_tuong` là DANH SÁCH 8 mục, khoá theo (tenant, vai trò),
                  `file_path` TƯƠNG ĐỐI so với gốc cây, băm đầy đủ 64 ký tự
        bộ đo     `doi_tuong` là TỪ ĐIỂN khoá `control_a` / `target_b`,
                  `file_path` TUYỆT ĐỐI, băm rút gọn 16 ký tự

    Phát hiện lúc chạy thật, không phải lúc đọc mã: bộ đo dừng ngay ở lượt nạp.
    Đó là kết cục ĐÚNG — một bộ đo nuốt được hình dạng lạ sẽ lặng lẽ đọc thiếu
    đối tượng rồi báo "không có vi phạm nào" cho một ma trận chưa từng bắn.

    Chuyển đổi đặt ở BỘ ĐO chứ không ở bộ gieo, vì cây fixture đã nằm trên đĩa và
    đang là bằng chứng: sửa bộ gieo thì phải gieo lại, và gieo lại là vứt đi đúng
    thứ vừa được đối chiếu ba kho thành công.

    Cũng chấp nhận hình dạng cũ để một artifact cũ vẫn đọc lại được.
    """
    import pathlib

    p = pathlib.Path(duong)
    goc = p if p.is_dir() else p.parent
    tep = (p / "fixture.json") if p.is_dir() else p
    with open(tep, encoding="utf-8") as fh:
        tho = json.load(fh)

    dt = tho.get("doi_tuong")
    if isinstance(dt, dict):
        tho.setdefault("dataset_root", str(goc))
        return tho

    # Hình dạng danh sách -> từ điển. Khoá là `<vai_tro>_<chu cai tenant>`, tức
    # `control_a` / `target_b` — đúng tên mà bộ đo tra cứu.
    chuan: dict[str, dict] = {}
    for m in dt:
        hau_to = m["tenant_id"].rsplit("_", 1)[-1]           # iso_a -> a
        vai = m["vai_tro"]
        nhan = f"{'target' if vai == 'target' else vai}_{hau_to}"
        chuan[nhan] = {
            "vai_tro": vai,
            "tenant_id": m["tenant_id"],
            "class_uid": m["class_uid"],
            "sample_uid": m["sample_uid"],
            # TUYỆT ĐỐI: hậu điều kiện mở tệp bằng đúng chuỗi này, và nó chạy
            # với thư mục làm việc khác thư mục fixture.
            "file_path": str(goc / m["file_path"]),
            "sha256_16": m["file_sha256"][:16],
        }

    # `control_a` là bí danh của `control_read_a`. Cây fixture tách ba đối tượng
    # đối chứng cho tenant A — đọc, sửa, xoá — chính vì đối chứng xoá mà dùng
    # chung đối tượng với đối chứng đọc thì nó tự phá mục tiêu của mình.
    if "control_a" not in chuan and "control_read_a" in chuan:
        chuan["control_a"] = chuan["control_read_a"]

    thieu = [k for k in ("control_a", "target_b") if k not in chuan]
    if thieu:
        raise SystemExit(
            f"cay fixture {goc} thieu doi tuong bat buoc: {thieu}. "
            f"Co: {sorted(chuan)}")

    return {**tho, "dataset_root": str(goc), "doi_tuong": chuan}


def hau_dieu_kien_dataset(dsn: str, dfx: dict) -> dict:
    """Hậu điều kiện trên CẢ BA nơi: PostgreSQL, labels/samples.csv, và tệp mẫu.

    Vì sao không đủ khi chỉ soi hàng CSDL
    -------------------------------------
    Đường lớp/mẫu không thuần PostgreSQL — `list_classes()` đọc `labels.csv` trên
    đĩa. Một lượt xoá đi lọt có thể gỡ dòng CSV hoặc tệp `.npz` mà không đụng tới
    hàng CSDL, và một hậu điều kiện chỉ đếm hàng sẽ báo "còn nguyên".

    Băm nội dung tệp để bắt cả UPDATE lén: phép đếm và phép kiểm tồn tại đều bỏ
    qua một tệp bị ghi đè.
    """
    import csv as _csv
    import hashlib
    import io as _io
    from pathlib import Path

    import psycopg2

    goc = Path(dfx["dataset_root"])
    lop_csv, mau_csv = set(), set()
    for ten_tep, dich, khoa in ((goc / "labels.csv", lop_csv, "class_uid"),
                                (goc / "samples.csv", mau_csv, "sample_uid")):
        if ten_tep.exists():
            with _io.open(ten_tep, encoding="utf-8", newline="") as fh:
                for r in _csv.DictReader(fh):
                    if r.get(khoa):
                        dich.add(r[khoa])

    ket = {}
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL app.system_scope = 'on'")
            for nhan, v in dfx["doi_tuong"].items():
                cur.execute("SELECT count(*) FROM classes WHERE class_uid = %s",
                            (v["class_uid"],))
                db_lop = cur.fetchone()[0] == 1
                cur.execute("SELECT count(*) FROM samples WHERE sample_uid = %s",
                            (v["sample_uid"],))
                db_mau = cur.fetchone()[0] == 1

                tep = Path(v["file_path"])
                con_tep = tep.exists()
                bam = (hashlib.sha256(tep.read_bytes()).hexdigest()[:16]
                       if con_tep else None)

                ket[nhan] = {
                    "vai_tro": v["vai_tro"],
                    "db_class": db_lop,
                    "db_sample": db_mau,
                    "csv_class": v["class_uid"] in lop_csv,
                    "csv_sample": v["sample_uid"] in mau_csv,
                    "tep_con": con_tep,
                    "bam_truoc": v["sha256_16"],
                    "bam_sau": bam,
                    "bam_khop": bam == v["sha256_16"],
                }
                ket[nhan]["nguyen_ven"] = all(
                    ket[nhan][k] for k in
                    ("db_class", "db_sample", "csv_class", "csv_sample",
                     "tep_con", "bam_khop"))
    return ket


def hau_dieu_kien(dsn: str, fx: dict) -> dict:
    """Sau khi bắn xong: tài nguyên của B có còn nguyên không?

    Vì sao mã HTTP là chưa đủ
    -------------------------
    `DELETE /…/samples/{b}` trả 404 KHÔNG chứng minh được là không có gì bị xoá.
    Một xử lý có thể xoá hàng rồi mới ngã ở bước kiểm quyền, hoặc xoá xong mới
    dựng phản hồi. Chuỗi sự cố `migration-data-steps` trong kho này đúng là kiểu
    đó: một câu bị RLS chặn IM LẶNG trong khi câu bên cạnh vẫn ghi. Phản hồi thì
    nhìn bình thường.

    Nên hợp đồng phải có vế THỨ BA: gọi xong, đọc lại CSDL bằng một vai quan sát
    được, và khẳng định trạng thái không đổi.
    """
    import hashlib
    import psycopg2

    ket = {}
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL app.system_scope = 'on'")
            for ten, v in fx["ben"].items():
                cur.execute("SELECT count(*) FROM tenants WHERE tenant_id = %s", (ten,))
                con_tenant = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM classes WHERE class_uid = %s",
                            (v["class_uid"],))
                con_lop = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM samples WHERE sample_uid = %s",
                            (v["sample_uid"],))
                con_mau = cur.fetchone()[0]
                # Vân tay nội dung: bắt cả UPDATE lén, thứ mà phép đếm bỏ qua.
                cur.execute(
                    "SELECT coalesce(label_original,'') || '|' || coalesce(slug,'') "
                    "|| '|' || coalesce(dialect,'') FROM classes WHERE class_uid = %s",
                    (v["class_uid"],))
                row = cur.fetchone()
                van_tay = hashlib.sha256((row[0] if row else "").encode()).hexdigest()[:16]
                ket[ten] = {
                    "tenant_con": con_tenant == 1,
                    "class_con": con_lop == 1,
                    "sample_con": con_mau == 1,
                    "class_van_tay": van_tay,
                }
    return ket


def moi_truong(dsn: str, base: str) -> dict:
    """Siêu dữ liệu để lượt đo này tái lập và kiểm chứng được về sau."""
    import subprocess
    import psycopg2

    md = {"base": base, "thoi_diem": _bay_gio()}

    # Bộ đo chạy BÊN TRONG mạng docker (Postgres không mở cổng ra host), và ở
    # đó không có `.git`. Nhận từ biến môi trường trước, rồi mới thử `git` —
    # nếu không thì mọi báo cáo đều mang `git_commit: null` và mất khả năng
    # truy lại chính xác lượt đo này ứng với mã nào.
    import os
    md["git_commit"] = os.environ.get("VOYA_GIT_COMMIT") or None
    md["git_ban"] = (os.environ.get("VOYA_GIT_DIRTY") == "1") if "VOYA_GIT_DIRTY" in os.environ else None
    if md["git_commit"] is None:
        try:
            md["git_commit"] = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                timeout=10).stdout.strip() or None
            md["git_ban"] = subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True,
                timeout=10).stdout.strip() != ""
        except Exception:
            pass

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT current_database(), current_user, version(),
                                  (SELECT rolsuper     FROM pg_roles WHERE rolname = current_user),
                                  (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user)""")
            db, who, ver, su, byp = cur.fetchone()
            cur.execute("SELECT coalesce(max(version)::text, '?') FROM schema_migrations")
            sv = cur.fetchone()[0]
    md.update({
        "database": db, "runtime_role": who, "postgres": ver.split(",")[0],
        "superuser": su, "bypass_rls": byp, "schema_version": sv,
    })
    return md


def _bay_gio() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Bộ kiểm đối kháng cách ly tenant.")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--tenant-a", required=True)
    ap.add_argument("--tenant-b", required=True)
    ap.add_argument("--token-a", required=True, help="token của quản trị viên tenant A")
    ap.add_argument("--token-b", required=True, help="token của tenant B (dựng dữ liệu)")
    ap.add_argument("--class-a", required=True)
    ap.add_argument("--class-b", required=True)
    ap.add_argument("--sample-b", required=True)
    ap.add_argument("--repeat", type=int, default=30,
                    help="số lần lặp mỗi thao tác; 30 × 17 thao tác ≈ 510 lượt")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--json", help="ghi kết quả thô")
    ap.add_argument("--sample-a", default="", help="mẫu của A — cho đối chứng dương")
    ap.add_argument("--dataset-fixture", default=None,
                    help="JSON do seed_isolation_dataset.py sinh ra. Khi có, các "
                         "mã lớp/mẫu lấy từ đây: control_* cho đối chứng dương, "
                         "target_* cho mục tiêu đối kháng — hai nhóm KHÔNG dùng "
                         "chung đối tượng.")
    ap.add_argument("--workspace-b", default="")
    ap.add_argument("--project-b", default="")
    ap.add_argument("--dsn", default=None,
                    help="DSN quan sát để kiểm hậu điều kiện + ghi siêu dữ liệu")
    ap.add_argument("--fixture", default=None,
                    help="tệp JSON do seed_isolation_fixture.py sinh ra")
    args = ap.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    # Cây dataset dùng-một-lần: đối chứng dương nhắm `control_*`, đối kháng nhắm
    # `target_*`. Tách hai nhóm là bắt buộc — đối chứng dương có thao tác ghi và
    # xoá, nên dùng chung đối tượng sẽ khiến nó tự xoá mục tiêu, rồi mọi ca đối
    # kháng sau đó trả 404 vì không còn gì để chạm.
    dfx = None
    if args.dataset_fixture:
        dfx = _doc_fixture_dataset(args.dataset_fixture)
        dt = dfx["doi_tuong"]
        args.class_a, args.sample_a = dt["control_a"]["class_uid"], dt["control_a"]["sample_uid"]
        args.class_b, args.sample_b = dt["target_b"]["class_uid"], dt["target_b"]["sample_uid"]
        upd = dt.get("control_update_a", {})
        dele = dt.get("control_delete_a", {})
        print(f"đối chứng A đọc : {args.class_a} / {args.sample_a}")
        print(f"đối chứng A sửa : {upd.get('class_uid', '(khong co)')}")
        print(f"đối chứng A xoá : {dele.get('sample_uid', '(khong co)')}")
        print(f"mục tiêu  B     : {args.class_b} / {args.sample_b}\n")

    bo = Bo(args.tenant_a, args.tenant_b, args.token_a, args.token_b,
            args.class_b, args.sample_b, args.class_a, args.sample_a,
            args.workspace_b, args.project_b,
            class_upd_a=(dfx or {}).get("doi_tuong", {})
                        .get("control_update_a", {}).get("class_uid", ""),
            class_del_a=(dfx or {}).get("doi_tuong", {})
                        .get("control_delete_a", {}).get("class_uid", ""),
            sample_del_a=(dfx or {}).get("doi_tuong", {})
                         .get("control_delete_a", {}).get("sample_uid", ""))
    # Đối chứng ghi chạy TRƯỚC nhóm đối kháng và ĐÚNG MỘT LẦN. Trước, vì nếu
    # quyền ghi của chính chủ đã hỏng thì không cần bắn 500 phát nữa mới biết
    # lượt đo vô hiệu. Một lần, vì nó có tác dụng phụ.
    ops = (bo.doi_chung_duong() * args.repeat
           + bo.doi_chung_duong_ghi()
           + bo.dung(args.repeat)
           + bo.ngoai_le_cong_khai() * args.repeat)

    # Chốt chặn TRƯỚC khi bắn phát nào: một đường gõ sai trả 404, và 404 được
    # tính là CHẶN. Xem `kiem_duong_dan`.
    thieu = kiem_duong_dan(args.base, ops, args.token_a, args.timeout)
    if thieu:
        print("DỪNG: các đường sau không có trong sơ đồ OpenAPI của máy chủ.")
        print("404 của chúng sẽ bị chấm là 'đã chặn' và làm đẹp kết quả một cách giả tạo.\n")
        for nhan in thieu:
            print(f"  {nhan}")
        return 3

    print(f"{len(ops)} thao tác -> {args.base}\n")
    tat_ca = [goi(args.base, op, args.timeout) for op in ops]

    # Nhóm X là NGOẠI LỆ TƯỜNG MINH (công khai / cộng đồng). Với nó, 2xx là kết
    # quả ĐÚNG. Để nó chung mẫu số sẽ đếm mỗi lượt đọc bảng giá thành một vụ
    # xuyên tenant, và CTIVR sẽ báo động về chính chức năng của sản phẩm.
    ket = [r for r in tat_ca if r.op.nhom not in ("X", "P")]
    ket_x = [r for r in tat_ca if r.op.nhom == "X"]
    ket_p = [r for r in tat_ca if r.op.nhom == "P"]

    # ĐỐI CHỨNG DƯƠNG trước tiên. Nếu A không đọc nổi dữ liệu của chính A thì
    # mọi ca "đã chặn" bên dưới không chứng minh được gì về cô lập — chúng chỉ
    # chứng minh rằng tài khoản ấy không đọc được gì cả. Đây là vô hiệu, không
    # phải trừ điểm, nên phải chặn TRƯỚC khi in bất kỳ tỉ lệ nào.
    if ket_p:
        truot = [r for r in ket_p if not (200 <= r.status < 400)]
        print("đối chứng dương (A đọc dữ liệu CỦA CHÍNH A — phải thành công):")
        da_in = set()
        for r in ket_p:
            if r.op.mo_ta in da_in:
                continue
            da_in.add(r.op.mo_ta)
            dat = "ĐẠT" if 200 <= r.status < 400 else f"TRƯỢT ({r.status})"
            print(f"  {dat:<14} {r.op.mo_ta}")
        if truot:
            print(f"\nVÔ HIỆU: {len(truot)}/{len(ket_p)} lượt đối chứng dương trượt.")
            print("Không công bố chỉ số nào. Kết quả 'đã chặn' ở các nhóm đối kháng")
            print("không phân định được giữa 'cô lập đúng' và 'tài khoản vốn không")
            print("đọc được gì'. Kiểm tư cách thành viên, vai, và cây dataset trước.")
            if args.json:
                # Ghi ra một artifact NÓI THẲNG là không đủ điều kiện, thay vì
                # in NaN rồi để bảng trông vẫn tử tế. `NOT_PUBLISHABLE` là một
                # chuỗi, không phải số — không ai lỡ tay đưa nó vào bảng được.
                with open(args.json, "w", encoding="utf-8") as fh:
                    json.dump({
                        "positive_control_passed": False,
                        "ctivr": "NOT_PUBLISHABLE",
                        "uasr": "NOT_PUBLISHABLE",
                        "svsr": "NOT_PUBLISHABLE",
                        "ly_do": (
                            "Đối chứng dương trượt: tài khoản không truy cập được "
                            "tài nguyên CỦA CHÍNH NÓ. Mọi kết quả 'đã chặn' vì thế "
                            "không phân định được giữa cách ly đúng và tài khoản "
                            "vốn không có quyền."),
                        "doi_chung_truot": [
                            {"mo_ta": r.op.mo_ta, "status": r.status}
                            for r in truot[:20]],
                    }, fh, ensure_ascii=False, indent=2)
                print(f"\nĐã ghi {args.json} (đánh dấu NOT_PUBLISHABLE)")
            return 4
        print()

    def dem(nhom: Optional[str], ket_cuc: str) -> int:
        return sum(1 for r in ket
                   if (nhom is None or r.op.nhom == nhom) and r.ket_cuc == ket_cuc)

    def tong(nhom: Optional[str]) -> int:
        return sum(1 for r in ket if nhom is None or r.op.nhom == nhom)

    print(f"{'nhóm':<6}{'lượt':>7}{'chặn':>7}{'VI PHẠM':>9}{'mờ':>6}")
    print("-" * 36)
    for nhom in ("A", "B", "C"):
        print(f"{nhom:<6}{tong(nhom):>7}{dem(nhom, CHAN):>7}"
              f"{dem(nhom, VI_PHAM):>9}{dem(nhom, MO):>6}")

    # Mẫu số là số lần thử KẾT LUẬN ĐƯỢC, không phải tổng số lần thử. Một ca mờ
    # không nói được là chặn hay thủng, nên để nó trong mẫu số sẽ KÉO TỈ LỆ VI
    # PHẠM XUỐNG — càng nhiều ca không kết luận được thì con số càng đẹp. Đó là
    # thiên lệch đi đúng hướng nguy hiểm.
    #
    # Và dù mẫu số đã đúng, vẫn KHÔNG công bố khi còn ca mờ: xem cuối hàm.
    def ket_luan_duoc(nhom: Optional[str]) -> int:
        return dem(nhom, CHAN) + dem(nhom, VI_PHAM)

    n_ct = ket_luan_duoc("B") + ket_luan_duoc("C")
    v_ct = dem("B", VI_PHAM) + dem("C", VI_PHAM)
    ctivr = v_ct / n_ct if n_ct else float("nan")
    uasr = (dem("A", VI_PHAM) / ket_luan_duoc("A")) if ket_luan_duoc("A") else float("nan")
    n_all = ket_luan_duoc(None)
    svsr = dem(None, VI_PHAM) / n_all if n_all else float("nan")
    mo = dem(None, MO)

    print(f"\nCTIVR = {ctivr:.4f}   ({v_ct} vi phạm / {n_ct} lần thử kết luận được, nhóm B+C)")
    print(f"UASR  = {uasr:.4f}   (nhóm A)")
    print(f"SVSR  = {svsr:.4f}   (gộp)")

    # Ngoại lệ công khai: báo ở BẢNG RIÊNG. Không tính vào tỉ lệ nào, nhưng
    # cũng không bỏ qua — một ngoại lệ ngừng chạy là hồi quy chức năng.
    if ket_x:
        print("\nngoại lệ công khai/cộng đồng (2xx = ĐÚNG, không phải vi phạm):")
        da_in = set()
        for r in ket_x:
            if r.op.mo_ta in da_in:
                continue
            da_in.add(r.op.mo_ta)
            dat = "ĐẠT" if 200 <= r.status < 400 else f"HỎNG ({r.status})"
            print(f"  {dat:<12} {r.op.mo_ta}")

    kpb = kiem_tra_khong_phan_biet(args.base, args.token_a, args.class_b, args.timeout)
    print(f"lạ ≈ không tồn tại: {kpb['ma_tai_nguyen_la']} vs "
          f"{kpb['ma_tai_nguyen_khong_ton_tai']} -> "
          f"{'ĐẠT' if kpb['tuong_duong'] else 'KHÔNG ĐẠT'}")

    if dem(None, VI_PHAM):
        print("\nVI PHẠM — liệt kê từng ca:")
        seen = set()
        for r in ket:
            if r.ket_cuc == VI_PHAM and r.op.mo_ta not in seen:
                seen.add(r.op.mo_ta)
                print(f"  [{r.op.nhom}] {r.status} {r.op.method} {r.op.path}"
                      f"  — {r.op.mo_ta}")

    # --- Hậu điều kiện: đọc lại CSDL, không tin vào mã HTTP -----------------
    hdk = None
    if args.dsn and args.fixture:
        with open(args.fixture, encoding="utf-8") as fh:
            fx = json.load(fh)
        hdk = hau_dieu_kien(args.dsn, fx)
        print("\nhậu điều kiện (đọc lại CSDL sau khi bắn):")
        moi_thu_con = True
        for ten, v in hdk.items():
            con = v["tenant_con"] and v["class_con"] and v["sample_con"]
            moi_thu_con = moi_thu_con and con
            print(f"  {ten:<8} tenant={v['tenant_con']} class={v['class_con']} "
                  f"sample={v['sample_con']}  vân_tay={v['class_van_tay']}")
        if not moi_thu_con:
            print("  !! CÓ TÀI NGUYÊN BIẾN MẤT — một lượt xoá đã đi lọt dù HTTP nói khác")
    else:
        print("\nhậu điều kiện: BỎ QUA (thiếu --dsn/--fixture) — kết quả chỉ dựa "
              "trên mã HTTP, chưa chứng minh được là không có tác dụng phụ")

    # Hậu điều kiện trên cây dataset: PostgreSQL + CSV + tệp, có so băm.
    hdk_ds = None
    if args.dsn and dfx:
        hdk_ds = hau_dieu_kien_dataset(args.dsn, dfx)
        print("\nhậu điều kiện cây dataset (CSDL + CSV + tệp):")
        for nhan, v in hdk_ds.items():
            trang_thai = "NGUYÊN VẸN" if v["nguyen_ven"] else "!! ĐÃ ĐỔI"
            print(f"  {nhan:<10} {v['vai_tro']:<10} db={v['db_class']}/{v['db_sample']} "
                  f"csv={v['csv_class']}/{v['csv_sample']} tệp={v['tep_con']} "
                  f"băm_khớp={v['bam_khop']}  {trang_thai}")
        hong = [n for n, v in hdk_ds.items() if not v["nguyen_ven"]]
        if hong:
            print(f"  !! {len(hong)} đối tượng KHÔNG còn nguyên: {', '.join(hong)}")

    md = moi_truong(args.dsn, args.base) if args.dsn else {"base": args.base}
    if args.dsn:
        print(f"\nmôi trường: {md['database']} / vai {md['runtime_role']} / "
              f"superuser={md['superuser']} bypass_rls={md['bypass_rls']} / "
              f"schema v{md['schema_version']}")

    if args.json:
        phan_bo = {}
        for r in tat_ca:
            phan_bo[str(r.status)] = phan_bo.get(str(r.status), 0) + 1
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({
                "moi_truong": md,
                "so_luot": len(ops),
                "so_luot_doi_khang": len(ket),
                "so_luot_ngoai_le": len(ket_x),
                "ctivr": ctivr, "uasr": uasr, "svsr": svsr, "so_ca_mo": mo,
                "cong_bo_duoc": mo == 0,

                # Vì sao mẫu số của CTIVR (480) NHỎ HƠN số lần thử đối kháng
                # (630). Không ghi ra thì người đọc phải tự suy, và "630 lần
                # thử, 630 lần bị chặn, mẫu số 480" là đúng loại chi tiết bị
                # hỏi đầu tiên khi phản biện.
                "ctivr_mau_so": n_ct,
                "ctivr_nhom": ["B", "C"],
                "ctivr_loai_tru": tong("A"),
                "ctivr_ly_do_loai_tru": (
                    "CTIVR đo vi phạm XUYÊN TENANT. Nhóm A nhắm vào tài nguyên "
                    "CỦA CHÍNH tenant mình bằng một vai không đủ quyền, nên theo "
                    "định nghĩa nó không thể là một vi phạm xuyên tenant — nó là "
                    "vi phạm phân quyền, và đi vào UASR. Gộp A vào CTIVR sẽ làm "
                    "chính cái tên của chỉ số nói sai; xem "
                    "docs/TENANT_ISOLATION_AND_AUTHZ.md §6.2."
                ),
                "uasr_mau_so": ket_luan_duoc("A"),
                "svsr_mau_so": n_all,
                "phan_bo_status": phan_bo,
                "positive_control_passed": True,
                "hau_dieu_kien": hdk,
                "hau_dieu_kien_dataset": hdk_ds,
                "khong_kiem_duoc": [
                    "đổi phạm vi workspace/project — API chưa có endpoint nào "
                    "cho workspaces/projects, nên chiều này KHÔNG được chứng minh",
                ],
                "khong_phan_biet": kpb,
                "chi_tiet": [{"nhom": r.op.nhom, "mo_ta": r.op.mo_ta,
                              "method": r.op.method, "path": r.op.path,
                              "status": r.status, "ket_cuc": r.ket_cuc}
                             for r in ket],
            }, fh, ensure_ascii=False, indent=2)
        print(f"\nĐã ghi {args.json}")

    if mo:
        print(f"\nCÒN {mo} CA MỜ (5xx / timeout / 4xx không thuộc 401-403-404).\n"
              f"KHÔNG công bố CTIVR khi còn ca mờ: một lỗi máy chủ có thể xảy ra "
              f"SAU khi tác dụng phụ đã ghi.")
        return 2
    return 1 if dem(None, VI_PHAM) else 0


if __name__ == "__main__":
    sys.exit(main())
