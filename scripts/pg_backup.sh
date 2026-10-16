#!/bin/sh
# Sao lưu Postgres + kho văn bản pháp lý theo lịch, giữ đời, và TỰ KIỂM mỗi bản.
#
# Vì sao có bước tự kiểm
# ----------------------
# Một bản sao lưu chưa từng được đọc lại thì chưa phải bản sao lưu — nó là một
# tệp mà ta hy vọng đọc được. Kiểu hỏng kinh điển là `pg_dump` bị cắt giữa
# chừng (hết đĩa, container bị giết): tệp vẫn có, kích thước trông hợp lý, và
# chỉ tới ngày cần khôi phục mới phát hiện nó cụt.
#
# Phép kiểm phải ĐỌC HẾT tệp, và đây là chỗ dễ làm sai. `pg_restore --list`
# trông có vẻ đủ, nhưng nó **không** bắt được tệp cụt: ở định dạng custom, mục
# lục nằm ở ĐẦU tệp, nên `--list` trả về 0 trên một bản dump bị cắt mất nửa sau.
# Đã đo (2026-08-08): bản 585 KB cắt còn 200 KB → `--list` cho 0, tức "đạt".
#
# `pg_restore -f /dev/null` giải nén toàn bộ khối dữ liệu và dựng câu SQL, nên
# nó chạm tới byte cuối cùng. Cùng bản cắt đó → trả 1. Nó tốn thêm vài giây và
# mua đúng thứ mà bước tự kiểm tồn tại để mua.
#
# Bản không qua kiểm bị đổi tên thành `.CORRUPT` chứ không bị xoá: một bản hỏng
# vẫn có thể cứu được phần nào, và nó là bằng chứng để truy nguyên.
#
# Phép kiểm mạnh hơn — khôi phục thật vào một cơ sở dữ liệu nháp rồi đếm dòng —
# nằm ở `scripts/pg_restore.sh --drill`. Nó không chạy ở đây vì nó cần vài phút
# và cần quyền tạo database; xem `docs/06-operations/BACKUP_RESTORE.md` về nhịp diễn tập.
#
# Vì sao định dạng custom (-Fc)
# ------------------------------
# Nén sẵn, khôi phục được từng bảng, và `pg_restore --list` đọc được mục lục —
# thứ mà một tệp .sql phẳng không có, khiến bước tự kiểm ở trên không thực hiện
# được. Đây là lý do kỹ thuật, không phải sở thích.
#
# Vì sao sao lưu HAI kho, và vì sao theo đúng thứ tự này
# -------------------------------------------------------
# Từ v6 thân văn bản pháp lý không nằm trong Postgres nữa mà ở kho định-địa-chỉ-
# bằng-nội-dung dưới `dataset/legal/`. Hàng dữ liệu chỉ giữ `storage_key`. Sao
# lưu một trong hai kho là sao lưu một nửa: khôi phục xong sẽ có bản ghi nói
# rằng người dùng đã ký một văn bản mà không ai đọc lại được nội dung văn bản đó.
#
# Hai kho không thể chụp cùng một khoảnh khắc, nên phải chọn hướng lệch. Bất
# biến cần giữ là **mọi khoá trong bản dump đều có tệp trong bản lưu trữ**;
# chiều ngược lại (lưu trữ có tệp thừa) chỉ là blob mồ côi, vô hại.
#
#   1. dump cơ sở dữ liệu   (ảnh chụp tại T1)
#   2. đọc danh sách khoá đang dùng  (T2 > T1 → tập này BAO danh sách trong dump)
#   3. nén thư mục kho      (T3 > T2 → chứa mọi tệp đã tồn tại ở T2)
#
# Bước 3 an toàn nhờ hai tính chất của kho: tệp được ghi TRƯỚC hàng dữ liệu, và
# tên tệp là băm nội dung nên không bao giờ bị ghi đè. Một văn bản công bố sau
# T2 nằm ngoài phép đối chiếu, đúng như mong muốn — nó cũng nằm ngoài bản dump.
#
# Vì sao khẳng định quyền vượt RLS ngay lúc khởi động
# -----------------------------------------------------
# Hai mươi mấy bảng bật `FORCE ROW LEVEL SECURITY`. Một vai không có
# `rolbypassrls` chạy `pg_dump` sẽ **không** lặng lẽ dump ra bảng rỗng —
# pg_dump đặt `row_security = off` và Postgres báo lỗi. Nhưng đó là hành vi
# đúng của hôm nay, phụ thuộc vào cờ mặc định của pg_dump. Một lượt "siết
# quyền" tương lai đổi service này sang vai ứng dụng sẽ biến mọi lượt sao lưu
# thành lỗi mà không ai đọc log. Khẳng định ở đây làm hỏng-thì-thấy-ngay:
# container không lên được, `docker compose ps` báo restarting.
#
# Vì sao không dùng cron
# -----------------------
# Ảnh postgres không có crond, và thêm một tiến trình giám sát nữa vào container
# chỉ để hẹn giờ là thêm một thứ có thể chết âm thầm. Vòng lặp `sleep` ở dưới
# nhìn thấy được trong `docker logs`, và nếu nó chết thì container chết theo —
# `restart: unless-stopped` dựng lại, và healthcheck báo.

set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
LEGAL_DIR="${LEGAL_STORE_DIR:-/dataset/legal}"

# Mã hoá — TẮT khi để trống, và im lặng thì không phải lựa chọn hợp lệ.
#
# Bản dump chứa địa chỉ email, số điện thoại, băm mật khẩu và toàn bộ chữ ký
# chấp thuận điều khoản của người dùng thật, ở dạng đọc thẳng ra được. Chừng
# nào nó còn nằm trên ổ của chính máy chủ thì rủi ro là "ai vào được máy thì
# đọc được"; ngày nó được chép sang ổ ngoài hay lên đám mây — tức là ngày làm
# BACKUP_MIRROR_DIR bên dưới — thì rủi ro đó đi theo nó ra khỏi nhà.
#
# Không tự bật được: khoá phải do người vận hành giữ, và một khoá do script tự
# sinh rồi cất cạnh bản sao lưu thì không mã hoá gì cả. Nên mặc định là tắt,
# nhưng `preflight` in cảnh báo mỗi lần khởi động — chọn không mã hoá phải là
# một quyết định, không phải một điều bị quên.
PASSPHRASE="${BACKUP_PASSPHRASE:-}"
#: Ngưỡng tối thiểu. Một bản sao lưu mã hoá bằng mật khẩu yếu còn tệ hơn không
#: mã hoá: nó tạo ra niềm tin sai, và người ta chép nó đi những nơi mà bản
#: không mã hoá sẽ không bao giờ được chép tới.
MIN_PASSPHRASE_LEN=16

# Bản sao thứ hai, ở NƠI KHÁC. Để trống thì bỏ qua, kèm cảnh báo.
#
# `./backups` nằm cùng ổ với `./dataset`. Một sự cố ổ đĩa mất cả dữ liệu lẫn
# bản sao lưu của nó, và đó là đúng tình huống mà bản sao lưu tồn tại để cứu.
# Script không chọn hộ nơi lưu — ổ ngoài, máy khác, hay dịch vụ đám mây là
# quyết định có ràng buộc về dữ liệu cá nhân. Nó chỉ chép vào chỗ được chỉ.
MIRROR_DIR="${BACKUP_MIRROR_DIR:-}"
PGHOST="${PGHOST:-postgres}"
PGUSER="${POSTGRES_USER:?POSTGRES_USER là bắt buộc}"
PGDATABASE="${POSTGRES_DB:?POSTGRES_DB là bắt buộc}"
export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD là bắt buộc}"

mkdir -p "$BACKUP_DIR"

log() {
    echo "[pg-backup $(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"
}

psql_value() {
    psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -Atqc "$1"
}

preflight() {
    # Kết nối được, và kết nối bằng một vai đọc được mọi dòng. Xem đầu tệp.
    if ! caps="$(psql_value "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")"; then
        log "LỖI: không kết nối được tới $PGHOST/$PGDATABASE bằng vai $PGUSER"
        return 1
    fi
    if [ "$caps" != "t" ]; then
        log "LỖI: vai '$PGUSER' không vượt được RLS (rolsuper=f, rolbypassrls=f)."
        log "      Hơn hai mươi bảng bật FORCE ROW LEVEL SECURITY; pg_dump bằng vai"
        log "      này sẽ thất bại hoặc bỏ sót dữ liệu. Xem docs/06-operations/BACKUP_RESTORE.md."
        return 1
    fi
    log "tiền kiểm: vai '$PGUSER' đọc được mọi dòng"

    if [ -n "$PASSPHRASE" ]; then
        if [ "${#PASSPHRASE}" -lt "$MIN_PASSPHRASE_LEN" ]; then
            log "LỖI: BACKUP_PASSPHRASE ngắn hơn $MIN_PASSPHRASE_LEN ký tự."
            log "      Từ chối chạy chứ không hạ tiêu chuẩn: một bản sao lưu mã hoá"
            log "      bằng mật khẩu yếu tạo ra niềm tin sai, và niềm tin đó là thứ"
            log "      khiến người ta chép nó tới những nơi bản không mã hoá sẽ"
            log "      không bao giờ được chép tới."
            return 1
        fi
        if ! command -v gpg > /dev/null 2>&1; then
            log "LỖI: đã đặt BACKUP_PASSPHRASE nhưng ảnh này không có gpg."
            return 1
        fi
        log "tiền kiểm: mã hoá BẬT (AES-256, gpg đối xứng)"
    else
        log "CẢNH BÁO: mã hoá TẮT — bản dump chứa email, số điện thoại, băm mật"
        log "          khẩu và chữ ký chấp thuận ở dạng đọc thẳng được."
        log "          Đặt BACKUP_PASSPHRASE (>= $MIN_PASSPHRASE_LEN ký tự) để bật."
    fi

    if [ -n "$MIRROR_DIR" ]; then
        if ! mkdir -p "$MIRROR_DIR" 2>/dev/null; then
            log "LỖI: không tạo/ghi được BACKUP_MIRROR_DIR=$MIRROR_DIR"
            return 1
        fi
        log "tiền kiểm: bản sao thứ hai -> $MIRROR_DIR"
    else
        log "CẢNH BÁO: chưa có bản sao ngoài. Thư mục sao lưu nằm CÙNG Ổ với"
        log "          dữ liệu, nên một sự cố ổ đĩa mất cả hai. Đặt"
        log "          BACKUP_MIRROR_DIR trỏ tới ổ ngoài hoặc máy khác."
    fi
    return 0
}

encrypt_in_place() {
    # $1 = tệp cần mã hoá. Thành công thì tệp gốc BIẾN MẤT, còn lại "$1.gpg".
    #
    # Thứ tự quan trọng: tự kiểm chạy TRƯỚC bước này, trên bản rõ, vì
    # `pg_restore` không đọc được tệp đã mã hoá. Nên sau khi mã hoá phải giải
    # mã lại một lượt — nếu không, thứ đã được kiểm và thứ được giữ lại là hai
    # tệp khác nhau, và cái được giữ chưa từng ai đọc thử.
    plain="$1"
    [ -n "$PASSPHRASE" ] || return 0

    if ! printf '%s' "$PASSPHRASE" | gpg --batch --quiet --yes \
            --pinentry-mode loopback --passphrase-fd 0 \
            --symmetric --cipher-algo AES256 --s2k-digest-algo SHA512 \
            --output "${plain}.gpg" "$plain"; then
        log "LỖI: mã hoá $(basename "$plain") thất bại — giữ bản rõ"
        rm -f "${plain}.gpg"
        return 1
    fi

    # Đọc lại bản đã mã hoá. gpg đối xứng có kiểm toàn vẹn (MDC), nên bước này
    # bắt được cả tệp cụt lẫn tệp bị sửa, không chỉ "sai mật khẩu".
    if ! printf '%s' "$PASSPHRASE" | gpg --batch --quiet --yes \
            --pinentry-mode loopback --passphrase-fd 0 \
            --decrypt --output /dev/null "${plain}.gpg" 2>/dev/null; then
        log "LỖI: bản mã hoá không giải mã lại được — giữ bản rõ, xoá bản mã hoá"
        rm -f "${plain}.gpg"
        return 1
    fi

    rm -f "$plain"
    log "đã mã hoá: $(basename "${plain}.gpg") ($(wc -c < "${plain}.gpg") byte, đã giải mã thử)"
    return 0
}

mirror_run() {
    # $1 = dấu thời gian. Chép lượt sao lưu sang nơi thứ hai.
    #
    # Hỏng ở đây KHÔNG làm hỏng lượt sao lưu: bản tại chỗ đã ghi xong và đã tự
    # kiểm. Nhưng nó phải kêu to, vì "có bản ngoài" là điều người ta tin vào
    # đúng lúc không kiểm lại được nữa.
    [ -n "$MIRROR_DIR" ] || return 0
    stamp="$1"
    copied=0
    for f in "$BACKUP_DIR/${PGDATABASE}_${stamp}.dump" \
             "$BACKUP_DIR/${PGDATABASE}_${stamp}.dump.gpg" \
             "$BACKUP_DIR/legal_${stamp}.tar.gz" \
             "$BACKUP_DIR/legal_${stamp}.tar.gz.gpg"; do
        [ -f "$f" ] || continue
        # Chép ra tên tạm rồi đổi tên, y như lúc ghi bản gốc: một lượt chép bị
        # cắt giữa chừng sang ổ ngoài để lại `.part`, không để lại một tệp mang
        # đúng tên bản sao lưu thật mà bên trong thì cụt.
        if cp "$f" "$MIRROR_DIR/$(basename "$f").part" \
           && mv "$MIRROR_DIR/$(basename "$f").part" "$MIRROR_DIR/$(basename "$f")"; then
            copied=$((copied + 1))
        else
            log "CẢNH BÁO: không chép được $(basename "$f") sang $MIRROR_DIR"
            rm -f "$MIRROR_DIR/$(basename "$f").part"
            return 1
        fi
    done
    printf '%s\n' "$stamp" > "$MIRROR_DIR/LATEST" 2>/dev/null || true
    log "bản sao ngoài: $copied tệp -> $MIRROR_DIR"
    return 0
}

dump_database() {
    # $1 = dấu thời gian. Trả 0 nếu bản dump đã ghi xong và đọc lại được.
    target="$BACKUP_DIR/${PGDATABASE}_$1.dump"
    # Ghi ra tên tạm rồi mới đổi tên. Cùng lý do với bản xuất dữ liệu tenant:
    # một tiến trình bị giết giữa chừng để lại `.part`, chứ không để lại một
    # tệp mang đúng tên bản sao lưu thật mà bên trong thì cụt.
    #
    # Có `$$` trong tên tạm vì dấu thời gian chỉ chính xác tới GIÂY. Chạy tay
    # một lượt sao lưu trong lúc service đang chạy lượt của nó — chuyện hoàn
    # toàn bình thường khi sắp làm gì đó rủi ro — mà trúng cùng một giây thì
    # hai tiến trình ghi chung một tệp `.part`, và cái `mv` về sau đặt tên thật
    # cho một bản dump bị hai bên ghi xen. Nó vẫn qua được phép tự kiểm nếu
    # phần chồng lấn rơi đúng chỗ, và đó là kiểu hỏng tệ nhất: một bản sao lưu
    # trông hợp lệ mà bên trong là hai bản trộn vào nhau.
    partial="${target}.$$.part"

    log "bắt đầu dump -> $(basename "$target")"
    if ! pg_dump -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -Fc -f "$partial"; then
        log "LỖI: pg_dump thất bại"
        rm -f "$partial"
        return 1
    fi

    # Đọc HẾT tệp, không chỉ mục lục. Xem đầu tệp về lý do.
    if ! pg_restore -f /dev/null "$partial" > /dev/null 2>&1; then
        log "LỖI: bản dump không đọc lại được trọn vẹn — giữ lại dưới tên .CORRUPT"
        mv "$partial" "${target}.CORRUPT"
        return 1
    fi

    mv "$partial" "$target"
    log "xong: $(basename "$target") ($(wc -c < "$target") byte, đã tự kiểm)"
    # Mã hoá SAU khi tự kiểm — `pg_restore` không đọc được tệp đã mã hoá, nên
    # đảo thứ tự là bỏ luôn phép kiểm. Hỏng ở bước mã hoá thì bản rõ ở lại: có
    # một bản sao lưu dùng được mà chưa mã hoá vẫn hơn không có bản nào.
    encrypt_in_place "$target" || log "CẢNH BÁO: $(basename "$target") còn ở dạng KHÔNG mã hoá"
    return 0
}

archive_legal() {
    # $1 = dấu thời gian. Gọi SAU dump_database — thứ tự là một phần của tính
    # đúng, xem đầu tệp.
    target="$BACKUP_DIR/legal_$1.tar.gz"
    partial="${target}.$$.part"   # xem `dump_database` về `$$`

    if [ ! -d "$LEGAL_DIR" ]; then
        log "LỖI: không thấy kho pháp lý tại $LEGAL_DIR — bản sao lưu này KHÔNG đầy đủ"
        return 1
    fi

    # Đọc khoá TRƯỚC khi nén. Xem lập luận thứ tự ở đầu tệp.
    if ! keys="$(psql_value "SELECT storage_key FROM legal_documents WHERE storage_key IS NOT NULL
                             UNION SELECT storage_key FROM legal_document_drafts WHERE storage_key IS NOT NULL
                             UNION SELECT storage_key FROM legal_document_events WHERE storage_key IS NOT NULL")"; then
        log "LỖI: không đọc được danh sách khoá kho pháp lý"
        return 1
    fi

    # `.tmp-*` là tệp đang ghi dở của `legal_store.write`, không phải nội dung.
    # tar trả 1 khi thư mục đổi trong lúc đọc (một lượt công bố chen vào giữa) —
    # đó là cảnh báo, không phải hỏng, và phép đối chiếu bên dưới mới là cửa ải
    # thật. Trả >1 mới là lỗi thật sự.
    rc=0
    tar -czf "$partial" -C "$LEGAL_DIR" --exclude='.tmp-*' . || rc=$?
    if [ "$rc" -gt 1 ]; then
        log "LỖI: tar thất bại (mã $rc)"
        rm -f "$partial"
        return 1
    fi

    if ! listing="$(tar -tzf "$partial" 2>/dev/null)"; then
        log "LỖI: bản lưu trữ kho pháp lý không đọc lại được — giữ lại dưới tên .CORRUPT"
        mv "$partial" "${target}.CORRUPT"
        return 1
    fi

    missing=0
    for key in $keys; do
        if ! printf '%s\n' "$listing" | grep -qxF "./$key"; then
            log "LỖI: khoá đang dùng nhưng thiếu tệp trong bản lưu trữ: $key"
            missing=$((missing + 1))
        fi
    done
    if [ "$missing" -gt 0 ]; then
        log "LỖI: $missing khoá không có tệp — giữ lại dưới tên .CORRUPT"
        mv "$partial" "${target}.CORRUPT"
        return 1
    fi

    mv "$partial" "$target"
    blobs="$(printf '%s\n' "$listing" | grep -c '\.md$' || true)"
    log "xong: $(basename "$target") ($(wc -c < "$target") byte, $blobs bản văn, đã đối chiếu)"
    encrypt_in_place "$target" || log "CẢNH BÁO: $(basename "$target") còn ở dạng KHÔNG mã hoá"
    return 0
}

run_backup() {
    stamp="$(date -u '+%Y%m%d_%H%M%S')"

    dump_database "$stamp" || return 1

    # Kho pháp lý hỏng KHÔNG làm mất bản dump: dump đã qua tự kiểm và vẫn dùng
    # được. Con trỏ LATEST vẫn trỏ tới lượt này, và script khôi phục sẽ kêu vì
    # không thấy tệp lưu trữ đi kèm — im lặng bỏ qua mới là cái bẫy.
    archive_legal "$stamp" || log "CẢNH BÁO: lượt $stamp thiếu phần kho pháp lý"

    # Con trỏ tới lượt mới nhất. Chứa DẤU THỜI GIAN chứ không phải tên tệp: một
    # lượt sao lưu giờ gồm hai tệp, và một con trỏ chỉ nêu được một tên sẽ buộc
    # script khôi phục đoán tên tệp còn lại.
    printf '%s\n' "$stamp" > "$BACKUP_DIR/LATEST"

    mirror_run "$stamp" || log "CẢNH BÁO: lượt $stamp CHƯA có bản sao ngoài"
    return 0
}

prune_old() {
    # `-mtime +N` bỏ những tệp cũ hơn N ngày. Chỉ đụng vào bản đã hoàn tất: tệp
    # .CORRUPT và .part được giữ lại có chủ ý cho tới khi có người xem xét.
    #
    # `.gpg` nằm trong danh sách này. Thiếu nó thì bật mã hoá lên đồng nghĩa
    # với tắt luôn việc dọn dẹp, và thư mục sao lưu lớn dần cho tới khi đầy ổ —
    # thứ đầu tiên hỏng khi ổ đầy chính là lượt sao lưu tiếp theo.
    removed="$(find "$BACKUP_DIR" -maxdepth 1 \
        \( -name '*.dump' -o -name '*.dump.gpg' \
           -o -name 'legal_*.tar.gz' -o -name 'legal_*.tar.gz.gpg' \) \
        -mtime "+${KEEP_DAYS}" -print -delete | wc -l)"
    if [ "$removed" -gt 0 ]; then
        log "dọn $removed tệp cũ hơn ${KEEP_DAYS} ngày"
    fi

    # Bản sao ngoài dọn theo cùng chính sách. Không dọn thì ổ ngoài đầy trong
    # im lặng, và lượt chép tiếp theo hỏng ở đúng nơi không ai nhìn.
    if [ -n "$MIRROR_DIR" ] && [ -d "$MIRROR_DIR" ]; then
        find "$MIRROR_DIR" -maxdepth 1 \
            \( -name '*.dump' -o -name '*.dump.gpg' \
               -o -name 'legal_*.tar.gz' -o -name 'legal_*.tar.gz.gpg' \) \
            -mtime "+${KEEP_DAYS}" -delete 2>/dev/null || true
    fi
}

log "khởi động: mỗi ${INTERVAL_SECONDS}s, giữ ${KEEP_DAYS} ngày, thư mục ${BACKUP_DIR}"

# Hỏng cấu hình thì chết hẳn, đừng chạy tiếp. Một service sao lưu đang
# "restarting" thì ai nhìn `docker compose ps` cũng thấy; một service đang "up"
# mà mọi lượt dump đều lỗi thì không ai thấy cho tới ngày cần khôi phục.
preflight || exit 1

# Chạy một lượt NGAY khi khởi động, không chờ hết chu kỳ đầu. Không có nó, một
# stack vừa được dựng lại sẽ không có bản sao lưu nào trong 24 giờ đầu — đúng
# quãng thời gian dễ hỏng nhất.
run_backup || log "lượt sao lưu đầu tiên thất bại; sẽ thử lại ở chu kỳ sau"
prune_old

while true; do
    sleep "$INTERVAL_SECONDS"
    run_backup || log "lượt sao lưu thất bại; sẽ thử lại ở chu kỳ sau"
    prune_old
done
