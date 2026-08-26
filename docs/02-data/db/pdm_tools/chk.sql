COPY (
SELECT t.relname AS table_name,
       c.conname AS constraint_name,
       COALESCE((SELECT string_agg(a.attname, '+' ORDER BY a.attnum)
                   FROM unnest(c.conkey) AS k(attnum)
                   JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum),
                '(nhieu cot / bieu thuc)') AS columns,
       CASE WHEN COALESCE(array_length(c.conkey,1),0) > 1
            THEN 'BAT BIEN NHIEU COT' ELSE 'mot cot' END AS scope,
       pg_get_constraintdef(c.oid) AS rule
  FROM pg_constraint c
  JOIN pg_class t     ON t.oid = c.conrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
 WHERE n.nspname='public' AND c.contype='c'
 ORDER BY t.relname, c.conname
) TO STDOUT WITH CSV HEADER;
