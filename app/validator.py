"""Static SQL validation with sqlglot: syntax, read-only, tables, columns, join relationships."""
import sqlglot
from sqlglot import exp

ROOTS = tuple(getattr(exp, n) for n in ("Select", "Union", "Intersect", "Except") if hasattr(exp, n))
FORBIDDEN = tuple(getattr(exp, n) for n in
                  ("Insert", "Update", "Delete", "Drop", "Alter", "Create", "Command", "TruncateTable", "Merge")
                  if hasattr(exp, n))


def validate(sql: str, schema: dict, fks: set, dialect: str = "sqlite") -> list[str]:
    try:
        stmts = [s for s in sqlglot.parse(sql, read=dialect) if s]
    except sqlglot.errors.SqlglotError as e:
        return [f"Syntax error: {str(e)[:200]}"]
    if len(stmts) != 1:
        return ["Exactly one statement is allowed."]
    tree = stmts[0]
    if not isinstance(tree, ROOTS) or any(tree.find(n) for n in FORBIDDEN):
        return ["Only read-only SELECT queries are allowed."]

    cols_of = {t.lower(): {c.lower() for c in cols} for t, cols in schema.items()}
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    errors, alias = [], {}  # alias -> real table, or None for CTE/subquery (columns unknown)

    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if name in ctes:
            alias[(t.alias or t.name).lower()] = None
        elif name not in cols_of:
            errors.append(f"Unknown table '{t.name}'.")
        else:
            alias[(t.alias or t.name).lower()] = name
    for sq in tree.find_all(exp.Subquery):
        if sq.alias:
            alias[sq.alias.lower()] = None

    out_aliases = {a.alias.lower() for a in tree.find_all(exp.Alias) if a.alias}
    real = [v for v in alias.values() if v]
    opaque = any(v is None for v in alias.values())

    def table_of(col):
        return alias.get(col.table.lower()) if col.table else None

    for col in tree.find_all(exp.Column):
        if isinstance(col.this, exp.Star):
            continue
        name, q = col.name.lower(), col.table.lower()
        if q:
            if q not in alias:
                errors.append(f"Unknown table alias '{col.table}'.")
            elif alias[q] and name not in cols_of[alias[q]]:
                errors.append(f"Column '{col.name}' does not exist in table '{alias[q]}'.")
        elif name not in out_aliases and not opaque and not any(name in cols_of[t] for t in real):
            errors.append(f"Unknown column '{col.name}'.")

    for j in tree.find_all(exp.Join):
        on = j.args.get("on")
        if (j.kind or "").upper() == "CROSS":
            errors.append("CROSS JOIN is not allowed; join tables along their foreign keys.")
            continue
        if on:
            cols = list(on.find_all(exp.Column))
            if cols and all(c.table for c in cols) and len({c.table.lower() for c in cols}) < 2:
                errors.append(f"Join condition '{on.sql()}' does not relate the joined table to any other table.")
        if not on and not j.args.get("using") and (j.side or j.kind) and (j.kind or "").upper() != "CROSS":
            errors.append("JOIN is missing an ON/USING condition.")
        for eq in (on.find_all(exp.EQ) if on else []):
            l, r = eq.left, eq.right
            if isinstance(l, exp.Column) and isinstance(r, exp.Column):
                tl, tr = table_of(l), table_of(r)
                if tl and tr and tl != tr and frozenset({(tl, l.name.lower()), (tr, r.name.lower())}) not in fks:
                    errors.append(f"Join {tl}.{l.name} = {tr}.{r.name} is not a defined relationship.")
    return list(dict.fromkeys(errors))
