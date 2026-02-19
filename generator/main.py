from __future__ import annotations

import json
import os
import random
import time
from uuid import uuid4

from faker import Faker
from kafka import KafkaProducer
import singlestoredb

fake = Faker()

company_suffixes = ["Labs", "Systems", "Cloud", "Analytics", "AI", "Software"]
titles = [
    "VP Engineering",
    "Director of Marketing",
    "Head of Sales",
    "CTO",
    "VP Revenue",
    "Product Manager",
]

signal_types = [
    "pricing_page_view",
    "email_open",
    "product_page_view",
    "demo_request",
    "case_study_view",
]


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def get_connection() -> singlestoredb.Connection:
    return singlestoredb.connect(
        host=_get_env("SINGLESTORE_HOST", "localhost"),
        port=int(_get_env("SINGLESTORE_PORT", "3306")),
        user=_get_env("SINGLESTORE_USER", "root"),
        password=_get_env("SINGLESTORE_PASSWORD", "singlestore"),
        database=_get_env("SINGLESTORE_DATABASE", "leads_demo"),
    )


def make_lead() -> dict:
    lead_id = f"lead_{uuid4().hex[:8]}"
    company = f"{fake.company().split(' ')[0]} {random.choice(company_suffixes)}"
    return {
        "lead_id": lead_id,
        "email": fake.company_email(),
        "name": fake.name(),
        "company": company,
        "title": random.choice(titles),
        "source": "demo_generator",
        "form_data": {"message": random.choice(["Interested in enterprise", "Need pricing", "Looking for demo"])},
    }


def make_signals(lead_id: str) -> list[dict]:
    signals = []
    for _ in range(random.randint(1, 4)):
        signal_type = random.choice(signal_types)
        signals.append(
            {
                "lead_id": lead_id,
                "signal_type": signal_type,
                "signal_data": {"path": signal_type, "ts": time.time()},
                "score_weight": round(random.uniform(0.5, 1.5), 2),
            }
        )
    return signals


def insert_signals(conn, signals: list[dict]) -> None:
    query = (
        "INSERT INTO intent_signals (lead_id, signal_type, signal_data, score_weight) "
        "VALUES (%s, %s, %s, %s)"
    )
    with conn.cursor() as cursor:
        cursor.executemany(
            query,
            [
                (
                    signal["lead_id"],
                    signal["signal_type"],
                    json.dumps(signal["signal_data"]),
                    signal["score_weight"],
                )
                for signal in signals
            ],
        )
    conn.commit()


def insert_raw_lead(conn, lead: dict) -> None:
    query = (
        "INSERT INTO raw_leads (lead_id, email, name, company, title, source, form_data, raw_payload) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )
    with conn.cursor() as cursor:
        cursor.execute(
            query,
            (
                lead["lead_id"],
                lead.get("email"),
                lead.get("name"),
                lead.get("company"),
                lead.get("title"),
                lead.get("source"),
                json.dumps(lead.get("form_data") or {}),
                json.dumps(lead),
            ),
        )
    conn.commit()


def main() -> None:
    bootstrap = _get_env("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
    interval = float(_get_env("GENERATOR_INTERVAL_SECONDS", "4"))
    write_db = (_get_env("GENERATOR_DB_WRITE", "true") or "true").lower() == "true"
    producer = KafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
    )

    conn = get_connection()

    while True:
        lead = make_lead()
        producer.send("inbound-leads", lead)
        producer.flush()

        if write_db:
            insert_raw_lead(conn, lead)

        signals = make_signals(lead["lead_id"])
        insert_signals(conn, signals)

        print(f"generated lead {lead['lead_id']}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
