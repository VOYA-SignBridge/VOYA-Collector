# Hai nhánh `son_arrange_repo2` và `main`: thử mã, đưa lên, cập nhật web, xử lý xung đột

Dành cho cả nhóm. Lệnh gõ trong **Git Bash**. Lệnh `VOYA.bat` trong Git Bash gõ dạng `cmd //c "VOYA.bat ..."`.

## Quy tắc chung

| Nhánh | Vai trò | Ai ghi vào |
|---|---|---|
| `son_arrange_repo2` | **Nhánh thử mã.** Mọi thay đổi vào đây trước, CI chạy ở mỗi lần push | Người viết code (trực tiếp, hoặc qua nhánh riêng rồi PR vào đây) |
| `main` | **Nhánh triển khai.** Mỗi commit lên `main` được CI dựng thành ảnh và đẩy lên Docker Hub; máy chạy web chỉ chạy `main` | Chỉ nhận mã từ `son_arrange_repo2` (mục 1). **Không** commit thẳng |

```
viết code ──push──▶ son_arrange_repo2 ──CI xanh + thử xong──▶ main ──CI dựng ảnh──▶ Docker Hub ──update-git──▶ máy chạy web
```

- Chỉ đưa lên `main` khi **CI trên GitHub xanh** ở commit mới nhất của `son_arrange_repo2`. Máy mình test xanh chưa đủ.
- Trên máy chạy web: **không** pull nhánh khác, **không** sửa mã, **không** commit.
- Cần sửa gấp cho web cũng làm trên `son_arrange_repo2` rồi đưa lên, để hai nhánh không lệch nhau.

## 1. Đưa mã từ `son_arrange_repo2` lên `main`

Người phụ trách mã làm trên máy phát triển, mỗi khi muốn web nhận bản mới.

**Bước 1. Kiểm tra CI:** trên GitHub, tab **Actions**, lượt chạy mới nhất của `son_arrange_repo2` phải xanh hết.

**Bước 2. Thử** trên máy không chạy web nếu đợt này đổi nhiều (đăng nhập, thu mẫu, huấn luyện, nhận dạng realtime, trang quản trị). Đổi nhỏ thì bỏ qua bước này.

**Bước 3. Đưa lên:**

```bash
git fetch origin
git log --oneline origin/main..origin/son_arrange_repo2
git push origin origin/son_arrange_repo2:main
```

- Lệnh 2 liệt kê các commit sắp lên `main`. Đọc lướt để chắc đúng thứ mình muốn đưa lên.
- Lệnh 3 làm `main` trỏ đúng vào commit đã được CI kiểm. Nếu git báo `rejected (non-fast-forward)`, nghĩa là `main` có commit mà `son_arrange_repo2` thiếu (ai đó commit thẳng vào `main`). **Dừng lại**, gộp `main` vào `son_arrange_repo2` (mục 4) rồi làm lại từ bước 1.

Cách khác: mở PR trên GitHub với `base: main` ← `compare: son_arrange_repo2`, CI xanh thì bấm **Create a merge commit**. Đừng chọn *Squash* hay *Rebase*: chúng tạo commit mới, và lần sau hai nhánh sẽ lệch nhau.

**Bước 4. Chờ ảnh:** tab **Actions**, lượt *Build & push images* của `main` phải xanh (khoảng 15–25 phút). Xong thì báo người cập nhật web (mục 5).

## 2. Chuyển máy chạy web sang `main` (làm một lần)

Máy **tải ảnh CI đã dựng** thay vì tự dựng. Lần đầu tải khoảng 5 GB (nén), nhưng web vẫn chạy trong lúc tải; chỉ gián đoạn vài phút lúc đổi sang bản mới. Làm vào giờ ít người dùng.

Trước khi bắt đầu, trên GitHub, tab **Actions**: lượt *Build & push images* mới nhất của `main` phải xanh.

| # | Lệnh | Đúng khi thấy |
|---|---|---|
| 1 | `cd /d/VOYA-Collector` | |
| 2 | `git branch --show-current` | `deploy_ctu_ver-2.2.1`. Tên khác thì **ghi lại**, dùng tên đó ở phần quay về |
| 3 | `git status --short --untracked-files=no` | Không in gì. Có tệp: **dừng**, báo người phụ trách |
| 4 | `grep -c -e "^SECRET_KEY=." -e "^AUTH_TOKEN_SECRET_KEY=." .env` | `1` hoặc `2`. Ra `0`: thêm `AUTH_TOKEN_SECRET_KEY=<khoá ngẫu nhiên 64 ký tự>` vào `.env` trước, nếu không backend mới từ chối khởi động |
| 5 | `grep -c -e REPLACE_WITH_RANDOM_SECRET -e change-me-in-production .env` | `0`. Khác 0: thay giá trị mẫu đó bằng khoá ngẫu nhiên |
| 6 | `grep "^VOYA_REGISTRY_NS=" .env` | Có một dòng. Chưa có thì thêm: `printf '\nVOYA_REGISTRY_NS=<tai-khoan-docker-hub>\n' >> .env` |
| 7 | `df -h /c /d` | Ổ chứa dữ liệu Docker (Docker Desktop → *Settings* → *Resources*) còn trống **ít nhất 20 GB** |
| 8 | `git fetch origin` | Không có `error` hay `fatal` |
| 9 | `git merge-base --is-ancestor HEAD origin/main && echo OK` | `OK`. Không in gì: **dừng**, báo người phụ trách |
| 10 | `git switch -C main` | `Switched to a new branch 'main'` (máy đã có nhánh `main` thì `Switched to and reset branch 'main'`) |
| 11 | `git branch -u origin/main` | `branch 'main' set up to track 'origin/main'` |
| 12 | `git show origin/main:scripts/voya.py > scripts/voya_main.py` | Không in gì |
| 13 | `cmd //c "python scripts\voya_main.py update-git"` | Liệt kê commit mới, báo `Che do keo anh`. Gõ `co` để tiếp tục. Chờ tới `OK: update-git` |
| 14 | `git restore --source=deploy_ctu_ver-2.2.1 --worktree -- processed/train_utils/outputs` | Không in gì (tên nhánh ở lệnh 2 khác thì thay vào) |
| 15 | `rm scripts/voya_main.py` | |
| 16 | `cmd //c "VOYA.bat status"` | Mọi dịch vụ `healthy` |

Giải thích:

- **Lệnh 10–11** là mẹo để `update-git` thấy toàn bộ khác biệt giữa bản đang chạy và `main`, rồi đi đúng quy trình thường ngày: sao lưu DB, tải ảnh trong lúc web vẫn chạy, bật trang bảo trì, đổi bản, kiểm sức khoẻ, hỏng thì tự quay về ảnh cũ.
- **Lệnh 12, 13, 15** chỉ cần cho lần chuyển này. `scripts/voya.py` trên máy vẫn là bản của `deploy_ctu_ver-2.2.1`, chưa có chế độ kéo ảnh: chạy `VOYA.bat update-git` lúc này sẽ **dựng lại toàn bộ tại chỗ** (tải lại torch khoảng 3 GB, từng kẹt nhiều giờ). Tệp tạm `voya_main.py` là `voya.py` của `main`; git bỏ qua nó vì chưa theo dõi. Từ lần sau chỉ cần `cmd //c "VOYA.bat update-git"`.
- **Lệnh 13** báo `chua co anh tren Docker Hub` mà tab Actions đã xanh: thường do mạng chập chờn lúc hỏi Docker Hub. Lệnh dừng trước khi đụng vào gì, chạy lại là được.
- **Lệnh 14:** `main` không còn giữ trong git các kết quả huấn luyện tháng 5–6 (`processed/train_utils/outputs/subset_*`), nên `git pull` ở lệnh 13 xoá chúng khỏi đĩa. Lệnh này chép lại từ nhánh cũ; `main` bỏ qua thư mục đó nên cây làm việc vẫn sạch. Kết quả huấn luyện chưa từng nằm trong git thì không bị đụng tới.
- Cũng ở lệnh 13, git xoá luận văn và báo cáo (`docs/00-thesis`, `reports/`, ...) khỏi đĩa máy này. Máy chạy web không dùng chúng; bản gốc vẫn còn trong lịch sử git.

Xong thì mở web, đăng nhập và thử vài chức năng.

**Quay về nếu hỏng.** `update-git` hỏng ở bước kiểm sức khoẻ thì tự gắn lại ảnh cũ, nhưng mã trên đĩa vẫn là `main`. Để về hẳn bản cũ (cả lúc nó tự quay về lẫn lúc phát hiện lỗi sau đó), dùng tên nhánh ở lệnh 2:

```bash
cd /d/VOYA-Collector
git switch deploy_ctu_ver-2.2.1
cmd //c "VOYA.bat rollback"
cmd //c "VOYA.bat status"
```

`rollback` in danh sách mốc rồi hỏi có quay về mốc mới nhất không. Mốc đó phải trùng dòng `Moc quay lui: rollback-auto-...` mà lệnh 13 đã in (mốc mới nhất). Đúng thì gõ `quay lui`.

Dữ liệu không mất, vì `main` không đổi cấu trúc DB so với `deploy_ctu_ver-2.2.1` (cùng lược đồ v8, kiểm ngày 10/11/2026). Điều này chỉ đúng cho lần chuyển này.

## 3. Máy có bản luận văn: cất ra trước khi chuyển nhánh

`main` và `son_arrange_repo2` không còn chứa luận văn (`docs/00-thesis`), bài báo (`docs/CTU_SignBridge`), báo cáo (`reports/`) và 3 tệp bằng chứng có tên người ký (`docs/02-data/db/evidence/*signer*.csv`). Khi chuyển sang một trong hai nhánh này, git sẽ **xoá chúng khỏi đĩa**. Vì vậy máy nào đang có chúng, nhất là máy đang viết luận văn, phải chép ra trước:

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

Sau đó mới `git switch`. Từ đây, sửa luận văn trong `Extra_docs/`.

> `Extra_docs/` **không có lịch sử git và không được sao lưu tự động.** Hãy tự sao lưu nó,
> ví dụ bằng OneDrive hoặc một repo riêng tư.

## 4. Kiểm tra và xử lý xung đột

Chỉ làm trên máy phát triển, không bao giờ làm trên máy chạy web. Dưới đây gộp `son_arrange_repo2` vào nhánh riêng của bạn. Muốn gộp `main` vào `son_arrange_repo2` (trường hợp bị từ chối ở mục 1) thì thay tên nhánh tương ứng.

**Xem trước:**

```bash
git fetch --all --prune
git switch <nhánh-của-bạn>
git merge-tree --write-tree --name-only origin/son_arrange_repo2 HEAD
```

Nếu chỉ in một dòng mã thì không có xung đột. Nếu in thêm tên tệp, đó là các tệp sẽ xung đột.

**Gộp:**

```bash
git merge origin/son_arrange_repo2
```

Nếu thấy `CONFLICT`, liệt kê tệp còn xung đột:

```bash
git diff --name-only --diff-filter=U
```

Muốn **huỷ** và trở về như trước khi gộp: `git merge --abort`.

**Sửa từng tệp:** mở tệp trong VS Code, chọn một trong ba nút:
- **Accept Current**: giữ phần của bạn.
- **Accept Incoming**: lấy phần của `son_arrange_repo2`.
- **Accept Both**: giữ cả hai.

Lấy nguyên cả tệp từ một phía:

```bash
git checkout --ours   <tệp>
git checkout --theirs <tệp>
```

`--ours` giữ bản của bạn, `--theirs` lấy bản của nhánh đang gộp vào.

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
- Sau khi push, mở PR vào `son_arrange_repo2` và chờ CI xanh.

## 5. Hằng ngày

**Người viết code:**

```bash
git switch son_arrange_repo2
git pull --ff-only
```

Sửa code, commit, rồi `git push`. CI tự chạy; xem kết quả ở tab **Actions**. Việc lớn thì tạo nhánh riêng (`git switch -c <tên-nhánh>`), push nhánh đó và mở PR vào `son_arrange_repo2`.

**Người cập nhật web:**
1. Trên GitHub, tab **Actions**: lượt *Build & push images* mới nhất của `main` phải xanh.
2. Cập nhật:
   ```bash
   cd /d/VOYA-Collector
   cmd //c "VOYA.bat update-git"
   cmd //c "VOYA.bat status"
   ```
   `update-git` tự kéo mã, tự dựng phần cần thiết, bật trang bảo trì trong lúc cập nhật, và tự quay về bản cũ nếu bản mới không chạy.

   Nếu `.env` có `VOYA_REGISTRY_NS` (xem [TRIEN_KHAI_TU_DAU.md](TRIEN_KHAI_TU_DAU.md), bước 7), máy **không dựng** mà tải ảnh CI đã dựng cho đúng commit. Nếu commit chưa có ảnh, lệnh báo `chua co anh tren Docker Hub` và dừng: đợi CI xanh rồi chạy lại.

**PR của Dependabot:** mỗi thứ Hai, Dependabot mở PR cập nhật gói vào `son_arrange_repo2`. Chỉ gộp khi CI xanh, và mỗi lần một PR. PR đổi ảnh gốc (`docker`) làm lần cập nhật web kế tiếp phải tải lại lớp thư viện nặng, nên gộp vào lúc không vội.

## Các nhánh khác

| Nhánh | Xử lý |
|---|---|
| `deploy_ctu_ver-2.2.1` | Giữ vài tuần để quay về khi cần, rồi xoá |
| `hoanganh_pytorch2tflie` | Bỏ qua, không có gì cần gộp |
| `experiment/feature-v2`, `feature/vocab-schema-v2`, `son_arrange_repo` | Đã nằm trọn trong `main`, có thể xoá |
| `dependabot/...` | Do Dependabot tạo và tự xoá khi PR đóng. PR nào nhắm `main` (tạo trước khi Dependabot chuyển sang `son_arrange_repo2`) thì **đóng, đừng gộp**: gộp vào `main` làm `main` có commit mà `son_arrange_repo2` thiếu, và CI sẽ từ chối dựng ảnh |
| Các nhánh còn lại | Hỏi người tạo trước khi xoá |
