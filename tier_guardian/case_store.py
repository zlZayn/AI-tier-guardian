"""相似案例存储 — 基于 SQLite，按 violation type 匹配。

每次审核产生 BLOCK 或 HUMAN_REVIEW 决策时自动入库。
下次判到 HUMAN_REVIEW 时按违规类型召回最近案例供审核员参考。
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from tier_guardian.models import SimilarCase, TaskContext


class CaseStore:
    def __init__(self, db_path: str = ".cache/cases.db") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                violation_type TEXT,
                severity TEXT,
                final_decision TEXT NOT NULL,
                reasoning_summary TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def save(self, ctx: TaskContext) -> None:
        judge = ctx.nodes.judge
        if judge is None:
            return
        v = judge.violation
        self._conn.execute(
            "INSERT OR REPLACE INTO cases VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                ctx.task_id,
                ctx.text[:200],
                v.type,
                v.severity.value if v.severity else None,
                ctx.final_decision.value if ctx.final_decision else None,
                judge.reasoning_summary,
                ctx.created_at,
            ),
        )
        self._conn.commit()

    def find_similar(
        self, violation_type: Optional[str], limit: int = 5
    ) -> list[SimilarCase]:
        if not violation_type:
            return []
        cursor = self._conn.execute(
            "SELECT id, final_decision, reasoning_summary FROM cases "
            "WHERE violation_type = ? ORDER BY created_at DESC LIMIT ?",
            (violation_type, limit),
        )
        return [
            SimilarCase(case_id=row[0], resolution=row[1] or "", summary=row[2] or "")
            for row in cursor.fetchall()
        ]

    def close(self) -> None:
        self._conn.close()
