"""Text-to-SQL for the structured search path, and the guard around it.

An LLM writes the SELECT, so nothing it produces is trusted. Every statement
must pass `validate_sql` before it reaches the database: SELECT only, one
statement, no comments, no DDL/DML verbs, `v_search` as the sole relation, and
a LIMIT the caller cannot raise.

Validation is a whitelist over a very narrow surface, not a general-purpose SQL
sanitiser. It is only safe because the one legal shape is
"SELECT ... FROM v_search ..." — do not widen it without rethinking this.
"""
import logging
import re
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.llm.client import generate_json
from app.llm.prompts import TEXT_TO_SQL_PROMPT

logger = logging.getLogger(__name__)

MAX_ROWS = 50
ALLOWED_RELATIONS = {"v_search"}

# Anything that writes, changes structure, or reaches outside the view.
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|attach|"
    r"detach|pragma|vacuum|copy|merge|call|execute|exec|commit|rollback|"
    r"savepoint|reindex|into|load_extension)\b",
    re.IGNORECASE,
)
_RELATION = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)
_LIMIT = re.compile(r"\blimit\s+(\d+)", re.IGNORECASE)


class UnsafeSQL(ValueError):
    """The generated SQL failed validation and was not executed."""


def validate_sql(raw: str) -> str:
    """Return an executable statement, or raise UnsafeSQL.

    Also normalises: strips one trailing semicolon and forces LIMIT <= MAX_ROWS.
    """
    sql = (raw or "").strip()
    if not sql:
        raise UnsafeSQL("Gemini returned an empty statement")

    # Comments could hide a second statement from the checks below.
    if "--" in sql or "/*" in sql:
        raise UnsafeSQL("SQL comments are not allowed")

    sql = sql.rstrip(";").strip()
    if ";" in sql:
        raise UnsafeSQL("only a single statement is allowed")

    # Plain SELECT only. WITH is deliberately not allowed: a CTE introduces an
    # alias the relation allowlist below would have to learn about, and none of
    # these questions need one. A narrow guard beats a clever one.
    if not re.match(r"^select\s", sql, re.IGNORECASE):
        raise UnsafeSQL("statement must start with SELECT")

    forbidden = _FORBIDDEN.search(sql)
    if forbidden:
        raise UnsafeSQL(f"forbidden keyword '{forbidden.group(1).upper()}'")

    relations = {name.lower() for name in _RELATION.findall(sql)}
    illegal = relations - ALLOWED_RELATIONS
    if illegal:
        raise UnsafeSQL(
            f"only v_search may be queried, not {', '.join(sorted(illegal))}"
        )
    if not relations:
        raise UnsafeSQL("statement does not read from v_search")

    limit = _LIMIT.search(sql)
    if limit is None:
        sql = f"{sql} LIMIT {MAX_ROWS}"
    elif int(limit.group(1)) > MAX_ROWS:
        sql = _LIMIT.sub(f"LIMIT {MAX_ROWS}", sql, count=1)

    return sql


def generate_sql(question: str, today: date | None = None) -> str:
    """Ask Gemini for a SELECT, then validate it. Raises UnsafeSQL if it fails."""
    result = generate_json(
        TEXT_TO_SQL_PROMPT.format(
            question=question, today=(today or date.today()).isoformat()
        )
    )
    candidate = str(result.get("sql") or "")
    logger.info("text-to-sql %r -> %s", question, candidate)
    return validate_sql(candidate)


def run_sql(db: Session, sql: str) -> list[dict]:
    """Execute a validated statement read-only and return plain dict rows.

    Raises SQLAlchemyError if the database rejects it — validation proves the
    statement is *safe*, not that it is *valid*.
    """
    try:
        rows = db.execute(text(sql)).mappings().all()
    finally:
        # Nothing here should write, but never leave a transaction open on a
        # statement an LLM composed.
        db.rollback()
    return [dict(row) for row in rows]
