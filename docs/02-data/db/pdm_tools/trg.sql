-- Nguon bang chung THU SAU: trigger.
--
-- Nam cau truy van dau (bang, cot, FK, CHECK, UNIQUE) KHONG thu trigger, va lo
-- do de `trg_legal_documents_freeze` di qua bon nhom QA ma khong ai thay: no
-- cuong che tinh bat bien cua legal_documents.content_hash o tang CSDL, nhung
-- khong xuat hien trong pg_constraint nen moi cong CHECK deu bao "sach".
--
-- Chi lay trigger NGUOI DUNG dinh nghia: tgisinternal loai bo trigger ma
-- Postgres tu dung cho khoa ngoai va ràng buộc hoan lai.
\pset format csv
\pset tuples_only off
SELECT c.relname                                       AS table_name,
       t.tgname                                        AS trigger_name,
       CASE WHEN t.tgtype & 2 = 2 THEN 'BEFORE' ELSE 'AFTER' END AS timing,
       btrim(CASE WHEN t.tgtype & 4  = 4  THEN 'INSERT ' ELSE '' END ||
             CASE WHEN t.tgtype & 8  = 8  THEN 'DELETE ' ELSE '' END ||
             CASE WHEN t.tgtype & 16 = 16 THEN 'UPDATE ' ELSE '' END ||
             CASE WHEN t.tgtype & 32 = 32 THEN 'TRUNCATE' ELSE '' END) AS events,
       CASE WHEN t.tgtype & 1 = 1 THEN 'ROW' ELSE 'STATEMENT' END AS level,
       p.proname                                       AS function_name
  FROM pg_trigger  t
  JOIN pg_class    c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_proc     p ON p.oid = t.tgfoid
 WHERE NOT t.tgisinternal
   AND n.nspname = 'public'
 ORDER BY c.relname, t.tgname;
