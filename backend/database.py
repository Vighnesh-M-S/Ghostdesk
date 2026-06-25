import sqlite3
import json
from datetime import datetime
from pathlib import Path
import os

DB_PATH = Path(os.getenv("GHOSTDESK_DB_PATH", "ghostdesk.db"))


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            intent TEXT,
            confidence REAL,
            risk_score REAL,
            recommended_action TEXT,
            requires_human_review INTEGER,
            verification_result TEXT,
            risk_flags TEXT,
            resolution_summary TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_result(state: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    final = state.get("final_output") or state
    cursor.execute(
        """
        INSERT INTO processing_history
            (created_at, intent, confidence, risk_score, recommended_action,
             requires_human_review, verification_result, risk_flags, resolution_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.utcnow().isoformat(),
            final.get("intent", ""),
            final.get("intent_confidence", 0.0),
            final.get("risk_score", 0.0),
            final.get("recommended_action", ""),
            1 if final.get("requires_human_review") else 0,
            final.get("verification_result", ""),
            json.dumps(final.get("risk_flags", [])),
            final.get("resolution_summary", ""),
        ),
    )
    conn.commit()
    conn.close()


def get_analytics() -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM processing_history")
    total = cursor.fetchone()[0]

    if total == 0:
        conn.close()
        return _empty_analytics()

    cursor.execute("SELECT COUNT(*) FROM processing_history WHERE requires_human_review = 0")
    automated = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM processing_history WHERE requires_human_review = 1")
    human_review = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(confidence) FROM processing_history")
    avg_confidence = cursor.fetchone()[0] or 0.0

    cursor.execute(
        "SELECT intent, COUNT(*) as cnt FROM processing_history WHERE intent != '' GROUP BY intent ORDER BY cnt DESC"
    )
    intent_dist = dict(cursor.fetchall())

    cursor.execute(
        "SELECT recommended_action, COUNT(*) as cnt FROM processing_history WHERE recommended_action != '' GROUP BY recommended_action ORDER BY cnt DESC"
    )
    action_dist = dict(cursor.fetchall())

    cursor.execute(
        """
        SELECT
            CASE
                WHEN risk_score < 0.3 THEN 'Low'
                WHEN risk_score < 0.7 THEN 'Medium'
                ELSE 'High'
            END as risk_level,
            COUNT(*) as cnt
        FROM processing_history
        GROUP BY risk_level
        """
    )
    risk_dist = dict(cursor.fetchall())

    cursor.execute(
        "SELECT created_at, intent, confidence, risk_score, recommended_action, requires_human_review, verification_result FROM processing_history ORDER BY created_at DESC LIMIT 10"
    )
    recent_rows = cursor.fetchall()
    recent_cols = ["created_at", "intent", "confidence", "risk_score", "recommended_action", "requires_human_review", "verification_result"]
    recent = [dict(zip(recent_cols, row)) for row in recent_rows]

    conn.close()

    return {
        "total_processed": total,
        "automated": automated,
        "human_review": human_review,
        "automation_rate": round((automated / total) * 100, 1) if total else 0,
        "human_review_rate": round((human_review / total) * 100, 1) if total else 0,
        "avg_confidence": round(avg_confidence * 100, 1),
        "intent_distribution": intent_dist,
        "action_distribution": action_dist,
        "risk_distribution": risk_dist,
        "recent": recent,
    }


def get_history(limit: int = 50) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM processing_history ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    cols = [
        "id", "created_at", "intent", "confidence", "risk_score",
        "recommended_action", "requires_human_review", "verification_result",
        "risk_flags", "resolution_summary",
    ]
    return [dict(zip(cols, row)) for row in rows]


def _empty_analytics() -> dict:
    return {
        "total_processed": 0,
        "automated": 0,
        "human_review": 0,
        "automation_rate": 0,
        "human_review_rate": 0,
        "avg_confidence": 0,
        "intent_distribution": {},
        "action_distribution": {},
        "risk_distribution": {},
        "recent": [],
    }
