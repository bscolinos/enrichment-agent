from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from openai import OpenAI
import singlestoredb


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def build_enrichment_prompt(lead: dict, signals: list[dict], similar: list[dict]) -> str:
    lead_block = json.dumps(lead, indent=2)
    signals_block = json.dumps(signals, indent=2)
    similar_block = json.dumps(similar, indent=2)

    return (
        "You are a lead enrichment agent.\n"
        "Use the provided lead data, intent signals, and similar account context.\n"
        "Return a single JSON object with these fields:\n"
        "normalized_company, industry, company_size, region, fit_score, intent_score, "
        "recommended_action, confidence, rationale, data_sources.\n"
        "fit_score and intent_score must be 0-100.\n"
        "rationale must cite specific data points, including signal counts or timestamps.\n"
        "data_sources must be an array of short strings describing the signals and context used.\n\n"
        f"lead:\n{lead_block}\n\n"
        f"signals:\n{signals_block}\n\n"
        f"similar_accounts:\n{similar_block}\n"
    )


def _safe_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def get_embedding(text: str) -> list[float]:
    openai_api_key = _get_env("OPENAI_API_KEY")

    client = OpenAI(api_key=openai_api_key)
    response = client.embeddings.create(
        model=_get_env("openai_embedding_model", "text-embedding-3-small"),
        input=text,
    )
    return response.data[0].embedding


def vector_search_similar(conn, embedding: list[float], limit: int = 5) -> list[dict]:
    query = (
        "SELECT entity_id, entity_type, content_text, metadata, "
        "DOT_PRODUCT(embedding, %s) AS score "
        "FROM account_memory "
        "ORDER BY score DESC "
        "LIMIT %s"
    )
    with conn.cursor(dictionary=True) as cursor:
        cursor.execute(query, (embedding, limit))
        return cursor.fetchall()


def _heuristic_enrichment(lead: dict, signals: list[dict]) -> dict:
    company = lead.get("company") or ""
    normalized_company = company.strip().title() if company else None
    title = (lead.get("title") or "").lower()

    industry = "software"
    if any(word in title for word in ["finance", "cfo", "accounting"]):
        industry = "finance"
    if any(word in title for word in ["marketing", "growth", "demand"]):
        industry = "marketing"

    signal_types = [signal.get("signal_type", "") for signal in signals]
    pricing_visits = sum(1 for signal in signal_types if "pricing" in signal)
    email_opens = sum(1 for signal in signal_types if "email" in signal)
    page_views = sum(1 for signal in signal_types if "page" in signal)

    intent_score = min(100, 25 + pricing_visits * 20 + email_opens * 10 + page_views * 5)
    fit_score = min(100, 50 + (10 if "vp" in title or "director" in title else 0))

    action = "email_followup" if intent_score >= 60 else "nurture_sequence"
    confidence = 0.65 if pricing_visits else 0.5

    rationale = (
        f"Intent score based on {pricing_visits} pricing visits, "
        f"{email_opens} email opens, {page_views} page views in last 7 days."
    )
    data_sources = [
        f"pricing_visits:{pricing_visits}",
        f"email_opens:{email_opens}",
        f"page_views:{page_views}",
    ]

    return {
        "normalized_company": normalized_company,
        "industry": industry,
        "company_size": "enterprise" if "vp" in title else "mid-market",
        "region": lead.get("region") or "unknown",
        "fit_score": float(fit_score),
        "intent_score": float(intent_score),
        "recommended_action": action,
        "confidence": float(confidence),
        "rationale": rationale,
        "data_sources": data_sources,
    }


def enrich_lead(lead: dict, signals: list[dict], similar: list[dict]) -> dict[str, Any]:
    openai_api_key = _get_env("OPENAI_API_KEY")
    if not openai_api_key:
        return _heuristic_enrichment(lead, signals)

    client = OpenAI(api_key=openai_api_key)
    prompt = build_enrichment_prompt(lead, signals, similar)
    response = client.chat.completions.create(
        model=_get_env("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "You are a precise data enrichment agent."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    content = response.choices[0].message.content or "{}"
    data = _safe_json(content)
    data.setdefault("enriched_at", datetime.now(timezone.utc).isoformat())
    return data


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


def execute(query: str, params: tuple | None = None) -> int:
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.rowcount


def fetch_new_leads(limit: int = 25) -> list[dict]:
    query = (
        "SELECT * FROM lead_current "
        "WHERE status = 'new' OR enriched_at IS NULL "
        "ORDER BY created_at ASC "
        "LIMIT %s"
    )
    return fetch_all(query, (limit,))


def fetch_intent_signals(lead_id: str, days: int = 7) -> list[dict]:
    query = (
        "SELECT * FROM intent_signals "
        "WHERE lead_id = %s AND created_at >= %s "
        "ORDER BY created_at DESC"
    )
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return fetch_all(query, (lead_id, since))


def upsert_enriched_lead(lead_id: str, data: dict) -> None:
    query = (
        "UPDATE lead_current SET "
        "normalized_company = %s, industry = %s, company_size = %s, region = %s, "
        "fit_score = %s, intent_score = %s, status = %s, enriched_at = NOW() "
        "WHERE lead_id = %s"
    )
    params = (
        data.get("normalized_company"),
        data.get("industry"),
        data.get("company_size"),
        data.get("region"),
        data.get("fit_score"),
        data.get("intent_score"),
        "enriched",
        lead_id,
    )
    execute(query, params)


def insert_recommendation(lead_id: str, data: dict) -> None:
    query = (
        "INSERT INTO recommendations (lead_id, action_type, action_detail, confidence, "
        "rationale, data_sources) VALUES (%s, %s, %s, %s, %s, %s)"
    )
    action_type = data.get("recommended_action")
    action_detail = json.dumps({"recommended_action": action_type})
    confidence = data.get("confidence")
    rationale = data.get("rationale")
    data_sources = json.dumps(data.get("data_sources", []))
    execute(query, (lead_id, action_type, action_detail, confidence, rationale, data_sources))


def mark_enriching(lead_id: str) -> None:
    execute("UPDATE lead_current SET status = 'enriching' WHERE lead_id = %s", (lead_id,))


def log_account_memory(lead: dict, embedding: list[float]) -> None:
    query = (
        "INSERT INTO account_memory (entity_type, entity_id, content_type, content_text, embedding, metadata) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )
    content_text = " ".join(
        filter(None, [lead.get("name"), lead.get("title"), lead.get("company")])
    )
    metadata = json.dumps({"source": lead.get("source", "unknown")})
    execute(
        query,
        (
            "lead",
            lead.get("lead_id"),
            "profile",
            content_text,
            embedding,
            metadata,
        ),
    )


def process_lead(lead: dict) -> None:
    lead_id = lead.get("lead_id")
    if not lead_id:
        return

    mark_enriching(lead_id)

    signals = fetch_intent_signals(lead_id)
    lead_text = " ".join(
        filter(None, [lead.get("name"), lead.get("title"), lead.get("company")])
    )
    embedding = get_embedding(lead_text)

    with get_conn() as conn:
        similar = vector_search_similar(conn, embedding, limit=5)

    enrichment = enrich_lead(lead, signals, similar)

    upsert_enriched_lead(lead_id, enrichment)
    insert_recommendation(lead_id, enrichment)
    log_account_memory(lead, embedding)


def main() -> None:
    poll_interval = float(_get_env("POLL_INTERVAL_SECONDS", "5"))
    while True:
        leads = fetch_new_leads()
        for lead in leads:
            try:
                process_lead(lead)
            except Exception as exc:  # noqa: BLE001
                print(f"agent error for lead {lead.get('lead_id')}: {exc}")
        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
