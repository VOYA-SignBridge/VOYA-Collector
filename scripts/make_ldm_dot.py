"""Generate the Logical Data Model (crow's-foot ERD) straight from the live database.

Reads the schema out of the running PostgreSQL container -- information_schema for
columns and types, pg_constraint for primary, unique and foreign keys -- and emits a
Graphviz .dot file in which every table is a ruled grid and every connector is anchored
to the exact column row it belongs to (Graphviz HTML-label PORTs).

Undeclared logical relations are listed explicitly below: they carry no FK constraint in
PostgreSQL, so they are drawn dashed. They are NOT inferred by name matching, because
inferring them would misrepresent the schema as enforcing something it does not.

Usage:  python scripts/make_ldm_dot.py [-o reports/fig_ldm.dot]
Then:   dot -Tsvg reports/fig_ldm.dot -o reports/fig_ldm_graphviz.svg
"""
import argparse
import html
import subprocess
import sys

CONTAINER = "voya_postgres"

Q_COLUMNS = """
SELECT c.table_name, c.column_name, c.data_type,
       coalesce(c.character_maximum_length::text, ''), c.is_nullable
FROM information_schema.columns c
JOIN information_schema.tables t
  ON t.table_name = c.table_name AND t.table_schema = c.table_schema
WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
ORDER BY c.table_name, c.ordinal_position;
"""

Q_KEYS = """
SELECT 'PK', tc.table_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON kcu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public'
UNION ALL
SELECT 'UQ', tc.table_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON kcu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = 'public';
"""

Q_FKEYS = """
SELECT con.conrelid::regclass::text,
       (SELECT string_agg(a.attname, ',') FROM unnest(con.conkey) k
          JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k),
       con.confrelid::regclass::text,
       (SELECT string_agg(a.attname, ',') FROM unnest(con.confkey) k
          JOIN pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k),
       con.confdeltype
FROM pg_constraint con WHERE con.contype = 'f';
"""

# Relations the application maintains but the schema does not declare.
# (child_table, child_column, parent_table, parent_column, parent_is_mandatory)
LOGICAL_RELATIONS = [
    ("samples", "class_uid", "classes", "class_uid", False),
    ("samples", "signer_id", "signers", "signer_id", False),
    ("raw_uploads", "class_uid", "classes", "class_uid", False),
    ("training_metrics", "job_id", "training_jobs", "job_id", True),
]

TYPE_ABBREV = {
    "character varying": "VARCHAR",
    "timestamp with time zone": "TIMESTAMPTZ",
    "double precision": "FLOAT8",
}

# Crow's-foot arrow primitives. In Graphviz a composed arrow is read from the
# node outwards, so the first primitive is the one touching the entity.
MANY_OPTIONAL = "crowodot"   # o{  zero or many
ONE_MANDATORY = "teetee"     # ||  exactly one
ONE_OPTIONAL = "teeodot"     # |o  zero or one


def psql(sql):
    out = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "bash", "-c",
         'psql -U $POSTGRES_USER -d $POSTGRES_DB -At -F"|"'],
        input=sql, capture_output=True, text=True, encoding="utf-8",
    )
    if out.returncode != 0:
        sys.exit("psql failed: " + (out.stderr or "").strip())
    return [ln.split("|") for ln in out.stdout.splitlines() if ln.strip()]


def short_type(data_type, maxlen):
    t = TYPE_ABBREV.get(data_type, data_type.upper())
    return "%s(%s)" % (t, maxlen) if maxlen else t


def build():
    columns, keys, fkeys = psql(Q_COLUMNS), psql(Q_KEYS), psql(Q_FKEYS)

    pk, uq = {}, {}
    for kind, table, col in keys:
        (pk if kind == "PK" else uq).setdefault(table, set()).add(col)

    fk = {}
    fk_edges = []
    for child, child_cols, parent, parent_cols, deltype in fkeys:
        rule = {"c": "cascade", "n": "set null", "a": "no action",
                "r": "restrict", "d": "set default"}.get(deltype, deltype)
        for cc in child_cols.split(","):
            fk.setdefault(child, {})[cc] = rule
        fk_edges.append((child, child_cols, parent, parent_cols, deltype))

    tables = {}
    for table, col, data_type, maxlen, nullable in columns:
        tables.setdefault(table, []).append((col, short_type(data_type, maxlen), nullable))

    L = []
    L.append("digraph ldm {")
    L.append('  graph [rankdir=TB, splines=polyline, nodesep=0.65, ranksep=0.95,')
    L.append('         bgcolor="white", fontname="Times New Roman,", fontsize=13];')
    L.append('  node  [shape=plaintext, fontname="Times New Roman,", fontsize=12];')
    L.append('  edge  [color="#333333", penwidth=1.1, arrowsize=1.0, dir=both];')
    L.append("")

    for table in sorted(tables):
        rows = tables[table]
        L.append('  %s [label=<' % table)
        L.append('    <TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" COLOR="#333333">')
        L.append('      <TR><TD COLSPAN="3" BGCOLOR="#E8E8E8" ALIGN="CENTER">'
                 '<B>%s</B></TD></TR>' % html.escape(table))
        for col, typ, nullable in rows:
            marks = []
            if col in pk.get(table, ()):
                marks.append("PK")
            if col in fk.get(table, {}):
                marks.append("FK %s" % fk[table][col])
            if col in uq.get(table, ()):
                marks.append("UK")
            key = " ".join(marks)
            name = html.escape(col)
            if marks:
                name = "<B>%s</B>" % name
            elif nullable == "NO":
                name = "%s <FONT COLOR=\"#777777\">*</FONT>" % name
            key_cell = ('<FONT COLOR="#555555">%s</FONT>' % key) if key else " "
            L.append(
                '      <TR>'
                '<TD ALIGN="LEFT"><FONT COLOR="#555555">%s</FONT></TD>'
                '<TD PORT="%s" ALIGN="LEFT">%s</TD>'
                '<TD ALIGN="CENTER">%s</TD>'
                '</TR>' % (html.escape(typ), html.escape(col), name, key_cell)
            )
        L.append("    </TABLE>>];")
        L.append("")

    L.append("  // Declared foreign keys, enforced by PostgreSQL")
    for child, child_cols, parent, parent_cols, deltype in sorted(fk_edges):
        cc, pc = child_cols.split(",")[0], parent_cols.split(",")[0]
        mandatory = any(c == cc and n == "NO" for c, _, n in tables[child])
        # Compass points pin each connector to the exact attribute row rather
        # than letting dot pick any side of the table.
        L.append(
            '  %s:%s:w -> %s:%s:w [arrowtail=%s, arrowhead=%s];'
            % (parent, pc, child, cc,
               ONE_MANDATORY if mandatory else ONE_OPTIONAL, MANY_OPTIONAL)
        )

    L.append("")
    L.append("  // Logical relations with no FK constraint in the schema")
    for child, cc, parent, pc, mandatory in LOGICAL_RELATIONS:
        L.append(
            '  %s:%s:w -> %s:%s:w [style=dashed, color="#777777", '
            'arrowtail=%s, arrowhead=%s];'
            % (parent, pc, child, cc,
               ONE_MANDATORY if mandatory else ONE_OPTIONAL, MANY_OPTIONAL)
        )

    L.append("}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="reports/fig_ldm.dot")
    a = ap.parse_args()
    open(a.out, "w", encoding="utf-8", newline="\n").write(build())
    print("wrote", a.out)
