import json
import sqlite3
from pathlib import Path

from mini_researcher.models import (
    Evidence,
    ResearchPlan,
    ResearchReport,
    ResearchState,
    TaskStatus,
    Usage,
)


class ResearchRepository:
    """使用SQLite保存和读取研究任务状态。"""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def _connect(self) -> sqlite3.Connection:
        """每次操作创建短连接，并为该连接启用外键约束。"""

        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        """创建Task 6规定的三张表；重复调用不会覆盖已有数据。"""

        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS research_tasks (
                    task_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    plan_json TEXT,
                    errors_json TEXT NOT NULL,
                    usage_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    task_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    content TEXT NOT NULL,
                    PRIMARY KEY (task_id, source_id),
                    FOREIGN KEY (task_id)
                        REFERENCES research_tasks(task_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS reports (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    html TEXT,
                    used_source_ids_json TEXT NOT NULL,
                    FOREIGN KEY (task_id)
                        REFERENCES research_tasks(task_id)
                        ON DELETE CASCADE
                );
                """
            )

    def save_state(self, state: ResearchState) -> None:
        """在一个事务中保存任务主记录，并替换该任务的Evidence快照。"""

        plan_json = state.plan.model_dump_json() if state.plan is not None else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO research_tasks (
                    task_id, topic, status, created_at, round_number,
                    plan_json, errors_json, usage_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    topic = excluded.topic,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    round_number = excluded.round_number,
                    plan_json = excluded.plan_json,
                    errors_json = excluded.errors_json,
                    usage_json = excluded.usage_json
                """,
                (
                    state.task_id,
                    state.topic,
                    state.status.value,
                    state.created_at.isoformat(),
                    state.round_number,
                    plan_json,
                    json.dumps(state.errors),
                    state.usage.model_dump_json(),
                ),
            )
            connection.execute(
                "DELETE FROM evidence WHERE task_id = ?",
                (state.task_id,),
            )
            connection.executemany(
                """
                INSERT INTO evidence (
                    task_id, source_id, question_id, title, url, content
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        state.task_id,
                        item.source_id,
                        item.question_id,
                        item.title,
                        item.url,
                        item.content,
                    )
                    for item in state.evidence
                ],
            )
            # 状态与报告在同一事务中提交，避免“已完成但报告缺失”的中间状态。
            if state.report is not None:
                self._save_report_row(connection, state.task_id, state.report)
            else:
                connection.execute(
                    "DELETE FROM reports WHERE task_id = ?",
                    (state.task_id,),
                )

    def save_report(self, task_id: str, report: ResearchReport) -> None:
        """保存任务的最终报告；同一任务再次保存时覆盖旧报告。"""

        with self._connect() as connection:
            self._save_report_row(connection, task_id, report)

    @staticmethod
    def _save_report_row(
        connection: sqlite3.Connection,
        task_id: str,
        report: ResearchReport,
    ) -> None:
        connection.execute(
            """
            INSERT INTO reports (
                task_id, title, markdown, html, used_source_ids_json
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                title = excluded.title,
                markdown = excluded.markdown,
                html = excluded.html,
                used_source_ids_json = excluded.used_source_ids_json
            """,
            (
                task_id,
                report.title,
                report.markdown,
                report.html,
                json.dumps(report.used_source_ids),
            ),
        )

    def get_task(self, task_id: str) -> ResearchState | None:
        """按任务ID读取主记录、Evidence和可选报告，再还原为ResearchState。"""

        with self._connect() as connection:
            task_row = connection.execute(
                "SELECT * FROM research_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if task_row is None:
                return None

            evidence_rows = connection.execute(
                """
                SELECT source_id, question_id, title, url, content
                FROM evidence
                WHERE task_id = ?
                ORDER BY rowid
                """,
                (task_id,),
            ).fetchall()
            report_row = connection.execute(
                "SELECT * FROM reports WHERE task_id = ?",
                (task_id,),
            ).fetchone()

        plan = (
            ResearchPlan.model_validate_json(task_row["plan_json"])
            if task_row["plan_json"] is not None
            else None
        )
        report = (
            ResearchReport(
                title=report_row["title"],
                markdown=report_row["markdown"],
                html=report_row["html"],
                used_source_ids=json.loads(report_row["used_source_ids_json"]),
            )
            if report_row is not None
            else None
        )
        return ResearchState(
            task_id=task_row["task_id"],
            topic=task_row["topic"],
            status=TaskStatus(task_row["status"]),
            created_at=task_row["created_at"],
            round_number=task_row["round_number"],
            plan=plan,
            evidence=[Evidence.model_validate(dict(row)) for row in evidence_rows],
            errors=json.loads(task_row["errors_json"]),
            usage=Usage.model_validate_json(task_row["usage_json"]),
            report=report,
        )

    def list_tasks(self) -> list[ResearchState]:
        """列出已保存任务，并为每一项还原完整ResearchState。"""

        with self._connect() as connection:
            task_ids = [
                row["task_id"]
                for row in connection.execute(
                    """
                    SELECT task_id
                    FROM research_tasks
                    ORDER BY created_at DESC, task_id DESC
                    """
                ).fetchall()
            ]

        tasks: list[ResearchState] = []
        for task_id in task_ids:
            state = self.get_task(task_id)
            if state is not None:
                tasks.append(state)
        return tasks
