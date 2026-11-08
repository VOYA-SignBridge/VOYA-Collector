' =====================================================================
'  Nhap CDM v8 vao SAP PowerDesigner tu NAM tep CSV canh script nay.
'
'  Chay: PowerDesigner -> Tools -> Execute Commands -> Edit/Run Script
'        (Ctrl+Shift+X), mo tep nay roi Run.
'
'  BON LOI CUA BAN TRUOC, da sua — ghi lai de khong tai pham:
'
'  1. Doc UTF-8 sai. Ban truoc dung
'        fso.OpenTextFile(..., 1, False, -1)
'     va chu thich "-1 = UTF-8". SAI: -1 la TristateTrue, tuc UTF-16, khong
'     phai UTF-8. Cac CSV o day la UTF-8 co BOM. Nay dung ADODB.Stream voi
'     Charset = "utf-8".
'
'  2. Cong dinh danh la XANH GIA. Ban truoc tang bo dem du KHONG gan duoc
'     thuoc tinh nao, nen man hinh cuoi bao "53 dinh danh" trong khi 20 cai
'     rong khong. Nay moi thanh phan khong gan duoc la DUNG HAN.
'
'  3. Khong nhap Data Type. Bay gio co.
'
'  4. Khong doc 05_relationship_attributes.csv, nen "Granted At" bi mat, va
'     chu thich dau script noi "nam tep" trong khi chi doc bon.
'
'  Script KHONG dat vi tri hop: bo cuc de PowerDesigner tu sap roi chinh tay.
' =====================================================================
Option Explicit

Dim THU_MUC, LOI
LOI = ""
THU_MUC = Left(ActiveDocument.FullName, InStrRev(ActiveDocument.FullName, "\"))

' --------------------------------------------------------------- doc UTF-8
Function DocUTF8(ten)
   Dim st
   Set st = CreateObject("ADODB.Stream")
   st.Type = 2                 ' adTypeText
   st.Charset = "utf-8"
   st.Open
   On Error Resume Next
   st.LoadFromFile THU_MUC & ten
   If Err.Number <> 0 Then
      MsgBox "Khong doc duoc " & THU_MUC & ten & vbCrLf & Err.Description, vbCritical
      DocUTF8 = ""
      Exit Function
   End If
   On Error GoTo 0
   DocUTF8 = st.ReadText(-1)   ' adReadAll
   st.Close
End Function

Function TachDong(dong)
   Dim kq(), n, i, c, trong, buf
   n = 0 : ReDim kq(0) : buf = "" : trong = False
   For i = 1 To Len(dong)
      c = Mid(dong, i, 1)
      If c = """" Then
         trong = Not trong
      ElseIf c = "," And Not trong Then
         ReDim Preserve kq(n) : kq(n) = buf : n = n + 1 : buf = ""
      Else
         buf = buf & c
      End If
   Next
   ReDim Preserve kq(n) : kq(n) = buf
   kq(0) = Replace(kq(0), ChrW(&HFEFF), "")     ' bo BOM
   TachDong = kq
End Function

Function DocCSV(ten)
   Dim noi, dong, i, dau, cot, j, o, ds
   noi = DocUTF8(ten)
   Set ds = CreateObject("Scripting.Dictionary")
   If noi = "" Then Set DocCSV = ds : Exit Function
   dong = Split(Replace(noi, vbCrLf, vbLf), vbLf)
   For i = 0 To UBound(dong)
      If Trim(dong(i)) <> "" Then
         cot = TachDong(dong(i))
         If i = 0 Then
            dau = cot
         Else
            Set o = CreateObject("Scripting.Dictionary")
            For j = 0 To UBound(dau)
               If j <= UBound(cot) Then o.Add dau(j), cot(j) Else o.Add dau(j), ""
            Next
            ds.Add ds.Count, o
         End If
      End If
   Next
   Set DocCSV = ds
End Function

Function Tim(bo, ten)
   Dim x
   For Each x In bo
      If x.Name = ten Then Set Tim = x : Exit Function
   Next
   Set Tim = Nothing
End Function

Sub Bao(s)
   LOI = LOI & s & vbCrLf
End Sub

' --------------------------------------------------------------- bat dau
Dim mo
Set mo = ActiveModel
If mo Is Nothing Then
   MsgBox "Mo mot Conceptual Data Model truoc da.", vbCritical
   WScript.Quit
End If
If Not mo.IsKindOf(PdCDM.cls_Model) Then
   MsgBox "Model dang mo khong phai CDM.", vbCritical
   WScript.Quit
End If

Dim ds, i, r, e, a, idf, q, n_e, n_a, n_i, n_ic, n_r, n_ra
n_e = 0 : n_a = 0 : n_i = 0 : n_ic = 0 : n_r = 0 : n_ra = 0

' ---- 1. Entity ----
Set ds = DocCSV("01_entities.csv")
For i = 0 To ds.Count - 1
   Set r = ds(i)
   Set e = mo.Entities.CreateNew
   e.Name = r("Entity")
   e.Code = Replace(UCase(r("Entity")), " ", "_")
   e.Comment = "Nguon PDM: " & r("Source Table") & vbCrLf & "Loai: " & r("Type")
   n_e = n_e + 1
Next

' ---- 2. Attribute (co Data Type va Mandatory) ----
Set ds = DocCSV("02_attributes.csv")
For i = 0 To ds.Count - 1
   Set r = ds(i)
   Set e = Tim(mo.Entities, r("Entity"))
   If e Is Nothing Then
      Bao "Thuoc tinh tro toi thuc the khong co: " & r("Entity") & "." & r("Attribute")
   Else
      Set a = e.Attributes.CreateNew
      a.Name = r("Attribute")
      a.Code = Replace(UCase(r("Attribute")), " ", "_")
      a.DataType = r("Data Type")
      a.Mandatory = (UCase(r("Mandatory")) = "Y")
      a.Comment = "Cot PDM: " & r("Source Column")
      n_a = n_a + 1
   End If
Next

' ---- 3. Identifier — moi thanh phan PHAI gan duoc ----
Set ds = DocCSV("03_identifiers.csv")
For i = 0 To ds.Count - 1
   Set r = ds(i)
   Set e = Tim(mo.Entities, r("Entity"))
   If e Is Nothing Then
      Bao "Dinh danh tro toi thuc the khong co: " & r("Entity")
   Else
      Set idf = e.Identifiers.CreateNew
      idf.Name = r("Identifier")
      idf.Code = Replace(UCase(r("Identifier")), " ", "_")
      If Left(r("Kind"), 7) = "Primary" Then idf.Primary = True
      Dim tp, k, at, gan
      tp = Split(r("Attributes"), "|")
      For k = 0 To UBound(tp)
         Set at = Tim(e.Attributes, Trim(tp(k)))
         If at Is Nothing Then
            Bao "Dinh danh KHONG gan duoc: " & r("Entity") & "." & _
                r("Identifier") & " -> thuoc tinh `" & Trim(tp(k)) & "`"
         Else
            idf.Attributes.Add at
            n_ic = n_ic + 1
         End If
      Next
      n_i = n_i + 1
   End If
Next

' ---- 4. Relationship ----
Set ds = DocCSV("04_relationships.csv")
For i = 0 To ds.Count - 1
   Set r = ds(i)
   Dim e1, e2
   Set e1 = Tim(mo.Entities, r("Entity 1"))
   Set e2 = Tim(mo.Entities, r("Entity 2"))
   If e1 Is Nothing Or e2 Is Nothing Then
      Bao "Quan he tro toi thuc the khong co: " & r("Entity 1") & " -> " & r("Entity 2")
   Else
      Set q = mo.Relationships.CreateNew
      q.Object1 = e1
      q.Object2 = e2
      If r("Name") <> "" Then q.Name = r("Name")
      If r("Code") <> "" Then q.Code = r("Code")
      q.Entity2ToEntity1RoleCardinality = LucLuong(r("Cardinality E1"))
      q.Entity1ToEntity2RoleCardinality = LucLuong(r("Cardinality E2"))
      If UCase(r("Identifying")) = "Y" Then q.Entity1ToEntity2Dependent = True
      q.Comment = r("Nguon")
      n_r = n_r + 1
   End If
Next

' ---- 5. Relationship attributes ----
Set ds = DocCSV("05_relationship_attributes.csv")
For i = 0 To ds.Count - 1
   Set r = ds(i)
   Set q = Tim(mo.Relationships, r("Relationship"))
   If q Is Nothing Then
      Bao "Thuoc tinh quan he tro toi quan he khong co: " & r("Relationship")
   Else
      q.Comment = q.Comment & vbCrLf & "Thuoc tinh: " & r("Attribute") & _
                  " (" & r("Data Type") & ")"
      n_ra = n_ra + 1
   End If
Next

Function LucLuong(s)
   Select Case s
      Case "1"     : LucLuong = "1,1"
      Case "0..1"  : LucLuong = "0,1"
      Case "1..N"  : LucLuong = "1,n"
      Case Else    : LucLuong = "0,n"
   End Select
End Function

' --------------------------------------------------------------- ket qua
Dim tt
tt = "Thuc the      " & n_e & "   (can 49)" & vbCrLf & _
     "Thuoc tinh    " & n_a & "  (can 396)" & vbCrLf & _
     "Dinh danh     " & n_i & "   (can 52)" & vbCrLf & _
     "  thanh phan  " & n_ic & "   (can 53 — Tenant Usage ghep 2)" & vbCrLf & _
     "Quan he       " & n_r & "  (can 114)" & vbCrLf & _
     "Thuoc tinh QH " & n_ra & "    (can 1)"

If LOI <> "" Then
   MsgBox "NHAP HONG — khong dung ket qua nay:" & vbCrLf & vbCrLf & LOI & _
          vbCrLf & tt, vbCritical, "CDM v8"
Else
   MsgBox "Da nhap CDM v8:" & vbCrLf & vbCrLf & tt & vbCrLf & vbCrLf & _
          "Lech con so nao thi DUNG lai va doi chieu CSV, dung sua tay tren so do.", _
          vbInformation, "CDM v8"
End If
