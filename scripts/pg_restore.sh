#!/bin/sh
# Khôi phục — và diễn tập khôi phục — từ bản sao lưu do `pg_backup.sh` tạo.
#
# Vì sao mặc định là DIỄN TẬP chứ không phải khôi phục
# ------------------------------------------------------
# Một script khôi phục chạy đúng một lần trong đời, vào ngày tệ nhất, bởi một
# người đang cuống. Nếu lần chạy đầu tiên của nó cũng là lần đầu tiên nó được
# thử thì nó không phải kế hoạch khôi phục — nó là một hy vọng.
#
# Nên chế độ mặc định (`--drill`) dựng bản sao lưu vào một cơ sở dữ liệu nháp,
# đếm từng bảng, đối chiếu với bản đang chạy, kiểm băm từng bản văn pháp lý,
# rồi xoá cơ sở dữ liệu nháp. Nó không đụng vào dữ liệu thật, nên chạy được
# hàng tuần, và mỗi lần chạy là một bằng chứng mới rằng bản sao lưu dùng được.
#
# Khôi phục đè lên dữ liệu thật cần `--force-into-production` KÈM biến môi
# trường `CONFIRM=RESTORE-<tên_db>`. Hai lớp, và lớp thứ hai buộc phải gõ đúng
# tên cơ sở dữ liệu: một cờ đơn lẻ là thứ người ta dán lại từ lịch sử shell.
#
# Vì sao vẫn dump trước khi đè
# ------------------------------
# Trạng thái hiện tại — kể cả trạng thái hỏng — là bằng chứng. Khôi phục nhầm
# bản, hoặc phát hiện sự cố tệ hơn ta tưởng sau khi đã đè, đều là chuyện có
# thật. Bản dump an toàn ở bước đầu là đường lui duy nhất.
#
# Cách chạy: xem docs/BACKUP_RESTORE.md

set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
LEGAL_DIR="${LEGAL_STORE_DIR:-/dataset/legal}"
PGHOST="${PGHOST:-postgres}"
PGUSER="${POSTGRES_USER:?POSTGRES_USER là bắt buộc}"
PGDATABASE="${POSTGRES_DB:?POSTGRES_DB là bắt buộc}"
export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD là bắt buộc}"

MODE="drill"
STAMP=""
TARGET_DB=""
KEEP_SCRATCH=0

log() {
    echo "[pg-restore $(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"
}

die() {
    log "LỖI: $*"
    exit 1
}

usage() {
    cat <<'EOF'
pg_restore.sh [tuỳ chọn]

  --drill                   (mặc định) dựng vào cơ sở dữ liệu nháp, đối chiếu,
                            rồi xoá. Không đụng dữ liệu thật.
  --into <db>               dựng vào một cơ sở dữ liệu có tên cụ thể và GIỮ lại.
  --force-into-production   đè lên $POSTGRES_DB. Cần CONFIRM=RESTORE-<db>.
  --stamp <YYYYmmdd_HHMMSS> chọn lượt sao lưu. Mặc định: đọc tệp LATEST.
  --keep-scratch            giữ lại cơ sở dữ liệu nháp sau khi diễn tập.
  --list                    liệt kê các lượt sao lưu đang có rồi thoát.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --drill) MODE="drill" ;;
        --into) MODE="into"; TARGET_DB="${2:?--into cần tên cơ sở dữ liệu}"; shift ;;
        --force-into-production) MODE="production" ;;
        --stamp) STAMP="${2:?--stamp cần dấu thời gian}"; shift ;;
        --keep-scratch) KEEP_SCRATCH=1 ;;
        --list) MODE="list" ;;
        -h|--help) usage; exit 0 ;;
        *) usage; die "tham số lạ: $1" ;;
    esac
    shift
done

psql_admin() {
    # `-d postgres` chứ không phải $PGDATABASE: CREATE/DROP DATABASE không chạy
    # được khi đang kết nối vào chính cơ sở dữ liệu đó.
    psql -h "$PGHOST" -U "$PGUSER" -d postgres -Atqc "$1"
}

list_backups() {
    log "thư mục $BACKUP_DIR:"
    latest="(không có)"
    [ -f "$BACKUP_DIR/LATEST" ] && latest="$(cat "$BACKUP_DIR/LATEST")"
    found=0
    for dump in "$BACKUP_DIR"/*.dump "$BACKUP_DIR"/*.dump.gpg; do
        [ -e "$dump" ] || continue
        found=$((found + 1))
        enc=""; base="$dump"
        case "$dump" in *.gpg) enc=" [đã mã hoá]"; base="${dump%.gpg}" ;; esac
        s="$(basename "$base" .dump | sed 's/^.*_\([0-9]\{8\}_[0-9]\{6\}\)$/\1/')"
        legal="$BACKUP_DIR/legal_${s}.tar.gz"
        [ -f "$legal" ] || legal="$BACKUP_DIR/legal_${s}.tar.gz.gpg"
        mark=" "; [ "$s" = "$latest" ] && mark="*"
        if [ -f "$legal" ]; then
            log "  $mark $s  db=$(wc -c < "$dump") byte  pháp lý=$(wc -c < "$legal") byte$enc"
        else
            log "  $mark $s  db=$(wc -c < "$dump") byte  pháp lý=THIẾU$enc"
        fi
    done
    [ "$found" -gt 0 ] || { log "  (chưa có bản sao lưu nào)"; return 0; }
    corrupt="$(find "$BACKUP_DIR" -maxdepth 1 -name '*.CORRUPT' | wc -l)"
    [ "$corrupt" -gt 0 ] && log "  CẢNH BÁO: $corrupt tệp .CORRUPT đang chờ xem xét"
    return 0
}

#: Nơi đặt bản đã giải mã. `mktemp -d` chứ không phải một tên cố định: hai lượt
#: diễn tập chạy song song sẽ ghi đè lên nhau, và bản rõ của một lượt sao lưu
#: là thứ không nên nằm ở một đường dẫn đoán được.
PLAINTEXT_DIR=""

cleanup_plaintext() {
    # Bản rõ chỉ sống trong lúc script chạy. Nó chứa email, số điện thoại và
    # băm mật khẩu; để lại trên đĩa là xoá sạch lý do đã mã hoá bản sao lưu.
    [ -n "$PLAINTEXT_DIR" ] && rm -rf "$PLAINTEXT_DIR"
    PLAINTEXT_DIR=""
}
trap cleanup_plaintext EXIT INT TERM

decrypt_if_needed() {
    # $1 = TÊN biến giữ đường dẫn. Nếu bản rõ không có mà bản `.gpg` có thì
    # giải mã ra thư mục tạm và trỏ biến sang đó.
    var="$1"
    eval "path=\${$var}"
    [ -n "$path" ] || return 0
    [ -f "$path" ] && return 0
    [ -f "${path}.gpg" ] || return 0

    [ -n "${BACKUP_PASSPHRASE:-}" ] \
        || die "lượt $STAMP đã mã hoá nhưng không có BACKUP_PASSPHRASE. Không có
       khoá thì không có cách nào khác — đó là điều mã hoá hứa hẹn."

    [ -n "$PLAINTEXT_DIR" ] || PLAINTEXT_DIR="$(mktemp -d)"
    out="$PLAINTEXT_DIR/$(basename "$path")"
    if ! printf '%s' "$BACKUP_PASSPHRASE" | gpg --batch --quiet --yes \
            --pinentry-mode loopback --passphrase-fd 0 \
            --decrypt --output "$out" "${path}.gpg" 2>/dev/null; then
        die "không giải mã được $(basename "${path}.gpg") — sai mật khẩu, hoặc tệp hỏng"
    fi
    log "đã giải mã $(basename "${path}.gpg") ra thư mục tạm"
    eval "$var=\$out"
    return 0
}

resolve_stamp() {
    if [ -z "$STAMP" ]; then
        if [ -f "$BACKUP_DIR/LATEST" ]; then
            STAMP="$(cat "$BACKUP_DIR/LATEST")"
            log "dùng lượt mới nhất theo con trỏ LATEST: $STAMP"
        else
            # Con trỏ mất không phải lý do để bó tay: tên tệp có dấu thời gian
            # và thứ tự từ điển của nó trùng thứ tự thời gian.
            STAMP="$(ls -1 "$BACKUP_DIR"/*.dump "$BACKUP_DIR"/*.dump.gpg 2>/dev/null \
                | sed 's/\.gpg$//' \
                | sed 's/.*_\([0-9]\{8\}_[0-9]\{6\}\)\.dump$/\1/' | sort -u | tail -1)"
            [ -n "$STAMP" ] || die "không có bản sao lưu nào trong $BACKUP_DIR"
            log "không thấy con trỏ LATEST; suy ra từ tên tệp: $STAMP"
        fi
    fi
    DUMP_FILE="$BACKUP_DIR/${PGDATABASE}_${STAMP}.dump"
    LEGAL_FILE="$BACKUP_DIR/legal_${STAMP}.tar.gz"

    # Bản mã hoá được giải ra thư mục tạm rồi mọi bước sau chạy như cũ. Giải mã
    # ở ĐÂY, một chỗ duy nhất, chứ không rải `gpg -d` khắp các nhánh: diễn tập,
    # khôi phục vào db nháp và khôi phục đè lên sản xuất đều đi qua hàm này.
    decrypt_if_needed DUMP_FILE
    decrypt_if_needed LEGAL_FILE

    [ -f "$DUMP_FILE" ] || die "không thấy bản dump $DUMP_FILE"
    # `-f /dev/null` chứ không phải `--list`: mục lục nằm ở đầu tệp, nên `--list`
    # trả 0 trên một bản dump bị cắt mất nửa sau. Xem `pg_backup.sh`.
    pg_restore -f /dev/null "$DUMP_FILE" > /dev/null 2>&1 \
        || die "bản dump $DUMP_FILE không đọc lại được trọn vẹn — đừng dùng nó"
    log "bản dump hợp lệ: $(basename "$DUMP_FILE") ($(wc -c < "$DUMP_FILE") byte)"
    if [ -f "$LEGAL_FILE" ]; then
        log "kho pháp lý đi kèm: $(basename "$LEGAL_FILE") ($(wc -c < "$LEGAL_FILE") byte)"
    else
        log "CẢNH BÁO: lượt $STAMP KHÔNG có bản lưu trữ kho pháp lý."
        log "          Khôi phục xong sẽ có hàng dữ liệu trỏ tới văn bản không đọc được."
        LEGAL_FILE=""
    fi
}

# Đếm chính xác từng bảng. `pg_stat_user_tables.n_live_tup` là số ƯỚC LƯỢNG do
# autovacuum cập nhật — nó lệch, và một phép đối chiếu sao lưu dựa trên số ước
# lượng thì không khẳng định được gì.
count_tables() {
    db="$1"
    query="$(psql -h "$PGHOST" -U "$PGUSER" -d "$db" -Atqc \
        "SELECT coalesce(string_agg(format('SELECT %L AS t, count(*) AS n FROM public.%I', tablename, tablename), ' UNION ALL '), '')
         FROM pg_tables WHERE schemaname = 'public'")"
    [ -n "$query" ] || return 0
    psql -h "$PGHOST" -U "$PGUSER" -d "$db" -Atqc "$query" | sort
}

compare_counts() {
    scratch="$1"
    live_counts="$(mktemp)"; restored_counts="$(mktemp)"
    count_tables "$PGDATABASE" > "$live_counts"
    count_tables "$scratch"    > "$restored_counts"

    empty_but_should_not_be=0
    missing_tables=0
    drifted=0

    while IFS='|' read -r table live_n; do
        [ -n "$table" ] || continue
        restored_n="$(awk -F'|' -v t="$table" '$1 == t { print $2 }' "$restored_counts")"
        if [ -z "$restored_n" ]; then
            log "  THIẾU BẢNG  $table (bản đang chạy có $live_n dòng)"
            missing_tables=$((missing_tables + 1))
        elif [ "$restored_n" = "0" ] && [ "$live_n" != "0" ]; then
            # Kiểu hỏng chết người: bản dump có cấu trúc bảng nhưng không có
            # dòng nào. Chính xác thứ mà một lượt dump bị RLS lọc sẽ tạo ra.
            log "  RỖNG        $table (bản đang chạy có $live_n dòng, bản khôi phục 0)"
            empty_but_should_not_be=$((empty_but_should_not_be + 1))
        elif [ "$restored_n" != "$live_n" ]; then
            # Chênh lệch là BÌNH THƯỜNG: bản sao lưu chụp ở quá khứ, hệ thống
            # vẫn chạy tiếp. Ghi ra để đọc, không tính là lỗi.
            log "  lệch        $table: sao lưu $restored_n / đang chạy $live_n"
            drifted=$((drifted + 1))
        fi
    done < "$live_counts"

    total="$(wc -l < "$restored_counts")"
    rm -f "$live_counts" "$restored_counts"

    log "đối chiếu: $total bảng khôi phục được, $drifted bảng lệch số dòng (bình thường)"
    if [ "$empty_but_should_not_be" -gt 0 ] || [ "$missing_tables" -gt 0 ]; then
        log "KẾT LUẬN: bản sao lưu KHÔNG dùng được — $empty_but_should_not_be bảng rỗng, $missing_tables bảng thiếu"
        return 1
    fi
    log "KẾT LUẬN: mọi bảng có dữ liệu ở bản đang chạy đều có dữ liệu ở bản khôi phục"
    return 0
}

# Kiểm kho pháp lý đầu-cuối: mọi khoá mà cơ sở dữ liệu VỪA KHÔI PHỤC trỏ tới
# đều có tệp trong bản lưu trữ, và băm của tệp khớp với tên nó. Đây là phép
# kiểm mà `pg_restore --list` không làm được — nó nối hai kho lại với nhau.
verify_legal() {
    db="$1"
    [ -n "$LEGAL_FILE" ] || { log "bỏ qua kiểm kho pháp lý: lượt này không có bản lưu trữ"; return 0; }

    workdir="$(mktemp -d)"
    tar -xzf "$LEGAL_FILE" -C "$workdir" || { rm -rf "$workdir"; die "không giải nén được $LEGAL_FILE"; }

    keys="$(psql -h "$PGHOST" -U "$PGUSER" -d "$db" -Atqc \
        "SELECT storage_key FROM legal_documents WHERE storage_key IS NOT NULL
         UNION SELECT storage_key FROM legal_document_drafts WHERE storage_key IS NOT NULL
         UNION SELECT storage_key FROM legal_document_events WHERE storage_key IS NOT NULL")"

    checked=0; bad=0
    for key in $keys; do
        path="$workdir/$key"
        checked=$((checked + 1))
        if [ ! -f "$path" ]; then
            log "  THIẾU TỆP   $key"
            bad=$((bad + 1))
            continue
        fi
        # Tên tệp LÀ băm sha256 của nội dung. Băm lại và so là đủ để phát hiện
        # hỏng bit, cắt cụt, hay tráo nội dung — không cần siêu dữ liệu nào.
        want="$(basename "$key" .md)"
        got="$(sha256sum "$path" | cut -d' ' -f1)"
        if [ "$want" != "$got" ]; then
            log "  SAI BĂM     $key (tệp băm ra $got)"
            bad=$((bad + 1))
        fi
    done

    blobs="$(find "$workdir" -name '*.md' | wc -l)"
    rm -rf "$workdir"

    if [ "$bad" -gt 0 ]; then
        log "kho pháp lý: $bad/$checked khoá HỎNG (kho có $blobs tệp)"
        return 1
    fi
    log "kho pháp lý: $checked/$checked khoá khớp băm (kho có $blobs tệp)"
    return 0
}

restore_into() {
    db="$1"
    log "dựng bản dump vào '$db' ..."
    # `--no-owner --no-privileges`: vai sở hữu ở máy đích có thể khác. Không có
    # hai cờ này, một bản khôi phục sang máy khác đổ hàng loạt lỗi "role does
    # not exist" và dừng giữa chừng.
    # `--exit-on-error`: mặc định pg_restore chạy tiếp qua lỗi và trả 0. Một
    # lượt khôi phục "thành công" mà bỏ sót nửa số bảng là kiểu hỏng tệ nhất.
    pg_restore -h "$PGHOST" -U "$PGUSER" -d "$db" \
        --no-owner --no-privileges --exit-on-error "$DUMP_FILE"
}

case "$MODE" in
    list)
        list_backups
        exit 0
        ;;

    drill)
        resolve_stamp
        # `$$` trong tên: hai lượt diễn tập cùng lúc trên cùng một bản sao lưu
        # — chẳng hạn một lượt chạy tay chen vào một lượt trong CI — sẽ dùng
        # chung tên cơ sở dữ liệu nháp, và lượt sau `DROP DATABASE IF EXISTS`
        # ngay giữa lúc lượt trước đang dựng.
        scratch="drill_${STAMP}_$$"
        log "diễn tập vào cơ sở dữ liệu nháp '$scratch' (không đụng '$PGDATABASE')"
        psql_admin "DROP DATABASE IF EXISTS \"$scratch\"" > /dev/null
        psql_admin "CREATE DATABASE \"$scratch\"" > /dev/null

        ok=0
        restore_into "$scratch" || ok=1
        [ "$ok" -eq 0 ] && { compare_counts "$scratch" || ok=1; }
        [ "$ok" -eq 0 ] && { verify_legal "$scratch" || ok=1; }

        if [ "$KEEP_SCRATCH" -eq 1 ]; then
            log "giữ lại '$scratch' theo yêu cầu (--keep-scratch)"
        else
            psql_admin "DROP DATABASE IF EXISTS \"$scratch\"" > /dev/null
            log "đã xoá cơ sở dữ liệu nháp '$scratch'"
        fi

        [ "$ok" -eq 0 ] || die "DIỄN TẬP THẤT BẠI cho lượt $STAMP"
        log "DIỄN TẬP ĐẠT cho lượt $STAMP"
        ;;

    into)
        resolve_stamp
        log "dựng vào '$TARGET_DB' và giữ lại"
        psql_admin "CREATE DATABASE \"$TARGET_DB\"" > /dev/null 2>&1 || log "'$TARGET_DB' đã tồn tại; dựng đè lên"
        restore_into "$TARGET_DB"
        verify_legal "$TARGET_DB" || log "CẢNH BÁO: kho pháp lý không kiểm được"
        log "xong. Bản lưu trữ kho pháp lý CHƯA được giải nén ra $LEGAL_DIR — làm bằng tay nếu cần."
        ;;

    production)
        [ "${CONFIRM:-}" = "RESTORE-$PGDATABASE" ] \
            || die "khôi phục đè cần CONFIRM=RESTORE-$PGDATABASE trong môi trường"
        resolve_stamp

        # Đường lui. Xem đầu tệp: trạng thái hiện tại, kể cả hỏng, là bằng chứng.
        safety="$BACKUP_DIR/${PGDATABASE}_pre_restore_$(date -u '+%Y%m%d_%H%M%S').dump"
        log "dump an toàn trạng thái HIỆN TẠI -> $(basename "$safety")"
        pg_dump -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -Fc -f "$safety" \
            || die "không dump được trạng thái hiện tại — dừng, không đè"
        pg_restore -f /dev/null "$safety" > /dev/null 2>&1 \
            || die "dump an toàn không đọc lại được trọn vẹn — dừng, không đè"
        log "đường lui đã sẵn: $safety"

        log "ĐANG ĐÈ LÊN '$PGDATABASE' bằng lượt $STAMP"
        # `--clean --if-exists` bỏ đối tượng cũ trước khi dựng lại. Không có nó,
        # bản khôi phục chồng lên schema cũ và mọi INSERT đụng khoá chính.
        pg_restore -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" \
            --clean --if-exists --no-owner --no-privileges --exit-on-error "$DUMP_FILE" \
            || die "khôi phục thất bại. Đường lui: $safety"

        verify_legal "$PGDATABASE" || log "CẢNH BÁO: kho pháp lý không khớp — xem docs/BACKUP_RESTORE.md"
        log "khôi phục xong. Kho tệp pháp lý PHẢI giải nén riêng:"
        log "  tar -xzf $LEGAL_FILE -C $LEGAL_DIR"
        log "Sau đó khởi động lại backend để nạp lại bộ nhớ đệm."
        ;;
esac
