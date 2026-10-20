"""Một cửa duy nhất để một lượt chạy biết nó đang tiêu thụ split nào.

Vì sao phải có, và vì sao chỉ được có MỘT:

Trước lượt này, mỗi nơi tự dựng đường dẫn. `train_tcn` có giá trị mặc định trỏ
vào `processed/splits/{train,val,test}.csv`; `training_tasks._build_cmd` chỉ
truyền đường dẫn tường minh ở nhánh nghiên cứu; `_split_csvs_of` đọc lại từ
`cmd` nên trả RỖNG cho nhánh legacy, khiến cổng đồng thuận không soi lượt
huấn luyện legacy nào. Ba cách hiểu khác nhau về cùng một câu hỏi "lượt này
đọc tệp nào", và chúng lệch nhau được mà không ai biết.

Hai không gian tên, KHÔNG trộn
------------------------------
`research`      `processed/splits/{train,val,test}.csv` — ba tệp ĐÓNG BĂNG.
                Không dựng lại. Đối chiếu với `FROZEN_RESEARCH_SPLITS.json`.
`operational`   `processed/splits/operational/<split_id>/` — hiện vật BẤT BIẾN,
                chỉ-tạo-mới. Không có khái niệm "split mới nhất": một lượt
                chạy ghim đúng một `split_id`, và `split_id` đó không bao giờ
                trỏ vào nội dung khác.

FAIL-CLOSED, và đây là bất biến quan trọng nhất của tệp này: một lượt chạy vận
hành KHÔNG có `split_id` thì DỪNG. Không rơi về ba tệp nghiên cứu. Rơi được
nghĩa là một lượt huấn luyện vận hành có thể lặng lẽ học trên mốc nghiên cứu
đóng băng, và checkpoint sẽ khai một nguồn gốc không đúng.

`resolve` không chỉ TÌM ĐƯỢC tệp — nó trả về hiện vật đã XÁC MINH. Chép ba CSV
từ hiện vật Y vào thư mục mang tên X sẽ bị từ chối, vì `split_id` và mã băm
từng tệp đều nằm trong bản khai.

Chủ sở hữu (C2b)
----------------
Một hiện vật vận hành phải TỰ KHAI nó thuộc tổ chức nào, và lời khai đó lấy từ
NGỮ CẢNH TẠO — không phải từ lượt huấn luyện đầu tiên muốn dùng nó. Suy chủ từ
bên tiêu thụ là tự cấp quyền: ai hỏi trước thì thành chủ.

```
purpose = operational, có split_id   ->  BẮT BUỘC có chủ
purpose = research                   ->  KHÔNG có khái niệm chủ tenant
```

Tầng này chỉ ĐỌC và XÁC MINH lời khai; nó chưa hỏi "tenant đang chạy có được
dùng hiện vật này không". Biểu diễn quyền sở hữu trước, cưỡng chế sau — làm
ngược lại chỉ tạo ra một phép kiểm bảo mật không có dữ liệu thẩm quyền phía sau.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

_log = logging.getLogger(__name__)

PURPOSE_RESEARCH = "research"
PURPOSE_OPERATIONAL = "operational"

OPERATIONAL_DIRNAME = "operational"
METADATA_NAME = "split_metadata.json"
FROZEN_REGISTRY_NAME = "FROZEN_RESEARCH_SPLITS.json"
PARTS = ("train", "val", "test")

OWNER_KEY = "tenant_id"
OWNER_BINDING_KEY = "owner_binding"

#: BA trạng thái, cố ý KHÔNG phải một `Optional[str]`.
#:
#: `None` một mình bắt người gọi tự diễn giải, và hai cách diễn giải đúng đắn
#: lại dẫn tới hai hành vi trái ngược: hiện vật nghiên cứu không có chủ tenant
#: là ĐÚNG HỢP ĐỒNG, còn hiện vật vận hành không có chủ là một khoảng trống
#: thẩm quyền. Gộp hai thứ đó vào một `None` là mời người viết sau xử lý chúng
#: như nhau — và cách xử lý "như nhau" duy nhất còn lại sẽ là cho qua.
OWNER_OWNED = "owned"                    # có chủ, đã xác minh ràng buộc
OWNER_UNKNOWN = "unknown"                # hiện vật vận hành có TRƯỚC hợp đồng này
OWNER_NOT_APPLICABLE = "not_applicable"  # nghiên cứu đóng băng: không có chủ tenant


class SplitArtifactError(Exception):
    """Không xác minh được hiện vật. Luôn là lý do để DỪNG."""


@dataclass(frozen=True)
class OwnerVerdict:
    """Hiện vật này thuộc về ai, và vì sao ta tin như vậy."""
    state: str
    tenant_id: Optional[str]
    reason: str

    @property
    def ok(self) -> bool:
        return self.state == OWNER_OWNED


@dataclass(frozen=True)
class SplitArtifact:
    split_id: str
    purpose: str
    train_csv: Path
    val_csv: Path
    test_csv: Path
    metadata: Dict[str, object] = field(default_factory=dict)
    #: Mặc định là `unknown`, không phải `owned`: ai dựng một `SplitArtifact`
    #: bằng tay mà quên khai chủ sở hữu thì được coi là KHÔNG BIẾT chủ, chứ
    #: không lặng lẽ được coi là hợp lệ.
    tenant_id: Optional[str] = None
    owner_state: str = OWNER_UNKNOWN

    @property
    def csv_paths(self):
        return [self.train_csv, self.val_csv, self.test_csv]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_hashes(directory: Path) -> Dict[str, Dict[str, object]]:
    """`{'train.csv': {'sha256': …, 'bytes': …}}` cho ba tệp trong thư mục."""
    ra = {}
    for ten in PARTS:
        p = Path(directory) / f"{ten}.csv"
        ra[f"{ten}.csv"] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    return ra


def operational_root(splits_root: Path) -> Path:
    return Path(splits_root) / OPERATIONAL_DIRNAME


def _kiem_ba_tep(thu_muc: Path, khai_files, nhan: str) -> None:
    """Đối chiếu mã băm. Đây là chỗ bắt được việc chép tệp từ hiện vật khác."""
    if not isinstance(khai_files, dict) or not khai_files:
        raise SplitArtifactError(
            f"{nhan}: bản khai không có mục `files` — không xác minh được nội "
            f"dung, chỉ biết là tệp có tồn tại. Đó chưa phải xác minh.")
    for ten in PARTS:
        khoa = f"{ten}.csv"
        muc = khai_files.get(khoa)
        if not isinstance(muc, dict) or not str(muc.get("sha256") or "").strip():
            raise SplitArtifactError(f"{nhan}: bản khai thiếu sha256 cho {khoa}")
        p = thu_muc / khoa
        if not p.exists():
            raise SplitArtifactError(f"{nhan}: thiếu tệp {p}")
        that = sha256_file(p)
        if that != muc["sha256"]:
            raise SplitArtifactError(
                f"{nhan}: {khoa} không khớp mã băm đã khai. "
                f"khai={muc['sha256']} thật={that}. Hiện vật đã bị sửa, hoặc "
                f"ba tệp được chép vào đây từ một hiện vật khác.")


def owner_binding(*, split_id: str, tenant_id: str,
                  files: Dict[str, Dict[str, object]]) -> str:
    """Gắn chủ sở hữu vào CHÍNH nội dung hiện vật.

    Vì sao không chỉ ghi một trường `tenant_id` trần:

    Ba tệp CSV đã có mã băm, nên sửa nội dung là bị bắt. Nhưng `split_metadata.json`
    không tự băm chính nó, nên một dòng `"tenant_id": "..."` sửa bằng tay — hoặc
    thêm mới bằng tay vào một hiện vật cũ chưa có chủ — sẽ đi qua mọi phép kiểm
    hiện có. Đó đúng là hai việc mà hợp đồng này cấm: đổi chủ bằng cách sửa JSON,
    và tự cấp chủ cho một hiện vật không rõ nguồn gốc.

    Ràng buộc này khoá `tenant_id` vào `split_id` và vào mã băm ba tệp, nên nó
    cũng không chép được từ hiện vật khác sang.

    GIỚI HẠN, nói thẳng để không ai nhầm nó là thứ nó không phải:
    đây là bằng chứng-chống-sửa, KHÔNG phải ranh giới thẩm quyền. Ai có quyền
    ghi vào cây hiện vật và đọc được hàm này thì tính lại được ràng buộc. Ranh
    giới thật vẫn là quyền ghi trên hệ tệp. Cái nó bắt được là những gì thực sự
    hay xảy ra: sửa tay, chép nửa vời, backfill "cho tiện".
    """
    canon = json.dumps(
        {
            "split_id": str(split_id or "").strip(),
            "tenant_id": str(tenant_id or "").strip(),
            "files": {k: str((files or {}).get(k, {}).get("sha256") or "")
                      for k in sorted(files or {})},
        },
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def read_owner(meta: Dict[str, object], *, split_id: str) -> OwnerVerdict:
    """MỘT bản cài đặt duy nhất của quy tắc chủ sở hữu.

    Cả `resolve_operational` lẫn công cụ rà soát hiện vật đều gọi hàm này. Hai
    bản cài đặt của cùng một quy ước là đúng cái bẫy đã làm mọi hiện vật vận
    hành bị từ chối hôm 15/08 — mỗi phía tự nhất quán với chính mình, và cả hai
    đều xanh.

    Phân biệt hai loại hỏng:

    ```
    thiếu chủ         ->  TRẠNG THÁI `unknown`, trả về để người gọi quyết định
    chủ bị giả mạo    ->  NỔ ngay, cùng hạng với sai mã băm tệp
    ```

    "Thiếu chủ" không được ném lỗi ở đây vì các hiện vật vận hành dựng trước hợp
    đồng này vẫn tồn tại thật, và việc chúng thuộc về ai là một câu hỏi chưa có
    lời đáp — không phải một hiện vật hỏng. Nơi quyết định "chưa biết chủ thì có
    được dùng không" là bên cưỡng chế, không phải bên đọc.
    """
    khai_owner = str((meta or {}).get(OWNER_KEY) or "").strip()
    khai_binding = str((meta or {}).get(OWNER_BINDING_KEY) or "").strip()

    if not khai_owner and not khai_binding:
        return OwnerVerdict(
            state=OWNER_UNKNOWN, tenant_id=None,
            reason=(f"{split_id}: hiện vật không khai `{OWNER_KEY}`. Chủ sở hữu "
                    f"KHÔNG BIẾT — và không biết thì không suy ra được. Không "
                    f"phải `default`, không phải tenant của lượt chạy đang hỏi."))

    if not khai_owner:
        raise SplitArtifactError(
            f"{split_id}: có `{OWNER_BINDING_KEY}` nhưng không có `{OWNER_KEY}`. "
            f"Bản khai tự mâu thuẫn.")

    mong_doi = owner_binding(split_id=split_id, tenant_id=khai_owner,
                             files=(meta or {}).get("files") or {})
    if khai_binding != mong_doi:
        raise SplitArtifactError(
            f"{split_id}: `{OWNER_KEY}={khai_owner!r}` không khớp "
            f"`{OWNER_BINDING_KEY}`. Chủ sở hữu của một hiện vật là BẤT BIẾN và "
            f"chỉ do bên tạo đặt; nó không đổi được bằng cách sửa JSON. Nếu cần "
            f"chuyển quyền sở hữu thì đó là một quy trình riêng, có ghi vết — "
            f"không phải một lượt sửa tệp.")

    return OwnerVerdict(state=OWNER_OWNED, tenant_id=khai_owner,
                        reason=f"{split_id}: chủ sở hữu {khai_owner!r}, ràng buộc khớp.")


def _khong_tim_thay(splits_root: Path, split_id: str) -> SplitArtifactError:
    """MỘT câu trả lời cho ba câu hỏi khác nhau, và đó là chủ ý.

    "Không tồn tại", "thuộc tổ chức khác" và "không rõ chủ" phải trông giống hệt
    nhau với người gọi. Nếu ba trạng thái cho ba câu trả lời khác nhau thì
    `split_id` trở thành một máy đoán: một tenant dò tên và đọc được cái gì tồn
    tại bên trong tổ chức khác, dù không đọc được nội dung. Đây đúng là lớp rò
    rỉ "existence oracle" đã kiểm ở A2 — chỉ khác mặt phẳng lưu trữ.

    Lý do thật vẫn được ghi ở mức ERROR phía máy chủ; người vận hành đọc nhật ký,
    người gọi thì không.
    """
    return SplitArtifactError(
        f"không có hiện vật vận hành `{split_id}` tại "
        f"{operational_root(splits_root) / str(split_id).strip()}. "
        f"Dựng bằng make_splits.py --operational_split_id={split_id} "
        f"--tenant_id=<ID>.")


def resolve_operational(splits_root: Path, split_id: str, *,
                        tenant_id: str) -> SplitArtifact:
    """`tenant_id` là tham số BẮT BUỘC, cố ý không có giá trị mặc định.

    Một mặc định — kể cả `None` — biến người gọi quên truyền thành người gọi
    được miễn kiểm, im lặng. Đó chính là hình dạng của `normalize_tenant_id("")`
    trả `"default"`: hàng rào vẫn còn đó, chỉ là không ai đi qua nó nữa. Ở đây
    quên truyền là `TypeError` ngay lúc gọi, không phải một lượt chạy được cấp
    quyền nhầm sáu tháng sau.
    """
    pham_vi = str(tenant_id or "").strip()
    if not pham_vi:
        raise SplitArtifactError(
            "phân giải hiện vật vận hành mà không biết tenant đang chạy. Không "
            "biết ai hỏi thì không trả lời được câu 'người này có quyền đọc "
            "không' — và mặc định của câu đó là KHÔNG.")

    if not str(split_id or "").strip():
        raise SplitArtifactError(
            "lượt chạy vận hành phải ghim một `split_id`. KHÔNG có mặc định và "
            "KHÔNG rơi về processed/splits/*.csv — ba tệp đó là mốc nghiên cứu "
            "đóng băng, học trên chúng rồi khai là lượt vận hành là khai sai "
            "nguồn gốc.")

    thu_muc = operational_root(splits_root) / str(split_id).strip()
    if not thu_muc.is_dir():
        raise _khong_tim_thay(splits_root, split_id)

    p_meta = thu_muc / METADATA_NAME
    if not p_meta.exists():
        raise SplitArtifactError(f"{split_id}: thiếu {METADATA_NAME}")
    try:
        meta = json.loads(p_meta.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SplitArtifactError(f"{split_id}: {METADATA_NAME} không đọc được: {exc}")

    khai_purpose = str(meta.get("purpose") or "").strip()
    if khai_purpose != PURPOSE_OPERATIONAL:
        raise SplitArtifactError(
            f"{split_id}: hiện vật tự khai purpose={khai_purpose!r}, không phải "
            f"{PURPOSE_OPERATIONAL!r}. Không suy purpose từ tên thư mục.")

    khai_id = str(meta.get("split_id") or "").strip()
    if khai_id != str(split_id).strip():
        raise SplitArtifactError(
            f"tên thư mục là {split_id!r} nhưng bản khai bên trong nói "
            f"split_id={khai_id!r}. Hiện vật đã bị đổi tên hoặc chép nhầm chỗ.")

    _kiem_ba_tep(thu_muc, meta.get("files"), split_id)

    chu = read_owner(meta, split_id=str(split_id).strip())

    # ★ C2c — cưỡng chế. Ba nhánh, và cả ba đều đóng.
    #
    # Thứ tự quan trọng: đọc chủ TRƯỚC, so sánh SAU. `read_owner` đã nổ nếu bản
    # khai bị sửa tay, nên tới được đây thì lời khai đã đáng tin — có gì để so.
    if chu.state != OWNER_OWNED:
        # `unknown`: hiện vật có nội dung hợp lệ nhưng KHÔNG đủ chứng cứ về phạm
        # vi tenant. Không phải dữ liệu hỏng — là provenance không đủ. Và thiếu
        # chứng cứ thì câu trả lời là KHÔNG, chứ không phải "chắc là của người
        # đang hỏi".
        #
        # Nhánh này CHẶN trùng với phép so bên dưới: `chu.tenant_id` là `None`
        # khi không rõ chủ, nên phép so cũng sẽ từ chối. Đo bằng đột biến ngày
        # 16/08: tắt nhánh này chỉ làm ĐỎ đúng một ca — ca về nội dung nhật ký.
        #
        # Nó vẫn phải ở đây, và lý do là CHẨN ĐOÁN chứ không phải chặn. Bỏ đi
        # thì người trực đọc được "hiện vật thuộc tenant None" và sẽ đi tìm một
        # lỗi lưu trữ. Vấn đề thật là nguồn gốc không đủ — cần tra lại lịch sử
        # tạo, không phải dựng lại hiện vật. Hai việc khác nhau.
        _log.error("[SPLIT] tu choi `%s`: %s", split_id, chu.reason)
        raise _khong_tim_thay(splits_root, split_id)

    if chu.tenant_id != pham_vi:
        _log.error(
            "[SPLIT] tu choi `%s`: hien vat thuoc tenant %r, luot chay thuoc "
            "tenant %r. Khong bao gio lay tenant nguoi hoi lam chu.",
            split_id, chu.tenant_id, pham_vi)
        raise _khong_tim_thay(splits_root, split_id)

    return SplitArtifact(
        split_id=str(split_id).strip(), purpose=PURPOSE_OPERATIONAL,
        train_csv=thu_muc / "train.csv", val_csv=thu_muc / "val.csv",
        test_csv=thu_muc / "test.csv", metadata=meta,
        tenant_id=chu.tenant_id, owner_state=chu.state,
    )


def resolve_research(splits_root: Path) -> SplitArtifact:
    """Ba tệp đóng băng, đối chiếu với sổ đăng ký.

    Cố ý KHÔNG đòi `split_metadata.json`: các tệp này có từ trước hợp đồng và
    ép chúng theo lược đồ mới sẽ phá đúng tính lặp lại mà chúng tồn tại để giữ.
    """
    goc = Path(splits_root)
    so = goc / FROZEN_REGISTRY_NAME
    if not so.exists():
        raise SplitArtifactError(
            f"thiếu {FROZEN_REGISTRY_NAME} — không có gì để đối chiếu, nên "
            f"không phát hiện được nếu ba tệp đã bị dựng lại.")
    khai = json.loads(so.read_text(encoding="utf-8"))
    _kiem_ba_tep(goc, khai.get("files"), "frozen research")

    # `not_applicable`, KHÔNG phải `unknown`. Ba tệp này không có chủ tenant vì
    # hợp đồng của chúng không có khái niệm đó — chúng là mốc so sánh đóng băng
    # của luận văn, và thêm một cột tenant vào chúng chỉ để khớp lược đồ mới sẽ
    # phá đúng tính lặp lại mà chúng tồn tại để giữ. Trạng thái riêng này giữ cho
    # bên cưỡng chế không bao giờ nhầm "nghiên cứu" thành "vận hành mất chủ".
    return SplitArtifact(
        split_id="frozen-research-legacy", purpose=PURPOSE_RESEARCH,
        train_csv=goc / "train.csv", val_csv=goc / "val.csv",
        test_csv=goc / "test.csv", metadata=khai,
        tenant_id=None, owner_state=OWNER_NOT_APPLICABLE,
    )


def resolve_split_artifact(
    *, purpose: str, splits_root: Path, tenant_id: str,
    split_id: Optional[str] = None,
) -> SplitArtifact:
    """Cửa duy nhất. Mọi nơi hỏi "lượt này đọc tệp nào" đều phải đi qua đây.

    Trả về cùng một object cho preflight, dựng lệnh, cổng đồng thuận và ghi
    nguồn gốc — nên không còn cảnh preflight soi tệp X trong khi trainer đọc
    tệp Y.

    `tenant_id` bắt buộc ở CẢ HAI nhánh dù nhánh nghiên cứu không dùng nó để
    đối chiếu chủ sở hữu. Đó là chủ ý: người viết một lượt gọi mới buộc phải có
    tenant trong tay tại điểm gọi. Một tham số tuỳ chọn ở đây sẽ khiến nhánh vận
    hành bị bỏ kiểm bất cứ khi nào ai đó chép một lượt gọi nghiên cứu rồi đổi
    `purpose`.
    """
    p = str(purpose or "").strip().lower()
    if p == PURPOSE_OPERATIONAL:
        return resolve_operational(splits_root, split_id or "", tenant_id=tenant_id)
    if p == PURPOSE_RESEARCH:
        # Hợp đồng RIÊNG. Ba tệp đóng băng là mốc so sánh của luận văn, không
        # phải dữ liệu vận hành của tổ chức nào — nên luật chủ sở hữu không áp
        # vào đây, và `not_applicable` nói đúng điều đó thay vì im lặng.
        return resolve_research(splits_root)
    raise SplitArtifactError(
        f"purpose không rõ: {purpose!r}. Chỉ có {PURPOSE_OPERATIONAL!r} và "
        f"{PURPOSE_RESEARCH!r}; đoán thêm là mở lại đúng chỗ mơ hồ vừa đóng.")
