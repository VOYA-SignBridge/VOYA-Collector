# CHƯƠNG 1 — GIỚI THIỆU

> **Bản viết lại 14/08/2026 — đồng bộ với `docs/00-thesis/LUANVAN_CHUONG2.md`.**
> Toàn bộ phần từ đây đến hết mục 1.7 là văn bản luận văn, chép thẳng vào quyển.
> Phần *Phụ chú cho tác giả* ở cuối tệp **không thuộc quyển**.
>
> **Chép vào Word thì dùng [`PHANGIOITHIEU_BAN_SACH.md`](PHANGIOITHIEU_BAN_SACH.md)** — bản
> đó chỉ có mục 1.1–1.7, đã bỏ khối ghi chú này và toàn bộ phụ chú, công thức đã chuyển sang ký
> tự thường. Sinh lại bằng `python scripts/tach_ban_sach_gioithieu.py` sau mỗi lần sửa tệp này.
>
> Trích dẫn đánh dấu bằng khoá `\cite{}` giống hệt Chương 2. Thân bài có **56 dấu `\cite{}`**
> ứng với **69 lượt tài liệu** (48 tài liệu riêng — một số chỗ chèn nhiều nguồn cùng lúc).
> Tra khoá → tiêu đề ở [`BANG_TRA_TRICH_DAN.md`](BANG_TRA_TRICH_DAN.md).
> Phụ chú A–F còn giữ vài tên khoá cũ để làm bảng đối chiếu — chúng không thuộc quyển.

---

## 1.1 Đặt vấn đề

Ngôn ngữ ký hiệu là ngôn ngữ tự nhiên sử dụng phương thức thị giác – cử chỉ. Một ký hiệu
không chỉ được xác định bởi hình dạng bàn tay mà còn bởi hướng, vị trí và chuyển động; bên
cạnh đó, các thành phần phi thủ công như biểu cảm khuôn mặt, chuyển động đầu và tư thế cơ
thể có thể tham gia biểu đạt nghĩa và chức năng ngữ pháp \cite{liddell_grammar_2003,bragg_sign_2019}.
Tính đồng thời của nhiều kênh biểu đạt làm cho ngôn ngữ ký hiệu vừa là một ngôn ngữ tự
nhiên đầy đủ, vừa là một đối tượng dữ liệu phức tạp hơn hẳn văn bản hay tiếng nói ở cả ba
khâu thu nhận, chú giải và lưu trữ.

Tại Việt Nam, Ngôn ngữ ký hiệu Việt Nam (Vietnamese Sign Language — VSL) giữ vai trò thiết
yếu trong giao tiếp, giáo dục và hoà nhập xã hội của cộng đồng người Điếc. Những tiến bộ
của thị giác máy tính và học sâu đã mở ra một lớp công nghệ hỗ trợ mới, nhưng hiệu quả thực
tế của lớp công nghệ này bị chặn trên bởi một điều kiện nằm ngoài mô hình: **sự sẵn có của
bộ dữ liệu có tổ chức, đủ tính đại diện và dùng lại được**.

Điểm này cần được nói rõ ngay từ đầu vì nó định hình toàn bộ đề tài. Các bộ dữ liệu tham
chiếu như WLASL và AUTSL không chỉ có giá trị ở quy mô, mà ở chỗ chúng mang theo siêu dữ
liệu về lớp ký hiệu, mẫu và người ký — nhờ đó cho phép xây dựng các giao thức đánh giá có ý
nghĩa, chẳng hạn phép chia dữ liệu tách biệt theo nhóm người ký
\cite{li_wlasl_baibao_2020,sincan_autsl_2020}. Nói cách khác, giá trị của một bộ dữ liệu
nghiên cứu không nằm ở số lượng tệp mà ở việc nó có được mô tả đủ để người khác diễn giải
và tái sử dụng hay không. Đây cũng là nội dung của các nguyên tắc FAIR và của hướng tài
liệu hoá bộ dữ liệu \cite{wilkinson_fair_2016,gebru_datasheets_2021}: siêu dữ liệu và nguồn
gốc không phải phần phụ thêm sau khi thu thập, mà là thành phần cấu thành giá trị của dữ
liệu.

So với các ngôn ngữ ký hiệu nhiều tài nguyên, VSL vẫn ở tình trạng thiếu hạ tầng dữ liệu.
Các bộ dữ liệu VSL hiện có phần lớn được xây dựng phục vụ từng đề tài riêng lẻ, với vốn từ
hạn chế và quy ước chú giải do mỗi nhóm tự định nghĩa. Biến thể phương ngữ theo vùng miền
làm phức tạp thêm cả ba khâu thu nhận, chú giải và quản lý, vì nó đòi hỏi khác biệt vùng
miền phải được ghi nhận như **một thuộc tính của dữ liệu** thay vì bị xem mặc nhiên là
nhiễu cần loại bỏ \cite{woodward_sign_2000}. Hệ quả là các bộ dữ liệu VSL khó liên thông
với nhau, và nỗ lực thu thập bị lặp lại nhiều lần trên cùng một vốn từ.

Ở đây cần phân biệt hai loại tài nguyên thường bị gộp làm một. Từ điển Ngôn ngữ ký hiệu
Việt Nam của dự án QIPEDC cung cấp một nguồn tham chiếu chuẩn hoá về vốn từ kèm video mẫu
\cite{bogddt_qipedc_2019}. Đó là **điểm xuất phát
cho danh mục**, không phải một bộ dữ liệu huấn luyện: nó không thay thế tập nhiều mẫu được
thu từ nhiều người ký và nhiều phiên phục vụ nghiên cứu thực nghiệm. Việt Nam đã có chuẩn
từ vựng; cái còn thiếu là **hạ tầng để nhiều đơn vị cùng sinh ra dữ liệu tuân theo chuẩn
đó**.

Thực tiễn thu thập dữ liệu VSL hiện nay chủ yếu dựa vào lưu trữ tệp dùng chung kết hợp quy
ước thư mục. Đây không phải một kiến trúc mà là một cách vận hành thủ công: nó có thể phù
hợp với nhóm nhỏ, nhưng ranh giới tổ chức, siêu dữ liệu, phiên bản và điều kiện sử dụng đều
phụ thuộc vào quy ước của người vận hành thay vì được biểu diễn và kiểm soát bởi lược đồ hệ
thống. Giới hạn trở nên nghiêm trọng khi **nhiều đơn vị độc lập** — một trường chuyên biệt,
một phòng thí nghiệm, một hội người khuyết tật, một nhóm nghiên cứu — muốn cùng khai thác
một nền tảng chung. Khi đó phát sinh một nhóm yêu cầu mà lưu trữ tệp không có khái niệm
tương ứng: ranh giới dữ liệu giữa các đơn vị; kiểm soát truy cập theo phạm vi; hạn mức tài
nguyên trên hạ tầng dùng chung; và điều kiện quản trị đối với dữ liệu gắn với con người.

Đây chính là nhóm mối quan tâm mà **kiến trúc đa thuê bao (multi-tenancy)** được sinh ra để
giải quyết \cite{bezemer_multi-tenant_2010,chong_architecture_2006}: nhiều miền quản trị
độc lập dùng chung một phần hạ tầng hoặc thành phần ứng dụng nhưng vẫn duy trì ranh giới
riêng về dữ liệu, quyền và cấu hình \cite{krebs_architectural_2012}. Trong luận văn này,
mỗi đơn vị sử dụng nền tảng tương ứng với một **tenant** — phạm vi quản trị logic cao nhất
đối với dữ liệu nghiệp vụ, thành viên, quyền truy cập và cấu hình riêng. Cần lưu ý ngay
rằng tenant **không nhất thiết đồng nhất với tư cách pháp nhân của một tổ chức**; đây trước
hết là một ranh giới kỹ thuật và quản trị trong hệ thống, và khái niệm này được định nghĩa
đầy đủ ở Chương 2.

Trong các yêu cầu nêu trên, **cô lập dữ liệu là yêu cầu mà một sai sót đơn lẻ đủ để phá huỷ
giá trị của toàn nền tảng**. Một đơn vị đọc được dữ liệu của đơn vị khác dù chỉ một lần
cũng đủ làm mất niềm tin, và với dữ liệu ghi lại chuyển động cơ thể của những con người cụ
thể, hậu quả không dừng ở uy tín kỹ thuật. Trong khi đó, mô hình lược đồ dùng chung — lựa
chọn phù hợp nhất với ràng buộc hạ tầng của đề tài — đặt phần lớn trách nhiệm cô lập lên
ranh giới **logic** thay vì ranh giới vật lý \cite{aulbach_multi-tenant_2008}. Cách hiện
thực phổ biến là thêm cột phân biệt và yêu cầu mọi truy vấn kèm điều kiện lọc tương ứng.
Cách này đặt bảo đảm an toàn lên **kỷ luật và trí nhớ của lập trình viên**, và điều nguy
hiểm là thất bại của nó không phát ra tín hiệu nào: một truy vấn quên điều kiện lọc vẫn
chạy bình thường, vẫn trả về kết quả, chỉ là trả về nhiều hơn phần được phép.

Giả định "lập trình viên sẽ luôn nhớ" không đứng vững trên thực tế. Khảo sát trên chính mã
nguồn của hệ thống tiền thân được thực hiện trong khuôn khổ đề tài này cho thấy: sau nhiều
đợt phát triển, vẫn tồn tại những hàm truy cập dữ liệu thiếu điều kiện lọc phạm vi mà không
có cơ chế nào phát hiện ra. Đây là một quan sát thực nghiệm, không phải một suy đoán, và nó
dẫn thẳng tới nguyên lý *fail-safe defaults*: trạng thái mặc định của cơ chế bảo vệ phải là
từ chối, và quyền chỉ được cấp khi có điều kiện cho phép tường minh \cite{saltzer_protection_1975}.

Từ những phân tích trên, vấn đề nghiên cứu của đề tài được phát biểu như sau:

> **Làm thế nào để thiết kế và hiện thực một hạ tầng phần mềm dùng chung, cho phép nhiều
> đơn vị độc lập cùng thu nhận và quản lý dữ liệu Ngôn ngữ ký hiệu Việt Nam theo chuẩn
> thống nhất, trong đó ranh giới cô lập giữa các tenant và các điều kiện quản trị dữ liệu
> người tham gia được cưỡng chế bằng cơ chế kiểm thử được, thay vì chỉ dựa vào quy ước lập
> trình?**

Cần nhấn mạnh rằng đây là một bài toán **kỹ thuật phần mềm**. Đề tài không đặt mục tiêu
nâng cao độ chính xác của mô hình nhận dạng ngôn ngữ ký hiệu; đề tài giải quyết điều kiện
tiên quyết đứng trước mô hình — sự tồn tại của một hạ tầng để dữ liệu được sinh ra một cách
chuẩn hoá, có siêu dữ liệu và nguồn gốc, có cơ sở quản trị hợp lệ, và dùng lại được.

---

## 1.2 Lịch sử giải quyết vấn đề

Vấn đề nêu ở mục 1.1 đã được tiếp cận từ nhiều hướng, mỗi hướng phục vụ một giai đoạn khác
nhau của vòng đời dữ liệu và được xây dựng cho những phạm vi quản trị khác nhau. Mục này
trình bày các hướng đó theo trình tự phát triển và chỉ ra khoảng trống còn lại; phân tích
định vị có hệ thống theo hai trục *giai đoạn vòng đời* và *phạm vi quản trị* được trình bày
ở Chương 2.

### 1.2.1 Hướng xây dựng bộ dữ liệu tham chiếu

Hướng tiếp cận lâu đời nhất là xây dựng một bộ dữ liệu quy mô lớn rồi công bố cho cộng
đồng. WLASL và AUTSL là hai đại diện tiêu biểu: quy mô lớn, tổ chức chặt chẽ, kèm mô hình
cơ sở để so sánh \cite{li_wlasl_baibao_2020,sincan_autsl_2020}. Đóng góp quan trọng của hướng
này đối với đề tài không nằm ở bản thân dữ liệu mà ở bài học về siêu dữ liệu: AUTSL sử dụng
các nhóm người ký tách biệt giữa các tập để đánh giá khả năng tổng quát hoá sang người ký
chưa xuất hiện trong huấn luyện \cite{sincan_autsl_2020}, và WLASL cung cấp thông tin về
nhiều người ký cùng các mẫu tương ứng \cite{li_wlasl_baibao_2020}. Điều đó cho thấy **thông
tin người ký là siêu dữ liệu cần thiết ngay từ khâu thu**, vì không thể tái tạo đáng tin cậy
về sau.

Những năm gần đây, hướng này dịch chuyển theo hướng huy động cộng đồng đóng góp thay vì thu
tập trung trong phòng thí nghiệm: ASL Citizen xây dựng bộ dữ liệu từ đóng góp của chính
người dùng ngôn ngữ ký hiệu \cite{desai_asl_2023}, còn PopSign ASL thu dữ liệu qua
điện thoại thông minh của người dùng phổ thông \cite{starner_popsign_2023}. Hai công trình
này chứng minh tính khả thi của mô hình thu nhận phân tán từ cộng đồng — tiền đề mà đề tài
kế thừa.

*Khoảng trống:* kể cả với các nỗ lực huy động cộng đồng, kết quả cuối cùng vẫn là **một sản
phẩm dữ liệu**, sinh ra bởi một chiến dịch thu thập do một nhóm duy nhất tổ chức và vận
hành. Hạ tầng phục vụ chiến dịch đó không được thiết kế để nhiều đơn vị độc lập cùng vận
hành song song với ranh giới dữ liệu, thành viên và cấu hình tách biệt. Khác biệt ở đây là
khác biệt giữa **một chiến dịch thu thập** và **một hạ tầng thu thập dùng chung**.

### 1.2.2 Hướng công cụ chú giải và nền tảng thu thập dữ liệu nghiên cứu

Ở phía công cụ, ELAN là môi trường chú giải đa phương thức được sử dụng rộng rãi trong
nghiên cứu ngôn ngữ \cite{wittenburg_elan_2006}. Loại công cụ này giải quyết tốt thao tác
chú giải, nhưng không mặc nhiên cung cấp mô hình quản trị nhiều tổ chức, vòng đời đồng
thuận hay cơ chế cô lập dữ liệu theo tenant.

Gần với đề tài hơn là lớp **nền tảng thu thập và quản lý dữ liệu nghiên cứu**. REDCap là
một đại diện trưởng thành: thu thập dựa trên biểu mẫu, hỗ trợ nhiều dự án, nghiên cứu đa
điểm, kiểm soát quyền ở cấp dự án và nhật ký kiểm toán \cite{harris_research_2009,harris_redcap_2019}.
REDCap chứng minh rằng các chức năng thu thập, phân quyền và kiểm toán có thể được tích hợp
trong một nền tảng nghiên cứu dùng chung — đây là mô hình tham chiếu gần nhất với
CTU.SignBridge.

*Khoảng trống:* mô hình của REDCap xoay quanh biểu mẫu và dự án nghiên cứu tổng quát. Nó
không đặt tầng danh mục chuyên biệt cho ngôn ngữ, phương ngữ và lớp ký hiệu, cũng không đặt
việc thu nhận dữ liệu thị giác và trích xuất đặc trưng tại máy khách làm một phần trung tâm
của mô hình miền.

### 1.2.3 Hướng kho lưu trữ và công bố dữ liệu nghiên cứu

Dataverse cung cấp cơ chế quản lý bộ dữ liệu, phiên bản, siêu dữ liệu, quyền truy cập và
điều kiện sử dụng; Zenodo cung cấp định danh bền vững, phiên bản, giấy phép và các mức truy
cập cho đối tượng nghiên cứu \cite{crosas_dataverse_2011,cern_openaire_zenodo_2013}. Đây là
những hệ thống trưởng thành về quản trị dữ liệu, và không nên mô tả chúng như thiếu cơ chế
quản trị.

*Khoảng trống:* điểm khác biệt nằm ở **thời điểm và đối tượng được quản trị**. Kho tiếp
nhận một đối tượng nghiên cứu do người nộp cung cấp, tức là quản trị bắt đầu khi dữ liệu đã
hình thành. Nền tảng thu nhận thì phải thiết lập quan hệ giữa chủ thể dữ liệu, cơ sở xử lý,
phiên thu và mẫu **ngay khi dữ liệu được tạo ra**. Những thông tin không được ghi nhận tại
thời điểm đó có thể không tái tạo đáng tin cậy về sau — và đây là ràng buộc không thể khắc
phục bằng cách bổ sung siêu dữ liệu ở giai đoạn công bố.

### 1.2.4 Hướng kiến trúc đa thuê bao và cưỡng chế cô lập

Song song, ngành công nghiệp phần mềm đã giải bài toán "nhiều miền quản trị, một thể hiện
ứng dụng" từ giữa những năm 2000. Chong và Carraro mô tả các mức độ chia sẻ tài nguyên
trong tiến hoá SaaS \cite{chong_architecture_2006}; Bezemer và Zaidman phân tích cái giá
phải trả về bảo trì \cite{bezemer_multi-tenant_2010}; Krebs và cộng sự phân tích các khía
cạnh cô lập liên quan đến dữ liệu, an ninh và hiệu năng \cite{krebs_architectural_2012}.
Aulbach và cộng sự hệ thống hoá các kỹ thuật tổ chức dữ liệu đa thuê bao, trong đó có mô
hình lược đồ dùng chung \cite{aulbach_multi-tenant_2008}. Về kiểm soát truy cập, RBAC là
nền tảng lý thuyết \cite{ferraiolo_proposed_2001,sandhu_role-based_1996}, và biến thể RBAC
có miền cho phép gắn một lần gán vai vào phạm vi hiệu lực tương ứng
\cite{casbin_authors_casbin_2024}.

*Khoảng trống:* các công trình này dừng ở mức mô hình tham chiếu. Chúng chỉ ra *nên cô lập*
và *cô lập theo mô hình nào*, nhưng không quy định **cơ chế cưỡng chế cụ thể khi tầng ứng
dụng viết sai**. Bản thân PostgreSQL cung cấp công cụ cho việc này — Row-Level Security
\cite{postgresql_rls_2026} — song việc áp dụng đúng cơ
chế đó trong một ứng dụng web dùng connection pool kéo theo một loạt ràng buộc về phạm vi
giao dịch và quyền của vai runtime; những ràng buộc này không được ghi trong tài liệu tham
chiếu kiến trúc, và khi bị vi phạm thì hệ thống không báo lỗi. Ngoài ra, các tài liệu về đa
thuê bao không xét tới đặc thù của dữ liệu có chủ thể là con người.

### 1.2.5 Tình hình nghiên cứu trong nước

Ở Việt Nam, các nỗ lực liên quan tập trung vào ba nhóm.

Nhóm thứ nhất là **chuẩn hoá vốn từ ở cấp quốc gia**, tiêu biểu là từ điển QIPEDC
\cite{bogddt_qipedc_2019}. Như đã phân tích ở mục 1.1, đây là một tài nguyên tham chiếu về từ vựng chứ không phải hạ tầng thu thập cộng tác.

Nhóm thứ hai là **các nghiên cứu nhận dạng VSL**, đã có kết quả đáng kể trong vài năm gần
đây: nhận dạng VSL bằng trích xuất đối tượng chuyển động kết hợp học sâu
\cite{pham_vietnamese_2021}; nhận dạng bảng chữ cái VSL trên nền điểm mốc MediaPipe
\cite{tran_vietnamese_2025}; và kiến trúc đa nhánh có cơ chế chú ý chéo cho nhận dạng VSL
\cite{chu_cross-attention_2025}. Điểm chung của cả ba là **mỗi công trình tự thu hoặc tự tổ chức
bộ dữ liệu riêng**, với vốn từ, quy ước nhãn và điều kiện thu khác nhau, nên kết quả giữa
chúng không so sánh trực tiếp được và dữ liệu không kế thừa được cho nghiên cứu sau.

Nhóm thứ ba là **các bộ dữ liệu phục vụ đề tài riêng lẻ**, mà VSL400 là một đại diện gần đây
theo hướng dữ liệu đa góc nhìn ở mức từ \cite{nguyenquoc_multiview_2026}. Các bộ dữ liệu này
minh hoạ chính xác hiện trạng phân mảnh: mỗi bộ dùng một quy ước chú giải riêng, quy mô hạn
chế, và không có cơ chế để bộ sau kế thừa bộ trước.

Nhận định tổng hợp: **nghiên cứu VSL trong nước tập trung gần như hoàn toàn ở phía mô hình,
trong khi phía hạ tầng dữ liệu gần như bỏ trống.** Đây vừa là khoảng trống mà đề tài nhắm
tới, vừa là lý do đề tài chọn đóng góp ở tầng hạ tầng thay vì cạnh tranh về độ chính xác
nhận dạng.

### 1.2.6 Hệ thống tiền thân của đề tài

Đề tài kế thừa trực tiếp một hệ thống tiền thân **đơn tenant** đã được phát triển và vận
hành trước đó, phục vụ thu nhận dữ liệu VSL cho một nhóm sử dụng duy nhất. Hệ thống tiền
thân đã chứng minh tính khả thi của quy trình thu nhận theo điểm mốc tại máy khách, nhưng
**không mang khái niệm nào về phạm vi quản trị**: không có ranh giới dữ liệu, không có vòng
đời thành viên, không có hạn mức tài nguyên, không có cơ chế đồng thuận và quy kết chủ thể,
và danh mục từ vựng được đồng bộ thủ công giữa các bản triển khai.

Toàn bộ phần đa thuê bao — mô hình dữ liệu theo phạm vi quản trị, cơ chế cô lập ở tầng cơ
sở dữ liệu, quản lý danh tính và phân quyền theo phạm vi, cơ chế phiên bản và toàn vẹn tạo
tác nghiên cứu, cùng cơ chế quản trị dữ liệu người tham gia — là nội dung được thiết kế và
hiện thực trong khuôn khổ luận văn này. Ranh giới giữa phần kế thừa và phần đóng góp mới
được trình bày tường minh ở mục 1.6.3.

### 1.2.7 Khoảng trống nghiên cứu

Mỗi hướng nêu trên giải quyết trọn vẹn một phần của bài toán. Bộ dữ liệu tham chiếu là đầu
ra của quá trình thu thập chứ không phải hạ tầng tổ chức quá trình đó; công cụ chú giải
không đặt quản trị nhiều tổ chức làm trọng tâm; nền tảng thu thập nghiên cứu tổng quát
không có tầng danh mục chuyên biệt cho miền ngôn ngữ ký hiệu; kho lưu trữ quản trị đối
tượng đã hình thành thay vì quá trình tạo ra nó; và tài liệu về đa thuê bao không xét đặc
thù dữ liệu gắn với con người.

Khoảng trống mà đề tài hướng tới nằm ở giao của ba yêu cầu: **(1) thu nhận dữ liệu theo
phương thức chuyên biệt của miền ngôn ngữ ký hiệu; (2) quản trị và cô lập nhiều tổ chức
trên hạ tầng dùng chung; và (3) thiết lập quan hệ giữa chủ thể dữ liệu, nguồn gốc, cơ sở xử
lý và phiên bản ngay từ thời điểm thu.**

---

## 1.3 Mục tiêu đề tài

### Mục tiêu tổng quát

Thiết kế, hiện thực và đánh giá **CTU.SignBridge** — một nền tảng web đa thuê bao hỗ trợ
thu nhận, tổ chức và quản trị bộ dữ liệu Ngôn ngữ ký hiệu Việt Nam theo chuẩn thống nhất,
cho phép nhiều đơn vị độc lập cùng vận hành trên một hạ tầng phần mềm dùng chung mà vẫn duy
trì ranh giới riêng về dữ liệu, thành viên, quyền và cấu hình.

### Mục tiêu cụ thể

Sáu mục tiêu chính, mỗi mục tiêu gắn với một tiêu chí đánh giá kiểm chứng được, và một mục
tiêu bổ trợ xuất phát từ đặc thù dữ liệu gắn với con người.

**MT1. Thiết kế kiến trúc và mô hình dữ liệu đa thuê bao** theo cây phạm vi
tenant ⊃ workspace ⊃ project, đồng thời phân biệt được ba phạm vi quản trị dữ liệu: danh
mục và cấu hình hệ thống, dữ liệu dùng chung cộng đồng, và dữ liệu theo tenant.
*Tiêu chí đánh giá:* lược đồ cơ sở dữ liệu biểu diễn được ba phạm vi này bằng các quan hệ
có thể truy vấn, sao cho quyền quản trị hạ tầng không tự tạo ra quyền khai thác dữ liệu; và
cây phạm vi không tự sinh ra kế thừa quyền mà kế thừa phải được khai báo tường minh.

**MT2. Cưỡng chế cô lập tenant ở tầng cơ sở dữ liệu** theo nguyên lý *fail-safe defaults*,
sao cho trạng thái thiếu ngữ cảnh tenant dẫn tới không truy cập được hàng nào thay vì mở
toàn bộ bảng.
*Tiêu chí đánh giá:* kiểm thử **hành vi** chứ không phải kiểm tra siêu dữ liệu — kết nối
bằng chính vai runtime của ứng dụng, đặt tenant A, xác nhận không đọc và không ghi được dữ
liệu của tenant B, đồng thời xác nhận trạng thái thiếu tenant bị từ chối. Vai runtime không
phải superuser, không có `BYPASSRLS` và không đủ quyền DDL để tự thay đổi cơ chế bảo vệ.

**MT3. Xây dựng mô hình quản lý danh tính và kiểm soát truy cập theo phạm vi**, vận hành
theo nguyên tắc mặc định từ chối, có vòng đời phiên và cơ chế xác thực lại cho thao tác
nhạy cảm.
*Tiêu chí đánh giá:* mọi tài nguyên hoặc hành động chưa được khai báo công khai đều không
truy cập được; quan hệ gán vai chứa tối thiểu bộ ba (chủ thể, vai, phạm vi); và hệ thống
phân biệt được "phiên hợp lệ" với "đã chứng minh lại danh tính cho hành động nhạy cảm".

**MT4. Hiện thực quy trình thu nhận tại máy khách và đường ống xử lý bất đồng bộ**, bao gồm
trích xuất điểm mốc phía máy khách, hàng đợi tác vụ, và các bước xử lý hạ nguồn.
*Tiêu chí đánh giá:* tác vụ dài không nằm trên đường đáp ứng HTTP; tác vụ được thiết kế cho
khả năng thực thi nhiều hơn một lần, tức bảo đảm tính luỹ đẳng; và các thuộc tính do máy
khách gửi lên được kiểm tra lại ở phía máy chủ thay vì mặc nhiên xem là bằng chứng chất
lượng.

**MT5. Thiết kế cơ chế phiên bản, toàn vẹn và nguồn gốc cho tạo tác nghiên cứu**, tách trạng
thái làm việc khỏi trạng thái đã công bố.
*Tiêu chí đánh giá:* phiên bản đã công bố là bất biến — thay đổi nội dung tạo phiên bản mới
thay vì ghi đè; bản kê được bảo vệ bằng giá trị băm và chữ ký số, cho phép **phát hiện** sửa
đổi; phía tiêu thụ xử lý lỗi xác minh theo hướng fail-closed thay vì tự động quay về bản
khác mà không báo trạng thái.

**MT6. Đánh giá phần lõi đã hiện thực** trên các phương diện: tính đúng đắn chức năng, cô
lập dữ liệu giữa các tenant, hiệu quả lưu trữ của biểu diễn theo điểm mốc, và đặc tính hiệu
năng của hệ thống.
*Tiêu chí đánh giá:* mỗi phương diện có ít nhất một phép đo hoặc một bộ kiểm thử tương ứng.
Riêng về hiệu năng, luận văn chỉ khẳng định hệ thống **có cơ chế hạn mức tài nguyên theo
tenant**; khẳng định đạt cô lập hiệu năng đầy đủ đòi hỏi thí nghiệm tải riêng và không thuộc
phạm vi đề tài.

**MT7 (bổ trợ). Thiết kế cơ chế quản trị dữ liệu người tham gia**, tách bạch người thực
hiện thao tác thu, người đóng góp dữ liệu và chủ thể được ghi nhận trong mẫu.
*Tiêu chí đánh giá:* quan hệ với chủ thể được ghi nhận **tại thời điểm thu**; bản ghi đồng
thuận liên kết được với chủ thể, văn bản, phiên bản và thời điểm; phiên bản văn bản đã dùng
để thu chấp thuận truy lại được đúng nội dung; và hệ thống phân biệt rõ những mức thu hồi
mà phần mềm cưỡng chế được với những mức phải thực hiện bằng quy trình pháp lý.

---

## 1.4 Đối tượng và phạm vi nghiên cứu

### 1.4.1 Đối tượng nghiên cứu

Đối tượng nghiên cứu là **kiến trúc phần mềm và mô hình dữ liệu của một nền tảng web đa
thuê bao phục vụ thu nhận và quản trị dữ liệu Ngôn ngữ ký hiệu Việt Nam**, gồm năm thành
phần:

1. **Kiến trúc hệ thống** — phân rã hệ thống thành các dịch vụ, ranh giới trách nhiệm giữa
   chúng, và mô hình triển khai container hoá. Cần lưu ý rằng container là ranh giới triển
   khai tiến trình chứ không phải ranh giới tenant \cite{merkel_docker_2014}; cô lập vẫn
   phải được thực hiện ở quản lý danh tính, cơ sở dữ liệu và kho nội dung.
2. **Mô hình dữ liệu đa thuê bao** — thiết kế cơ sở dữ liệu quan hệ biểu diễn cây phạm vi
   tenant ⊃ workspace ⊃ project và ba phạm vi quản trị dữ liệu, kèm sự phân biệt giữa danh
   mục, bộ dữ liệu và tạo tác nghiên cứu.
3. **Cơ chế cô lập tenant** — chính sách Row-Level Security, cách truyền ngữ cảnh tenant
   trong phạm vi giao dịch khi ứng dụng dùng connection pool, và sự phân tách vai sở hữu/di
   trú lược đồ khỏi vai runtime của ứng dụng.
4. **Quy trình thu nhận và xử lý dữ liệu** — từ trích xuất điểm mốc tại máy khách, qua hàng
   đợi tác vụ bất đồng bộ, đến lưu trữ nội dung và siêu dữ liệu, cùng ranh giới tin cậy phát
   sinh khi một phần xử lý nằm ngoài tầm kiểm soát của máy chủ.
5. **Cơ chế phiên bản, toàn vẹn và nguồn gốc** — bản kê, giá trị băm, chữ ký số, xác minh
   fail-closed và chiến lược hợp nhất chỉ bổ sung giữa các bản triển khai.

Đối tượng nghiên cứu **không bao gồm** kiến trúc mô hình nhận dạng hay độ chính xác nhận
dạng. Thành phần trích xuất điểm mốc được sử dụng như **một kỹ thuật thu nhận có sẵn**, và
các mô-đun huấn luyện hoặc nhận dạng được xem là **bên tiêu thụ dữ liệu ở hạ nguồn**.

### 1.4.2 Phạm vi nghiên cứu

Đề tài giới hạn ở khía cạnh **kỹ thuật phần mềm** của việc thiết kế, hiện thực và đánh giá
nền tảng.

#### Phạm vi bao gồm

| # | Nội dung |
|---|---|
| 1 | Thu nhận dữ liệu qua nền tảng với trích xuất điểm mốc bàn tay tại máy khách |
| 2 | Quản lý danh mục từ vựng và phương ngữ, có phiên bản và cơ chế ghim phiên bản cho bộ dữ liệu |
| 3 | Cô lập và phân quyền theo phạm vi tổ chức: Row-Level Security, RBAC theo phạm vi, mặc định từ chối, vòng đời phiên và xác thực lại |
| 4 | Đường ống nhập liệu và xử lý bất đồng bộ, có tính luỹ đẳng và cơ chế xử lý lỗi tạm thời/vĩnh viễn |
| 5 | Quản trị đồng thuận và quy kết chủ thể dữ liệu, gắn với phiên thu và mẫu |
| 6 | Phiên bản và toàn vẹn của tạo tác nghiên cứu: bản kê, băm, chữ ký số, xác minh fail-closed |
| 7 | Hạn mức tài nguyên theo tenant như một cơ chế bảo vệ tài nguyên dùng chung |
| 8 | Nguyên tắc triển khai và di trú hệ thống đang vận hành, tách cấu hình triển khai khỏi cấu hình tenant |
| 9 | Đánh giá: đúng đắn chức năng, cô lập dữ liệu tenant, hiệu quả lưu trữ, đặc tính hiệu năng |

#### Phạm vi loại trừ

| # | Nội dung loại trừ | Lý do |
|---|---|---|
| 1 | Huấn luyện, tối ưu và đánh giá mô hình nhận dạng | Nằm ngoài đối tượng nghiên cứu; mô-đun nhận dạng là bên tiêu thụ dữ liệu hạ nguồn |
| 2 | Phát triển một thuật toán trích xuất điểm mốc mới | Thành phần trích xuất được dùng như kỹ thuật thu nhận có sẵn; luận văn không huấn luyện lại hay tuyên bố cải thiện mô hình điểm mốc |
| 3 | Triển khai phân tán quy mô lớn: điều phối Kubernetes, tự co giãn ngang, sẵn sàng cao | Ràng buộc hạ tầng thực tế của đề tài |
| 4 | Chứng minh cô lập hiệu năng đầy đủ giữa các tenant | Đòi hỏi thí nghiệm tải riêng; luận văn chỉ khẳng định có cơ chế hạn mức |
| 5 | Thu và xử lý tư thế toàn thân cùng biểu cảm khuôn mặt | Các trường dữ liệu được dành sẵn trong lược đồ; đường ống xử lý chưa hiện thực |
| 6 | Tích hợp cổng thanh toán và nghiệp vụ thu tiền | Vòng đời đăng ký có hiện thực nhưng không phát sinh giao dịch tài chính |
| 7 | Tuyên bố tuân thủ pháp lý toàn diện | Luận văn chuyển các yêu cầu liên quan thành ràng buộc kiến trúc; đánh giá tuân thủ đầy đủ còn phụ thuộc quy trình vận hành, nội dung văn bản và vai trò pháp lý của các bên |
| 8 | Tuyên bố đạt một mức conformance WCAG cụ thể | WCAG 2.2 \cite{w3c_wcag22_2023} được dùng làm khung tham chiếu cho yêu cầu giao diện; tuyên bố mức conform đòi hỏi kế hoạch kiểm thử và bằng chứng tương ứng |
| 9 | Nghiên cứu ngôn ngữ học về VSL: xây dựng bộ ký hiệu mới, chuẩn hoá gloss ở cấp ngôn ngữ | Đề tài kế thừa tài nguyên tham chiếu quốc gia, không đặt vấn đề chuẩn hoá ngôn ngữ học |

**Bối cảnh pháp lý.** Hệ thống xử lý dữ liệu gắn với cá nhân tại Việt Nam, nên các yêu cầu
của Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 \cite{quochoi_luat_bvdlcn_2025}
và Nghị định số 356/2025/NĐ-CP \cite{chinhphu_nd356_2025} — cả hai có hiệu lực từ ngày
01/01/2026 — được xem là ràng buộc thiết kế. Cần lưu ý rằng việc dữ liệu đã được chuyển
sang dạng điểm mốc **không đương nhiên đưa nó ra khỏi phạm vi quản trị dữ liệu cá nhân**;
mức độ nhận dạng phải được đánh giá dựa trên khả năng liên kết với cá nhân, dữ liệu phụ trợ
và mục đích xử lý \cite{wp29_anonymisation_2014}.

**Phạm vi không gian và thời gian.** Hệ thống được triển khai và vận hành tại Trường Công
nghệ Thông tin và Truyền thông, Trường Đại học Cần Thơ, trên hạ tầng một máy chủ đơn. Dữ
liệu dùng cho đánh giá là dữ liệu được thu qua chính nền tảng trong quá trình phát triển,
tính đến tháng 8 năm 2026.

---

## 1.5 Nội dung nghiên cứu

### 1.5.1 Quy trình nghiên cứu

Đề tài kết hợp **phát triển hệ thống theo hướng tăng trưởng** với **đánh giá thực nghiệm**.
Lựa chọn này bị quy định bởi một đặc điểm của bối cảnh: đã tồn tại một hệ thống đơn tenant
đang vận hành và đã mang dữ liệu thật. Với hệ thống đã có dữ liệu và người dùng, thay đổi
kiến trúc theo kiểu thay thế toàn bộ trong một lần làm tăng phạm vi rủi ro. Vì vậy kiến
trúc đa thuê bao được đưa vào theo mẫu **Strangler Fig**
\cite{fowler_strangler_2004}: chức năng mới được xây bên cạnh đường cũ,
nghiệp vụ được chuyển dần, và thành phần cũ chỉ được bỏ khi đã được thay thế và kiểm chứng.

Với các cơ chế nhạy cảm, đề tài áp dụng **chế độ song song (shadow mode)**: đường cũ vẫn
quyết định, đường mới tính kết quả để đối chiếu và ghi nhật ký; quyền quyết định chỉ được
chuyển sang cơ chế mới khi sai khác đã được giải thích và kiểm thử đạt yêu cầu. Cách tiếp
cận tăng dần không loại bỏ nhu cầu di trú dữ liệu, rollback và kiểm thử; nó chỉ giới hạn
phạm vi thay đổi tại từng bước.

Quy trình phát triển áp dụng mô hình **lặp và tăng trưởng**, hiện thực bằng **Kanban**
\cite{anderson_kanban_2010,kniberg_kanban_2010}, do ba ràng buộc: một lập trình viên
duy nhất, một thời hạn cố định, và việc mở rộng một hệ thống đang chạy. Mô hình thác nước
không phù hợp vì công việc không diễn ra tuần tự từ số không và yêu cầu tiến hoá đồng thời
với quá trình hiện thực; Scrum không phù hợp vì các vai trò và nghi thức của nó giả định
một đội nhiều người. Nhịp rà soát hằng tuần được duy trì theo tinh thần Scrumban
\cite{ladas_scrumban_2009}. Về kỹ thuật, đề tài tuân theo các thực hành của Extreme
Programming \cite{beck_extreme_2004}: viết kiểm thử trước, tích hợp liên tục, tăng trưởng theo
bước nhỏ. Bằng chứng tuân thủ quy trình là các sản phẩm phụ bất biến có mốc thời gian của
chính công việc — lịch sử phiên bản, các yêu cầu hợp nhất mã và nhật ký kiểm thử — chứ
không phải một bảng Kanban duy trì thủ công.

Quy trình nghiên cứu gồm sáu giai đoạn:

| Giai đoạn | Nội dung | Kết quả |
|---|---|---|
| 1 | Tổng quan tài liệu và phân tích vấn đề | Báo cáo tổng quan các lớp công cụ liên quan; xác định khoảng trống và phát biểu vấn đề |
| 2 | Phân tích yêu cầu | Đặc tả yêu cầu chức năng và phi chức năng; mô hình tác nhân và use case |
| 3 | Thiết kế kiến trúc và cơ sở dữ liệu | Sơ đồ kiến trúc và triển khai, lược đồ quan hệ, đặc tả giao diện lập trình, các bản ghi quyết định kiến trúc |
| 4 | Hiện thực tăng trưởng phần lõi đa thuê bao | Mã nguồn thực thi được; kịch bản di trú lược đồ |
| 5 | Kiểm thử và đánh giá thực nghiệm | Kế hoạch kiểm thử, bộ ca kiểm thử, kết quả đo |
| 6 | Phân tích kết quả và hoàn thiện luận văn | Báo cáo đánh giá; quyển luận văn hoàn chỉnh |

Một đặc điểm phương pháp cần nêu rõ vì nó ảnh hưởng đến cách đọc phần đánh giá: **hệ thống
được phát triển và đánh giá trong khi đang phục vụ dữ liệu thật**, không phải trên một bản
dựng thí nghiệm. Điều này khiến các lỗi phát hiện trong quá trình phát triển là lỗi thật
với hậu quả thật, và một số lỗi đó — được ghi chép và phân tích nguyên nhân gốc — trở thành
luận cứ thực nghiệm cho các quyết định thiết kế được bảo vệ ở Chương 3.

### 1.5.2 Công nghệ sử dụng

Các công nghệ được lựa chọn theo ba tiêu chí: mã nguồn mở, vận hành được trên hạ tầng một
máy chủ đơn, và có cộng đồng đủ lớn để bảo trì lâu dài. Bảng dưới chỉ liệt kê những công
nghệ thực sự hiện diện trong hệ thống.

| Tầng | Công nghệ | Vai trò trong hệ thống |
|---|---|---|
| **Giao diện người dùng** | React, TypeScript, Vite | Ứng dụng một trang |
| | Tailwind CSS | Hệ thiết kế giao diện thống nhất |
| | MediaPipe Hands \cite{lugaresi_mediapipe_2019,zhang_mediapipe_2020} | Trích xuất 21 điểm mốc cho mỗi bàn tay; với tối đa hai bàn tay, số giá trị hình học trên mỗi khung là $21 \times 3 \times 2 = 126$ |
| | Three.js, Recharts | Dựng hình khung xương; biểu đồ thống kê |
| **Máy chủ ứng dụng** | FastAPI (Python) | Giao diện lập trình REST; xác thực; điều phối nghiệp vụ |
| | Uvicorn / Gunicorn | Máy chủ ASGI |
| **Tầng dữ liệu** | PostgreSQL \cite{postgresql_rls_2026} | Siêu dữ liệu; cưỡng chế cô lập tenant bằng Row-Level Security |
| | Redis \cite{redis_ltd_redis_2026} | Môi giới hàng đợi tác vụ; bộ đếm hạn mức; danh sách thu hồi phiên |
| | Hệ tệp cục bộ kết hợp dịch vụ lưu trữ đám mây | Kho nội dung cho tệp đặc trưng và bản ghi nguồn |
| **Xử lý nền** | Celery \cite{celery_contributors_celery_2026} | Hàng đợi tác vụ phân tán cho các bước xử lý hạ nguồn |
| | Celery Beat | Tác vụ định kỳ: đối soát dữ liệu, nhắc kỳ hạn, giám sát tài nguyên |
| **Học máy** | PyTorch, scikit-learn, NumPy | Huấn luyện mô hình nhận dạng trong phạm vi tenant (bên tiêu thụ hạ nguồn) |
| **Phân quyền** | Casbin \cite{casbin_authors_casbin_2024} | Hiện thực RBAC có miền cho mô hình quyền theo phạm vi |
| **An toàn thông tin** | SHA-2 \cite{nist_fips180_4_2015} | Giá trị băm cho bản kê và kiểm tra toàn vẹn nội dung |
| | Ed25519 \cite{bernstein_high-speed_2012,josefsson_edwards-curve_2017} | Chữ ký số cho bản kê phát hành |
| | JWT \cite{jones_json_2015} | Biểu diễn claim cho phiên làm việc |
| | TOTP | Xác thực lại cho thao tác nhạy cảm |
| **Triển khai** | Docker, Docker Compose \cite{merkel_docker_2014} | Container hoá và điều phối dịch vụ trên một nút |
| | Nginx | Cổng vào duy nhất cho cả giao diện và API |
| **Quan trắc** | Prometheus, Grafana, Loki | Thu thập chỉ số; biểu đồ và cảnh báo; tập trung nhật ký |

Ba lựa chọn dưới đây định hình toàn bộ kiến trúc nên cần được giải thích ngay trong phần
giới thiệu.

**Thứ nhất, trích xuất điểm mốc được đặt tại máy khách, và toàn bộ đường hiển thị được dựng
lại từ toạ độ.** Quyết định này phân bố một phần công việc thị giác máy tính ra biên thay vì
tập trung hoàn toàn trên máy chủ. Quan trọng hơn về mặt thiết kế, nó cho phép hệ thống
**không đưa hình ảnh người đóng góp vào bất kỳ đường hiển thị nào**: mọi chế độ xem một
phiên thu — khung xương hai chiều, mô hình ba chiều, và cả bản xem nhẹ dạng video — đều được
dựng lại từ chuỗi toạ độ đã lưu, chứ không phát lại thước phim gốc. Bản xem nhẹ tuy có định
dạng video nhưng là **video tổng hợp**: nó được kết xuất từ chuỗi điểm mốc, không chứa khung
hình nào của người thu. Đây là một tính chất của kiến trúc chứ không phải một quy ước vận
hành, vì đường hiển thị không có sẵn dữ liệu hình ảnh để mà hiển thị.

Tính chất đạt được ở đây được gọi là **không lộ diện**: dữ liệu đi qua đường hiển thị không
mang diện mạo, bối cảnh phòng ốc hay bất kỳ chi tiết hình ảnh nào cho phép một người xem
nhận ra người ký bằng mắt thường. Người xem thấy nhãn ký hiệu và thấy chuyển động của bàn
tay, nhưng không thấy khuôn mặt và không thấy những gì lọt vào khung hình lúc quay. Đây là
cách phát biểu chính xác cho mức bảo vệ mà kiến trúc cung cấp, và cần được phân biệt với hai
khái niệm lân cận:

* **Giảm mức phơi bày ở đường thu và lưu trữ** — với luồng thu trực tiếp, hệ thống có thể
  không truyền và không lưu hình ảnh. Mức tiết kiệm tài nguyên cụ thể phải được đo trong Chương 4 thay vì suy ra bằng lý thuyết.
* **Ẩn danh hoá dữ liệu** theo nghĩa dữ liệu không còn khả năng quy về một cá nhân —
  **không** được tuyên bố, vì hệ thống **cố ý không** theo đuổi tính chất này. Mỗi mẫu giữ
  liên kết tới chủ thể và phiên thu, và chính liên kết đó là điều kiện để thực hiện các
  quyền của chủ thể dữ liệu (mục tiêu MT7). Dữ liệu điểm mốc cũng không đương nhiên là dữ
  liệu ẩn danh: khả năng nhận dạng còn phụ thuộc nội dung, dữ liệu liên kết và bối cảnh sử
  dụng \cite{wp29_anonymisation_2014}. Nói cách khác, an toàn của người đóng góp ở đây
  được bảo đảm bằng **không lộ diện cộng kiểm soát truy cập cộng cơ sở đồng thuận**, chứ
  không bằng việc dữ liệu mất khả năng quy về cá nhân.

Ngoài ra, việc đặt xử lý ở máy khách **dịch chuyển ranh giới tin cậy**: payload đến máy chủ
được tạo trong môi trường không do máy chủ kiểm soát hoàn toàn, nên các thuộc tính do máy
khách gửi lên phải được xem là đầu vào không đáng tin cậy cho tới khi được kiểm tra.

**Thứ hai, cơ chế cô lập được đặt ở hệ quản trị cơ sở dữ liệu.** Row-Level Security cho
phép biến ranh giới tenant từ một *quy ước lập trình* thành một *điều kiện được cơ sở dữ
liệu áp dụng cho mọi truy vấn trên bảng, kể cả những truy vấn được viết sau này mà tác giả
quên lọc* \cite{postgresql_rls_2026}. Đây là lý do
PostgreSQL được chọn, và cũng là lý do hệ thống tách vai sở hữu/di trú lược đồ khỏi vai
runtime của ứng dụng theo nguyên lý đặc quyền tối thiểu \cite{saltzer_protection_1975}.

**Thứ ba, biểu diễn theo điểm mốc là một phép biến đổi có mất mát, và điều đó tạo ra một sự
đánh đổi phải nói rõ.** Biểu diễn chỉ gồm điểm mốc bàn tay không bảo toàn đầy đủ các thành
phần phi thủ công vốn có thể mang thông tin ngôn ngữ
\cite{liddell_grammar_2003,bragg_sign_2019}. Nguyên tắc thiết kế hệ thống dữ
liệu khuyến nghị giữ **bản ghi nguồn** tách khỏi **dữ liệu dẫn xuất**, và đặt các phép biến
đổi có mất mát ở hạ nguồn để có thể tái xử lý khi thuật toán hoặc mục tiêu nghiên cứu thay
đổi \cite{kleppmann_designing_2017}.

Hệ thống áp dụng nguyên tắc này ở **một mức**, không phải mọi mức. Kho bản ghi nguồn lưu
chuỗi toạ độ **trước chuẩn hoá**, tách khỏi chuỗi đã chuẩn hoá dùng làm đầu vào mô hình.
Nhờ đó, khi quy ước chuẩn hoá thay đổi thì dữ liệu cũ vẫn tái xử lý được — và cũng nhờ đó
giao diện dựng lại được hình dạng bàn tay đúng với lúc thu, thay vì hiển thị một bàn tay đã
bị phép chuẩn hoá làm bẹt. Nhưng vì hình ảnh không được giữ lại trong luồng thu trực tiếp,
**không thể trích xuất lại bằng một mô hình điểm mốc khác**. Đây là chỗ hai mục tiêu kéo
ngược chiều nhau: giữ hình ảnh thì tái xử lý được sâu hơn nhưng mất tính không lộ diện; bỏ
hình ảnh thì giữ được tính không lộ diện nhưng chốt lại lựa chọn mô hình trích xuất. Đề tài
chọn vế thứ hai, và tuyên bố lựa chọn đó cùng hệ quả của nó thay vì trình bày như thể đã đạt
cả hai.

### 1.5.3 Công cụ xây dựng và phát triển

| Nhóm | Công cụ | Mục đích sử dụng |
|---|---|---|
| Môi trường soạn thảo | Visual Studio Code; trợ lý lập trình dựa trên mô hình ngôn ngữ lớn | Viết mã, tái cấu trúc, rà soát |
| Quản lý mã nguồn | Git; GitHub (nhánh và yêu cầu hợp nhất) | Quản lý phiên bản; đồng thời là bằng chứng khách quan cho quy trình ở mục 1.5.1 |
| Môi trường vận hành | Docker Desktop; Docker Compose | Dựng lại toàn bộ hệ thống bằng một lệnh; giữ môi trường phát triển gần với môi trường triển khai |
| Kiểm thử phía máy chủ | pytest, chạy trong container trên cùng mạng với các dịch vụ | Kiểm thử đơn vị, tích hợp, và kiểm thử hành vi cô lập tenant dưới đúng vai runtime |
| Kiểm thử phía giao diện | Vitest, Testing Library, jsdom | Kiểm thử thành phần giao diện |
| Kiểm tra chất lượng mã | ESLint; trình biên dịch TypeScript ở chế độ kiểm kiểu | Phát hiện lỗi tĩnh trước khi chạy |
| Cơ sở dữ liệu | `psql`; công cụ vẽ lược đồ | Truy vấn; kiểm chứng chính sách Row-Level Security; vẽ lược đồ quan hệ |
| Kiểm thử giao diện lập trình | Tài liệu OpenAPI do FastAPI sinh; thư viện `httpx` | Thử nghiệm thủ công và kiểm thử tích hợp các điểm cuối |
| Quan trắc trong phát triển | Grafana, Prometheus, Loki | Theo dõi chỉ số và nhật ký trên bản triển khai thật |
| Kiểm chứng triển khai | Kịch bản triển khai và kịch bản kiểm tra độ mới của bản dựng | Xác nhận mã đang chạy đúng là mã vừa được xây dựng |
| Sao lưu và khôi phục | `pg_dump` / `pg_restore` trong dịch vụ sao lưu định kỳ, có chế độ diễn tập khôi phục | Bảo vệ dữ liệu thật trong quá trình phát triển |
| Quản lý tài liệu tham khảo | Zotero, kiểu trích dẫn IEEE | Quản lý danh mục tài liệu tham khảo |

Nhóm **kiểm chứng triển khai** cần giải thích thêm vì nó không phổ biến trong các đề tài
cùng loại. Công cụ này được xây dựng sau một sự cố thực tế: một bản dựng giao diện từng
chạy sau mã nguồn nhiều giờ trong khi toàn bộ container đều báo trạng thái khoẻ mạnh, trang
web tải bình thường và phục vụ mã cũ. Lệnh kiểm tra trạng thái container trả lời câu hỏi
"tiến trình còn sống hay không", chứ không trả lời "đó có đúng là tiến trình vừa được xây
dựng hay không". Đây là minh hoạ cụ thể cho một luận điểm xuyên suốt luận văn, cũng là luận
điểm được phát biểu ở Chương 2 dưới dạng nguyên lý: **một phép kiểm chỉ đọc siêu dữ liệu
chưa chứng minh cơ chế đang hoạt động; phép kiểm có giá trị hơn là kiểm thử hành vi ở đúng
vị trí thực thi.**

---

## 1.6 Những đóng góp chính của đề tài

### 1.6.1 Đóng góp về kiến trúc và kỹ thuật

**Đóng góp 1 — Mô hình cưỡng chế cô lập tenant theo nguyên lý fail-safe defaults, kiểm
chứng được bằng hành vi.** Đây là đóng góp cốt lõi. Mục tiêu thiết kế là: khi ngữ cảnh
tenant chưa được thiết lập, tập hàng truy cập được phải rỗng, chứ không phải toàn bộ bảng.
Mô hình gồm bốn thành phần, mỗi thành phần xử lý một chế độ hỏng khác nhau:

* *Cột phân biệt phạm vi* trên các bảng thuộc phạm vi tenant — cần thiết, nhưng bản thân nó
  chỉ là dữ liệu định danh chứ chưa phải ranh giới.
* *Chính sách Row-Level Security* với `USING` và `WITH CHECK`, kiểm soát cả việc đọc dữ liệu
  ngoài phạm vi lẫn việc ghi dữ liệu sang phạm vi không hợp lệ. Ngữ cảnh tenant được đọc
  theo cách có thể trả về giá trị rỗng khi chưa thiết lập, nhờ đó biểu thức chính sách không
  thể trở thành đúng và trạng thái thiếu ngữ cảnh trở thành trạng thái từ chối.
* *Ngữ cảnh có vòng đời trùng với đơn vị giao dịch*, thay vì lưu ở phạm vi phiên. Đây là
  thành phần chống lại một chế độ hỏng đặc thù của ứng dụng web dùng connection pool: nếu
  ngữ cảnh được lưu ở phạm vi phiên trên một kết nối tái sử dụng, kết nối có thể mang giá
  trị của yêu cầu trước sang yêu cầu sau. Cách tổ chức này phù hợp với nguyên lý *complete
  mediation*: mỗi đơn vị truy cập được đánh giá trong ngữ cảnh của chính nó thay vì thừa
  hưởng trạng thái an ninh từ lần sử dụng kết nối trước \cite{saltzer_protection_1975}.
* *Phân tách vai cơ sở dữ liệu* theo đặc quyền tối thiểu: vai runtime không phải superuser,
  không có `BYPASSRLS`, và không đủ quyền thay đổi lược đồ để tự vô hiệu hoá cơ chế bảo vệ
  \cite{postgresql_rls_2026,saltzer_protection_1975}.

Giá trị của đóng góp nằm ở chỗ nó chuyển bảo đảm cô lập từ *kỷ luật lập trình* sang *điều
kiện được cơ sở dữ liệu áp dụng*, nhờ đó phủ cả những truy vấn **chưa được viết**; và ở chỗ
nó được kiểm chứng bằng **kiểm thử hành vi dưới đúng vai runtime** thay vì bằng kiểm tra
siêu dữ liệu chính sách.

**Đóng góp 2 — Cơ chế phiên bản và toàn vẹn cho tạo tác nghiên cứu, áp dụng cho danh mục dữ
liệu miền.** Đề tài hiện thực một cơ chế trong đó một bản triển khai đăng ký giữ khoá riêng
và công bố các phiên bản bất biến của danh mục; các bản triển khai còn lại xác minh chữ ký
trước khi sử dụng và áp dụng chiến lược **hợp nhất chỉ bổ sung**: thêm những đối tượng đã
công bố mà mình chưa có, nhưng không để một bản đồng bộ cũ tự động xoá dữ liệu hiện hữu.
Cách làm này tận dụng tính đơn điệu của trạng thái \cite{hellerstein_keeping_2020}, và lỗi xác
minh được xử lý theo hướng fail-closed thay vì tự động quay về một bản khác mà không báo
trạng thái.

Hai giới hạn được phát biểu tường minh, vì chúng phân định phạm vi của đóng góp. Thứ nhất,
băm và chữ ký cho tính chất **tamper-evident** chứ không phải **tamper-proof**: chúng giúp
thay đổi trái với bản kê bị phát hiện khi xác minh, nhưng không làm cho việc sửa hoặc xoá
tệp trên thiết bị lưu trữ trở thành bất khả thi. Thứ hai, hợp nhất đơn điệu **không phải
giải pháp tổng quát cho mọi bài toán đồng bộ**; nó chỉ áp dụng cho những miền dữ liệu được
thiết kế theo hướng bổ sung hoặc công bố phiên bản mới.

**Đóng góp 3 — Phân tách vai người tham gia và cưỡng chế điều kiện quản trị ngay tại đường
thu.** Đề tài chỉ ra rằng người thực hiện thao tác thu, người đóng góp dữ liệu và chủ thể
được ghi nhận trong mẫu là ba vai có thể không trùng nhau — tình huống phổ biến khi thu tại
cơ sở giáo dục đặc biệt, nơi một cán bộ vận hành thiết bị cho người tham gia thực hiện ký
hiệu. Ba vai này được tách ở mức lược đồ, nhờ đó hệ thống trả lời được ba câu hỏi độc lập:
ai thực hiện thao tác kỹ thuật, ai chịu trách nhiệm đưa dữ liệu vào, và dữ liệu ghi nhận
ai. Trên nền đó, đề tài phân biệt bốn lớp cho phép — cơ sở xử lý dữ liệu cá nhân, quyền
đóng góp, giấy phép tái sử dụng, và thoả thuận truy cập — với nguyên tắc rằng giấy phép tái
sử dụng không thay thế được cơ sở hợp pháp để thu thập và xử lý, và không thể cấp nhiều
quyền hơn những quyền mà bên cấp phép thực sự có.

Bản ghi đồng thuận liên kết chủ thể, văn bản, phiên bản và thời điểm, kéo theo yêu cầu lưu
trữ: phiên bản văn bản đã dùng để thu chấp thuận phải truy lại được đúng nội dung. Hệ thống
cũng phân biệt bốn mức xử lý liên quan đến thu hồi và xoá, và **tuyên bố rõ mức nào phần
mềm cưỡng chế được**: nền tảng có thể ngăn một mẫu xuất hiện trong bản phát hành mới, nhưng
không có khả năng kỹ thuật thu hồi một bản sao đã được bên thứ ba tải về trước đó. Đây là
một đóng góp về tính trung thực của cam kết, không chỉ về cơ chế.

**Đóng góp 4 — Phân tách năm câu hỏi kiểm soát thành năm cơ chế độc lập.** Đề tài tách bạch
các câu hỏi thường bị gộp làm một trong hệ thống cùng loại: *chủ thể là ai* (xác thực và
quản lý phiên) — *chủ thể được thực hiện hành động nghiệp vụ nào* (RBAC theo phạm vi) —
*quan hệ dữ liệu này có được phép tồn tại* (ràng buộc khoá và toàn vẹn tham chiếu) — *hàng
dữ liệu nào được chạm tới* (Row-Level Security) — *có cần chứng minh lại danh tính cho thao
tác nhạy cảm* (xác thực lại theo chính sách). Việc phân lớp giúp tránh một lỗi phổ biến:
dùng RBAC để thay cho cô lập tenant, hoặc dùng RLS để thay cho kiểm soát hành động nghiệp
vụ. Một điểm thiết kế đi kèm là cây phạm vi tenant ⊃ workspace ⊃ project **không tự động
tạo ra kế thừa quyền**; kế thừa phải được khai báo bằng policy tường minh, vì phân cấp tài
nguyên và phân cấp vai là hai khái niệm khác nhau.

**Đóng góp 5 — Mở rộng ranh giới cô lập sang tài nguyên nằm ngoài cơ sở dữ liệu.** Row-Level
Security bảo vệ hàng dữ liệu trong PostgreSQL và không tự mở rộng sang kho nội dung. Đề tài
xác định rằng cô lập phải áp dụng cho cả *đường lấy tham chiếu* lẫn *đường đọc nội dung*,
vì nếu siêu dữ liệu được bảo vệ nhưng máy chủ chấp nhận một khoá tệp tuỳ ý và trả nội dung
mà không kiểm phạm vi, ranh giới bị phá vỡ ở tầng lưu trữ dù cơ sở dữ liệu vẫn đúng chính
sách. Thiết kế cũng xử lý bài toán ghi kép giữa hai hệ thống không cùng một giao dịch: thứ
tự ghi xác định trước, trạng thái trung gian an toàn, và đối soát định kỳ để phát hiện đối
tượng mồ côi hoặc tham chiếu hỏng \cite{kleppmann_designing_2017}.

### 1.6.2 Đóng góp về thực tiễn

**Đóng góp 6 — Một nền tảng vận hành thực tế.** Hệ thống được triển khai và đang phục vụ
trên hạ tầng thật, với hệ quan trắc, cơ chế sao lưu – khôi phục và quy trình kiểm chứng
triển khai. Toàn bộ nghiệp vụ được đặc tả qua mô hình tác nhân và use case, làm cơ sở để
tiếp tục phát triển sau khi đề tài kết thúc.

**Đóng góp 7 — Đường hiển thị không lộ diện, cưỡng chế bằng kiến trúc chứ không bằng quy
tắc vận hành.** Trong các hệ thống thu dữ liệu thị giác, việc bảo vệ hình ảnh người tham gia
thường được thực hiện bằng quy tắc vận hành: hạn chế ai được mở tệp, ai được tải về. Quy tắc
loại đó phụ thuộc vào kỷ luật của người vận hành và mất hiệu lực ngay khi có một tài khoản
đặc quyền. Đề tài đưa bảo đảm này xuống tầng kiến trúc: **mọi chế độ xem một phiên thu đều
được dựng lại từ chuỗi toạ độ** — khung xương hai chiều, mô hình ba chiều, và cả chế độ xem
có định dạng video, vốn là video tổng hợp kết xuất từ điểm mốc chứ không phải thước phim
gốc. Hệ quả: người dùng nền tảng, **kể cả biên tập viên và quản trị viên**, không có đường
nào để nhìn thấy diện mạo người ký qua giao diện — không phải vì bị chặn quyền, mà vì dữ
liệu hình ảnh không tham gia vào đường hiển thị.

Đóng góp không nằm ở việc chọn biểu diễn theo điểm mốc, vốn là kỹ thuật đã có, mà ở chỗ
**tính không lộ diện được giữ nguyên xuyên suốt vòng đời dữ liệu** thay vì chỉ tồn tại ở
khâu thu: từ thu nhận, qua lưu trữ, tới mọi giao diện xem lại. Giá trị thứ hai là nó tách
được hai thứ thường bị gộp: *không lộ diện* là tính chất của đường hiển thị và kiểm chứng
được bằng thiết kế, còn *ẩn danh hoá* là tính chất của bản thân dữ liệu mà hệ thống này cố ý
không theo đuổi. Sự phân biệt này không phải để dè dặt câu chữ: một hệ thống tuyên bố dữ
liệu của mình đã ẩn danh sẽ **không thể** đồng thời hứa rằng nó xác định và xử lý được phần
đóng góp của một người khi người đó rút lại đồng thuận. Giữ liên kết tới chủ thể chính là
điều kiện để cơ chế đồng thuận ở đóng góp 3 có ý nghĩa. Vì vậy việc không tuyên bố ẩn danh
là một **lựa chọn thiết kế nhất quán**, không phải một hạn chế — và nó phân biệt đề tài với
các mô tả thường gặp rằng "dữ liệu điểm mốc là dữ liệu vô danh nên không cần quản trị".

**Đóng góp 8 — Một tập bài học kỹ thuật có ghi chép.** Đề tài ghi lại và phân tích nguyên
nhân gốc của các sự cố thực tế gặp phải trong quá trình vận hành, trong đó có ba bài học
khái quát: một phép kiểm chỉ đọc siêu dữ liệu chưa chứng minh cơ chế đang hoạt động ở đúng
vị trí thực thi; một cơ chế fail-closed ở tầng cơ sở dữ liệu vẫn có thể bị tầng ứng dụng
diễn giải sai khi truy vấn được thực hiện *trước khi* ngữ cảnh được xác lập, khiến kết quả
"không có hàng nào" bị hiểu thành "không tồn tại dữ liệu" thay vì "chưa có ngữ cảnh"; và
trạng thái khoẻ mạnh của container không đồng nghĩa với việc hệ thống đang chạy đúng phiên
bản mã nguồn mới nhất. Các bài học này được trình bày trong phần thảo luận thay vì bị lược
bỏ, vì chúng là bằng chứng thực nghiệm cho các quyết định thiết kế nêu ở các đóng góp trên.

### 1.6.3 Ranh giới giữa phần kế thừa và phần đóng góp mới

| Thành phần | Kế thừa từ hệ thống tiền thân | Thiết kế và hiện thực trong luận văn |
|---|---|---|
| Thu nhận theo điểm mốc tại máy khách | Quy trình thu cơ bản, một nhóm sử dụng | Mở rộng theo phạm vi tenant; phiên thu; quy kết chủ thể; kiểm tra lại phía máy chủ các thuộc tính do máy khách gửi |
| Đường ống xử lý bất đồng bộ | Các bước xử lý cơ bản | Tách kho bản ghi nguồn; tính luỹ đẳng; xử lý lỗi tạm thời/vĩnh viễn; đồng bộ theo phạm vi tenant |
| Mô hình dữ liệu | Bảng mẫu và bảng lớp ký hiệu | Cây phạm vi tenant/workspace/project; ba phạm vi quản trị dữ liệu; mặt phẳng phân quyền; mặt phẳng pháp lý |
| Cô lập tenant | Không có | Toàn bộ (đóng góp 1, 5) |
| Danh tính và kiểm soát truy cập | Đăng nhập đơn giản | Toàn bộ mô hình theo phạm vi, vòng đời phiên, xác thực lại (đóng góp 4) |
| Phiên bản và toàn vẹn danh mục | Không có | Toàn bộ (đóng góp 2) |
| Quản trị dữ liệu người tham gia | Không có | Toàn bộ (đóng góp 3) |
| Hạn mức và vòng đời tenant | Không có | Toàn bộ |
| Quan trắc, sao lưu, kiểm chứng triển khai | Không có | Toàn bộ |

---

## 1.7 Bố cục quyển luận văn

Quyển luận văn được tổ chức thành năm chương. Chương hiện tại là chương thứ nhất.

**Chương 1 — Giới thiệu** (chương này) đặt vấn đề nghiên cứu, khảo sát các hướng đã được
tiếp cận và khoảng trống còn lại, phát biểu mục tiêu kèm tiêu chí đánh giá, xác định đối
tượng và phạm vi, trình bày nội dung và phương pháp nghiên cứu, và nêu những đóng góp chính
cùng ranh giới giữa phần kế thừa và phần thực hiện trong luận văn.

**Chương 2 — Cơ sở lý thuyết** trình bày nền tảng lý thuyết của giải pháp qua mười một nội
dung: miền ứng dụng và vị thế của đề tài; kiến trúc SaaS và tính đa thuê bao; phạm vi quản
trị dữ liệu; cưỡng chế cô lập ở tầng cơ sở dữ liệu; quản lý danh tính và kiểm soát truy
cập; thu nhận dữ liệu tại máy khách; xử lý bất đồng bộ và lưu trữ nội dung; vòng đời tạo
tác nghiên cứu gồm phiên bản, toàn vẹn và nguồn gốc; quản trị dữ liệu người tham gia; triển
khai và tiến hoá hệ thống; và phần tổng hợp xác định khoảng trống nghiên cứu. Chương này
chỉ xác lập khái niệm và nguyên lý; mọi quyết định hiện thực cụ thể được dành cho Chương 3.

**Chương 3 — Phân tích và thiết kế hệ thống** là chương trọng tâm. Phần phân tích trình bày
mô hình tác nhân, danh mục use case và đặc tả yêu cầu chức năng, phi chức năng. Phần thiết
kế trình bày kiến trúc tổng thể và mô hình triển khai; thiết kế cơ sở dữ liệu; thiết kế cơ
chế cô lập tenant kèm lý do lựa chọn mô hình tổ chức dữ liệu; thiết kế quản lý danh tính và
phân quyền theo phạm vi; thiết kế danh mục có phiên bản và cơ chế ghim; thiết kế đường ống
xử lý bất đồng bộ; thiết kế cơ chế toàn vẹn và đồng bộ tạo tác nghiên cứu; thiết kế cơ chế
quản trị dữ liệu người tham gia; và phần thiết kế tham chiếu cho những năng lực chưa hiện
thực trong phạm vi đề tài.

**Chương 4 — Hiện thực và đánh giá** trình bày môi trường triển khai, cấu hình các dịch vụ
và cách hiện thực từng mô-đun chức năng, kèm giao diện minh hoạ và các đoạn mã then chốt;
nêu rõ trạng thái hiện thực của từng cơ chế, phân biệt phần đã cưỡng chế trong vận hành với
phần còn ở mức thiết kế. Phần đánh giá trình bày chiến lược và kết quả kiểm thử; kiểm chứng
cô lập dữ liệu giữa các tenant bằng kiểm thử hành vi dưới đúng vai runtime; đo hiệu quả lưu
trữ của biểu diễn theo điểm mốc; đo đặc tính hiệu năng; và bảng đối chiếu từng mục tiêu cụ
thể ở mục 1.3 với mức độ đạt được cùng bằng chứng tương ứng.

**Chương 5 — Kết luận và hướng phát triển** tổng kết các đóng góp, nêu rõ những hạn chế còn
tồn tại của hệ thống và của quá trình nghiên cứu, và đề xuất các hướng phát triển tiếp theo.

Phần **Phụ lục** gồm các bản ghi quyết định kiến trúc, lược đồ quan hệ đầy đủ, đặc tả chi
tiết các use case, và trích đoạn mã của những ca kiểm thử chứng minh tính cô lập dữ liệu
giữa các tenant.

---
---

# PHỤ CHÚ CHO TÁC GIẢ — KHÔNG THUỘC QUYỂN LUẬN VĂN

## A. Rà soát mâu thuẫn với Chương 2 (`docs/00-thesis/LUANVAN_CHUONG2.md`)

Chương 2 bản hoàn chỉnh khác bản thảo trước khá nhiều. Đã đối chiếu từng khẳng định.
**Chín mâu thuẫn tìm thấy, đã sửa hết ở phần giới thiệu:**

| # | Chương 2 nói | Phần giới thiệu từng nói | Đã sửa thành |
|---|---|---|---|
| 1 | §2.6.3, §2.6.5: "landmark **không đương nhiên là dữ liệu ẩn danh**"; §2.9.5 nhắc lại | "loại bỏ luôn ngoại hình của người ký", "người đóng góp giữ được **mức ẩn danh** mà lưu video không bao giờ đạt tới" | **Giảm mức phơi bày**, kèm câu giới hạn tường minh và trích \cite{article29_anonymisation_2014}. Đây là mâu thuẫn nghiêm trọng nhất |
| 2 | §2.3 tiêu đề "**Phạm vi quản trị dữ liệu**"; mở đầu nói rõ "không nhằm đưa ra kết luận pháp lý về **quyền sở hữu**" | "ba mặt phẳng **sở hữu** dữ liệu… **chủ sở hữu** khác nhau" | "ba **phạm vi quản trị** dữ liệu"; bỏ toàn bộ ngôn ngữ sở hữu |
| 3 | Bảng 2-22 liệt kê **năm** câu hỏi kiểm soát (có "chủ thể là ai") | "**bốn** câu hỏi kiểm soát" | Đóng góp 4 chuyển sang **năm** cơ chế, khớp Bảng 2-22 |
| 4 | §2.1.8, Bảng 2-10: lớp công cụ gồm **REDCap, Dataverse, Zenodo** | Mục 2 không hề nhắc ba hệ thống này; thay vào đó dùng OpenML/Git-Theta không có trong Chương 2 | Mục 2 tái cấu trúc theo taxonomy của Chương 2; bỏ OpenML/Git-Theta |
| 5 | §2.2.1: "Tenant **không nhất thiết đồng nhất với tư cách pháp nhân**… trước hết là ranh giới kỹ thuật" | "mỗi tổ chức tham gia nền tảng **tương ứng với** một tenant" | Thêm câu giới hạn đúng theo §2.2.1 |
| 6 | §2.2.1, §2.5.6: cây phạm vi "**không tự sinh ra quyền truy cập**", "không tự động tạo ra kế thừa quyền" | Không nói gì → dễ bị hiểu là có kế thừa | MT1 và đóng góp 4 nêu tường minh: kế thừa phải khai báo bằng policy |
| 7 | §2.2.8: "nếu không thực hiện phép đo thì **chỉ nên khẳng định có cơ chế hạn mức**, không khẳng định đạt performance isolation" | MT6 và phạm vi ghi chung chung "đánh giá hiệu năng" | MT6 nêu rõ giới hạn; thêm dòng loại trừ số 4 |
| 8 | §2.8.7: hợp nhất đơn điệu "**không phải giải pháp tổng quát**"; §2.8.6 phân biệt tamper-evident/tamper-proof | Đóng góp 2 trình bày cơ chế như một bảo đảm chung | Đóng góp 2 phát biểu tường minh **hai giới hạn** |
| 9 | Toàn chương dùng `\cite{key}` | Phần giới thiệu dùng `[n]` | Chuyển toàn bộ sang `\cite{}` với khoá của Chương 2 |

**Sáu chỗ đã kiểm và xác nhận KHÔNG mâu thuẫn** (đừng "sửa" lại):

* **Số chương.** §2.11 kết bằng "cơ sở để **Chương 3** mô tả kiến trúc…" → cấu trúc năm
  chương ở mục 7 vẫn đúng.
* **126 chiều.** §2.6.2 tính $21\times3\times2=126$; phần giới thiệu dùng đúng công thức và
  **không** mô tả đây là tái dựng 3D tuyệt đối (§2.6.2 cảnh báo điều này).
* **Bốn mức thu hồi** (Bảng 2-35) và **bốn lớp cho phép** (Bảng 2-33) là hai bảng khác nhau —
  đóng góp 3 nay nhắc cả hai, không gộp.
* **MediaPipe Hands** là "thành phần thu nhận có sẵn" — phần giới thiệu và mục loại trừ số 2
  phát biểu đúng như §2.6.2.
* **Không có con số "giảm trên 90%"** ở bất kỳ đâu; §2.6.3 yêu cầu đo trong chương thực
  nghiệm, phần giới thiệu tuân thủ.
* **Container ≠ ranh giới tenant** (§2.10.2) — mục 4.1 nay nói rõ điều này.

## A2. Thuật ngữ đã chốt: dùng "không lộ diện", không dùng "ẩn danh"

**Từ đã chọn: "không lộ diện".** Nó nói đúng thứ hệ thống làm được — người xem thấy nhãn ký
hiệu và thấy chuyển động bàn tay, nhưng không thấy khuôn mặt, không thấy bối cảnh phòng ốc,
không thấy bất kỳ chi tiết hình ảnh nào nhận ra được người ký. Đây chính là điều bạn muốn
diễn đạt. Kèm theo là cụm kỹ thuật **"giảm mức phơi bày"**, mượn nguyên văn của Chương 2
§2.6.3 để hai chương dùng chung một thuật ngữ.

**Từ đã loại: "ẩn danh".** Không phải vì hệ thống bảo vệ kém hơn, mà vì trong ngữ cảnh bảo
vệ dữ liệu cá nhân, "ẩn danh" có nghĩa hẹp: *dữ liệu không còn khả năng quy về một cá nhân
bởi bất kỳ ai, bằng bất kỳ phương tiện hợp lý nào*. Hệ thống này **cố ý** không đạt nghĩa
đó, vì mỗi mẫu phải giữ liên kết tới chủ thể để thực hiện được quyền rút đồng thuận. Dùng
từ "ẩn danh" sẽ mâu thuẫn với Chương 2 §2.6.5 (nói thẳng ba lần) và tự phủ định MT7.

Ba cụm dùng được trong quyển, xếp theo mức trang trọng:

| Cụm | Dùng ở đâu |
|---|---|
| **không lộ diện** | thuật ngữ chính, dùng xuyên suốt |
| **giảm mức phơi bày** | khi cần khớp thuật ngữ Chương 2 §2.6.3 |
| *"người xem không nhận ra người ký qua giao diện"* | khi cần diễn giải dài cho người đọc không chuyên |

**Tuyệt đối tránh:** "ẩn danh", "vô danh", "phi định danh", "dữ liệu đã được ẩn danh hoá" —
trừ đúng một chỗ: câu tuyên bố tường minh rằng đề tài **không** khẳng định tính chất đó.

---

### Bằng chứng từ mã nguồn cho tính không lộ diện

Đây là chỗ dễ bị hội đồng hỏi nhất, nên phần này ghi lại đầy đủ những gì đã kiểm.

**Ba tầng khác nhau, đừng gộp:**

| Tầng | Câu hỏi | Hệ thống đạt được? |
|---|---|---|
| Hiển thị | Người xem có nhìn thấy ngoại hình người ký không? | **Không nhìn thấy** — đạt, cưỡng chế bằng kiến trúc |
| Lưu trữ | Hệ thống có giữ hình ảnh gốc không? | Luồng camera: **không**. Luồng tải video: có đường lưu, nhưng bộ dữ liệu hiện tại không dùng |
| Bản chất dữ liệu | Dữ liệu có còn quy về cá nhân được không? | **Còn** — đây là **giả danh**, không phải ẩn danh |

**Bằng chứng cho tầng hiển thị** (kiểm 14/08/2026):

* `backend/app/preview_render.py:273` — `render_sequence_to_mp4(sequence, out_path, fps)`:
  bản xem nhẹ dạng `.mp4` được **kết xuất từ mảng toạ độ**, không phải từ thước phim gốc.
* `backend/app/preview_render.py:408` — `render_preview_for_session()` mô tả pipeline là
  "locate the session's original `.npz` and render its preview" — đầu vào là `.npz`.
* `docs/09-specs/USE_CASE_SPECIFICATION.md`, UC208 bước 4: "The Worker **renders the landmark sequence
  into a video**".
* `frontend/src/pages/LabelDetailPage.tsx:423` — giao diện đã nói đúng điều này với người
  dùng: *"Trình xem chỉ hiển thị đúng dữ liệu tọa độ đã thu (.npz) — không dùng video quay
  gốc, nên danh tính người đóng góp luôn được bảo vệ."*
* Ba chế độ xem trong `LabelDetailPage` — khung xương 2D, mô hình 3D, và "video nhẹ (server)"
  — cả ba đều đọc từ toạ độ.

**Bằng chứng cho tầng lưu trữ:**

* `dataset/raw/` chứa **440 tệp, 100% là `.npz`** — đây là kho *điểm mốc thô chưa chuẩn hoá*,
  không phải kho video. Tên thư mục dễ gây hiểu nhầm.
* `dataset/samples.csv`: **3.860/3.860 mẫu có `source_type = camera`**, không mẫu nào từ
  luồng tải video. `dataset/raw_videos/` chỉ còn 14 KB tệp sổ sách, không chứa video.
* Tuy vậy `backend/app/routers/upload.py:86` (`POST /upload/video`) **có** đường lưu video
  thô vào `dataset/raw_videos/` và mirror lên Google Drive. Năng lực này tồn tại trong mã
  dù bộ dữ liệu hiện tại chưa dùng — **Chương 4 phải nói đúng như vậy**, đừng viết "hệ thống
  không bao giờ lưu video".

**Vì sao vẫn không được gọi là ẩn danh — bốn lý do, xếp theo sức nặng:**

1. **Hệ thống cố ý giữ định danh.** Mỗi dòng trong `samples.csv` mang `signer_id`,
   `auth_user_id`, `session_id`, `user_id`, `tenant_id`. Dữ liệu có định danh trực tiếp đi
   kèm là dữ liệu **giả danh**; hướng dẫn về kỹ thuật ẩn danh phân biệt rõ giả danh với ẩn
   danh thật \cite{article29_anonymisation_2014}. Không hiển thị một trường không làm trường
   đó biến mất.
2. **Ẩn danh sẽ phá huỷ đóng góp mạnh nhất của luận văn.** MT7 hứa rằng khi một người rút
   đồng thuận, hệ thống xác định được những dòng nào là của người đó. Nếu dữ liệu thật sự ẩn
   danh thì lời hứa đó **không thể thực hiện được**. Hai tuyên bố loại trừ nhau; giữ tuyên bố
   ẩn danh là tự bắn vào Chương 3 mục quản trị dữ liệu người tham gia.
3. **Chính động học bàn tay mang thông tin định danh.** Đây là lý do tồn tại của phép chia
   dữ liệu tách biệt theo người ký: nếu chuỗi toạ độ không mang dấu vết cá nhân thì mô hình
   đã không "học thuộc" người ký, và AUTSL đã không cần nhóm người ký tách biệt giữa các tập
   \cite{sincan_autsl_2020}. Mục 2.1 của phần giới thiệu dùng chính lập luận này — nên không
   thể quay lại nói rằng cùng dữ liệu đó là vô danh.
4. **Chương 2 §2.6.3, §2.6.5 và §2.9.5 phát biểu thẳng điều này ba lần.** Phần giới thiệu mà
   nói ngược lại thì mâu thuẫn nội bộ quyển.

**Kết luận cho quyển:** phát biểu đúng là *"an toàn của người đóng góp được bảo đảm bằng ba
lớp: đường hiển thị **không lộ diện**, kiểm soát truy cập theo phạm vi, và cơ sở đồng thuận
có phiên bản"* — **không** phải *"dữ liệu đã được ẩn danh"*. Cách phát biểu này mạnh hơn, vì
nó đúng và kiểm chứng được bằng mã nguồn; còn tuyên bố ẩn danh thì vừa sai vừa không bảo vệ
được trước một câu hỏi phản biện.

### Phát hiện thêm: kho `raw` là điểm mốc, không phải video

Kiểm ngày 14/08 trên `backend/app/dataset_samples.py:281` (`load_display_sequence`) và
`dataset/raw/`:

* Kho bản ghi nguồn lưu **chuỗi toạ độ trước chuẩn hoá** (`landmarks_raw`), tách khỏi chuỗi
  đã chuẩn hoá (`sequence`) dùng làm đầu vào mô hình. Không có tệp hình ảnh nào.
* Phép chuẩn hoá làm mất hai thứ **không khôi phục được** từ `sequence`: vị trí tương đối
  giữa hai bàn tay (cả hai cổ tay bị đưa về gốc toạ độ — khoảng cách đo được là đúng 0.0000
  ở `sequence` so với 0,026–0,343 ở `landmarks_raw`), và tỉ lệ chiều sâu (z không được nhân
  theo x,y nên bàn tay dựng ra bị bẹt). Đây là lý do trình xem ưu tiên đọc `landmarks_raw`.
* Chỉ **1.674/3.860 mẫu (43,4%)** có `raw_landmarks_available`; phần còn lại phải quay về
  `sequence`, và giao diện báo cho người dùng biết nó đang xem loại nào thay vì lặng lẽ hiển
  thị một bàn tay đã bị làm bẹt như thể là thật.

**Hệ quả cho quyển:** Chương 2 §2.6.6 khuyến nghị giữ bản ghi nguồn để tái xử lý được khi
thuật toán thay đổi. Hệ thống đạt nguyên tắc này **ở mức chuẩn hoá** (đổi quy ước chuẩn hoá
thì dữ liệu cũ vẫn dùng lại được) nhưng **không ở mức trích xuất** (không thể chạy lại bằng
một mô hình điểm mốc khác, vì hình ảnh không còn). Mục 5.2 của phần giới thiệu đã nêu đánh
đổi này tường minh. **Đừng viết Chương 3 hay 4 như thể hệ thống bảo toàn được bản ghi nguồn
đầy đủ** — nó bảo toàn một tầng, không phải mọi tầng, và đó là hệ quả trực tiếp của lựa chọn
không lộ diện.

Cũng nên sửa cách gọi tên: thư mục `dataset/raw/` dễ bị hiểu là kho video thô. Trong quyển
hãy gọi là **"kho toạ độ trước chuẩn hoá"** để không tạo kỳ vọng sai.

## B. Đối chiếu trích dẫn với `SignBridge_Reference.bib` (bản 91 mục, 14/08/2026)

Tệp tham chiếu chính là **`docs/00-thesis/SignBridge_Reference/SignBridge_Reference.bib`** —
**91 mục, không trùng khoá, không trùng DOI, không trùng tiêu đề**. Bộ khoá đã được đặt lại
thủ công thành dạng ngắn đọc được (`quochoi_luat_bvdlcn_2025`, `postgresql_rls_2026`,
`li_wlasl_baibao_2020`…). Đây là bộ khoá **đời thứ ba**; hai đời trước — khoá đặt tay ban đầu
và khoá dài Zotero tự sinh — đều đã bị thay.

Trạng thái sau lượt sửa 14/08 — **đã khép, không còn khoá nào in ra `[?]`**:

| | Số khoá trích | Phân giải được | Còn thiếu |
|---|---|---|---|
| **Thân phần giới thiệu** (mục 1–7) | 48 | 48 | 0 ✓ |
| **Chương 2** | 53 | 53 | 0 ✓ |

Bốn tài liệu từng thiếu (REDCap ×2, Dataverse, Zenodo, WCAG 2.2) đã được nối vào `.bib`
ngày 14/08 — nay **96 mục**.

Phụ chú A–F cố ý còn giữ vài tên khoá cũ để làm bảng đối chiếu; chúng không thuộc quyển nên
không cần sửa.

### B.1 — Phần giới thiệu: xong

Đã áp dụng vào thân bài. Bản đồ đầy đủ (gom cả ba đời khoá) nằm trong
`scripts/doi_khoa_trichdan.py`, chạy lại nhiều lần không hại gì.

### B.2 — Chương 2: 51 lượt đổi khoá — ĐÃ CHẠY ✓

Tài liệu **đã có đủ** trong `.bib`; chỉ sai tên khoá. Không sửa tệp `.bib` — khoá Zotero
phải giữ nguyên để lần xuất sau không lệch tiếp. Chạy:

```
python scripts/doi_khoa_trichdan.py            # chạy thử, không ghi
python scripts/doi_khoa_trichdan.py --ghi --c2 # 51 lượt đổi, tự tạo .bak
```

Ba nhóm đáng chú ý trong đó:

* **Ba mục PostgreSQL nay TÁCH RIÊNG**, không còn gộp một như bản `.bib` cũ:
  `postgresql_rls_2026`, `postgresql_set_2026` và `postgresql_configfunc_2026`. Nghĩa là cách Chương 2 §2.4.6/§2.4.7 trích hai khoá riêng nay **đúng**
  — chỉ cần đổi tên. Ghi chú "gộp làm một" ở lượt rà trước đã hết hiệu lực.
* **Ba mục trước đây thiếu nay đã có**: `sheffer_json_2020` (RFC 8725),
  `lodderstedt_best_2025` (RFC 9700), `casbin_authors_rbac_2026` (RBAC with Domains).
* **Xung đột NIST SP 800-63B đã tự giải quyết.** `.bib` mới có `nist_sp800_63b_2025`
  (bản 2025) và **đã gỡ** `grassi_digital_2017` (bản 2017). Vậy câu *"SP 800-63B-4"* ở
  §2.5.8 nay khớp nguồn — không phải sửa câu chữ nữa, chỉ đổi khoá.

### B.3 — Bốn tài liệu từng thiếu — ĐÃ NỐI VÀO `.bib` ✓

Cả hai chương đều trích, và đây là chỗ duy nhất còn in ra `[?]`.

| Khoá | Tài liệu | Đỡ luận điểm nào |
|---|---|---|
| `harris_research_2009` | REDCap — Harris và cs., *J Biomed Inform* 42(2), 2009. DOI `10.1016/j.jbi.2008.08.010` | §2.1.8 lớp "nền tảng thu thập dữ liệu nghiên cứu"; GT mục 2 |
| `harris_redcap_2019` | REDCap consortium — *J Biomed Inform* 95, 2019. DOI `10.1016/j.jbi.2019.103208` | như trên |
| `crosas_dataverse_2011` | The Dataverse Network — *D-Lib Magazine* 17(1/2), 2011. DOI `10.1045/january2011-crosas` | §2.1.8 lớp "kho lưu trữ và công bố"; §2.11 định vị |
| `cern_openaire_zenodo_2013` | Zenodo — CERN/OpenAIRE. DOI `10.25495/7GXK-RD71` | như trên |
| `w3c_wcag22_2023` | WCAG 2.2, W3C Recommendation 05/10/2023 | §2.9 và GT mục 5.2 — khung tham chiếu giao diện |

Bỏ REDCap/Dataverse/Zenodo thì §2.1.8 mất hẳn hai trong bốn lớp công cụ, và đoạn định vị ở
§2.11 (*"kho tiếp nhận đối tượng đã hình thành, nền tảng thu thập phải thiết lập quan hệ
subject–session–sample ngay khi dữ liệu sinh ra"*) không còn đối tượng để so. Đây là lập luận
"khoảng trống" chính của đề tài, nên **thêm bốn mục này quan trọng hơn mọi việc còn lại ở phụ
chú B**. Bỏ WCAG thì mục "không tuyên bố mức conformance" mất chỗ dựa.

### B.4 — Bốn cặp dễ trích nhầm (bẫy đã được vô hiệu hoá)

Bốn cặp dưới đây là **cùng tác giả / cùng chủ đề nhưng khác tài liệu**. Trích nhầm sẽ in ra
**đúng định dạng nhưng sai nguồn** — không công cụ nào bắt được. Bộ khoá mới đã đặt tên sao
cho nhìn là phân biệt được, nên bẫy này coi như đã xử lý; giữ bảng để đối chiếu khi viết
Chương 3–5:

| Khoá | Là tài liệu gì | Cặp đôi của nó |
|---|---|---|
| `quochoi_luat_bvdlcn_2025` | Luật BVDLCN **91/2025/QH15** | `quochoi_luat_shtt_2025` (131/2025) · `quochoi_luat_dulieu_2024` (60/2024) |
| `chinhphu_nd356_2025` | Nghị định **356/2025/NĐ-CP** | `chinhphu_nd165_2025` (165/2025) |
| `nguyenquoc_multiview_2026` | **Bài bộ dữ liệu** VSL đa góc nhìn mức từ | `nguyenquoc_vsl400_dua_2026` = bản *thoả thuận sử dụng* |
| `li_wlasl_baibao_2020` | **Bài báo** WLASL | `li_wlasl_giayphep_2020` = *điều khoản giấy phép* |

### B.5 — Quyển soạn trên Word: `.bib` KHÔNG còn điều khiển gì

Quyết định 14/08: **soạn trên Word, bỏ LaTeX.** Điều đó lật ngược phần lớn phụ chú B ở trên.

Word chèn trích dẫn bằng **plugin Zotero** (`Ctrl+Alt+C`, style **IEEE**) và tự sinh danh
mục. Nó đọc **thư viện Zotero**, không đọc tệp `.bib`. Kéo theo:

* **Khoá trích dẫn không còn quan trọng.** Hộp *Add/Edit Citation* tìm theo **tiêu đề**.
  Khoá trong `.bib` đổi mỗi lần xuất lại từ Zotero — đã đổi ba lần trong hai ngày — và
  chuyện đó nay vô hại. Khoá chỉ còn là nhãn nội bộ của bản thảo markdown.
* **Ngày truy cập phải nằm ở trường `Accessed` của mục trong Zotero**, không phải ở `note`
  hay `annote` của `.bib`. `ieee.csl` in ra từ trường đó. Đã điền cho **31 mục** bằng
  `SignBridge_Reference/dien_ngay_truycap_zotero.js` (Tools → Developer → Run JavaScript).
* Tệp `SignBridge_Reference.bib` giữ lại làm **bản sao đọc được** của thư viện — tiện tra
  cứu và kiểm đếm, không tham gia vào việc dựng quyển.

Cầu nối giữa bản thảo và Word là [`BANG_TRA_TRICH_DAN.md`](BANG_TRA_TRICH_DAN.md): khoá →
tiêu đề, kèm số lượt xuất hiện ở mỗi chương để đếm xem đã chèn hết chưa (**69 lượt** ở phần
giới thiệu, **109 lượt** ở Chương 2). Sinh lại bằng `python scripts/sinh_bang_tra_trichdan.py`.

### B.6 — Mục có trong thư viện nhưng chưa chương nào trích (33)

Phần lớn là tài liệu giấy phép/quản trị dữ liệu (`cc_*`, `spdx_*`, `carroll_care_2020`,
`microsoft_computational_nodate`, `physionet_giayphep_nodate`) và các bộ dữ liệu SLR
(`duarte_how2sign_2021`, `selvaraj_openhands_2022`, `hu_signbert_2021`, `jiang_skeleton_2021`,
`lee_human_2023`, `sincan_chalearn_2021`, `gruber_mutual_2021`) — nhiều khả năng dành cho
Chương 3–5, nên **không xoá**. Word chỉ đưa vào danh mục những mục thật sự được chèn, nên để
đó vô hại; danh sách đầy đủ ở cuối `BANG_TRA_TRICH_DAN.md`.

### B.7 — Ba tệp `.bib` cũ nên ngừng dùng

`docs/proposal_references.bib` (29 mục, khoá kiểu `ref01_mediapipe`, **đã xoá khỏi cây làm việc**),
`Extra_docs/90-research/LuanVan_LaTeX/references.bib` và
`Extra_docs/90-research/References_Train_Model/training_references.bib` đều thuộc bộ khung
LaTeX đã bỏ. Đừng nhập chúng vào Zotero — sẽ sinh mục trùng cho cùng một tài liệu, và trong
Word hai mục trùng sẽ mang hai số khác nhau trong danh mục.

## C. Số liệu đã kiểm chứng trên mã nguồn (13/08/2026)

Dùng cho Chương 3, 4, 5. Phần giới thiệu cố ý không chứa các con số này.

| Hạng mục | Số | Cách kiểm |
|---|---|---|
| Mã backend | 56.812 dòng Python, 161 tệp | `backend/app/` |
| Mã frontend | 46.437 dòng TS/TSX, 217 tệp | `frontend/src/` |
| Tệp kiểm thử backend | 115 | `backend/tests/` |
| Điểm cuối API | 210 trên 28 router | đếm decorator `@router.<method>` |
| Bảng CSDL đang chạy | 56 (+1 view `tenant_members`) | `CREATE TABLE IF NOT EXISTS` trong `backend/app/storage/` |
| Bảng có chính sách RLS | 27 | `RLS_TABLES` — `backend/app/storage/rls.py` |
| Quyền / vai | 63 / 13 | `catalog.py` |
| Use case đã đặc tả | 75 (10 tác nhân người, 6 tác nhân hệ thống) | `docs/09-specs/USE_CASE_SPECIFICATION.md` |
| Dịch vụ container | 15 | `docker-compose.yml` |
| Mẫu đã thu | 3.860 thuộc 60 lớp | `dataset/samples.csv` |
| Phân bố phương ngữ | bảng chữ cái 2.487 · hoa-đề 830 · common 363 · Cần Thơ 109 · spa 71 | như trên |
| Tệp đặc trưng trên đĩa | 3.871 · 146,0 MB | `scripts/do_hieu_qua_luu_tru.py` |
| **Chi phí biểu diễn điểm mốc** | **298,4 byte/khung · 8,74 KB/giây thu** | như trên — xem [`DO_HIEU_QUA_LUU_TRU.md`](DO_HIEU_QUA_LUU_TRU.md) |
| Bản sao thừa trong kho đặc trưng | 42,2 MB = 28,9% (`landmarks_normalized` ≡ `sequence`) | như trên, đối chiếu CRC-32 từng mảng |
| **Tỉ lệ video / điểm mốc** | **≈ 25×, tiết kiệm 96,0%** | 40 cặp QIPEDC, lọc phát hiện ≥90% — `scripts/do_video_vs_diemmoc.py` |
| Bitrate video QIPEDC (đo) | 1,22 Mbps · 1280×720 · trung vị 4,22 s | như trên |
| MediaPipe bắt được tay — **trong đoạn có ký hiệu** | trung vị 98,3% (150 video) | `scripts/do_doan_ky_hieu.py` |
| Phần thời lượng video QIPEDC thực sự có ký hiệu | trung vị 64,7%; 52/150 video không có đoạn nghỉ | như trên |
| Nền tảng tự thu: khung có ít nhất một bàn tay | **100%** trên 1.997 mẫu có mặt nạ | `frame_valid_mask` trong `dataset/features/` |

## D. Tám việc phải làm trước khi nộp

1. ~~**Dọn bản thảo Chương 2 cũ.**~~ ✓ Xong — `LUANVAN_CHUONG2_BANTHAO.md` không còn trong
   cây làm việc; bản hoàn chỉnh nằm ở `docs/00-thesis/LUANVAN_CHUONG2.md`.
2. **Thêm bốn tài liệu ở B.3 vào Zotero** (REDCap ×2, Dataverse, Zenodo, WCAG 2.2) — đều có
   DOI nên nhập bằng DOI là xong. Rồi **đổi 28 khoá của Chương 2** (B.2). Sau hai bước này
   toàn quyển phân giải 100%.
3. ~~**Đo hiệu quả lưu trữ.**~~ ✓ **Xong cả hai phía** —
   [`DO_HIEU_QUA_LUU_TRU.md`](DO_HIEU_QUA_LUU_TRU.md): biểu diễn tốn 298,4 byte/khung
   (8,74 KB/giây thu) trên 3.871 mẫu, và so ghép cặp với 40 video QIPEDC cho **≈25×, tiết
   kiệm 96,0%**. Con số "90%" và "99,1%" của các bản nháp cũ **đã bị loại**.
   **Khi viết phải kèm hai câu giới hạn:** video QIPEDC là bản studio 1280×720 chứ không phải
   webcam của nền tảng; và tỉ lệ phải lọc theo mẫu có phát hiện bàn tay ≥90%, nếu không thành
   45× do khung rỗng nén gần như miễn phí.
4. **Sửa bản sao thừa trong kho đặc trưng.** Phép đo ở mục 3 phát hiện `landmarks_normalized`
   trùng byte-for-byte với `sequence` ở cả 2.437 tệp — 42,2 MB, 28,9% kho. Tìm chỗ ghi cả hai
   tên rồi bỏ một; **phải di trú 2.437 tệp cũ cùng lúc**, sửa mỗi đường ghi sẽ tạo bố cục thứ
   tư. Nếu không kịp sửa thì vẫn phải **nêu trong Chương 4** như một khiếm khuyết đã biết —
   nó là bằng chứng cho thấy phép đo có giá trị phát hiện, không phải điểm trừ.
5. **Vẽ lại ERD** — 56 bảng, không phải 44. `docs/02-data/db/schema_erd.sql` đã cũ.
6. **Chạy lại toàn bộ kiểm thử** bằng `scripts/run_tests.sh` và ghi số mới.
7. **Trích xuất bằng chứng cô lập** — chọn 3–5 ca kiểm thử **hành vi dưới vai runtime** (đúng
   dạng §2.4.8 yêu cầu), đưa mã vào Chương 4 và Phụ lục.
8. **Viết phần phân tích của Chương 3** — 10 tác nhân, 75 use case, yêu cầu chức năng và phi
   chức năng. Nội dung không được trùng Chương 1: Chương 1 nói *vì sao cần*, Chương 3 nói
   *cần cụ thể những gì*.

## E. Bốn tuyên bố cần xác minh trước khi in

1. **Khảo sát với các bên liên quan ở Cần Thơ.** Bản nháp tiếng Anh cũ nêu "khảo sát sơ bộ
   với 3 nhóm nghiên cứu và 5 tình nguyện viên". Phần giới thiệu này **cố ý không dùng**
   tuyên bố đó. Nếu các buổi làm việc thật sự diễn ra, bổ sung vào mục 5.1 kèm hình thức và
   thời điểm cụ thể — đó là điểm cộng lớn.
2. **Ba hàm thiếu điều kiện lọc.** Mục 1 dựa vào quan sát này. Đã xác nhận ngày 13/08 trong
   `backend/app/storage/metadata_db.py`. Kiểm lại trước khi in; nếu đã vá thì đổi sang thì
   quá khứ, **đừng bỏ đoạn** — đây là luận cứ thực nghiệm mạnh nhất cho đóng góp 1.
3. **Bảng 6.3.** Rà lại với lịch sử phiên bản thực tế để không nhận nhầm phần kế thừa thành
   đóng góp mới. Đây là câu hỏi phản biện gần như chắc chắn sẽ có.
4. **Trạng thái Casbin.** Mặt phẳng phân quyền đang chạy **chế độ song song**
   (`AUTHZ_MODE=shadow`): hệ cũ vẫn ra quyết định. Mục 5.1 của phần giới thiệu đã mô tả
   shadow mode như một *phương pháp di trú* nên phát biểu đúng; nhưng **Chương 4 bắt buộc
   phải nói rõ cơ chế nào còn đang ở chế độ này**.

## F. Quy tắc giữ nhất quán khi viết các chương còn lại

1. **Thuật ngữ.** *đa thuê bao* cho tính chất kiến trúc; *tenant / workspace / project* cho
   phạm vi; *ba phạm vi quản trị dữ liệu* (không phải "mặt phẳng sở hữu"); *bản ghi nguồn* vs
   *dữ liệu dẫn xuất*; *danh mục / bộ dữ liệu / tạo tác nghiên cứu* theo §2.3.5.
2. **Bốn khẳng định không được vượt quá Chương 2:** landmark không phải dữ liệu ẩn danh; có
   hạn mức ≠ đạt cô lập hiệu năng; tamper-evident ≠ tamper-proof; hợp nhất đơn điệu không
   tổng quát.
3. **Mức độ hoàn thành.** Chương 2 cố ý không tuyên bố mức độ hiện thực. Chương 4 và 5 phải
   nói rõ, đặc biệt với dữ liệu dùng chung cộng đồng, Casbin và giao diện cấp
   workspace/project.
4. **Trích dẫn.** Toàn quyển dùng `\cite{key}`. Không trộn với `[n]`.
