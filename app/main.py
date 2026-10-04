from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db

db.init_db()
from . import graph as agent  # noqa: E402  (imported after DB init)

app = FastAPI(title="SQLPilot")


class ChatIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=2000)
    dialect: Literal["sqlite", "postgres", "mysql"] = "sqlite"


@app.post("/api/chat")
def chat(body: ChatIn):
    try:
        out = agent.run(body.session_id, body.message, body.dialect)
    except Exception as e:
        name = type(e).__name__
        if "RateLimit" in name or "ResourceExhausted" in name or "429" in str(e):
            raise HTTPException(429, "Gemini rate limit reached. Wait about a minute and try again.") from e
        raise HTTPException(500, f"The agent failed ({name}). Check the API key and server logs.") from e
    keys = ["intent", "reply", "sql", "explanation", "issues", "suggestions", "columns", "rows", "exec_error"]
    return {k: out.get(k) for k in keys}


@app.get("/api/schema")
def schema():
    return {"schema": db.get_schema()}


app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True), name="static")
