COPY (
WITH pk AS (
  SELECT c.conrelid, a.attname FROM pg_constraint c
    JOIN unnest(c.conkey) AS k(attnum) ON TRUE
    JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum
   WHERE c.contype='p'),
fkcol AS (
  SELECT c.conrelid, a.attname FROM pg_constraint c
    JOIN unnest(c.conkey) AS k(attnum) ON TRUE
    JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum
   WHERE c.contype='f')
SELECT t.relname                             AS table_name,
       a.attnum                              AS ordinal,
       a.attname                             AS column_name,
       format_type(a.atttypid, a.atttypmod)  AS data_type,
       CASE WHEN a.attnotnull THEN 'NO' ELSE 'YES' END AS nullable,
       COALESCE(pg_get_expr(ad.adbin, ad.adrelid), '') AS column_default,
       CASE WHEN EXISTS (SELECT 1 FROM pk WHERE pk.conrelid=t.oid AND pk.attname=a.attname)
            THEN 'PK' ELSE '' END            AS is_pk,
       CASE WHEN EXISTS (SELECT 1 FROM fkcol WHERE fkcol.conrelid=t.oid AND fkcol.attname=a.attname)
            THEN 'FK' ELSE '' END            AS is_fk,
       CASE a.attidentity WHEN 'a' THEN 'ALWAYS' WHEN 'd' THEN 'BY DEFAULT' ELSE '' END AS identity,
       CASE a.attgenerated WHEN 's' THEN 'STORED' ELSE '' END AS generated,
       ''                                    AS description
  FROM pg_attribute a
  JOIN pg_class t     ON t.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
  LEFT JOIN pg_attrdef ad ON ad.adrelid=a.attrelid AND ad.adnum=a.attnum
 WHERE n.nspname='public' AND t.relkind='r'
   AND a.attnum > 0 AND NOT a.attisdropped
 ORDER BY t.relname, a.attnum
) TO STDOUT WITH CSV HEADER;
