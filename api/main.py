from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import singlestoredb
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def get_connection_params() -> dict:
    return {
        "host": _get_env("SINGLESTORE_HOST", "localhost"),
        "port": int(_get_env("SINGLESTORE_PORT", "3306")),
        "user": _get_env("SINGLESTORE_USER", "root"),
        "password": _get_env("SINGLESTORE_PASSWORD", "singlestore"),
        "database": _get_env("SINGLESTORE_DATABASE", "leads_demo"),
    }


@contextmanager
def get_conn():
    params = get_connection_params()
    conn = singlestoredb.connect(**params)
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(query: str, params: tuple | None = None) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
    return rows


def fetch_one(query: str, params: tuple | None = None) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchone()


def execute(query: str, params: tuple | None = None) -> int:
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.rowcount


class LeadCreate(BaseModel):
    lead_id: str
    email: str | None = None
    name: str | None = None
    company: str | None = None
    title: str | None = None
    source: str | None = None
    form_data: dict[str, Any] | None = None


def deterministic_embedding(text: str, dims: int = 1536) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big", signed=False)
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(dims)]


def get_embedding(text: str) -> list[float]:
    openai_api_key = _get_env("OPENAI_API_KEY")
    if not openai_api_key:
        return deterministic_embedding(text)

    client = OpenAI(api_key=openai_api_key)
    response = client.embeddings.create(
        model=_get_env("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        input=text,
    )
    return response.data[0].embedding


app = FastAPI(title="Lead Enrichment API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/leads")
def list_leads(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items = fetch_all(
        "SELECT * FROM lead_current ORDER BY created_at DESC LIMIT %s OFFSET %s",
        (limit, offset),
    )
    total = fetch_one("SELECT COUNT(*) AS total FROM lead_current")
    return {"items": items, "total": total["total"] if total else 0}


@app.get("/leads/{lead_id}")
def get_lead(lead_id: str):
    lead = fetch_one("SELECT * FROM lead_current WHERE lead_id = %s", (lead_id,))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    recommendations = fetch_all(
        "SELECT action_type, action_detail, confidence, rationale, data_sources, created_at "
        "FROM recommendations WHERE lead_id = %s ORDER BY created_at DESC",
        (lead_id,),
    )
    for rec in recommendations:
        rec["action_detail"] = json.loads(rec.get("action_detail") or "{}")
        rec["data_sources"] = json.loads(rec.get("data_sources") or "[]")

    signals = fetch_all(
        "SELECT signal_type, signal_data, score_weight, created_at "
        "FROM intent_signals WHERE lead_id = %s ORDER BY created_at DESC",
        (lead_id,),
    )
    for signal in signals:
        signal["signal_data"] = json.loads(signal.get("signal_data") or "{}")

    lead["recommendations"] = recommendations
    lead["signals"] = signals
    return lead


@app.get("/leads/{lead_id}/signals")
def get_signals(lead_id: str, days: int = Query(7, ge=1, le=30)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    signals = fetch_all(
        "SELECT * FROM intent_signals WHERE lead_id = %s AND created_at >= %s "
        "ORDER BY created_at DESC",
        (lead_id, since),
    )
    for signal in signals:
        signal["signal_data"] = json.loads(signal.get("signal_data") or "{}")
    return {"items": signals}


@app.get("/leads/{lead_id}/similar")
def get_similar(lead_id: str, limit: int = Query(5, ge=1, le=20)):
    lead = fetch_one("SELECT * FROM lead_current WHERE lead_id = %s", (lead_id,))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead_text = " ".join(
        filter(None, [lead.get("name"), lead.get("title"), lead.get("company")])
    )
    embedding = get_embedding(lead_text)

    query = (
        "SELECT entity_id, entity_type, content_text, metadata, "
        "DOT_PRODUCT(embedding, %s) AS score "
        "FROM account_memory ORDER BY score DESC LIMIT %s"
    )
    with get_conn() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (embedding, limit))
            results = cursor.fetchall()
    for row in results:
        row["metadata"] = json.loads(row.get("metadata") or "{}")
    return {"items": results}


@app.post("/leads")
def create_lead(payload: LeadCreate):
    raw_payload = payload.model_dump()
    execute(
        "INSERT INTO raw_leads (lead_id, email, name, company, title, source, form_data, raw_payload) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            payload.lead_id,
            payload.email,
            payload.name,
            payload.company,
            payload.title,
            payload.source,
            json.dumps(payload.form_data or {}),
            json.dumps(raw_payload),
        ),
    )
    return {"status": "created", "lead_id": payload.lead_id}


@app.get("/stats")
def get_stats():
    totals = fetch_one("SELECT COUNT(*) AS total FROM lead_current") or {"total": 0}
    averages = fetch_one(
        "SELECT AVG(fit_score) AS avg_fit, AVG(intent_score) AS avg_intent "
        "FROM lead_current"
    ) or {"avg_fit": 0, "avg_intent": 0}
    today = fetch_one(
        "SELECT COUNT(*) AS leads_today FROM lead_current "
        "WHERE created_at >= DATE(NOW())"
    ) or {"leads_today": 0}

    breakdown = fetch_all(
        "SELECT action_type, COUNT(*) AS count FROM recommendations "
        "GROUP BY action_type ORDER BY count DESC"
    )

    return {
        "total_leads": totals.get("total", 0),
        "avg_fit_score": float(averages.get("avg_fit") or 0),
        "avg_intent_score": float(averages.get("avg_intent") or 0),
        "leads_today": today.get("leads_today", 0),
        "action_breakdown": breakdown,
    }


async def _poll_leads():
    items = fetch_all(
        "SELECT * FROM lead_current ORDER BY updated_at DESC LIMIT 50"
    )
    return items


@app.websocket("/ws/leads")
async def ws_leads(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            items = await _poll_leads()
            await websocket.send_json({"type": "leads_update", "items": items})
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
