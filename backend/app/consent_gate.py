"""Thực thi phạm vi đồng thuận của người ký ở chỗ CHỌN MẪU.

Vì sao module này tồn tại
-------------------------
Bảng `signer_consents` có từ lược đồ v3.4 và được thiết kế đúng: ba mức phạm vi
tăng dần, `withdrawn_at`, người ghi nhận, bằng chứng, tên người giám hộ, và một
ràng buộc "một đồng thuận còn hiệu lực cho mỗi cặp người-ký × mức".

Nhưng cho tới 2026-08-09, **toàn bộ mã đọc bảng đó chỉ có ba nơi**: lớp ghi
CSDL, khai báo RLS, và tác vụ xoá tenant. Không nơi nào ở đường xuất dữ liệu,
đường huấn luyện, đường tạo split, hay đường đóng gói phát hành nghiên cứu.

Hệ quả đo được, không phải suy đoán: một người ký chỉ đồng ý `internal_training`
thì dữ liệu của họ **vẫn** đi vào bản phát hành nghiên cứu; một người đã rút
đồng thuận thì `withdrawn_at` được ghi và **không có gì xảy ra tiếp theo**.

Ghi nhận đồng thuận mà không thực thi thì TỆ HƠN không ghi: nó tạo ra hồ sơ
trông như đã tuân thủ, trong khi hành vi thật của hệ thống bỏ qua hoàn toàn.

Quy tắc, viết ra đầy đủ vì nó là quyết định đạo đức chứ không phải chi tiết kỹ thuật
------------------------------------------------------------------------------------
Ba mức là một cái THANG, không phải ba ô đánh dấu rời nhau — lược đồ đã nói vậy
("ba mức tăng dần"). Đồng ý mức cao bao hàm mức thấp; đồng ý mức thấp KHÔNG kéo
theo mức cao.

    internal_training  <  research_release  <  public_library

Với mỗi mẫu, hỏi người ký của nó:

  * **Có đồng thuận còn hiệu lực** → cho phép tới đúng mức cao nhất đã cấp.
  * **Từng có, nay đã rút hết** → CHẶN ở MỌI mức, kể cả nội bộ. Rút là rút.
  * **Chưa từng có dòng nào** → chỉ `internal_training`, và chỉ khi bật cờ
    kế thừa (xem dưới). Không bao giờ được phát hành hay công bố.
  * **Mẫu không có `signer_id`** → như trên: nội bộ thì được kế thừa, phát hành
    thì không bao giờ.

Vì sao phải có cờ kế thừa, và vì sao nó không phải một lỗ hổng
--------------------------------------------------------------
Đo trên dữ liệu sản xuất ngày 2026-08-09: 3.860 mẫu, **0 dòng** trong
`signer_consents`, và 56,6% số mẫu không có `signer_id`. Thực thi chặt tuyệt
đối ở mọi mức sẽ loại 100% kho dữ liệu ra khỏi cả huấn luyện nội bộ — tức là
làm hỏng hệ thống đang chạy để sửa một lỗ hổng về phát hành.

Nên ranh giới đặt ở chỗ nó thật sự quan trọng: **nội bộ thì kế thừa, ra ngoài
thì phải xin phép**. Dữ liệu đã thu chính là để huấn luyện nội bộ; đưa nó vào
một bản phát hành nghiên cứu hay một thư viện công khai là một mục đích MỚI, và
mục đích mới cần đồng thuận mới. Tắt cờ này (`CONSENT_GRANDFATHER_INTERNAL=0`)
là chuyển sang chặt tuyệt đối, và lúc đó tập huấn luyện sẽ rỗng cho tới khi có
người đi thu đồng thuận — đó là hành vi ĐÚNG, chỉ là chưa dùng được hôm nay.

Cái mà cờ kế thừa KHÔNG che: một lần rút đồng thuận. Người từng ký rồi rút thì
bị chặn ở mọi mức bất kể cờ. Kế thừa chỉ áp cho người chưa từng được hỏi.

Việc mẫu vô danh không bao giờ ra được khỏi nhà là một TÍNH CHẤT, không phải
hạn chế: không truy được về ai thì không chứng minh được đã xin phép ai, và
cũng không thi hành nổi lời rút của người đó. 56,6% kho dữ liệu hiện nằm trong
tình trạng này, và con số đó giờ tự nó chặn đường phát hành thay vì chỉ nằm
trong một bản báo cáo.

Cái module này CỐ Ý không làm
-----------------------------
Không xoá gì cả. Rút đồng thuận ở đây nghĩa là "không đi vào lượt chọn mẫu tiếp
theo", không phải "biến mất khỏi ổ đĩa". `docs/needFix/COMMUNITY_DATA_COMMONS.md`
tách bốn nghĩa của thu hồi và nói rõ vì sao không được hứa nghĩa mạnh nhất; đây
là nghĩa thứ hai trong bốn nghĩa đó.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

#: Thang phạm vi, thấp → cao. Thứ tự Ở ĐÂY là nguồn sự thật; ràng buộc CHECK
#: trong `signer_consents` liệt kê cùng ba giá trị nhưng không nói chúng xếp
#: hạng thế nào, vì SQL không diễn đạt được điều đó.
SCOPE_LADDER: Tuple[str, ...] = ("internal_training", "research_release", "public_library")

#: Mức duy nhất mà dữ liệu chưa được hỏi ý kiến còn được phép đi vào.
GRANDFATHERABLE_SCOPE = "internal_training"


class ConsentScopeError(ValueError):
    """Tên phạm vi không nằm trên thang. Ném ra chứ không đoán."""


def scope_rank(scope: str) -> int:
    try:
        return SCOPE_LADDER.index(scope)
    except ValueError:
        raise ConsentScopeError(
            f"phạm vi không hợp lệ: {scope!r}; phải là một trong {SCOPE_LADDER}"
        ) from None


def grandfather_internal_enabled() -> bool:
    """Đọc cờ mỗi lần gọi, không chốt lúc nạp module.

    Bộ test cần bật/tắt được cờ này giữa các trường hợp, và một hằng số ở cấp
    module thì đóng băng theo tiến trình worker đầu tiên nạp nó.
    """
    return os.getenv("CONSENT_GRANDFATHER_INTERNAL", "1").strip().lower() not in {
        "0", "false", "no", "off",
    }


# --------------------------------------------------------------------------- lý do

#: Vì sao một mẫu bị giữ lại. Đi thẳng vào báo cáo cho người vận hành, nên phải
#: đọc được chứ không phải mã lỗi.
REASON_WITHDRAWN = "da_rut_dong_thuan"
REASON_SCOPE_TOO_LOW = "dong_thuan_thap_hon_muc_yeu_cau"
REASON_NO_CONSENT = "chua_co_dong_thuan"
REASON_UNATTRIBUTED = "khong_truy_duoc_nguoi_ky"

REASON_TEXT: Dict[str, str] = {
    REASON_WITHDRAWN: "người ký đã rút đồng thuận",
    REASON_SCOPE_TOO_LOW: "đồng thuận hiện có thấp hơn mức yêu cầu",
    REASON_NO_CONSENT: "chưa có đồng thuận nào cho người ký này",
    REASON_UNATTRIBUTED: "mẫu không có signer_id nên không xác định được ai đã đồng ý",
}


@dataclass
class SignerConsent:
    """Trạng thái đồng thuận đã rút gọn của MỘT người ký."""

    highest_live_rank: Optional[int] = None   # None = không có đồng thuận còn hiệu lực
    has_any_record: bool = False              # từng được hỏi, dù nay đã rút hết

    def allows(self, wanted_rank: int) -> Tuple[bool, str]:
        if self.highest_live_rank is not None:
            if self.highest_live_rank >= wanted_rank:
                return True, ""
            return False, REASON_SCOPE_TOO_LOW
        if self.has_any_record:
            # Từng ký, nay không còn dòng nào hiệu lực → đã rút. Kế thừa KHÔNG
            # áp ở đây: cờ kế thừa dành cho người chưa từng được hỏi.
            return False, REASON_WITHDRAWN
        if wanted_rank == scope_rank(GRANDFATHERABLE_SCOPE) and grandfather_internal_enabled():
            return True, ""
        return False, REASON_NO_CONSENT


@dataclass
class GateResult:
    """Kết quả lọc: phần đi tiếp, phần bị giữ lại, và vì sao."""

    scope: str
    kept: List[Dict[str, Any]] = field(default_factory=list)
    withheld: List[Dict[str, Any]] = field(default_factory=list)
    #: lý do → số mẫu. Đủ để in một dòng tổng kết mà không phải duyệt lại.
    reasons: Dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.kept) + len(self.withheld)

    def summary(self) -> str:
        if not self.withheld:
            return f"{len(self.kept)}/{self.total} mẫu đủ điều kiện cho '{self.scope}'"
        parts = ", ".join(
            f"{count} {REASON_TEXT.get(reason, reason)}"
            for reason, count in sorted(self.reasons.items(), key=lambda kv: -kv[1])
        )
        return (f"{len(self.kept)}/{self.total} mẫu đủ điều kiện cho '{self.scope}'; "
                f"giữ lại {len(self.withheld)} ({parts})")


# --------------------------------------------------------------------------- đọc CSDL


def _resolve_chain(direct: Dict[str, str]) -> Dict[str, str]:
    """Đi hết chuỗi gộp A→B→C thành A→C, B→C.

    Tách khỏi phần đọc CSDL để test được mà không cần cơ sở dữ liệu — và vì
    logic chống vòng lặp dưới đây là thứ đáng được nhìn riêng.
    """
    resolved: Dict[str, str] = {}
    for old in direct:
        seen = {old}
        cur = direct[old]
        # Bản ghi vòng tròn (A→B→A) đáng lẽ không tồn tại, nhưng ràng buộc
        # `signer_aliases_not_self` chỉ chặn được vòng độ dài 1. Không có `seen`
        # thì một vòng độ dài 2 treo cả tiến trình.
        while cur in direct and cur not in seen:
            seen.add(cur)
            cur = direct[cur]
        resolved[old] = cur
    return resolved


def _resolve_aliases(tenant_id: str) -> Dict[str, str]:
    """old_signer_id → new_signer_id, đã đi hết chuỗi gộp.

    Bỏ qua bước này thì một lần gộp người ký sẽ ÂM THẦM làm mất đồng thuận: mẫu
    cũ vẫn trỏ tới id cũ, còn dòng đồng thuận thì gắn vào id mới, nên người đã
    ký lại bị đọc thành "chưa từng có đồng thuận".
    """
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT old_signer_id, new_signer_id FROM signer_aliases WHERE tenant_id = %s",
        (tenant_id,),
    )
    return _resolve_chain({r["old_signer_id"]: r["new_signer_id"] for r in rows})


def load_consents(tenant_id: str) -> Dict[str, SignerConsent]:
    """Trạng thái đồng thuận của mọi người ký trong một tenant, MỘT lượt truy vấn.

    Một lượt cho cả tenant chứ không phải một lượt mỗi mẫu: đường gọi là các
    tác vụ nền duyệt hàng nghìn dòng, và một truy vấn mỗi dòng biến bộ lọc này
    thành thứ người ta sẽ tắt đi vì chậm.
    """
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT signer_id, scope, withdrawn_at FROM signer_consents WHERE tenant_id = %s",
        (tenant_id,),
    )

    if not rows:
        # KHÔNG phải lỗi, nhưng gần như luôn là thứ người ta muốn biết. Hai
        # nguyên nhân cho cùng một kết quả rỗng:
        #
        #   * chưa ai ký gì cả (tình trạng thật ngày 2026-08-09: 0 dòng);
        #   * người gọi không có phạm vi tenant, nên RLS lọc sạch.
        #
        # Cả hai đều làm cổng KHOÁ CHẶT hơn chứ không mở ra, nên không cần ném
        # lỗi — nhưng "mọi mẫu đều bị chặn" mà không có dòng log nào giải thích
        # là thứ tốn nửa ngày để lần ra.
        from app.tenant_context import describe_scope

        logger.warning("[CONSENT] khong co dong thuan nao cho tenant %r (pham vi: %s) "
                       "— moi muc phat hanh se tra ve RONG", tenant_id, describe_scope())

    state: Dict[str, SignerConsent] = {}
    for row in rows:
        signer = row["signer_id"]
        entry = state.setdefault(signer, SignerConsent())
        entry.has_any_record = True
        if row["withdrawn_at"] is not None:
            continue
        try:
            rank = scope_rank(row["scope"])
        except ConsentScopeError:
            # Ràng buộc CHECK đáng lẽ đã chặn. Nếu vẫn lọt thì coi như không có
            # — một giá trị lạ không được phép mở rộng quyền.
            logger.warning("[CONSENT] bỏ qua phạm vi lạ %r của người ký %s",
                           row["scope"], signer)
            continue
        if entry.highest_live_rank is None or rank > entry.highest_live_rank:
            entry.highest_live_rank = rank
    return state


# --------------------------------------------------------------------------- lọc


def _signer_of(row: Dict[str, Any]) -> str:
    """Chỉ đọc `signer_id`. CỐ Ý không lùi về `user_id`.

    `user_id` là văn bản tự do — "Trâm"/"Tram" là một người, "Trân" là người
    khác, và một dòng có nguyên UUID lọt vào ô tên. Lùi về nó nghĩa là gán đồng
    thuận của người này cho dữ liệu của người kia dựa trên trùng chính tả. Thà
    coi là vô danh (và do đó không phát hành được) còn hơn quy kết sai.
    """
    value = row.get("signer_id")
    return str(value).strip() if value is not None else ""


def filter_rows(
    rows: Iterable[Dict[str, Any]],
    *,
    scope: str,
    tenant_id: Optional[str] = None,
    consents: Optional[Dict[str, SignerConsent]] = None,
    aliases: Optional[Dict[str, str]] = None,
) -> GateResult:
    """Chia các dòng mẫu thành phần được phép dùng ở `scope` và phần bị giữ lại.

    `consents` / `aliases` truyền vào được để người gọi tự nạp một lần rồi lọc
    nhiều lô — và để test chạy được mà không cần cơ sở dữ liệu.
    """
    wanted = scope_rank(scope)
    rows = list(rows)

    if consents is None or aliases is None:
        tid = tenant_id or _default_tenant()
        if consents is None:
            consents = load_consents(tid)
        if aliases is None:
            aliases = _resolve_aliases(tid)

    result = GateResult(scope=scope)
    for row in rows:
        signer = _signer_of(row)
        if not signer:
            if wanted == scope_rank(GRANDFATHERABLE_SCOPE) and grandfather_internal_enabled():
                result.kept.append(row)
            else:
                result.withheld.append(row)
                result.reasons[REASON_UNATTRIBUTED] = \
                    result.reasons.get(REASON_UNATTRIBUTED, 0) + 1
            continue

        signer = aliases.get(signer, signer)
        allowed, reason = consents.get(signer, SignerConsent()).allows(wanted)
        if allowed:
            result.kept.append(row)
        else:
            result.withheld.append(row)
            result.reasons[reason] = result.reasons.get(reason, 0) + 1
    return result


def _default_tenant() -> str:
    from app.tenant_context import current_tenant
    from app.config import settings

    return current_tenant() or str(settings.public_tenant_id)


# --------------------------------------------------------------------------- cổng chặn


class ConsentGateBlocked(RuntimeError):
    """Ném ra khi một đường CHỈ ĐƯỢC chạy trên dữ liệu đã có đồng thuận."""

    def __init__(self, result: GateResult) -> None:
        super().__init__(result.summary())
        self.result = result


def require_all(result: GateResult) -> GateResult:
    """Chặn hẳn nếu có bất kỳ mẫu nào bị giữ lại.

    Dùng cho đường phát hành: một bản phát hành nghiên cứu thiếu vài mẫu so với
    manifest đã ký là một bản phát hành SAI, không phải một bản phát hành nhỏ
    hơn. Người vận hành phải thấy con số rồi tự quyết, chứ không để hệ thống âm
    thầm rút gọn tập dữ liệu sau lưng.
    """
    if result.withheld:
        raise ConsentGateBlocked(result)
    return result


# --------------------------------------------------------------------------- ảnh chụp
#
# Vì sao cần ảnh chụp, chứ không phải cứ hỏi thẳng CSDL
# ------------------------------------------------------
# Các script dựng manifest / chia split / đóng gói phát hành chạy TRÊN MÁY CHỦ,
# ngoài mạng compose, và Postgres không mở cổng ra host (đã kiểm: `docker port
# voya_postgres` không trả gì). Bắt chúng nối CSDL nghĩa là biến chúng thành
# thứ không chạy được, và một cổng không chạy được là một cổng bị gỡ bỏ.
#
# Nên trạng thái đồng thuận được XUẤT thành một tệp có dấu thời gian và mã băm,
# giống hệt cách kho này đã làm với manifest dữ liệu và SOT. Script offline đọc
# tệp đó, và TỪ CHỐI chạy khi tệp vắng mặt hoặc quá cũ — mặc định-từ-chối, để
# quên chạy lệnh xuất không âm thầm biến thành "không lọc gì cả".

SNAPSHOT_VERSION = 1

#: Ảnh chụp cũ hơn ngần này ngày thì coi như không dùng được. Một lời rút đồng
#: thuận phải có đường tới bản phát hành kế tiếp trong thời gian hợp lý; con số
#: này chính là lời hứa đó, viết thành mã.
SNAPSHOT_MAX_AGE_DAYS = 7


def build_snapshot(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Kết tinh trạng thái đồng thuận hiện tại thành một dict tuần tự hoá được."""
    import hashlib
    import json
    from datetime import datetime, timezone

    tid = tenant_id or _default_tenant()
    consents = load_consents(tid)
    aliases = _resolve_aliases(tid)

    signers = {
        signer: {
            "highest_live_rank": state.highest_live_rank,
            "has_any_record": state.has_any_record,
        }
        for signer, state in sorted(consents.items())
    }
    body = {
        "snapshot_version": SNAPSHOT_VERSION,
        "tenant_id": tid,
        "scope_ladder": list(SCOPE_LADDER),
        "signers": signers,
        "aliases": dict(sorted(aliases.items())),
    }
    # Băm phần THÂN, không băm cả tệp: `generated_at` đổi mỗi lần chạy, nên băm
    # cả tệp thì hai ảnh chụp giống hệt nhau về nội dung lại cho hai mã khác
    # nhau, và không ai đối chiếu được "đồng thuận có đổi gì không".
    payload = json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    body["content_hash"] = hashlib.sha256(payload).hexdigest()
    body["generated_at"] = datetime.now(timezone.utc).isoformat()
    return body


class SnapshotUnusable(RuntimeError):
    """Ảnh chụp vắng mặt, hỏng, hoặc quá cũ. Mặc định là TỪ CHỐI chạy."""


def load_snapshot(
    path: Any,
    *,
    max_age_days: Optional[int] = SNAPSHOT_MAX_AGE_DAYS,
) -> Tuple[Dict[str, SignerConsent], Dict[str, str], Dict[str, Any]]:
    """Đọc ảnh chụp → (đồng thuận, bí danh, siêu dữ liệu). Ném khi không dùng được."""
    import json
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    p = Path(str(path))
    if not p.is_file():
        raise SnapshotUnusable(
            f"không có ảnh chụp đồng thuận tại {p}. Chạy trong container: "
            f"python -m app.cli.consent_snapshot --out dataset/consent_snapshot.json"
        )
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SnapshotUnusable(f"ảnh chụp đồng thuận {p} không đọc được: {exc}") from exc

    if int(data.get("snapshot_version", 0)) != SNAPSHOT_VERSION:
        raise SnapshotUnusable(
            f"ảnh chụp {p} thuộc phiên bản {data.get('snapshot_version')!r}, "
            f"mã này đọc phiên bản {SNAPSHOT_VERSION}"
        )

    ladder = tuple(data.get("scope_ladder") or ())
    if ladder != SCOPE_LADDER:
        # Thang phạm vi đổi nghĩa là thứ hạng đổi nghĩa. Diễn giải một ảnh chụp
        # cũ theo thang mới sẽ nâng hoặc hạ quyền của mọi người ký cùng lúc.
        raise SnapshotUnusable(
            f"ảnh chụp {p} dùng thang phạm vi {ladder}, mã này dùng {SCOPE_LADDER}"
        )

    # Đối chiếu mã băm: tệp này đi qua ổ đĩa chia sẻ và qua tay người, và một
    # ảnh chụp bị sửa tay là cách rẻ nhất để mở toang cổng mà không ai thấy.
    # Băm lại đúng phần thân, theo cùng cách `build_snapshot` đã băm.
    import hashlib

    body = {k: data[k] for k in
            ("snapshot_version", "tenant_id", "scope_ladder", "signers", "aliases")
            if k in data}
    recomputed = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    stored = str(data.get("content_hash") or "")
    if stored and stored != recomputed:
        raise SnapshotUnusable(
            f"ảnh chụp {p} có content_hash không khớp nội dung "
            f"(lưu {stored[:12]}…, tính lại {recomputed[:12]}…) — tệp đã bị sửa "
            f"hoặc hỏng. Xuất lại thay vì dùng nó."
        )

    if max_age_days is not None:
        try:
            generated = datetime.fromisoformat(str(data["generated_at"]))
        except Exception as exc:
            raise SnapshotUnusable(f"ảnh chụp {p} thiếu generated_at hợp lệ") from exc
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - generated
        if age > timedelta(days=max_age_days):
            raise SnapshotUnusable(
                f"ảnh chụp {p} đã {age.days} ngày tuổi (tối đa {max_age_days}). "
                f"Một lời rút đồng thuận trong khoảng đó sẽ không được thấy — "
                f"chạy lại lệnh xuất ảnh chụp."
            )

    consents = {
        signer: SignerConsent(
            highest_live_rank=entry.get("highest_live_rank"),
            has_any_record=bool(entry.get("has_any_record")),
        )
        for signer, entry in (data.get("signers") or {}).items()
    }
    aliases = dict(data.get("aliases") or {})
    return consents, aliases, data


#: Mục đích chạy huấn luyện → mức phạm vi phải có. Một lượt "research" sinh ra
#: checkpoint và số liệu đi vào bài báo, tức là dữ liệu rời khỏi phạm vi nội bộ.
RUN_PURPOSE_SCOPE: Dict[str, str] = {
    "research": "research_release",
    "release": "public_library",
}


def scope_for_run_purpose(purpose: Optional[str]) -> str:
    return RUN_PURPOSE_SCOPE.get(str(purpose or "").strip().lower(), "internal_training")


def audit_csv_files(
    paths: Iterable[Any],
    *,
    scope: str,
    tenant_id: Optional[str] = None,
    consents: Optional[Dict[str, SignerConsent]] = None,
    aliases: Optional[Dict[str, str]] = None,
) -> GateResult:
    """Soi các tệp split đã dựng sẵn, thay vì soi lượt chọn mẫu.

    Cần một lối vào riêng cho tệp vì trình huấn luyện KHÔNG đọc `samples.csv` —
    nó đọc `train.csv` / `val.csv` / `test.csv` đã đóng băng từ trước, có thể từ
    nhiều tuần trước. Một người rút đồng thuận hôm nay không làm thay đổi những
    tệp đó, nên chặn ở lúc dựng split là chưa đủ: phải hỏi lại ngay trước khi
    chạy.

    Tệp không tồn tại thì BỎ QUA chứ không coi là rỗng — trình huấn luyện sẽ tự
    báo lỗi thiếu tệp, và một cổng đồng thuận trả "sạch" cho một đường dẫn gõ
    sai là đúng thứ không được phép xảy ra.
    """
    import csv
    from pathlib import Path

    rows: List[Dict[str, Any]] = []
    for raw_path in paths:
        path = Path(str(raw_path))
        if not path.is_file():
            continue
        with path.open(newline="", encoding="utf-8") as fh:
            rows.extend(dict(r) for r in csv.DictReader(fh))
    return filter_rows(rows, scope=scope, tenant_id=tenant_id,
                       consents=consents, aliases=aliases)


def enforce(
    rows: Sequence[Dict[str, Any]],
    *,
    scope: str,
    purpose: str,
    tenant_id: Optional[str] = None,
    strict: bool = False,
) -> List[Dict[str, Any]]:
    """Lối vào một-dòng cho mọi đường chọn mẫu. Lọc, ghi log, trả về phần đi tiếp.

    `purpose` chỉ để đọc log — nó trả lời "ai đã lọc và để làm gì" khi có người
    nhìn vào một tập huấn luyện nhỏ hơn mong đợi sáu tháng sau.
    """
    result = filter_rows(rows, scope=scope, tenant_id=tenant_id)
    if result.withheld:
        logger.warning("[CONSENT] %s: %s", purpose, result.summary())
    else:
        logger.info("[CONSENT] %s: %s", purpose, result.summary())
    if strict:
        require_all(result)
    return result.kept


# --------------------------------------------------------------------------- cầu nối
#
# Nối chấp thuận CỦA TÀI KHOẢN sang đồng thuận CỦA NGƯỜI KÝ
# ---------------------------------------------------------
# Hai bảng, hai chủ thể, và trước 2026-08-09 không có đường nào nối chúng:
#
#   `user_consents`   — chủ tài khoản đã ký văn bản nào, bản số mấy.
#   `signer_consents` — người xuất hiện TRONG dữ liệu cho phép dùng tới mức nào.
#
# Hệ quả đo được: 10 tài khoản đã chấp thuận `terms` và `privacy`, và **0 dòng**
# trong `signer_consents`. Người dùng bấm đồng ý, hệ thống ghi nhận, rồi cổng
# đồng thuận vẫn đọc ra "chưa ai cho phép gì".
#
# Vì sao mức là `internal_training`, không phải mức cao hơn
# ---------------------------------------------------------
# Đọc thẳng từ văn bản `data_contribution` bản 2026-08-08, mục 4:
#
#   **Có:** huấn luyện mô hình; đo và so sánh chất lượng; xây dựng bộ dữ liệu
#   phục vụ nghiên cứu CỦA TỔ CHỨC BẠN.
#
#   **Chỉ khi bạn đồng ý riêng bằng văn bản:** đưa vào bộ dữ liệu công bố cùng
#   bài báo; chia sẻ cho nhóm nghiên cứu NGOÀI tổ chức bạn; dùng làm ví dụ
#   minh hoạ.
#
# Ba mức của lược đồ chính là ba đoạn đó, và ranh giới "chỉ khi đồng ý riêng"
# nằm đúng giữa `internal_training` và `research_release`. Bản văn đã nói rồi;
# hàm này chỉ thi hành cho đúng lời đã nói.
#
# Nâng mức tự động từ một văn bản DUY NHẤT là điều không được làm: nó biến một
# lần bấm "tôi đồng ý đóng góp" thành giấy phép công bố khuôn mặt người ta.

#: Văn bản pháp lý → mức phạm vi mà việc ký nó CẤP.
CONSENT_DOCUMENT_SCOPE: Dict[str, str] = {
    "data_contribution": "internal_training",
}


def sync_signer_consent(user_id: str, kind: str, *, withdrawn: bool = False) -> Optional[str]:
    """Phản chiếu một chấp thuận của tài khoản sang bảng đồng thuận người ký.

    Trả về `signer_id` đã ghi, hoặc None khi không có gì để làm.

    Idempotent. Chỉ mục `uq_signer_consents_live` cho phép đúng một dòng còn
    hiệu lực cho mỗi (tenant, người ký, mức), nên bấm đồng ý hai lần không sinh
    hai dòng — đúng thứ người dùng mong đợi: **đồng ý rồi thì nó cứ ở đó.**

    Không bao giờ ném ra ngoài. Đường gọi là lúc người dùng đang đăng ký hoặc
    đang bấm đồng ý, và một trục trặc ở bảng phản chiếu không được phép làm hỏng
    chính hành động mà nó đang ghi lại. Hỏng thì log, và
    `cli/backfill_signer_consents.py` vá lại sau.
    """
    scope = CONSENT_DOCUMENT_SCOPE.get(kind)
    if not scope:
        return None

    try:
        return _sync_signer_consent_inner(user_id, kind, scope, withdrawn)
    except Exception as exc:
        logger.error("[CONSENT] khong phan chieu duoc chap thuan %s cua %s (%s: %s) "
                     "— chay app.cli.backfill_signer_consents de va",
                     kind, user_id, type(exc).__name__, exc)
        return None


def _sync_signer_consent_inner(user_id: str, kind: str, scope: str,
                               withdrawn: bool) -> Optional[str]:
    import uuid as _uuid

    from app.storage.metadata_db import _cursor, _fetch_all
    from app.tenant_context import system_scope

    # `system_scope` vì bảng `signers` gắn với TÀI KHOẢN, không gắn với phiên
    # làm việc: lời gọi tới đây có thể đến từ luồng đăng ký, nơi người dùng chưa
    # thuộc tenant nào.
    with system_scope("consent: phan chieu chap thuan tai khoan sang nguoi ky"):
        # `ORDER BY signer_id` để kết quả xác định. Một tài khoản đáng lẽ chỉ có
        # một hồ sơ người ký, nhưng "đáng lẽ" không phải ràng buộc: chọn bừa
        # hàng đầu tiên sẽ làm cùng một lời gọi cho hai kết quả khác nhau ở hai
        # lần chạy, và đó là loại lỗi không tài nào tái hiện được.
        rows = _fetch_all(
            "SELECT signer_id, tenant_id FROM signers WHERE external_user_id = %s "
            "ORDER BY signer_id",
            (str(user_id),))
        if not rows:
            # Chưa có hồ sơ người ký. KHÔNG tự tạo ở đây: hồ sơ người ký được
            # lập lúc đóng góp lần đầu (`signers.resolve_signer_for_user`), và
            # tạo sớm ở đây sẽ đẻ ra một hàng người ký cho mọi tài khoản chỉ
            # ghé xem. Chấp thuận vẫn nằm nguyên trong `user_consents`, và
            # đường thu mẫu gọi lại hàm này ngay sau khi lập hồ sơ.
            logger.info("[CONSENT] %s da ky %s nhung chua co ho so nguoi ky — "
                        "se phan chieu khi dong gop lan dau", user_id, kind)
            return None

        signer_id = rows[0]["signer_id"]
        tenant_id = rows[0]["tenant_id"]
        doc_version = _current_document_version(kind)
        if doc_version is None:
            logger.warning("[CONSENT] khong co ban %s dang hieu luc — bo qua", kind)
            return None

        with _cursor() as cur:
            if withdrawn:
                cur.execute(
                    "UPDATE signer_consents SET withdrawn_at = now() "
                    "WHERE tenant_id = %s AND signer_id = %s AND scope = %s "
                    "AND withdrawn_at IS NULL",
                    (tenant_id, signer_id, scope))
                logger.info("[CONSENT] rut dong thuan %s cua nguoi ky %s", scope, signer_id)
                return signer_id

            # Đã có dòng còn hiệu lực thì thôi — đó chính là "đồng ý rồi thì
            # nó cứ ở đó". Ghi đè sẽ đổi `granted_at`, tức là xoá mất mốc thời
            # gian người ta thật sự đồng ý.
            cur.execute(
                "SELECT consent_id FROM signer_consents "
                "WHERE tenant_id = %s AND signer_id = %s AND scope = %s "
                "AND withdrawn_at IS NULL",
                (tenant_id, signer_id, scope))
            if cur.fetchone():
                return signer_id

            cur.execute(
                "INSERT INTO signer_consents "
                "(consent_id, tenant_id, signer_id, scope, kind, version, evidence) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (str(_uuid.uuid4()), tenant_id, signer_id, scope, kind, doc_version,
                 f"phan chieu tu user_consents cua tai khoan {user_id}"))
            logger.info("[CONSENT] nguoi ky %s duoc cap muc %s (tu %s ban %s)",
                        signer_id, scope, kind, doc_version)
        return signer_id


def _current_document_version(kind: str) -> Optional[str]:
    """Số hiệu bản đang hiệu lực. Khoá ngoại `fk_signer_consents_document` đòi nó có thật."""
    from app import legal

    doc = legal.current_document(kind)
    return str(doc["version"]) if doc else None
