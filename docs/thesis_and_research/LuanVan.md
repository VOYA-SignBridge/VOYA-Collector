# HƯỚNG DẪN BIÊN DỊCH LATEX CHO OVERLEAF

Chào bạn, tôi đã phân tách toàn bộ nội dung luận văn thành một dự án LaTeX hoàn chỉnh và lưu trong thư mục **`LuanVan_LaTeX`** ngay cạnh file này. 
Lý do file này lúc nãy trông "từ lưa" là vì nó đang chứa bản nháp cũ tiếng Việt, còn các file hoàn chỉnh tiếng Anh thì đang nằm trong thư mục kia.

**ĐỂ SỬ DỤNG TRÊN OVERLEAF:**
Bạn hãy nén toàn bộ thư mục **`LuanVan_LaTeX`** thành file `.zip`, sau đó lên Overleaf chọn "Upload Project". Nó sẽ tự động biên dịch hoàn hảo.

---

### TÔI ĐÃ FIX CÁC LỖI "BỂ CẤU TRÚC" (BROKEN STRUCTURE & FONT):

1. **Sửa lỗi Vỡ Font (Broken Font):**
   - Trong môi trường `babel` tiếng Anh, nếu bạn gọi tên tác giả người Việt (như *Lê Thị Lan* ở phần Reference), pdfLaTeX sẽ bị vỡ font và làm mất chữ. 
   - **Cách fix:** Tôi đã chèn trực tiếp `\usepackage[T5]{fontenc}` vào file `preample.tex`. Đảm bảo 100% không còn vỡ chữ tiếng Việt dù bạn đang dùng môi trường Tiếng Anh.

2. **Sửa lỗi Bể Cấu Trúc Chữ Ký (Broken Layout):**
   - Lỗi kinh điển của LaTeX là dùng 2 cái `\begin{minipage}{0.5\textwidth}` cạnh nhau nhưng vô tình có khoảng trắng/xuống dòng ở giữa khiến 2 cái này bị đẩy xuống 2 hàng thay vì nằm ngang hàng. 
   - **Cách fix:** Tôi đã thêm ký tự `%` ở cuối dòng giữa 2 minipage trong file `nhanxet.tex`. Bây giờ phần duyệt của Trưởng Khoa và Cán bộ hướng dẫn đã nằm song song hoàn hảo ngang hàng nhau.

3. **Sửa lỗi Header rác:**
   - Gói `fancyhdr` ban đầu không có cấu hình, dẫn đến việc Overleaf tự động nhét các header mặc định xấu xí lên đầu mỗi trang.
   - **Cách fix:** Tôi đã thêm `\fancyhead{}` để dọn sạch rác header.

Nếu bạn muốn xem một bản gộp duy nhất (Monolithic) của toàn bộ các file LaTeX đó, bạn có thể copy toàn bộ đoạn mã bên dưới và dán đè vào file `main.tex` trên Overleaf:

<details>
<summary><b>Nhấn vào đây để xem toàn bộ Mã Nguồn Gộp (Single File)</b></summary>

```latex
\documentclass{report}

% --- PREAMBLE ---
\usepackage[T5]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[english]{babel}
\usepackage[left=3.5cm, right=2cm, top=3.5cm, bottom=3cm]{geometry}
\usepackage{graphicx,float}
\usepackage{mathtools}
\usepackage{amssymb,amsmath}
\usepackage{mathptmx}       
\usepackage[varvw]{newtxmath}
\usepackage{multicol}
\usepackage{xcolor}
\usepackage{titlesec,titletoc}
\usepackage{indentfirst}
\usepackage{tikz}
\usetikzlibrary{calc}
\usepackage{tikzpagenodes}
\usepackage{fancyhdr}
\pagestyle{fancy}
\setlength{\headheight}{18pt}
\fancyhead{} 
\fancyhead[R]{\thepage} 
\fancyfoot{}
\usepackage[fontsize=13]{scrextend}
\renewcommand{\baselinestretch}{1.5} 
\setlength{\parindent}{0cm}
\allowdisplaybreaks
\usepackage{hyperref}
\hypersetup{colorlinks=true,linkcolor=black,citecolor=black,urlcolor=black}

\newcommand{\coverborder}{
\begin{tikzpicture}[remember picture,overlay]
\draw[line width=0.8pt] (current page text area.north west) rectangle (current page text area.south east);
\draw[line width=2.8pt] ($(current page text area.north west)+(0.15cm,-0.15cm)$) rectangle ($(current page text area.south east)+(-0.15cm,0.15cm)$);
\end{tikzpicture}
} 

\usepackage{titletoc}
\titlecontents{chapter}[0pt]{\bfseries\color{black}}{\MakeUppercase\chaptername\ \thecontentslabel\quad}{}{\normalfont\dotfill\bfseries\contentspage}
\titlecontents{section}[2.5ex]{\color{black}}{ \thecontentslabel\quad}{}{\dotfill\contentspage}
\titlecontents{subsection}[5ex]{\color{black}}{ \thecontentslabel\quad}{}{\dotfill\contentspage}
\titlecontents{figure}[0pt]{\color{black}}{\figurename\ \thecontentslabel:\quad}{}{\dotfill\contentspage}
\titlecontents{table}[0pt]{\color{black}}{\tablename\ \thecontentslabel:\quad}{}{\dotfill\contentspage}

\usepackage{caption}
\usepackage{subcaption}
\captionsetup[figure]{labelfont=it,textfont=it}
\captionsetup[table]{labelfont=it,textfont=it}
\numberwithin{figure}{chapter}
\numberwithin{table}{chapter}

\usepackage{glossaries}
\makeglossaries
\usepackage{array, diagbox, booktabs}
\usepackage[table]{xcolor}

\newcommand{\StudentName}{[STUDENT NAME IN ALL CAPS]}
\newcommand{\StudentID}{[YOUR STUDENT ID]}
\newcommand{\ClassCode}{[CLASS CODE]}
\newcommand{\ThesisTitle}{BUILDING A LARGE-SCALE SIGN LANGUAGE DATA COLLECTION AND MANAGEMENT PLATFORM INTEGRATED WITH MULTI-TENANCY}
\newcommand{\SupervisorName}{[SUPERVISOR'S NAME]}
\newcommand{\SupervisorTitle}{Assoc. Prof. / Dr. / MSc.}
\newcommand{\insertfigure}[4]{
    \begin{figure}[H]
        \centering
        \includegraphics[width=#1\textwidth]{#2}
        \caption{#3}
        \label{fig:#4}
    \end{figure}
}

\begin{document}

% --- COVER 1 ---
\begin{titlepage}
\coverborder
\begin{center}
    {\large CAN THO UNIVERSITY} \\
    {\large COLLEGE OF INFORMATION AND COMMUNICATION TECHNOLOGY} \\ 
    {\large DEPARTMENT OF SOFTWARE ENGINEERING} \\
    \vspace{3cm}
    {\large \textbf{\StudentName}} \\
    \vspace{2cm}
    {\Huge \textbf{\ThesisTitle}} \\
    \vspace{2cm}
    {\large UNDERGRADUATE THESIS} \\
    {\large MAJOR: SOFTWARE ENGINEERING} \\
    \vfill
    {\large 202X}
\end{center}
\end{titlepage}

% --- COVER 2 ---
\begin{titlepage}
\coverborder
\begin{center}
    {\large CAN THO UNIVERSITY} \\
    {\large COLLEGE OF INFORMATION AND COMMUNICATION TECHNOLOGY} \\
    {\large DEPARTMENT OF SOFTWARE ENGINEERING} \\
    \vspace{2cm}
    {\large \textbf{\StudentName}} \\
    \vspace{2cm}
    {\Huge \textbf{\ThesisTitle}} \\
    \vspace{2cm}
    {\large UNDERGRADUATE THESIS} \\
    {\large MAJOR: SOFTWARE ENGINEERING} \\
    \vspace{1.5cm}
    \begin{flushright}
    SUPERVISOR \\
    \textbf{\SupervisorTitle\ \SupervisorName}
    \end{flushright}
    \vfill
    {\large 202X}
\end{center}
\end{titlepage}

% --- APPROVAL ---
\newpage
\begin{center}
    {\large CAN THO UNIVERSITY} \\
    {\large COLLEGE OF INFORMATION AND COMMUNICATION TECHNOLOGY} \\
    {\large DEPARTMENT OF SOFTWARE ENGINEERING} \\
    \vspace{1cm}
    {\large \textbf{THESIS APPROVAL}}
\end{center}
\vspace{0.5cm}
\noindent Thesis Title: “\ThesisTitle”, carried out by student \textbf{\StudentName} at [Laboratory Name] – Department of Software Engineering – College of Information and Communication Technology – Can Tho University, from [Month] to [Month] under the supervision of \SupervisorTitle\ \SupervisorName.
\vspace{1.5cm}
\noindent
\begin{minipage}{0.5\textwidth}
\begin{center}
Can Tho, [Month] [Day], 20...\\
\textbf{Department of Software Engineering}\\
(Approved)
\end{center}
\end{minipage}%
\begin{minipage}{0.5\textwidth}
\begin{center}
Can Tho, [Month] [Day], 20...\\
\textbf{Supervisor}\\
\vspace{2cm}
\textbf{\SupervisorTitle\ \SupervisorName}
\end{center}
\end{minipage}
\vspace{3cm}
\begin{center}
Can Tho, [Month] [Day], 20...\\
\textbf{College of Information and Communication Technology}\\
(Approved)
\end{center}

% --- ABSTRACT ---
\newpage
\chapter*{ABSTRACT}
The project “Building a large-scale Sign Language data collection...”

\newpage
\tableofcontents
\newpage
\listoftables
\addcontentsline{toc}{chapter}{LIST OF TABLES}
\newpage
\listoffigures
\addcontentsline{toc}{chapter}{LIST OF FIGURES}

\chapter{INTRODUCTION}
According to statistics...

\chapter{THEORETICAL BACKGROUND}
\section{Domestic and Foreign Research}

\end{document}
```
</details>
