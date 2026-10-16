# CHƯƠNG 2. CƠ SỞ LÝ THUYẾT

Chương này trình bày cơ sở lý thuyết của giải pháp theo một khuôn lập luận thống nhất: **khái niệm tổng quan → các phương án đã có → so sánh theo tiêu chí → yêu cầu của bài toán → định hướng được chọn → đánh đổi**. Khuôn này bảo đảm mỗi lựa chọn kiến trúc phát sinh từ một yêu cầu đã phát biểu trước đó, chứ không từ sự có sẵn của một công nghệ.

Phạm vi của chương dừng ở các phương án phổ quát và tiêu chí lựa chọn: chương trả lời **vì sao đi theo những định hướng này**, còn **CTU.SignBridge hiện thực chúng bằng cách nào** thuộc Chương 3, và kết quả đo thuộc Chương 4. Chương 2 do đó không phát biểu mức độ hoàn thành của bất kỳ cơ chế nào.

Công thức trong chương có hai vai trò. Phần lớn là **ký hiệu quy ước của luận văn** dùng để phát biểu gọn một phân biệt khái niệm — chẳng hạn \(\text{Dùng chung} \neq \text{Không có phạm vi}\) — và là định nghĩa nội bộ nên không kèm trích dẫn. Số còn lại **phát biểu lại một kết quả đã có nguồn**, chẳng hạn ngữ nghĩa giao nhận hay cấu trúc chữ ký số, và luôn có trích dẫn ở câu dẫn ngay trước. Chương không chứa mã nguồn; cú pháp hiện thực thuộc Chương 3 và các phụ lục kỹ thuật.

Nội dung đi theo tám lớp: đặc trưng dữ liệu và cơ sở mô hình hóa (2.1) → kiến trúc đa thuê bao (2.2) → phạm vi quản trị và chia sẻ (2.3) → an ninh và cô lập (2.4, 2.5) → thu nhận và xử lý (2.6, 2.7) → phiên bản, nguồn gốc và toàn vẹn (2.8) → quản trị người tham gia (2.9) → triển khai, tiến hóa và tổng hợp (2.10, 2.11).

## Thuộc tính chất lượng dùng làm tiêu chí so sánh

Các bảng so sánh trong chương này sử dụng nhiều tiêu chí khác nhau. Để các tiêu chí đó không xuất hiện một cách tùy tiện theo từng bảng, chương xác lập trước một tập thuộc tính chất lượng và lấy tiêu chí so sánh từ tập này khi phù hợp. Tên gọi các thuộc tính dựa trên mô hình chất lượng sản phẩm phần mềm của ISO/IEC 25010 \cite{iso_25010_2023}, bổ sung một số thuộc tính đặc thù của bài toán dữ liệu nghiên cứu; cách dùng thuộc tính chất lượng làm cơ sở cho quyết định kiến trúc theo hướng trình bày trong \cite{bass_software_2021}.

**Bảng 2-1. Các thuộc tính chất lượng dùng làm tiêu chí so sánh trong chương**

| Thuộc tính chất lượng | Ý nghĩa cụ thể trong luận văn | Xuất hiện chủ yếu ở |
|---|---|---|
| An toàn thông tin | Ranh giới giữa các tổ chức; kiểm soát hành động; hành vi khi thiếu ngữ cảnh | 2.2, 2.4, 2.5 |
| Khả năng bảo trì | Chi phí thay đổi lược đồ và mã khi hệ thống tiến hóa | 2.2, 2.7, 2.10 |
| Độ tin cậy | Thử lại, phục hồi, trạng thái thất bại quan sát được | 2.7 |
| Hiệu quả hiệu năng | Dung lượng lưu trữ, chi phí tính toán, độ trễ đường thu | 2.6, 2.7 |
| Khả năng tái lập | Một bộ dữ liệu và không gian nhãn của nó dựng lại được đúng như đã dùng | 2.3, 2.8 |
| Khả năng truy vết và quy trách nhiệm | Truy được ai đã làm gì, trên tài nguyên nào, trong phạm vi nào | 2.5, 2.8, 2.9 |
| Chất lượng dữ liệu | Tính hợp lệ, đầy đủ, nhất quán và duy nhất của mẫu thu được | 2.1, 2.6 |
| Chi phí vận hành | Số đơn vị phải triển khai, giám sát, sao lưu và di trú | 2.2, 2.10 |
| Khả năng tiếp cận | Hệ thống dùng được bởi nhóm người dùng mà nền tảng phục vụ | 2.9 |

*Nguồn: tác giả tổng hợp; tên gọi thuộc tính theo \cite{iso_25010_2023}, cách sử dụng theo \cite{bass_software_2021}. Bốn thuộc tính lấy tên từ tiêu chuẩn — an toàn thông tin, khả năng bảo trì, độ tin cậy, hiệu quả hiệu năng — giữ nguyên tên qua cả hai lần ban hành 2011 và 2023; năm thuộc tính còn lại là bổ sung đặc thù của bài toán dữ liệu nghiên cứu, không thuộc tiêu chuẩn. Luận văn **không** thực hiện một phương pháp đánh giá kiến trúc hình thức; bảng này là khung đặt tên tiêu chí, không phải một quy trình chấm điểm.*

Một nhận xét cần nêu ngay: các thuộc tính trên **xung đột với nhau**, và phần lớn các bảng so sánh trong chương là bảng biểu diễn xung đột đó. Chia sẻ hạ tầng nhiều hơn cải thiện chi phí vận hành nhưng làm tăng yêu cầu an toàn thông tin. Phiên bản bất biến cải thiện khả năng tái lập nhưng tăng chi phí lưu trữ. Trích xuất tại máy khách cải thiện hiệu quả hiệu năng nhưng làm suy giảm mức tin cậy của dữ liệu đầu vào. Vì vậy mỗi lựa chọn trong chương được trình bày kèm thuộc tính bị hy sinh, chứ không được trình bày như một cải thiện thuần túy.

## 2.1. Dữ liệu ngôn ngữ ký hiệu, chất lượng dữ liệu và cơ sở mô hình hóa

Mục này không nhằm trình bày ngôn ngữ học ngôn ngữ ký hiệu. Câu hỏi được đặt ra hẹp hơn và mang tính kỹ thuật: **dữ liệu ngôn ngữ ký hiệu có những đặc trưng gì khiến một nền tảng thu thập và quản lý nó phải được thiết kế khác với một hệ thống tải tệp lên thông thường?** Bốn nhóm đặc trưng ở mục 2.1.1 sinh ra các yêu cầu về siêu dữ liệu (2.1.3) và chất lượng dữ liệu (2.1.4); mục 2.1.5 trình bày cơ sở lý thuyết để chuyển các yêu cầu đó thành một lược đồ cơ sở dữ liệu.

### 2.1.1. Bốn nhóm đặc trưng của dữ liệu ngôn ngữ ký hiệu

**Thứ nhất, ký hiệu là hiện tượng thị giác đa thành phần.** Ngôn ngữ ký hiệu là ngôn ngữ tự nhiên sử dụng phương thức thị giác – cử chỉ. Một ký hiệu không chỉ được xác định bởi hình dạng bàn tay mà còn bởi hướng lòng bàn tay, vị trí thực hiện và chuyển động; bên cạnh đó, các thành phần phi thủ công như biểu cảm khuôn mặt, chuyển động đầu và tư thế cơ thể có thể tham gia biểu đạt nghĩa và chức năng ngữ pháp \cite{liddell_grammar_2003,bragg_sign_2019}. Nhiều kênh biểu đạt cùng hoạt động đồng thời trong một khoảng thời gian ngắn.

Hệ quả kỹ thuật trực tiếp: **một nhãn ký hiệu không phải là toàn bộ dữ liệu**. Mẫu còn gắn với tín hiệu quan sát ban đầu và bối cảnh thu nhận. Nếu hệ thống chỉ lưu cặp (nhãn, tệp đặc trưng), nó đã cam kết trước rằng phép trích chọn đang dùng là phép trích chọn duy nhất mà mọi nghiên cứu hạ nguồn sẽ cần — một cam kết không có cơ sở khi mục tiêu nghiên cứu còn có thể thay đổi.

**Thứ hai, tồn tại biến thể theo vùng và cộng đồng sử dụng.** Ngôn ngữ ký hiệu không đồng nhất trên toàn lãnh thổ. Đối với ngôn ngữ ký hiệu Việt Nam, khác biệt vùng miền cần được ghi nhận như một thuộc tính của dữ liệu thay vì bị xem mặc nhiên là nhiễu cần loại bỏ \cite{woodward_sign_2000}.

Đặc trưng này có hệ quả sâu hơn ba đặc trưng còn lại vì nó chạm trực tiếp vào **định danh của lớp dữ liệu**. Có thể phát biểu quan hệ cần giữ:

\[
\text{Lớp ký hiệu} \neq \text{Phương ngữ} \neq \text{Vùng}.
\]

Hai biểu hiện khác nhau theo vùng của cùng một khái niệm không phải hai lần thu của cùng một lớp, và cũng không phải hai khái niệm không liên quan. Nếu ngôn ngữ, phương ngữ và lớp ký hiệu bị ghép thành một chuỗi nhãn duy nhất, hệ thống mất khả năng trả lời hai câu hỏi khác nhau: *"có bao nhiêu mẫu cho khái niệm này"* và *"có bao nhiêu mẫu cho biến thể vùng này của khái niệm đó"*. Câu hỏi thứ hai là câu hỏi quyết định khi xây dựng tập huấn luyện và tập đánh giá. Vì vậy ba khái niệm phải là ba thực thể tách biệt trong lược đồ, có quan hệ tường minh với nhau — một yêu cầu được đưa về cơ sở lý thuyết mô hình hóa ở mục 2.1.5.

**Thứ ba, tồn tại biến thiên giữa những người ký.** Ngay trong cùng một lớp và cùng một vùng, cách thực hiện giữa các cá nhân vẫn khác nhau về tốc độ, biên độ và chi tiết hình học. Biến thiên này không phải lỗi thu; nó là thuộc tính của hiện tượng được quan sát.

Hệ quả cần được phát biểu theo điều kiện thu, không phát biểu như một mệnh lệnh tuyệt đối. Đối với **thu có kiểm soát** — nơi nền tảng biết ai đang ký và trong phiên nào — quan hệ mẫu–người ký–phiên thu cần được ghi nhận ngay tại đường thu, vì như đoạn dưới sẽ chỉ ra, nó không tái tạo được về sau. Đối với dữ liệu **đã có từ trước** hoặc thu qua đường không xác định được chủ thể, quan hệ ấy có thể khuyết; khi đó mẫu vẫn dùng được cho một số mục đích và không dùng được cho một số mục đích khác. Nói cách khác, đây là một **thuộc tính quyết định phạm vi sử dụng** của mẫu, chứ không phải một điều kiện để mẫu tồn tại:

\[
\text{Phạm vi sử dụng}(m) = f\big(\text{độ đầy đủ của nguồn gốc}(m)\big).
\]

Phân biệt này quan trọng vì nó tách hai loại thiếu sót thường bị gộp: một hệ thống **không ghi** quan hệ đó là khiếm khuyết thiết kế; một tập dữ liệu **không có** quan hệ đó là giới hạn về trạng thái dữ liệu. Hai loại đòi hỏi hai cách xử lý khác nhau, và chỉ loại thứ nhất sửa được bằng cách sửa hệ thống.

Thông tin người ký có ý nghĩa trực tiếp đối với thiết kế giao thức đánh giá. AUTSL, chẳng hạn, sử dụng các nhóm người ký tách biệt giữa các tập dữ liệu để đánh giá khả năng tổng quát hóa sang người ký chưa xuất hiện trong quá trình huấn luyện \cite{sincan_autsl_2020}. WLASL cũng cung cấp thông tin về nhiều người ký và các mẫu tương ứng, qua đó cho phép phân tích dữ liệu theo chủ thể \cite{li_wlasl_baibao_2020}. Vì vậy, danh tính hoặc định danh nghiên cứu của người ký là siêu dữ liệu cần thiết để xây dựng các phép chia dữ liệu phù hợp; không nên suy diễn rằng mọi bộ dữ liệu tham chiếu đều sử dụng cùng một giao thức độc lập người ký.

Nếu quan hệ mẫu–người ký không được ghi nhận, một phép chia độc lập người ký **không thể tái lập được về sau**, kể cả khi dữ liệu vẫn còn nguyên vẹn: thông tin cần thiết để thực hiện phép chia đã không tồn tại trong hệ thống ngay từ đầu.

**Thứ tư, dữ liệu tồn tại ở nhiều mức biểu diễn.** Cùng một lần thu có thể được biểu diễn dưới dạng bản ghi video, chuỗi khung ảnh, chuỗi điểm mốc, hoặc các đặc trưng dẫn xuất tiếp theo:

\[
\text{Video nguồn} \rightarrow \text{Chuỗi khung} \rightarrow \text{Điểm mốc} \rightarrow \text{Đặc trưng dẫn xuất}.
\]

Các mức phía sau thường nhỏ gọn hơn và thuận tiện hơn cho xử lý tự động, nhưng chúng là kết quả của những phép biến đổi thường **có mất mát**. Đặc trưng này là cơ sở cho sự phân biệt trình bày ở mục 2.1.2 và cho toàn bộ lập luận về biểu diễn ở mục 2.6.

**Bảng 2-2. Bốn nhóm đặc trưng dữ liệu và ràng buộc phát sinh đối với nền tảng**

| Nhóm đặc trưng | Biểu hiện | Ràng buộc đối với nền tảng |
|---|---|---|
| Hiện tượng thị giác đa thành phần | Hình dạng, hướng, vị trí, chuyển động, thành phần phi thủ công cùng hoạt động | Nhãn không thay thế được tín hiệu; cần bảo toàn khả năng truy lại bản ghi nguồn khi biểu diễn dẫn xuất có mất mát |
| Biến thể theo vùng và cộng đồng | Cùng khái niệm, khác biểu hiện theo vùng | Tách ngôn ngữ, phương ngữ và lớp ký hiệu thành thực thể riêng; danh mục phải quản lý được phiên bản |
| Biến thiên giữa những người ký | Cùng lớp, cùng vùng, khác cách thực hiện | Ghi nhận người ký và phiên thu ngay tại đường thu; điều kiện để phép chia theo chủ thể tái lập được |
| Nhiều mức biểu diễn | Video → khung → điểm mốc → đặc trưng | Phân biệt bản ghi nguồn và dữ liệu dẫn xuất; ghi nhận quan hệ nguồn gốc giữa hai lớp |

*Nguồn: tác giả tổng hợp từ \cite{liddell_grammar_2003,bragg_sign_2019,woodward_sign_2000,sincan_autsl_2020,li_wlasl_baibao_2020}.*

Ngoài ý nghĩa nghiên cứu, thông tin người ký còn có ý nghĩa quản trị. Khi dữ liệu gắn với một cá nhân có thể xác định, quan hệ giữa mẫu và chủ thể là điều kiện để thực hiện các nghĩa vụ trình bày ở mục 2.9. Do đó, cùng một thuộc tính — người ký — đồng thời phục vụ hai mục tiêu khác nhau: kiểm soát chất lượng nghiên cứu và thực hiện quyền của chủ thể dữ liệu. Hai mục tiêu này độc lập với nhau, nhưng cùng đòi hỏi một quan hệ dữ liệu duy nhất, và quan hệ đó chỉ có thể được thiết lập đáng tin cậy tại thời điểm thu.

### 2.1.2. Dữ liệu nguồn và dữ liệu dẫn xuất

**Ba** khái niệm cần được phân biệt, không phải hai. Gộp hai khái niệm đầu là một nhầm lẫn thường gặp và nó dẫn tới một suy luận sai về nghĩa vụ lưu trữ.

**Tín hiệu nguồn (source signal)** là hiện tượng vật lý được quan sát: chuyển động của người ký trước ống kính. Nó tồn tại độc lập với hệ thống, và mọi thứ hệ thống có được đều là kết quả của một phép ghi nhận áp lên nó.

**Tạo tác nguồn được lưu giữ (retained source artifact)** là bản ghi của tín hiệu ấy mà hệ thống **thực sự giữ lại** — chẳng hạn một tệp video. Đây là một quyết định kiến trúc, không phải một tất yếu.

**Dữ liệu dẫn xuất (derived data)** là dữ liệu được tạo ra bằng một phép biến đổi áp lên tín hiệu nguồn hoặc lên tạo tác nguồn, chẳng hạn chuỗi điểm mốc.

Quan hệ giữa ba khái niệm:

\[
\text{Tín hiệu nguồn} \neq \text{Tạo tác nguồn được lưu giữ} \neq \text{Dữ liệu dẫn xuất}.
\]

Một phép trích xuất có thể quan sát tín hiệu nguồn mà không tạo ra tạo tác nguồn được lưu giữ. Khi phép trích xuất diễn ra tại thiết bị và chỉ dữ liệu dẫn xuất được truyền lên nền tảng, sự tồn tại của mẫu không hàm ý sự tồn tại của video nguồn trong hệ thống. Câu *"mẫu này có video gốc"* khi đó là sai, còn câu *"mẫu này bắt nguồn từ một quan sát thị giác"* vẫn đúng. Hai mệnh đề tách nhau ở đúng chỗ nào trong kiến trúc được trình bày ở mục 2.6.8.

Một biểu diễn dẫn xuất có thể nhỏ hơn nhiều lần và thuận tiện hơn cho xử lý, nhưng **không đương nhiên bảo toàn toàn bộ thông tin của nguồn**. Khi phép biến đổi có mất mát, ba hệ quả phát sinh.

Thứ nhất, biểu diễn dẫn xuất mang theo một **giả định về mục đích sử dụng**. Nó giữ lại những gì phép biến đổi coi là cần thiết cho mục đích tại thời điểm thiết kế. Khi mục đích thay đổi, giả định đó có thể không còn đúng.

Thứ hai, **mất mát là một chiều**. Không tồn tại phép biến đổi ngược để khôi phục thông tin đã bị loại bỏ. Nếu bản ghi nguồn không được giữ, quyết định trích chọn ban đầu trở thành quyết định vĩnh viễn đối với toàn bộ dữ liệu đã thu.

Thứ ba, hệ thống cần duy trì **quan hệ nguồn gốc (provenance)** giữa hai lớp khi nghiệp vụ yêu cầu: mỗi đối tượng dẫn xuất phải truy được về đối tượng nguồn đã sinh ra nó và về phép biến đổi đã được áp dụng. Không có quan hệ này, một tập dữ liệu dẫn xuất trở thành một tập số không giải thích được. Khung khái niệm để mô hình hóa quan hệ này được trình bày ở mục 2.8.5.

Ba hệ quả trên không dẫn tới kết luận rằng mọi hệ thống đều phải lưu bản ghi nguồn. Chúng dẫn tới một kết luận yếu hơn nhưng chặt hơn: **việc có lưu bản ghi nguồn hay không phải là một quyết định kiến trúc tường minh, có lý do và có đánh đổi được phát biểu**, chứ không phải một hệ quả phụ của việc chọn định dạng lưu trữ. Quyết định cụ thể của CTU.SignBridge được trình bày ở mục 2.6 và Chương 3.

> ### ▣ HÌNH 2-1 — Chuỗi biểu diễn từ tín hiệu nguồn đến đặc trưng dẫn xuất
> **Loại:** sơ đồ luồng một chiều · **Công cụ đề nghị:** draw.io
> **Phải thể hiện:** bốn mức biểu diễn xếp theo hàng ngang (bản ghi nguồn → chuỗi khung → điểm mốc → đặc trưng dẫn xuất); mũi tên **một chiều** giữa các mức, có nhãn "phép biến đổi có mất mát"; dưới mỗi mức ghi thông tin **bị loại bỏ** ở bước đó; một mũi tên đứt nét ngược chiều bị gạch chéo, kèm chú "không khôi phục được"; một liên kết nét đứt từ mọi mức dẫn xuất trỏ ngược về bản ghi nguồn, nhãn "quan hệ nguồn gốc phải được lưu".
> **Chú thích dưới hình:** *Hình 2-1: Chuỗi biểu diễn từ tín hiệu nguồn đến đặc trưng dẫn xuất và tính một chiều của phép biến đổi.*

### 2.1.3. Siêu dữ liệu cần thiết cho dữ liệu ngôn ngữ ký hiệu

Từ bốn nhóm đặc trưng ở mục 2.1.1 và sự phân biệt nguồn – dẫn xuất ở mục 2.1.2 có thể suy ra tập siêu dữ liệu tối thiểu. Mỗi dòng trong bảng dưới đây không phải một trường "nên có cho đầy đủ", mà là trường mà **thiếu nó thì một loại câu hỏi nghiên cứu hoặc một nghĩa vụ quản trị trở nên không trả lời được**.

**Bảng 2-3. Siêu dữ liệu tối thiểu và câu hỏi mà mỗi nhóm cho phép trả lời**

| Đặc trưng phát sinh yêu cầu | Siêu dữ liệu cần có | Câu hỏi không trả lời được nếu thiếu |
|---|---|---|
| Biến thể theo vùng | Ngôn ngữ, phương ngữ, vùng | Biến thể vùng nào đang được đại diện trong tập dữ liệu, và với bao nhiêu mẫu? |
| Không gian lớp có cấu trúc | Lớp ký hiệu và quan hệ với phương ngữ | Hai mẫu này thuộc cùng một lớp hay hai biến thể của cùng khái niệm? |
| Biến thiên giữa người ký | Người ký (định danh nghiên cứu) | Phép chia dữ liệu này có độc lập người ký không? |
| Nhiều lần thu, nhiều bối cảnh | Phiên thu, thời điểm, điều kiện thu | Hai mẫu giống nhau bất thường là do trùng lặp hay do cùng một phiên thu? |
| Nhiều mức biểu diễn | Quan hệ nguồn – dẫn xuất, tham số phép biến đổi | Chuỗi số này được sinh ra từ bản ghi nào, bằng phép biến đổi nào? |
| Không gian lớp thay đổi theo thời gian | Phiên bản danh mục được sử dụng | Nhãn của mẫu này ứng với không gian lớp nào tại thời điểm sử dụng? |
| Dữ liệu được chọn vào một tập cụ thể | Tư cách thành viên và phiên bản của bộ dữ liệu | Bộ dữ liệu dùng trong thí nghiệm đó gồm chính xác những mẫu nào? |
| Dữ liệu gắn với cá nhân | Chủ thể dữ liệu, cơ sở xử lý, phạm vi đồng thuận | Mẫu này có được phép xuất hiện trong bản phát hành sắp tới không? |

*Nguồn: tác giả tổng hợp; cột thứ ba là tiêu chí để xác định trường nào là tối thiểu.*

Bảng trên dẫn tới một kết luận định hướng cho toàn bộ chương: trong phạm vi luận văn, **dữ liệu ngôn ngữ ký hiệu được xem là dữ liệu có cấu trúc và có vòng đời, không phải một tập tệp video hoặc tệp đặc trưng**. Bốn nhóm trường cuối bảng — phiên bản danh mục, tư cách thành viên bộ dữ liệu, cơ sở xử lý và phạm vi đồng thuận — không mô tả nội dung của mẫu; chúng mô tả **trạng thái của mẫu trong một vòng đời**. Đó là loại thông tin mà một cây thư mục không biểu diễn được.

### 2.1.4. Chất lượng dữ liệu trong nền tảng thu thập

Nếu đề tài là thu thập và quản lý dữ liệu, thì câu hỏi *"thế nào là một mẫu có chất lượng"* phải được trả lời bằng những chiều mà hệ thống **quản lý được**, chứ không bằng một đánh giá chủ quan. Chất lượng dữ liệu là một khái niệm nhiều chiều và phụ thuộc mục đích sử dụng, chứ không quy về một thuộc tính "đúng/sai" duy nhất \cite{wang_beyond_1996}. Sáu chiều dưới đây được chọn vì mỗi chiều tương ứng với một cơ chế kiểm tra cụ thể trong nền tảng.

**Bảng 2-4. Sáu chiều chất lượng dữ liệu và cơ chế kiểm tra tương ứng**

| Chiều chất lượng | Câu hỏi | Cơ chế kiểm tra khả dĩ |
|---|---|---|
| Tính hợp lệ | Dữ liệu có đúng cấu trúc và thuộc miền giá trị hợp lệ không? | Kiểm tra số chiều và khoảng giá trị; ràng buộc miền; khóa ngoại tới danh mục |
| Tính đầy đủ | Các trường siêu dữ liệu bắt buộc có mặt không? | Ràng buộc `NOT NULL`; kiểm tra ở cổng công bố |
| Tính nhất quán | Các quan hệ có mâu thuẫn nhau không? | Ràng buộc toàn vẹn tham chiếu và toàn vẹn xuyên phạm vi (mục 2.1.5, 2.2.6) |
| Tính duy nhất | Cùng một lần đóng góp có bị ghi thành nhiều mẫu không? | Ràng buộc duy nhất; khóa lũy đẳng (mục 2.7.2) |
| Đầy đủ về nguồn gốc | Có biết mẫu này từ ai, phiên nào, nguồn nào không? | Quan hệ bắt buộc tới người ký và phiên thu tại đường thu |
| Chất lượng thu nhận và biểu diễn | Dữ liệu có đủ ổn định và đầy đủ để dùng được về sau không? | Chỉ số chất lượng tính tự động trên chính dữ liệu; kiểm tra đặc trưng, tách khỏi kiểm tra cấu trúc |

*Nguồn: tác giả tổng hợp; các chiều đặt tên theo hướng nhiều chiều của \cite{wang_beyond_1996}, cơ chế kiểm tra suy ra từ yêu cầu của mục 2.1.3.*

Dòng cuối bảng chứa một phân biệt cần được giữ nghiêm ngặt trong toàn quyển: **hợp lệ về kỹ thuật và được chấp nhận vào bộ dữ liệu là hai trạng thái khác nhau**:

\[
\text{HợpLệVềLượcĐồ} \;\nRightarrow\; \text{ĐủĐiềuKiệnVàoBộDữLiệu}.
\]

Một mẫu có thể đúng số chiều, đủ trường bắt buộc, trỏ tới lớp tồn tại — và vẫn không dùng được vì người ký thực hiện sai ký hiệu, khung hình bị che, hoặc điều kiện thu không đạt.

Hai chiều này khác nhau ở **loại câu hỏi**, không chỉ ở độ khó. Chiều thứ nhất hỏi dữ liệu có đúng hình dạng đã quy ước hay không — trả lời được bằng đối chiếu với lược đồ. Chiều thứ hai hỏi dữ liệu có phản ánh đúng hiện tượng cần ghi hay không. Một phần của chiều thứ hai vẫn đo được tự động từ chính dữ liệu, chẳng hạn tỉ lệ khung thiếu điểm mốc hay mức dao động bất thường của quỹ đạo; phần còn lại — *"ký hiệu này thực hiện đúng chưa"* — thì không.

Điều cần rút ra là hai chiều phải **biểu diễn được tách nhau**, chứ không phải là chiều thứ hai bắt buộc phải do người trả lời. Gộp chúng vào một cờ duy nhất khiến hệ thống hoặc từ chối dữ liệu còn dùng được, hoặc phát hành dữ liệu mà chưa có căn cứ nào về chất lượng. Các cách trả lời chiều thứ hai, cùng ràng buộc mà mỗi cách đặt ra, được phân tích ở mục 2.1.5.

### 2.1.5. Kiểm tra tại thời điểm thu và làm sạch hậu kỳ

Từ sáu chiều trên phát sinh một quyết định kiến trúc: **kiểm tra ở đâu trong vòng đời**.

**Phương án A — làm sạch hậu kỳ.** Thu nhận mọi thứ với ràng buộc tối thiểu, rà soát và làm sạch về sau. Đường thu đơn giản và không từ chối dữ liệu. Nhược điểm quyết định: **siêu dữ liệu đã mất thì không tái tạo được**. Một mẫu thu xong mà không biết người ký là ai sẽ vĩnh viễn không biết, vì thông tin đó chỉ tồn tại ở thời điểm và địa điểm thu.

**Phương án B — kiểm tra tại thời điểm thu.** Ràng buộc được cưỡng chế ngay khi dữ liệu vào hệ thống. Sai sót được phát hiện khi còn sửa được, và một số bất biến được bảo đảm từ đầu. Nhược điểm: đường thu phức tạp hơn, và kiểm tra quá nghiêm có thể từ chối dữ liệu còn giá trị — đặc biệt nguy hiểm trong bài toán này, nơi việc mời một người tham gia đến thu lại không phải thao tác rẻ.

**Phương án C — kết hợp.** Phân loại ràng buộc theo tiêu chí *có tái tạo được về sau hay không*: những gì mất đi là mất vĩnh viễn thì cưỡng chế ngay lúc thu; những gì đánh giá được sau thì để ở một khâu riêng.

**Bảng 2-5. So sánh ba thời điểm kiểm tra chất lượng**

| Tiêu chí | A. Làm sạch hậu kỳ | B. Kiểm tra lúc thu | C. Kết hợp |
|---|---|---|---|
| Phát hiện lỗi sớm | Thấp | Cao | Cao |
| Độ phức tạp của đường thu | Thấp | Cao | Trung bình |
| Bảo vệ siêu dữ liệu không tái tạo được | Kém | Tốt | Tốt |
| Rủi ro từ chối dữ liệu còn giá trị | Thấp | Cao | Thấp |
| Chỗ cho đánh giá của con người | Có | Không đủ | Có, ở khâu riêng |
| Định hướng được chọn | | | **Được chọn** |

*Nguồn: tác giả tổng hợp.*

**Định hướng được chọn và lý do.** Phương án kết hợp phù hợp, với một quy tắc phân loại tường minh: **ràng buộc về cấu trúc và về quản trị được cưỡng chế tại thời điểm thu, còn đánh giá chất lượng mang tính định tính được xử lý ở một khâu tách rời khỏi đường thu**. Tiêu chí phân loại là khả năng tái tạo: quan hệ với người ký, phiên thu và cơ sở xử lý thuộc nhóm thứ nhất vì chúng không dựng lại được; nhận định "ký hiệu này thực hiện chưa chuẩn" thuộc nhóm thứ hai vì nó vẫn đánh giá được từ chính dữ liệu đã lưu.

**Phân biệt cần giữ: hợp lệ về cấu trúc không đồng nghĩa với đúng về ngữ nghĩa.**

\[
\text{Hợp lệ theo lược đồ} \ \neq\ \text{Đúng về ngữ nghĩa} \ \neq\ \text{Được chấp nhận vào một bộ dữ liệu}.
\]

Ba mệnh đề này độc lập với nhau. Một mẫu có thể đủ số khung, đủ chiều đặc trưng, đủ siêu dữ liệu bắt buộc — tức hợp lệ theo lược đồ — mà vẫn ghi lại một ký hiệu thực hiện sai. Ngược lại, một mẫu đúng về ngữ nghĩa vẫn có thể chưa được chấp nhận vào một bộ dữ liệu cụ thể vì lý do phạm vi sử dụng chứ không vì chất lượng.

**Điều luận văn KHÔNG kết luận từ phân biệt này.** Việc ba mệnh đề tách nhau về mặt khái niệm không kéo theo rằng hệ thống phải có một quy trình phê duyệt thủ công. Nó chỉ nói rằng nếu chỉ có kiểm tra cấu trúc thì mệnh đề thứ hai chưa được trả lời. Các cách trả lời khả dĩ gồm: một khâu duyệt do người thực hiện; một chỉ số chất lượng tự động dùng làm tiêu chí lọc ở khâu chọn mẫu; hoặc chuyển câu hỏi xuống hạ nguồn cho bên xây dựng bộ dữ liệu. Ba cách có chi phí vận hành và mức bảo đảm khác nhau, và **việc chọn cách nào là quyết định của Chương 3**, không phải một kết luận của Chương 2.

**Đánh đổi.** Bất kỳ cách nào trong ba cách trên cũng buộc hệ thống biểu diễn được một trạng thái trung gian — "hợp lệ về cấu trúc, chưa kết luận về ngữ nghĩa" — mà một mô hình chỉ có một cờ đúng/sai không diễn đạt được. Đây là ràng buộc mà mô hình trạng thái của mẫu phải đáp ứng, độc lập với việc khâu đánh giá ngữ nghĩa được hiện thực bằng cơ chế nào.

### 2.1.6. Cơ sở mô hình hóa dữ liệu quan hệ

Các mục trước xác định *dữ liệu nào phải có*. Mục này trình bày cơ sở lý thuyết để chuyển các yêu cầu đó thành một lược đồ cơ sở dữ liệu — nền cho mô hình dữ liệu ở Chương 3 và Phụ lục A.

#### Mô hình thực thể – quan hệ và bốn khái niệm nền

Trước khi phân biệt các mức trừu tượng, cần cố định bốn khái niệm mà mọi mức đều dùng tới. Mô hình thực thể – quan hệ được đề xuất nhằm mô tả dữ liệu bằng những khái niệm gần với nhận thức về miền ứng dụng, thay vì bằng cấu trúc lưu trữ \cite{chen_entity-relationship_1976}.

**Thực thể (entity)** là một loại đối tượng mà miền ứng dụng cần phân biệt và lưu thông tin về nó — người ký, phiên thu, lớp ký hiệu, mẫu. Điều quan trọng không phải định nghĩa mà tiêu chí nhận biết: một khái niệm xứng đáng là thực thể riêng khi nó có **định danh độc lập** và có thuộc tính của riêng nó, chứ không chỉ khi nó xuất hiện thường xuyên trong lời mô tả nghiệp vụ.

**Thuộc tính (attribute)** là một tính chất của thực thể. Ranh giới giữa "một thuộc tính" và "một thực thể riêng" là quyết định thiết kế quan trọng nhất ở mức khái niệm: khi một tính chất bắt đầu có tính chất của chính nó, nó đã trở thành thực thể — đây chính là lập luận dẫn tới việc tách vùng miền ra khỏi bảng mẫu ở phần sau.

**Quan hệ (relationship)** là một liên hệ có nghĩa giữa các thực thể. Quan hệ cũng có thể mang thuộc tính của riêng nó, và khi điều đó xảy ra, mô hình quan hệ ở mức logic biểu diễn nó bằng một thực thể liên kết.

**Lực lượng (cardinality)** xác định mỗi thực thể ở một phía tham gia vào bao nhiêu thể hiện của quan hệ — một–một, một–nhiều, nhiều–nhiều — cùng với **tính tùy chọn**: sự tham gia là bắt buộc hay có thể vắng. Lực lượng là nơi phần lớn ràng buộc nghiệp vụ được phát biểu, và cũng là nơi một mô hình dễ nói mạnh hơn thực tế nhất: khẳng định "mỗi mẫu **phải** thuộc một phiên thu" là một ràng buộc lực lượng, và nó chỉ đúng nếu mọi đường dữ liệu vào hệ thống đều bảo đảm được điều đó.

#### Ba mức mô hình dữ liệu

Mô hình thực thể – quan hệ là **khung khái niệm**, không phải một mức trong dãy dưới đây. Nó cung cấp từ vựng để mô tả miền; ba mức sau đây là ba **mức trừu tượng của thiết kế dữ liệu**, và mức đầu tiên trong đó được xây dựng bằng chính từ vựng ấy. Viết chúng thành một dãy bốn tầng nối tiếp là sai bản chất: ER không đứng trước CDM theo thời gian, nó nằm bên trong CDM như phương tiện biểu đạt.

Thực hành mô hình hóa dữ liệu phân biệt ba mức trừu tượng, mỗi mức trả lời một câu hỏi khác nhau và **không được trộn lẫn** \cite{elmasri_fundamentals_2015}:

\[
\text{Mô hình khái niệm} \rightarrow \text{Mô hình logic} \rightarrow \text{Mô hình vật lý}.
\]

**Bảng 2-6. Ba mức mô hình dữ liệu**

| Mức | Câu hỏi trả lời | Nội dung điển hình | Không thuộc mức này |
|---|---|---|---|
| Khái niệm (CDM) | Miền nghiệp vụ có những khái niệm nào và liên hệ ra sao? | Thực thể, quan hệ, lực lượng ở mức nghiệp vụ — tenant, người ký, phiên thu, mẫu, lớp ký hiệu, bộ dữ liệu | Kiểu dữ liệu, chỉ mục, tên bảng vật lý |
| Logic (LDM) | Các thực thể và quan hệ được tổ chức thế nào theo mô hình quan hệ? | Khóa chính, khóa ngoại, lực lượng và tính tùy chọn, thực thể liên kết, tổng quát hóa/chuyên biệt hóa, mức chuẩn hóa | Đặc thù của một hệ quản trị cụ thể |
| Vật lý (PDM) | Chúng được triển khai trên hệ quản trị cụ thể ra sao? | Kiểu dữ liệu, chỉ mục, ràng buộc, phân mảnh, chính sách mức hàng, trigger | Ngữ nghĩa nghiệp vụ mới không có ở hai mức trên |

*Nguồn: tác giả tổng hợp theo \cite{elmasri_fundamentals_2015,chen_entity-relationship_1976}.*

Mức khái niệm dựa trên mô hình thực thể – quan hệ, vốn được đề xuất nhằm mô tả dữ liệu ở mức gần với nhận thức về miền ứng dụng thay vì gần với cách lưu trữ \cite{chen_entity-relationship_1976}. Mô hình quan hệ ở mức logic tách biểu diễn dữ liệu khỏi cách tổ chức lưu trữ vật lý, cho phép hai mức tiến hóa tương đối độc lập \cite{codd_relational_1970}.

Lý do phân biệt ba mức không phải hình thức: **chúng thay đổi với tốc độ khác nhau và vì những nguyên nhân khác nhau**. Mức khái niệm chỉ thay đổi khi hiểu biết về miền thay đổi — chẳng hạn khi nhận ra phương ngữ là một phần của định danh lớp chứ không phải thuộc tính phụ. Mức vật lý thay đổi vì hiệu năng hoặc vì năng lực của hệ quản trị. Trộn hai mức khiến một quyết định về chỉ mục trông giống một quyết định về miền, và ngược lại.

#### Chuẩn hóa và phi chuẩn hóa có chủ đích

Chuẩn hóa tổ chức các thuộc tính sao cho mỗi thuộc tính phụ thuộc vào đúng thực thể mà nó mô tả, nhằm giảm dư thừa và tránh các bất thường khi cập nhật \cite{elmasri_fundamentals_2015}. Dạng chuẩn thứ nhất yêu cầu giá trị của thuộc tính là nguyên tử theo mô hình quan hệ \cite{codd_relational_1970}.

Trong bài toán này, nguyên tắc đó trả lời trực tiếp một câu hỏi thiết kế cụ thể: **vì sao vùng, phương ngữ và người ký không được lưu như chuỗi văn bản trong bảng mẫu**. Nếu tên vùng nằm trong mỗi bản ghi mẫu, thì việc đổi tên một vùng đòi hỏi sửa hàng loạt bản ghi, hai cách viết khác nhau của cùng một vùng sẽ cùng tồn tại mà không có gì phát hiện, và không có chỗ nào để gắn thuộc tính của chính vùng đó. Khi vùng là một thực thể riêng được các thực thể khác tham chiếu, ngữ nghĩa của vùng được quản lý tại một chỗ duy nhất.

Tuy nhiên, kết luận **không phải** "càng chuẩn hóa càng tốt". Phi chuẩn hóa có chủ đích là một công cụ hợp lệ khi chi phí của nó được hiểu rõ.

**Bảng 2-7. Chuẩn hóa và phi chuẩn hóa có chủ đích**

| Tiêu chí | Mô hình chuẩn hóa | Phi chuẩn hóa có chủ đích |
|---|---|---|
| Mức dư thừa | Thấp | Cao hơn |
| Bất thường khi cập nhật | Ít | Phải tự kiểm soát |
| Nguồn sự thật cho một giá trị | Một chỗ duy nhất | Nhiều bản sao |
| Độ phức tạp truy vấn | Có thể cần nhiều phép nối | Thường đơn giản hơn |
| Phù hợp với dữ liệu giao dịch | Phù hợp | Chỉ khi có lý do cụ thể |
| Phù hợp với ảnh chụp bất biến, báo cáo | Có thể phức tạp | Phù hợp |
| Rủi ro chính | Truy vấn phức tạp hơn | Hai bản sao lệch nhau mà không ai biết |

*Nguồn: tác giả tổng hợp theo \cite{elmasri_fundamentals_2015}.*

**Định hướng được chọn.** Dữ liệu giao dịch và dữ liệu quản trị giữ ở dạng chuẩn hóa, nơi tính nhất quán quan trọng hơn sự tiện lợi khi truy vấn. Ngược lại, **các ảnh chụp bất biến có thể sao chép có chủ đích một số thông tin** để bảo toàn ý nghĩa lịch sử. Lý do rất cụ thể và không mâu thuẫn với nguyên tắc chuẩn hóa: một bản công bố phải ghi lại tên lớp *tại thời điểm công bố*; nếu nó chỉ giữ tham chiếu tới bảng danh mục hiện hành, việc đổi tên lớp về sau sẽ **âm thầm viết lại lịch sử** của một bản công bố đáng lẽ bất biến. Ở đây, dư thừa không phải khiếm khuyết mà chính là cơ chế bảo toàn ngữ nghĩa.

**Đánh đổi.** Hai bản sao có thể lệch nhau. Sự lệch đó chỉ chấp nhận được vì đối tượng chứa bản sao là bất biến — nghĩa là bản sao *không được phép* cập nhật theo. Nếu tính bất biến không được cưỡng chế, lập luận này sụp đổ và phi chuẩn hóa trở lại thành khiếm khuyết.

#### Định danh: khóa tự nhiên, khóa thay thế và khóa tổ hợp theo phạm vi

**Khóa tự nhiên** mang ý nghĩa nghiệp vụ, chẳng hạn tổ hợp ngôn ngữ – phương ngữ – vùng – định danh rút gọn của một lớp. Nó tự diễn đạt và tự cưỡng chế tính duy nhất nghiệp vụ, nhưng có thể thay đổi khi giá trị nghiệp vụ thay đổi, và làm khóa ngoại trở nên cồng kềnh.

**Khóa thay thế** là định danh không mang ngữ nghĩa, chẳng hạn một định danh sinh tự động. Nó ổn định khi giá trị nghiệp vụ thay đổi và làm khóa ngoại gọn, nhưng **tự nó không bảo vệ tính duy nhất nghiệp vụ**: hai hàng có định danh khác nhau vẫn có thể mô tả cùng một lớp ký hiệu nếu không có ràng buộc riêng.

**Khóa tổ hợp theo phạm vi** đưa khóa phạm vi vào chính định danh, dạng (phạm vi, định danh cục bộ). Nó cho phép cưỡng chế những bất biến mà hai loại trên không diễn đạt được — nội dung của mục 2.2.6.

**Bảng 2-8. So sánh ba cách tổ chức định danh**

| Tiêu chí | Khóa tự nhiên | Khóa thay thế | Khóa tổ hợp theo phạm vi |
|---|---|---|---|
| Mang ngữ nghĩa nghiệp vụ | Cao | Không | Trung bình |
| Ổn định khi giá trị nghiệp vụ đổi | Thấp | Cao | Cao |
| Khóa ngoại gọn nhẹ | Có thể cồng kềnh | Gọn | Phức tạp hơn |
| Tự cưỡng chế duy nhất nghiệp vụ | Có | Không — cần ràng buộc riêng | Có, trong phạm vi |
| Cưỡng chế bao hàm theo phạm vi | Không tự nhiên | Không tự nhiên | **Mạnh** |

*Nguồn: tác giả tổng hợp theo \cite{elmasri_fundamentals_2015}.*

**Định hướng được chọn.** Ba loại này **không loại trừ nhau**, và việc buộc phải chọn đúng một loại là một cách đặt vấn đề sai. Định hướng phù hợp là dùng khóa thay thế cho định danh ổn định và cho quan hệ khóa ngoại thông thường, đồng thời dùng **ràng buộc duy nhất trên tổ hợp thuộc tính nghiệp vụ** để bảo vệ tính duy nhất mà khóa thay thế không bảo vệ, và dùng khóa tổ hợp theo phạm vi ở những quan hệ cần cưỡng chế bao hàm. Đây cũng là lý do một lược đồ có khóa thay thế vẫn cần ràng buộc duy nhất nhiều cột: hai cơ chế trả lời hai câu hỏi khác nhau.

#### Bốn loại toàn vẹn quan hệ

Thuật ngữ "toàn vẹn" trong chương này xuất hiện ở nhiều nghĩa; các nghĩa được phân tách đầy đủ ở mục 2.8.4. Ở mức cơ sở dữ liệu quan hệ, cần phân biệt bốn loại ràng buộc \cite{elmasri_fundamentals_2015}.

**Bảng 2-9. Bốn loại toàn vẹn ở tầng cơ sở dữ liệu quan hệ**

| Loại | Bảo đảm điều gì | Cơ chế điển hình | Hỏng thì hậu quả gì |
|---|---|---|---|
| Toàn vẹn thực thể | Mỗi thực thể có định danh ổn định và không rỗng | Khóa chính | Không tham chiếu hay cập nhật đúng đối tượng được |
| Toàn vẹn tham chiếu | Khóa ngoại trỏ tới đối tượng thực sự tồn tại | Khóa ngoại | Bản ghi mồ côi, phép nối mất dữ liệu âm thầm |
| Toàn vẹn miền | Giá trị thuộc miền hợp lệ | Kiểu dữ liệu, `CHECK`, khóa ngoại tới danh mục | Giá trị rác lọt vào; thống kê sai mà không báo lỗi |
| Toàn vẹn xuyên phạm vi | Các đối tượng liên quan cùng thuộc một phạm vi quản trị | Khóa tổ hợp có khóa phạm vi; ràng buộc tương ứng | Quan hệ hợp lệ về cấu trúc nhưng **vượt ranh giới tổ chức** |

*Nguồn: tác giả tổng hợp theo \cite{elmasri_fundamentals_2015}; loại thứ tư là ràng buộc đặc thù của hệ nhiều phạm vi quản trị, phân tích ở mục 2.2.6.*

Ba loại đầu là nội dung tiêu chuẩn của thiết kế cơ sở dữ liệu quan hệ. Loại thứ tư chỉ phát sinh khi một lược đồ phục vụ nhiều phạm vi quản trị, và nó là loại dễ bị bỏ sót nhất vì một lược đồ thiếu nó vẫn **trông hoàn toàn đúng**.

### 2.1.7. Bộ dữ liệu dùng lại được như một đối tượng có vòng đời

Giá trị của một bộ dữ liệu nghiên cứu không chỉ phụ thuộc vào số lượng mẫu. FAIR đề xuất bốn thuộc tính định hướng cho dữ liệu khoa học: có thể tìm thấy, có thể truy cập, có khả năng tương tác và có khả năng tái sử dụng \cite{wilkinson_fair_2016}. Bổ sung cho hướng tiếp cận này, *Datasheets for Datasets* nhấn mạnh việc tài liệu hóa động cơ xây dựng, thành phần, quá trình thu thập, cách sử dụng dự kiến và các giới hạn của bộ dữ liệu \cite{gebru_datasheets_2021}. Hai hướng tiếp cận đều cho thấy siêu dữ liệu và nguồn gốc dữ liệu không phải phần phụ thêm sau khi thu thập, mà là thành phần cần thiết để dữ liệu có thể được diễn giải và tái sử dụng.

Trong phạm vi luận văn, một bộ dữ liệu vì vậy được xem là một đối tượng có vòng đời, bao gồm tối thiểu dữ liệu quan sát, danh mục ký hiệu, thông tin ngôn ngữ và phương ngữ, người ký và phiên thu, nguồn gốc dữ liệu, trạng thái đánh giá chất lượng và phạm vi sử dụng, phiên bản và cơ sở sử dụng. Cách nhìn này khác với cách tổ chức dữ liệu như một thư mục tệp: thư mục có thể cho biết tệp nằm ở đâu nhưng không tự biểu diễn được ai tạo dữ liệu, dữ liệu thuộc phạm vi quản trị nào, phiên bản nào đã được công bố, hoặc điều kiện nào cho phép dữ liệu được phân phối.

Vòng đời cũng làm phát sinh sự khác biệt giữa **dữ liệu đang làm việc** và **dữ liệu đã công bố**. Trạng thái đang làm việc có thể tiếp tục thay đổi khi thêm mẫu, hiệu chỉnh siêu dữ liệu hoặc rà soát chất lượng; ngược lại, một phiên bản đã được dùng làm tham chiếu nghiên cứu cần có khả năng truy lại đúng nội dung tại thời điểm công bố. Yêu cầu này là cơ sở cho cơ chế phiên bản bất biến và truy xuất nguồn gốc ở mục 2.8.

### 2.1.8. Vị thế của đề tài trong các lớp công cụ liên quan

Các công trình liên quan phục vụ những giai đoạn khác nhau của vòng đời dữ liệu và được xây dựng cho những phạm vi quản trị khác nhau. Việc phân loại theo hai trục này giúp định vị đề tài mà không cần giả định rằng mọi công cụ đều giải quyết cùng một bài toán. Mục này giới thiệu các lớp công cụ ở mức đủ để định vị; một bảng đối chiếu chi tiết theo các tiêu chí được xây dựng dần trong các mục 2.2–2.9 được đặt ở mục 2.11.2, khi người đọc đã có đủ tiêu chí để đọc bảng đó.

**Bộ dữ liệu** là kết quả của một quá trình thu thập. WLASL và AUTSL là các bộ dữ liệu tham chiếu cho nhận dạng ngôn ngữ ký hiệu \cite{li_wlasl_baibao_2020,sincan_autsl_2020}. Trong chương này, chúng chủ yếu được dùng để minh họa rằng dữ liệu dùng lại được cần có siêu dữ liệu về lớp ký hiệu, mẫu và người ký; chúng không phải đối tượng mà đề tài cạnh tranh trực tiếp.

**Tài nguyên từ vựng tham chiếu** là nguồn tra cứu về từ vựng của một ngôn ngữ ký hiệu. Từ điển Ngôn ngữ ký hiệu Việt Nam của dự án QIPEDC cung cấp một nguồn tham chiếu cho danh mục từ vựng \cite{bogddt_qipedc_2019}. Luận văn dùng cách gọi này thay vì "từ điển chuẩn hoá": các nguồn được khảo sát không cho thấy tài nguyên ấy được ban hành như một chuẩn có hiệu lực bắt buộc, nên một cách gọi mạnh hơn sẽ vượt quá điều nguồn nói. Vai trò của loại tài nguyên này đối với nền tảng là cung cấp điểm xuất phát cho danh mục; nó không thay thế tập nhiều mẫu được thu từ nhiều người ký và nhiều phiên phục vụ nghiên cứu thực nghiệm.

**Công cụ chú giải** hỗ trợ gán nhãn và mô tả dữ liệu đã tồn tại. ELAN là môi trường chú giải đa phương thức được sử dụng rộng rãi trong nghiên cứu ngôn ngữ \cite{wittenburg_elan_2006}. Loại công cụ này giải quyết tốt thao tác chú giải nhưng không mặc nhiên cung cấp mô hình quản trị nhiều tổ chức, vòng đời đồng thuận hay cơ chế cô lập dữ liệu theo tenant.

**Nền tảng thu thập dữ liệu nghiên cứu** là lớp công cụ gần với đề tài nhất. REDCap là một nền tảng thu thập và quản lý dữ liệu nghiên cứu dựa trên biểu mẫu, hỗ trợ nhiều dự án, nghiên cứu đa điểm, kiểm soát quyền ở cấp dự án và nhật ký kiểm toán \cite{harris_research_2009,harris_redcap_2019}. REDCap cho thấy các chức năng thu thập, phân quyền và kiểm toán có thể được tích hợp trong một nền tảng nghiên cứu dùng chung. Tuy nhiên, mô hình của REDCap chủ yếu xoay quanh biểu mẫu và dự án nghiên cứu tổng quát; nó không đặt tầng danh mục chuyên biệt cho ngôn ngữ, phương ngữ và lớp ký hiệu, cũng không đặt việc thu nhận dữ liệu thị giác và trích xuất đặc trưng tại máy khách làm một phần trung tâm của mô hình miền. Điểm khác biệt vì vậy **không nằm ở số lượng chức năng** mà ở mô hình miền và phương thức thu nhận.

**Kho lưu trữ và công bố dữ liệu nghiên cứu** phục vụ chủ yếu giai đoạn lưu giữ, mô tả và phân phối các đối tượng nghiên cứu đã được hình thành. Dataverse cung cấp cơ chế quản lý bộ dữ liệu, phiên bản, siêu dữ liệu, quyền truy cập và điều kiện sử dụng; Zenodo cung cấp định danh bền vững, phiên bản, giấy phép và các mức truy cập cho đối tượng nghiên cứu \cite{crosas_dataverse_2011,cern_openaire_zenodo_2013}. Điểm khác biệt với nền tảng thu thập không nằm ở việc các kho này thiếu cơ chế quản trị, mà ở **thời điểm và đối tượng được quản trị**: kho tiếp nhận một đối tượng nghiên cứu do người nộp cung cấp, trong khi nền tảng thu thập phải thiết lập quan hệ giữa chủ thể dữ liệu, cơ sở xử lý, phiên thu và mẫu ngay khi dữ liệu được tạo ra. Những thông tin không được ghi nhận tại thời điểm đó có thể không tái tạo đáng tin cậy về sau — đúng lập luận đã nêu ở mục 2.1.5.

Một dạng tổ chức khác thường xuất hiện ở giai đoạn đầu của các dự án dữ liệu là lưu trữ tệp dùng chung kết hợp với quy ước thư mục. Đây không phải một sản phẩm hay kiến trúc cụ thể, mà là một cách vận hành thủ công. Cách này có thể phù hợp với nhóm nhỏ, nhưng ranh giới tổ chức, siêu dữ liệu, phiên bản và điều kiện sử dụng phụ thuộc vào quy ước của người vận hành thay vì được biểu diễn và kiểm soát bởi lược đồ hệ thống.

**Bảng 2-10. Định vị đề tài theo giai đoạn vòng đời và phạm vi quản trị**

| Loại công cụ | Giai đoạn chính | Tổ chức / phạm vi độc lập | Danh mục chuyên biệt theo miền | Đồng thuận và quy kết tại thời điểm thu |
|---|---|---|---|---|
| Công cụ chú giải (ELAN) | Chú giải | Không phải trọng tâm | Không phải trọng tâm | Không phải chức năng cốt lõi |
| Lưu trữ tệp + thư mục thủ công | Thu thập, lưu trữ | Dựa trên quy ước thủ công | Dựa trên quy ước | Dựa trên quy trình ngoài hệ thống |
| REDCap | Thu thập, quản lý nghiên cứu | Dự án, đa điểm, quyền theo dự án | Biểu mẫu tổng quát | Có thể cấu hình theo nghiên cứu |
| Dataverse, Zenodo | Nộp lưu, lưu giữ, công bố | Collection/community và quyền của kho | Không phải trọng tâm | Không phải chức năng cốt lõi của giai đoạn thu |
| **Phân hệ của luận văn** | **Thu nhận → quản lý → sử dụng ở hạ nguồn** (phát hành là nhánh tuỳ trường hợp) | **Tổ chức → không gian làm việc → dự án** | **Ngôn ngữ → phương ngữ → lớp ký hiệu, có phiên bản** | **Khả năng liên kết chủ thể dữ liệu với điều kiện sử dụng** |

*Nguồn: tác giả tổng hợp trong phạm vi các lớp công cụ được khảo sát.*

Đề tài thuộc lớp nền tảng thu thập và quản trị dữ liệu nghiên cứu. Cần nêu rõ phạm vi ngay tại đây để tránh một cách hiểu quá rộng: đối tượng của luận văn là **phân hệ thu thập và quản lý dữ liệu ngôn ngữ ký hiệu của CTU.SignBridge**, không phải toàn bộ nền tảng. Các thành phần khác của nền tảng — trong đó có huấn luyện và nhận dạng — được xem là bên tiêu thụ dữ liệu ở hạ nguồn.

Điểm định vị của phân hệ nằm ở giao của ba yêu cầu: **thu nhận theo phương thức chuyên biệt của miền ngôn ngữ ký hiệu**, **quản trị nhiều phạm vi tổ chức trên một hạ tầng dùng chung**, và **quản trị dữ liệu ngay từ thời điểm thu**. Từ vị thế này phát sinh ba hệ quả chi phối các mục còn lại của chương.

Thứ nhất, nghĩa vụ quản trị phát sinh trực tiếp tại đường thu. Nền tảng không thể chỉ dựa vào khai báo bổ sung sau khi dữ liệu đã tồn tại; các thông tin về chủ thể, phiên thu, nguồn gốc và cơ sở sử dụng phải được ghi nhận khi còn có thể xác định đáng tin cậy. Thứ hai, nhiều đơn vị có thể cùng vận hành trên một hạ tầng nhưng cần ranh giới riêng về dữ liệu, thành viên, quyền và cấu hình; đây là cơ sở của các mục 2.2 đến 2.5. Thứ ba, dữ liệu tăng trưởng liên tục theo thời gian thay vì tồn tại như một bản phát hành duy nhất, nên hệ thống phải tách trạng thái đang làm việc khỏi phiên bản đã công bố và duy trì khả năng truy xuất nguồn gốc; đây là trọng tâm của mục 2.8.

Phạm vi của luận văn bao gồm thu nhận dữ liệu qua nền tảng, quản lý danh mục từ vựng và phương ngữ, cô lập và phân quyền theo phạm vi tổ chức, đường ống nhập liệu và xử lý bất đồng bộ, quản trị đồng thuận và quy kết, phiên bản và toàn vẹn của tạo tác nghiên cứu, cùng các nguyên tắc triển khai và di trú hệ thống. Ngoài phạm vi là huấn luyện, tối ưu và đánh giá mô hình nhận dạng, cũng như phát triển một thuật toán trích xuất điểm mốc mới. Thành phần trích xuất được sử dụng như một kỹ thuật thu nhận có sẵn.

## 2.2. Kiến trúc SaaS và tính đa thuê bao

Tên đề tài đặt tính đa thuê bao ở vị trí trung tâm, nên mục này cần trả lời đầy đủ bốn câu hỏi: đa thuê bao là gì và khác gì với nhiều người dùng; có những cách xây dựng đa thuê bao nào; phân hệ chọn mức chia sẻ nào; và lựa chọn đó tạo ra nghĩa vụ gì đối với lược đồ và cơ chế cưỡng chế.

### 2.2.1. SaaS, multi-user, multi-tenancy và các phạm vi tài nguyên

Software as a Service (SaaS) là mô hình cung cấp phần mềm trong đó năng lực ứng dụng được cung cấp qua mạng và người sử dụng không trực tiếp quản lý hạ tầng điện toán nền bên dưới \cite{mell_nist_2011}. Trong quá trình phát triển SaaS, một quyết định kiến trúc quan trọng là mức độ chia sẻ tài nguyên giữa các khách hàng hoặc miền quản trị \cite{chong_architecture_2006}.

Cần phân biệt **multi-user** và **kiến trúc đa thuê bao (multi-tenancy)**. Multi-user là đặc tính cho phép nhiều người dùng cùng sử dụng một ứng dụng. Multi-tenancy là cách tổ chức kiến trúc trong đó nhiều miền quản trị dùng chung một phần hạ tầng hoặc thành phần ứng dụng nhưng vẫn duy trì ranh giới riêng về dữ liệu, quyền và cấu hình \cite{bezemer_multi-tenant_2010,krebs_architectural_2012}. Có thể phát biểu quan hệ:

\[
\text{SaaS} \neq \text{Multi-user} \neq \text{Multi-tenant}.
\]

Ba khái niệm này thường xuất hiện cùng nhau nhưng không kéo theo nhau. Một hệ thống có thể là SaaS mà chỉ phục vụ một tổ chức; có thể là multi-user mà không có khái niệm miền quản trị nào. Vì vậy, việc người dùng A không xem được dữ liệu của người dùng B **chưa đủ** để kết luận một hệ thống là multi-tenant; đó mới chỉ là phân quyền theo người dùng. Câu hỏi phân định là: hệ thống có mô hình hóa các **miền quản trị độc lập** — mỗi miền có thành viên riêng, vai trò riêng, dữ liệu riêng, cấu hình riêng và phạm vi tài nguyên riêng — và có cưỡng chế ranh giới giữa chúng hay không. Một dấu hiệu khác của multi-tenancy thật sự là **một người dùng có thể thuộc nhiều miền quản trị** với tư cách khác nhau ở mỗi miền; điều này không có nghĩa trong một hệ thống chỉ phân quyền theo người dùng.

Trong luận văn này, **tenant** được định nghĩa là phạm vi quản trị logic cao nhất đối với dữ liệu nghiệp vụ, thành viên, quyền truy cập và cấu hình riêng của một đơn vị sử dụng nền tảng. Tenant không nhất thiết đồng nhất với tư cách pháp nhân của một tổ chức; đây trước hết là một ranh giới kỹ thuật và quản trị trong hệ thống.

Bên trong tenant, **không gian làm việc (workspace)** tổ chức một nhóm hoạt động hoặc tài nguyên có liên quan; **dự án (project)** là phạm vi hẹp hơn cho một mục tiêu hoặc hoạt động cụ thể. Quan hệ chứa được biểu diễn:

\[
Tenant \supset Workspace \supset Project.
\]

Sự tách bạch ba tầng này giải quyết một vấn đề cụ thể: nếu ranh giới tổ chức công việc và ranh giới cô lập là một, thì mọi nhóm công việc mới đều trở thành một thuê bao mới, và một đơn vị có nhiều nhóm cùng thu dữ liệu không có cách biểu diễn tự nhiên. Tách ba tầng cho phép **cô lập** dừng ở tầng trên cùng trong khi **tổ chức công việc** tiếp tục ở hai tầng dưới.

Cần nhấn mạnh: cây phạm vi này không tự sinh ra quyền truy cập. Nó chỉ tạo cấu trúc để chính sách phân quyền có thể gắn vai trò và quyền vào đúng cấp, sau đó xác định rõ có hay không cơ chế kế thừa xuống phạm vi con. Điểm này được trở lại ở mục 2.5.6.

### 2.2.2. Bốn mức chia sẻ tài nguyên trong kiến trúc đa thuê bao

Đa thuê bao không phải một lựa chọn nhị phân, và cũng không chỉ là lựa chọn về cơ sở dữ liệu. Có thể chia sẻ ở nhiều tầng khác nhau, tạo thành một dải liên tục từ chia sẻ ít nhất đến chia sẻ nhiều nhất \cite{chong_architecture_2006,bezemer_multi-tenant_2010}.

**Mức 1 — Ứng dụng riêng, cơ sở dữ liệu riêng.** Mỗi tenant có một bản triển khai ứng dụng riêng và một cơ sở dữ liệu riêng. Đây thực chất là *n* lần triển khai một sản phẩm đơn thuê bao. Cô lập mạnh nhất, chia sẻ ít nhất, và chi phí vận hành tăng gần như tuyến tính theo số tenant.

**Mức 2 — Ứng dụng dùng chung, cơ sở dữ liệu riêng.** Một bản triển khai ứng dụng phục vụ nhiều tenant, nhưng mỗi tenant có cơ sở dữ liệu riêng; ứng dụng chọn kết nối theo tenant hiện hành.

**Mức 3 — Ứng dụng dùng chung, cơ sở dữ liệu dùng chung, lược đồ riêng.** Một cơ sở dữ liệu chứa nhiều lược đồ, mỗi tenant một lược đồ, cấu trúc bảng giống nhau nhưng nằm trong các không gian tên khác nhau.

**Mức 4 — Ứng dụng dùng chung, cơ sở dữ liệu dùng chung, lược đồ dùng chung.** Dữ liệu của mọi tenant nằm trong cùng các bảng và được phân biệt bằng một khóa phạm vi trên từng hàng.

**Bảng 2-11. Bốn mức chia sẻ tài nguyên trong kiến trúc đa thuê bao**

| Mức | Ứng dụng | Cơ sở dữ liệu | Lược đồ | Ranh giới cô lập nằm ở đâu |
|---|---|---|---|---|
| 1 | Riêng theo tenant | Riêng theo tenant | Riêng | Tiến trình và cơ sở dữ liệu |
| 2 | Dùng chung | Riêng theo tenant | Riêng | Cơ sở dữ liệu |
| 3 | Dùng chung | Dùng chung | Riêng theo tenant | Lược đồ (không gian tên) |
| 4 | Dùng chung | Dùng chung | Dùng chung | **Hàng dữ liệu** |

*Nguồn: tác giả tổng hợp từ \cite{chong_architecture_2006,bezemer_multi-tenant_2010,aulbach_multi-tenant_2008}.*

Quan hệ chi phối toàn bộ dải này có thể phát biểu ngắn gọn:

\[
\text{Mức chia sẻ càng cao} \Rightarrow \text{Yêu cầu đối với cô lập logic càng cao}.
\]

Khi ranh giới vật lý biến mất, ranh giới logic phải gánh toàn bộ trách nhiệm mà ranh giới vật lý từng gánh. Đây là lý do một lựa chọn chia sẻ cao **không phải là lựa chọn rẻ hơn mà không mất gì**; nó là lựa chọn đánh đổi chi phí vận hành lấy yêu cầu về an toàn thông tin — hai thuộc tính chất lượng ở Bảng 2-1 xung đột trực tiếp tại đây.

Đối với phân hệ được nghiên cứu trong luận văn, mức 4 là mức được xem xét cho dữ liệu nghiệp vụ đa thuê bao. Ba tiểu mục tiếp theo phân tích ba mô hình tổ chức dữ liệu tương ứng với các mức 2, 3 và 4.

> ### ▣ HÌNH 2-2 — Bốn mức chia sẻ tài nguyên trong kiến trúc đa thuê bao
> **Loại:** sơ đồ khối bốn cột · **Công cụ đề nghị:** draw.io
> **Phải thể hiện:** bốn cột tương ứng bốn mức, mỗi cột vẽ ba tenant A/B/C; các khối được **tô cùng màu khi dùng chung** và khác màu khi riêng; một đường kẻ ngang đánh dấu **vị trí ranh giới cô lập** ở mỗi cột (tiến trình → cơ sở dữ liệu → lược đồ → hàng); mũi tên nằm dưới chạy từ trái sang phải với hai nhãn đối lập: "chia sẻ tài nguyên tăng" và "yêu cầu cô lập logic tăng".
> **Chú thích dưới hình:** *Hình 2-2: Bốn mức chia sẻ tài nguyên và vị trí ranh giới cô lập tương ứng.*

### 2.2.3. Cơ sở dữ liệu riêng cho từng tenant

Mô hình này cấp cho mỗi tenant một cơ sở dữ liệu riêng, dùng chung tầng ứng dụng.

**Ưu điểm.** Ranh giới giữa các tenant là ranh giới ở cấp cơ sở dữ liệu, nên một truy vấn sai trong ngữ cảnh của tenant A **không đọc tới bảng của tenant B** vì hai bảng không nằm cùng một không gian truy vấn. Sao lưu và khôi phục cho riêng một tenant tương đối trực tiếp vì đơn vị sao lưu trùng với đơn vị nghiệp vụ. Với những khách hàng lớn có yêu cầu riêng, có thể cấu hình tham số cơ sở dữ liệu khác nhau cho từng bản.

**Nhược điểm.** Nếu số tenant là \(N\) thì số cơ sở dữ liệu cần quản lý tỉ lệ thuận với \(N\):

\[
\text{Số cơ sở dữ liệu} \propto N.
\]

Hệ quả trải rộng trên nhiều mặt vận hành. Mỗi thay đổi cấu trúc phải được áp lên *N* bản, và một bản chạy lỗi tạo ra **lệch lược đồ (schema drift)** — trạng thái mà các bản không còn giống nhau, và mã ứng dụng dùng chung không còn giả định được điều gì về cấu trúc. Số kết nối và cấu hình bể kết nối phức tạp hơn. Số đơn vị cần giám sát, sao lưu và kiểm tra sao lưu tăng theo *N*. Việc khởi tạo một tenant mới không còn là một thao tác ghi dữ liệu mà là một thao tác cấp phát hạ tầng. Cuối cùng, các truy vấn thống kê ở phạm vi nền tảng — vốn cần đọc ngang qua nhiều tenant — trở nên khó thực hiện.

**Phù hợp hơn khi** yêu cầu cô lập vật lý hoặc khả năng tùy biến cho từng tenant quan trọng hơn hiệu quả vận hành, chẳng hạn khi các tenant chịu những chế độ quản lý dữ liệu khác nhau hoặc yêu cầu dữ liệu nằm trên hạ tầng tách biệt.

### 2.2.4. Lược đồ riêng cho từng tenant

Mô hình này dùng chung một hệ quản trị cơ sở dữ liệu nhưng cấp cho mỗi tenant một lược đồ riêng.

**Ưu điểm.** Chia sẻ được hệ quản trị và tài nguyên máy chủ, nên chi phí thấp hơn mức 2. Không gian tên tách biệt tạo một ranh giới logic rõ hơn so với việc các hàng nằm lẫn trong cùng bảng, và việc di chuyển dữ liệu của một tenant vẫn tương đối gọn.

**Nhược điểm.** Số lược đồ vẫn tăng theo số tenant:

\[
\text{Số lược đồ} \approx \text{Số tenant}.
\]

Do đó phần lớn các vấn đề của mức 2 vẫn tồn tại ở dạng nhẹ hơn: di trú vẫn phải lặp, lệch lược đồ vẫn có thể xảy ra, công cụ vận hành vẫn phải xử lý số lượng đối tượng tăng dần. Ngoài ra xuất hiện một lớp lỗi đặc thù: việc phân giải tenant phụ thuộc vào **đường tìm kiếm lược đồ (search path)** của phiên kết nối. Nếu đường tìm kiếm được đặt sai hoặc không được đặt lại khi kết nối quay về bể, một truy vấn viết đúng cú pháp có thể chạy trên lược đồ của tenant khác mà không báo lỗi.

### 2.2.5. Lược đồ dùng chung

Mô hình này để dữ liệu của mọi tenant trong cùng các bảng, phân biệt bằng một cột khóa phạm vi \cite{aulbach_multi-tenant_2008}.

**Ưu điểm.** Chỉ tồn tại một lược đồ, nên thay đổi cấu trúc được thực hiện tập trung một lần và không phát sinh lệch lược đồ giữa các tenant. Các quan hệ dữ liệu được định nghĩa một lần và áp dụng thống nhất. Khởi tạo một tenant mới là một thao tác ghi dữ liệu chứ không phải cấp phát hạ tầng. Các nghiệp vụ ở phạm vi nền tảng đọc ngang nhiều tenant trở nên khả thi thay vì phải tổng hợp từ nhiều nguồn. Mô hình đặc biệt phù hợp khi các tenant **cùng vận hành trên một mô hình miền chung** — như trường hợp các đơn vị cùng thu dữ liệu ngôn ngữ ký hiệu theo cùng một cấu trúc khái niệm đã mô tả ở mục 2.1.6.

**Nhược điểm.** Cô lập chuyển hoàn toàn từ ranh giới vật lý sang ranh giới logic. Một cột khóa phạm vi **tự nó chỉ là dữ liệu định danh**; nó không có năng lực cưỡng chế nào. Nếu cơ chế bảo vệ chỉ là quy ước "mọi truy vấn phải thêm điều kiện lọc theo tenant", thì độ an toàn của toàn hệ thống bằng độ an toàn của **truy vấn cẩu thả nhất trong toàn bộ mã nguồn**, kể cả những truy vấn sẽ được viết trong tương lai bởi người không biết quy ước đó. Đây là một tính chất bất lợi nghiêm trọng vì nó không suy giảm dần: một chỗ sót là đủ, và lỗi loại này thường **không sinh ra triệu chứng** — truy vấn trả về nhiều dữ liệu hơn dự kiến chứ không báo lỗi.

Nhận định này là cơ sở trực tiếp cho mục 2.4: khi chọn lược đồ dùng chung, câu hỏi kiến trúc kế tiếp không còn là *"có nên cô lập không"* mà là *"đặt cơ chế cưỡng chế ở tầng nào để một truy vấn nghiệp vụ thông thường không thể vô tình bỏ qua nó"*.

### 2.2.6. Toàn vẹn xuyên phạm vi trong lược đồ dùng chung

Trước khi so sánh ba mô hình, cần nêu một hệ quả của lược đồ dùng chung đối với thiết kế ràng buộc — loại toàn vẹn thứ tư ở Bảng 2-9. Đây là điểm dễ bị bỏ sót nhất vì một lược đồ thiếu nó vẫn thỏa mãn đầy đủ ba loại toàn vẹn tiêu chuẩn.

Xét quan hệ chứa `Tenant ⊃ Workspace ⊃ Project`. Một khóa ngoại thông thường từ dự án tới không gian làm việc chỉ bảo đảm rằng không gian làm việc được tham chiếu **tồn tại**. Nó không bảo đảm rằng hai đối tượng **thuộc cùng một tenant**. Nói cách khác, toàn vẹn tham chiếu trả lời "đối tượng này có tồn tại không", còn câu hỏi cần trả lời trong hệ đa thuê bao là "đối tượng này có hợp lệ **trong phạm vi quản trị hiện hành** không". Bất biến cần giữ là:

\[
Project.tenant = Workspace.tenant.
\]

Nếu bất biến này không được cưỡng chế ở tầng lược đồ, một bản ghi có thể được tạo ra trong đó dự án của tenant A trỏ tới không gian làm việc của tenant B. Bản ghi đó **hợp lệ về cấu trúc**: khóa chính hợp lệ, khóa ngoại trỏ tới hàng tồn tại, giá trị thuộc miền hợp lệ. Nhưng nó vượt ranh giới tổ chức, và nó tạo ra một đường đi mà cơ chế cô lập ở mục 2.4 không nhất thiết chặn được, vì cơ chế đó lọc theo phạm vi chứ không kiểm tính nhất quán của quan hệ.

Cách diễn đạt bất biến này ở tầng lược đồ là đưa khóa phạm vi vào chính khóa được tham chiếu, tức là dùng khóa tổ hợp theo phạm vi đã nêu ở mục 2.1.6:

\[
FK\,(Project.tenant,\; Project.workspace) \rightarrow Workspace\,(tenant,\; workspace).
\]

Khi khóa ngoại mang theo khóa phạm vi, một quan hệ vượt tenant trở thành **không biểu diễn được** ở tầng cấu trúc, thay vì chỉ là một trạng thái mà mã ứng dụng được kỳ vọng sẽ tránh. Đây là cùng một nguyên lý được lặp lại ở mục 2.4: chuyển một bất biến từ chỗ *phải nhớ* sang chỗ *không thể vi phạm*.

Ở mức lý thuyết, điều cần giữ là **toàn vẹn tham chiếu không hàm ý toàn vẹn xuyên phạm vi**: hai loại toàn vẹn này cần hai cơ chế khác nhau. Chi tiết hiện thực và phạm vi áp dụng thuộc Chương 3 và Phụ lục A.

### 2.2.7. So sánh ba mô hình và định hướng được chọn

**Bảng 2-12. So sánh ba mô hình tổ chức dữ liệu đa thuê bao**

| Tiêu chí | CSDL riêng theo tenant | Lược đồ riêng theo tenant | Lược đồ dùng chung |
|---|---|---|---|
| Ranh giới dữ liệu | Cấp cơ sở dữ liệu | Cấp lược đồ | Cấp hàng |
| Di trú cấu trúc | Lặp theo từng CSDL | Lặp theo từng lược đồ | Tập trung, một lần |
| Khởi tạo tenant mới | Cấp phát hạ tầng | Trung bình | Thao tác ghi dữ liệu |
| Chi phí vận hành theo số tenant | Cao | Trung bình | Thấp |
| Yêu cầu đối với cơ chế cưỡng chế cô lập | Thấp hơn | Trung bình | **Rất cao** |
| Phù hợp khi các tenant dùng chung mô hình miền | Có | Có | Rất phù hợp |
| Rủi ro đặc trưng cần phòng ngừa | Vận hành không theo kịp | Sai đường tìm kiếm lược đồ | **Rò dữ liệu khi truy vấn sót điều kiện phạm vi** |

*Nguồn: tác giả tổng hợp định tính từ \cite{bezemer_multi-tenant_2010,chong_architecture_2006,aulbach_multi-tenant_2008,krebs_architectural_2012}; bảng thể hiện so sánh tương đối theo tiêu chí thiết kế, không phải kết quả đo hiệu năng.*

Bảng trên chỉ giữ bảy tiêu chí dẫn trực tiếp tới lựa chọn của luận văn. Phân tích mở rộng theo tám tiêu chí còn lại — sao lưu và khôi phục riêng tenant, hiệu suất sử dụng tài nguyên, mức tuỳ biến cho từng tenant, nghiệp vụ đọc ngang nhiều tenant, nguy cơ lệch lược đồ, chi phí khởi tạo, yêu cầu toàn vẹn xuyên phạm vi và mức chia sẻ tài nguyên — được trình bày tại **Phụ lục F.2, Bảng F-1**.

**Định hướng được chọn.** Đối với phân hệ được nghiên cứu, mô hình lược đồ dùng chung là mô hình phù hợp, dựa trên ba lý do có thể kiểm chứng bằng chính đặc điểm bài toán. Thứ nhất, các tenant cùng vận hành trên một mô hình dữ liệu ngôn ngữ ký hiệu chung — cùng khái niệm lớp ký hiệu, phương ngữ, người ký, phiên thu — nên một lược đồ thống nhất phản ánh đúng miền chứ không phải là sự đơn giản hóa. Thứ hai, hệ thống còn đang tiến hóa, nên khả năng thay đổi cấu trúc **một lần** thay vì lặp trên *N* bản là điều kiện thực tế để phát triển tiếp. Thứ ba, các nghiệp vụ ở phạm vi nền tảng — thống kê, đối soát, công bố danh mục dùng chung — đọc ngang qua nhiều tenant, và mô hình này hỗ trợ chúng tự nhiên.

**Đánh đổi** gồm hai nghĩa vụ, không phải một. Nghĩa vụ thứ nhất: ranh giới tenant trở thành ranh giới logic, nên nền tảng phải có một cơ chế cô lập đủ mạnh ở tầng cơ sở dữ liệu, đặt tại vị trí mà mã nghiệp vụ không thể vô tình bỏ qua — nội dung mục 2.4. Nghĩa vụ thứ hai, ít được chú ý hơn: lược đồ phải cưỡng chế toàn vẹn xuyên phạm vi như mục 2.2.6 đã nêu, vì cơ chế lọc theo phạm vi không tự phát hiện một quan hệ đã được tạo ra sai ngay từ đầu.

### 2.2.8. Các chiều cô lập khác và hạn mức tài nguyên

Cô lập trong hệ thống đa thuê bao không chỉ liên quan đến dữ liệu. Krebs và cộng sự phân tích các khía cạnh cô lập liên quan đến dữ liệu, an ninh và hiệu năng trong ứng dụng multi-tenant \cite{krebs_architectural_2012}. Trong phạm vi luận văn, cô lập dữ liệu và cô lập an ninh là hai chiều được đặt làm trọng tâm nghiên cứu; chiều hiệu năng được xem xét ở mức hạn mức tài nguyên theo tenant. Mức độ hiện thực và kết quả đo của từng chiều thuộc Chương 3 và Chương 4.

Hạn mức cần được nhìn như một cơ chế bảo vệ tài nguyên dùng chung, không chỉ là thành phần của bảng giá. Một tenant có thể vẫn tuân thủ ranh giới dữ liệu nhưng tiêu thụ số lượng mẫu, người dùng, tác vụ hoặc tài nguyên xử lý quá lớn, từ đó làm suy giảm dịch vụ dành cho tenant khác. Đây là dạng nhiễu mà ranh giới dữ liệu không chặn được, vì nó không đi qua đường dữ liệu. Vì vậy quota là một lớp giới hạn mức sử dụng trong không gian chia sẻ, độc lập với cơ chế cô lập dữ liệu.

Tuy nhiên, việc có quota không đồng nghĩa đã chứng minh được khả năng cô lập hiệu năng. Đánh giá nhiễu hiệu năng giữa các tenant đòi hỏi thí nghiệm tải riêng, trong đó tải của một tenant được tăng có kiểm soát và độ trễ của tenant khác được đo đồng thời. Nếu luận văn không thực hiện phép đo này thì chỉ nên khẳng định rằng hệ thống **có cơ chế hạn mức**, không khẳng định đã đạt cô lập hiệu năng đầy đủ.

### 2.2.9. Tài nguyên ngoài cơ sở dữ liệu và ranh giới bảo vệ

Không phải mọi nội dung của nền tảng đều phù hợp để lưu trực tiếp trong bảng quan hệ. Video, tệp đặc trưng, tệp tài liệu hoặc các đối tượng dung lượng lớn có thể được đặt trong hệ thống tệp hoặc dịch vụ lưu trữ bên ngoài, trong khi cơ sở dữ liệu giữ định danh, đường dẫn hoặc khóa tham chiếu. So sánh đầy đủ giữa hai phương án lưu trữ được trình bày ở mục 2.7.5; ở đây chỉ xét hệ quả đối với ranh giới bảo vệ. Khi đó cần tách hai vấn đề: **toàn vẹn của nội dung được tham chiếu** và **quyền được truy cập nội dung đó**.

Với **tham chiếu định địa chỉ theo vị trí**, định danh cho biết đối tượng nằm ở đâu. Nội dung có thể bị thay thế tại cùng vị trí nếu hệ thống lưu trữ cho phép, nên vị trí tự nó không chứng minh nội dung vẫn là bản ban đầu. Với **tham chiếu định địa chỉ theo nội dung (content-addressed reference)**, định danh được suy ra từ giá trị băm mật mã của nội dung. Khi dùng một hàm băm có tính kháng va chạm phù hợp, việc chủ động tìm một nội dung khác có cùng giá trị băm được xem là bất khả thi về mặt tính toán trong điều kiện thực tế \cite{nist_fips180_4_2015}. Bên nhận có thể băm lại nội dung để kiểm tra nó có khớp với định danh đã lưu hay không.

Cơ chế này cung cấp khả năng phát hiện thay đổi nội dung, nhưng **không phải cơ chế kiểm soát truy cập**. Row-Level Security bảo vệ hàng dữ liệu trong PostgreSQL và không tự mở rộng sang kho đối tượng bên ngoài. Tài nguyên ngoài cơ sở dữ liệu vì vậy cần một đường truy cập riêng, dùng cùng ngữ cảnh tenant và cùng nguyên tắc mặc định từ chối.

Hai nguyên lý chi phối đường đó. *Complete mediation* yêu cầu mọi truy cập được kiểm tại điểm sử dụng. Một thành phần có quyền rộng truy cập tài nguyên thay mặt người dùng mà không kiểm lại phạm vi sẽ rơi vào dạng lỗi *confused deputy* \cite{saltzer_protection_1975,hardy_confused_1988}. Hệ quả thực tế: nếu kho cho phép đọc chỉ bằng việc biết định danh thì định danh trở thành một chứng chỉ truy cập, và tính bí mật của đường dẫn không phải một cơ chế bảo vệ.

Việc lưu siêu dữ liệu và nội dung trên hai hệ thống khác nhau còn làm phát sinh bài toán ghi kép, được phân tích ở mục 2.7.4.

**Bảng 2-13. Các yêu cầu khi nội dung nằm ngoài cơ sở dữ liệu**

| Yêu cầu | Cơ chế hoặc nguyên tắc |
|---|---|
| Xác định nội dung có bị thay đổi | Giá trị băm / tham chiếu định địa chỉ theo nội dung khi phù hợp |
| Bảo vệ quyền đọc | Điểm kiểm soát truy cập dùng cùng ngữ cảnh tenant; không dựa vào tính bí mật của đường dẫn |
| Xử lý ghi kép | Thứ tự ghi xác định trước, trạng thái trung gian và đối soát định kỳ (mục 2.7.4) |
| Quản lý xóa | Quy trình xóa bao phủ cả hàng dữ liệu và đối tượng lưu trữ |

*Nguồn: tác giả tổng hợp từ \cite{saltzer_protection_1975,hardy_confused_1988,kleppmann_designing_2017,nist_fips180_4_2015}.*

> ### ▣ HÌNH 2-3 — Hai cách tham chiếu nội dung và phạm vi bảo đảm của từng cách
> **Loại:** sơ đồ đối chiếu hai nhánh · **Công cụ đề nghị:** draw.io
> **Phải thể hiện:** nhánh trên là tham chiếu theo **vị trí** (hàng dữ liệu giữ đường dẫn → đối tượng trong kho), kèm một mũi tên "nội dung bị thay tại chỗ" mà tham chiếu **không phát hiện được**; nhánh dưới là tham chiếu theo **nội dung** (hàng dữ liệu giữ giá trị băm → bên đọc băm lại và đối chiếu), cùng mũi tên thay nội dung nhưng kết quả là **phát hiện được**; một khung bao quanh cả hai nhánh ghi rõ giới hạn chung: "cả hai cách đều **không** là cơ chế kiểm soát truy cập — vẫn cần điểm kiểm quyền riêng cho đường đọc nội dung".
> **Chú thích dưới hình:** *Hình 2-3: Hai cách tham chiếu nội dung và phạm vi bảo đảm của từng cách.*

## 2.3. Phạm vi quản trị và chia sẻ dữ liệu

Mục 2.2 xác định ranh giới giữa các tenant. Bên trong và bên ngoài các ranh giới đó, nền tảng còn chứa những loại dữ liệu có mục đích và chủ thể quản trị khác nhau. Việc phân biệt các phạm vi này là vấn đề quản trị kỹ thuật; nó không nhằm đưa ra kết luận pháp lý về quyền sở hữu tài sản hay quyền tác giả.

### 2.3.1. Ba phạm vi quản trị dữ liệu

Trong một nền tảng dùng chung có thể phân biệt ba nhóm dữ liệu theo chủ thể quản trị và mục đích, thay vì theo vị trí lưu trữ.

**Danh mục và cấu hình hệ thống** là dữ liệu phục vụ hoạt động của chính nền tảng: danh mục chuẩn dùng làm điểm xuất phát, cấu hình gói dịch vụ, bảng tham chiếu kỹ thuật. Chủ thể quản trị là nhà vận hành nền tảng.

**Dữ liệu dùng chung cộng đồng** là dữ liệu nghiệp vụ đã được đưa vào phạm vi dùng chung theo những điều kiện đã xác lập. Đây là mẫu nghiên cứu thật, kèm thông tin quy kết và cơ sở sử dụng.

**Dữ liệu theo tenant** là dữ liệu nghiệp vụ được tạo và quản lý trong phạm vi một tenant.

**Bảng 2-14. Ba phạm vi quản trị dữ liệu**

| Phạm vi | Nội dung điển hình | Chủ thể quản trị chính | Loại quyền chi phối |
|---|---|---|---|
| Danh mục/cấu hình hệ thống | cấu hình nền tảng, danh mục chuẩn dùng làm điểm xuất phát | nhà vận hành nền tảng | quyền vận hành kỹ thuật |
| Dữ liệu dùng chung cộng đồng | dữ liệu được đóng góp để chia sẻ theo điều kiện đã xác lập | cơ chế quản trị cộng đồng/nền tảng trong phạm vi quyền được cấp | quyền khai thác trong khuôn khổ điều kiện đóng góp |
| Dữ liệu theo tenant | dữ liệu nghiệp vụ được tạo và quản lý trong một tenant | tenant tương ứng theo quyền và nghĩa vụ đã xác lập | quyền của tenant, giới hạn bởi nghĩa vụ với chủ thể dữ liệu |

*Nguồn: tác giả tổng hợp.*

Sự phân biệt quan trọng nhất là giữa **danh mục hệ thống** và **dữ liệu dùng chung cộng đồng**, vì hai loại này dễ bị gộp dưới cùng một tên gọi. Danh mục hệ thống là cấu hình kỹ thuật: nó xác định những ngôn ngữ, phương ngữ, lớp hoặc hồ sơ nào có thể được dùng làm điểm xuất phát. Dữ liệu dùng chung cộng đồng lại bao gồm mẫu nghiên cứu cùng thông tin quy kết, cơ sở sử dụng và các điều kiện quản trị. Việc gọi cả hai bằng một tên chung dễ làm nhòe ranh giới giữa quyền vận hành nền tảng và quyền được khai thác dữ liệu. Có thể phát biểu:

\[
\text{Cấu hình hệ thống} \neq \text{Dữ liệu dùng chung} \neq \text{Dữ liệu riêng của tenant}.
\]

Nguyên tắc cần giữ là: **quyền quản trị hạ tầng không tự tạo ra quyền khai thác dữ liệu**. Một tài khoản có quyền vận hành máy chủ hoặc quản trị cấu hình không vì thế mặc nhiên được phép công bố hoặc tái sử dụng mọi dữ liệu có trên hệ thống. Quyền truy cập kỹ thuật, cơ sở xử lý dữ liệu cá nhân, quyền đóng góp và giấy phép tái sử dụng là các lớp khác nhau; chúng được phân tách rõ hơn ở mục 2.9.2.

Một hệ quả thiết kế cần rút ra ngay: phạm vi dùng để **khởi tạo** một tenant mới và phạm vi **dùng chung cộng đồng** không nên là cùng một thực thể. Phạm vi thứ nhất là nguồn sao chép ban đầu; phạm vi thứ hai là kho dữ liệu nghiệp vụ có điều kiện sử dụng. Gộp hai vai này khiến việc thay đổi danh mục chuẩn vô tình trở thành thay đổi dữ liệu cộng đồng, và ngược lại.

### 2.3.2. Dùng chung không có nghĩa là không có phạm vi

Một bất biến khái niệm cần được phát biểu tường minh, vì đây là chỗ mà một suy diễn sai sẽ vô hiệu hóa toàn bộ cơ chế của mục 2.4:

\[
\text{Dùng chung} \neq \text{Không có phạm vi}.
\]

Dữ liệu dùng chung cộng đồng là một **phạm vi được quản trị tường minh**, không phải trạng thái vắng mặt của phạm vi. Từ đó rút ra ba hệ quả.

Thứ nhất, phạm vi cộng đồng **không phải là hợp của các phạm vi riêng**. Một khung nhìn cộng đồng không được hiện thực bằng cách bỏ điều kiện lọc theo tenant, vì làm như vậy biến "dùng chung" thành "không cô lập" và mọi dữ liệu riêng đều lọt vào. Dữ liệu chỉ thuộc phạm vi cộng đồng khi nó đã **được đưa vào** phạm vi đó qua một hành động có chủ đích và có điều kiện.

Thứ hai, **tư cách thành viên trong phạm vi cộng đồng không tự cấp quyền**. Đây là hệ quả của cùng nguyên tắc đã nêu ở mục 2.5.1: thuộc về một phạm vi và được phép hành động trong phạm vi đó là hai điều khác nhau. Việc một người dùng có quyền đọc dữ liệu cộng đồng không hàm ý họ được đóng góp, sửa hay công bố lại dữ liệu đó.

Thứ ba, khả năng nhìn thấy rộng hơn **không nới lỏng các nghĩa vụ ở mục 2.9**. Một mẫu được chia sẻ trong phạm vi cộng đồng vẫn mang theo cơ sở xử lý và phạm vi đồng thuận của chính nó; việc nó dùng chung không mở rộng những điều kiện đó.

Cách biểu diễn phạm vi cộng đồng trong lược đồ là quyết định của Chương 3. Điều cần giữ ở mức lý thuyết là phạm vi cộng đồng phải là một phạm vi **có thể kiểm tra được**, chứ không phải một ngoại lệ của cơ chế kiểm tra.

### 2.3.3. Dữ liệu dùng chung cộng đồng như một data commons

Data commons có thể được hiểu là một môi trường kết hợp dữ liệu với hạ tầng, dịch vụ và cơ chế quản trị nhằm phục vụ một cộng đồng sử dụng \cite{grossman_case_2016}. Có thể diễn đạt khái niệm này dưới dạng bốn thành phần không thể thiếu thành phần nào:

\[
\text{Data commons} = \text{Dữ liệu} + \text{Hạ tầng} + \text{Cơ chế quản trị} + \text{Cộng đồng}.
\]

Cách hiểu này loại trừ một cách hiểu phổ biến nhưng sai: commons không phải "một thư mục dùng chung ai cũng đọc được" — đúng bất biến đã nêu ở mục 2.3.2. Điểm quan trọng của khái niệm không nằm ở việc đặt nhiều tệp vào cùng một kho, mà ở việc xác lập các quy tắc về đóng góp, truy cập, sử dụng, trách nhiệm và duy trì tài nguyên. Các nghiên cứu về knowledge commons nhấn mạnh vai trò của quy tắc và thiết chế quản trị đối với tài nguyên tri thức dùng chung \cite{hess_understanding_2007}.

Đối với dữ liệu ngôn ngữ ký hiệu, yêu cầu tham gia của cộng đồng liên quan còn có cơ sở từ các nghiên cứu nhấn mạnh sự cần thiết của góc nhìn liên ngành và sự tham gia của cộng đồng người Điếc trong công nghệ ngôn ngữ ký hiệu \cite{bragg_sign_2019}. Thành phần "cộng đồng" trong công thức trên vì vậy không phải yếu tố trang trí: nó là điều kiện để các quy tắc quản trị có tính chính đáng đối với chính những người mà dữ liệu mô tả.

Từ góc độ lược đồ, một commons có quản trị cần có khả năng trả lời tối thiểu năm câu hỏi: mẫu này bắt nguồn từ đâu; ai là chủ thể liên quan; mẫu được đóng góp trong bối cảnh nào; phiên bản và trạng thái nào đang được dùng; điều kiện nào cho phép truy cập hoặc phân phối. Nếu những thông tin này chỉ tồn tại trong tài liệu ngoài hệ thống, khả năng cưỡng chế và kiểm toán sẽ yếu hơn so với khi chúng được biểu diễn bằng các quan hệ có thể truy vấn. Đây chính là cầu nối giữa mục này và mục 2.9: quản trị cộng đồng chỉ có hiệu lực kỹ thuật khi các điều kiện của nó là dữ liệu, không phải văn bản.

Cách hiện thực dữ liệu dùng chung cộng đồng trong hệ thống — chẳng hạn ánh xạ nó vào loại phạm vi nào, luồng phê duyệt nào và policy nào — là quyết định thiết kế của Chương 3, không phải tính chất phổ quát của data commons.

Cần thêm một bất biến nữa, vì bốn thành phần trong công thức trên rất dễ bị đọc thành một tuyên bố về hiện trạng:

\[
\text{Khái niệm commons} \neq \text{Hiện thực hoá ở thời gian chạy}.
\]

Một hệ thống có thể **đăng ký** một phạm vi cộng đồng — đặt tên nó, dành riêng nó, cho nó một vị trí trong mô hình phân quyền — mà chưa vận hành đầy đủ vòng đời đóng góp, công bố và rút lui trên phạm vi đó. Hai trạng thái ấy khác nhau, và khoảng cách giữa chúng là khoảng cách giữa một phạm vi đã được định nghĩa và một miền dữ liệu đang hoạt động.

Vì vậy Chương 2 mô tả commons như một **phạm vi được quản trị** ở mức khái niệm. Nó không phát biểu rằng một commons dữ liệu ngôn ngữ ký hiệu đã vận hành đầy đủ trong hệ thống nào; mức độ hiện thực hoá thuộc Chương 3, và phát biểu về nó phải nêu rõ phần nào đã có, phần nào mới là phạm vi đã đăng ký.

### 2.3.4. Ba cách chia sẻ danh mục giữa nền tảng và tenant

Một tenant mới thường cần bắt đầu từ danh mục chuẩn của nền tảng thay vì từ một danh mục rỗng. Có ba cách tổ chức quan hệ này, khác nhau ở chỗ **kết quả phân giải một mục danh mục phụ thuộc vào cái gì**.

**Cách A — Danh mục toàn cục dùng chung lúc chạy.** Tenant không giữ bản sao; mọi truy vấn đều đọc trực tiếp danh mục hiện hành của nền tảng. Không phát sinh trùng lặp dữ liệu, và một cập nhật ở nền tảng có hiệu lực ngay với mọi tenant. Đổi lại, tenant hoàn toàn phụ thuộc vào trạng thái toàn cục: nó không thể mở rộng danh mục theo nhu cầu riêng, và một thay đổi ở thượng nguồn làm thay đổi kết quả ở hạ nguồn mà tenant không tham gia quyết định.

**Cách B — Danh mục cha kết hợp tra cứu dự phòng lúc chạy.** Tenant chỉ lưu phần khác biệt của mình; khi không tìm thấy một mục trong phạm vi riêng, hệ thống quay về tra cứu danh mục hệ thống hiện tại:

\[
\text{Tra cứu ở tenant} \rightarrow \text{nếu thiếu} \rightarrow \text{Tra cứu ở danh mục toàn cục}.
\]

Cách này tiết kiệm bản sao và cho phép tùy biến một phần. Nhược điểm nằm ở chỗ khó thấy: **kết quả phân giải phụ thuộc vào thời điểm truy vấn**. Cùng một truy vấn, cùng dữ liệu riêng không đổi, vẫn có thể cho hai kết quả khác nhau ở hai thời điểm nếu danh mục gốc đã thay đổi ở giữa. Với dữ liệu nghiên cứu, đây là một khiếm khuyết nghiêm trọng vì nó phá vỡ khả năng tái lập mà không để lại dấu vết: không có bản ghi nào cho biết kết quả đã thay đổi.

**Cách C — Sao chép một lần tại một phiên bản xác định và ghi nhận nguồn.** Tenant nhận một ảnh chụp danh mục tại một phiên bản cụ thể, sau đó quản lý bản sao đó trong phạm vi của mình:

\[
\text{DanhMucNguon}(v_k) \xrightarrow{\ \text{sao chép một lần}\ } \text{DanhMucTenant}.
\]

Sau thời điểm sao chép, tenant phát triển danh mục riêng độc lập; một cập nhật ở nguồn **không tự động** thay đổi danh mục của tenant. Khi một bộ dữ liệu được công bố, nó ghim vào một phiên bản danh mục cụ thể. Chi phí là trùng lặp siêu dữ liệu và nhu cầu quản lý quan hệ nguồn – phiên bản; đây là một trường hợp của phi chuẩn hóa có chủ đích đã phân tích ở mục 2.1.6.

**Bảng 2-15. So sánh ba cách chia sẻ danh mục giữa nền tảng và tenant**

| Tiêu chí | A. Dùng chung lúc chạy | B. Tra cứu dự phòng | C. Sao chép có ghim phiên bản |
|---|---|---|---|
| Mức độ độc lập của tenant | Thấp | Trung bình | Cao |
| Cập nhật ở nguồn ảnh hưởng tenant | Trực tiếp và tức thì | Có thể, không báo trước | Không ngầm; chỉ khi tenant chủ động cập nhật |
| Kết quả phân giải phụ thuộc thời điểm | Có | **Có** | Không |
| Khả năng tái lập của bộ dữ liệu | Thấp | Trung bình | Cao |
| Điều kiện tiên quyết để có hiệu lực | — | — | **Phiên bản được ghim phải bất biến** |
| Định hướng phù hợp với yêu cầu tái lập | | | **Được chọn** |

*Nguồn: tác giả tổng hợp; tiêu chí phân biệt chính là sự phụ thuộc của kết quả phân giải vào trạng thái thượng nguồn tại thời điểm truy vấn.*

Bảng trên giữ sáu tiêu chí. Bản đầy đủ, gồm chi phí lưu trữ, khả năng tuỳ biến danh mục riêng và khả năng truy vết nguồn gốc của từng mục danh mục, được trình bày tại **Phụ lục F.3, Bảng F-2**.

**Định hướng được chọn và lý do.** Yêu cầu chi phối ở đây là khả năng tái lập: một bộ dữ liệu đã dùng cho một thí nghiệm phải truy lại được **đúng không gian nhãn** đã sử dụng. Cách A và cách B đều để kết quả phân giải phụ thuộc trạng thái thượng nguồn tại thời điểm truy vấn, nên cả hai đều không thỏa mãn yêu cầu này. Cách C thỏa mãn, đồng thời cho phép tenant mở rộng danh mục riêng mà không phải sửa danh mục gốc — một nhu cầu thực tế khi các đơn vị khác nhau ghi nhận những biến thể phương ngữ khác nhau.

**Một bất biến rút ra từ so sánh trên.** Khác biệt giữa cách B và cách C không phải khác biệt về chi phí lưu trữ mà về **thời điểm** quan hệ với danh mục gốc phát huy tác dụng:

\[
\text{Kế thừa lúc TẠO} \neq \text{Tra cứu dự phòng lúc CHẠY}.
\]

Cách C dùng danh mục nền tảng làm **nguồn khởi tạo**: quan hệ ấy phát huy tác dụng đúng một lần, tại thời điểm tạo, và sau đó chấm dứt. Cách B dùng nó làm **đường lùi khi truy vấn**: quan hệ ấy phát huy tác dụng ở mọi lượt đọc, mãi mãi. Hai cơ chế nghe gần nhau vì cùng mô tả "tenant thừa hưởng danh mục chung", nhưng chỉ cơ chế thứ hai làm kết quả phân giải phụ thuộc trạng thái thượng nguồn.

Phân biệt này còn có hệ quả về an toàn ngoài phạm vi tái lập: một đường lùi lúc chạy là một đường mà truy vấn của tenant này có thể chạm tới dữ liệu ngoài phạm vi của nó. Đó là lý do bất biến trên được phát biểu ở đây chứ không chỉ ở mục 2.8, và vì sao nó phải được giữ cùng bất biến \(\text{Dùng chung} \neq \text{Không có phạm vi}\) ở mục 2.3.2.

**Đánh đổi và điều kiện tiên quyết.** Chi phí trực tiếp là trùng lặp siêu dữ liệu và nghĩa vụ quản lý quan hệ giữa bản sao và nguồn. Nhưng ràng buộc quan trọng hơn là một điều kiện tiên quyết: **cơ chế ghim chỉ có ý nghĩa khi phiên bản được ghim là bất biến**. Nếu cùng một số phiên bản có thể trỏ tới nội dung khác sau một lần cập nhật, tham chiếu phiên bản không còn bảo đảm khả năng tái lập, và cách C suy thoái về đúng vấn đề của cách B, nhưng khó phát hiện hơn vì tham chiếu vẫn trông ổn định. Vì vậy lựa chọn ở mục này **phụ thuộc trực tiếp** vào cơ chế phiên bản bất biến trình bày ở mục 2.8.1.

> ### ▣ HÌNH 2-4 — Ba cách chia sẻ danh mục và sự phụ thuộc vào trạng thái thượng nguồn
> **Loại:** sơ đồ ba nhánh có trục thời gian · **Công cụ đề nghị:** draw.io
> **Phải thể hiện:** ba nhánh A, B, C; mỗi nhánh vẽ danh mục nền tảng ở trên, tenant ở dưới, và **hai mốc thời gian** t₁ và t₂ với một thay đổi ở danh mục nền tảng xảy ra giữa hai mốc; kết quả phân giải cùng một truy vấn tại t₁ và t₂ được ghi rõ ở mỗi nhánh — nhánh A và B **đổi kết quả**, nhánh C **giữ nguyên**; ở nhánh C ghi thêm điều kiện tiên quyết "phiên bản được ghim phải bất biến (mục 2.8.1)".
> **Chú thích dưới hình:** *Hình 2-4: Ba cách chia sẻ danh mục và sự phụ thuộc của kết quả phân giải vào trạng thái thượng nguồn.*

### 2.3.5. Danh mục, bộ dữ liệu và tạo tác nghiên cứu

Ba khái niệm cần được phân biệt:

- **Danh mục (catalog/registry)** xác định không gian nhãn và các quan hệ miền, chẳng hạn ngôn ngữ, phương ngữ, lớp ký hiệu và hồ sơ nhận dạng.
- **Bộ dữ liệu (dataset)** xác định tập mẫu cùng siêu dữ liệu và phiên bản danh mục được sử dụng.
- **Tạo tác nghiên cứu (research artifact)**, trong phạm vi luận văn, là sản phẩm đã được công bố ở một phiên bản có thể kiểm chứng, chẳng hạn gói bộ dữ liệu, bản kê, tệp đặc trưng hoặc kết quả dẫn xuất cần được tham chiếu ổn định.

Theo định nghĩa nội bộ này, một phiên bản bộ dữ liệu đã công bố là một trường hợp của tạo tác nghiên cứu. "Artifact" không được dùng như một khái niệm bao trùm cho mọi đối tượng tạm thời trong hệ thống; chỉ những sản phẩm cần vòng đời công bố, phiên bản và kiểm chứng mới thuộc phạm vi này.

## 2.4. Cưỡng chế cô lập tenant

Mục 2.2.7 kết thúc bằng một nghĩa vụ: khi chọn lược đồ dùng chung, hệ thống phải có cơ chế cô lập đặt tại vị trí mà mã nghiệp vụ không thể vô tình bỏ qua. Mục này xác định vị trí đó bằng cách xét lần lượt các chiến lược khả dĩ, và — quan trọng không kém — xác định **phát biểu về bảo mật nào là hợp lệ** đối với từng chiến lược.

### 2.4.1. Cô lập không phải một tầng duy nhất

Một sai lầm thường gặp là đồng nhất "cô lập tenant" với "cô lập ở cơ sở dữ liệu". Trên thực tế, dữ liệu của một tenant đi qua nhiều thành phần, và ranh giới phải tồn tại ở mọi nơi dữ liệu đi qua. Có thể phân biệt năm tầng.

**Bảng 2-16. Năm tầng cần cô lập và câu hỏi mà mỗi tầng trả lời**

| Tầng | Câu hỏi cần trả lời | Hệ quả nếu tầng này thiếu ranh giới |
|---|---|---|
| Ứng dụng | Yêu cầu này đang hành động thay mặt tenant nào? | Ngữ cảnh sai được truyền xuống mọi tầng dưới |
| Phân quyền | Chủ thể có được thực hiện hành động này trong phạm vi này không? | Thành viên của tenant A thực hiện thao tác quản trị của tenant B |
| Cơ sở dữ liệu | Truy vấn này được chạm tới những hàng nào? | Một truy vấn sót điều kiện lọc trả về dữ liệu ngoài tenant |
| Kho nội dung ngoài CSDL | Yêu cầu này được đọc những tệp nào? | Siêu dữ liệu được bảo vệ nhưng nội dung tải về tự do bằng khóa tệp |
| Tác vụ nền | Tác vụ chạy ngoài ngữ cảnh yêu cầu thuộc phạm vi nào? | Worker chạy với quyền rộng, xử lý nhầm dữ liệu của tenant khác |

*Nguồn: tác giả tổng hợp từ \cite{krebs_architectural_2012,saltzer_protection_1975}.*

Hai tầng cuối thường bị bỏ sót. Kho nội dung nằm ngoài phạm vi cưỡng chế của cơ sở dữ liệu, như đã nêu ở mục 2.2.9. Tác vụ nền thì chạy **ngoài vòng đời của một yêu cầu HTTP**, nên không tự nhiên thừa hưởng ngữ cảnh tenant từ phiên người dùng; nếu thiết kế không quy định rõ tác vụ nền lấy ngữ cảnh từ đâu, cách cài đặt đơn giản nhất là cho worker chạy với quyền rộng, và khi đó ranh giới ở ba tầng trên không còn hiệu lực đối với mọi dữ liệu đi qua worker.

> ### ▣ HÌNH 2-5 — Năm tầng cần cô lập trên đường đi của một yêu cầu
> **Loại:** sơ đồ luồng có các trạm kiểm soát · **Công cụ đề nghị:** draw.io
> **Phải thể hiện:** đường đi của một yêu cầu từ trình duyệt qua ứng dụng → phân quyền → cơ sở dữ liệu, và một nhánh rẽ sang kho nội dung ngoài cùng một nhánh rẽ sang hàng đợi/tác vụ nền; mỗi tầng là một **trạm kiểm soát** ghi câu hỏi mà nó trả lời; hai nhánh rẽ được tô nhấn kèm chú "hai tầng thường bị bỏ sót — không thừa hưởng ngữ cảnh của yêu cầu".
> **Chú thích dưới hình:** *Hình 2-5: Năm tầng cần cô lập trên đường đi của một yêu cầu và hai nhánh thường bị bỏ sót.*

### 2.4.2. Lọc ở tầng ứng dụng

Cách trực tiếp nhất: ứng dụng xác định tenant hiện hành từ phiên, rồi thêm điều kiện phạm vi vào từng truy vấn.

**Ưu điểm.** Dễ hiểu và dễ triển khai, không đòi hỏi năng lực đặc biệt của hệ quản trị cơ sở dữ liệu, và linh hoạt vì lập trình viên kiểm soát hoàn toàn từng truy vấn. Cách này cũng dễ dàng biểu diễn những trường hợp ngoại lệ hợp lệ.

**Nhược điểm.** Tính đúng đắn của cơ chế bảo vệ trở thành **tính đúng đắn của mọi đường truy vấn trong toàn hệ thống**. Ba đặc điểm khiến đây là một điểm yếu có tính hệ thống chứ không phải một rủi ro thông thường.

Thứ nhất, nghĩa vụ là **phân tán và lặp lại**: mỗi truy vấn mới là một cơ hội sót mới, và số cơ hội tăng theo kích thước mã nguồn.

Thứ hai, **lỗi không sinh triệu chứng**. Một truy vấn sót điều kiện phạm vi vẫn chạy, vẫn trả kết quả, chỉ là trả nhiều hơn mức được phép. Không có ngoại lệ nào được ném, không có bản ghi lỗi nào được sinh ra. Lỗi loại này thường chỉ lộ ra khi một người dùng tình cờ nhìn thấy dữ liệu không thuộc về mình.

Thứ ba, và là điểm quyết định, **cơ chế phụ thuộc vào trí nhớ của người viết mã trong tương lai**. Một quy ước được thiết lập hôm nay không ràng buộc được hàm sẽ được viết sáu tháng sau bởi người chưa từng đọc quy ước đó. Vì vậy khả năng bảo vệ suy giảm theo thời gian và theo số lượng người tham gia, ngay cả khi không có thay đổi nào về kiến trúc.

Đặc tính của lớp lỗi này quyết định vì sao lọc ở tầng ứng dụng không đủ. Lỗi thiếu điều kiện lọc theo phạm vi có ba tính chất bất lợi cùng lúc: nó **phân tán** — có thể xuất hiện ở bất kỳ truy vấn nào trong hệ thống; nó **im lặng** — một truy vấn thiếu điều kiện vẫn chạy đúng cú pháp và trả về kết quả trông hợp lệ; và số cơ hội mắc lỗi **tăng theo số đường truy vấn**, tức tăng liên tục suốt vòng đời hệ thống. Một cơ chế phòng vệ dựa trên việc mọi truy vấn đều được viết đúng vì vậy yếu dần theo thời gian, kể cả khi quy ước ban đầu được phát biểu rõ ràng.

### 2.4.3. Gán phạm vi tự động ở tầng trung gian

Một cải tiến tự nhiên là chuyển nghĩa vụ từ từng truy vấn lên một lớp chung: tầng trung gian phân giải tenant từ phiên, và tầng truy cập dữ liệu tự động chèn điều kiện phạm vi.

**Ưu điểm.** Loại bỏ phần lớn sự lặp lại, tập trung logic phạm vi vào một chỗ có thể rà soát được, và giảm đáng kể xác suất sót so với cách lọc thủ công.

**Nhược điểm.** Cơ chế vẫn nằm **hoàn toàn ở tầng ứng dụng**, nên nó bảo vệ được đúng những đường đi qua nó. Ba lối vòng vẫn mở: truy vấn SQL thô không đi qua lớp trừu tượng; các hàm tiện ích hoặc kịch bản bảo trì gọi thẳng xuống cơ sở dữ liệu; và các tác vụ nền được thiết kế chạy ngoài ngữ cảnh yêu cầu. Nói cách khác, cải tiến này làm cho **con đường đúng trở nên dễ đi hơn**, nhưng không loại bỏ được con đường sai.

### 2.4.4. Cưỡng chế ở tầng cơ sở dữ liệu

Chiến lược thứ ba đưa chính cơ sở dữ liệu vào việc quyết định hàng nào được truy cập. Row-Level Security (RLS) là cơ chế kiểm soát truy cập ở cấp hàng của PostgreSQL. Khi RLS được bật, policy có thể giới hạn những hàng mà một vai được phép nhìn thấy hoặc tác động; nếu không có policy cho phép phù hợp, PostgreSQL áp dụng hành vi mặc định từ chối \cite{postgresql_rls_2026}. Thành phần `USING` xác định tập hàng hiện hữu có thể được truy cập hoặc tác động, còn `WITH CHECK` kiểm tra trạng thái mới do thao tác `INSERT` hoặc `UPDATE` tạo ra \cite{postgresql_rls_2026}.

Với bảng đa thuê bao, điều kiện cơ bản là hàng chỉ thuộc phạm vi truy cập khi khóa phạm vi khớp với tenant hiện hành. Điểm quan trọng không nằm ở biểu thức so sánh — biểu thức đó giống hệt điều kiện lọc mà cách 2.4.2 yêu cầu lập trình viên viết tay — mà nằm ở **vị trí cưỡng chế**. Policy được cơ sở dữ liệu áp dụng cho mọi truy vấn trên bảng, bất kể truy vấn đó do lớp trừu tượng sinh ra, do một hàm tiện ích viết tay, hay do một kịch bản bảo trì gõ trực tiếp.

Có thể tóm tắt sự dịch chuyển này như sau: ở tầng ứng dụng, điều kiện phạm vi là thứ mà **truy vấn phải nhớ mang theo**; ở tầng cơ sở dữ liệu, nó là thứ mà **truy vấn không thể bỏ lại**. Tuy nhiên, phát biểu này chỉ đúng trong một phạm vi giả định cụ thể, và mục 2.4.5 xác định phạm vi đó trước khi các mục sau sử dụng kết luận.

### 2.4.5. Mô hình đe dọa và ranh giới tin cậy

Một phát biểu về bảo mật chỉ có nghĩa khi kèm theo mô hình đe dọa: nó bảo vệ chống lại **ai**, có **năng lực gì**, và với giả định nào về những thành phần được tin cậy \cite{shostack_threat_2014}. Không có mô hình đe dọa, các phát biểu dạng "cơ chế này khiến điều đó không thể xảy ra" là những phát biểu không kiểm chứng được — và trong phần lớn trường hợp là những phát biểu quá mạnh.

**Cơ sở tính toán được tin cậy (trusted computing base)** của cơ chế đang xét gồm ba thành phần: hệ quản trị cơ sở dữ liệu và cơ chế policy của nó; thành phần đặt ngữ cảnh tenant cho mỗi đơn vị công việc; và cấu hình quyền của vai runtime. Mọi phát biểu dưới đây có hiệu lực **khi và chỉ khi** ba thành phần này chưa bị chiếm quyền.

**Mô hình đe dọa I — máy khách không được tin cậy.** Kẻ tấn công có một tài khoản hợp lệ hoặc một token, có thể sửa nội dung yêu cầu, đoán định danh tài nguyên, gọi các điểm cuối không theo trình tự dự kiến; nhưng **không có thông tin xác thực của cơ sở dữ liệu** và không thực thi được SQL tùy ý dưới vai runtime. Đây là mô hình đe dọa tương ứng với một dịch vụ web công khai, và là mô hình mà phần lớn rủi ro thực tế nằm trong đó.

Trong mô hình này, khi thành phần được tin cậy đặt ngữ cảnh tenant là A, một truy vấn sót điều kiện lọc vẫn bị policy giới hạn về phạm vi của A. Phát biểu hợp lệ: cơ chế **loại bỏ lớp lỗi "quên lọc theo tenant"** khỏi trách nhiệm của từng truy vấn nghiệp vụ.

**Mô hình đe dọa II — thông tin xác thực cơ sở dữ liệu của ứng dụng bị lộ.** Kẻ tấn công thực thi được SQL tùy ý dưới chính vai mà ứng dụng dùng. Khi đó, nếu đầu vào của policy là một biến ngữ cảnh mà chính vai đó đặt được, kẻ tấn công cũng đặt được biến đó và tự chọn phạm vi cho mình. Cơ chế **không** cung cấp bảo đảm ở mức tương đương mô hình I. Điều nó vẫn cung cấp là hạn chế những gì vai runtime làm được so với một vai có toàn quyền — đây là lý do nguyên lý đặc quyền tối thiểu ở mục 2.4.7 vẫn có giá trị trong mô hình này, dù không phải giá trị tuyệt đối.

**Bảng 2-17. Phạm vi bảo đảm của các cơ chế theo mô hình đe dọa**

| Dạng đe dọa | Lọc ở tầng ứng dụng | Cưỡng chế ở CSDL với ngữ cảnh do thành phần tin cậy đặt | Tách hạ tầng vật lý |
|---|---|---|---|
| Lập trình viên quên điều kiện lọc theo tenant | Không bảo vệ | **Bảo vệ** | Bảo vệ |
| Máy khách sửa yêu cầu, khai báo tenant khác | Phụ thuộc mã ứng dụng | **Bảo vệ**, nếu thành phần đặt ngữ cảnh đáng tin | Bảo vệ |
| Truy vấn SQL thô hoặc kịch bản bảo trì chạy dưới vai runtime | Không bảo vệ | **Bảo vệ** đối với lỗi thiếu lọc | Bảo vệ |
| Kẻ tấn công thực thi SQL tùy ý dưới vai runtime | Không bảo vệ | **Không bảo vệ ở mức tương đương** — đặt lại được ngữ cảnh | Bảo vệ |
| Vai sở hữu lược đồ hoặc superuser bị chiếm | Không bảo vệ | Không bảo vệ | Tùy phạm vi bị chiếm |

*Nguồn: tác giả tổng hợp theo nguyên tắc phát biểu bảo mật kèm mô hình đe dọa của \cite{shostack_threat_2014}, kết hợp hành vi cơ chế theo \cite{postgresql_rls_2026}.*

Hệ quả về **cách phát biểu kết quả**, và đây là điểm phải giữ nhất quán ở Chương 3, Chương 4 và phần Kết luận. Không viết:

> Cưỡng chế ở tầng cơ sở dữ liệu làm cho đường truy vấn sai trở thành **bất khả thi**.

Mà viết:

> Cưỡng chế ở tầng cơ sở dữ liệu **đưa điều kiện phạm vi ra khỏi trách nhiệm của truy vấn nghiệp vụ thông thường** và loại bỏ lớp lỗi thiếu điều kiện lọc, **trong phạm vi mô hình đe dọa và ranh giới tin cậy đã nêu**.

Phát biểu thứ hai yếu hơn nhưng đúng, và nó vẫn là một phát biểu mạnh: lớp lỗi mà nó loại bỏ chính là lớp lỗi phân tán, im lặng và tăng theo số đường truy vấn đã mô tả ở mục 2.4.2 — tức lớp lỗi mà một quy ước lập trình khó chống lại nhất. Bằng chứng thực nghiệm về việc lớp lỗi này có xuất hiện hay không trong một hệ thống cụ thể thuộc phạm vi Chương 4.

> ### ▣ HÌNH 2-6 — Hai mô hình đe dọa và ranh giới tin cậy của cơ chế cô lập
> **Loại:** sơ đồ ranh giới tin cậy · **Công cụ đề nghị:** draw.io
> **Phải thể hiện:** một đường bao **cơ sở tính toán được tin cậy** chứa ba thành phần (hệ quản trị CSDL và policy; thành phần đặt ngữ cảnh tenant; cấu hình quyền của vai runtime); bên ngoài đường bao là máy khách và mạng; hai mũi tên tấn công — mũi tên I xuất phát từ **ngoài** đường bao và bị chặn ở policy; mũi tên II xuất phát từ **bên trong** đường bao (chiếm được thông tin xác thực CSDL) và **đi qua**, kèm chú "ngoài phạm vi bảo đảm — xem Bảng 2-17".
> **Chú thích dưới hình:** *Hình 2-6: Hai mô hình đe dọa và ranh giới tin cậy của cơ chế cô lập ở tầng cơ sở dữ liệu.*

### 2.4.6. Mặc định từ chối và thiết kế fail-closed

Một cơ chế cưỡng chế còn phải trả lời câu hỏi: điều gì xảy ra khi thông tin cần thiết để ra quyết định **không có**? Hai khả năng đối lập:

\[
\text{Thiếu ngữ cảnh} \Rightarrow \text{Truy cập không giới hạn} \quad (\textit{fail-open}),
\]
\[
\text{Thiếu ngữ cảnh tenant} \Rightarrow \text{Không có dữ liệu tenant nào} \quad (\textit{fail-closed}).
\]

Nguyên lý *fail-safe defaults* yêu cầu trạng thái mặc định của cơ chế bảo vệ là từ chối và quyền chỉ được cấp khi có điều kiện cho phép tường minh \cite{saltzer_protection_1975}. Lý do khiến fail-open đặc biệt nguy hiểm trong bối cảnh đa thuê bao là nó biến **một lỗi thiếu sót** thành **một sự cố rò rỉ toàn phần**: đường mã quên thiết lập ngữ cảnh không nhận được ít dữ liệu hơn, mà nhận được toàn bộ.

Về mặt cơ chế, nếu ngữ cảnh tenant được đọc theo dạng cho phép giá trị vắng mặt, PostgreSQL có thể trả `NULL` khi biến không tồn tại \cite{postgresql_configfunc_2026}. Khi policy yêu cầu so sánh khóa phạm vi với giá trị này, biểu thức không thể trở thành `TRUE` nếu tenant chưa được thiết lập — vì phép so sánh với `NULL` không cho `TRUE`. Nhờ đó trạng thái thiếu ngữ cảnh được thiết kế theo hướng không trả hàng nào thay vì vô tình mở toàn bộ bảng. Mục tiêu thiết kế có thể biểu diễn:

\[
current\_tenant = \varnothing \Rightarrow AccessibleRows = \varnothing.
\]

Một lựa chọn thay thế là đọc ngữ cảnh theo dạng bắt buộc phải có, khiến biến chưa gán ném lỗi. Cách này nghe có vẻ an toàn hơn vì nó ồn ào hơn, nhưng nó biến mọi công việc nền hợp lệ chưa gán ngữ cảnh thành lỗi hệ thống. Đánh đổi giữa hai dạng fail-closed — im lặng trả về rỗng, hay ồn ào ném lỗi — là một quyết định thiết kế thật, và nó được phân tích ở Chương 3 cùng với bối cảnh vận hành cụ thể.

Đây là mục tiêu thiết kế của policy; tính đúng đắn cuối cùng vẫn cần được kiểm thử bằng hành vi dưới đúng vai runtime, như trình bày ở mục 2.4.8.

### 2.4.7. Phạm vi giao dịch và connection pooling

Ứng dụng web thường sử dụng connection pool để tái sử dụng kết nối cơ sở dữ liệu giữa nhiều yêu cầu. Điều này tạo ra một vấn đề đặc thù cho mọi cơ chế cô lập dựa trên ngữ cảnh phiên: **ngữ cảnh có vòng đời dài hơn yêu cầu đã đặt ra nó**.

PostgreSQL phân biệt thiết lập ở phạm vi phiên với thiết lập cục bộ trong giao dịch; `SET LOCAL` chỉ có hiệu lực tới khi giao dịch hiện hành kết thúc \cite{postgresql_set_2026}. Nếu ngữ cảnh tenant được lưu ở phạm vi phiên trên một kết nối tái sử dụng, kết nối có thể mang giá trị của yêu cầu trước sang yêu cầu sau. Hệ quả là một yêu cầu của tenant B, chạy trên kết nối vừa phục vụ tenant A và chưa được đặt lại, có thể thao tác trong ngữ cảnh của tenant A. Đây là dạng lỗi khó phát hiện nhất trong cả nhóm: nó phụ thuộc thứ tự yêu cầu và trạng thái bể kết nối, nên **không tái hiện được một cách ổn định** và không sinh ra thông báo lỗi nào.

Vì vậy, ngữ cảnh tenant nên có vòng đời trùng với đơn vị giao dịch nghiệp vụ: bắt đầu giao dịch, thiết lập tenant ở phạm vi cục bộ, thực hiện các truy vấn, sau đó kết thúc giao dịch. Khi kết nối quay về pool, ngữ cảnh cục bộ không tiếp tục tồn tại như trạng thái phiên dài hạn. Cách tổ chức này phù hợp với *complete mediation*: mỗi đơn vị truy cập được đánh giá trong ngữ cảnh của chính nó thay vì thừa hưởng trạng thái an ninh từ lần sử dụng kết nối trước \cite{saltzer_protection_1975}. Nó cũng gắn ranh giới an ninh vào **ranh giới giao dịch** — khái niệm được trình bày ở mục 2.7.3.

Kết hợp với fail-closed ở mục 2.4.6, lỗi quên thiết lập tenant biểu hiện thành **thiếu dữ liệu**, thay vì trả về dữ liệu ngoài phạm vi — với điều kiện policy, quyền của vai runtime và cách truyền ngữ cảnh đều được cấu hình nhất quán.

### 2.4.8. Vai runtime, đặc quyền tối thiểu và cách kiểm chứng

RLS không tạo ra ranh giới bảo vệ nếu tài khoản mà ứng dụng sử dụng có khả năng bỏ qua cơ chế. PostgreSQL quy định superuser và các vai có thuộc tính `BYPASSRLS` có thể bỏ qua RLS; chủ sở hữu bảng thông thường cũng có thể không chịu RLS trừ khi áp dụng `FORCE ROW LEVEL SECURITY` trong các trường hợp phù hợp \cite{postgresql_rls_2026}. Vì vậy, cấu hình production cần tách vai sở hữu/di trú lược đồ khỏi vai runtime của ứng dụng và áp dụng nguyên lý **đặc quyền tối thiểu (least privilege)** \cite{saltzer_protection_1975}.

Vai runtime chỉ nên có những quyền dữ liệu cần thiết cho ứng dụng, đồng thời không phải superuser, không có `BYPASSRLS` và không có quyền DDL đủ để tự thay đổi cơ chế bảo vệ. Lý do cho điều kiện cuối rất cụ thể: lệnh vô hiệu hóa một policy là một lệnh thay đổi cấu trúc. Một vai vừa ghi được dữ liệu vừa chạy được lệnh cấu trúc thì về nguyên tắc **tự gỡ được vòng vây của chính nó**, và cơ chế bảo đảm suy giảm thành một khuyến nghị. Vai dùng cho migration có thể cần quyền rộng hơn nhưng không nên được dùng cho đường xử lý yêu cầu thông thường.

Từ đây rút ra một nguyên tắc về **cách kiểm chứng**, không chỉ về cách thiết kế. Một kiểm tra chỉ đọc siêu dữ liệu — ví dụ policy có tồn tại hay RLS có được bật — chưa chứng minh ranh giới đang hoạt động dưới tài khoản thật. Nó trả lời câu hỏi "cơ chế đã được khai báo chưa", trong khi câu hỏi cần trả lời là "cơ chế có chặn được không". Phép kiểm có giá trị hơn là kiểm thử hành vi: kết nối bằng chính vai runtime, đặt tenant A, xác nhận không đọc và không ghi được dữ liệu của tenant B; đồng thời xác nhận trạng thái thiếu tenant bị từ chối. Nguyên tắc này chi phối phương pháp đo ở Chương 4.

### 2.4.9. Phòng thủ nhiều lớp và bảng so sánh

Các chiến lược ở trên không loại trừ nhau, và đây là điểm dễ hiểu sai nhất của mục này. Lựa chọn kiến trúc **không phải** "phân quyền ứng dụng *hoặc* cô lập ở cơ sở dữ liệu", mà là tổ hợp:

\[
\text{Xác thực} + \text{Phân quyền} + \text{Ràng buộc lược đồ} + \text{Cô lập ở CSDL} + \text{Phạm vi kho nội dung}.
\]

Mỗi lớp xử lý một loại lỗi khác nhau, và không lớp nào phủ được phần của lớp khác. Phân quyền ứng dụng bắt lỗi "chủ thể này không được làm hành động này". Ràng buộc lược đồ bắt lỗi "quan hệ này không hợp lệ trong phạm vi" (mục 2.2.6). Cô lập ở cơ sở dữ liệu bắt lỗi "truy vấn này quên giới hạn phạm vi". Phạm vi kho nội dung bắt lỗi "khóa tệp tùy ý vẫn tải được nội dung".

**Bảng 2-18. So sánh bốn chiến lược cưỡng chế cô lập dữ liệu**

| Tiêu chí | Lọc ở tầng ứng dụng | Gán phạm vi ở tầng trung gian | Cưỡng chế ở tầng CSDL | Tách hạ tầng vật lý |
|---|---|---|---|---|
| Phụ thuộc vào kỷ luật lập trình viên | Rất cao | Trung bình | Thấp | Thấp |
| Bảo vệ được truy vấn SQL thô | Không | Không | Có | Có |
| Bảo vệ được tác vụ nền và kịch bản bảo trì | Không chắc | Không chắc | Có, nếu chạy dưới vai runtime | Có |
| Hành vi khi thiếu ngữ cảnh | Do mã quyết định, dễ fail-open | Do mã quyết định | Mặc định từ chối, tự nhiên fail-closed | Không phát sinh |
| Khả năng suy giảm theo thời gian | Cao — mã mới có thể sót | Trung bình | Thấp | Thấp |
| Chống được kẻ tấn công có thông tin xác thực CSDL | Không | Không | **Không** (xem Bảng 2-17) | Có |
| Phù hợp với lược đồ dùng chung | Có nhưng yếu | Có, chưa đủ | **Rất phù hợp** | Không phải mô hình đã chọn |

*Nguồn: tác giả tổng hợp từ \cite{postgresql_rls_2026,saltzer_protection_1975,krebs_architectural_2012,bezemer_multi-tenant_2010,shostack_threat_2014}.*

Bảng trên giữ bảy tiêu chí. Bản đầy đủ mười tiêu chí, bổ sung mức độ dễ triển khai, khả năng kiểm chứng bằng kiểm thử hành vi và chi phí vận hành, được trình bày tại **Phụ lục F.4, Bảng F-3**.

**Định hướng được chọn.** Với mô hình lược đồ dùng chung đã chọn ở mục 2.2.7, cưỡng chế ở tầng cơ sở dữ liệu là tầng bảo vệ chính, kết hợp với ràng buộc lược đồ, phân quyền ở tầng ứng dụng và kiểm soát phạm vi ở đường đọc nội dung. Lập luận quyết định là tiêu chí "khả năng suy giảm theo thời gian": một cơ chế dựa vào việc lập trình viên nhớ làm đúng sẽ hỏng ở **hàm được viết sau khi quy ước được đặt ra**, và hỏng theo kiểu không sinh triệu chứng. Đặt cơ chế ở cơ sở dữ liệu bảo vệ luôn cả những đường mã chưa được viết.

**Đánh đổi.** Cách này đòi hỏi năng lực cụ thể của hệ quản trị cơ sở dữ liệu, nên nó ràng buộc lựa chọn công nghệ. Nó làm cho một lớp lỗi cấu hình — quên thiết lập ngữ cảnh — biểu hiện thành dữ liệu rỗng, điều có thể gây nhầm lẫn khi gỡ lỗi. Nó đặt ra một yêu cầu vận hành mới: vai runtime phải được cấu hình đúng và điều đó phải kiểm được bằng truy vấn siêu dữ liệu. Và như Bảng 2-17 đã nêu, **nó không mở rộng bảo đảm sang mô hình đe dọa II**; bảo vệ chống lại việc lộ thông tin xác thực cơ sở dữ liệu là bài toán của quản lý bí mật và kiểm soát truy cập hạ tầng, không phải của policy mức hàng.

Cần khẳng định lại để tránh một cách hiểu sai phổ biến: RLS trả lời câu hỏi **hàng nào có thể được chạm tới**. Nó không trả lời câu hỏi **người dùng có được phép thực hiện hành động nghiệp vụ này hay không**. Hai câu hỏi cần hai lớp kiểm soát khác nhau, dẫn đến mục 2.5.

## 2.5. Quản lý danh tính, kiểm soát truy cập và quy trách nhiệm

### 2.5.1. Xác thực, tư cách thành viên và phân quyền

Ba khái niệm thường bị gộp nhưng trả lời ba câu hỏi khác nhau:

\[
\text{Xác thực} \rightarrow \text{Chủ thể là ai?}
\]
\[
\text{Tư cách thành viên} \rightarrow \text{Chủ thể thuộc phạm vi nào?}
\]
\[
\text{Phân quyền} \rightarrow \text{Chủ thể được làm gì?}
\]

**Xác thực (authentication)** xác định chủ thể đang tương tác với hệ thống. **Tư cách thành viên (membership)** xác định chủ thể thuộc những tenant, workspace hoặc project nào. **Phân quyền (authorization)** quyết định chủ thể đã được xác thực được phép thực hiện hành động nào trên tài nguyên nào và trong phạm vi nào.

Trong kiến trúc đa thuê bao, hai bước suy diễn sai thường xảy ra. Thứ nhất, **đăng nhập thành công không cấp quyền đối với mọi tenant** mà người dùng biết hoặc từng tham gia; nó chỉ xác nhận danh tính. Thứ hai, và tinh vi hơn, **tư cách thành viên không tự đồng nghĩa với quyền**: việc một người thuộc về một phạm vi chỉ đặt họ vào phạm vi đó, chưa nói gì về những hành động họ được thực hiện bên trong. Gộp hai khái niệm này dẫn tới mô hình trong đó mọi thành viên của một tenant có quyền như nhau — đủ dùng cho một nhóm nhỏ, nhưng không biểu diễn được một tổ chức có người thu dữ liệu, người kiểm duyệt và người chỉ đọc. Cùng nguyên tắc này đã được áp dụng cho phạm vi cộng đồng ở mục 2.3.2.

Nguyên tắc mặc định từ chối tiếp tục áp dụng ở tầng ứng dụng: tài nguyên hoặc hành động chưa được khai báo công khai hay chưa có policy cho phép thì không nên truy cập được \cite{saltzer_protection_1975}. Mô hình ngược lại — chỉ chặn những điểm cuối đã biết là nhạy cảm — khiến mỗi tính năng mới có nguy cơ xuất hiện trong trạng thái mở cho tới khi được bổ sung rule. Đây là cùng một lập luận về sự suy giảm theo thời gian đã nêu ở mục 2.4.9, áp cho tầng ứng dụng.

### 2.5.2. Danh sách kiểm soát truy cập (ACL)

Mô hình cơ bản nhất gán quyền trực tiếp cho từng cặp chủ thể – tài nguyên:

\[
(\text{Chủ thể}, \text{Tài nguyên}, \text{Quyền}).
\]

**Ưu điểm.** Rất mịn: có thể diễn đạt chính xác ngoại lệ cho từng đối tượng. Trực quan khi số tài nguyên nhỏ và quan hệ quyền không có cấu trúc chung.

**Nhược điểm.** Số bản ghi cần quản lý tăng theo tích của hai chiều:

\[
|\text{Chủ thể}| \times |\text{Tài nguyên}|.
\]

Với một nền tảng có hàng chục nghìn mẫu và nhiều người dùng, việc quản lý trở nên bất khả thi bằng thao tác thủ công. Nghiêm trọng hơn về mặt quản trị, ACL **không biểu diễn được lý do**: nó ghi nhận rằng một người có quyền, nhưng không cho biết họ có quyền đó vì giữ vai trò gì. Khi một người thay đổi vị trí công tác, không có cách hệ thống nào để điều chỉnh toàn bộ quyền của họ.

### 2.5.3. Kiểm soát truy cập theo vai (RBAC)

Role-Based Access Control (RBAC) chèn một tầng trung gian giữa người dùng và quyền \cite{ferraiolo_proposed_2001,sandhu_role-based_1996}:

\[
\text{Người dùng} \rightarrow \text{Vai trò} \rightarrow \text{Quyền}.
\]

**Ưu điểm.** Tầng trung gian này ánh xạ tự nhiên vào **trách nhiệm trong tổ chức**, nên mô hình dễ diễn đạt cho người quản trị nghiệp vụ. Thay đổi tập quyền được thực hiện một lần trên vai trò thay vì lặp trên từng người. Việc kiểm toán trở nên khả thi vì câu hỏi "ai có quyền này" quy về câu hỏi "ai giữ vai trò này". Mô hình RBAC chuẩn còn hỗ trợ các quan hệ phân cấp vai và ràng buộc nhằm tổ chức quyền có cấu trúc \cite{ferraiolo_proposed_2001}.

**Nhược điểm.** Khi các trường hợp ngoại lệ tăng, số vai trò có thể bùng nổ vì mỗi tổ hợp quyền đặc thù lại sinh một vai mới. RBAC cơ bản cũng không diễn đạt tốt các điều kiện phụ thuộc ngữ cảnh, chẳng hạn giới hạn theo thời gian hoặc theo thuộc tính của chính tài nguyên.

### 2.5.4. Kiểm soát truy cập theo thuộc tính (ABAC)

ABAC ra quyết định bằng một hàm trên thuộc tính của bốn thành phần \cite{hu_guide_2014}:

\[
\text{Quyết định} = f(\text{Chủ thể}, \text{Tài nguyên}, \text{Hành động}, \text{Môi trường}).
\]

**Ưu điểm.** Khả năng biểu đạt cao. Những policy phụ thuộc ngữ cảnh — chẳng hạn chỉ cho phép khi thuộc tính của người dùng khớp thuộc tính của tài nguyên, hoặc chỉ trong một khoảng thời gian — được diễn đạt trực tiếp mà không cần tạo vai trò mới.

**Nhược điểm.** Chi phí chuyển sang phía vận hành và kiểm toán. Vì quyết định được suy ra từ nhiều thuộc tính tại thời điểm truy cập, câu hỏi "người này hiện có những quyền gì" không còn tra được bằng một truy vấn đơn giản mà phải mô phỏng trên tập tình huống. Việc gỡ lỗi một quyết định từ chối cũng phức tạp hơn vì phải truy ngược qua nhiều thuộc tính đầu vào.

### 2.5.5. Kiểm soát truy cập theo quan hệ (ReBAC)

ReBAC ra quyết định dựa trên các quan hệ trong một đồ thị đối tượng — *người dùng là thành viên của workspace*, *workspace chứa project* — và đã được áp dụng ở quy mô lớn trong các hệ thống phân quyền tập trung \cite{pang_zanzibar_2019}. Điểm mạnh là biểu diễn tự nhiên các quan hệ chứa nhiều cấp; điểm yếu là đòi hỏi mô hình hoá và hạ tầng đánh giá quan hệ riêng, chi phí khó biện minh khi tập hành động nghiệp vụ đã tương đối ổn định. Mô hình được đưa vào bảng so sánh ở mục 2.5.7 để hoàn chỉnh phổ lựa chọn, không phải vì nó là ứng viên chính.

### 2.5.6. RBAC theo phạm vi

Trong hệ đa thuê bao, quan hệ `Người dùng → Vai trò → Quyền` chưa đủ nếu vai trò không gắn với phạm vi. Cùng một người có thể là quản trị viên ở tenant A, người chỉ đọc ở workspace B, và không có quyền ở project C. Vì vậy quan hệ gán vai cần chứa tối thiểu bộ ba:

\[
(\text{Người dùng}, \text{Vai trò}, \text{Phạm vi}).
\]

Casbin mô tả mô hình RBAC with Domains, trong đó domain có thể được dùng để biểu diễn phạm vi mà một lần gán vai có hiệu lực \cite{casbin_authors_casbin_2024,casbin_authors_rbac_2026}. Với hệ thống đang xét, tenant, workspace và project tạo thành các loại phạm vi mà policy có thể tham chiếu.

Quan hệ chứa giữa các phạm vi **không tự động tạo ra kế thừa quyền**:

\[
\text{Phân cấp tài nguyên} \neq \text{Phân cấp vai trò}.
\]

Việc tenant chứa workspace là một sự thật về cấu trúc dữ liệu. Việc một vai trò ở tenant có hiệu lực xuống workspace con hay không là một **quyết định chính sách** phải được phát biểu tường minh. Nếu hệ thống mặc nhiên coi hai điều này là một, quyền hiệu dụng của một người sẽ lớn hơn dự kiến ở mọi nơi cấu trúc chứa mở rộng, và điều đó xảy ra một cách im lặng mỗi khi thêm một phạm vi con mới.

### 2.5.7. So sánh các mô hình kiểm soát truy cập

**Bảng 2-19. So sánh năm mô hình kiểm soát truy cập**

| Tiêu chí | ACL | RBAC | ABAC | ReBAC | RBAC theo phạm vi |
|---|---|---|---|---|---|
| Đơn vị cấp quyền | Cặp chủ thể – tài nguyên | Vai trò | Thuộc tính | Quan hệ trong đồ thị | Vai trò trong phạm vi |
| Khả năng quản lý khi quy mô tăng | Thấp | Cao | Trung bình | Trung bình | Cao |
| Khả năng kiểm toán quyền hiệu dụng | Trung bình | Cao | Thấp – trung bình | Trung bình | Cao |
| Ánh xạ vào trách nhiệm trong tổ chức | Yếu | Cao | Có thể | Có thể | Cao |
| Hỗ trợ phạm vi đa thuê bao | Thủ công | Cần mở rộng | Có thể qua thuộc tính | Tự nhiên qua quan hệ | **Tự nhiên** |
| Định hướng được chọn | | | | | **Được chọn** |

*Nguồn: tác giả tổng hợp từ \cite{ferraiolo_proposed_2001,sandhu_role-based_1996,hu_guide_2014,casbin_authors_casbin_2024,casbin_authors_rbac_2026,pang_zanzibar_2019}.*

Bảng trên giữ sáu tiêu chí dẫn tới lựa chọn. Đối chiếu đầy đủ giữa ACL, RBAC, ABAC, ReBAC và RBAC theo phạm vi — bổ sung khả năng diễn đạt điều kiện theo ngữ cảnh và chi phí mô hình hoá cùng hạ tầng — được trình bày tại **Phụ lục F.5, Bảng F-4**.

**Định hướng được chọn và lý do.** Bài toán có hai đặc điểm quyết định. Thứ nhất, tập hành động nghiệp vụ tương đối ổn định và ánh xạ rõ vào trách nhiệm trong tổ chức: người thu dữ liệu, người kiểm duyệt, người quản trị, người chỉ đọc. Thứ hai, hệ thống cần trả lời được câu hỏi quản trị "ai đang giữ vai gì ở phạm vi nào" một cách trực tiếp, vì đó là câu hỏi mà một tổ chức sử dụng nền tảng sẽ đặt ra thường xuyên, và cũng là câu hỏi mà nhật ký kiểm toán ở mục 2.5.9 phải trả lời được. Hai đặc điểm này ưu tiên khả năng kiểm toán hơn khả năng biểu đạt, nên RBAC theo phạm vi là lựa chọn phù hợp.

**Đánh đổi.** Mô hình này diễn đạt điều kiện ngữ cảnh kém hơn ABAC. Khi phát sinh nhu cầu về policy phụ thuộc thuộc tính, hai hướng bổ sung khả dĩ là thêm điều kiện thuộc tính vào một số policy cụ thể, hoặc chấp nhận tạo thêm vai trò. Hướng thứ nhất giữ được tính kiểm toán tổng thể nhưng làm mô hình lai; hướng thứ hai giữ mô hình thuần nhất nhưng có nguy cơ bùng nổ vai trò.

### 2.5.8. Mô hình phiên và ba mức chứng minh danh tính

**Phiên có trạng thái phía máy chủ.** Máy chủ lưu trạng thái phiên và định danh phiên được gửi kèm mỗi yêu cầu. Ưu điểm chính là **thu hồi trực tiếp**: xóa trạng thái là phiên mất hiệu lực ngay. Nhược điểm là cần kho lưu phiên, và mở rộng theo chiều ngang đòi hỏi kho phiên dùng chung.

**Token tự chứa được ký.** JSON Web Token (JWT) là định dạng gọn để biểu diễn tập claim giữa các bên, được chuẩn hóa trong RFC 7519 \cite{jones_json_2015}. Với JWT tự chứa được ký, hệ thống **có thể** xác minh tính toàn vẹn và một số claim mà không cần truy vấn lại toàn bộ trạng thái phiên ở mỗi yêu cầu. Nhược điểm đối xứng: thu hồi phức tạp hơn, và quyền ghi trong token có thể **cũ hơn** quyền thực tế nếu vai trò của người dùng vừa thay đổi.

**Bảng 2-20. So sánh phiên có trạng thái và token tự chứa**

| Tiêu chí | Phiên có trạng thái | Token tự chứa được ký |
|---|---|---|
| Nơi giữ trạng thái | Máy chủ | Một phần nằm trong token |
| Thu hồi tức thì | Trực tiếp | Cần cơ chế bổ sung |
| Quyền bị cũ sau khi đổi vai | Không | Có, tới khi token hết hạn |
| Rủi ro khi token bị lộ | Thu hồi được ngay | Còn hiệu lực tới hạn hoặc tới khi có cơ chế chặn |

*Nguồn: tác giả tổng hợp từ \cite{jones_json_2015,sheffer_json_2020,hardt_oauth_2012,nist_sp800_63b_2025}.*

Bảng trên giữ bốn tiêu chí phân định. Các tiêu chí vận hành còn lại — cách xác minh mỗi yêu cầu, khả năng mở rộng theo chiều ngang và mức phù hợp với API nhiều máy khách — được trình bày tại **Phụ lục F.5, Bảng F-5**.

Hai lựa chọn này **không loại trừ nhau**. JWT không phải một giao thức xác thực hoàn chỉnh và cũng không bắt buộc hệ thống phải hoàn toàn phi trạng thái. Việc thu hồi phiên, vô hiệu hóa thiết bị, thay đổi quyền hoặc phát hiện token bị lộ vẫn có thể cần trạng thái phía máy chủ. Các thực hành an toàn cho JWT được tổng hợp trong RFC 8725 \cite{sheffer_json_2020}. Vì vậy luận văn không mô tả hệ thống là "phi trạng thái"; JWT được dùng như một biểu diễn cho tập claim, còn vòng đời phiên vẫn có trạng thái ở những chỗ cần thu hồi.

Một thiết kế phổ biến là dùng access token thời gian sống ngắn cho API và refresh token có vòng đời dài hơn để xin access token mới — một điểm cân bằng giữa hai cột của bảng trên. Refresh token là khái niệm được định nghĩa trong OAuth 2.0 \cite{hardt_oauth_2012}; việc dùng cặp access/refresh không có nghĩa toàn bộ hệ thống phải được mô tả là một triển khai OAuth 2.0. Các khuyến nghị an toàn hiện hành được cập nhật trong RFC 9700 \cite{lodderstedt_best_2025}.

**Ba mức chứng minh danh tính.** Đối với thao tác nhạy cảm, cần phân biệt ba mức mà hai mức đầu đã trình bày ở mục 2.5.1:

\[
\text{Xác thực} \;\nRightarrow\; \text{Phân quyền} \;\nRightarrow\; \text{Danh tính vừa được chứng minh lại}.
\]

Mức thứ ba trả lời một câu hỏi mà hai mức đầu không trả lời: **người đang cầm phiên này có còn là chủ sở hữu hợp pháp của nó tại thời điểm hành động hay không**. Một phiên hợp lệ chỉ chứng minh rằng tại một thời điểm nào đó trong quá khứ, ai đó đã xác thực thành công. Với một thiết bị bị bỏ lại trong trạng thái đã đăng nhập, hoặc một token bị đánh cắp còn trong hạn, hai mức đầu vẫn cho kết quả "được phép" trong khi giả định nền của chúng đã không còn đúng.

Hướng dẫn NIST SP 800-63B-4 trình bày các yêu cầu và khuyến nghị về xác thực, quản lý phương tiện xác thực, xác thực nhiều yếu tố và vòng đời xác thực \cite{nist_sp800_63b_2025}. Trong kiến trúc ứng dụng, điều này tạo cơ sở cho cơ chế **xác thực lại (step-up authentication)** trước các thao tác có mức rủi ro cao. Tiêu chí xác định thao tác nào cần mức thứ ba không phải mức độ "quan trọng" một cách cảm tính, mà là ba tính chất cụ thể: thao tác khó hoặc không đảo ngược được; thao tác mở rộng quyền của chính người thực hiện hoặc của người khác; hoặc thao tác đưa dữ liệu ra ngoài phạm vi kiểm soát hiện tại. Ba nhóm này trùng phần lớn với nhóm sự kiện cần ghi nhận đặc biệt trong nhật ký kiểm toán ở mục 2.5.9 . Cả hai đều xuất phát từ mức độ hệ quả của hành động. Cách hiện thực cụ thể thuộc Chương 3.

### 2.5.9. Khả năng truy vết và quy trách nhiệm

Kiểm soát truy cập quyết định điều gì được phép xảy ra. Nó **không** trả lời câu hỏi điều gì đã thực sự xảy ra — và trong một nền tảng quản trị dữ liệu của nhiều tổ chức, câu hỏi thứ hai cũng là một yêu cầu kiến trúc chứ không phải một tiện ích vận hành.

Cần phân biệt hai loại nhật ký thường bị gộp làm một.

**Nhật ký vận hành** phục vụ chẩn đoán kỹ thuật: lỗi kết nối, số lần thử lại của một tác vụ, độ trễ của một yêu cầu. Người đọc là người vận hành hệ thống, và câu hỏi là "hệ thống đang chạy thế nào".

**Nhật ký kiểm toán** phục vụ quy trách nhiệm. Câu hỏi là "ai đã làm gì, trên tài nguyên nào, trong phạm vi nào, khi nào, và kết quả ra sao". Ở mức tối thiểu, một sự kiện kiểm toán là một bộ:

\[
AuditEvent = (\text{Chủ thể}, \text{Hành động}, \text{Phạm vi}, \text{Tài nguyên}, \text{Thời điểm}, \text{Kết quả}).
\]

Thành phần **kết quả** hay bị bỏ: một nỗ lực thực hiện hành động **bị từ chối** cũng là một sự kiện kiểm toán, và trong nhiều trường hợp là sự kiện đáng chú ý hơn một hành động thành công. Nếu chỉ ghi những gì thành công, hệ thống không có dữ liệu nào về việc có ai đó đang thử vượt ranh giới.

**Bảng 2-21. Nhật ký vận hành và nhật ký kiểm toán**

| Tiêu chí | Nhật ký vận hành | Nhật ký kiểm toán |
|---|---|---|
| Mục tiêu | Chẩn đoán, gỡ lỗi, quan trắc | Quy trách nhiệm, đối chiếu nghĩa vụ |
| Chủ thể hành động | Không bắt buộc | **Bắt buộc** |
| Phạm vi và tài nguyên | Không luôn có | **Bắt buộc** |
| Kết quả, kể cả bị từ chối | Thường chỉ ghi lỗi kỹ thuật | **Bắt buộc, gồm cả từ chối** |
| Hệ quả nếu thiếu | Khó gỡ lỗi | **Không chứng minh được điều gì đã xảy ra** |

*Nguồn: tác giả tổng hợp từ \cite{saltzer_protection_1975,nist_sp800_63b_2025}; yêu cầu về khả năng chứng minh liên hệ với các nghĩa vụ ở mục 2.9.*

Bảng trên giữ năm tiêu chí. Bản đầy đủ, bổ sung nhóm người đọc, thời gian lưu và mức kiểm soát việc sửa hoặc xoá, được trình bày tại **Phụ lục F.5, Bảng F-6**.

Một nhóm sự kiện cần mức ghi nhận cao hơn thao tác đọc ghi thông thường: thay đổi việc gán vai và quyền; xóa hoặc thanh lọc dữ liệu; công bố một phiên bản ra ngoài; thay đổi trạng thái đồng thuận; và thay đổi cấu hình của chính cơ chế kiểm soát. Đặc điểm chung của nhóm này là chúng **thay đổi tập những gì có thể xảy ra về sau**, chứ không chỉ thay đổi dữ liệu — đúng nhóm cần mức chứng minh danh tính thứ ba ở mục 2.5.8.

Cuối cùng, nhật ký kiểm toán có một quan hệ hai chiều với cơ chế cô lập ở mục 2.4 mà thiết kế phải giải quyết tường minh. Một mặt, bản ghi kiểm toán về hoạt động của một tenant là dữ liệu của tenant đó và chịu cùng ranh giới phạm vi. Mặt khác, nhật ký kiểm toán chỉ có giá trị làm bằng chứng nếu chính nó không bị sửa bởi những chủ thể mà nó ghi nhận. Hai yêu cầu này kéo về hai hướng ngược nhau, và việc dung hòa chúng — ai đọc được gì, ai không ghi đè được gì — là một quyết định thiết kế thuộc Chương 3.

### 2.5.10. Các lớp kiểm soát và ranh giới trách nhiệm

Các cơ chế bảo vệ trả lời những câu hỏi khác nhau và không thay thế nhau.

**Bảng 2-22. Các câu hỏi kiểm soát và cơ chế tương ứng**

| Câu hỏi | Cơ chế |
|---|---|
| Chủ thể là ai? | Xác thực và quản lý phiên |
| Chủ thể được thực hiện hành động nghiệp vụ nào? | RBAC theo phạm vi / policy ứng dụng |
| Quan hệ dữ liệu này có được phép tồn tại? | Khóa chính, khóa ngoại, `UNIQUE`, `CHECK`, ràng buộc xuyên phạm vi |
| Hàng dữ liệu nào được chạm tới? | Row-Level Security |
| Có cần chứng minh lại danh tính cho thao tác nhạy cảm? | Xác thực lại / MFA theo chính sách |
| Điều gì đã thực sự xảy ra? | Nhật ký kiểm toán |

*Nguồn: tác giả tổng hợp từ \cite{postgresql_rls_2026,ferraiolo_proposed_2001,sandhu_role-based_1996,casbin_authors_casbin_2024,saltzer_protection_1975,nist_sp800_63b_2025,elmasri_fundamentals_2015}.*

Việc phân lớp giúp tránh một lỗi phổ biến: dùng RBAC để thay cho cô lập tenant hoặc dùng RLS để thay cho kiểm soát hành động nghiệp vụ. RLS có thể ngăn đọc hàng ngoài tenant nhưng không biết thao tác "công bố bộ dữ liệu" có được phép hay không; ngược lại, policy ứng dụng có thể cho phép "công bố" nhưng không nên có khả năng đọc hàng của tenant khác để thực hiện thao tác đó. Dòng thứ ba cũng đáng lưu ý: ràng buộc toàn vẹn của cơ sở dữ liệu là một lớp kiểm soát riêng, trả lời một câu hỏi mà cả phân quyền lẫn RLS đều không trả lời (mục 2.1.6 và 2.2.6). Dòng cuối là lớp duy nhất hoạt động **sau khi** hành động đã xảy ra, và vì vậy là lớp duy nhất còn giá trị khi năm lớp trên đã bị vượt qua.

## 2.6. Thu thập và thu nhận dữ liệu ngôn ngữ ký hiệu

Tên đề tài có hai vế ngang hàng: **thu thập** và **quản lý** dữ liệu. Các mục 2.2–2.5 và 2.8–2.9 xây dựng cơ sở cho vế thứ hai. Mục này xây dựng cơ sở cho vế thứ nhất, và cần được đọc như một trục lý thuyết độc lập chứ không phải phần phụ của mục biểu diễn dữ liệu.

Phạm vi của mục cần được giới hạn rõ ngay từ đầu. Luận văn nghiên cứu **thu thập dữ liệu như một quá trình có tổ chức và có quản trị**: đơn vị thu, phương thức thu, chiến lược thu, độ bao phủ, và kiểm tra tại thời điểm thu. Luận văn **không** nghiên cứu xử lý tín hiệu thô — cắt ghép video, chuẩn hóa khung hình, khử nhiễu, phân đoạn tự động, tăng cường dữ liệu hay so sánh định dạng nén. Những nội dung đó thuộc đường ống tiền xử lý thị giác máy tính, nằm ngoài phạm vi của một phân hệ thu thập và quản lý dữ liệu. Thành phần ước lượng điểm mốc xuất hiện ở mục 2.6.7 vì nó là **kỹ thuật thu nhận** mà đường thu sử dụng, không phải vì nó là đối tượng nghiên cứu.

### 2.6.1. Ba khái niệm bị gộp dưới một chữ "thu"

Tiếng Việt dùng "thu thập" và "thu nhận" gần như thay thế được cho nhau, còn tiếng Anh phân biệt ba thuật ngữ ở ba tầng khác nhau. Phân biệt này cần được đặt ngay đầu mục, vì phần còn lại của 2.6 nói về ba thứ khác nhau và một thuật ngữ chung sẽ làm chúng lẫn vào nhau.

**Thu thập dữ liệu (data collection)** là **toàn bộ quá trình có tổ chức** làm cho dữ liệu hình thành hoặc được tiếp nhận: xác định mục tiêu bao phủ, tổ chức phiên thu, xác lập giao thức, phân công vai trò, đặt điều kiện sử dụng. Đây là một khái niệm ở tầng **quy trình và quản trị**, không phải ở tầng kỹ thuật.

**Thu nhận tín hiệu (data acquisition)** là **bước kỹ thuật** lấy tín hiệu hoặc một biểu diễn của tín hiệu từ nguồn quan sát: ghi hình, ước lượng điểm mốc, lấy mẫu theo tần số khung. Đây là bước duy nhất trong ba bước có tiếp xúc với hiện tượng vật lý.

**Nạp dữ liệu vào nền tảng (data ingestion / import)** là đưa dữ liệu **đã tồn tại bên ngoài** vào trong ranh giới của hệ thống: nhận tệp người dùng tải lên, nhập từ một bộ dữ liệu khác, ánh xạ không gian nhãn của nguồn sang danh mục của hệ thống.

Quan hệ giữa ba khái niệm là quan hệ **bao hàm ở tầng khác nhau**, không phải ba bước nối tiếp của một dây chuyền:

\[
\text{Thu thập} \supset \{\text{Thu nhận tín hiệu},\ \text{Nạp dữ liệu}\}.
\]

Phép bao hàm này là **phân loại đường vào trong phạm vi nền tảng**, không phải một phát biểu về toàn bộ lịch sử hình thành của dữ liệu. Xét tại ranh giới tiếp nhận của nền tảng, một mẫu hoặc được hình thành qua đường thu nhận trực tiếp, hoặc được đưa vào từ dữ liệu đã tồn tại. Hai khái niệm mô tả hai cơ chế đầu vào khác nhau; chúng **không** phủ định việc dữ liệu được nạp vào có thể đã bắt nguồn từ một quá trình thu nhận trước đó ở bên ngoài nền tảng.

Phân biệt này quan trọng vì nó tránh một suy luận sai dễ mắc: từ chỗ một mẫu đi vào bằng đường nạp, kết luận rằng nó không có nguồn gốc thu nhận nào. Điều đúng là nền tảng **không quan sát được** quá trình thu nhận ấy, chứ không phải quá trình ấy không tồn tại. Nói cách khác, thu nhận và nạp là hai đường vào khác nhau của cùng một quá trình thu thập, và mỗi mẫu đi vào bằng đúng một trong hai — tính "đúng một" nói về cơ chế đầu vào, không nói về tiểu sử của dữ liệu. Hai hệ quả:

Thứ nhất, một nền tảng có thể tổ chức thu thập rất tốt mà **không** tự thực hiện bước thu nhận tín hiệu nào — nếu toàn bộ dữ liệu đến bằng đường nạp. Ngược lại, một hệ thống thực hiện thu nhận tín hiệu tinh vi vẫn có thể **không có** quá trình thu thập: nó ghi được dữ liệu nhưng không trả lời được dữ liệu ấy phục vụ mục tiêu bao phủ nào, thu theo giao thức nào, dùng được cho việc gì.

Thứ hai, và quan trọng hơn cho các mục sau: **nguồn gốc của một mẫu phụ thuộc vào nó đi vào bằng đường nào.** Ở đường thu nhận, hệ thống *quan sát* được bối cảnh vì chính nó dẫn dắt quy trình. Ở đường nạp, mọi siêu dữ liệu về bối cảnh đều là *khai báo* của bên đóng góp. Đây là gốc của phân biệt quan sát – khai báo ở mục 2.6.3.

Phân biệt này thuần tuý khái niệm. Việc một hệ thống cụ thể có hiện thực đường nạp hay không, và hiện thực tới mức nào, là câu hỏi của Chương 3; Chương 2 chỉ khẳng định rằng nếu cả hai đường cùng tồn tại thì chúng phải phân biệt được trong lược đồ, vì chúng sinh ra siêu dữ liệu có mức tin cậy khác nhau.

### 2.6.2. Đơn vị thu thập và mô hình phiên thu

Một hệ thống thu dữ liệu có thể tổ chức quanh hai đơn vị khác nhau, và lựa chọn giữa chúng có hệ quả sâu hơn vẻ ngoài.

**Đơn vị là tệp.** Mỗi mẫu là một đối tượng độc lập với siêu dữ liệu riêng. Đơn giản, nhưng mọi mẫu đều rời rạc: hệ thống biết từng mẫu nhưng không biết những mẫu nào thuộc về cùng một lần thu.

**Đơn vị là phiên thu.** Mẫu được nhóm theo bối cảnh mà chúng được tạo ra:

\[
\text{Người tham gia} \rightarrow \text{Phiên thu} \rightarrow \text{Mẫu}.
\]

Một phiên thu là **bối cảnh chung của một nhóm mẫu được thu cùng nhau**, và có thể gắn với: người ký, người vận hành, phạm vi tenant và dự án, thời điểm, phương thức thu, và tập lớp ký hiệu được nhắm tới.

Lý do phiên thu là một thực thể cần thiết chứ không phải siêu dữ liệu tùy chọn nằm ở những câu hỏi mà mô hình chỉ có `Người ký → Mẫu` **không trả lời được**:

- Những mẫu nào được tạo ra trong cùng một bối cảnh, cùng thiết bị, cùng buổi?
- Nếu một lần thu có sự cố — đặt sai lớp, thiết bị lệch, người vận hành hiểu sai quy trình — thì **chính xác nhóm mẫu nào** bị ảnh hưởng và cần rà lại?
- Một lần thu đã bao phủ những lớp nào, và còn thiếu lớp nào so với mục tiêu?
- Hai mẫu giống nhau bất thường là do trùng lặp dữ liệu hay vì chúng đến từ cùng một phiên?

Câu hỏi thứ hai là câu hỏi vận hành thật. Không có thực thể phiên, phạm vi ảnh hưởng của một sự cố thu chỉ có thể ước lượng bằng cách lọc theo thời gian và người ký — một phép suy đoán, không phải một truy vấn.

Phiên thu cũng là đơn vị tự nhiên để gắn **phương thức thu** (mục 2.6.3), vì đó là thuộc tính của bối cảnh chứ không phải của từng mẫu riêng lẻ. Ghi nó ở mức mẫu sẽ lặp lại cùng một giá trị hàng trăm lần và tạo ra khả năng các bản sao lệch nhau — đúng dạng bất thường mà chuẩn hóa ở mục 2.1.6 loại trừ. Khi nghiệp vụ yêu cầu, phiên thu cũng có thể liên kết tới bối cảnh quản trị hoặc cơ sở sử dụng đang áp dụng cho lần thu đó.

Cần tránh một suy diễn gần đúng ở đây: **đồng thuận không phải là một thuộc tính của phiên thu.** Theo mô hình ở mục 2.9.3, đồng thuận là quan hệ giữa một *chủ thể dữ liệu* với một *văn bản*, ở một *phiên bản*, tại một *thời điểm*, cho một *phạm vi sử dụng* — và nó được kiểm tại thao tác mà phạm vi ấy điều chỉnh, chứ không phải tại nơi dữ liệu được tạo ra. Một phiên thu có thể tham chiếu tới trạng thái đồng thuận đang áp dụng, nhưng lưu đồng thuận **như một trường của phiên thu** sẽ làm mất hai tính chất thiết yếu: nó gắn với chủ thể chứ không với bối cảnh, và nó thay đổi được sau thời điểm thu.

### 2.6.3. Ba phương thức thu nhận dữ liệu

Không phải mọi mẫu đều đến với hệ thống theo cùng một cách, và **cách nó đến là một phần của nguồn gốc dữ liệu**.

**Thu trực tiếp.** Người ký thực hiện ký hiệu trước camera trong một phiên thu do hệ thống điều phối. Hệ thống biết lớp đang thu, người ký, người vận hành và thời điểm — vì chính nó dẫn dắt quy trình.

**Đóng góp tệp đã có.** Người dùng tải lên bản ghi đã tồn tại. Hệ thống nhận được dữ liệu nhưng không quan sát được bối cảnh tạo ra nó; mọi siêu dữ liệu về bối cảnh đều là **khai báo** chứ không phải **quan sát**.

**Nhập từ nguồn bên ngoài.** Dữ liệu đến từ một bộ dữ liệu hoặc hệ thống khác. Ngoài vấn đề của phương thức thứ hai, còn phát sinh nhu cầu ánh xạ không gian nhãn của nguồn sang danh mục của hệ thống — một phép ánh xạ có thể không toàn phần.

**Bảng 2-23. So sánh ba phương thức thu nhận dữ liệu**

| Tiêu chí | Thu trực tiếp | Đóng góp tệp đã có | Nhập từ nguồn ngoài |
|---|---|---|---|
| Mức kiểm soát quy trình thu | Cao | Trung bình | Thấp |
| Siêu dữ liệu tại thời điểm tạo mẫu | Hệ thống **quan sát** được | Do người tải **khai báo** | Phải ánh xạ từ nguồn |
| Liên kết người ký – phiên thu | Tự nhiên, do quy trình sinh ra | Cần khai báo tường minh | Có thể không tồn tại ở nguồn |
| Độ tin cậy của nguồn gốc | Cao | Trung bình | Phụ thuộc nguồn |
| Phù hợp để thu mới có kiểm soát | Cao | Trung bình | Thấp |

*Nguồn: tác giả tổng hợp; tiêu chí phân biệt chính là việc siêu dữ liệu bối cảnh do hệ thống quan sát hay do bên đóng góp khai báo.*

Bảng trên giữ năm tiêu chí. Bản đầy đủ giữa thu trực tiếp, đóng góp tệp đã có và nhập từ nguồn ngoài — bổ sung tính đồng nhất về định dạng, cách ánh xạ vào danh mục lớp và khả năng tận dụng dữ liệu đã tồn tại — được trình bày tại **Phụ lục F.6, Bảng F-7**.

**Kết luận định hướng.** Nền tảng **không nên coi mọi mẫu là như nhau chỉ vì chúng cùng được lưu ở một định dạng**. Phương thức thu là một thuộc tính nguồn gốc phải được ghi nhận, vì nó cho biết **quan hệ người ký được thiết lập bằng cách nào**.

Sự phân biệt quan sát – khai báo **không tự nó** chia dữ liệu thành phần đáng tin và phần không đáng tin: một định danh người ký được khai báo vẫn có thể hoàn toàn đáng tin nếu nguồn nhập có nguồn gốc và tài liệu chứng minh tốt. Phát biểu đúng là:

> Phân tích độc lập người ký có cơ sở vững nhất khi danh tính người ký được ghi nhận như một phần của bối cảnh thu có kiểm soát. Với dữ liệu được nhập hoặc đóng góp về sau, độ tin cậy của phân tích phụ thuộc vào nguồn gốc và bằng chứng chống lưng cho siêu dữ liệu người ký được khai báo.

Nói cách khác, mức tin cậy của một trường siêu dữ liệu phụ thuộc vào **cách nó được xác lập**, chứ không chỉ vào giá trị của nó. Vì vậy điều hệ thống cần làm không phải là xếp hạng nguồn dữ liệu, mà là **ghi lại cách xác lập** để bên tiêu thụ ở hạ nguồn tự đánh giá được — nếu hai loại này không phân biệt được trong lược đồ, giới hạn đó không phát biểu được ở bất kỳ đâu về sau.

Cách phân biệt này cũng nối trực tiếp với ranh giới tin cậy ở mục 2.6.8: dữ liệu do máy khách hoặc người đóng góp cung cấp nằm ngoài phạm vi quan sát của máy chủ, và phải được xử lý theo đúng nguyên tắc dành cho đầu vào không được tin cậy.

### 2.6.4. Thu có hướng dẫn và đóng góp mở

Từ ba phương thức trên phát sinh một quyết định về **chiến lược thu**.

**Thu có hướng dẫn.** Hệ thống dẫn người dùng qua một trình tự xác định: chọn người ký → chọn lớp ký hiệu cần thu → thực hiện → ghi mẫu. Vì lớp và người ký được xác định **trước** khi mẫu tồn tại, siêu dữ liệu đầy đủ theo thiết kế chứ không nhờ kỷ luật của người nhập. Độ bao phủ (mục 2.6.5) theo dõi được theo thời gian thực. Đổi lại, quy trình cứng hơn và đòi hỏi tổ chức phiên thu.

**Đóng góp mở.** Người dùng tải dữ liệu lên rồi mô tả sau. Rào cản đóng góp thấp và tận dụng được dữ liệu đã có, nhưng siêu dữ liệu phụ thuộc hoàn toàn vào khai báo, quan hệ người ký và phiên thu có thể không xác định được, và việc ánh xạ nhãn dễ sai lệch.

**Bảng 2-24. So sánh ba chiến lược thu thập**

| Tiêu chí | Thu có hướng dẫn | Đóng góp mở | Kết hợp |
|---|---|---|---|
| Mức đầy đủ của siêu dữ liệu | Cao, theo thiết kế | Thấp hơn, phụ thuộc khai báo | Cao ở luồng thu mới |
| Tính nhất quán của nhãn lớp | Cao — xác định trước khi thu | Phụ thuộc khai báo sau | Có kiểm soát theo luồng |
| Nguồn gốc người ký và phiên thu | Cao | Có thể thiếu | Khác nhau theo luồng, được ghi nhận |
| Tận dụng dữ liệu đã tồn tại | Thấp | Cao | Cao |
| Định hướng được chọn | | | **Được chọn** |

*Nguồn: tác giả tổng hợp.*

**Định hướng được chọn và lý do.** Chiến lược kết hợp phù hợp: **thu có hướng dẫn cho dữ liệu thu mới, kèm một đường đóng góp riêng cho dữ liệu đã tồn tại với yêu cầu siêu dữ liệu tường minh**. Hai đường phục vụ hai mục tiêu khác nhau và không nên bị ép về một quy trình chung. Ép dữ liệu đã có đi qua quy trình thu có hướng dẫn sẽ loại bỏ nguồn dữ liệu hợp lệ; ngược lại, hạ chuẩn luồng thu mới xuống mức của luồng đóng góp sẽ làm mất chính lợi thế mà một nền tảng thu có được so với một thư mục tệp.

**Đánh đổi.** Hệ thống phải duy trì hai đường thu với hai tập ràng buộc khác nhau, và — quan trọng hơn — phải **ghi nhận mẫu đến theo đường nào**, vì nếu không, sự khác biệt về độ tin cậy của siêu dữ liệu sẽ biến mất khỏi dữ liệu và không phát biểu được ở hạ nguồn.

### 2.6.5. Độ bao phủ và các chiều lấy mẫu

Đây là điểm mà một nền tảng thu thập khác rõ nhất so với một kho chứa tệp: **thu thập không phải là làm tăng số lượng mẫu**.

Một bộ dữ liệu có thể có rất nhiều mẫu mà vẫn không dùng được cho mục tiêu nghiên cứu, nếu phân bố của nó lệch trên những chiều có ý nghĩa. Từ bốn nhóm đặc trưng ở mục 2.1.1 suy ra ít nhất bốn chiều cần theo dõi:

\[
\text{Lớp ký hiệu} \times \text{Người ký} \times \text{Vùng/phương ngữ} \times \text{Phiên thu}.
\]

**Bảng 2-25. Các chiều bao phủ và câu hỏi tương ứng**

| Chiều | Câu hỏi cần trả lời | Hệ quả nếu lệch |
|---|---|---|
| Lớp ký hiệu | Lớp nào đang thiếu mẫu so với mục tiêu? | Lớp thiểu số không học được, hoặc bị loại khi áp sàn số mẫu |
| Người ký | Dữ liệu có phụ thuộc quá mức vào một vài người không? | Không tách được đặc trưng của ký hiệu khỏi đặc trưng của người thực hiện |
| Vùng / phương ngữ | Biến thể vùng nào chưa được đại diện? | Kết luận về "ngôn ngữ ký hiệu Việt Nam" thực chất chỉ đúng cho một vùng |
| Phiên thu | Bao nhiêu mẫu đến từ cùng một bối cảnh thu duy nhất? | Đa dạng biểu kiến cao nhưng đa dạng thực tế thấp |
| Phương thức thu | Tỉ lệ giữa thu trực tiếp, đóng góp và nhập ngoài là bao nhiêu? | Không biết phần nào của dữ liệu có nguồn gốc quan sát được |

*Nguồn: tác giả tổng hợp; các chiều suy ra từ đặc trưng dữ liệu ở mục 2.1.1 và mô hình phiên thu ở mục 2.6.2.*

Chiều **phiên thu** dễ bị bỏ qua nhất. Một trăm mẫu của cùng một lớp, cùng một người ký, thu liên tiếp trong một buổi, không cung cấp lượng thông tin tương đương một trăm mẫu trải trên nhiều buổi khác nhau — nhưng hai trường hợp này **trông giống hệt nhau** nếu hệ thống chỉ đếm số mẫu. Chỉ có thực thể phiên thu mới cho phép phân biệt.

**Phạm vi trách nhiệm của nền tảng cần được phát biểu thận trọng.** Luận văn không đề xuất một giao thức lấy mẫu tối ưu, không thực hiện lấy mẫu phân tầng có kiểm soát và không tuyên bố dữ liệu thu được là đại diện cho một tổng thể. Phát biểu đúng là:

> Nền tảng có trách nhiệm lưu đủ siêu dữ liệu để **độ bao phủ đo được và quản trị được** trên các chiều có ý nghĩa; nó không bảo đảm rằng bộ dữ liệu thu được là cân bằng hay đại diện.

Đây là ranh giới phải giữ. Một hệ thống đo được độ lệch là một hệ thống cho phép người dùng nhận ra vấn đề và điều chỉnh kế hoạch thu; một hệ thống *tuyên bố* dữ liệu cân bằng lại đang đưa ra một khẳng định thống kê mà nó không có cơ sở để đưa ra.

### 2.6.6. Giao thức thu như một khái niệm tách khỏi lược đồ

Hai đơn vị cùng sử dụng một nền tảng, với cùng một lược đồ dữ liệu, vẫn có thể tạo ra hai bộ dữ liệu **không so sánh được với nhau** nếu họ thu theo hai quy trình khác nhau. Từ đó phát sinh một phân biệt cần giữ:

\[
\text{Lược đồ dữ liệu} \neq \text{Giao thức thu}.
\]

**Lược đồ** xác định dữ liệu có cấu trúc gì. **Giao thức thu** xác định dữ liệu được tạo ra trong điều kiện và quy trình nào. Ở mức khái niệm, một giao thức thu có thể được mô tả bằng năm thành phần:

\[
Protocol = (\text{Tập lớp nhắm tới},\ \text{Bối cảnh người tham gia},\ \text{Phương thức thu},\ \text{Siêu dữ liệu bắt buộc},\ \text{Quy tắc kiểm tra}).
\]

Ý nghĩa thực tế của phân biệt này với một nền tảng nhiều tổ chức: khi hai tenant đóng góp vào một phạm vi dùng chung, sự khác biệt về giao thức thu là một **thông tin cần thiết cho bên tiêu thụ ở hạ nguồn**, chứ không phải chi tiết vận hành nội bộ của từng tenant. Không ghi nhận nó thì việc gộp dữ liệu từ nhiều nguồn trở thành một phép gộp không có điều kiện.

Cần nêu rõ giới hạn: đây là một **khái niệm để giải thích** vai trò của siêu dữ liệu phiên thu và quy tắc kiểm tra; Chương 2 không khẳng định hệ thống phải có một thực thể mang đúng tên gọi này. Mức độ hiện thực hóa thuộc Chương 3.

### 2.6.7. Các mức biểu diễn dữ liệu thu nhận

**Video nguồn.** Giữ toàn bộ tín hiệu quan sát: bàn tay, cơ thể, khuôn mặt và bối cảnh. Đây là biểu diễn duy nhất cho phép **trích xuất lại một loại đặc trưng khác về sau**, nên là biểu diễn duy nhất không khóa chặt hệ thống vào giả định nghiên cứu hiện tại. Đổi lại, dung lượng lớn, băng thông tải lên cao, và mức phơi bày thông tin cá nhân cao nhất.

**Chuỗi khung ảnh.** Loại bỏ phần đóng gói của định dạng video nhưng vẫn là dữ liệu thị giác đầy đủ theo từng khung. Dung lượng giảm không đáng kể so với mức độ phơi bày vẫn giữ nguyên.

**Điểm mốc toàn thân hoặc đa thành phần.** Bao gồm tư thế cơ thể, hai bàn tay và tùy cấu hình có thể gồm cả khuôn mặt. Giữ được nhiều thành phần biểu đạt hơn — bao gồm một phần các thành phần phi thủ công có ý nghĩa ngôn ngữ nêu ở mục 2.1.1 — nhưng số chiều đặc trưng và chi phí tính toán cao hơn.

**Điểm mốc bàn tay.** Chỉ giữ hình học bàn tay. Nhỏ gọn nhất, chi phí tính toán hạ nguồn thấp nhất. Mất toàn bộ thông tin về khuôn mặt, đầu và tư thế cơ thể.

**Bảng 2-26. So sánh các mức biểu diễn dữ liệu thu nhận**

| Tiêu chí | Video nguồn | Chuỗi khung ảnh | Điểm mốc toàn thân | Điểm mốc bàn tay |
|---|---|---|---|---|
| Lượng thông tin thị giác giữ lại | Rất cao | Rất cao | Cao | Giới hạn |
| Hình học bàn tay | Gián tiếp | Gián tiếp | Có | Trực tiếp |
| Dung lượng lưu trữ mỗi mẫu | Cao | Cao | Thấp | Rất thấp |
| Khả năng trích xuất lại đặc trưng khác | Cao nhất | Cao | Hạn chế | Không |
| Mức phơi bày thông tin nhận dạng | Cao | Cao | Trung bình | Thấp hơn — **không phải ẩn danh** |
| Định hướng cho biểu diễn dẫn xuất chính | | | | **Được chọn** |

*Nguồn: tác giả tổng hợp; các mức định tính, không phải kết quả đo. Số liệu định lượng về hiệu quả lưu trữ được trình bày ở Chương 4.*

Bảng trên giữ sáu tiêu chí. Bản đầy đủ — bổ sung băng thông tải lên, chi phí tính toán ở hạ nguồn, và việc từng thành phần khuôn mặt, đầu và tư thế cơ thể được giữ lại hay mất đi — được trình bày tại **Phụ lục F.6, Bảng F-9**.

**Định hướng được chọn và lý do.** Điểm mốc bàn tay được chọn làm biểu diễn dẫn xuất chính: nó cung cấp trực tiếp thông tin hình học mà đường xử lý hạ nguồn hiện sử dụng; nó cho phép **video thô không bắt buộc phải rời khỏi máy người dùng** trong những luồng chỉ cần điểm mốc; và nó giảm mạnh cả dung lượng lưu trữ lẫn chi phí tính toán tập trung.

**Đánh đổi.** Đây là phép biến đổi có mất mát và **mất mát là một chiều** (mục 2.1.2): nếu bản ghi nguồn không được giữ theo một chính sách riêng, một nghiên cứu tương lai cần thành phần phi thủ công sẽ phải thu lại. Và **không được lập luận rằng điểm mốc là dữ liệu ẩn danh** (mục 2.6.10). Lựa chọn biểu diễn dẫn xuất **không đồng nhất với** quyết định có lưu bản ghi nguồn hay không; hai quyết định độc lập.

Về các họ mô hình ước lượng điểm mốc: OpenPose là một công trình tiêu biểu cho ước lượng tư thế nhiều người dựa trên keypoint \cite{cao_openpose_2021}; MediaPipe cung cấp một khung xây dựng đường ống tri giác đa nền tảng \cite{lugaresi_mediapipe_2019}; MediaPipe Hands tập trung vào bàn tay với bộ phát hiện lòng bàn tay và mô hình dự đoán 21 điểm mốc cho mỗi bàn tay, hướng tới suy luận thời gian thực trên thiết bị \cite{zhang_mediapipe_2020}. MediaPipe Hands phù hợp với đường thu điểm mốc bàn tay và với yêu cầu chạy tại máy khách ở mục 2.6.8, đồng thời không đòi hỏi phát triển một mô hình điểm mốc riêng.

Trong luận văn, MediaPipe Hands được sử dụng như một **thành phần thu nhận có sẵn**, không phải đối tượng nghiên cứu thị giác máy tính: luận văn không huấn luyện lại, không mở rộng, không tuyên bố cải thiện mô hình điểm mốc, và không thực hiện phép đo đối chứng nào giữa ba họ mô hình trên — nên cũng không tuyên bố họ nào vượt trội.

Về cấu trúc dữ liệu đầu ra: mỗi bàn tay có 21 điểm, mỗi điểm có ba thành phần tọa độ theo biểu diễn của mô hình \cite{zhang_mediapipe_2020}. Với tối đa hai bàn tay:

\[
21 \times 3 \times 2 = 126 \quad\text{giá trị mỗi khung}, \qquad X \in \mathbb{R}^{T \times 126}.
\]

Biểu diễn này không nên được mô tả như tái dựng hình học 3D tuyệt đối của bàn tay; thành phần độ sâu là tọa độ tương đối theo mô hình, phù hợp hơn với cách hiểu 2.5D/relative-depth của đường ống MediaPipe Hands \cite{zhang_mediapipe_2020}.

> ### ▣ HÌNH 2-7 — Cấu trúc 21 điểm mốc bàn tay của MediaPipe Hands
> **Loại:** sơ đồ giải phẫu có đánh số · **Công cụ đề nghị:** draw.io hoặc vẽ vector
> **Phải thể hiện:** một bàn tay với 21 điểm được đánh số theo thứ tự của mô hình, các cạnh nối theo cấu trúc ngón; chú thích nhóm điểm theo cổ tay và năm ngón; một ghi chú nêu rõ mỗi điểm có ba thành phần tọa độ và **thành phần độ sâu là tương đối theo mô hình**, không phải toạ độ 3D tuyệt đối; góc dưới ghi phép tính 21 × 3 × 2 = 126 giá trị mỗi khung.
> **Chú thích dưới hình:** *Hình 2-7: Cấu trúc 21 điểm mốc bàn tay của MediaPipe Hands. Nguồn: vẽ lại từ \cite{zhang_mediapipe_2020}.*

### 2.6.8. Trích xuất tại máy khách và tại máy chủ

Trục quyết định này độc lập với trục biểu diễn: phép trích xuất đặc trưng chạy ở đâu.

**Bảng 2-27. So sánh trích xuất tại máy khách và tại máy chủ**

| Tiêu chí | Trích xuất tại máy khách | Trích xuất tại máy chủ |
|---|---|---|
| Tải tính toán trên máy chủ | Thấp hơn | Cao |
| Băng thông tải lên | Thấp nếu chỉ gửi điểm mốc | Cao nếu phải gửi video |
| Mức phơi bày dữ liệu thị giác | Có thể thấp hơn trong luồng không cần video | Dữ liệu nguồn phải tới máy chủ |
| Mức tin cậy của dữ liệu nhận được | **Không tin cậy hoàn toàn** — sinh ra ngoài tầm kiểm soát | Do backend tạo, tin cậy hơn |
| Định hướng cho luồng thu điểm mốc | **Được chọn** | |

*Nguồn: tác giả tổng hợp.*

**Định hướng được chọn.** Trích xuất tại máy khách cho đường thu điểm mốc, nhằm phân bố tải tính toán và giảm nhu cầu chuyển dữ liệu thị giác trong những luồng nghiệp vụ không cần đến nó.

**Đánh đổi**, gồm ba hệ quả kiến trúc. Thứ nhất, **phân bố tải xử lý**: một phần công việc thị giác được thực hiện ở biên, nhưng mức tiết kiệm cụ thể phải được đo ở chương thực nghiệm thay vì suy ra bằng lý thuyết, và sự không đồng nhất về phần cứng người dùng trở thành một biến mới ảnh hưởng tới chất lượng dữ liệu. Thứ hai, **giảm mức phơi bày** trong những luồng không cần video thô — nhưng không đồng nghĩa dữ liệu đã vô danh (mục 2.6.10). Thứ ba, và quyết định về mặt an ninh, **dịch chuyển ranh giới tin cậy**: máy khách nằm **ngoài** cơ sở tính toán được tin cậy định nghĩa ở mục 2.4.5, nên mọi dữ liệu nó gửi là đầu vào không đáng tin cho tới khi được kiểm tra.

### 2.6.9. Kiểm tra tại thời điểm thu

Mục 2.1.4 đã nêu sáu chiều chất lượng và mục 2.1.5 đã chọn chiến lược kết hợp. Ở đây, các nguyên tắc đó được đặt vào đúng đường thu, và phân thành ba loại kiểm tra khác nhau về **ai thực hiện được**.

**Kiểm tra cấu trúc — máy thực hiện được ngay.** Số chiều và khoảng giá trị của chuỗi điểm mốc; lớp ký hiệu được tham chiếu có tồn tại; người ký được tham chiếu có tồn tại; quan hệ giữa mẫu, phiên thu và phạm vi tenant có nhất quán (mục 2.2.6). Toàn bộ nhóm này phải được kiểm **ở máy chủ**, kể cả khi máy khách đã kiểm — không phải vì nghi ngờ người dùng, mà vì một máy khách lỗi tạo ra dữ liệu sai giống hệt một máy khách cố ý.

**Kiểm tra tính đầy đủ — máy thực hiện được, nhưng là câu hỏi khác.** Mẫu có đủ thông tin để dùng được về sau hay không. Nhóm ràng buộc này thuộc loại **không tái tạo được** theo tiêu chí ở mục 2.1.5, nên chỗ đứng của nó phụ thuộc vào đường mà dữ liệu đi vào (mục 2.6.1):

- **Đường thu có kiểm soát.** Những siêu dữ liệu mà giao thức thu yêu cầu — chẳng hạn người ký, phiên thu, nguồn gốc — phải được kiểm ngay tại thời điểm thu, vì sau thời điểm đó chúng không dựng lại được.
- **Đường nạp dữ liệu đã tồn tại.** Một phần các siêu dữ liệu ấy có thể không tồn tại ở nguồn. Khi đó điều hệ thống làm được không phải là bắt buộc chúng phải có, mà là **ghi nhận mức đầy đủ của nguồn gốc**, để mức ấy quyết định phạm vi sử dụng ở hạ nguồn.

**Đồng thuận không thuộc nhóm kiểm tra này.** Nó được kiểm tại thao tác mà phạm vi đồng thuận điều chỉnh — huấn luyện, phát hành, phân phối — chứ không phải tại thời điểm thu; xem mục 2.9.3. Đưa nó vào cổng kiểm tại đường thu vừa sai vị trí, vừa tạo ra một bảo đảm giả: đồng thuận có thể được rút sau thời điểm thu, nên một phép kiểm chỉ chạy lúc thu không nói gì về trạng thái tại lúc dữ liệu được dùng.

**Rà soát ngữ nghĩa — máy không quyết định thay được.** Người ký có thực hiện đúng ký hiệu của lớp đã chọn không; điều kiện thu có đạt không; mẫu có dùng được về mặt chuyên môn không. Do đó:

\[
\text{Hợp lệ về cấu trúc} \;\nRightarrow\; \text{Được chấp nhận vào bộ dữ liệu}.
\]

Ba loại kiểm tra trên gợi ý một vòng đời khái niệm cho mẫu:

\[
\text{Tiếp nhận} \rightarrow \text{Kiểm tra} \rightarrow \text{Quản lý} \rightarrow \text{Đánh giá điều kiện cho một mục đích cụ thể}.
\]

Cần nêu rõ đây là **vòng đời khái niệm**, dùng để phân biệt các loại điều kiện; nó không hàm ý mọi hệ thống phải có đúng bốn trạng thái mang đúng tên gọi này. Điều bắt buộc về mặt lý thuyết chỉ là: trạng thái "hợp lệ về cấu trúc" và trạng thái "đủ điều kiện cho một mục đích" phải phân biệt được với nhau, vì gộp chúng vào một cờ duy nhất buộc hệ thống hoặc từ chối dữ liệu còn dùng được, hoặc phát hành dữ liệu mà chưa có căn cứ nào về chất lượng.

Hai điểm nữa cần giữ khi đọc chuỗi trên. Thứ nhất, **rà soát ngữ nghĩa không phải một nút bắt buộc** trên chuỗi này: nó là một trong ba cách trả lời câu hỏi chất lượng ngữ nghĩa ở mục 2.1.5, và cách nào được chọn là quyết định quy trình. Thứ hai, bước cuối mang tên "cho một mục đích cụ thể" có chủ đích — điều kiện đủ để một mẫu đi vào một tập huấn luyện nội bộ khác với điều kiện đủ để nó được phát hành ra ngoài. Vì vậy đây không phải một trạng thái tuyệt đối mà mẫu đạt được một lần rồi giữ mãi.

Về những thuộc tính mà **chỉ máy khách quan sát được** — chẳng hạn một chỉ số ổn định của việc phát hiện bàn tay trong lúc thu — máy chủ không thể tái lập chúng. Chúng vẫn có ích như thông tin tham khảo, nhưng không nên được xem là bằng chứng chất lượng và không nên là điều kiện duy nhất để một mẫu được chấp nhận. Ghi nhận chúng kèm nhãn nguồn gốc là cách xử lý trung thực hơn là im lặng coi chúng như dữ liệu đo được. Ngược lại, các thuộc tính thuộc thẩm quyền của máy chủ — thời điểm tiếp nhận, danh tính người thao tác, phạm vi tenant — **không được lấy từ payload** ngay cả khi máy khách có gửi, vì làm vậy cho phép máy khách tự khai báo ngữ cảnh an ninh của chính nó.

### 2.6.10. Giới hạn của biểu diễn điểm mốc

Hai giới hạn phải được phát biểu thẳng và giữ nhất quán trong toàn quyển.

**Điểm mốc bàn tay không phải biểu diễn đầy đủ của ngôn ngữ ký hiệu.** Biểu diễn này không bảo toàn các thành phần phi thủ công như khuôn mặt, đầu và tư thế cơ thể, trong khi những thành phần đó có thể mang thông tin ngôn ngữ \cite{liddell_grammar_2003,bragg_sign_2019}. Việc chọn điểm mốc bàn tay là một quyết định về **phạm vi triển khai**, không phải một tuyên bố rằng ngôn ngữ ký hiệu chỉ gồm bàn tay. Nguyên tắc chung về vị trí của phép biến đổi: nếu hệ thống lưu bản ghi nguồn theo chính sách cho phép, các phép biến đổi có mất mát nên nằm ở hạ nguồn so với điểm lưu nguồn, để có thể tái xử lý khi mục tiêu nghiên cứu thay đổi \cite{kleppmann_designing_2017}.

**Điểm mốc không đương nhiên là dữ liệu ẩn danh.** Việc loại bỏ hình ảnh khuôn mặt làm **giảm mức phơi bày**, nhưng không tự động đưa dữ liệu ra khỏi phạm vi quản trị dữ liệu cá nhân. Hướng dẫn về kỹ thuật ẩn danh nhấn mạnh sự khác biệt giữa dữ liệu thực sự không còn khả năng quy về cá nhân và dữ liệu đã được giảm hoặc tách định danh nhưng vẫn có khả năng liên kết lại \cite{wp29_anonymisation_2014}. Một chuỗi điểm mốc vẫn là dữ liệu về một con người cụ thể; khả năng quy về cá nhân phụ thuộc vào nội dung, dữ liệu liên kết sẵn có và mục đích xử lý — mà trong một nền tảng có quan hệ mẫu–người ký–phiên thu, dữ liệu liên kết là thứ **luôn tồn tại theo thiết kế**. Thuật ngữ dùng thống nhất trong luận văn vì vậy là **"giảm mức phơi bày"** hoặc **"không lộ diện"**, không phải "ẩn danh" \cite{quochoi_luat_bvdlcn_2025}.

### 2.6.11. Nguồn gốc của quá trình thu: ghi gì và không ghi gì

Mục 2.8.5 sẽ trình bày khung đối tượng – hoạt động – chủ thể cho nguồn gốc nói chung. Riêng với hoạt động thu, có thể liệt kê các chiều nguồn gốc cần cân nhắc: **ai** (người ký, người vận hành), **cái gì** (lớp ký hiệu, mẫu), **khi nào** (phiên thu, thời điểm), **bằng cách nào** (phương thức thu, biểu diễn), và **trong phạm vi nào** (tenant, dự án, điều kiện đồng thuận và sử dụng).

Nguyên tắc ở đây mang tính **giới hạn**, không phải một lời kêu gọi thu thập nhiều hơn:

> Nguồn gốc của quá trình thu chỉ nên ghi những thuộc tính bối cảnh thực sự cần cho nghiên cứu, quản trị hoặc truy vết vận hành. Thu thập thêm siêu dữ liệu **không tự động tốt hơn**, vì mỗi thuộc tính được ghi thêm đều làm tăng gánh nặng quản lý và mở rộng phạm vi dữ liệu cá nhân phải bảo vệ.

Nguyên tắc này là đối trọng cần thiết với toàn bộ mục 2.1.3: bảng siêu dữ liệu tối thiểu ở đó được xây dựng theo tiêu chí *thiếu nó thì câu hỏi nào không trả lời được*, chứ không theo tiêu chí *ghi được gì thì ghi*. Hai mục đọc cùng nhau xác lập cả cận dưới lẫn cận trên của siêu dữ liệu cần thu.

## 2.7. Xử lý, giao dịch và lưu trữ nội dung

### 2.7.1. Xử lý đồng bộ và xử lý bất đồng bộ

**Xử lý đồng bộ** thực hiện toàn bộ công việc trong vòng đời của một yêu cầu:

\[
\text{Yêu cầu} \rightarrow \text{Xử lý} \rightarrow \text{Phản hồi}.
\]

Mô hình này phù hợp với các thao tác ngắn và có kết quả xác định nhanh. Ưu điểm là đơn giản — không có trạng thái trung gian, không có hàng đợi, người dùng nhận kết quả ngay. Nó không phù hợp với công việc mà thời gian thực hiện không dự đoán được hoặc phụ thuộc dịch vụ bên ngoài, vì khi đó thời gian phản hồi bằng thời gian của bước chậm nhất, và một lỗi tạm thời ở giữa đường làm hỏng toàn bộ thao tác.

**Xử lý bất đồng bộ** tách đường tiếp nhận khỏi đường thực thi \cite{kleppmann_designing_2017}:

\[
\text{Yêu cầu} \rightarrow \text{Hàng đợi} \rightarrow \text{Worker} \rightarrow \text{Kết quả}.
\]

Mô hình hàng đợi tác vụ gồm ba vai chính: **producer** tạo tác vụ; **broker** lưu và điều phối thông điệp; **worker** nhận và thực thi. Celery là framework hàng đợi tác vụ hỗ trợ mô hình này \cite{celery_contributors_celery_2026}; Redis có thể đảm nhiệm vai trò broker hoặc backend tùy cấu hình \cite{redis_ltd_redis_2026}. Việc lựa chọn công nghệ cụ thể thuộc Chương 3.

**Bảng 2-28. So sánh xử lý đồng bộ và xử lý bất đồng bộ**

| Tiêu chí | Đồng bộ | Bất đồng bộ |
|---|---|---|
| Có kết quả ngay trong phản hồi | Có | Không nhất thiết |
| Phù hợp với công việc dài | Không | Có |
| Khả năng thử lại độc lập | Khó | Tốt hơn |
| Cô lập thất bại | Thấp | Cao hơn |
| Ngữ cảnh tenant | Thừa hưởng từ yêu cầu | **Phải truyền tường minh** (mục 2.7.6) |

*Nguồn: tác giả tổng hợp từ \cite{kleppmann_designing_2017,hohpe_enterprise_2003}.*

Bảng trên giữ năm tiêu chí. Bản đầy đủ, bổ sung độ phức tạp triển khai, độ trễ của yêu cầu, lượng trạng thái phải quản lý và yêu cầu về quan trắc, được trình bày tại **Phụ lục F.7, Bảng F-11**.

**Định hướng được chọn.** Kết luận đúng không phải "hệ thống là hệ thống bất đồng bộ", mà là một quy tắc phân loại: **các thao tác ngắn giữ nguyên xử lý đồng bộ, các thao tác dài hoặc cần thử lại được chuyển sang worker nền**. Phát biểu này tránh hai sai lầm đối xứng — đưa mọi thứ vào hàng đợi làm hệ thống phức tạp không cần thiết, và giữ mọi thứ trong request làm các thao tác dài trở nên mong manh.

**Đánh đổi.** Bất đồng bộ chuyển chi phí từ độ trễ sang **độ phức tạp của trạng thái và nhu cầu quan trắc**, đồng thời mang theo hai vấn đề được phân tích riêng ở hai mục tiếp theo: ngữ nghĩa giao nhận, và ranh giới giao dịch.

### 2.7.2. Ngữ nghĩa giao nhận, thử lại và tính lũy đẳng

Trong hệ thống phân tán, một worker có thể thực hiện xong tác vụ nhưng thất bại trước khi xác nhận, hoặc broker có thể giao lại thông điệp khi trạng thái hoàn thành chưa rõ. Vì vậy ứng dụng không nên giả định ngữ nghĩa giao nhận đúng một lần \cite{kleppmann_designing_2017}:

\[
\text{Không giả định } \textit{exactly-once}; \text{ thiết kế cho } \textit{at-least-once} + \text{xử lý lũy đẳng}.
\]

Đây không phải khiếm khuyết của một sản phẩm hàng đợi cụ thể mà là hệ quả của việc không thể phân biệt, từ phía người gửi, giữa "người nhận chưa xử lý" và "người nhận đã xử lý nhưng xác nhận bị mất" \cite{kleppmann_designing_2017}.

Biện pháp tương ứng là **tính lũy đẳng (idempotency)**. Với trạng thái hệ thống \(S\) và tác vụ \(t\):

\[
apply(apply(S,t),t)=apply(S,t).
\]

Ví dụ trong miền bài toán: nếu tác vụ tạo một bản ghi mẫu sau khi tải tệp lên, lần thử lại không được tạo ra hai mẫu độc lập cho cùng một lần đóng góp — đây chính là chiều *tính duy nhất* ở Bảng 2-4, và nó cho thấy một thuộc tính chất lượng dữ liệu phụ thuộc trực tiếp vào một quyết định kiến trúc xử lý. Tính lũy đẳng có thể được hỗ trợ bằng idempotency key, ràng buộc duy nhất ở cơ sở dữ liệu, kiểm tra trạng thái xử lý, hoặc thiết kế upsert phù hợp.

Điểm cần lưu ý: **các bước khác nhau trong cùng một tác vụ có thể có mức lũy đẳng khác nhau**, và mức bảo đảm của cả tác vụ bằng mức của bước yếu nhất. Một bước ghi tệp cục bộ dễ làm cho lũy đẳng hơn một bước gọi dịch vụ bên ngoài.

Các mẫu như *Idempotent Receiver*, *Guaranteed Delivery* và *Dead Letter Channel* được mô tả trong các mẫu tích hợp hệ thống doanh nghiệp \cite{hohpe_enterprise_2003}. Đối với lỗi tạm thời, retry cần có giới hạn và khoảng giãn phù hợp; đối với lỗi vĩnh viễn, tác vụ cần đi vào trạng thái quan sát được để xử lý thay vì lặp vô hạn hoặc biến mất. Nguyên tắc chung: một tác vụ thất bại phải để lại **dấu vết có thể truy vấn**, vì khác với lỗi trong request, nó không có người dùng nào đang chờ để phát hiện ra nó.

### 2.7.3. Ranh giới giao dịch

Trước khi bàn về nhất quán giữa hai kho, cần xác định đơn vị nhất quán bên trong một kho. Một giao dịch cơ sở dữ liệu tạo ra một ranh giới mà bên trong đó nhiều thao tác được xem là một đơn vị duy nhất: hoặc toàn bộ có hiệu lực, hoặc không thao tác nào có hiệu lực. Bốn thuộc tính thường được gán cho ranh giới này — tính nguyên tử, tính nhất quán, tính cô lập và tính bền vững — được hệ thống hóa trong \cite{harder_principles_1983}.

Ý nghĩa đối với bài toán không nằm ở định nghĩa mà ở **phạm vi** của ranh giới. Một thao tác tạo mẫu thường gồm nhiều thao tác ghi liên quan: bản ghi mẫu, quan hệ tới người ký và phiên thu, cập nhật số đếm, ghi sự kiện kiểm toán. Tất cả những thao tác này nằm trong cùng một cơ sở dữ liệu, nên chúng **có thể** nằm trong một giao dịch: hoặc mẫu tồn tại đầy đủ với mọi quan hệ, hoặc không tồn tại. Đây cũng là ranh giới mà ngữ cảnh tenant được gắn vào ở mục 2.4.7 . Cả hai đều cần cùng một đơn vị công việc.

Nhưng phát biểu quan trọng là phát biểu phủ định: **việc ghi một tệp vào kho nội dung bên ngoài nằm ngoài ranh giới đó**. Kho tệp không tham gia giao dịch của cơ sở dữ liệu; nó không nhận lệnh hoàn tác khi giao dịch bị hủy. Đây chính là nguồn gốc của bài toán ở mục tiếp theo, và nó là hệ quả trực tiếp của quyết định lưu nội dung ngoài cơ sở dữ liệu ở mục 2.7.5 — một ví dụ điển hình cho việc một lựa chọn kiến trúc tạo ra một lớp vấn đề mới thay vì chỉ tối ưu một chỉ số.

### 2.7.4. Nhất quán giữa hai kho lưu trữ

Khi một thao tác nghiệp vụ phải ghi vào cả cơ sở dữ liệu lẫn kho nội dung, có ba chiến lược.

**Chiến lược A — ghi kép trực tiếp.** Ứng dụng lần lượt ghi vào hai kho. Đơn giản nhất và cũng yếu nhất: nếu ghi cơ sở dữ liệu thành công nhưng ghi tệp thất bại, hệ thống có bản ghi trỏ tới tệp không tồn tại; nếu ngược lại, hệ thống có tệp mồ côi không ai tham chiếu. Không có bước nào trong quy trình phát hiện hai trạng thái này.

**Chiến lược B — giao dịch phân tán.** Hai kho cùng tham gia một giao thức cam kết chung, chẳng hạn cam kết hai pha. Về nguyên tắc đạt được tính nguyên tử xuyên hệ thống. Trên thực tế, giao thức đòi hỏi mọi bên tham gia phải hỗ trợ nó — điều mà phần lớn kho tệp và dịch vụ lưu trữ đối tượng không đáp ứng — đồng thời làm tăng độ phức tạp vận hành và tạo ra trạng thái treo khi một bên không phản hồi \cite{kleppmann_designing_2017}.

**Chiến lược C — giao dịch cục bộ kèm khôi phục bất đồng bộ.** Ứng dụng thực hiện một giao dịch cục bộ trong cơ sở dữ liệu, trong đó ghi cả dữ liệu nghiệp vụ lẫn một bản ghi mô tả **công việc còn phải hoàn tất**. Hai thứ này cùng nằm trong một giao dịch, nên hoặc cùng tồn tại hoặc cùng không. Sau đó một tiến trình riêng đọc bản ghi công việc, thực hiện tác động ra kho ngoài, và đánh dấu hoàn tất — có thử lại khi thất bại. Đây là mẫu **hộp thư đi có giao dịch (transactional outbox)** \cite{richardson_microservices_2018}.

Điểm cốt lõi của chiến lược C: nó không loại bỏ khả năng hai kho lệch nhau tại một thời điểm, mà **biến sự lệch đó thành một trạng thái tường minh, có thể truy vấn và có thể khôi phục**, thay vì một sự cố im lặng. Hệ thống luôn biết còn công việc nào chưa xong. Tính nhất quán đạt được là nhất quán cuối cùng, không phải nhất quán tức thời — và đây là điều phải phát biểu thẳng thay vì che đi.

**Bảng 2-29. So sánh ba chiến lược nhất quán giữa cơ sở dữ liệu và kho nội dung**

| Tiêu chí | A. Ghi kép trực tiếp | B. Giao dịch phân tán | C. Giao dịch cục bộ + khôi phục bất đồng bộ |
|---|---|---|---|
| Tính nguyên tử xuyên hệ thống | Không | Cao | Nhất quán cuối cùng |
| Yêu cầu đối với kho ngoài | Không | **Phải hỗ trợ giao thức cam kết** | Không |
| Phát hiện được trạng thái lệch | Không | Không phát sinh | **Có — trạng thái tường minh** |
| Rủi ro tệp mồ côi / tham chiếu hỏng | Cao | Thấp | Thấp, có đối soát |
| Định hướng được chọn | | | **Được chọn** |

*Nguồn: tác giả tổng hợp từ \cite{kleppmann_designing_2017,harder_principles_1983,richardson_microservices_2018,hohpe_enterprise_2003}.*

Bảng trên giữ năm tiêu chí. Bản đầy đủ, bổ sung mức đơn giản khi mới triển khai, cơ chế thử lại và độ phức tạp vận hành, được trình bày tại **Phụ lục F.7, Bảng F-12**.

**Định hướng được chọn và lý do.** Chiến lược C phù hợp: chiến lược B bị loại vì kho nội dung thông thường không tham gia được giao thức cam kết chung, còn chiến lược A bị loại vì nó không cung cấp cách nào để **biết** rằng hệ thống đang ở trạng thái lệch.

**Đánh đổi.** Nhất quán chỉ đạt được sau một khoảng thời gian, nên mọi thành phần đọc dữ liệu phải chấp nhận rằng một bản ghi có thể tồn tại trước khi nội dung của nó sẵn sàng — trạng thái đó cần được biểu diễn trong mô hình dữ liệu thay vì bị coi là bất thường. Hệ thống cũng phải mang thêm một tiến trình nền và cơ chế đối soát định kỳ. Cuối cùng, chiến lược C **không tự bảo đảm tính lũy đẳng** của tác động ra kho ngoài: nếu bước đó chạy lại, nó phải an toàn theo nghĩa ở mục 2.7.2, và điều này phải được bảo đảm riêng cho từng loại tác động.

### 2.7.5. Lưu nội dung trong cơ sở dữ liệu hay bên ngoài

**Lưu nội dung trong cơ sở dữ liệu.** Tệp được lưu như một trường nhị phân trong bảng. Ưu điểm là siêu dữ liệu và nội dung nằm trong cùng một giao dịch — nghĩa là toàn bộ bài toán ở mục 2.7.4 **không phát sinh** — và sao lưu cơ sở dữ liệu bao trọn cả nội dung. Nhược điểm là kích thước cơ sở dữ liệu tăng nhanh, và tệp lớn không phải loại tải công việc mà một hệ quản trị quan hệ được tối ưu cho.

**Lưu nội dung ngoài cơ sở dữ liệu.** Cơ sở dữ liệu giữ định danh, siêu dữ liệu, tham chiếu và khóa phạm vi; kho nội dung giữ tệp. Ưu điểm là mỗi hệ thống làm đúng việc của mình và cơ sở dữ liệu giữ được kích thước hợp lý.

**Bảng 2-30. So sánh lưu nội dung trong cơ sở dữ liệu và lưu bên ngoài**

| Tiêu chí | Nội dung trong CSDL | Nội dung ngoài CSDL + siêu dữ liệu trong CSDL |
|---|---|---|
| Tính đơn giản của giao dịch | Cao — một ranh giới giao dịch duy nhất | Thấp hơn — hai kho, cần chiến lược ở mục 2.7.4 |
| Phù hợp với tệp lớn | Thấp | Cao |
| Tốc độ tăng kích thước CSDL | Cao | Thấp |
| Vấn đề nhất quán xuyên kho | Không phát sinh | **Phải quản lý** |
| Cưỡng chế cô lập | Theo cơ chế của CSDL | Cần điểm kiểm soát riêng cho đường đọc nội dung |
| Định hướng cho nội dung dung lượng lớn | | **Được chọn** |

*Nguồn: tác giả tổng hợp từ \cite{kleppmann_designing_2017,saltzer_protection_1975}.*

Bảng trên giữ sáu tiêu chí. Bản đầy đủ, bổ sung khả năng mở rộng độc lập hai tầng, truy vấn theo siêu dữ liệu và cách sao lưu, được trình bày tại **Phụ lục F.7, Bảng F-13**.

**Định hướng được chọn và lý do.** Với nội dung dung lượng lớn — bản ghi hình, tệp đặc trưng, gói công bố — phương án lưu ngoài cơ sở dữ liệu là phù hợp, vì kích thước và mẫu truy cập của loại nội dung này không tương thích với tải công việc của một hệ quản trị quan hệ.

**Đánh đổi.** Lựa chọn này tạo ra hai nghĩa vụ mới. Thứ nhất là **nhất quán xuyên kho**, giải quyết bằng chiến lược ở mục 2.7.4. Thứ hai là **cô lập ở đường đọc nội dung**: nếu siêu dữ liệu được RLS bảo vệ nhưng backend chấp nhận một khóa tệp tùy ý và trả nội dung mà không kiểm phạm vi, ranh giới tenant bị phá vỡ ở tầng lưu trữ dù cơ sở dữ liệu vẫn đúng policy. Đây là lý do phép đo cô lập ở Chương 4 phải phủ cả hai kho chứ không chỉ cơ sở dữ liệu.

Các yêu cầu đối với kho nội dung không phụ thuộc vào tên sản phẩm: định danh ổn định, kiểm soát truy cập theo phạm vi, khả năng kiểm tra toàn vẹn khi cần, và xử lý nhất quán với retry.

### 2.7.6. Cô lập tenant trong đường xử lý nền

Mục 2.4.1 đã nêu tác vụ nền là một trong hai tầng dễ bị bỏ sót khi thiết kế cô lập. Vấn đề chính xác là: tác vụ nền chạy **ngoài vòng đời của yêu cầu**, nên nó không có sẵn ngữ cảnh tenant lấy từ phiên người dùng. Điều này tạo ra ba yêu cầu.

Thứ nhất, **ngữ cảnh tenant phải là một phần của định nghĩa tác vụ**, được truyền khi tác vụ được tạo ra thay vì được suy ra khi tác vụ chạy. Thứ hai, worker phải thiết lập ngữ cảnh đó trước khi chạm dữ liệu, theo cùng cơ chế phạm vi giao dịch ở mục 2.4.7. Thứ ba, những công việc nền **hợp lệ** cần chạy ngang nhiều tenant — đối soát dữ liệu, bảo trì theo lịch, đọc nguồn sự thật — cần một cơ chế cấp phạm vi riêng, tường minh và tách biệt, chứ không nên được biểu diễn bằng cách để trống ngữ cảnh tenant.

Lý do cho yêu cầu thứ ba đáng được nêu rõ: nếu "chạy thay mọi tenant" được biểu diễn bằng **sự vắng mặt** của ngữ cảnh, thì mọi lỗi quên thiết lập ngữ cảnh đều vô tình trở thành một đặc quyền toàn hệ thống — đúng dạng fail-open mà mục 2.4.6 loại trừ. Một phạm vi đặc biệt phải là một giá trị được đặt có chủ đích, không phải một trạng thái mặc định.

## 2.8. Vòng đời tạo tác nghiên cứu: phiên bản, nguồn gốc và toàn vẹn

### 2.8.1. Trạng thái làm việc và trạng thái đã công bố

Một nền tảng dữ liệu cần tách **trạng thái làm việc** khỏi **trạng thái đã công bố**. Trạng thái làm việc có thể thay đổi khi thêm mẫu, sửa siêu dữ liệu, điều chỉnh danh mục hoặc loại dữ liệu không đạt. Trạng thái đã công bố phải cung cấp một điểm tham chiếu ổn định cho nghiên cứu và trao đổi giữa các hệ thống.

Với một phiên bản \(D_v\) đã công bố tại thời điểm \(t_v\), yêu cầu bất biến có thể biểu diễn \cite{kleppmann_designing_2017}:

\[
Published(D_v) \Rightarrow \forall t>t_v: D_v(t)=D_v(t_v).
\]

Nếu cần thay đổi nội dung, hệ thống tạo phiên bản mới \(D_{v+1}\) thay vì ghi đè \(D_v\). Cách tổ chức này giữ cho kết quả nghiên cứu, bản kê hoặc đường đồng bộ đã tham chiếu phiên bản cũ vẫn có thể được kiểm chứng \cite{kleppmann_designing_2017}. Nó cũng chính là **điều kiện tiên quyết** mà mục 2.3.4 đã nêu: cơ chế ghim phiên bản danh mục chỉ có ý nghĩa khi phiên bản được ghim là bất biến. Và nó là điều kiện để lập luận về phi chuẩn hóa có chủ đích ở mục 2.1.6 đứng vững: một bản sao trong ảnh chụp chỉ chấp nhận được vì ảnh chụp không được phép thay đổi.

### 2.8.2. Ba mô hình quản lý phiên bản bộ dữ liệu

**Mô hình A — Bộ dữ liệu khả biến.** Một định danh bộ dữ liệu trỏ tới trạng thái hiện tại. Đơn giản nhất và không tốn thêm lưu trữ. Nhược điểm là "bộ dữ liệu A hôm qua" và "bộ dữ liệu A hôm nay" có thể không giống nhau, mà **không có cách nào phân biệt** hai trạng thái đó khi đọc một kết quả nghiên cứu tham chiếu tới "bộ dữ liệu A". Khả năng tái lập gần như bằng không.

**Mô hình B — Ảnh chụp đầy đủ theo phiên bản.** Mỗi phiên bản là một bản sao đầy đủ của toàn bộ nội dung. Dễ hiểu, ổn định, và một phiên bản là một đối tượng tự chứa. Nhược điểm là trùng lặp lưu trữ tăng theo số phiên bản — nghiêm trọng khi nội dung gồm tệp phương tiện, vì hai phiên bản khác nhau ở vài mẫu vẫn nhân đôi toàn bộ dữ liệu.

**Mô hình C — Ảnh chụp theo bản kê tham chiếu.** Một phiên bản không chứa nội dung mà chứa **danh sách tham chiếu** tới các đối tượng thành phần ở đúng trạng thái của chúng, kèm phiên bản danh mục được ghim:

\[
DatasetVersion = \{\,r_1, r_2, \ldots, r_n\,\} \ \cup\ \{\,VocabularyVersion\,\}.
\]

Ổn định về thành phần như mô hình B nhưng không nhân bản nội dung, đồng thời làm cho quan hệ nguồn gốc trở nên tường minh vì bản kê chính là bản ghi về việc phiên bản này gồm những gì.

**Điều kiện tiên quyết của mô hình C** cần được nêu rõ vì nó dễ bị bỏ qua: các đối tượng được tham chiếu **cũng phải bất biến hoặc có phiên bản**. Nếu bản kê trỏ tới một đối tượng còn có thể thay đổi tại chỗ, thì phiên bản chỉ ổn định về danh sách chứ không ổn định về nội dung — một dạng ổn định giả, nguy hiểm hơn mô hình A vì nó tạo ra ấn tượng sai về khả năng tái lập.

**Bảng 2-31. So sánh ba mô hình quản lý phiên bản bộ dữ liệu**

| Tiêu chí | A. Khả biến | B. Ảnh chụp đầy đủ | C. Bản kê tham chiếu |
|---|---|---|---|
| Tham chiếu lịch sử | Không có | Có | Có |
| Khả năng tái lập | Thấp | Cao | Cao |
| Chi phí lưu trữ | Thấp | Cao — nhân bản theo phiên bản | Thấp hơn B đáng kể |
| Điều kiện tiên quyết | — | — | **Đối tượng được tham chiếu phải bất biến** |
| Định hướng được chọn | | | **Được chọn** |

*Nguồn: tác giả tổng hợp.*

**Định hướng được chọn và lý do.** Mô hình bản kê tham chiếu thỏa mãn đồng thời hai yêu cầu vốn xung đột trong hai mô hình còn lại: khả năng tái lập của mô hình B và chi phí lưu trữ của mô hình A. Với dữ liệu gồm tệp phương tiện, khoảng cách chi phí giữa B và C không phải chi tiết kỹ thuật mà là điều kiện khả thi.

**Hai mức phiên bản và vai trò khác nhau của chúng.** Đây là phân biệt dễ mất nhất trong cả mục 2.8, vì tiếng Việt dùng một chữ "phiên bản" cho cả hai:

\[
\text{Phiên bản danh mục} \ \neq\ \text{Phiên bản bộ dữ liệu}.
\]

Phiên bản **danh mục** cố định *không gian nhãn*: tại một trạng thái danh mục xác định, tập lớp – phương ngữ – nhóm từ vựng là gì. Phiên bản **bộ dữ liệu** cố định *thành phần mẫu*: đúng những mẫu nào đã đi vào một lần dùng cụ thể. Hai câu hỏi khác nhau, và cơ chế trả lời chúng cũng khác nhau.

Quan hệ giữa hai mức là quan hệ **điều kiện cần**, không phải quan hệ tương đương:

\[
\text{Ghim phiên bản danh mục} \Rightarrow \text{cố định không gian nhãn},
\]
\[
\text{cố định không gian nhãn} \ \not\Rightarrow\ \text{bộ dữ liệu tái lập được}.
\]

Muốn một bộ dữ liệu tái lập được, cần **cả hai**: không gian nhãn cố định *và* tập mẫu cố định. Phần thứ hai là thứ bản kê tham chiếu của mô hình C cung cấp.

Hai mức vì vậy phục vụ hai mục đích khác nhau và không thay thế nhau: phiên bản hoá **danh mục** phục vụ cố định không gian nhãn; phiên bản hoá **bộ dữ liệu** phục vụ cố định thành phần mẫu, và được trình bày ở đây như một **hướng mở rộng của vòng đời tạo tác dữ liệu**. Mức độ hiện thực của từng mức thuộc phạm vi Chương 3.

Phân biệt này cũng là lý do luận văn không phát biểu rằng cơ chế danh mục có phiên bản tự nó làm cho một bộ dữ liệu tái lập được. Phát biểu đúng và hẹp hơn: nó **bảo toàn không gian nhãn** ứng với một trạng thái danh mục xác định.

**Đánh đổi.** Mô hình này đòi hỏi quản lý một đồ thị tham chiếu, và tính đúng đắn của nó phụ thuộc vào một tính chất của các đối tượng khác — tính bất biến — chứ không chỉ phụ thuộc vào chính nó. Nói cách khác, mô hình C **chuyển một phần nghĩa vụ sang tầng lưu trữ đối tượng**, và nghĩa vụ đó phải được kiểm chứng chứ không giả định.

> ### ▣ HÌNH 2-8 — Ba mô hình quản lý phiên bản bộ dữ liệu
> **Loại:** sơ đồ ba nhánh · **Công cụ đề nghị:** draw.io
> **Phải thể hiện:** nhánh A một nút "Bộ dữ liệu A" trỏ tới tập mẫu hiện tại, kèm chú "trạng thái hôm qua không truy lại được"; nhánh B ba khối v1/v2/v3, mỗi khối chứa **bản sao đầy đủ** của cùng phần lớn mẫu (thể hiện rõ sự nhân bản); nhánh C ba bản kê v1/v2/v3 gồm các **mũi tên tham chiếu** trỏ về một kho mẫu bất biến dùng chung, cộng một mũi tên "ghim phiên bản danh mục"; dưới nhánh C ghi điều kiện tiên quyết "đối tượng được tham chiếu phải bất biến".
> **Chú thích dưới hình:** *Hình 2-8: Ba mô hình quản lý phiên bản bộ dữ liệu và chi phí lưu trữ tương ứng.*

### 2.8.3. Nguồn gốc và phiên bản là hai khái niệm khác nhau

Hai khái niệm này thường bị dùng thay thế cho nhau nhưng trả lời hai câu hỏi khác nhau.

**Nguồn gốc (provenance)** trả lời: *dữ liệu này đến từ đâu, qua những bước nào, do ai?* **Phiên bản (versioning)** trả lời: *trạng thái nào đã được sử dụng?* Nó là một nhãn cố định trỏ tới một nội dung bất biến.

Hai khái niệm bổ sung cho nhau và không thay thế nhau. Một hệ thống có phiên bản nhưng không có nguồn gốc biết chính xác *cái gì* đã được dùng nhưng không biết cái đó *hình thành ra sao* — đủ để tái chạy một thí nghiệm, không đủ để trả lời một yêu cầu của chủ thể dữ liệu hay để điều tra một vấn đề chất lượng. Ngược lại, một hệ thống có nguồn gốc nhưng không có phiên bản biết dữ liệu hình thành ra sao nhưng không xác định được trạng thái nào đã được dùng ở một thời điểm cụ thể.

### 2.8.4. Ba nghĩa của "toàn vẹn"

Thuật ngữ "toàn vẹn" xuất hiện nhiều lần trong chương với những nghĩa khác nhau, và việc trộn chúng là một nguồn nhầm lẫn thường gặp. Cần tách ba nghĩa.

**Bảng 2-32. Ba nghĩa của "toàn vẹn" và cơ chế tương ứng**

| Nghĩa | Câu hỏi bảo đảm | Cơ chế | Trình bày ở |
|---|---|---|---|
| Toàn vẹn quan hệ | Dữ liệu có thỏa mãn các ràng buộc cấu trúc của miền không? | Khóa chính, khóa ngoại, ràng buộc miền, ràng buộc xuyên phạm vi | 2.1.6, 2.2.6 |
| Toàn vẹn lịch sử | Trạng thái đã công bố có còn nguyên như lúc công bố không? | Phiên bản bất biến, tách trạng thái làm việc và đã công bố | 2.8.1, 2.8.2 |
| Toàn vẹn nội dung | Chuỗi byte của tệp có bị thay đổi không, và ai công bố nó? | Giá trị băm, bản kê, chữ ký số | 2.8.6 |

*Nguồn: tác giả tổng hợp.*

Ba nghĩa này độc lập, và một hệ thống có thể đạt nghĩa này mà hỏng nghĩa kia. Một tệp có giá trị băm khớp hoàn toàn (toàn vẹn nội dung đạt) vẫn có thể được tham chiếu bởi một bản ghi trỏ sang tenant khác (toàn vẹn quan hệ hỏng). Một cơ sở dữ liệu có mọi ràng buộc hợp lệ (toàn vẹn quan hệ đạt) vẫn có thể để một bản công bố cũ bị ghi đè (toàn vẹn lịch sử hỏng). Vì vậy khi Chương 4 báo cáo kết quả về "toàn vẹn", nó phải nêu rõ đang nói về nghĩa nào.

### 2.8.5. Mô hình nguồn gốc: đối tượng, hoạt động và chủ thể

Để mô hình hóa nguồn gốc một cách có hệ thống thay vì bằng các quan hệ đặc thù, có thể dùng khung khái niệm ba thành phần của mô hình dữ liệu nguồn gốc PROV: **đối tượng (entity)**, **hoạt động (activity)** và **chủ thể (agent)** \cite{moreau_prov_dm_2013}. Quan hệ cơ bản giữa ba thành phần:

\[
\text{Đối tượng} \xrightarrow{\ \text{được sinh ra bởi}\ } \text{Hoạt động} \xrightarrow{\ \text{gắn với}\ } \text{Chủ thể}.
\]

Giá trị của khung này đối với bài toán nằm ở chỗ nó **buộc phải tách ba loại thứ vốn hay bị gộp**: cái gì được tạo ra, quá trình nào tạo ra nó, và ai chịu trách nhiệm cho quá trình đó. Ánh xạ vào miền ứng dụng:

**Bảng 2-33. Ánh xạ khung đối tượng – hoạt động – chủ thể vào miền ứng dụng**

| Thành phần | Trong miền dữ liệu ngôn ngữ ký hiệu |
|---|---|
| Đối tượng | Bản ghi nguồn; chuỗi điểm mốc; phiên bản danh mục; phiên bản bộ dữ liệu; gói công bố |
| Hoạt động | Thu nhận một mẫu; trích xuất điểm mốc; đánh giá chất lượng (nếu có); công bố phiên bản; đồng bộ |
| Chủ thể | Người ký (chủ thể dữ liệu); người vận hành thu; người rà soát (nếu có); tổ chức; thành phần phần mềm thực hiện xử lý |

*Nguồn: tác giả ánh xạ theo khung khái niệm của \cite{moreau_prov_dm_2013}.*

Hai nhận xét quan trọng rút ra từ bảng này.

Thứ nhất, hàng "chủ thể" chứa **nhiều loại chủ thể khác nhau cho cùng một đối tượng**, và đây chính là nội dung của mục 2.9.1: người ký, người vận hành và tổ chức là ba chủ thể riêng biệt gắn với cùng một mẫu qua những hoạt động khác nhau. Một lược đồ chỉ có một trường "người tạo" đã gộp ba vai này lại và không thể tách ra về sau.

Thứ hai, khung này làm rõ vì sao mắt xích đầu tiên trong chuỗi nguồn gốc có vị trí đặc biệt: hoạt động **thu nhận** là hoạt động duy nhất mà chủ thể gắn với nó — người ký — không suy ra được từ dữ liệu hệ thống. Các hoạt động sau đều để lại dấu vết trong hệ thống và có thể dựng lại; hoạt động đầu thì không.

Cần nêu rõ giới hạn của việc mượn khung này: luận văn sử dụng **nguyên lý phân biệt đối tượng – hoạt động – chủ thể ở mức mô hình miền**, không tuyên bố tuân thủ đầy đủ đặc tả PROV, không sinh tài liệu PROV và không cung cấp giao diện trao đổi theo chuẩn đó.

> ### ▣ HÌNH 2-9 — Chuỗi nguồn gốc theo khung đối tượng – hoạt động – chủ thể
> **Loại:** sơ đồ ba làn · **Công cụ đề nghị:** draw.io
> **Phải thể hiện:** ba làn ngang — đối tượng, hoạt động, chủ thể; chuỗi thời gian từ trái sang phải qua bốn hoạt động (thu nhận → trích xuất → đánh giá chất lượng → công bố), trong đó hoạt động thứ ba vẽ nét mảnh kèm chú "tuỳ quy trình"; mũi tên "được sinh ra bởi" nối làn đối tượng xuống làn hoạt động, mũi tên "gắn với" nối làn hoạt động xuống làn chủ thể; hoạt động **thu nhận** được tô nhấn kèm chú "chủ thể của hoạt động này không suy ra được từ dữ liệu hệ thống — phải ghi tại thời điểm thu".
> **Chú thích dưới hình:** *Hình 2-9: Chuỗi nguồn gốc theo khung đối tượng – hoạt động – chủ thể.*

### 2.8.6. Hàm băm, bản kê và chữ ký số

Hàm băm mật mã ánh xạ nội dung có độ dài bất kỳ thành giá trị băm có độ dài cố định. SHA-2 được chuẩn hóa trong FIPS 180-4 \cite{nist_fips180_4_2015}. Với mục tiêu phát hiện thay đổi:

\[
H = \mathrm{SHA256}(\text{Nội dung}), \qquad \text{Nội dung}' \neq \text{Nội dung} \Rightarrow \mathrm{SHA256}(\text{Nội dung}') \neq H
\]

với xác suất rất cao trong điều kiện thực tế. Khi một phiên bản gồm nhiều tệp, các định danh, siêu dữ liệu cần thiết và giá trị băm có thể được tập hợp trong một **bản kê (manifest)** để mô tả chính xác nội dung của bản phát hành.

Giá trị băm chứng minh nội dung không đổi, nhưng **không tự chứng minh ai là bên đã công bố giá trị đó**. Một bên tấn công thay đổi được cả nội dung lẫn giá trị băm đi kèm sẽ tạo ra một cặp nhất quán mà phép kiểm băm không phát hiện được. Chữ ký số bổ sung đúng thuộc tính còn thiếu này, theo lược đồ ký được chuẩn hoá trong \cite{josefsson_edwards-curve_2017}:

\[
\text{Chữ ký} = \mathrm{Sign}_{\text{khóa riêng}}(\text{Bản kê}),
\]

và bên xác minh dùng khóa công khai tương ứng để kiểm tra. Ed25519 là một biến thể EdDSA được thiết kế cho chữ ký hiệu năng cao \cite{bernstein_high-speed_2012} và được chuẩn hóa trong RFC 8032 \cite{josefsson_edwards-curve_2017}. Thuật toán ký có tính xác định, không phụ thuộc vào một nonce ngẫu nhiên mới cho mỗi chữ ký \cite{josefsson_edwards-curve_2017}.

**Bảng 2-34. Ba cơ chế và thuộc tính mà mỗi cơ chế thực sự bảo đảm**

| Cơ chế | Phát hiện nội dung bị thay đổi | Xác minh bên đã công bố | Ngăn được việc sửa đổi |
|---|---|---|---|
| Số phiên bản | Không — số có thể bị gán lại | Không | Không |
| Giá trị băm | Có, nếu giá trị băm tham chiếu đáng tin | Không | Không |
| Chữ ký số trên bản kê | Có | Có, với bên tin cậy khóa công khai | Không |

*Nguồn: tác giả tổng hợp từ \cite{nist_fips180_4_2015,bernstein_high-speed_2012,josefsson_edwards-curve_2017}.*

Cột cuối dẫn tới một phân biệt thuật ngữ phải giữ nhất quán trong toàn quyển: **tamper-evident** khác **tamper-proof**. Hash và chữ ký giúp thay đổi trái với bản kê được **phát hiện** khi xác minh; chúng không làm cho việc sửa hoặc xóa tệp trên thiết bị lưu trữ trở thành bất khả thi. Bảo vệ khóa riêng, phân quyền lưu trữ, sao lưu và khả năng phục hồi vẫn là các vấn đề riêng.

### 2.8.7. Xác minh fail-closed và hợp nhất chỉ bổ sung

Khi một tạo tác được quy định phải có hash hoặc chữ ký hợp lệ, phía tiêu thụ cần xử lý lỗi xác minh theo hướng fail-closed: **không sử dụng tạo tác như hợp lệ nếu hash hoặc chữ ký không khớp** \cite{saltzer_protection_1975}. Cần nêu rõ hành vi sai thường gặp: tự động quay về một bản khác khi xác minh thất bại, mà không báo trạng thái. Cách xử lý đó nghe có vẻ vững chắc về mặt vận hành nhưng nó **che giấu lỗi toàn vẹn** và âm thầm thay đổi dữ liệu đầu vào của quá trình nghiên cứu — đúng loại thay đổi mà toàn bộ cơ chế phiên bản được dựng lên để ngăn.

Đối với một số luồng đồng bộ, hệ thống có thể sử dụng chiến lược **hợp nhất chỉ bổ sung**: bên nhận thêm những đối tượng đã được công bố mà mình chưa có, nhưng không để một bản đồng bộ cũ tự động xóa dữ liệu hiện hữu.

Chiến lược này có hai giới hạn phải nêu kèm, vì bỏ qua chúng dẫn tới một phát biểu quá mạnh. Thứ nhất, nó **không phải giải pháp tổng quát cho mọi bài toán đồng bộ**: nếu nghiệp vụ yêu cầu truyền thao tác xóa, thay thế hoặc giải quyết cập nhật xung đột, phép hợp nhất chỉ bổ sung không còn mô tả đầy đủ trạng thái. Thứ hai, và tinh vi hơn, hợp nhất chỉ bổ sung **không tự bảo đảm tính đơn điệu của phiên bản**: nó ngăn việc mất dữ liệu, nhưng không tự ngăn một bản công bố cũ được nạp sau một bản mới. Hai tính chất này khác nhau và cần được kiểm chứng riêng — một điểm mà Chương 4 báo cáo trung thực thay vì gộp lại.

## 2.9. Quản trị dữ liệu người tham gia

### 2.9.1. Người thu dữ liệu, người đóng góp và chủ thể dữ liệu

Mục 2.8.5 đã cho thấy nhiều loại chủ thể cùng gắn với một mẫu qua những hoạt động khác nhau. Mục này khai triển hệ quả của điều đó.

Trong một phiên thu, **người thực hiện thao tác thu**, **người đóng góp dữ liệu** và **chủ thể được ghi nhận trong mẫu** có thể là cùng một người nhưng không phải lúc nào cũng trùng:

\[
\text{Người vận hành} \neq \text{Người đóng góp} \neq \text{Chủ thể dữ liệu}.
\]

Chẳng hạn một cán bộ nghiên cứu có thể vận hành thiết bị cho một người tham gia thực hiện ký hiệu; người vận hành tạo yêu cầu nhưng người tham gia mới là chủ thể xuất hiện trong dữ liệu. Hệ quả trực tiếp đối với lược đồ: trường ghi nhận tài khoản đã tạo bản ghi **không phải** trường ghi nhận người ký, và không được dùng thay cho nhau.

Việc tách các vai này giúp hệ thống trả lời ba câu hỏi độc lập: ai thực hiện thao tác kỹ thuật; ai chịu trách nhiệm đưa dữ liệu vào hệ thống; và dữ liệu mô tả hoặc ghi nhận ai. Nếu quan hệ với chủ thể không được ghi lại tại thời điểm thu, hệ thống có thể không còn đủ thông tin để xác định các bản ghi cần xử lý khi có yêu cầu liên quan đến dữ liệu cá nhân — và như đã nêu ở mục 2.8.5, đây là mắt xích duy nhất trong chuỗi nguồn gốc không thể dựng lại về sau.

### 2.9.2. Bốn lớp cho phép và điều kiện sử dụng

Trong nền tảng vừa thu thập vừa phân phối dữ liệu, cần phân biệt ít nhất bốn lớp có chức năng khác nhau.

**Bảng 2-35. Bốn lớp cho phép và điều kiện sử dụng**

| Lớp | Mục đích | Chủ thể/bên liên quan điển hình |
|---|---|---|
| A. Cơ sở xử lý dữ liệu cá nhân | xác lập căn cứ và phạm vi xử lý dữ liệu về cá nhân | chủ thể dữ liệu và bên xử lý/kiểm soát theo quy định áp dụng |
| B. Quyền/khả năng đóng góp | xác nhận bên đưa dữ liệu vào có cơ sở để thực hiện việc đóng góp | người đóng góp / đơn vị cung cấp |
| C. Giấy phép tái sử dụng | quy định quyền sao chép, chia sẻ, tạo bản phái sinh, ghi công | bên có thẩm quyền cấp phép |
| D. Thỏa thuận truy cập/sử dụng | đặt nghĩa vụ cho bên nhận, ví dụ mục đích sử dụng, bảo mật, không tái định danh | bên nhận dữ liệu |

*Nguồn: tác giả tổng hợp.*

Các lớp không thay thế nhau, và quan hệ giữa chúng có hướng: **A và B là các điều kiện tiên quyết để C và D có thể được thiết lập một cách hợp lệ đối với dữ liệu tương ứng**. Giấy phép tái sử dụng không thể thay thế cơ sở hợp pháp để thu thập và xử lý dữ liệu cá nhân, đồng thời không thể cấp nhiều quyền hơn những quyền mà bên cấp phép thực sự có.

Tương tự, license và thỏa thuận truy cập có chức năng khác nhau. License chủ yếu quy định phạm vi quyền tái sử dụng đối tượng được cấp phép; thỏa thuận truy cập có thể bổ sung nghĩa vụ dành riêng cho bên nhận. Việc lựa chọn license cụ thể cho dữ liệu dùng chung là quyết định của Chương 3; Chương 2 giữ mô hình trung lập với loại giấy phép để không đồng nhất quản trị dữ liệu cá nhân với cấp phép tài sản trí tuệ.

Bốn lớp này cũng là chỗ nối với mục 2.3.1: quyền quản trị hạ tầng không nằm ở bất kỳ lớp nào trong bốn lớp trên, nên nó không tạo ra quyền ở lớp nào cả. Và như mục 2.3.2 đã nêu, việc một mẫu nằm trong phạm vi dùng chung không mở rộng các điều kiện ở lớp A và B của chính mẫu đó.

### 2.9.3. Đồng thuận nhị phân và đồng thuận có phiên bản

Một bản ghi đồng thuận chỉ chứa giá trị đúng/sai không đủ để chứng minh chủ thể đã chấp thuận nội dung nào. Ở mức tối thiểu, hệ thống cần liên kết chấp thuận với chủ thể, văn bản, phiên bản và thời điểm:

\[
Consent = (\text{Chủ thể}, \text{Văn bản}, \text{Phiên bản}, \text{Thời điểm}).
\]

Khi phạm vi sử dụng cũng được mô hình hóa tường minh, bản ghi trở thành một bộ năm với thành phần phạm vi bổ sung, cho phép phân biệt các mức sử dụng khác nhau thay vì một chấp thuận duy nhất cho mọi mục đích.

**Bảng 2-36. So sánh đồng thuận nhị phân và đồng thuận có phiên bản**

| Tiêu chí | Đồng thuận nhị phân | Đồng thuận có phiên bản |
|---|---|---|
| Biết đã chấp thuận **nội dung nào** | Không | Có |
| Biết chấp thuận vào thời điểm nào | Không nhất thiết | Có |
| Phân biệt phạm vi sử dụng | Không | Có, nếu phạm vi được mô hình hóa |
| Bằng chứng lịch sử khi văn bản thay đổi | Thấp | Cao |
| Định hướng được chọn | | **Được chọn** |

*Nguồn: tác giả tổng hợp.*

Từ đó phát sinh yêu cầu lưu trữ: phiên bản văn bản đã được dùng để thu chấp thuận phải truy lại được **đúng nội dung**. Nếu nội dung pháp lý hoặc điều kiện xử lý được thay đổi theo cách có thể làm thay đổi ý nghĩa, hệ thống cần tạo phiên bản mới và áp dụng quy trình chấp thuận phù hợp thay vì ghi đè tài liệu cũ. Đây là cùng một yêu cầu bất biến ở mục 2.8.1, áp cho một loại đối tượng khác — nghĩa **toàn vẹn lịch sử** ở Bảng 2-32. Việc một thay đổi cụ thể có yêu cầu xin lại đồng thuận hay không là vấn đề pháp lý/nghiệp vụ; cơ chế kỹ thuật phải bảo đảm lịch sử phiên bản đủ để thực hiện quyết định đó.

### 2.9.4. Bốn mức xử lý khi thu hồi

"Thu hồi" hoặc "xóa" cũng không phải một thao tác duy nhất. Có thể phân biệt bốn mức theo **cơ chế thi hành** — tiêu chí phân loại này quan trọng vì nó cho biết mức nào hệ thống cưỡng chế được và mức nào không.

**Bảng 2-37. Các mức xử lý liên quan đến thu hồi và xóa**

| Mức | Nội dung | Cơ chế chính |
|---|---|---|
| 1 | Thu hồi quyền truy cập trong nền tảng | IAM/RBAC/RLS/session |
| 2 | Loại dữ liệu khỏi các bản phát hành trong tương lai | cổng kiểm tra trong pipeline công bố |
| 3 | Xóa dữ liệu khỏi các kho mà nền tảng kiểm soát | cơ sở dữ liệu + kho nội dung + quy trình vận hành |
| 4 | Xử lý bản sao đã được chuyển hợp pháp cho bên thứ ba | thỏa thuận, nghĩa vụ pháp lý và quy trình ngoài phạm vi kỹ thuật thuần túy |

*Nguồn: tác giả tổng hợp; tiêu chí phân loại là cơ chế thi hành.*

Bốn mức không tự động kéo theo nhau. Hệ thống có thể ngăn một mẫu xuất hiện trong bản phát hành mới nhưng không có khả năng kỹ thuật thu hồi một bản sao đã được bên thứ ba tải về trước đó. Mức 3 đòi hỏi vòng đời xóa phủ **cả hai kho** — đúng nghĩa vụ nhất quán xuyên kho ở mục 2.7.4: xóa một hàng không tự xóa tệp, và một thao tác xóa chỉ hoàn tất khi cả hai kho đã phản ánh nó.

Vì vậy phần mềm không nên hứa một cơ chế thu hồi tuyệt đối đối với dữ liệu đã rời khỏi phạm vi kiểm soát; thay vào đó cần phân biệt rõ những gì hệ thống cưỡng chế được với những nghĩa vụ cần được thực hiện bằng quy trình pháp lý hoặc hợp đồng.

### 2.9.5. Cơ sở pháp lý về bảo vệ dữ liệu cá nhân tại Việt Nam

Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 được ban hành ngày 26/06/2025 và có hiệu lực từ ngày 01/01/2026 \cite{quochoi_luat_bvdlcn_2025}. Nghị định số 356/2025/NĐ-CP quy định chi tiết một số điều và biện pháp thi hành Luật, có hiệu lực cùng ngày 01/01/2026 \cite{chinhphu_nd356_2025}. Đây là các căn cứ pháp lý trực tiếp cần xem xét khi hệ thống xử lý dữ liệu gắn với cá nhân tại Việt Nam.

Ở mức thiết kế phần mềm, các yêu cầu pháp lý liên quan chuyển thành một số năng lực hệ thống cần có. Thứ nhất, để thực hiện yêu cầu của chủ thể dữ liệu, hệ thống phải truy được những bản ghi liên quan đến chủ thể tương ứng — quan hệ mà mục 2.9.1 yêu cầu ghi nhận tại thời điểm thu. Thứ hai, để chứng minh nội dung đã được thông báo hoặc chấp thuận, hệ thống phải bảo toàn phiên bản văn bản và bằng chứng chấp thuận — mục 2.9.3. Thứ ba, kiểm soát truy cập phải giới hạn những người và quy trình được phép xử lý dữ liệu — các mục 2.4 và 2.5. Thứ tư, phải chứng minh được điều gì đã xảy ra với dữ liệu — nhật ký kiểm toán ở mục 2.5.9. Thứ năm, vòng đời xóa phải bao phủ cả siêu dữ liệu và tệp nằm ngoài cơ sở dữ liệu — mục 2.7.5 và mức 3 ở bảng trên.

Đáng chú ý là cả năm năng lực này đều đã phát sinh từ các lập luận kỹ thuật độc lập trước đó trong chương; yêu cầu pháp lý ở đây **củng cố** chứ không tạo mới các ràng buộc kiến trúc. Đây là một dấu hiệu tốt về tính nhất quán của thiết kế: một hệ thống phải thêm cơ chế mới hoàn toàn để đáp ứng nghĩa vụ pháp lý thường là hệ thống đã bỏ sót điều gì đó ở tầng thiết kế dữ liệu.

Việc dữ liệu đã được chuyển sang điểm mốc hoặc dạng đặc trưng không đương nhiên đưa nó ra khỏi phạm vi quản trị dữ liệu cá nhân. Mức độ nhận dạng phải được đánh giá dựa trên khả năng liên kết với cá nhân, dữ liệu phụ trợ và mục đích xử lý \cite{wp29_anonymisation_2014,quochoi_luat_bvdlcn_2025}. Điểm này đã được nêu ở mục 2.6.6 và nhắc lại ở đây vì nó là chỗ mà một suy diễn sai sẽ dẫn tới việc bỏ qua toàn bộ các nghĩa vụ của mục này.

Phần này chỉ chuyển các yêu cầu liên quan thành ràng buộc kiến trúc phục vụ luận văn thuộc lĩnh vực Công nghệ phần mềm; nó không nhằm tuyên bố nền tảng đã đạt tuân thủ pháp lý toàn diện. Đánh giá tuân thủ đầy đủ còn phụ thuộc quy trình vận hành, nội dung văn bản, vai trò pháp lý của các bên và bối cảnh triển khai thực tế.

### 2.9.6. Khả năng tiếp cận như một thuộc tính chất lượng

Nền tảng phục vụ người dùng có nhu cầu và phương thức giao tiếp khác nhau, trong đó có người Điếc và người sử dụng ngôn ngữ ký hiệu. Do đó, khả năng tiếp cận cần được xem là một **thuộc tính chất lượng** của giao diện và quy trình tương tác chứ không phải phần bổ sung sau khi hệ thống đã hoàn thành. Điểm này có ý nghĩa đặc biệt trong bài toán đang xét: cộng đồng mà dữ liệu mô tả cũng chính là một nhóm người dùng của hệ thống, nên một giao diện giả định một phương thức giao tiếp duy nhất sẽ loại trừ chính những người mà nền tảng phục vụ.

Web Content Accessibility Guidelines (WCAG) 2.2 của W3C cung cấp một khung tham chiếu cho việc thiết kế nội dung web có khả năng tiếp cận tốt hơn \cite{w3c_wcag22_2023}. Trong luận văn, WCAG 2.2 được dùng làm **khung tham chiếu** để hình thành yêu cầu giao diện. Chỉ khi có kế hoạch kiểm thử và bằng chứng tương ứng mới nên tuyên bố một mức conform cụ thể; Chương 2 không mặc nhiên khẳng định hệ thống đạt WCAG 2.2 AA hay một mức nào khác.

## 2.10. Kiểu kiến trúc, triển khai và tiến hóa hệ thống

### 2.10.1. Kiểu kiến trúc phần mềm

Trước khi bàn về cách đóng gói và triển khai, cần xác định **kiểu kiến trúc** của chính ứng dụng — một câu hỏi khác hẳn và thường bị lẫn với câu hỏi triển khai.

**Ứng dụng nguyên khối.** Toàn bộ chức năng nằm trong một đơn vị triển khai chính. Ưu điểm là giao dịch đơn giản vì mọi thao tác nằm trong cùng một ranh giới (mục 2.7.3), gỡ lỗi đơn giản vì luồng thực thi liên tục, và triển khai đơn giản vì chỉ có một đơn vị. Nhược điểm là mức phụ thuộc lẫn nhau giữa các phần có thể tăng dần nếu không có kỷ luật phân tách, và việc mở rộng riêng một năng lực khó thực hiện.

**Nguyên khối có mô-đun.** Vẫn một đơn vị triển khai chính, nhưng bên trong được chia thành các mô-đun có ranh giới rõ ràng và phụ thuộc được kiểm soát. Giữ được sự đơn giản về giao dịch và vận hành của kiểu thứ nhất, đồng thời giữ được ranh giới trách nhiệm. Nhược điểm là ranh giới mang tính logic — nó phụ thuộc vào kỷ luật chứ không được cưỡng chế bởi mạng — và việc mở rộng vẫn chủ yếu ở mức toàn ứng dụng.

**Vi dịch vụ.** Các dịch vụ được triển khai độc lập, giao tiếp qua mạng. Cho phép mở rộng và triển khai độc lập từng năng lực, và ranh giới quyền sở hữu giữa các nhóm rõ ràng. Đổi lại, hệ thống thừa hưởng toàn bộ vấn đề của hệ phân tán: lỗi mạng, giao dịch trải trên nhiều dịch vụ, độ phức tạp quan trắc, chi phí triển khai, và nhu cầu quản lý tiến hóa hợp đồng giữa các dịch vụ \cite{newman_building_2021}.

**Bảng 2-38. So sánh ba kiểu kiến trúc phần mềm**

| Tiêu chí | Nguyên khối | Nguyên khối có mô-đun | Vi dịch vụ |
|---|---|---|---|
| Tính đơn giản của giao dịch | Cao | Cao | Thấp — phải xử lý xuyên dịch vụ |
| Mở rộng độc lập từng năng lực | Thấp | Trung bình | Cao |
| Ranh giới giữa các phần | Tùy kỷ luật | Cao nếu được cưỡng chế | Cao, cưỡng chế bởi ranh giới tiến trình |
| Phù hợp với nhóm phát triển nhỏ | Cao | Cao | Thấp |
| Định hướng được chọn | | **Được chọn** | |

*Nguồn: tác giả tổng hợp từ \cite{bass_software_2021,newman_building_2021}.*

Bảng trên giữ năm tiêu chí. Bản đầy đủ, bổ sung độ phức tạp triển khai cùng chi phí vận hành và quan trắc, được trình bày tại **Phụ lục F.10, Bảng F-16**.

**Định hướng được chọn và lý do.** Kiểu nguyên khối có mô-đun phù hợp với **phân hệ và bối cảnh triển khai hiện tại**, vì hai lý do gắn trực tiếp với các lập luận trước đó. Thứ nhất, phần lớn giá trị của thiết kế nằm ở các **bất biến xuyên nhiều thực thể** — toàn vẹn xuyên phạm vi (mục 2.2.6), ngữ cảnh tenant theo giao dịch (mục 2.4.7), ghi dữ liệu nghiệp vụ cùng bản ghi công việc trong một giao dịch (mục 2.7.4) — và cả ba được duy trì một cách tự nhiên bên trong một ranh giới giao dịch quan hệ dùng chung. Thứ hai, quy mô nhóm phát triển và quy mô triển khai chưa tạo ra áp lực mà một kiến trúc phân tán được thiết kế để giải quyết.

Lập luận này nói về **mức phù hợp trong bối cảnh hiện tại**, không về khả năng nguyên tắc: kiến trúc vi dịch vụ vẫn duy trì được các bất biến trên bằng những mẫu phối hợp phân tán, với chi phí phối hợp và vận hành cao hơn. Một phân rã theo hướng dịch vụ vẫn khả thi về sau cho các thành phần mà yêu cầu nhất quán và đặc tính mở rộng biện minh được cho chi phí bổ sung.

**Đánh đổi.** Việc mở rộng riêng một năng lực khó hơn, và ranh giới mô-đun không được cưỡng chế bởi hạ tầng nên phải được duy trì bằng kỷ luật thiết kế và rà soát.

Số tiến trình không xác định kiểu kiến trúc. Một ứng dụng web, một worker nền, một broker và một cơ sở dữ liệu là bốn tiến trình phục vụ **một** ứng dụng có mô-đun, không phải bốn dịch vụ nghiệp vụ độc lập với hợp đồng riêng và vòng đời triển khai riêng. Cách mô tả chính xác cho kiến trúc dạng này là *ứng dụng web có mô-đun kèm hạ tầng xử lý nền*, và cách gọi này được giữ nhất quán ở Chương 3.

### 2.10.2. Đóng gói và triển khai

Câu hỏi đóng gói độc lập với câu hỏi kiểu kiến trúc: một ứng dụng nguyên khối có mô-đun vẫn có thể được đóng gói theo nhiều cách.

**Bảng 2-39. Ba cách đóng gói đơn vị triển khai**

| Tiêu chí | Tiến trình trực tiếp trên máy chủ | Máy ảo | Container |
|---|---|---|---|
| Mức cô lập giữa các đơn vị | Thấp | Cao | Trung bình |
| Thời gian khởi động | Nhanh | Chậm hơn | Nhanh |
| Đóng gói phụ thuộc | Thấp | Cao | Cao |
| Chi phí tài nguyên | Thấp | Cao | Thấp |
| Tính nhất quán giữa các môi trường | Thấp | Cao | Cao |

*Nguồn: tác giả tổng hợp từ \cite{merkel_docker_2014}.*

Container đóng gói ứng dụng và các phụ thuộc vào đơn vị triển khai tương đối nhất quán giữa các môi trường \cite{merkel_docker_2014}; đây là lý do chính để chọn container, chứ không phải mức cô lập. Điểm này quan trọng vì nó dẫn tới một nhầm lẫn phổ biến cần loại bỏ: **container là ranh giới triển khai tiến trình, không phải ranh giới tenant**. Việc chạy các thành phần trong các container khác nhau không tự tạo ra cô lập dữ liệu giữa các tổ chức; cô lập tenant vẫn phải được thực hiện ở năm tầng đã nêu tại Bảng 2-16.

The Twelve-Factor App đề xuất tách cấu hình triển khai khỏi mã nguồn và xem database/broker như dịch vụ hậu thuẫn \cite{wiggins_twelve-factor_2017}. Từ đó phát sinh một phân biệt có hệ quả kiến trúc trực tiếp:

\[
\text{Cấu hình triển khai} \neq \text{Cấu hình tenant}.
\]

**Bảng 2-40. Phân biệt cấu hình triển khai và cấu hình tenant**

| Tiêu chí | Cấu hình triển khai | Cấu hình tenant |
|---|---|---|
| Nội dung điển hình | địa chỉ CSDL, broker, secret, endpoint dịch vụ | lựa chọn danh mục, hạn mức, thiết lập chức năng |
| Thay đổi theo | môi trường chạy | từng tenant |
| Nơi lưu phù hợp | biến môi trường / cấu hình triển khai | dữ liệu có phạm vi trong CSDL |
| Ai thay đổi | người vận hành hệ thống | quản trị viên của tenant, trong quyền được cấp |
| Chịu cơ chế cô lập tenant | Không áp dụng | **Có** — như mọi tài nguyên tenant khác |
| Hệ quả nếu đặt sai chỗ | — | mỗi tenant cần một bản triển khai riêng, mất mục tiêu chia sẻ hạ tầng |

*Nguồn: tác giả tổng hợp từ \cite{wiggins_twelve-factor_2017,merkel_docker_2014}.*

Dòng cuối là lý do phân biệt này không phải chuyện hình thức: nếu cấu hình tenant được đặt trong biến môi trường, kiến trúc trượt ngược về mức 1 của Bảng 2-11 mà không ai chủ động quyết định điều đó.

### 2.10.3. Di trú hệ thống đang vận hành

Với hệ thống đã có dữ liệu và người dùng, thay đổi kiến trúc theo kiểu thay thế toàn bộ trong một lần làm tăng phạm vi rủi ro. *Strangler Fig Application* mô tả cách hiện đại hóa từng bước: chức năng mới được xây bên cạnh đường cũ, lưu lượng hoặc nghiệp vụ được chuyển dần, và thành phần cũ chỉ được bỏ khi đã được thay thế và kiểm chứng \cite{fowler_strangler_2004}.

Nguyên lý này phù hợp với các thay đổi nền tảng như chuyển từ mô hình đơn tenant sang multi-tenant, thêm cơ chế phân quyền mới hoặc thay đổi cơ chế lưu trữ. Một cơ chế nhạy cảm có thể chạy ở chế độ song song (*shadow mode*): đường cũ vẫn quyết định, đường mới tính kết quả để đối chiếu và ghi log. Chỉ khi sai khác đã được giải thích và kiểm thử đạt yêu cầu mới chuyển quyền quyết định sang cơ chế mới.

Chế độ song song có một tính chất đáng nêu: nó biến việc chuyển đổi thành một quá trình **có bằng chứng**. Sai khác giữa hai đường không phải phiền toái cần bỏ qua mà là dữ liệu về mức độ tương đương của chúng, và số lượng sai khác chưa giải thích được là một tiêu chí khách quan để quyết định thời điểm chuyển.

Cách tiếp cận tăng dần không loại bỏ nhu cầu di trú dữ liệu, rollback và kiểm thử; nó chỉ giới hạn phạm vi thay đổi tại từng bước. Chương 3 trình bày cách nguyên tắc này được áp dụng, và Phụ lục E ghi lại các quyết định kiến trúc đã bị thay thế cùng bằng chứng dẫn tới việc thay thế.

## 2.11. Tổng hợp và khoảng trống nghiên cứu

### 2.11.1. Hai vòng đời và các cổng nối giữa chúng

Các cơ sở lý thuyết trong chương có thể được nhìn qua hai vòng đời liên kết: **vòng đời dữ liệu** và **vòng đời quản trị**. Vòng đời dữ liệu mô tả quá trình từ quan sát nguồn, mẫu hợp lệ, phiên bản bộ dữ liệu đến phân phối. Vòng đời quản trị mô tả các điều kiện cần thiết để từng chuyển tiếp được phép xảy ra.

**Bảng 2-41. Các cổng nối vòng đời dữ liệu và vòng đời quản trị**

| Chuyển tiếp trong vòng đời dữ liệu | Điều kiện quản trị cần kiểm tra |
|---|---|
| Bản ghi nguồn → mẫu hợp lệ | chủ thể/nguồn gốc được xác định; ràng buộc cấu trúc và quản trị đạt tại thời điểm thu; cơ sở xử lý và quyền đóng góp phù hợp |
| Mẫu hợp lệ → mẫu đủ điều kiện đưa vào bộ dữ liệu | kết luận về chất lượng ngữ nghĩa — bằng đánh giá của người có thẩm quyền, bằng tiêu chí tự động, hoặc do bên xây dựng bộ dữ liệu quyết định ở hạ nguồn (xem 2.1.5) |
| Mẫu đủ điều kiện → phiên bản bộ dữ liệu đã công bố | phiên bản bất biến, bản kê/hash/chữ ký khi được yêu cầu; đồng thuận còn hiệu lực |
| Phiên bản bộ dữ liệu → phân phối | điều kiện cấp phép/tái sử dụng đã được xác lập |
| Phân phối → bên nhận bên ngoài | điều kiện truy cập hoặc thỏa thuận sử dụng tương ứng được chấp nhận |

*Nguồn: tác giả tổng hợp. Chuyển tiếp thứ hai phản ánh sự phân biệt ở mục 2.1.5 giữa hợp lệ về lược đồ, đúng về ngữ nghĩa và đủ điều kiện vào một bộ dữ liệu.*

**Chuỗi này là một vòng đời trung tính, không phải một quy trình đã chọn.** Diễn đạt ở mức khái quát nhất:

\[
\text{Thu nhận} \rightarrow \text{Kiểm tra} \rightarrow \text{Quản lý} \rightarrow \text{Tham chiếu có kiểm soát / sử dụng ở hạ nguồn},
\]

trong đó **phát hành và chia sẻ ra ngoài là một nhánh tuỳ trường hợp**, không phải bước bắt buộc của mọi mẫu. Cần tránh cách đọc chuỗi thành một dây chuyền cố định kiểu *thu → duyệt → phiên bản → công bố*: cách đọc đó gán cho hệ thống hai thứ mà Chương 2 không kết luận — một khâu phê duyệt bắt buộc do người thực hiện (xem 2.1.5), và một giả định rằng mọi dữ liệu cuối cùng đều được công bố. Nhiều mẫu sẽ dừng lại ở bước quản lý và chỉ được tham chiếu nội bộ, và đó là một trạng thái hợp lệ chứ không phải một vòng đời dở dang.

> ### ▣ HÌNH 2-10 — Vòng đời dữ liệu và vòng đời quản trị với các cổng kiểm soát
> **Loại:** sơ đồ hai làn song song có cổng · **Công cụ đề nghị:** draw.io
> **Phải thể hiện:** làn trên là vòng đời dữ liệu (bản ghi nguồn → mẫu hợp lệ → mẫu đủ điều kiện → phiên bản đã công bố → phân phối → bên nhận bên ngoài); làn dưới là vòng đời quản trị với các điều kiện tương ứng; giữa hai làn là **năm cổng** đặt đúng vị trí năm chuyển tiếp của Bảng 2-41, mỗi cổng ghi điều kiện phải đạt; cổng thứ hai ghi rõ "kết luận về chất lượng ngữ nghĩa — ba cách trả lời, xem 2.1.5" và **không** khẳng định cách nào đã được chọn; cổng cuối vẽ khác biệt kèm chú "vượt quá phạm vi cưỡng chế kỹ thuật — xem Bảng 2-37 mức 4".
> **Chú thích dưới hình:** *Hình 2-10: Vòng đời dữ liệu và vòng đời quản trị với các cổng kiểm soát.*

Từ hai vòng đời này có thể tổng hợp bốn quan hệ chính. Thứ nhất, nhiều tổ chức dùng chung hạ tầng làm phát sinh yêu cầu cô lập ở cả cơ sở dữ liệu, lược đồ và đường truy cập nội dung ngoài cơ sở dữ liệu. Thứ hai, cô lập dữ liệu và phân quyền nghiệp vụ trả lời hai câu hỏi khác nhau, và cả hai đều không trả lời câu hỏi thứ ba — điều gì đã thực sự xảy ra. Thứ ba, dữ liệu chỉ có khả năng tái sử dụng đáng tin cậy khi đi kèm siêu dữ liệu, nguồn gốc và phiên bản bất biến. Thứ tư, khi nền tảng trực tiếp tạo dữ liệu từ người tham gia, quản trị chủ thể, cơ sở xử lý và bằng chứng chấp thuận phải xuất hiện ngay trong đường thu.

### 2.11.2. Đối chiếu với các hệ thống liên quan theo tiêu chí đã xây dựng

Mục 2.1.8 đã giới thiệu các lớp công cụ liên quan ở mức đủ để định vị. Sau khi các mục 2.2–2.10 đã xây dựng đầy đủ tiêu chí, có thể đối chiếu chi tiết hơn. Bảng dưới đây **không dùng ký hiệu có/không**, vì phần lớn các ô không phải câu hỏi nhị phân mà là câu hỏi về trọng tâm thiết kế. Mục đích của bảng **không phải** để cho thấy một hệ thống vượt trội, mà để cho thấy **mỗi hệ thống tối ưu cho một giai đoạn khác nhau của vòng đời dữ liệu**.

**Bảng 2-42. Đối chiếu các hệ thống liên quan theo tiêu chí của chương**

| Tiêu chí | ELAN | REDCap | Dataverse, Zenodo | WLASL, AUTSL | QIPEDC | **Định hướng của phân hệ** |
|---|---|---|---|---|---|---|
| Giai đoạn chính trong vòng đời | Chú giải | Thu thập theo biểu mẫu | Nộp lưu và công bố | Sản phẩm dữ liệu đã hình thành | Tài nguyên từ vựng tham chiếu | Thu nhận, quản trị, và tham chiếu có kiểm soát |
| **Thu trực tiếp có hướng dẫn** | Không phải trọng tâm | Biểu mẫu có hướng dẫn, không phải thu thị giác | Không | Không áp dụng | Không phải nền tảng thu | Đặt làm trọng tâm: dẫn theo lớp và người ký |
| **Nạp dữ liệu đã tồn tại** | Làm việc trên dữ liệu đã có | Có thể đính kèm | Là phương thức chính | Không áp dụng | Không áp dụng | Đường vào riêng, yêu cầu siêu dữ liệu khai báo (2.6.1) |
| **Theo dõi độ bao phủ theo lớp × người ký × vùng** | Không phải trọng tâm | Theo dõi được ở mức bản ghi | Không phải trọng tâm | Là thuộc tính của bản phát hành | Là danh mục, không phải dữ liệu mẫu | Yêu cầu siêu dữ liệu bắt buộc để độ bao phủ đo được |
| Mô hình miền chuyên biệt cho ngôn ngữ ký hiệu | Hỗ trợ chú giải đa phương thức | Không chuyên biệt | Không | Có, ở mức nội dung dữ liệu | Có, ở mức từ vựng | Đặt ở mức lược đồ |
| Danh mục ngôn ngữ – phương ngữ – lớp có phiên bản | Không phải trọng tâm | Không có danh mục miền | Siêu dữ liệu và phiên bản ở mức đối tượng nộp lưu | Không phải cơ chế của bộ dữ liệu | Có ngữ cảnh vùng, không có cơ chế phiên bản cho tenant | Thành phần cốt lõi của thiết kế |
| Mô hình người ký và phiên thu | Có thể chú giải | Có thể cấu hình theo nghiên cứu | Do người nộp khai báo | Có siêu dữ liệu tương ứng | Không áp dụng | Thực thể bậc nhất, ghi nhận tại thời điểm thu có kiểm soát (2.1.1) |
| Phạm vi nhiều tổ chức | Không phải trọng tâm | Dự án và nghiên cứu đa điểm | Phạm vi của kho | Không áp dụng | Không áp dụng | Phân cấp tổ chức – không gian làm việc – dự án |
| Đồng thuận gắn với chủ thể tại thời điểm thu | Quy trình ngoài công cụ | Có thể cấu hình | Không thuộc giai đoạn thu | Không thuộc phạm vi công cụ | Không áp dụng | Mối quan tâm của đường thu, không phải bước hậu kỳ |

*Nguồn: tác giả tổng hợp trong phạm vi các lớp công cụ được khảo sát, dựa trên \cite{wittenburg_elan_2006,harris_research_2009,harris_redcap_2019,crosas_dataverse_2011,cern_openaire_zenodo_2013,li_wlasl_baibao_2020,sincan_autsl_2020,bogddt_qipedc_2019}; các ô mô tả trọng tâm thiết kế của từng lớp công cụ, **không phải** đánh giá chất lượng.*

**Cách đọc cột cuối.** Cột này ghi **định hướng thiết kế** rút ra từ các mục 2.1–2.10, không phải bản kiểm kê những gì hệ thống đã xây. Nó trả lời câu hỏi *"phân hệ đặt trọng tâm ở đâu, và vì sao"*, cùng loại câu hỏi mà năm cột trước trả lời cho năm lớp công cụ kia. Câu hỏi *"cơ chế đó nằm ở bảng nào, đường nào, đã được đo ra sao"* thuộc Chương 3 và Chương 4; áp dụng quy tắc \(\text{Được chọn} \neq \text{Đã hiện thực} \neq \text{Đã kiểm chứng}\) ở mục 2.11.4.

Phân biệt này không làm yếu bảng. Năm cột đầu cũng mô tả trọng tâm thiết kế chứ không liệt kê năng lực đã kiểm chứng của từng công cụ, nên đọc cột cuối theo cùng một thước là cách đọc **nhất quán**, không phải cách đọc dè dặt.

Bảng trên giữ chín tiêu chí. Bản đầy đủ, bổ sung cô lập ở tầng cơ sở dữ liệu, phiên bản của bộ dữ liệu, xử lý bất đồng bộ nội dung phương tiện và quan hệ với bên tiêu thụ ở hạ nguồn, được trình bày tại **Phụ lục F.11, Bảng F-17**.

Đọc theo cột, bảng cho thấy một quy luật: mỗi hệ thống mạnh ở đúng giai đoạn mà nó được thiết kế cho. ELAN mạnh ở chú giải. REDCap mạnh ở thu thập có cấu trúc theo biểu mẫu và quản trị dự án nghiên cứu. Dataverse và Zenodo mạnh ở lưu giữ, mô tả và phân phối đối tượng nghiên cứu đã hình thành. WLASL và AUTSL là sản phẩm dữ liệu, không phải hạ tầng. Đọc theo hàng, bảng cho thấy các hàng về **danh mục có phiên bản**, **cô lập nhiều tổ chức** và **đồng thuận tại thời điểm thu** là những hàng mà không lớp công cụ nào đặt làm trọng tâm đồng thời.

### 2.11.3. Khoảng trống nghiên cứu là khoảng trống về tích hợp

Các tài liệu về multi-tenancy và RBAC cung cấp cơ sở cho ranh giới tổ chức và kiểm soát truy cập \cite{bezemer_multi-tenant_2010,chong_architecture_2006,aulbach_multi-tenant_2008,krebs_architectural_2012,ferraiolo_proposed_2001,sandhu_role-based_1996}. Lý thuyết mô hình hóa dữ liệu quan hệ cung cấp cơ sở cho lược đồ và ràng buộc \cite{codd_relational_1970,chen_entity-relationship_1976,elmasri_fundamentals_2015}. FAIR, Datasheets và data commons cung cấp cơ sở cho khả năng tái sử dụng và quản trị \cite{wilkinson_fair_2016,gebru_datasheets_2021,grossman_case_2016,hess_understanding_2007}.

Vì vậy khoảng trống mà luận văn hướng tới **không phải là sự thiếu vắng của một cơ chế**. Row-Level Security, RBAC theo phạm vi, hàng đợi tác vụ, hàm băm, chữ ký số, quản lý phiên bản và trích xuất điểm mốc đều đã tồn tại và đều có cơ sở kỹ thuật vững. Phát biểu chính xác hơn về khoảng trống là:

> **Trong phạm vi các lớp công cụ được khảo sát**, chưa có một cấu trúc tích hợp phù hợp với vòng đời dữ liệu ngôn ngữ ký hiệu nhiều tổ chức, trong đó siêu dữ liệu người ký, ranh giới tổ chức, danh mục có phiên bản và điều kiện sử dụng được **duy trì liên tục** từ thời điểm thu tới phiên bản dữ liệu được tái sử dụng.

Cách phát biểu này chặt hơn "chưa có nền tảng nào làm được", và nó cũng xác định đúng bản chất của đóng góp: giá trị không nằm ở việc phát minh từng cơ chế, mà ở việc tổ chức chúng thành một chuỗi liên tục trong đó **không có mắt xích nào bị đứt**. Một hệ thống có RLS nhưng không có quan hệ người ký sẽ mất khả năng thực hiện quyền của chủ thể. Một hệ thống có phiên bản bộ dữ liệu nhưng không ghim phiên bản danh mục sẽ mất khả năng tái lập. Một hệ thống có đồng thuận nhưng không có cổng kiểm tra ở khâu công bố sẽ không cưỡng chế được đồng thuận đó. Giá trị nằm ở tính liên tục, và tính liên tục chỉ chứng minh được bằng cơ chế **có thể kiểm thử** thay vì bằng quy ước lập trình.

Có thể tóm tắt ba chuỗi lập luận trung tâm của chương. Trên trục cô lập:

\[
\text{Hạ tầng dùng chung} \Rightarrow \text{Đa thuê bao} \Rightarrow \text{Lược đồ dùng chung} \Rightarrow \text{Cô lập logic trở nên quyết định} \Rightarrow \text{Ràng buộc lược đồ} + \text{Phân quyền} + \text{Cưỡng chế ở CSDL}.
\]

Trên trục dữ liệu:

\[
\text{Biến thể vùng và người ký} \Rightarrow \text{Danh mục có cấu trúc} + \text{Siêu dữ liệu người ký/phiên thu} \Rightarrow \text{Danh mục có phiên bản} \Rightarrow \text{Bộ dữ liệu có phiên bản} + \text{Nguồn gốc}.
\]

Trên trục quản trị:

\[
\text{Dữ liệu gắn với cá nhân} \Rightarrow \text{Ghi nhận chủ thể tại thời điểm thu} \Rightarrow \text{Đồng thuận có phiên bản} \Rightarrow \text{Cổng kiểm tra khi công bố} + \text{Nhật ký kiểm toán}.
\]

Trong cả ba chuỗi, mỗi bước là hệ quả của bước trước chứ không phải một lựa chọn công nghệ độc lập.

### 2.11.4. Tổng hợp các quyết định kiến trúc

Bảng dưới đây tập hợp toàn bộ các quyết định đã được lập luận trong chương. Nó là điểm nối giữa Chương 2 và Chương 3: mỗi dòng nêu **định hướng và lý do**, còn cách hiện thực và mức độ hoàn thành thuộc Chương 3 và Chương 4.

**Cách đọc bảng này — quy tắc bắt buộc.** Đây là bảng tổng hợp **quyết định lý thuyết**, không phải bản kiểm kê năng lực đã có. Ba trạng thái sau đây tách rời nhau và không suy ra được nhau:

\[
\text{Được chọn} \neq \text{Đã hiện thực} \neq \text{Đã kiểm chứng}.
\]

Một định hướng được chọn là một lập luận đã hoàn tất trong Chương 2. Nó chưa nói gì về việc hệ thống đã xây phần đó hay chưa, và càng chưa nói gì về việc phần đã xây có được đo bằng một phép đo có khả năng thất bại hay không. Vì bảng này nằm ở điểm hội tụ của cả chương, một cách đọc lỏng ở đây sẽ vô hiệu hoá mọi giới hạn đã phát biểu cẩn thận ở các mục trước.

Ba nhóm nhãn được dùng khi đối chiếu sang Chương 3:

| Nhãn | Nghĩa |
|---|---|
| **Định hướng kiến trúc** | lựa chọn được lập luận từ lý thuyết — trạng thái mặc định của mọi dòng trong bảng dưới |
| **Hướng mở rộng** | phù hợp với lập luận nhưng chưa hiện thực |
| **Được áp dụng trong phân hệ** | chỉ dùng khi Chương 3 chứng minh được có đối tượng tương ứng trong hệ thống |

**Bảng 2-43. Tóm tắt các nhóm quyết định kiến trúc và định hướng được chọn**

| Nhóm quyết định | Định hướng được chọn | Mục |
|---|---|---|
| Tổ chức dữ liệu đa thuê bao | Lược đồ dùng chung | 2.2.7 |
| Toàn vẹn quan hệ xuyên tenant | Khoá tổ hợp mang khoá phạm vi | 2.2.6 |
| Cưỡng chế cô lập | Ràng buộc lược đồ + phân quyền ứng dụng + cưỡng chế ở CSDL | 2.4.9 |
| Hành vi khi thiếu ngữ cảnh | Fail-closed | 2.4.6 |
| Mô hình phân quyền | RBAC theo phạm vi, kế thừa khai báo tường minh | 2.5.6, 2.5.7 |
| Ghi nhận hành động | Nhật ký kiểm toán tách khỏi nhật ký vận hành | 2.5.9 |
| Kế thừa danh mục | Sao chép một lần, ghim phiên bản | 2.3.4 |
| Đơn vị và chiến lược thu thập | Theo phiên thu; kết hợp thu có hướng dẫn và đóng góp mở | 2.6.2, 2.6.4 |
| Trách nhiệm về độ bao phủ | Đo được và quản trị được, không bảo đảm cân bằng | 2.6.5 |
| Biểu diễn và vị trí trích xuất | Điểm mốc bàn tay làm biểu diễn dẫn xuất; trích xuất tại máy khách | 2.6.7, 2.6.8 |
| Tổ chức bước xử lý | Ngắn thì đồng bộ, dài hoặc cần thử lại thì bất đồng bộ | 2.7.1 |
| Nhất quán giữa hai kho | Giao dịch cục bộ kèm khôi phục bất đồng bộ | 2.7.4 |
| Lưu nội dung | Ngoài CSDL, siêu dữ liệu trong CSDL | 2.7.5 |
| Phiên bản và nguồn gốc | Ghim phiên bản **danh mục**; bản kê tham chiếu cho phiên bản **bộ dữ liệu**; khung đối tượng – hoạt động – chủ thể | 2.8.2, 2.8.5 |
| Bảo đảm toàn vẹn | Bản kê băm kèm chữ ký số; xác minh fail-closed | 2.8.6, 2.8.7 |
| Mô hình đồng thuận | Có phiên bản, giới hạn theo phạm vi; phân biệt chấp thuận mức tài khoản với đồng thuận của chủ thể dữ liệu | 2.9.2, 2.9.3 |
| Kiểu kiến trúc và tiến hoá | Nguyên khối có mô-đun; thay thế dần có chế độ song song | 2.10.1, 2.10.3 |

*Nguồn: tác giả tổng hợp từ các lập luận trong Chương 2. Mọi dòng ở trạng thái **định hướng kiến trúc**; xem quy tắc đọc ở đầu mục.*

**Bốn dòng cần đặc biệt thận trọng khi đối chiếu sang Chương 3**, vì chúng dễ bị nâng lên nhãn "được áp dụng trong phân hệ" mà không có đối tượng tương ứng chống lưng:

| Dòng | Phần đã có thể áp dụng | Phần thuộc **hướng mở rộng** |
|---|---|---|
| Phiên bản và nguồn gốc | ghim phiên bản **danh mục** — cố định không gian nhãn | phiên bản **bộ dữ liệu** ở mức bản kê bất biến — cố định tập mẫu (xem 2.8.2) |
| Vòng đời tạo tác nghiên cứu | — | đăng ký thực nghiệm và phiên bản mô hình như thực thể có vòng đời |
| Bảo đảm toàn vẹn | ký và xác minh hiện vật có phiên bản | thẩm quyền ký gắn theo **từng tổ chức** thay vì theo cấu hình triển khai |
| Phạm vi dùng chung cộng đồng | phạm vi được **đăng ký** và chịu cùng cơ chế kiểm tra | vòng đời đóng góp – công bố – rút lui vận hành đầy đủ trên phạm vi đó (xem 2.3.3) |

Bốn dòng này không phải khiếm khuyết của lập luận: lập luận dẫn tới chúng vẫn đứng vững. Chúng là chỗ mà **khoảng cách giữa lập luận và hiện trạng lớn nhất**, nên là chỗ một câu viết lỏng gây thiệt hại nhiều nhất.

Bảng trên là **bản tóm tắt theo nhóm**, đủ để theo dõi mạch lập luận của chương và để đối chiếu với Chương 3. Danh mục **đầy đủ ba mươi mốt quyết định** — mỗi dòng ghi các phương án đã cân nhắc, định hướng được chọn, lý do chính, đánh đổi phải chấp nhận và mục tương ứng của Chương 2 — được trình bày tại **Phụ lục F.11, Bảng F-18**. Không quyết định nào bị lược bỏ; bảng ở đây chỉ gộp những quyết định cùng một trục thành một dòng.

Các khái niệm và quan hệ được trình bày trong chương này là cơ sở để Chương 3 mô tả kiến trúc, mô hình dữ liệu, cơ chế phân quyền, vòng đời dữ liệu và phương án triển khai cụ thể của hệ thống.
