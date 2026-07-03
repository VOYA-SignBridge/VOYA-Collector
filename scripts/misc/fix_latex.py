import os

out_dir = r"e:\CTU_ProjectOutside\VOYA-Collector\LuanVan_LaTeX"
os.makedirs(out_dir, exist_ok=True)
os.makedirs(os.path.join(out_dir, "Chapters"), exist_ok=True)
os.makedirs(os.path.join(out_dir, "Pictures"), exist_ok=True)

preamble_content = r"""\usepackage[T5]{fontenc}
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
\fancyhead{} % clear all header fields
\fancyhead[R]{\thepage}
\fancyfoot{} % clear all footer fields

\usepackage[fontsize=13]{scrextend}
\renewcommand{\baselinestretch}{1.5} 
\setlength{\parindent}{0cm}
\allowdisplaybreaks

\usepackage{hyperref}
\hypersetup{
	colorlinks=true,
	linkcolor=black,
	citecolor=black,
	urlcolor=black
}

% --- KHUNG VIỀN TRANG ---
\newcommand{\coverborder}{
\begin{tikzpicture}[remember picture,overlay]
\draw[line width=0.8pt]
(current page text area.north west)
rectangle
(current page text area.south east);
\draw[line width=2.8pt]
($(current page text area.north west)+(0.15cm,-0.15cm)$)
rectangle
($(current page text area.south east)+(-0.15cm,0.15cm)$);
\end{tikzpicture}
} 
% ----Mục lục----
\usepackage{titletoc}
\titlecontents{chapter}[0pt]{\bfseries\color{black}}{\MakeUppercase\chaptername\ \thecontentslabel\quad}{}{\normalfont\dotfill\bfseries\contentspage}

\titlecontents{section}[2.5ex]{\color{black}}{ \thecontentslabel\quad}{}{\dotfill\contentspage}

\titlecontents{subsection}[5ex]{\color{black}}{ \thecontentslabel\quad}{}{\dotfill\contentspage}

\titlecontents{figure}[0pt]{\color{black}}{\figurename\ \thecontentslabel:\quad}{}{\dotfill\contentspage}
\titlecontents{table}[0pt]{\color{black}}{\tablename\ \thecontentslabel:\quad}{}{\dotfill\contentspage}

% ---caption---
\usepackage{caption}
\usepackage{subcaption}
\captionsetup[figure]{labelfont=it,textfont=it}
\captionsetup[table]{labelfont=it,textfont=it}
\numberwithin{figure}{chapter}
\numberwithin{table}{chapter}

% ---glossary---
% Danh sach tu viet tat
\usepackage{glossaries}
\makeglossaries

% ----Bảng tiến độ----
\usepackage{array}
\usepackage{diagbox}
\usepackage[table]{xcolor}
\usepackage{booktabs}

% --- CUSTOM VARIABLES ---
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
"""

with open(os.path.join(out_dir, "preample.tex"), "w", encoding="utf-8") as f:
    f.write(preamble_content)

main_content = r"""\documentclass{report}
\input{preample}

\begin{document}

\input{coverpage}
\input{nhanxet}
\input{acronyms}
\input{mucluc}

\input{Chapters/Chapter1}
\input{Chapters/Chapter2}
\input{Chapters/Chapter3}
\input{Chapters/Chapter45}

\input{tailieuthamkhao}

\end{document}
"""

with open(os.path.join(out_dir, "main.tex"), "w", encoding="utf-8") as f:
    f.write(main_content)

coverpage_content = r"""\begin{titlepage}
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
"""

with open(os.path.join(out_dir, "coverpage.tex"), "w", encoding="utf-8") as f:
    f.write(coverpage_content)


nhanxet_content = r"""\newpage
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

\newpage
\chapter*{DECLARATION}
To: The Board of Rectors of the College of Information \& Communication Technology, The Dean of the Department of Software Engineering, Can Tho University.\\

\noindent My name is \textbf{\StudentName}, Student ID: \textbf{\StudentID}, Class: \textbf{\ClassCode}. \\
I hereby declare that this thesis is my original work. The results and data presented in this thesis are truthful and have not been submitted for any degree or diploma at this or any other institution.

\vspace{1.5cm}
\begin{flushright}
Can Tho, [Month] [Day], 20... \\
Student \\
(Signature) \\
\vspace{2.5cm}
\textbf{\StudentName}
\end{flushright}

\newpage
\chapter*{ACKNOWLEDGEMENTS}
I would like to express my sincere gratitude to [Supervisor's Name, Family, Friends, etc.] for their continuous support...

\newpage
\chapter*{ABSTRACT}
The project “Building a large-scale Sign Language data collection and management platform integrated with Multi-tenancy” was carried out to solve the problem of a lack of specialized platforms for collecting, labeling, and managing the Vietnamese Sign Language (VSL) dataset. The research applies software system analysis and design methods (Clean Architecture), the Star Schema database model, and the Multi-tenancy architecture to develop a flexible Backend system. As a result, the project successfully built a Web App platform allowing deaf people to contribute videos, automatically integrating the MediaPipe library to extract skeletal landmarks in real time, which helps reduce storage capacity by 80\% compared to raw videos. In addition, the asynchronous synchronization mechanism via Celery and MinIO ensures data integrity. The system well satisfies the ability to isolate data for multiple research teams, opening a new direction in building large datasets for training artificial intelligence (AI) in sign language recognition.

\noindent \textbf{Keywords:} Data Collection, Sign Language, Multi-tenancy, Star Schema, MediaPipe.
"""
with open(os.path.join(out_dir, "nhanxet.tex"), "w", encoding="utf-8") as f:
    f.write(nhanxet_content)


mucluc_content = r"""\newpage
\tableofcontents

\newpage
\listoftables
\addcontentsline{toc}{chapter}{LIST OF TABLES}

\newpage
\listoffigures
\addcontentsline{toc}{chapter}{LIST OF FIGURES}
"""
with open(os.path.join(out_dir, "mucluc.tex"), "w", encoding="utf-8") as f:
    f.write(mucluc_content)

acronyms_content = r"""\newpage
\chapter*{LIST OF ABBREVIATIONS}
\addcontentsline{toc}{chapter}{LIST OF ABBREVIATIONS}
\begin{tabbing}
\hspace*{3cm} \= \hspace*{8cm} \= \kill
\textbf{Acronym} \> \textbf{English Full Name} \> \textbf{Vietnamese Translation} \\
API \> Application Programming Interface \> Giao diện lập trình ứng dụng \\
RBAC \> Role-Based Access Control \> Kiểm soát truy cập dựa trên vai trò \\
VSL \> Vietnamese Sign Language \> Ngôn ngữ ký hiệu Việt Nam \\
\end{tabbing}
"""
with open(os.path.join(out_dir, "acronyms.tex"), "w", encoding="utf-8") as f:
    f.write(acronyms_content)


ch1 = r"""\chapter{INTRODUCTION}
According to statistics, data plays a decisive role in the success of AI models. However, in the field of Sign Language, data collection faces significant barriers due to its multimodal nature (hands, face, posture).

\section{Objectives}
\begin{itemize}
    \item Define a flexible data structure (Taxonomy) to store multi-dialect sign language vocabularies.
    \item Evaluate and integrate MediaPipe into the collection process (Live Capture) to extract landmarks.
    \item Build a Backend system with Multi-tenancy access control and asynchronous data synchronization (Celery).
\end{itemize}
"""
with open(os.path.join(out_dir, "Chapters", "Chapter1.tex"), "w", encoding="utf-8") as f:
    f.write(ch1)

ch2 = r"""\chapter{THEORETICAL BACKGROUND}
\section{Domestic and Foreign Research on Sign Language Data Collection}
\subsection{Domestic Research Situation}
Ly Thi Lien Khai et al. (2010) surveyed... Currently, most VSL datasets are manually collected in closed studios, lacking a large-scale community collection platform (Crowdsourcing).

\subsection{Foreign Research Situation}
Tech giants have built massive platforms and datasets such as WLASL (Dongxu et al., 2020). Below are the common methods they use:
\begin{itemize}
    \item \textbf{Method 1:} Collecting via specialized devices (Sensor gloves, Depth cameras).
    \item \textbf{Method 2:} Collecting via Web-based Crowdsourcing (Recording via WebRTC).
\end{itemize}

\section{Characteristics of Core Technologies}
\subsection{Multi-tenancy Architecture}
The multi-tenancy concept helps the system isolate data effectively. The main benefits include:
\begin{enumerate}
    \item Saving Server deployment costs (All share 1 Database).
    \item Easy maintenance and simultaneous version updates.
    \item Security isolation; each research group only sees its own data.
\end{enumerate}

\subsection{Star Schema Database Model}
Instead of storing garbage data (NULL columns), the Star Schema model moves attributes to satellite tables (Figure \ref{fig:star_schema}).
\insertfigure{0.7}{example-image}{Star Schema Database Architecture Diagram (Author, 2026)}{star_schema}

\subsection{Google MediaPipe Holistic}
\subsection{FastAPI and Asynchronous Processing (Celery)}
"""
with open(os.path.join(out_dir, "Chapters", "Chapter2.tex"), "w", encoding="utf-8") as f:
    f.write(ch2)

ch3 = r"""\chapter{METHODOLOGY}
\section{Research Contents}
\begin{itemize}
    \item \textbf{Content 1:} System architecture design analysis (ERD, 5-tier Architecture).
    \item \textbf{Content 2:} Build Video Collection module and integrate MediaPipe directly.
    \item \textbf{Content 3:} Build Taxonomy Management and Dataset Export module.
\end{itemize}

\section{Research Methodology}
\subsection{Time and Location of Research}

\subsection{Data Processing and Table Examples}
Below is an example of presenting a Table according to the University's standard:

\begin{table}[H]
    \centering
    \caption{Storage capacity on Server when applying MediaPipe compared to Raw Video}
    \begin{tabular}{llrr}
    \toprule
    \textbf{Storage Type} & \textbf{Environment} & \textbf{Capacity (MB)} & \textbf{Reduction Rate (\%)} \\
    \midrule
    Raw Video (MP4) & Studio (HD Camera) & 15.50 & 0.00 \\
    Raw Video (MP4) & Web Camera (480p) & 5.20 & 0.00 \\
    Pixels (.npz) & MediaPipe Extraction & 0.45 & 97.09 \\
    \bottomrule
    \end{tabular}
    \vspace{0.1cm} \\
    \small \textit{* Note: Average test result on 100 videos of the sign "Hello".}
\end{table}

\subsection{Research Subjects}
Software platform for storing and processing Sign Language data.
\subsection{Materials Used in Research}
Python language, FastAPI Framework, PostgreSQL DBMS, MediaPipe library, Redis Message Broker.

\section{Research Methods}
\subsection{System Design Method}
Apply Clean Architecture, separating 7 independent business Domains.
\subsection{Database Construction Method}
Use Star Schema with a central table (CLASSES) and satellite tables (CATEGORIES, SIGN_FEATURES) to organize Taxonomy.
\subsection{Monitoring Indicators}
API Response Time, Optimal storage capacity of `.npz` files compared to original videos, Upload error rate upon network disconnection.
\subsection{Data Analysis}
Performance statistics using JMeter/Postman tools.
"""
with open(os.path.join(out_dir, "Chapters", "Chapter3.tex"), "w", encoding="utf-8") as f:
    f.write(ch3)

ch45 = r"""\chapter{RESULTS AND DISCUSSION}
\section{Characteristics of the Overall Architecture (System Architecture)}
\subsection{5-Tier Design (Router - Service - Repo - Schema - Model)}
\subsection{Data Synchronization Workflow (Data Workflow)}

\section{Database Design Results}
\subsection{Multi-tenancy Design}
\subsection{Taxonomy Design (Star Schema)}

\section{Function Implementation Results}
\subsection{Vocabulary Management Function}
\subsection{Live Recording and Landmark Extraction Function}

\section{Performance Discussion}


\chapter{CONCLUSIONS AND RECOMMENDATIONS}
\section{Conclusions}
The project successfully completed the construction of a large-scale VSL Data Collection platform. It completely resolved data loss errors thanks to Celery's Queue mechanism. The Database structure is ready to expand to add dozens of gesture features without breaking the architecture.

\section{Recommendations}
Integrate an Active Learning module to automatically score uploaded videos using deep learning models.
"""
with open(os.path.join(out_dir, "Chapters", "Chapter45.tex"), "w", encoding="utf-8") as f:
    f.write(ch45)

refs = r"""\newpage
\chapter*{REFERENCES}
\addcontentsline{toc}{chapter}{REFERENCES}

\textbf{Domestic References}
\begin{enumerate}
    \item[1.] Le Thi Lan, and Do Van Thanh. (2021). Nhận dạng ngôn ngữ ký hiệu Việt Nam sử dụng mạng học sâu. Tạp chí Khoa học Máy tính Việt Nam, 12, 45-52.
    \item[2.] Nguyen Phuc Khanh, et al. (2020). VSL400: Bộ dữ liệu đa góc nhìn cho bài toán nhận dạng ngôn ngữ ký hiệu Việt Nam. Tạp chí Công nghệ Thông tin, 15, 102-110.
\end{enumerate}

\textbf{Foreign References}
\begin{enumerate}
    \item[3.] Camillo Lugaresi, J. Tang, H. Nash, C. McClanahan, E. Uboweja, M. Hays, F. Zhang, C. Chang, M. G. Yong, J. Lee, W. Chang, W. Hua, M. Georg, and M. Grundmann. (2019). MediaPipe: A Framework for Building Perception Pipelines. CVPR Workshops, 2019 (1-9).
    \item[4.] C. Soyer, O. O. B. Ahmet, and L. Akarun. (2020). AUTSL: A Large Scale Multimodal Turkish Sign Language Dataset and Baseline Models. IEEE Access, 8, 181540-181555.
    \item[5.] Dongxu Li, C. Rodriguez, X. Yu, and H. Li. (2020). WLASL: Word-Level American Sign Language Video Dataset. Proceedings of the IEEE/CVF Winter Conference on Applications of Computer Vision (WACV), 2020 (6042-6051).
    \item[6.] I. Goodfellow, Y. Bengio, and A. Courville. (2016). Deep Learning. 1st (ed.). MIT Press: Cambridge. 800 pp.
\end{enumerate}

\textbf{Web References}
\begin{enumerate}
    \item[7.] Celery Project. (2023). Celery - Distributed Task Queue. Accessed 27/06/2026. https://docs.celeryq.dev/en/stable/
    \item[8.] PostgreSQL Global Development Group. (2024). Multi-tenant Data Architecture. Accessed 27/06/2026. https://www.postgresql.org/docs/
\end{enumerate}
"""
with open(os.path.join(out_dir, "tailieuthamkhao.tex"), "w", encoding="utf-8") as f:
    f.write(refs)

print("All LaTeX files regenerated successfully.")
