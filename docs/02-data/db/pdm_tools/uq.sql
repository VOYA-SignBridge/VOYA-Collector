COPY (
SELECT t.relname AS table_name,
       COALESCE(c.conname, i.relname) AS object_name,
       CASE WHEN c.contype='p' THEN 'PRIMARY KEY'
            WHEN c.contype='u' THEN 'UNIQUE CONSTRAINT'
            WHEN idx.indpred IS NOT NULL THEN 'UNIQUE INDEX (MOT PHAN)'
            ELSE 'UNIQUE INDEX' END AS kind,
       (SELECT string_agg(a.attname, '+' ORDER BY x.ord)
          FROM unnest(idx.indkey::int[]) WITH ORDINALITY AS x(attnum, ord)
          JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=x.attnum) AS columns,
       COALESCE(pg_get_expr(idx.indpred, idx.indrelid), '') AS predicate
  FROM pg_index idx
  JOIN pg_class i     ON i.oid = idx.indexrelid
  JOIN pg_class t     ON t.oid = idx.indrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
  LEFT JOIN pg_constraint c ON c.conindid = idx.indexrelid AND c.contype IN ('p','u')
 WHERE n.nspname='public' AND t.relkind='r' AND idx.indisunique
 ORDER BY t.relname, kind, object_name
) TO STDOUT WITH CSV HEADER;
