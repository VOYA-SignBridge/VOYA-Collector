# Nhánh `main`: chuyển sang, cập nhật web, xử lý xung đột

Dành cho cả nhóm. Lệnh gõ trong **Git Bash**. Lệnh `VOYA.bat` trong Git Bash gõ dạng `cmd //c "VOYA.bat ..."`.

## Quy tắc chung

- Chỉ có **một nhánh chính là `main`**, và máy chạy web chạy `main`.
- Làm việc gì cũng tạo nhánh riêng từ `main`, xong thì mở PR vào `main`.
- PR chỉ được gộp khi **CI trên GitHub xanh**. Máy mình test xanh chưa đủ.
- Trên máy chạy web: **không** pull nhánh khác, **không** sửa mã, **không** commit.

## 1. Đưa nhánh tái cấu trúc lên `main` (làm một lần)

Người phụ trách mã làm việc này trên máy phát triển.

**Bước 1. Kiểm tra trước, không thay đổi gì:**

```bash
git fetch --all --prune
git merge-base --is-ancestor origin/deploy_ctu_ver-2.2.1 origin/son_arrange_repo2 && echo DU || echo THIEU
git merge-tree --write-tree --name-only origin/main origin/son_arrange_repo2
```

- Lệnh 2 phải in `DU`. Nếu in `THIEU`, gộp `deploy_ctu_ver-2.2.1` vào nhánh trước (xem mục 4).
- Lệnh 3 phải in **đúng một dòng mã**. Nếu in thêm tên tệp, đó là các tệp xung đột (xem mục 4).

**Bước 2. Mở PR:** trên GitHub vào **Pull requests → New**, chọn `base: main` ← `compare: son_arrange_repo2`. Chờ CI chạy xong; mọi dòng phải có dấu tích xanh.

**Bước 3. Thử trên máy không chạy web**, nạp bản sao DB thật (xem [BACKUP_RESTORE.md](BACKUP_RESTORE.md)), và đặt `USE_GOOGLE_DRIVE=0`. Thử lần lượt: đăng nhập, quên mật khẩu, đổi tổ chức, thu mẫu, tải video, huấn luyện, nhận dạng realtime, các trang quản trị.

**Bước 4. Bấm Merge.** Sau đó vào **Settings → Branches**, thêm luật cho `main`:
- *Require a pull request before merging*;
- *Require status checks to pass*.

**Bước 5. Báo nhóm:** từ nay dùng `main`; ngừng push vào `deploy_ctu_ver-2.2.1`; ai có nhánh riêng thì gộp `main` mới vào (mục 4) rồi mở PR.

## 2. Chuyển máy chạy web sang `main` (làm một lần)

Làm sau mục 1, vào giờ ít người dùng. Web gián đoạn vài phút.

| # | Lệnh | Đúng khi thấy |
|---|---|---|
| 1 | `cd /d/VOYA-Collector` | |
| 2 | `git status` | `working tree clean`. Nếu không sạch: **dừng**, báo người phụ trách |
| 3 | `git fetch --all --prune` | Không có `error` hay `fatal` |
| 4 | `git switch main` | `Switched to branch 'main'` |
| 5 | `git pull --ff-only` | `Fast-forward` hoặc `Already up to date`. Nếu `fatal`: **dừng**, báo người phụ trách |
| 6 | `cmd //c "VOYA.bat update-code --frontend"` | Chạy xong không lỗi (5–10 phút) |
| 7 | `cmd //c "VOYA.bat status"` | Mọi dịch vụ `healthy` |

Xong thì mở web, đăng nhập và thử vài chức năng.

**Quay về nếu hỏng:**

```bash
git switch deploy_ctu_ver-2.2.1
cmd //c "VOYA.bat update-code --frontend"
```

Dữ liệu không mất, vì nhánh mới không đổi cấu trúc DB (đã kiểm ngày 08/11/2026). Điều này chỉ đúng cho lần chuyển này.

## 3. Máy có bản luận văn: cất ra trước khi chuyển

`main` không còn chứa luận văn (`docs/00-thesis`), bài báo (`docs/CTU_SignBridge`), báo cáo (`reports/`) và 3 tệp bằng chứng có tên người ký (`docs/02-data/db/evidence/*signer*.csv`). Khi chuyển sang `main`, git sẽ **xoá chúng khỏi đĩa**. Vì vậy máy nào đang có chúng, nhất là máy đang viết luận văn, phải chép ra trước:

```bash
git status
mkdir -p Extra_docs/signer_evidence
cp -r docs/00-thesis docs/CTU_SignBridge reports Extra_docs/
cp docs/02-data/db/evidence/*signer*.csv Extra_docs/signer_evidence/
ls Extra_docs
git restore docs/00-thesis docs/CTU_SignBridge reports
```

- **Lệnh 1:** sửa đổi nào **không** thuộc ba thư mục trên thì commit hoặc `git stash` trước.
- **Lệnh 3–4:** chép cả ba thư mục, kể cả các sửa đổi chưa commit, cùng 3 tệp bằng chứng sang `Extra_docs/`. Thư mục này nằm ngoài git.
- **Lệnh 5:** phải thấy `00-thesis`, `CTU_SignBridge`, `reports` và `signer_evidence`.
- **Lệnh 6:** bỏ sửa đổi trên bản cũ trong repo; bản đầy đủ đã nằm trong `Extra_docs/`.

Sau đó làm tiếp từ bước 3 ở mục 2. Từ đây, sửa luận văn trong `Extra_docs/`.

> `Extra_docs/` **không có lịch sử git và không được sao lưu tự động.** Hãy tự sao lưu nó,
> ví dụ bằng OneDrive hoặc một repo riêng tư.

## 4. Kiểm tra và xử lý xung đột

Chỉ làm trên máy phát triển, không bao giờ làm trên máy chạy web.

**Xem trước:**

```bash
git fetch --all --prune
git switch <nhánh-của-bạn>
git merge-tree --write-tree --name-only origin/main HEAD
```

Nếu chỉ in một dòng mã thì không có xung đột. Nếu in thêm tên tệp, đó là các tệp sẽ xung đột.

**Gộp:**

```bash
git merge origin/main
```

Nếu thấy `CONFLICT`, liệt kê tệp còn xung đột:

```bash
git diff --name-only --diff-filter=U
```

Muốn **huỷ** và trở về như trước khi gộp: `git merge --abort`.

**Sửa từng tệp:** mở tệp trong VS Code, chọn một trong ba nút:
- **Accept Current**: giữ phần của bạn.
- **Accept Incoming**: lấy phần của `main`.
- **Accept Both**: giữ cả hai.

Lấy nguyên cả tệp từ một phía:

```bash
git checkout --ours   <tệp>
git checkout --theirs <tệp>
```

`--ours` giữ bản của bạn, `--theirs` lấy bản của `main`.

Nếu git báo tệp bị **xoá ở một phía, sửa ở phía kia**: muốn giữ thì `git add <tệp>`, đồng ý xoá thì `git rm <tệp>`.

**Mã đã bị dời chỗ do tái cấu trúc:** backend nay nằm trong `backend/app/modules/...`. Nếu bạn sửa một tệp ở chỗ cũ, hãy chép phần sửa sang tệp ở chỗ mới. Sau đó tìm các import còn trỏ đường cũ:

```bash
git grep -n "from app.<tên-module-cũ>"
```

**Hoàn tất:**

```bash
git add <các tệp đã sửa>
git diff --name-only --diff-filter=U
git grep -n -E "^(<<<<<<<|>>>>>>>)"
git commit --no-edit
git push
```

- Lệnh 2 và lệnh 3 phải **không in ra gì**.
- Sau khi push, mở PR vào `main` và chờ CI xanh.

## 5. Hằng ngày

**Người viết code:**

```bash
git switch main
git pull --ff-only
git switch -c <tên-nhánh>
git push -u origin <tên-nhánh>
```

Lệnh 3 tạo nhánh riêng; sửa code và commit trên nhánh đó. Lệnh 4 đẩy nhánh lên. Sau đó mở PR vào `main`; CI xanh thì Merge.

**Người cập nhật web:**
1. Trên GitHub, tab **Actions**: commit mới nhất của `main` phải xanh.
2. Cập nhật:
   ```bash
   cd /d/VOYA-Collector
   cmd //c "VOYA.bat update-git"
   cmd //c "VOYA.bat status"
   ```
   `update-git` tự kéo mã, tự dựng phần cần thiết, bật trang bảo trì trong lúc cập nhật, và tự quay về bản cũ nếu bản mới không chạy.

## Các nhánh cũ

| Nhánh | Xử lý |
|---|---|
| `deploy_ctu_ver-2.2.1` | Giữ vài tuần để quay về khi cần, rồi xoá |
| `son_arrange_repo2` | Xoá sau khi đã gộp vào `main` |
| `hoanganh_pytorch2tflie` | Gộp `main` vào (mục 4), rồi mở PR. Sẽ có 1 xung đột ở `backend/app/routers/training.py`: chọn **Accept Incoming**, rồi đặt 2 dòng `"handgcn_lite"` / `"hdgcn_lite"` vào `_MODEL_NAME_TO_REGISTRY_KEY` ở chỗ mới là `backend/app/modules/training/inference_service.py` |
| `experiment/feature-v2`, `feature/vocab-schema-v2` | Không còn gì riêng, có thể xoá |
| Các nhánh còn lại | Hỏi người tạo trước khi xoá |
