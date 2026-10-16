COPY (
WITH pk AS (
  SELECT c.conrelid, string_agg(a.attname,'+' ORDER BY x.ord) AS cols
    FROM pg_constraint c
    JOIN unnest(c.conkey) WITH ORDINALITY AS x(attnum,ord) ON TRUE
    JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=x.attnum
   WHERE c.contype='p' GROUP BY c.conrelid),
fko AS (SELECT conrelid AS oid, count(*) n FROM pg_constraint WHERE contype='f' GROUP BY 1),
fki AS (SELECT confrelid AS oid, count(*) n FROM pg_constraint WHERE contype='f' GROUP BY 1)
SELECT t.relname AS tbl,
       COALESCE(pk.cols,'(khong co)') AS pk,
       (SELECT count(*) FROM information_schema.columns
         WHERE table_schema='public' AND table_name=t.relname) AS n_cols,
       COALESCE(fko.n,0) AS fk_ra, COALESCE(fki.n,0) AS fk_vao,
       t.relrowsecurity AS rls,
       EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name=t.relname
                  AND column_name='tenant_id') AS co_tenant_id
  FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace
  LEFT JOIN pk  ON pk.conrelid=t.oid
  LEFT JOIN fko ON fko.oid=t.oid
  LEFT JOIN fki ON fki.oid=t.oid
 WHERE n.nspname='public' AND t.relkind='r'
 ORDER BY t.relname
) TO STDOUT WITH CSV HEADER;
