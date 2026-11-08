COPY (
SELECT child.relname AS child_table,
       (SELECT string_agg(a.attname, '+' ORDER BY x.ord)
          FROM unnest(con.conkey) WITH ORDINALITY AS x(attnum, ord)
          JOIN pg_attribute a ON a.attrelid=con.conrelid AND a.attnum=x.attnum) AS child_cols,
       parent.relname AS parent_table,
       (SELECT string_agg(a.attname, '+' ORDER BY x.ord)
          FROM unnest(con.confkey) WITH ORDINALITY AS x(attnum, ord)
          JOIN pg_attribute a ON a.attrelid=con.confrelid AND a.attnum=x.attnum) AS parent_cols,
       -- Phia CHA: NOT NULL o moi cot khoa ngoai nghia la con LUON co cha.
       CASE WHEN (SELECT bool_or(NOT a.attnotnull)
                    FROM unnest(con.conkey) AS k(attnum)
                    JOIN pg_attribute a ON a.attrelid=con.conrelid AND a.attnum=k.attnum)
            THEN '0..1' ELSE '1' END AS parent_card,
       -- Phia CON KHONG mac dinh 0..N. Neu bang con co mot khoa duy nhat VO
       -- DIEU KIEN ma tap cot cua no nam gon trong tap cot khoa ngoai, thi moi
       -- hang cha co nhieu nhat MOT hang con: quan he 1-1, khong phai 1-N.
       --
       -- `indpred IS NULL` la dieu kien then chot. Chi muc MOT PHAN chi rang
       -- buoc cac hang thoa vi tu cua no, nen no khong bao dam duoc tinh chat
       -- nay cho ca quan he. He thong nay co 22 chi muc mot phan, nen bo qua
       -- dieu kien do se bien nhieu quan he 1-N thanh 1-1 mot cach im lang.
       CASE WHEN EXISTS (
              SELECT 1 FROM pg_index i
               WHERE i.indrelid = con.conrelid
                 AND i.indisunique AND i.indpred IS NULL
                 AND (SELECT array_agg(x::int) FROM unnest(i.indkey) AS x)
                     <@ (SELECT array_agg(y::int) FROM unnest(con.conkey) AS y)
            ) THEN '0..1' ELSE '0..N' END AS child_card,
       array_length(con.conkey,1) AS n_cols,
       CASE con.confdeltype WHEN 'a' THEN 'NO ACTION' WHEN 'r' THEN 'RESTRICT'
            WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL'
            WHEN 'd' THEN 'SET DEFAULT' END AS on_delete,
       con.conname
  FROM pg_constraint con
  JOIN pg_class child  ON child.oid  = con.conrelid
  JOIN pg_class parent ON parent.oid = con.confrelid
  JOIN pg_namespace n  ON n.oid = child.relnamespace
 WHERE con.contype='f' AND n.nspname='public'
 ORDER BY child.relname, con.conname
) TO STDOUT WITH CSV HEADER;
