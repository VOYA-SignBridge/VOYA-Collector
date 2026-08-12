"""Trợ lý tự động trả lời trước khi có người trực.

Vì sao có nó
-------------
Phần lớn phiếu hỗ trợ hỏi lại đúng vài câu: quên mật khẩu, mẫu tải lên không
thấy đâu, huấn luyện báo lỗi, muốn đổi tên đăng nhập. Người dùng chờ hàng giờ
cho một câu trả lời đã nằm sẵn trong tài liệu, còn người trực gõ lại nó lần thứ
mười. Trợ lý này cắt vòng lặp đó.

Bốn điều nó CỐ Ý không làm
---------------------------
1. **Không hoãn việc báo cho người trực.** Người trực vẫn nhận thông báo ngay
   khi phiếu mở, y như trước. Trợ lý chạy song song chứ không đứng chắn cửa —
   "để bot xử lý trước rồi mới gọi người" là cách biến một sự cố gấp thành một
   sự cố gấp bị bỏ quên.
2. **Không đổi trạng thái phiếu.** Nếu câu trả lời của trợ lý đẩy phiếu sang
   `pending` ("chờ người dùng"), phiếu rơi khỏi hàng đợi mặc định của người
   trực và không ai thấy nó nữa cho tới khi người dùng nhắn tiếp. Đó đúng là
   lớp lỗi "người dùng nhắn mà quản trị viên không nhận được" đã phải đi vá.
3. **Không đóng, không đánh dấu đã giải quyết.** Chỉ người thật làm được.
4. **Không đoán khi không chắc.** Không khớp luật nào thì nói thẳng là chưa
   hiểu và mời người trực, chứ không trả lời chung chung cho có.

Vì sao là luật từ khoá chứ không phải mô hình ngôn ngữ
------------------------------------------------------
Một câu sai trong kênh hỗ trợ của hệ thống thu dữ liệu có chữ ký đồng thuận
không phải là một câu vô hại. Luật từ khoá **đọc được, kiểm được, và tái lập
được**: cùng một câu hỏi luôn ra cùng một câu trả lời, và mọi câu trả lời đều
do người viết ra chứ không do máy sinh. Đánh đổi là nó chỉ phủ những gì đã
lường trước — nên nó phải biết im lặng, xem điểm 4.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

#: Nhãn hiện trên mọi lời của trợ lý. Có chữ "tự động" ngay trong tên là chủ ý:
#: người đọc phải biết mình đang nói với máy mà không cần đọc chú thích.
BOT_LABEL = "Trợ lý tự động"


@dataclass(frozen=True)
class Rule:
    """Một chủ đề trợ lý biết trả lời."""

    topic: str
    #: Từ khoá đã BỎ DẤU, chữ thường. Xem `_normalize`.
    keywords: tuple
    answer: str
    #: Chip gợi ý hiện dưới ô nhập sau khi trả lời. Đây là chữ giao diện nên
    #: chúng đi qua `t()` ở phía trình duyệt.
    suggestions: tuple = field(default=())


#: Câu mở đầu, gửi ngay khi phiếu được tạo — trước cả lượt khớp luật.
GREETING = (
    "Xin chào! Tôi là trợ lý tự động của CTU.SignBridge. "
    "Tôi trả lời được ngay một số câu hỏi thường gặp. "
    "Người trực cũng đã nhận được thông báo và sẽ vào khi sẵn sàng."
)

#: Câu khi không khớp luật nào. Nói thẳng là không biết — xem điểm 4 ở đầu tệp.
FALLBACK = (
    "Tôi chưa hiểu chắc ý bạn nên sẽ không đoán. "
    "Người trực đã nhận được phiếu này và sẽ trả lời trực tiếp. "
    "Trong lúc chờ, bạn mô tả thêm giúp tôi: bạn đang ở màn hình nào, "
    "và hệ thống hiện ra chữ gì?"
)

#: Câu khi người dùng chủ động xin gặp người thật.
HANDOFF = (
    "Rồi, tôi dừng ở đây. Phiếu của bạn đã nằm trong hàng đợi của người trực "
    "kèm toàn bộ nội dung trao đổi phía trên, nên bạn không phải kể lại từ đầu."
)

#: Chip gợi ý lúc mở hội thoại mới. Ngắn, và mỗi cái ứng với một luật ở dưới.
STARTERS = (
    "Tôi quên mật khẩu",
    "Mẫu tôi tải lên không thấy đâu",
    "Huấn luyện báo lỗi",
    "Tôi muốn đổi tên đăng nhập",
    "Tôi cần gặp người hỗ trợ",
)

#: Chip luôn có mặt: lối thoát khỏi trợ lý, ở mọi bước.
ESCAPE_CHIP = "Tôi cần gặp người hỗ trợ"


RULES: tuple = (
    Rule(
        topic="handoff",
        keywords=("nguoi that", "nguoi ho tro", "gap nguoi", "nhan vien",
                  "ky thuat vien", "khong phai bot", "gap admin",
                  "chuyen giup", "chuyen tiep"),
        answer=HANDOFF,
        suggestions=(),
    ),
    Rule(
        topic="password",
        keywords=("quen mat khau", "mat khau", "dat lai mat khau", "khong dang nhap duoc",
                  "dang nhap khong duoc", "reset password"),
        answer=(
            "Bạn tự đặt lại được mà không cần chờ ai: vào trang đăng nhập, bấm "
            "\"Quên mật khẩu?\", nhập tên đăng nhập hoặc email, rồi nhập mã sáu "
            "chữ số được gửi tới. Mã sống 5 phút.\n\n"
            "Nếu không nhận được mã, hãy kiểm tra hộp thư rác trước — và cho tôi "
            "biết bạn dùng email hay số điện thoại."
        ),
        suggestions=("Tôi không nhận được mã", ESCAPE_CHIP),
    ),
    Rule(
        topic="otp",
        keywords=("khong nhan duoc ma", "khong co ma", "ma het han", "ma khong dung",
                  "otp"),
        answer=(
            "Mã sống 5 phút và mỗi mã chỉ dùng được một lần. Ba việc đáng thử "
            "theo thứ tự: xem hộp thư rác; bấm \"Gửi lại mã\" sau khi bộ đếm "
            "chạy hết; kiểm tra xem địa chỉ đã xác minh có đúng là địa chỉ bạn "
            "đang mở không.\n\n"
            "Vẫn không được thì để người trực kiểm tra nhật ký gửi thư giúp bạn."
        ),
        suggestions=(ESCAPE_CHIP,),
    ),
    Rule(
        topic="upload",
        keywords=("tai len", "upload", "khong thay mau", "mau bi mat", "mat mau",
                  "video khong len", "khong hien mau"),
        answer=(
            "Mẫu vừa thu đi qua hàng đợi xử lý trước khi hiện trong thư viện, nên "
            "trễ vài phút là bình thường.\n\n"
            "Nếu quá lâu, hãy cho tôi biết: bạn thu bằng webcam hay tải video lên, "
            "nhãn là gì, và lúc đó màn hình có báo lỗi gì không. Có ba chi tiết đó "
            "thì người trực dò được đúng phiên thu của bạn."
        ),
        suggestions=("Tôi thu bằng webcam", "Tôi tải video lên", ESCAPE_CHIP),
    ),
    # Ba luật dưới đây là bước THỨ HAI của một cuộc hỏi đáp, không phải câu mở
    # đầu. Chúng tồn tại vì mỗi chip gợi ý phải khớp một luật — một chip không
    # khớp gì là cái bẫy: người dùng bấm vào rồi nhận đúng câu "tôi chưa hiểu".
    # Bài test `test_moi_chip_goi_y_deu_khop_mot_luat` canh chỗ này.
    Rule(
        topic="capture_source",
        keywords=("thu bang webcam", "quay bang webcam", "tai video len",
                  "upload video"),
        answer=(
            "Cảm ơn, thế thì khoanh vùng được rồi.\n\n"
            "Với mẫu thu bằng webcam: mở lại Thư viện nhãn, tìm đúng nhãn, và xem "
            "phần \"lần quay\" — nếu lần quay có ở đó mà mẫu chưa hiện thì nó vẫn "
            "đang trong hàng đợi xử lý.\n\n"
            "Với video tải lên: kiểm tra tệp có dưới 100 MB và đúng định dạng video "
            "không. Quá cỡ thì hệ thống từ chối ngay lúc tải.\n\n"
            "Cho tôi biết nhãn và khoảng giờ bạn thu, người trực sẽ dò đúng phiên đó."
        ),
        suggestions=(ESCAPE_CHIP,),
    ),
    Rule(
        topic="training_data",
        keywords=("thieu du lieu", "bao thieu du lieu", "khong du du lieu",
                  "khong du mau"),
        answer=(
            "Đây là loại lỗi bạn tự xử lý được.\n\n"
            "Mỗi nhãn cần ít nhất 5 lần quay mới đủ điều kiện huấn luyện. Mở Thư "
            "viện nhãn, những nhãn còn thiếu có ghi rõ \"Cần thêm N lần quay\".\n\n"
            "Nếu bạn đang chạy ở chế độ nghiên cứu thì còn một điều kiện nữa: phải "
            "có một split đã được đánh phiên bản. Chưa có split thì chỉ chạy được "
            "chế độ thăm dò."
        ),
        suggestions=(ESCAPE_CHIP,),
    ),
    Rule(
        topic="training_system",
        keywords=("loi he thong", "bao loi he thong", "su co he thong",
                  "hang doi khong phan hoi"),
        answer=(
            "Sự cố hệ thống thì bạn không phải làm gì cả — quản trị viên đã được "
            "thông báo tự động và sự việc đã vào nhật ký giám sát.\n\n"
            "Dữ liệu của bạn không bị ảnh hưởng: lần chạy hỏng không xoá mẫu nào. "
            "Chờ ít phút rồi chạy lại; nếu vẫn hỏng thì để người trực xem nhật ký."
        ),
        suggestions=(ESCAPE_CHIP,),
    ),
    Rule(
        topic="delete_account",
        keywords=("xoa tai khoan", "huy tai khoan", "dong tai khoan"),
        answer=(
            "Yêu cầu xoá tài khoản phải qua người trực — tôi không tự làm được, và "
            "đó là chủ ý: đây là thao tác không hoàn tác được.\n\n"
            "Một điều nên biết trước: xoá tài khoản khác với rút đồng ý. Rút đồng ý "
            "loại mẫu của bạn khỏi mọi lượt chọn dữ liệu về sau nhưng giữ tệp; xoá "
            "tài khoản là yêu cầu gỡ hẳn. Nếu bạn chỉ muốn dừng đóng góp thì rút "
            "đồng ý là đủ và làm được ngay trong Cài đặt."
        ),
        suggestions=("Tôi chỉ muốn rút đồng ý", ESCAPE_CHIP),
    ),
    Rule(
        topic="training",
        keywords=("huan luyen", "training", "train loi", "khong train duoc",
                  "job that bai", "model loi"),
        answer=(
            "Màn hình huấn luyện có phân loại sẵn nguyên nhân — thiếu dữ liệu, hết "
            "bộ nhớ GPU, hàng đợi không phản hồi, hay quá thời gian chờ — kèm cách "
            "khắc phục cho từng loại. Hãy mở lại lần chạy đó và đọc phần \"Nguyên "
            "nhân có thể\".\n\n"
            "Nếu nó báo sự cố hệ thống thì bạn không phải làm gì: quản trị viên "
            "được thông báo tự động."
        ),
        suggestions=("Nó báo thiếu dữ liệu", "Nó báo lỗi hệ thống", ESCAPE_CHIP),
    ),
    Rule(
        topic="rename",
        keywords=("doi ten", "ten dang nhap", "doi username", "sua ten"),
        answer=(
            "Vào Cài đặt → Tài khoản để đổi tên đăng nhập.\n\n"
            "Một điều nên biết trước khi đổi: tên này đã được chép vào từng mẫu "
            "bạn đóng góp ngay lúc ghi. Đổi ở đây sẽ cập nhật cả những bản sao đó. "
            "Riêng nhật ký kiểm toán giữ nguyên tên cũ — đó là bằng chứng lịch sử "
            "về việc ai đã làm gì."
        ),
        suggestions=(ESCAPE_CHIP,),
    ),
    Rule(
        topic="consent",
        keywords=("dong y", "chap thuan", "rut dong y", "dieu khoan", "quyen rieng tu"),
        answer=(
            "Vào Cài đặt → Tài khoản, mục \"Chấp thuận của tôi\". Ở đó bạn xem lại "
            "được mình đã đồng ý với BẢN NÀO của từng văn bản, mở lại đúng bản đó "
            "để đọc, và rút đồng ý nếu muốn.\n\n"
            "Rút đồng ý loại mẫu của bạn khỏi mọi lượt chọn dữ liệu về sau, kể cả "
            "huấn luyện nội bộ. Tệp đã đóng góp thì không bị xoá — muốn xoá hãy "
            "dùng Thùng rác hoặc yêu cầu xoá tài khoản."
        ),
        suggestions=("Tôi muốn xoá tài khoản", ESCAPE_CHIP),
    ),
    Rule(
        topic="quota",
        keywords=("het han muc", "han muc", "quota", "goi dich vu", "dung thu",
                  "het phut", "nang goi"),
        answer=(
            "Vào Cài đặt → Gói dịch vụ để xem hạn mức hiện tại và mức đã dùng trong "
            "30 ngày qua.\n\n"
            "Tài khoản dùng thử có giới hạn số phút nhận diện mỗi ngày, và chỉ tính "
            "thời gian máy thật sự xử lý. Muốn nâng hạn mức thì cần quản trị viên "
            "tổ chức — tôi chuyển tiếp giúp bạn nhé?"
        ),
        suggestions=("Vâng, chuyển giúp tôi", ESCAPE_CHIP),
    ),
    Rule(
        topic="export",
        keywords=("xuat du lieu", "tai du lieu ve", "export", "mang du lieu di",
                  "lay du lieu"),
        answer=(
            "Vào Tổ chức → \"Mang dữ liệu đi\". Bạn đặt một bản xuất, hệ thống dựng "
            "nền, và khi xong sẽ có liên kết tải về.\n\n"
            "Có hai phạm vi: chỉ siêu dữ liệu, hoặc toàn bộ. Bản xuất vẫn đặt được "
            "cả khi tổ chức đang ở chế độ chỉ đọc."
        ),
        suggestions=(ESCAPE_CHIP,),
    ),
)


def _normalize(text: str) -> str:
    """Bỏ dấu, hạ chữ thường, gom khoảng trắng.

    Người ta gõ "quên mật khẩu", "quen mat khau" và "Quên Mật Khẩu" như nhau.
    Khớp trên chuỗi thô sẽ trượt hai trong ba, và cái trượt đó im lặng —
    trợ lý chỉ đơn giản là không trả lời được, không ai biết vì sao.
    """
    lowered = (text or "").lower()
    # đ/Đ không phân rã được bằng NFD nên phải thay tay.
    lowered = lowered.replace("đ", "d")
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", stripped).strip()


def match(text: str) -> Optional[Rule]:
    """Luật đầu tiên có từ khoá nằm trong câu hỏi, hoặc `None`.

    Thứ tự trong `RULES` là thứ tự ưu tiên, và `handoff` đứng đầu là cố ý: khi
    người ta đã nói "cho tôi gặp người thật" thì mọi luật khác đều sai, kể cả
    khi câu đó có nhắc tới mật khẩu.
    """
    haystack = _normalize(text)
    if not haystack:
        return None
    for rule in RULES:
        for kw in rule.keywords:
            if kw in haystack:
                return rule
    return None


def answer_for(text: str) -> tuple:
    """`(câu trả lời, chip gợi ý, chủ đề)` cho một lời của người dùng.

    Luôn trả về một câu — im lặng trong kênh hỗ trợ là hướng hỏng tệ nhất: người
    dùng không phân biệt được "hệ thống chưa đọc" với "hệ thống bỏ qua tôi".
    """
    rule = match(text)
    if rule is None:
        return FALLBACK, (ESCAPE_CHIP,), "unknown"
    return rule.answer, rule.suggestions, rule.topic


def wants_human(text: str) -> bool:
    """Người dùng đã xin gặp người thật chưa."""
    rule = match(text)
    return rule is not None and rule.topic == "handoff"


def starters() -> List[str]:
    return list(STARTERS)
