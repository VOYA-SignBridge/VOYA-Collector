# CHƯƠNG 2. CƠ SỞ LÝ THUYẾT

## 2.1. Miền ứng dụng và vị thế của đề tài

### 2.1.1. Đặc trưng dữ liệu ngôn ngữ ký hiệu và hệ quả đối với siêu dữ liệu

Ngôn ngữ ký hiệu là ngôn ngữ tự nhiên sử dụng phương thức thị giác – cử chỉ. Một ký hiệu không chỉ được xác định bởi hình dạng bàn tay mà còn bởi hướng, vị trí và chuyển động; bên cạnh đó, các thành phần phi thủ công như biểu cảm khuôn mặt, chuyển động đầu và tư thế cơ thể có thể tham gia biểu đạt nghĩa và chức năng ngữ pháp \cite{liddell_grammar_2003,bragg_sign_2019}. Ngôn ngữ ký hiệu cũng tồn tại biến thể theo vùng và cộng đồng sử dụng. Đối với ngôn ngữ ký hiệu Việt Nam, khác biệt vùng miền cần được ghi nhận như một thuộc tính của dữ liệu thay vì bị xem mặc nhiên là nhiễu cần loại bỏ \cite{woodward_sign_2000}.

Các đặc trưng trên dẫn đến ba yêu cầu trực tiếp đối với nền tảng quản lý dữ liệu. Thứ nhất, biểu diễn dùng cho xử lý tự động chỉ là một phép trích chọn từ tín hiệu quan sát ban đầu; nếu phép biến đổi làm mất thông tin thì hệ thống cần có khả năng truy lại bản ghi nguồn khi mục đích nghiên cứu thay đổi. Thứ hai, ngôn ngữ, phương ngữ và lớp ký hiệu phải được mô hình hóa thành các khái niệm tách biệt thay vì ghép thành một nhãn chuỗi duy nhất. Thứ ba, dữ liệu phải liên kết được với người thực hiện ký hiệu và bối cảnh thu nhận tương ứng.

**Bảng 2.1. Từ đặc trưng miền ứng dụng đến yêu cầu đối với nền tảng**

| Đặc trưng dữ liệu | Yêu cầu đối với nền tảng |
|---|---|
| Nhiều kênh biểu đạt đồng thời | Bảo toàn khả năng truy lại bản ghi nguồn khi biểu diễn dẫn xuất là phép biến đổi có mất mát |
| Biến thể theo vùng và cộng đồng | Tách ngôn ngữ, phương ngữ và lớp ký hiệu trong lược đồ; cho phép quản lý phiên bản danh mục |
| Dữ liệu gắn với người thực hiện | Ghi nhận người ký, phiên thu và thông tin quy kết cần thiết cho nghiên cứu và quản trị dữ liệu |

Thông tin người ký có ý nghĩa trực tiếp đối với thiết kế giao thức đánh giá. AUTSL, chẳng hạn, sử dụng các nhóm người ký tách biệt giữa các tập dữ liệu để đánh giá khả năng tổng quát hóa sang người ký chưa xuất hiện trong quá trình huấn luyện \cite{sincan_autsl_2020}. WLASL cũng cung cấp thông tin về nhiều người ký và các mẫu tương ứng, qua đó cho phép phân tích dữ liệu theo chủ thể \cite{li_wlasl_baibao_2020}. Vì vậy, danh tính hoặc định danh nghiên cứu của người ký là siêu dữ liệu cần thiết để xây dựng các phép chia dữ liệu phù hợp; không nên suy diễn rằng mọi bộ dữ liệu tham chiếu đều sử dụng cùng một giao thức độc lập người ký.

Mặt khác, khi dữ liệu gắn với một cá nhân có thể xác định, quan hệ giữa mẫu và chủ thể còn là điều kiện để thực hiện các nghĩa vụ quản trị ở mục 2.9. Do đó, cùng một thuộc tính — người ký — đồng thời phục vụ hai mục tiêu khác nhau: kiểm soát chất lượng nghiên cứu và thực hiện quyền của chủ thể dữ liệu.

### 2.1.2. Bộ dữ liệu dùng lại được như một đối tượng có vòng đời

Giá trị của một bộ dữ liệu nghiên cứu không chỉ phụ thuộc vào số lượng mẫu. FAIR đề xuất bốn thuộc tính định hướng cho dữ liệu khoa học: có thể tìm thấy, có thể truy cập, có khả năng tương tác và có khả năng tái sử dụng \cite{wilkinson_fair_2016}. Bổ sung cho hướng tiếp cận này, *Datasheets for Datasets* nhấn mạnh việc tài liệu hóa động cơ xây dựng, thành phần, quá trình thu thập, cách sử dụng dự kiến và các giới hạn của bộ dữ liệu \cite{gebru_datasheets_2021}. Hai hướng tiếp cận đều cho thấy siêu dữ liệu và nguồn gốc dữ liệu không phải phần phụ thêm sau khi thu thập, mà là thành phần cần thiết để dữ liệu có thể được diễn giải và tái sử dụng.

Trong phạm vi luận văn, một bộ dữ liệu vì vậy được xem là một đối tượng có vòng đời, bao gồm tối thiểu dữ liệu quan sát, danh mục ký hiệu, thông tin ngôn ngữ và phương ngữ, người ký và phiên thu, nguồn gốc dữ liệu, trạng thái kiểm duyệt, phiên bản và cơ sở sử dụng. Cách nhìn này khác với cách tổ chức dữ liệu như một thư mục tệp: thư mục có thể cho biết tệp nằm ở đâu nhưng không tự biểu diễn được ai tạo dữ liệu, dữ liệu thuộc phạm vi quản trị nào, phiên bản nào đã được công bố, hoặc điều kiện nào cho phép dữ liệu được phân phối.

Vòng đời cũng làm phát sinh sự khác biệt giữa dữ liệu đang làm việc và dữ liệu đã công bố. Trạng thái đang làm việc có thể tiếp tục thay đổi khi thêm mẫu, hiệu chỉnh siêu dữ liệu hoặc rà soát chất lượng; ngược lại, một phiên bản đã được dùng làm tham chiếu nghiên cứu cần có khả năng truy lại đúng nội dung tại thời điểm công bố. Yêu cầu này là cơ sở cho cơ chế phiên bản bất biến và truy xuất nguồn gốc ở mục 2.8.

### 2.1.3. Vị thế của đề tài trong các lớp công cụ liên quan

Các công trình liên quan phục vụ những giai đoạn khác nhau của vòng đời dữ liệu và được xây dựng cho những phạm vi quản trị khác nhau. Việc phân loại theo hai trục này giúp định vị CTU-SignBridge mà không cần giả định rằng mọi công cụ đều giải quyết cùng một bài toán.

**Bộ dữ liệu** là kết quả của một quá trình thu thập. WLASL và AUTSL là các bộ dữ liệu tham chiếu cho nhận dạng ngôn ngữ ký hiệu \cite{li_wlasl_baibao_2020,sincan_autsl_2020}. Trong chương này, chúng chủ yếu được dùng để minh họa rằng dữ liệu dùng lại được cần có siêu dữ liệu về lớp ký hiệu, mẫu và người ký; chúng không phải đối tượng mà CTU-SignBridge cạnh tranh trực tiếp.

**Từ điển chuẩn hóa** là tài nguyên tham chiếu về từ vựng. Từ điển Ngôn ngữ ký hiệu Việt Nam của dự án QIPEDC cung cấp một nguồn tham chiếu cho danh mục từ vựng \cite{bogddt_qipedc_2019}. Vai trò của loại tài nguyên này đối với nền tảng là cung cấp điểm xuất phát cho danh mục; nó không thay thế tập nhiều mẫu được thu từ nhiều người ký và nhiều phiên phục vụ nghiên cứu thực nghiệm.

**Công cụ chú giải** hỗ trợ gán nhãn và mô tả dữ liệu đã tồn tại. ELAN là môi trường chú giải đa phương thức được sử dụng rộng rãi trong nghiên cứu ngôn ngữ \cite{wittenburg_elan_2006}. Loại công cụ này giải quyết tốt thao tác chú giải nhưng không mặc nhiên cung cấp mô hình quản trị nhiều tổ chức, vòng đời đồng thuận hay cơ chế cô lập dữ liệu theo tenant.

**Nền tảng thu thập dữ liệu nghiên cứu** là lớp công cụ gần với đề tài nhất. REDCap là một nền tảng thu thập và quản lý dữ liệu nghiên cứu dựa trên biểu mẫu, hỗ trợ nhiều dự án, nghiên cứu đa điểm, kiểm soát quyền ở cấp dự án và nhật ký kiểm toán \cite{harris_research_2009,harris_redcap_2019}. REDCap cho thấy các chức năng thu thập, phân quyền và kiểm toán có thể được tích hợp trong một nền tảng nghiên cứu dùng chung. Tuy nhiên, mô hình của REDCap chủ yếu xoay quanh biểu mẫu và dự án nghiên cứu tổng quát; nó không đặt tầng danh mục chuyên biệt cho ngôn ngữ, phương ngữ và lớp ký hiệu, cũng không đặt việc thu nhận dữ liệu thị giác và trích xuất đặc trưng tại máy khách làm một phần trung tâm của mô hình miền.

**Kho lưu trữ và công bố dữ liệu nghiên cứu** phục vụ chủ yếu giai đoạn lưu giữ, mô tả và phân phối các đối tượng nghiên cứu đã được hình thành. Dataverse cung cấp cơ chế quản lý bộ dữ liệu, phiên bản, siêu dữ liệu, quyền truy cập và điều kiện sử dụng; Zenodo cung cấp định danh bền vững, phiên bản, giấy phép và các mức truy cập cho đối tượng nghiên cứu \cite{crosas_dataverse_2011,cern_openaire_zenodo_2013}. Điểm khác biệt với nền tảng thu thập không nằm ở việc các kho này thiếu cơ chế quản trị, mà ở **thời điểm và đối tượng được quản trị**: kho tiếp nhận một đối tượng nghiên cứu do người nộp cung cấp, trong khi nền tảng thu thập phải thiết lập quan hệ giữa chủ thể dữ liệu, cơ sở xử lý, phiên thu và mẫu ngay khi dữ liệu được tạo ra. Những thông tin không được ghi nhận tại thời điểm đó có thể không tái tạo đáng tin cậy về sau.

Một dạng tổ chức khác thường xuất hiện ở giai đoạn đầu của các dự án dữ liệu là lưu trữ tệp dùng chung kết hợp với quy ước thư mục. Đây không phải một sản phẩm hay kiến trúc cụ thể, mà là một cách vận hành thủ công. Cách này có thể phù hợp với nhóm nhỏ, nhưng ranh giới tổ chức, siêu dữ liệu, phiên bản và điều kiện sử dụng phụ thuộc vào quy ước của người vận hành thay vì được biểu diễn và kiểm soát bởi lược đồ hệ thống.

**Bảng 2.2. Định vị đề tài theo giai đoạn vòng đời và phạm vi quản trị**

| Loại công cụ | Giai đoạn chính | Tổ chức / phạm vi độc lập | Danh mục chuyên biệt theo miền | Đồng thuận và quy kết tại thời điểm thu |
|---|---|---|---|---|
| Công cụ chú giải (ELAN) | Chú giải | Không phải trọng tâm | Không phải trọng tâm | Không phải chức năng cốt lõi |
| Lưu trữ tệp + thư mục thủ công | Thu thập, lưu trữ | Dựa trên quy ước thủ công | Dựa trên quy ước | Dựa trên quy trình ngoài hệ thống |
| REDCap | Thu thập, quản lý nghiên cứu | Dự án, đa điểm, quyền theo dự án | Biểu mẫu tổng quát | Có thể cấu hình theo nghiên cứu |
| Dataverse, Zenodo | Nộp lưu, lưu giữ, công bố | Collection/community và quyền của kho | Không phải trọng tâm | Không phải chức năng cốt lõi của giai đoạn thu |
| **CTU-SignBridge** | **Thu nhận → quản trị → công bố** | **Tenant → workspace → project** | **Ngôn ngữ → phương ngữ → lớp ký hiệu, có phiên bản** | **Gắn với chủ thể, mẫu và phiên thu trong đường thu** |

*Nguồn: tác giả tổng hợp trong phạm vi các lớp công cụ được khảo sát.*

CTU-SignBridge thuộc lớp nền tảng thu thập và quản trị dữ liệu nghiên cứu. Điểm định vị của đề tài nằm ở giao của ba yêu cầu: **thu nhận theo phương thức chuyên biệt của miền ngôn ngữ ký hiệu**, **quản trị nhiều phạm vi tổ chức trên một hạ tầng dùng chung**, và **quản trị dữ liệu ngay từ thời điểm thu**. Từ vị thế này phát sinh ba hệ quả chi phối các mục còn lại của chương.

Thứ nhất, nghĩa vụ quản trị phát sinh trực tiếp tại đường thu. Nền tảng không thể chỉ dựa vào khai báo bổ sung sau khi dữ liệu đã tồn tại; các thông tin về chủ thể, phiên thu, nguồn gốc và cơ sở sử dụng phải được ghi nhận khi còn có thể xác định đáng tin cậy. Thứ hai, nhiều đơn vị có thể cùng vận hành trên một hạ tầng nhưng cần ranh giới riêng về dữ liệu, thành viên, quyền và cấu hình; đây là cơ sở của các mục 2.2 đến 2.5. Thứ ba, dữ liệu tăng trưởng liên tục theo thời gian thay vì tồn tại như một bản phát hành duy nhất, nên hệ thống phải tách trạng thái đang làm việc khỏi phiên bản đã công bố và duy trì khả năng truy xuất nguồn gốc; đây là trọng tâm của mục 2.8.

Phạm vi của luận văn bao gồm thu nhận dữ liệu qua nền tảng, quản lý danh mục từ vựng và phương ngữ, cô lập và phân quyền theo phạm vi tổ chức, đường ống nhập liệu và xử lý bất đồng bộ, quản trị đồng thuận và quy kết, phiên bản và toàn vẹn của tạo tác nghiên cứu, cùng các nguyên tắc triển khai và di trú hệ thống. Ngoài phạm vi là huấn luyện, tối ưu và đánh giá mô hình nhận dạng, cũng như phát triển một thuật toán trích xuất điểm mốc mới. Thành phần trích xuất được sử dụng như một kỹ thuật thu nhận có sẵn; các mô-đun huấn luyện hoặc nhận dạng được xem là bên tiêu thụ dữ liệu ở hạ nguồn.

## 2.2. Kiến trúc SaaS và tính đa thuê bao

### 2.2.1. SaaS, multi-user, multi-tenancy và các phạm vi tài nguyên

Software as a Service (SaaS) là mô hình cung cấp phần mềm trong đó năng lực ứng dụng được cung cấp qua mạng và người sử dụng không trực tiếp quản lý hạ tầng điện toán nền bên dưới \cite{mell_nist_2011}. Trong quá trình phát triển SaaS, một quyết định kiến trúc quan trọng là mức độ chia sẻ tài nguyên giữa các khách hàng hoặc miền quản trị \cite{chong_architecture_2006}.

Cần phân biệt **multi-user** và **kiến trúc đa thuê bao (multi-tenancy)**. Multi-user là đặc tính cho phép nhiều người dùng cùng sử dụng một ứng dụng. Multi-tenancy là cách tổ chức kiến trúc trong đó nhiều miền quản trị dùng chung một phần hạ tầng hoặc thành phần ứng dụng nhưng vẫn duy trì ranh giới riêng về dữ liệu, quyền và cấu hình \cite{bezemer_multi-tenant_2010,krebs_architectural_2012}. Vì vậy, việc người dùng A không xem được dữ liệu của người dùng B chưa đủ để kết luận một hệ thống là multi-tenant; câu hỏi quan trọng hơn là hệ thống có mô hình hóa và cưỡng chế ranh giới giữa các miền quản trị độc lập hay không.

Trong luận văn này, **tenant** được định nghĩa là phạm vi quản trị logic cao nhất đối với dữ liệu nghiệp vụ, thành viên, quyền truy cập và cấu hình riêng của một đơn vị sử dụng nền tảng. Tenant không nhất thiết đồng nhất với tư cách pháp nhân của một tổ chức; đây trước hết là một ranh giới kỹ thuật và quản trị trong hệ thống.

Bên trong tenant, **không gian làm việc (workspace)** tổ chức một nhóm hoạt động hoặc tài nguyên có liên quan; **dự án (project)** là phạm vi hẹp hơn cho một mục tiêu hoặc hoạt động cụ thể. Quan hệ chứa được biểu diễn:

\[
Tenant \supset Workspace \supset Project.
\]

Cây phạm vi này không tự sinh ra quyền truy cập. Nó chỉ tạo cấu trúc để chính sách phân quyền có thể gắn vai trò và quyền vào đúng cấp, sau đó xác định rõ có hay không cơ chế kế thừa xuống phạm vi con.

### 2.2.2. Các mô hình tổ chức dữ liệu đa thuê bao

Đối với cơ sở dữ liệu quan hệ, ba mô hình thường được thảo luận gồm: cơ sở dữ liệu riêng cho từng tenant; lược đồ riêng cho từng tenant trong cùng hệ quản trị; và lược đồ dùng chung, trong đó dữ liệu của nhiều tenant nằm trong cùng bảng và được phân biệt bằng khóa phạm vi \cite{chong_architecture_2006,aulbach_multi-tenant_2008}.

Mô hình cơ sở dữ liệu riêng tạo ranh giới vật lý rõ hơn nhưng làm tăng số đơn vị cần sao lưu, giám sát và di trú khi số tenant tăng. Mô hình lược đồ riêng chia sẻ máy chủ cơ sở dữ liệu nhưng vẫn duy trì nhiều cấu trúc song song. Mô hình lược đồ dùng chung có chi phí cấu trúc thấp hơn và thuận lợi cho di trú tập trung, nhưng yêu cầu cơ chế cưỡng chế truy cập ở cấp hàng hoặc tương đương vì cột `tenant_id` tự nó chỉ là dữ liệu định danh.

**Bảng 2.3. So sánh ba mô hình tổ chức dữ liệu đa thuê bao**

| Tiêu chí | CSDL riêng | Lược đồ riêng | Lược đồ dùng chung |
|---|---|---|---|
| Ranh giới dữ liệu | Vật lý ở cấp CSDL | Logic/vật lý ở cấp lược đồ | Logic ở cấp hàng |
| Chi phí vận hành theo số tenant | Cao | Trung bình | Thấp hơn |
| Di trú cấu trúc | Lặp theo từng CSDL | Lặp theo từng lược đồ | Tập trung |
| Yêu cầu kiểm soát truy vấn | Thấp hơn | Trung bình | Cao, cần cơ chế cưỡng chế nhất quán |

*Nguồn: tác giả tổng hợp định tính từ \cite{bezemer_multi-tenant_2010,chong_architecture_2006,aulbach_multi-tenant_2008,krebs_architectural_2012}; bảng thể hiện so sánh tương đối, không phải kết quả đo hiệu năng.*

Lựa chọn lược đồ dùng chung không làm giảm yêu cầu cô lập; nó chuyển phần lớn trách nhiệm từ ranh giới vật lý sang ranh giới logic. Do đó, một thiết kế chỉ yêu cầu lập trình viên nhớ thêm `WHERE tenant_id = ...` vào từng truy vấn chưa tạo ra một ranh giới đủ mạnh. Cơ chế bảo vệ cần được đặt ở tầng mà một truy vấn nghiệp vụ thông thường không thể vô tình bỏ qua, dẫn đến vai trò của Row-Level Security ở mục 2.4.

### 2.2.3. Các chiều cô lập và hạn mức tài nguyên

Cô lập trong hệ thống đa thuê bao không chỉ liên quan đến dữ liệu. Krebs và cộng sự phân tích các khía cạnh cô lập liên quan đến dữ liệu, an ninh và hiệu năng trong ứng dụng multi-tenant \cite{krebs_architectural_2012}. Trong phạm vi luận văn, cô lập dữ liệu và cô lập an ninh là trọng tâm được hiện thực và kiểm thử trực tiếp; chiều hiệu năng được phản ánh thông qua hạn mức tài nguyên theo tenant.

Hạn mức cần được nhìn như một cơ chế bảo vệ tài nguyên dùng chung, không chỉ là thành phần của bảng giá. Một tenant có thể vẫn tuân thủ ranh giới dữ liệu nhưng tiêu thụ số lượng mẫu, người dùng, tác vụ hoặc tài nguyên xử lý quá lớn, từ đó làm suy giảm dịch vụ dành cho tenant khác. Vì vậy quota là một lớp giới hạn mức sử dụng trong không gian chia sẻ.

Tuy nhiên, việc có quota không đồng nghĩa đã chứng minh được khả năng cô lập hiệu năng. Đánh giá nhiễu hiệu năng giữa các tenant đòi hỏi thí nghiệm tải riêng; nếu luận văn không thực hiện phép đo này thì chỉ nên khẳng định rằng hệ thống **có cơ chế hạn mức**, không khẳng định đã đạt performance isolation đầy đủ.

### 2.2.4. Tài nguyên ngoài cơ sở dữ liệu và ranh giới bảo vệ

Không phải mọi nội dung của nền tảng đều phù hợp để lưu trực tiếp trong bảng quan hệ. Video, tệp đặc trưng, tệp tài liệu hoặc các đối tượng dung lượng lớn có thể được đặt trong hệ thống tệp hoặc dịch vụ lưu trữ bên ngoài, trong khi cơ sở dữ liệu giữ định danh, đường dẫn hoặc khóa tham chiếu. Khi đó cần tách hai vấn đề: **toàn vẹn của nội dung được tham chiếu** và **quyền được truy cập nội dung đó**.

Với **tham chiếu định địa chỉ theo vị trí**, định danh cho biết đối tượng nằm ở đâu. Nội dung có thể bị thay thế tại cùng vị trí nếu hệ thống lưu trữ cho phép, nên vị trí tự nó không chứng minh nội dung vẫn là bản ban đầu. Với **tham chiếu định địa chỉ theo nội dung (content-addressed reference)**, định danh được suy ra từ giá trị băm mật mã của nội dung. Khi dùng một hàm băm có tính kháng va chạm phù hợp, việc chủ động tìm một nội dung khác có cùng giá trị băm được xem là bất khả thi về mặt tính toán trong điều kiện thực tế \cite{nist_fips180_4_2015}. Bên nhận có thể băm lại nội dung để kiểm tra nó có khớp với định danh đã lưu hay không.

Cơ chế này cung cấp khả năng phát hiện thay đổi nội dung, nhưng **không phải cơ chế kiểm soát truy cập**. RLS bảo vệ hàng dữ liệu trong PostgreSQL và không tự mở rộng sang hệ thống tệp hay kho đối tượng bên ngoài. Tài nguyên ngoài cơ sở dữ liệu cần một đường truy cập riêng sử dụng cùng ngữ cảnh tenant và cùng nguyên tắc mặc định từ chối. Nếu một kho lưu trữ cho phép đọc đối tượng chỉ bằng việc biết URL hoặc định danh, định danh đó có thể hoạt động như một *bearer capability*; ngược lại, nếu kho vẫn yêu cầu xác thực và kiểm tra quyền thì việc biết giá trị băm không tự cấp quyền truy cập. Nguyên lý *complete mediation* yêu cầu mọi truy cập tới đối tượng được kiểm tra tại điểm sử dụng \cite{saltzer_protection_1975}; việc một thành phần có quyền rộng thay mặt người dùng truy cập tài nguyên mà không kiểm lại phạm vi có thể dẫn đến dạng lỗi *confused deputy* \cite{hardy_confused_1988}.

Việc lưu metadata và nội dung trên hai hệ thống khác nhau còn làm phát sinh bài toán ghi kép. Một thao tác tạo mẫu có thể thành công ở kho tệp nhưng thất bại ở cơ sở dữ liệu, hoặc ngược lại. Vì hai bên không cùng tham gia một giao dịch ACID, thiết kế cần xác định thứ tự ghi, trạng thái trung gian an toàn và cơ chế đối soát để phát hiện các đối tượng mồ côi hoặc tham chiếu hỏng \cite{kleppmann_designing_2017}. Tương tự, xóa một hàng không tự xóa tệp; vòng đời xóa phải được định nghĩa cho cả metadata và nội dung.

**Bảng 2.4. Các yêu cầu khi nội dung nằm ngoài cơ sở dữ liệu**

| Yêu cầu | Cơ chế hoặc nguyên tắc |
|---|---|
| Xác định nội dung có bị thay đổi | Giá trị băm / tham chiếu định địa chỉ theo nội dung khi phù hợp |
| Bảo vệ quyền đọc | Điểm kiểm soát truy cập dùng cùng ngữ cảnh tenant; không dựa vào tính bí mật của đường dẫn |
| Xử lý ghi kép | Thứ tự ghi xác định trước, trạng thái trung gian và đối soát định kỳ |
| Quản lý xóa | Quy trình xóa bao phủ cả hàng dữ liệu và đối tượng lưu trữ |

**Hình 2.1. Hai cách tham chiếu nội dung và phạm vi bảo đảm của từng cách.**  
*Nguồn: tác giả xây dựng dựa trên \cite{saltzer_protection_1975,kleppmann_designing_2017,nist_fips180_4_2015}.*

## 2.3. Phạm vi quản trị dữ liệu

Mục 2.2 xác định ranh giới giữa các tenant. Bên trong và bên ngoài các ranh giới đó, nền tảng còn chứa những loại dữ liệu có mục đích và chủ thể quản trị khác nhau. Việc phân biệt các phạm vi này là vấn đề quản trị kỹ thuật; nó không nhằm đưa ra kết luận pháp lý về quyền sở hữu tài sản hay quyền tác giả.

### 2.3.1. Ba phạm vi quản trị dữ liệu

Trong phạm vi CTU-SignBridge có thể phân biệt ba nhóm dữ liệu: **danh mục và cấu hình hệ thống**, **dữ liệu dùng chung cộng đồng**, và **dữ liệu theo tenant**.

**Bảng 2.5. Ba phạm vi quản trị dữ liệu**

| Phạm vi | Nội dung điển hình | Chủ thể quản trị chính |
|---|---|---|
| Danh mục/cấu hình hệ thống | cấu hình nền tảng, danh mục chuẩn dùng làm điểm xuất phát | nhà vận hành nền tảng |
| Dữ liệu dùng chung cộng đồng | dữ liệu được đóng góp để chia sẻ theo điều kiện đã xác lập | cơ chế quản trị cộng đồng/nền tảng trong phạm vi quyền được cấp |
| Dữ liệu theo tenant | dữ liệu nghiệp vụ được tạo và quản lý trong một tenant | tenant tương ứng theo quyền và nghĩa vụ đã xác lập |

*Nguồn: tác giả tổng hợp.*

Sự phân biệt quan trọng nhất là giữa danh mục hệ thống và dữ liệu dùng chung cộng đồng. Danh mục hệ thống là cấu hình kỹ thuật: nó xác định những ngôn ngữ, phương ngữ, lớp hoặc hồ sơ nào có thể được dùng làm điểm xuất phát. Dữ liệu dùng chung cộng đồng lại bao gồm mẫu nghiên cứu cùng thông tin quy kết, cơ sở sử dụng và các điều kiện quản trị. Việc gọi cả hai bằng một tên “community” dễ làm nhòe ranh giới giữa quyền vận hành nền tảng và quyền được khai thác dữ liệu.

Nguyên tắc cần giữ là: **quyền quản trị hạ tầng không tự tạo ra quyền khai thác dữ liệu**. Một tài khoản có quyền vận hành máy chủ hoặc quản trị cấu hình không vì thế mặc nhiên được phép công bố hoặc tái sử dụng mọi dữ liệu có trên hệ thống. Quyền truy cập kỹ thuật, cơ sở xử lý dữ liệu cá nhân, quyền đóng góp và giấy phép tái sử dụng là các lớp khác nhau; chúng được phân tách rõ hơn ở mục 2.9.

### 2.3.2. Dữ liệu dùng chung cộng đồng như một data commons

Data commons có thể được hiểu là một môi trường kết hợp dữ liệu với hạ tầng, dịch vụ và cơ chế quản trị nhằm phục vụ một cộng đồng sử dụng \cite{grossman_case_2016}. Điểm quan trọng của khái niệm này không chỉ nằm ở việc đặt nhiều tệp vào cùng một kho, mà ở việc xác lập các quy tắc về đóng góp, truy cập, sử dụng, trách nhiệm và duy trì tài nguyên.

Các nghiên cứu về knowledge commons nhấn mạnh vai trò của quy tắc và thiết chế quản trị đối với tài nguyên tri thức dùng chung \cite{hess_understanding_2007}. Đối với dữ liệu ngôn ngữ ký hiệu, yêu cầu tham gia của cộng đồng liên quan còn có cơ sở từ các nghiên cứu nhấn mạnh sự cần thiết của góc nhìn liên ngành và sự tham gia của cộng đồng người Điếc trong công nghệ ngôn ngữ ký hiệu \cite{bragg_sign_2019}.

Từ góc độ lược đồ, một commons có quản trị cần có khả năng trả lời tối thiểu: mẫu này bắt nguồn từ đâu; ai là chủ thể liên quan; mẫu được đóng góp trong bối cảnh nào; phiên bản và trạng thái nào đang được dùng; điều kiện nào cho phép truy cập hoặc phân phối. Nếu những thông tin này chỉ tồn tại trong tài liệu ngoài hệ thống, khả năng cưỡng chế và kiểm toán sẽ yếu hơn so với khi chúng được biểu diễn bằng các quan hệ có thể truy vấn.

Cách hiện thực dữ liệu dùng chung cộng đồng trong CTU-SignBridge — chẳng hạn ánh xạ nó vào loại tenant nào, luồng phê duyệt nào và policy nào — là quyết định thiết kế của Chương 3, không phải tính chất phổ quát của data commons.

### 2.3.3. Kế thừa tường minh và ghim phiên bản danh mục

Một tenant mới thường cần bắt đầu từ danh mục chuẩn của nền tảng. Có hai cách tổ chức phổ biến về mặt khái niệm. Cách thứ nhất là tra cứu động: tenant chỉ lưu phần khác biệt và khi thiếu một mục thì quay về danh mục hệ thống hiện tại. Cách này tiết kiệm bản sao nhưng làm kết quả phân giải phụ thuộc vào trạng thái của danh mục hệ thống tại thời điểm truy vấn; nếu danh mục gốc thay đổi, tenant có thể nhận kết quả khác dù dữ liệu riêng không thay đổi.

Cách thứ hai là **sao chép một lần và ghi nhận nguồn phiên bản**. Tenant nhận một ảnh chụp danh mục tại phiên bản xác định, sau đó quản lý bản sao theo phạm vi của mình. Khi một bộ dữ liệu được công bố, nó ghim vào một phiên bản danh mục cụ thể. Cách này tốn thêm lưu trữ nhưng tạo ba lợi ích: kết quả phân giải ổn định theo phiên bản; tenant có thể mở rộng danh mục riêng mà không sửa danh mục gốc; và một phiên bản bộ dữ liệu có thể truy lại đúng không gian nhãn đã dùng.

Cơ chế ghim chỉ có ý nghĩa khi phiên bản được ghim là bất biến. Nếu cùng một số phiên bản có thể trỏ tới nội dung khác sau một lần cập nhật, tham chiếu phiên bản không còn bảo đảm khả năng tái lập. Vì vậy, quan hệ giữa danh mục và bộ dữ liệu phụ thuộc trực tiếp vào cơ chế phiên bản ở mục 2.8.

### 2.3.4. Danh mục, bộ dữ liệu và tạo tác nghiên cứu

Ba khái niệm cần được phân biệt:

- **Danh mục (catalog/registry)** xác định không gian nhãn và các quan hệ miền, chẳng hạn ngôn ngữ, phương ngữ, lớp ký hiệu và hồ sơ nhận dạng.
- **Bộ dữ liệu (dataset)** xác định tập mẫu cùng siêu dữ liệu và phiên bản danh mục được sử dụng.
- **Tạo tác nghiên cứu (research artifact)**, trong phạm vi luận văn, là sản phẩm đã được công bố ở một phiên bản có thể kiểm chứng, chẳng hạn gói bộ dữ liệu, bản kê, tệp đặc trưng hoặc kết quả dẫn xuất cần được tham chiếu ổn định.

Theo định nghĩa nội bộ này, một phiên bản bộ dữ liệu đã công bố là một trường hợp của tạo tác nghiên cứu. “Artifact” không được dùng như một khái niệm bao trùm cho mọi đối tượng tạm thời trong hệ thống; chỉ những sản phẩm cần vòng đời công bố, phiên bản và kiểm chứng mới thuộc phạm vi này.

## 2.4. Cưỡng chế cô lập ở tầng cơ sở dữ liệu

### 2.4.1. Row-Level Security và mặc định từ chối

Row-Level Security (RLS) là cơ chế kiểm soát truy cập ở cấp hàng của PostgreSQL. Khi RLS được bật, policy có thể giới hạn những hàng mà một vai được phép nhìn thấy hoặc tác động; nếu không có policy cho phép phù hợp, PostgreSQL áp dụng hành vi mặc định từ chối \cite{postgresql_rls_2026}. Thành phần `USING` xác định tập hàng hiện hữu có thể được truy cập hoặc tác động, còn `WITH CHECK` kiểm tra trạng thái mới do thao tác `INSERT` hoặc `UPDATE` tạo ra \cite{postgresql_rls_2026}.

Với bảng đa thuê bao, điều kiện cơ bản là hàng chỉ thuộc phạm vi truy cập khi `tenant_id` khớp với tenant hiện hành. Điểm quan trọng không nằm ở biểu thức so sánh mà ở **vị trí cưỡng chế**: policy được cơ sở dữ liệu áp dụng cho truy vấn trên bảng, thay vì phụ thuộc vào việc từng lập trình viên nhớ thêm điều kiện lọc.

Nguyên lý *fail-safe defaults* yêu cầu trạng thái mặc định của cơ chế bảo vệ là từ chối và quyền chỉ được cấp khi có điều kiện cho phép tường minh \cite{saltzer_protection_1975}. Nếu ngữ cảnh tenant được đọc bằng `current_setting(..., true)`, PostgreSQL có thể trả `NULL` khi biến không tồn tại \cite{postgresql_configfunc_2026}. Khi policy yêu cầu so sánh `tenant_id` với giá trị này, biểu thức không thể trở thành `TRUE` nếu tenant chưa được thiết lập, nhờ đó trạng thái thiếu ngữ cảnh có thể được thiết kế theo hướng không trả hàng nào thay vì vô tình mở toàn bộ bảng.

Có thể biểu diễn mục tiêu thiết kế dưới dạng:

\[
current\_tenant = \varnothing \Rightarrow AccessibleRows = \varnothing.
\]

Đây là mục tiêu fail-closed của thiết kế policy; tính đúng đắn cuối cùng vẫn cần được kiểm thử bằng hành vi dưới đúng vai runtime.

### 2.4.2. Phạm vi giao dịch và connection pooling

Ứng dụng web thường sử dụng connection pool để tái sử dụng kết nối cơ sở dữ liệu giữa nhiều yêu cầu. PostgreSQL phân biệt thiết lập ở phạm vi phiên với thiết lập cục bộ trong giao dịch; `SET LOCAL` chỉ có hiệu lực tới khi giao dịch hiện hành kết thúc \cite{postgresql_set_2026}. Nếu ngữ cảnh tenant được lưu ở phạm vi phiên trên một kết nối tái sử dụng, kết nối có thể mang giá trị của yêu cầu trước sang yêu cầu sau nếu không được đặt lại đúng cách.

Vì vậy, ngữ cảnh tenant nên có vòng đời trùng với đơn vị giao dịch nghiệp vụ: bắt đầu giao dịch, thiết lập tenant ở phạm vi cục bộ, thực hiện các truy vấn, sau đó kết thúc giao dịch. Khi kết nối quay về pool, ngữ cảnh cục bộ không tiếp tục tồn tại như trạng thái phiên dài hạn. Cách tổ chức này giảm nguy cơ rò rỉ ngữ cảnh giữa các yêu cầu và phù hợp với *complete mediation*: mỗi đơn vị truy cập được đánh giá trong ngữ cảnh của chính nó thay vì thừa hưởng trạng thái an ninh từ lần sử dụng kết nối trước \cite{saltzer_protection_1975}.

Một lợi ích quan trọng của thiết kế fail-closed là dạng lỗi khi quên thiết lập tenant có xu hướng biểu hiện thành thiếu dữ liệu hoặc yêu cầu thất bại, thay vì trả về dữ liệu ngoài phạm vi. Tuy nhiên, đây chỉ đúng nếu policy, quyền của vai runtime và cách truyền ngữ cảnh đều được cấu hình nhất quán.

### 2.4.3. Vai runtime và khả năng vượt qua RLS

RLS không tạo ra ranh giới bảo vệ nếu tài khoản mà ứng dụng sử dụng có khả năng bỏ qua cơ chế. PostgreSQL quy định superuser và các vai có thuộc tính `BYPASSRLS` có thể bỏ qua RLS; chủ sở hữu bảng thông thường cũng có thể không chịu RLS trừ khi áp dụng `FORCE ROW LEVEL SECURITY` trong các trường hợp phù hợp \cite{postgresql_rls_2026}. Vì vậy, cấu hình production cần tách vai sở hữu/di trú lược đồ khỏi vai runtime của ứng dụng và áp dụng nguyên lý **đặc quyền tối thiểu (least privilege)** \cite{saltzer_protection_1975}.

Vai runtime chỉ nên có những quyền dữ liệu cần thiết cho ứng dụng, đồng thời không phải superuser, không có `BYPASSRLS` và không có quyền DDL đủ để tự thay đổi cơ chế bảo vệ. Vai dùng cho migration có thể cần quyền rộng hơn nhưng không nên được dùng cho đường xử lý yêu cầu thông thường.

Một kiểm tra chỉ đọc metadata — ví dụ policy có tồn tại hay RLS có bật — chưa chứng minh ranh giới đang hoạt động dưới tài khoản thật. Phép kiểm có giá trị hơn là kiểm thử hành vi: kết nối bằng chính vai runtime, đặt tenant A, xác nhận không đọc/ghi được dữ liệu tenant B; đồng thời xác nhận trạng thái thiếu tenant bị từ chối. Như vậy, cấu hình an ninh được kiểm chứng ở đúng vị trí thực thi.

RLS trả lời câu hỏi **hàng nào có thể được chạm tới**. Nó không trả lời câu hỏi **người dùng có được phép thực hiện hành động nghiệp vụ này hay không**. Hai câu hỏi cần hai lớp kiểm soát khác nhau, dẫn đến mục 2.5.

## 2.5. Quản lý danh tính và kiểm soát truy cập

### 2.5.1. Xác thực, phân quyền và mặc định từ chối

**Xác thực (authentication)** xác định chủ thể đang tương tác với hệ thống. **Phân quyền (authorization)** quyết định chủ thể đã được xác thực được phép thực hiện hành động nào trên tài nguyên nào và trong phạm vi nào. Trong kiến trúc đa thuê bao, đăng nhập thành công chỉ xác nhận danh tính; nó không tự cấp quyền đối với mọi tenant mà người dùng biết hoặc từng tham gia.

Nguyên tắc mặc định từ chối tiếp tục áp dụng ở tầng ứng dụng: tài nguyên hoặc hành động chưa được khai báo công khai hay chưa có policy cho phép thì không nên truy cập được \cite{saltzer_protection_1975}. Mô hình ngược lại — chỉ chặn những điểm cuối đã biết là nhạy cảm — khiến mỗi tính năng mới có nguy cơ xuất hiện trong trạng thái mở cho tới khi được bổ sung rule.

### 2.5.2. Token và vòng đời phiên

JSON Web Token (JWT) là định dạng gọn để biểu diễn tập claim giữa các bên, được chuẩn hóa trong RFC 7519 \cite{jones_json_2015}. Với JWT tự chứa được ký, hệ thống **có thể** xác minh tính toàn vẹn và một số claim mà không cần truy vấn lại toàn bộ trạng thái phiên ở mỗi yêu cầu. Tuy nhiên, JWT không phải một giao thức xác thực hoàn chỉnh và cũng không bắt buộc hệ thống phải hoàn toàn phi trạng thái. Việc thu hồi phiên, vô hiệu hóa thiết bị, thay đổi quyền hoặc phát hiện token bị lộ vẫn có thể cần trạng thái phía máy chủ. Các thực hành an toàn cho JWT còn được tổng hợp trong RFC 8725 \cite{sheffer_json_2020}.

Một thiết kế phổ biến là dùng access token thời gian sống ngắn cho API và refresh token có vòng đời dài hơn để xin access token mới. Refresh token là một khái niệm được định nghĩa trong OAuth 2.0 \cite{hardt_oauth_2012}. Việc dùng cặp access/refresh trong một hệ thống không có nghĩa toàn bộ hệ thống phải được mô tả là một triển khai OAuth 2.0; luận văn chỉ sử dụng khái niệm vòng đời token làm cơ sở thiết kế. Các khuyến nghị an toàn hiện hành cho OAuth 2.0 được cập nhật trong RFC 9700 \cite{lodderstedt_best_2025}.

Đối với thao tác nhạy cảm, một phiên đang còn hiệu lực chưa chắc đủ để chứng minh người dùng hiện vẫn kiểm soát phiên đó. Hướng dẫn NIST SP 800-63B-4 trình bày các yêu cầu và khuyến nghị về xác thực, quản lý phương tiện xác thực, xác thực nhiều yếu tố và vòng đời xác thực \cite{nist_sp800_63b_2025}. Trong kiến trúc ứng dụng, điều này tạo cơ sở cho cơ chế xác thực lại trước các thao tác có mức rủi ro cao. Cách hiện thực cụ thể — chẳng hạn passcode, MFA hoặc “sudo mode” — thuộc Chương 3; Chương 2 chỉ xác lập nhu cầu phân biệt giữa “phiên hợp lệ” và “đã chứng minh lại danh tính cho hành động nhạy cảm”.

### 2.5.3. RBAC và phân quyền theo phạm vi

Role-Based Access Control (RBAC) gán quyền cho vai trò và gán người dùng vào vai trò, thay vì cấp trực tiếp từng quyền cho từng người dùng \cite{ferraiolo_proposed_2001,sandhu_role-based_1996}. Mô hình RBAC chuẩn còn hỗ trợ các quan hệ phân cấp vai và ràng buộc nhằm tổ chức quyền có cấu trúc \cite{ferraiolo_proposed_2001}.

Trong hệ đa thuê bao, quan hệ `User → Role → Permission` chưa đủ nếu vai trò không gắn với phạm vi. Cùng một người có thể là quản trị viên ở tenant A, người chỉ đọc ở workspace B, và không có quyền ở project C. Vì vậy quan hệ gán vai cần chứa tối thiểu bộ ba:

\[
(User, Role, Scope).
\]

Casbin mô tả mô hình RBAC with Domains, trong đó domain có thể được dùng để biểu diễn phạm vi mà một lần gán vai có hiệu lực \cite{casbin_authors_casbin_2024,casbin_authors_rbac_2026}. Với CTU-SignBridge, tenant, workspace và project tạo thành các loại scope mà policy có thể tham chiếu.

Quan hệ chứa `tenant → workspace → project` **không tự động tạo ra kế thừa quyền**. Hệ thống phải định nghĩa policy tường minh cho việc một vai ở tenant có hay không hiệu lực đối với workspace và project con. Cách phân biệt này quan trọng vì resource hierarchy và role hierarchy là hai khái niệm khác nhau; việc gộp chúng dễ dẫn đến quyền hiệu dụng lớn hơn dự kiến.

Một mô hình tổng quát hơn là Attribute-Based Access Control (ABAC), trong đó quyết định dựa trên thuộc tính của chủ thể, tài nguyên, hành động và môi trường \cite{hu_guide_2014}. ABAC có tính biểu đạt cao đối với policy động; đổi lại, việc giải thích và kiểm toán tập quyền hiệu dụng có thể phức tạp hơn vì quyết định được suy ra từ nhiều thuộc tính tại thời điểm truy cập. Với hệ thống có tập hành động nghiệp vụ tương đối ổn định và cần trả lời rõ “ai đang giữ vai gì ở phạm vi nào”, scoped RBAC là lựa chọn phù hợp; ABAC vẫn có thể bổ sung cho những điều kiện ngữ cảnh nếu về sau cần thiết.

### 2.5.4. Các lớp kiểm soát

Các cơ chế bảo vệ trả lời những câu hỏi khác nhau và không thay thế nhau.

**Bảng 2.6. Các câu hỏi kiểm soát và cơ chế tương ứng**

| Câu hỏi | Cơ chế |
|---|---|
| Chủ thể là ai? | Xác thực và quản lý phiên |
| Chủ thể được thực hiện hành động nghiệp vụ nào? | RBAC theo phạm vi / policy ứng dụng |
| Quan hệ dữ liệu này có được phép tồn tại? | Khóa chính, khóa ngoại, `UNIQUE`, `CHECK`, trigger/ràng buộc tương ứng |
| Hàng dữ liệu nào được chạm tới? | Row-Level Security |
| Có cần chứng minh lại danh tính cho thao tác nhạy cảm? | Xác thực lại / MFA theo chính sách |

*Nguồn: tác giả tổng hợp từ \cite{postgresql_rls_2026,ferraiolo_proposed_2001,sandhu_role-based_1996,casbin_authors_casbin_2024,saltzer_protection_1975,nist_sp800_63b_2025}.*

Việc phân lớp giúp tránh một lỗi phổ biến: dùng RBAC để thay cho tenant isolation hoặc dùng RLS để thay cho kiểm soát hành động nghiệp vụ. RLS có thể ngăn đọc hàng ngoài tenant nhưng không biết thao tác “publish dataset” có được phép hay không; ngược lại, policy ứng dụng có thể cho phép “publish” nhưng không nên có khả năng đọc hàng của tenant khác để thực hiện thao tác đó.

## 2.6. Thu nhận dữ liệu tại máy khách

### 2.6.1. Điểm mốc bàn tay như một kỹ thuật thu nhận

Ước lượng điểm mốc (landmark/keypoint estimation) xác định các điểm cấu trúc của cơ thể hoặc bộ phận cơ thể từ ảnh hoặc video. OpenPose là một công trình tiêu biểu cho ước lượng tư thế nhiều người dựa trên keypoint \cite{cao_openpose_2021}. MediaPipe cung cấp một khung xây dựng đường ống tri giác đa nền tảng \cite{lugaresi_mediapipe_2019}; MediaPipe Hands tập trung vào bàn tay với bộ phát hiện lòng bàn tay và mô hình dự đoán 21 điểm mốc cho mỗi bàn tay, hướng tới suy luận thời gian thực trên thiết bị \cite{zhang_mediapipe_2020}.

Trong luận văn, MediaPipe Hands được sử dụng như một **thành phần thu nhận có sẵn**, không phải đối tượng nghiên cứu thị giác máy tính. Luận văn không huấn luyện lại, mở rộng hay tuyên bố cải thiện mô hình điểm mốc.

Mỗi bàn tay có 21 điểm; mỗi điểm cung cấp ba thành phần tọa độ theo biểu diễn của mô hình. Với tối đa hai bàn tay, số giá trị hình học trên mỗi khung là:

\[
21 \times 3 \times 2 = 126.
\]

Một mẫu gồm \(T\) khung có thể được biểu diễn ở mức giao diện dữ liệu bằng ma trận:

\[
X \in \mathbb{R}^{T \times 126}.
\]

Biểu diễn này không nên được mô tả như tái dựng hình học 3D tuyệt đối của bàn tay; thành phần độ sâu của landmark là tọa độ tương đối theo mô hình, phù hợp hơn với cách hiểu 2.5D/relative-depth của đường ống MediaPipe Hands \cite{zhang_mediapipe_2020}.

**Hình 2.2. Cấu trúc 21 điểm mốc bàn tay của MediaPipe Hands.**  
*Nguồn: vẽ lại từ \cite{zhang_mediapipe_2020}.*

### 2.6.2. Hệ quả kiến trúc của trích xuất tại máy khách

Đặt bước trích xuất trên thiết bị người dùng tạo ra ba hệ quả kiến trúc.

Thứ nhất là **phân bố tải xử lý**. Một phần công việc thị giác máy tính được thực hiện ở biên thay vì tập trung hoàn toàn trên máy chủ. Điều này có thể giảm nhu cầu xử lý đồng bộ trên backend trong đường thu, nhưng mức tiết kiệm cụ thể phải được đo trong chương thực nghiệm thay vì suy ra bằng lý thuyết.

Thứ hai là **giảm mức phơi bày trong những luồng không cần video thô**. Nếu một nghiệp vụ chỉ yêu cầu landmark, hệ thống có thể lựa chọn không truyền hoặc không lưu hình ảnh trong chính luồng đó. Tuy nhiên, điều này không đồng nghĩa landmark đã trở thành dữ liệu vô danh; khả năng nhận dạng còn phụ thuộc nội dung, dữ liệu liên kết và bối cảnh sử dụng.

Thứ ba là **dịch chuyển ranh giới tin cậy**. Payload đến máy chủ đã được tạo trong môi trường không do backend kiểm soát hoàn toàn. Vì vậy máy chủ phải coi landmark, nhãn, timestamp và các chỉ số do máy khách gửi là dữ liệu đầu vào không đáng tin cậy cho tới khi được kiểm tra. Những thuộc tính có thể xác minh từ payload cần được kiểm tra lại; những thuộc tính không thể tái lập ở máy chủ không nên được mặc nhiên xem là bằng chứng chất lượng chỉ vì client đã tính chúng. Đây là điểm mà một quyết định tối ưu đường thu đồng thời trở thành một quyết định an ninh và toàn vẹn dữ liệu.

### 2.6.3. Giới hạn của biểu diễn và vị trí của phép biến đổi có mất mát

Biểu diễn chỉ gồm điểm mốc bàn tay không bảo toàn đầy đủ các thành phần phi thủ công như khuôn mặt, đầu và tư thế cơ thể, trong khi những thành phần này có thể mang thông tin ngôn ngữ \cite{liddell_grammar_2003,bragg_sign_2019}. Do đó, landmark bàn tay là một biểu diễn phù hợp cho một số nghiệp vụ hoặc phạm vi ký hiệu nhưng không phải biểu diễn đầy đủ của mọi hiện tượng ngôn ngữ ký hiệu.

Đây là lý do cần phân biệt **bản ghi nguồn** và **dữ liệu dẫn xuất**. Nếu hệ thống quyết định lưu bản ghi nguồn theo chính sách cho phép, các phép biến đổi có mất mát nên nằm ở hạ nguồn để có thể tái xử lý khi thuật toán hoặc mục tiêu nghiên cứu thay đổi. Nguyên tắc tách dữ liệu nguồn khỏi các biểu diễn dẫn xuất phù hợp với thiết kế hệ thống dữ liệu cần khả năng tái xử lý và truy xuất nguồn gốc \cite{kleppmann_designing_2017}.

Cuối cùng, dữ liệu landmark không đương nhiên là dữ liệu ẩn danh. Hướng dẫn về kỹ thuật ẩn danh nhấn mạnh sự khác biệt giữa dữ liệu thực sự không còn khả năng quy về cá nhân và dữ liệu đã được giảm hoặc tách định danh nhưng vẫn có khả năng liên kết lại \cite{wp29_anonymisation_2014}. Trong bối cảnh Việt Nam, việc xác định nghĩa vụ cụ thể cần dựa trên Luật Bảo vệ dữ liệu cá nhân và mục đích xử lý thực tế \cite{quochoi_luat_bvdlcn_2025}.

## 2.7. Xử lý bất đồng bộ và lưu trữ nội dung

### 2.7.1. Mô hình hàng đợi tác vụ

Một số thao tác như xử lý tệp, đồng bộ dịch vụ lưu trữ hoặc tạo dữ liệu dẫn xuất có thời gian thực hiện và khả năng thất bại khác với một yêu cầu HTTP tương tác. Giữ toàn bộ công việc trong request khiến thời gian phản hồi phụ thuộc vào bước chậm nhất và làm khó việc thử lại độc lập. Kiến trúc bất đồng bộ tách đường tiếp nhận khỏi đường thực thi công việc dài hơn \cite{kleppmann_designing_2017}.

Mô hình hàng đợi tác vụ gồm ba vai chính: **producer** tạo tác vụ; **broker** lưu và điều phối thông điệp; **worker** nhận và thực thi. Celery là framework hàng đợi tác vụ hỗ trợ mô hình này \cite{celery_contributors_celery_2026}; Redis có thể đảm nhiệm vai trò broker hoặc backend tùy cấu hình \cite{redis_ltd_redis_2026}. Việc lựa chọn công nghệ cụ thể thuộc Chương 3; ở mức cơ sở lý thuyết, điều quan trọng là tách giao thức nhận yêu cầu khỏi quá trình xử lý có thể chậm, thử lại hoặc thất bại.

### 2.7.2. Giao nhận, thử lại và tính lũy đẳng

Trong hệ thống phân tán, một worker có thể thực hiện xong tác vụ nhưng thất bại trước khi xác nhận, hoặc broker có thể giao lại thông điệp khi trạng thái hoàn thành chưa rõ. Vì vậy ứng dụng phải thiết kế cho khả năng **một tác vụ được thực thi nhiều hơn một lần** thay vì giả định mỗi thông điệp chắc chắn chỉ chạy đúng một lần \cite{kleppmann_designing_2017}.

Một biện pháp quan trọng là **tính lũy đẳng (idempotency)**. Với trạng thái hệ thống \(S\) và tác vụ \(t\), tác dụng mong muốn là:

\[
apply(apply(S,t),t)=apply(S,t).
\]

Ví dụ, nếu tác vụ tạo một bản ghi mẫu sau khi upload tệp, lần thử lại không được tạo ra hai mẫu độc lập cho cùng một lần đóng góp. Tính lũy đẳng có thể được hỗ trợ bằng idempotency key, unique constraint, trạng thái xử lý hoặc thiết kế upsert phù hợp; lựa chọn cụ thể phụ thuộc nghiệp vụ.

Các mẫu như *Idempotent Receiver*, *Guaranteed Delivery* và *Dead Letter Channel* được mô tả trong các mẫu tích hợp hệ thống doanh nghiệp \cite{hohpe_enterprise_2003}. Đối với lỗi tạm thời, retry cần có giới hạn và khoảng giãn phù hợp; đối với lỗi vĩnh viễn, tác vụ cần đi vào trạng thái quan sát được để xử lý thay vì lặp vô hạn hoặc biến mất khỏi hệ thống.

### 2.7.3. Yêu cầu đối với kho nội dung

Kho nội dung phục vụ tệp lớn cần đáp ứng các yêu cầu đã nêu ở mục 2.2.4: định danh ổn định, kiểm soát truy cập theo phạm vi, khả năng kiểm tra toàn vẹn khi cần, và xử lý nhất quán với retry. Công nghệ có thể là hệ thống tệp cục bộ hoặc dịch vụ lưu trữ bên ngoài; bản chất của cơ chế bảo vệ không phụ thuộc vào tên sản phẩm.

Một điểm cần giữ nhất quán là tenant isolation phải áp dụng cho **đường lấy tham chiếu** lẫn **đường đọc nội dung**. Nếu metadata được RLS bảo vệ nhưng backend chấp nhận một khóa tệp tùy ý và trả nội dung mà không kiểm scope, ranh giới tenant bị phá vỡ ở tầng lưu trữ dù cơ sở dữ liệu vẫn đúng policy.

## 2.8. Vòng đời tạo tác nghiên cứu: phiên bản, toàn vẹn và nguồn gốc

### 2.8.1. Trạng thái làm việc và trạng thái đã công bố

Một nền tảng dữ liệu cần tách **trạng thái làm việc** khỏi **trạng thái đã công bố**. Trạng thái làm việc có thể thay đổi khi thêm mẫu, sửa siêu dữ liệu, điều chỉnh danh mục hoặc loại dữ liệu không đạt. Trạng thái đã công bố phải cung cấp một điểm tham chiếu ổn định cho nghiên cứu và trao đổi giữa các hệ thống.

Với một phiên bản \(D_v\) đã công bố tại thời điểm \(t_v\), yêu cầu bất biến có thể biểu diễn:

\[
Published(D_v) \Rightarrow \forall t>t_v: D_v(t)=D_v(t_v).
\]

Nếu cần thay đổi nội dung, hệ thống tạo phiên bản mới \(D_{v+1}\) thay vì ghi đè \(D_v\). Cách tổ chức này giữ cho kết quả nghiên cứu, manifest hoặc đường đồng bộ đã tham chiếu phiên bản cũ vẫn có thể được kiểm chứng \cite{kleppmann_designing_2017}. Nó cũng là điều kiện để cơ chế ghim danh mục ở mục 2.3.3 có ý nghĩa.

### 2.8.2. Hàm băm, bản kê và chữ ký số

Hàm băm mật mã ánh xạ nội dung có độ dài bất kỳ thành giá trị băm có độ dài cố định. SHA-2 được chuẩn hóa trong FIPS 180-4 \cite{nist_fips180_4_2015}. Với mục tiêu phát hiện thay đổi, hệ thống có thể lưu giá trị băm của từng thành phần. Khi một phiên bản gồm nhiều tệp, các định danh, metadata cần thiết và giá trị băm có thể được tập hợp trong một **bản kê (manifest)** để mô tả chính xác nội dung của bản phát hành.

Giá trị băm chứng minh tính đồng nhất của nội dung theo nghĩa kiểm tra thay đổi, nhưng không tự chứng minh ai là bên đã công bố giá trị đó. Chữ ký số bổ sung thuộc tính xác thực nguồn công bố khi bên xác minh tin cậy khóa công khai tương ứng. Ed25519 là một biến thể EdDSA được thiết kế cho chữ ký hiệu năng cao \cite{bernstein_high-speed_2012} và được chuẩn hóa trong RFC 8032 \cite{josefsson_edwards-curve_2017}. Với Ed25519, khóa công khai dài 32 byte và chữ ký dài 64 byte; thuật toán ký có tính xác định, tránh phụ thuộc vào một nonce ngẫu nhiên mới cho mỗi chữ ký theo cách của một số lược đồ khác \cite{josefsson_edwards-curve_2017}.

Cần phân biệt **tamper-evident** và **tamper-proof**. Hash và chữ ký giúp thay đổi trái với bản kê được phát hiện khi xác minh; chúng không làm cho việc sửa hoặc xóa tệp trên thiết bị lưu trữ trở thành bất khả thi. Bảo vệ khóa riêng, phân quyền lưu trữ, sao lưu và khả năng phục hồi vẫn là các vấn đề riêng.

### 2.8.3. Xác minh fail-closed và hợp nhất đơn điệu

Khi một artifact được quy định phải có hash hoặc chữ ký hợp lệ, phía tiêu thụ cần xử lý lỗi xác minh theo hướng fail-closed: không sử dụng artifact như hợp lệ nếu hash hoặc chữ ký không khớp \cite{saltzer_protection_1975}. Việc tự động quay về một bản khác mà không báo trạng thái có thể che giấu lỗi integrity và làm thay đổi dữ liệu đầu vào của quá trình nghiên cứu.

Đối với một số luồng đồng bộ, hệ thống có thể sử dụng chiến lược **hợp nhất chỉ bổ sung**: bên nhận thêm những đối tượng đã được công bố mà mình chưa có, nhưng không để một bản đồng bộ cũ tự động xóa dữ liệu hiện hữu. Cách làm này tận dụng tính đơn điệu khi trạng thái chỉ tăng lên; nguyên lý CALM cho thấy tính đơn điệu có quan hệ chặt với khả năng đạt nhất quán mà không cần phối hợp cho từng cập nhật \cite{hellerstein_keeping_2020}.

Tuy nhiên, đây **không phải giải pháp tổng quát cho mọi bài toán đồng bộ**. Nếu nghiệp vụ yêu cầu truyền thao tác xóa, thay thế hoặc giải quyết cập nhật xung đột, phép hợp nhất đơn điệu không còn mô tả đầy đủ trạng thái. Do đó luận văn chỉ áp dụng lập luận này cho những miền dữ liệu được thiết kế theo hướng bổ sung hoặc công bố phiên bản mới, không dùng nó để phủ nhận nhu cầu xử lý delete/overwrite ở các miền khác.

## 2.9. Quản trị dữ liệu người tham gia

### 2.9.1. Người thu dữ liệu, người đóng góp và chủ thể dữ liệu

Trong một phiên thu, **người thực hiện thao tác thu**, **người đóng góp dữ liệu** và **chủ thể được ghi nhận trong mẫu** có thể là cùng một người nhưng không phải lúc nào cũng trùng. Chẳng hạn một cán bộ nghiên cứu có thể vận hành thiết bị cho một người tham gia thực hiện ký hiệu; người vận hành tạo request nhưng người tham gia mới là chủ thể xuất hiện trong dữ liệu.

Việc tách các vai này ở lược đồ giúp hệ thống trả lời ba câu hỏi độc lập: ai thực hiện thao tác kỹ thuật; ai chịu trách nhiệm đưa dữ liệu vào hệ thống; và dữ liệu mô tả hoặc ghi nhận ai. Nếu quan hệ với chủ thể không được ghi lại tại thời điểm thu, hệ thống có thể không còn đủ thông tin để xác định các bản ghi cần xử lý khi có yêu cầu liên quan đến dữ liệu cá nhân.

### 2.9.2. Bốn lớp cho phép và điều kiện sử dụng

Trong nền tảng vừa thu thập vừa phân phối dữ liệu, cần phân biệt ít nhất bốn lớp có chức năng khác nhau.

**Bảng 2.7. Bốn lớp cho phép và điều kiện sử dụng**

| Lớp | Mục đích | Chủ thể/bên liên quan điển hình |
|---|---|---|
| A. Cơ sở xử lý dữ liệu cá nhân | xác lập căn cứ và phạm vi xử lý dữ liệu về cá nhân | chủ thể dữ liệu và bên xử lý/kiểm soát theo quy định áp dụng |
| B. Quyền/khả năng đóng góp | xác nhận bên đưa dữ liệu vào có cơ sở để thực hiện việc đóng góp | người đóng góp / đơn vị cung cấp |
| C. Giấy phép tái sử dụng | quy định quyền sao chép, chia sẻ, tạo bản phái sinh, ghi công | bên có thẩm quyền cấp phép |
| D. Thỏa thuận truy cập/sử dụng | đặt nghĩa vụ cho bên nhận, ví dụ mục đích sử dụng, bảo mật, không tái định danh | bên nhận dữ liệu |

*Nguồn: tác giả tổng hợp.*

Các lớp không thay thế nhau. **A và B là các điều kiện tiên quyết để C và D có thể được thiết lập một cách hợp lệ đối với dữ liệu tương ứng**. Giấy phép tái sử dụng không thể thay thế cơ sở hợp pháp để thu thập và xử lý dữ liệu cá nhân, đồng thời không thể cấp nhiều quyền hơn những quyền mà bên cấp phép thực sự có.

Tương tự, license và thỏa thuận truy cập có chức năng khác nhau. License chủ yếu quy định phạm vi quyền tái sử dụng đối tượng được cấp phép; thỏa thuận truy cập có thể bổ sung nghĩa vụ dành riêng cho bên nhận, chẳng hạn bảo vệ dữ liệu, giới hạn mục đích hoặc không thực hiện tái định danh. Việc lựa chọn license cụ thể cho dữ liệu dùng chung là quyết định của Chương 3; Chương 2 giữ mô hình trung lập với loại giấy phép để không đồng nhất quản trị dữ liệu cá nhân với cấp phép tài sản trí tuệ.

### 2.9.3. Đồng thuận có phiên bản và các mức xử lý khi thu hồi

Một bản ghi đồng thuận chỉ chứa giá trị `true/false` không đủ để chứng minh chủ thể đã chấp thuận nội dung nào. Ở mức tối thiểu, hệ thống cần liên kết chấp thuận với chủ thể, văn bản, phiên bản và thời điểm:

\[
Consent=(Subject,Document,Version,Time).
\]

Từ đó phát sinh yêu cầu lưu trữ: phiên bản văn bản đã được dùng để thu chấp thuận phải truy lại được đúng nội dung. Nếu nội dung pháp lý hoặc điều kiện xử lý được thay đổi theo cách có thể làm thay đổi ý nghĩa, hệ thống cần tạo phiên bản mới và áp dụng quy trình chấp thuận phù hợp thay vì ghi đè tài liệu cũ. Việc một thay đổi cụ thể có yêu cầu xin lại đồng thuận hay không là vấn đề pháp lý/nghiệp vụ cần được xác định theo nội dung thay đổi; cơ chế kỹ thuật phải bảo đảm lịch sử phiên bản đủ để thực hiện quyết định đó.

“Thu hồi” hoặc “xóa” cũng không phải một thao tác duy nhất. Có thể phân biệt bốn mức theo cơ chế thi hành.

**Bảng 2.8. Các mức xử lý liên quan đến thu hồi và xóa**

| Mức | Nội dung | Cơ chế chính |
|---|---|---|
| 1 | Thu hồi quyền truy cập trong nền tảng | IAM/RBAC/RLS/session |
| 2 | Loại dữ liệu khỏi các bản phát hành trong tương lai | cổng kiểm tra trong pipeline công bố |
| 3 | Xóa dữ liệu khỏi các kho mà nền tảng kiểm soát | cơ sở dữ liệu + kho nội dung + quy trình vận hành |
| 4 | Xử lý bản sao đã được chuyển hợp pháp cho bên thứ ba | thỏa thuận, nghĩa vụ pháp lý và quy trình ngoài phạm vi kỹ thuật thuần túy |

*Nguồn: tác giả tổng hợp; tiêu chí phân loại là cơ chế thi hành.*

Bốn mức không tự động kéo theo nhau. Hệ thống có thể ngăn một mẫu xuất hiện trong bản phát hành mới nhưng không có khả năng kỹ thuật thu hồi một bản sao đã được bên thứ ba tải về trước đó. Vì vậy phần mềm không nên hứa một cơ chế “recall” tuyệt đối đối với dữ liệu đã rời khỏi phạm vi kiểm soát; thay vào đó cần phân biệt rõ những gì hệ thống cưỡng chế được với những nghĩa vụ cần được thực hiện bằng quy trình pháp lý hoặc hợp đồng.

### 2.9.4. Cơ sở pháp lý về bảo vệ dữ liệu cá nhân tại Việt Nam

Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 được ban hành ngày 26/06/2025 và có hiệu lực từ ngày 01/01/2026 \cite{quochoi_luat_bvdlcn_2025}. Nghị định số 356/2025/NĐ-CP quy định chi tiết một số điều và biện pháp thi hành Luật, có hiệu lực cùng ngày 01/01/2026 \cite{chinhphu_nd356_2025}. Đây là các căn cứ pháp lý trực tiếp cần xem xét khi hệ thống xử lý dữ liệu gắn với cá nhân tại Việt Nam.

Ở mức thiết kế phần mềm, các yêu cầu pháp lý liên quan chuyển thành một số năng lực hệ thống cần có. Thứ nhất, để thực hiện yêu cầu của chủ thể dữ liệu, hệ thống phải truy được những bản ghi liên quan đến chủ thể tương ứng. Thứ hai, để chứng minh nội dung đã được thông báo hoặc chấp thuận, hệ thống phải bảo toàn phiên bản văn bản và bằng chứng chấp thuận. Thứ ba, kiểm soát truy cập phải giới hạn những người và quy trình được phép xử lý dữ liệu. Thứ tư, vòng đời xóa phải bao phủ cả metadata và tệp nằm ngoài cơ sở dữ liệu.

Việc dữ liệu đã được chuyển sang landmark hoặc dạng đặc trưng không đương nhiên đưa nó ra khỏi phạm vi quản trị dữ liệu cá nhân. Mức độ nhận dạng phải được đánh giá dựa trên khả năng liên kết với cá nhân, dữ liệu phụ trợ và mục đích xử lý, thay vì chỉ dựa trên việc ảnh khuôn mặt có còn tồn tại hay không \cite{wp29_anonymisation_2014,quochoi_luat_bvdlcn_2025}.

Phần này chỉ chuyển các yêu cầu liên quan thành ràng buộc kiến trúc phục vụ luận văn Software Engineering; nó không nhằm tuyên bố nền tảng đã đạt tuân thủ pháp lý toàn diện. Đánh giá tuân thủ đầy đủ còn phụ thuộc quy trình vận hành, nội dung văn bản, vai trò pháp lý của các bên và bối cảnh triển khai thực tế.

### 2.9.5. Khả năng tiếp cận như một thuộc tính chất lượng

Nền tảng phục vụ người dùng có nhu cầu và phương thức giao tiếp khác nhau, trong đó có người Điếc và người sử dụng ngôn ngữ ký hiệu. Do đó, khả năng tiếp cận cần được xem là một thuộc tính chất lượng của giao diện và quy trình tương tác chứ không phải phần bổ sung sau khi hệ thống đã hoàn thành.

Web Content Accessibility Guidelines (WCAG) 2.2 của W3C cung cấp một khung tham chiếu cho việc thiết kế nội dung web có khả năng tiếp cận tốt hơn \cite{w3c_wcag22_2023}. Trong luận văn, WCAG 2.2 được dùng làm **khung tham chiếu** để hình thành yêu cầu giao diện. Chỉ khi có kế hoạch kiểm thử và bằng chứng tương ứng mới nên tuyên bố một mức conform cụ thể; Chương 2 không mặc nhiên khẳng định CTU-SignBridge đạt WCAG 2.2 AA hay một mức nào khác.

## 2.10. Triển khai và tiến hóa hệ thống

### 2.10.1. Container hóa, Twelve-Factor và ranh giới cấu hình

Container đóng gói ứng dụng và các phụ thuộc vào đơn vị triển khai tương đối nhất quán giữa các môi trường \cite{merkel_docker_2014}. Tuy nhiên, container là ranh giới triển khai tiến trình, **không phải ranh giới tenant**. Việc chạy backend, worker hay frontend trong các container khác nhau không tự tạo ra cô lập dữ liệu giữa các tổ chức; tenant isolation vẫn phải được thực hiện trong IAM, cơ sở dữ liệu và kho nội dung.

The Twelve-Factor App đề xuất các nguyên tắc cho ứng dụng dạng dịch vụ, trong đó có tách cấu hình triển khai khỏi mã nguồn, xem database/broker như backing services, hạn chế trạng thái cục bộ của tiến trình và xem log như luồng sự kiện \cite{wiggins_twelve-factor_2017}. Những nguyên tắc này phù hợp với nền tảng có nhiều môi trường triển khai và nhiều thành phần thực thi.

Cần phân biệt:

\[
DeploymentConfiguration \neq TenantConfiguration.
\]

**Cấu hình triển khai** mô tả môi trường chạy: địa chỉ cơ sở dữ liệu, broker, secret, endpoint dịch vụ. **Cấu hình tenant** là dữ liệu nghiệp vụ riêng của một tenant, chẳng hạn lựa chọn danh mục, giới hạn hoặc thiết lập chức năng. Nếu cấu hình tenant được đặt trong biến môi trường, mỗi tenant sẽ cần một deployment riêng và làm mất mục tiêu chia sẻ hạ tầng. Vì vậy tenant configuration cần được lưu như dữ liệu có scope và chịu cùng cơ chế kiểm soát với tài nguyên tenant khác.

### 2.10.2. Di trú hệ thống đang vận hành

Với hệ thống đã có dữ liệu và người dùng, thay đổi kiến trúc theo kiểu thay thế toàn bộ trong một lần làm tăng phạm vi rủi ro. *Strangler Fig Application* mô tả cách hiện đại hóa từng bước: chức năng mới được xây bên cạnh đường cũ, lưu lượng hoặc nghiệp vụ được chuyển dần, và thành phần cũ chỉ được bỏ khi đã được thay thế và kiểm chứng \cite{fowler_strangler_2004}.

Đối với CTU-SignBridge, nguyên lý này phù hợp với các thay đổi nền tảng như chuyển từ mô hình đơn tenant sang multi-tenant, thêm authorization engine hoặc thay đổi cơ chế lưu trữ. Một cơ chế nhạy cảm có thể chạy ở chế độ song song (*shadow mode*): đường cũ vẫn quyết định, đường mới tính kết quả để đối chiếu và ghi log. Chỉ khi sai khác đã được giải thích và test đạt yêu cầu mới chuyển quyền quyết định sang cơ chế mới.

Cách tiếp cận tăng dần không loại bỏ nhu cầu migration dữ liệu, rollback và test; nó chỉ giới hạn phạm vi thay đổi tại từng bước. Chương 3 sẽ trình bày cách nguyên tắc này được áp dụng vào kiến trúc hiện hữu của nền tảng.

## 2.11. Tổng hợp và khoảng trống nghiên cứu

Các cơ sở lý thuyết trong chương có thể được nhìn qua hai vòng đời liên kết: **vòng đời dữ liệu** và **vòng đời quản trị**. Vòng đời dữ liệu mô tả quá trình từ quan sát nguồn, mẫu hợp lệ, phiên bản bộ dữ liệu đến phân phối. Vòng đời quản trị mô tả các điều kiện cần thiết để từng chuyển tiếp được phép xảy ra: cơ sở xử lý, quyền đóng góp, kiểm tra toàn vẹn, giấy phép và thỏa thuận truy cập.

**Bảng 2.9. Các cổng nối vòng đời dữ liệu và vòng đời quản trị**

| Chuyển tiếp trong vòng đời dữ liệu | Điều kiện quản trị cần kiểm tra |
|---|---|
| Bản ghi nguồn → mẫu hợp lệ | chủ thể/nguồn gốc được xác định; cơ sở xử lý và quyền đóng góp phù hợp |
| Mẫu → phiên bản bộ dữ liệu đã công bố | kiểm duyệt, phiên bản bất biến, manifest/hash/chữ ký khi được yêu cầu |
| Phiên bản bộ dữ liệu → phân phối | điều kiện cấp phép/tái sử dụng đã được xác lập |
| Phân phối → bên nhận bên ngoài | điều kiện truy cập hoặc thỏa thuận sử dụng tương ứng được chấp nhận |

**Hình 2.3. Vòng đời dữ liệu và vòng đời quản trị với các cổng kiểm soát.**  
*Nguồn: tác giả xây dựng.*

Từ hai vòng đời này có thể tổng hợp bốn quan hệ chính. Thứ nhất, nhiều tổ chức dùng chung hạ tầng làm phát sinh yêu cầu cô lập ở cả cơ sở dữ liệu và đường truy cập nội dung ngoài cơ sở dữ liệu. Thứ hai, cô lập dữ liệu và phân quyền nghiệp vụ trả lời hai câu hỏi khác nhau, nên cần RLS/ràng buộc dữ liệu ở một lớp và authorization theo phạm vi ở lớp khác. Thứ ba, dữ liệu chỉ có khả năng tái sử dụng đáng tin cậy khi đi kèm siêu dữ liệu, nguồn gốc và phiên bản bất biến. Thứ tư, khi nền tảng trực tiếp tạo dữ liệu từ người tham gia, quản trị chủ thể, cơ sở xử lý và bằng chứng chấp thuận phải xuất hiện ngay trong đường thu thay vì được xem như metadata tùy chọn bổ sung về sau.

Trong các lớp công cụ đã khảo sát, bộ dữ liệu như WLASL và AUTSL cung cấp sản phẩm dữ liệu và cho thấy vai trò của metadata, nhưng chúng là đầu ra của quá trình thu thập chứ không phải hạ tầng tổ chức quá trình đó \cite{li_wlasl_baibao_2020,sincan_autsl_2020}. ELAN hỗ trợ chú giải dữ liệu đã có nhưng không đặt multi-tenant governance làm trọng tâm \cite{wittenburg_elan_2006}. REDCap cho thấy thu thập dựa trên biểu mẫu, phân quyền theo dự án và audit có thể được tích hợp trong một nền tảng nghiên cứu \cite{harris_research_2009,harris_redcap_2019}; điểm định vị khác của CTU-SignBridge là phương thức thu nhận dữ liệu ngôn ngữ ký hiệu, tầng danh mục chuyên biệt và ranh giới tenant/workspace/project. Dataverse và Zenodo cung cấp năng lực nộp lưu, mô tả, phiên bản, định danh và điều kiện truy cập đối với research object đã được hình thành \cite{crosas_dataverse_2011,cern_openaire_zenodo_2013}; nền tảng thu thập cần bổ sung khả năng thiết lập quan hệ subject–session–sample và cơ sở xử lý ngay trong quá trình tạo dữ liệu.

Các tài liệu về multi-tenancy và RBAC cung cấp cơ sở cho ranh giới tổ chức và kiểm soát truy cập \cite{bezemer_multi-tenant_2010,chong_architecture_2006,aulbach_multi-tenant_2008,krebs_architectural_2012,ferraiolo_proposed_2001,sandhu_role-based_1996}. FAIR, Datasheets và data commons cung cấp cơ sở cho khả năng tái sử dụng, tài liệu hóa và quản trị dữ liệu \cite{wilkinson_fair_2016,gebru_datasheets_2021,grossman_case_2016,hess_understanding_2007}. Các hướng này là nền tảng cần thiết nhưng không tự xác định một kiến trúc cụ thể cho việc thu thập VSL đa tổ chức.

**Trong phạm vi các lớp công cụ được khảo sát**, khoảng trống mà luận văn hướng tới nằm ở giao của ba yêu cầu: **(1) thu nhận dữ liệu theo phương thức chuyên biệt của miền ngôn ngữ ký hiệu; (2) quản trị và cô lập nhiều tổ chức trên hạ tầng dùng chung; và (3) thiết lập quan hệ giữa chủ thể dữ liệu, nguồn gốc, cơ sở xử lý và phiên bản ngay từ thời điểm thu**. Đóng góp của luận văn không nằm ở việc phát minh riêng từng cơ chế — RLS, RBAC, task queue, hash hay versioning đều đã có cơ sở kỹ thuật — mà ở việc tổ chức chúng thành một nền tảng thống nhất, trong đó các ranh giới quan trọng được biểu diễn và cưỡng chế bằng cơ chế có thể kiểm thử thay vì chỉ dựa vào quy ước lập trình.

Các khái niệm và quan hệ được trình bày trong chương này là cơ sở để Chương 3 mô tả kiến trúc, mô hình dữ liệu, cơ chế phân quyền, vòng đời dữ liệu và phương án triển khai cụ thể của CTU-SignBridge.
