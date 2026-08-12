"""Kho tài liệu pháp lý trên đĩa: định địa chỉ bằng nội dung, ghi nguyên tử.

Tên tệp LÀ mã băm
------------------
``legal/<kind>/<hash[0:2]>/<hash>.md``

Không phải một quy ước đặt tên cho đẹp — nó mua ba tính chất mà một sơ đồ kiểu
``terms-2026-08-08.md`` không có:

* **Bất biến.** Đường dẫn sinh ra TỪ nội dung, nên không có cách nào tráo nội
  dung mà giữ nguyên địa chỉ. Với một tài liệu có chữ ký trỏ vào, đây là tính
  chất quan trọng nhất.
* **Khử trùng lặp.** Lưu một bản nháp giống hệt bản đang công bố không ghi thêm
  byte nào. Người soạn bấm Lưu mười lần thì vẫn là một tệp.
* **Kiểm tra toàn vẹn không cần siêu dữ liệu.** Băm lại tệp và so với tên nó là
  đủ; không phải tra bảng nào.

Thư mục con hai ký tự đầu (`ab/abcdef…`) là thói quen của Git và của mọi kho
định-địa-chỉ-bằng-nội-dung: một thư mục phẳng vài nghìn mục làm chậm `readdir`
trên nhiều hệ tệp, và ext4 không có thư mục con thì tra cứu tuyến tính.

Ghi blob TRƯỚC, ghi hàng SAU
-----------------------------
Thứ tự này là một phần của tính đúng, không phải sở thích. Một blob mồ côi —
tệp đã ghi mà hàng cơ sở dữ liệu không ghi được — thì vô hại và ``collect_
garbage`` dọn được. Chiều ngược lại, một hàng trỏ tới tệp không tồn tại, thì
không có cách nào cứu: nội dung đã mất và bản ghi nói rằng nó từng có.

Vì ghi là idempotent (tên = băm), lặp lại lượt ghi sau một lần hỏng giữa chừng
là an toàn.

Vì sao nằm dưới ``/dataset``
-----------------------------
``./dataset:/dataset`` đã được mount vào cả năm service chạy ảnh backend, nên
kho này không cần một dòng nào trong ``docker-compose.yml`` và không thêm bước
triển khai nào. Đã kiểm: không có tiến trình nào duyệt toàn bộ cây ``dataset/``,
nên một thư mục con mới không lọt vào đường đồng bộ nào.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: Chỉ chấp nhận băm sha256 viết thường. Dùng để chặn đường dẫn dựng từ dữ liệu
#: không tin được — xem `_resolve`.
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

#: Blob phải "nguội" bao lâu mới được coi là rác. Cửa sổ này che đúng một khoảng
#: hẹp: một lượt công bố đã ghi tệp và chưa kịp ghi hàng. Không có nó, một lần
#: dọn rác chạy trúng giây đó sẽ xoá mất nội dung của bản vừa công bố.
GC_MIN_AGE_SECONDS = 24 * 3600


def store_root() -> Path:
    """Gốc kho. Đọc lại mỗi lần gọi chứ không chốt ở thời điểm import.

    Test đổi `DATASET_ROOT` bằng monkeypatch sau khi module đã nạp; một hằng số
    cấp module sẽ giữ giá trị cũ và bộ test sẽ ghi vào kho thật.
    """
    from app.config import settings

    override = os.getenv("LEGAL_STORE_ROOT")
    if override:
        return Path(override)
    return Path(settings.dataset_root) / "legal"


def content_digest(body: str) -> str:
    return hashlib.sha256((body or "").encode("utf-8")).hexdigest()


#: Đuôi tệp được nhận. Danh sách TRẮNG, không phải danh sách đen: một kho nhận
#: mọi thứ trừ vài đuôi cấm sẽ nhận `.svg` (chạy script khi mở trực tiếp),
#: `.htm`, `.xht`… Ở đây chỉ có định dạng văn bản người ta thật sự ký.
ALLOWED_EXTENSIONS: dict = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}

#: Trần kích thước một bản văn. 25 MB là rộng rãi cho một văn bản có chữ ký
#: quét; cao hơn thì gần như chắc chắn là nhầm tệp.
MAX_FILE_BYTES = 25 * 1024 * 1024


def normalize_extension(file_name: str) -> str:
    """Đuôi viết thường của một tên tệp, hoặc raise nếu không nằm trong danh sách.

    Lấy từ TÊN TỆP chứ không từ `Content-Type` do trình duyệt khai: header đó do
    bên gửi đặt và không kiểm chứng được. Đuôi cũng do bên gửi đặt, nhưng nó là
    thứ quyết định `Content-Type` ta trả về lúc TẢI XUỐNG — nên chốt nó vào một
    danh sách trắng là đủ để không bao giờ phục vụ một kiểu nội dung ngoài dự
    kiến.
    """
    name = (file_name or "").strip().lower()
    dot = name.rfind(".")
    ext = name[dot:] if dot > 0 else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "định dạng không được chấp nhận: "
            + ", ".join(sorted(ALLOWED_EXTENSIONS))
        )
    return ext


def storage_key(kind: str, digest: str, extension: str = ".md") -> str:
    """Địa chỉ tương đối của một blob, tính từ gốc kho.

    Lưu TƯƠNG ĐỐI trong cơ sở dữ liệu, không tuyệt đối: gốc kho khác nhau giữa
    máy phát triển, container và một lần khôi phục sao lưu, và một đường tuyệt
    đối trong bảng sẽ biến mỗi lần dời chỗ thành một lần chạy UPDATE hàng loạt.

    `extension` mặc định `.md` để mọi khoá đã nằm trong cơ sở dữ liệu vẫn sinh
    ra y hệt — đổi mặc định là làm mồ côi toàn bộ kho hiện có.
    """
    if not _HEX64.match(digest or ""):
        raise ValueError(f"digest không phải sha256 hợp lệ: {digest!r}")
    safe_kind = re.sub(r"[^a-z0-9_]+", "", (kind or "").lower())
    if not safe_kind:
        raise ValueError(f"kind không hợp lệ: {kind!r}")
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"đuôi tệp không được chấp nhận: {extension!r}")
    return f"{safe_kind}/{digest[:2]}/{digest}{extension}"


def _resolve(key: str) -> Path:
    """Khoá tương đối → đường tuyệt đối, từ chối mọi thứ thoát khỏi gốc kho.

    `storage_key` sinh ra khoá sạch, nhưng hàm này cũng nhận khoá ĐỌC TỪ cơ sở
    dữ liệu. Nếu một hàng bị sửa thành `../../etc/passwd` thì phép kiểm ở đây là
    thứ duy nhất còn đứng giữa. Rẻ, và chỗ cần nó là chỗ không ai nghĩ tới.
    """
    root = store_root().resolve()
    target = (root / key).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"khoá kho thoát khỏi gốc: {key!r}")
    return target


def exists(key: str) -> bool:
    try:
        return _resolve(key).is_file()
    except ValueError:
        return False


def write_bytes(kind: str, payload: bytes, extension: str) -> Tuple[str, str, int]:
    """Ghi một blob nhị phân vào kho. Trả về `(khoá, băm, số byte)`.

    Đây là đường đi thật của cả hai loại nội dung; `write()` chỉ là lớp bọc mã
    hoá UTF-8 lên trên. Tách ra vì một tệp PDF không có "chuỗi" nào để đi qua,
    và ép nó thành `str` là cách chắc chắn nhất làm hỏng một byte ở đâu đó.

    Idempotent: nội dung đã có thì không ghi lại. Vẫn trả về khoá như thường,
    nên bên gọi không cần phân biệt hai trường hợp.

    Ghi nguyên tử qua tệp tạm rồi `os.replace`. Không có bước này, một tiến
    trình bị giết giữa chừng để lại tệp CỤT mang đúng tên băm của nội dung đầy
    đủ — tức là một blob nói dối về chính nó, và mọi phép kiểm toàn vẹn sau đó
    đều tin nó cho tới khi có người đọc.
    """
    if not payload:
        raise ValueError("không ghi tệp rỗng vào kho")
    if len(payload) > MAX_FILE_BYTES:
        raise ValueError(
            f"tệp lớn hơn mức cho phép ({MAX_FILE_BYTES // (1024 * 1024)} MB)"
        )

    digest = hashlib.sha256(payload).hexdigest()
    key = storage_key(kind, digest, extension)
    target = _resolve(key)

    if target.is_file():
        return key, digest, target.stat().st_size

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".tmp-{uuid.uuid4().hex}"
    try:
        with open(tmp, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    finally:
        # `os.replace` thành công thì `tmp` không còn; câu này dọn nhánh hỏng.
        if tmp.exists():
            tmp.unlink(missing_ok=True)

    logger.info("[LEGAL_STORE] ghi %s (%d byte)", key, len(payload))
    return key, digest, len(payload)


def write(kind: str, body: str) -> Tuple[str, str, int]:
    """Ghi một bản văn (markdown) vào kho. Trả về `(khoá, băm, số byte)`.

    Băm tính trên **byte UTF-8**, đúng như `content_digest`, nên khoá sinh ra
    giống hệt bản trước khi tách hàm — mọi hàng đang trỏ vào kho vẫn đúng.
    """
    if not (body or "").strip():
        raise ValueError("không ghi văn bản rỗng vào kho")
    return write_bytes(kind, body.encode("utf-8"), ".md")


def read(key: str) -> str:
    return _resolve(key).read_text(encoding="utf-8")


def read_bytes(key: str) -> bytes:
    return _resolve(key).read_bytes()


def content_type_for(key: str) -> str:
    """Kiểu nội dung trả về khi phục vụ một blob.

    Suy từ ĐUÔI CỦA KHOÁ, không từ bất cứ thứ gì người tải lên khai. Khoá do
    `storage_key` sinh ra và đuôi của nó đã qua danh sách trắng, nên đường này
    không bao giờ phục vụ được một kiểu ngoài dự kiến — kể cả khi một hàng
    trong cơ sở dữ liệu bị sửa.
    """
    dot = key.rfind(".")
    return ALLOWED_EXTENSIONS.get(key[dot:].lower() if dot > 0 else "", "application/octet-stream")


def verify(key: str, expected_digest: Optional[str] = None) -> bool:
    """Tệp có còn đúng là nội dung mà tên nó tuyên bố không?

    `expected_digest` mặc định lấy từ chính tên tệp; truyền vào tường minh khi
    muốn đối chiếu với băm lưu trong cơ sở dữ liệu — đó là phép kiểm mạnh hơn,
    vì nó bắt được cả trường hợp hàng dữ liệu bị sửa để trỏ sang blob khác.
    """
    try:
        path = _resolve(key)
    except ValueError:
        return False
    if not path.is_file():
        return False
    want = expected_digest or path.stem
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    return actual == want


def iter_keys() -> Iterable[str]:
    """Mọi blob đang nằm trong kho, dưới dạng khoá tương đối.

    Duyệt theo TOÀN BỘ danh sách đuôi được phép, không chỉ `*.md`. Bản đầu chỉ
    tìm markdown; khi kho bắt đầu nhận PDF thì những tệp đó biến mất khỏi tầm
    nhìn của `collect_garbage` — hỏng về phía an toàn (không bao giờ bị xoá
    nhầm) nhưng vẫn là hỏng: một tệp không ai trỏ tới sẽ nằm lại vĩnh viễn, và
    một lượt kiểm toàn vẹn quét kho sẽ báo "sạch" mà chưa nhìn nó lần nào.
    """
    root = store_root()
    if not root.is_dir():
        return
    for ext in ALLOWED_EXTENSIONS:
        for path in root.rglob(f"*{ext}"):
            if path.name.startswith(".tmp-"):
                continue
            yield str(path.relative_to(root)).replace("\\", "/")


def collect_garbage(referenced: Iterable[str], *, dry_run: bool = True,
                    min_age_seconds: int = GC_MIN_AGE_SECONDS) -> List[str]:
    """Xoá blob không còn hàng nào trỏ tới VÀ đã đủ nguội.

    Hai điều kiện, và điều kiện tuổi là điều kiện dễ bỏ quên nhất: giữa lúc ghi
    blob và lúc ghi hàng có một khoảng vài mili giây trong đó blob hợp lệ nhưng
    chưa ai trỏ tới. Dọn rác chạy trúng khoảng đó mà không xét tuổi sẽ xoá nội
    dung của bản vừa công bố, và hàng dữ liệu sinh ra ngay sau đó trỏ vào một
    tệp không tồn tại.

    `dry_run=True` là mặc định: đây là lệnh xoá tệp, và một lệnh xoá tệp không
    nên chạy vì người ta gõ thiếu một cờ.
    """
    keep = set(referenced)
    now = time.time()
    removed: List[str] = []
    for key in iter_keys():
        if key in keep:
            continue
        path = _resolve(key)
        try:
            if now - path.stat().st_mtime < min_age_seconds:
                continue
        except OSError:
            continue
        removed.append(key)
        if not dry_run:
            path.unlink(missing_ok=True)
            logger.info("[LEGAL_STORE] don rac %s", key)
    return removed
