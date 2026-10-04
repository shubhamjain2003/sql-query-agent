import operator, os, re
from typing import Annotated, Literal, TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from . import db, prompts, validator

MAX_ATTEMPTS = 3
DESTRUCTIVE = re.compile(
    r"\b(delete\s+from|drop\s+(table|database|index|view)|truncate|update\s+\w+\s+set|insert\s+into|alter\s+table)\b", re.I)


class Intent(BaseModel):
    intent: Literal["generate", "optimize", "debug", "explain", "destructive", "out_of_scope", "clarify"]
    clarification: str  # empty string unless intent is clarify


class SQLOut(BaseModel):
    sql: str


class Review(BaseModel):
    explanation: str
    issues: list[str]
    suggestions: list[str]


class State(TypedDict, total=False):
    user_input: str
    dialect: str
    history: Annotated[list[str], operator.add]  # persists across turns (conversation context)
    last_sql: str                                # persists: follow-ups modify this
    intent: str
    clarification: str
    sql: str
    errors: list[str]
    attempts: int
    columns: list
    rows: list
    exec_error: str
    explanation: str
    issues: list[str]
    suggestions: list[str]
    reply: str


def _llm():
    return ChatGoogleGenerativeAI(model=os.getenv("MODEL", "gemini-2.5-flash"), temperature=0)


def _hist(s):
    return "\n".join(s.get("history", [])[-12:]) or "(none)"


def _user_msg(s):
    return f"Conversation so far:\n{_hist(s)}\n\n<user_request>\n{s['user_input']}\n</user_request>"


def classify(s: State):
    if DESTRUCTIVE.search(s["user_input"]):  # deterministic guard before any LLM call
        return {"intent": "destructive"}
    sys = prompts.CLASSIFY.format(schema=db.schema_text(), last_sql=s.get("last_sql") or "none")
    out = _llm().with_structured_output(Intent).invoke([("system", sys), ("human", _user_msg(s))])
    return {"intent": out.intent, "clarification": out.clarification}


def refuse(s: State):
    reply = prompts.REFUSALS.get(s["intent"]) or s.get("clarification") or "Could you clarify your request?"
    return {"reply": reply, "history": [f"User: {s['user_input']}", f"Assistant: {reply}"]}


def write_sql(s: State):
    fb = ""
    if s.get("errors"):
        fb = f"Your previous attempt:\n{s['sql']}\nfailed validation:\n- " + "\n- ".join(s["errors"]) + "\nFix these."
    sys = prompts.WRITE.format(schema=db.schema_text(), dialect=s["dialect"], task=prompts.TASKS[s["intent"]],
                               last_sql=s.get("last_sql") or "none", feedback=fb)
    out = _llm().with_structured_output(SQLOut).invoke([("system", sys), ("human", _user_msg(s))])
    return {"sql": out.sql.strip().rstrip(";") + ";"}


def validate(s: State):
    errs = validator.validate(s["sql"], db.get_schema(), db.get_fks(), s["dialect"])
    if not errs and s["dialect"] == "sqlite":
        try:
            db.explain(s["sql"])
        except Exception as e:
            errs = [f"SQLite rejected the query: {e}"]
    return {"errors": errs, "attempts": s.get("attempts", 0) + 1}


def after_validate(s: State):
    if not s["errors"]:
        return "execute"
    return "write_sql" if s["attempts"] < MAX_ATTEMPTS else "fail"


def fail(s: State):
    reply = "I couldn't produce a query that passes validation: " + "; ".join(s["errors"]) + \
            ". Try rephrasing or naming the tables you mean."
    return {"sql": "", "reply": reply, "history": [f"User: {s['user_input']}", f"Assistant: {reply}"]}


def execute(s: State):
    if s["dialect"] != "sqlite":  # sample DB is SQLite; other dialects are generate/validate only
        return {}
    try:
        cols, rows = db.run_query(s["sql"])
        return {"columns": cols, "rows": rows}
    except Exception as e:
        return {"exec_error": str(e)}


def review(s: State):
    sys = prompts.REVIEW.format(schema=db.schema_text(), dialect=s["dialect"], intent=s["intent"], sql=s["sql"])
    out = _llm().with_structured_output(Review).invoke([("system", sys), ("human", _user_msg(s))])
    return {"explanation": out.explanation, "issues": out.issues, "suggestions": out.suggestions,
            "reply": out.explanation, "last_sql": s["sql"],
            "history": [f"User: {s['user_input']}", f"Assistant SQL: {s['sql']}"]}


b = StateGraph(State)
for name, fn in [("classify", classify), ("refuse", refuse), ("write_sql", write_sql), ("validate", validate),
                 ("fail", fail), ("execute", execute), ("review", review)]:
    b.add_node(name, fn)
b.add_edge(START, "classify")
b.add_conditional_edges("classify", lambda s: "refuse" if s["intent"] in ("destructive", "out_of_scope", "clarify")
                        else "write_sql", ["refuse", "write_sql"])
b.add_edge("write_sql", "validate")
b.add_conditional_edges("validate", after_validate, ["execute", "write_sql", "fail"])
b.add_edge("execute", "review")
for n in ("refuse", "fail", "review"):
    b.add_edge(n, END)
graph = b.compile(checkpointer=MemorySaver())


def run(session_id: str, message: str, dialect: str = "sqlite") -> dict:
    fresh = {"user_input": message, "dialect": dialect, "intent": "", "clarification": "", "sql": "", "errors": [],
             "attempts": 0, "columns": [], "rows": [], "exec_error": "", "explanation": "", "issues": [],
             "suggestions": [], "reply": ""}  # per-turn reset; history and last_sql persist via the checkpointer
    return graph.invoke(fresh, {"configurable": {"thread_id": session_id}})
