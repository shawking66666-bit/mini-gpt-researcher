import json
import sqlite3
from pathlib import Path

from mini_researcher.models import (
    Evidence,
    EvidenceSourceType,
    ResearchPlan,
    ResearchReport,
    ResearchState,
    RetrievalMode,
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
        """新库建 v2；已有 v1 库在同一个事务中保留数据升级。"""

        with self._connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > 2:
                raise ValueError(f"unsupported database schema version: {version}")
            existing = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            if version == 2:
                return
            # sqlite3 的上下文管理器不会自动为 DDL 开始事务；显式 BEGIN 才能回滚迁移中的加列/建表。
            connection.execute("BEGIN IMMEDIATE")
            if version == 0 and not existing:
                connection.execute("""
                    CREATE TABLE research_tasks (
                        task_id TEXT PRIMARY KEY, topic TEXT NOT NULL,
                        status TEXT NOT NULL, created_at TEXT NOT NULL,
                        round_number INTEGER NOT NULL, plan_json TEXT,
                        errors_json TEXT NOT NULL, usage_json TEXT NOT NULL,
                        retrieval_mode TEXT NOT NULL DEFAULT 'web', knowledge_base_id TEXT
                    )
                """)
                connection.execute(self._evidence_schema("evidence"))
                connection.execute("""
                    CREATE TABLE reports (
                        task_id TEXT PRIMARY KEY, title TEXT NOT NULL,
                        markdown TEXT NOT NULL, html TEXT,
                        used_source_ids_json TEXT NOT NULL,
                        FOREIGN KEY (task_id) REFERENCES research_tasks(task_id) ON DELETE CASCADE
                    )
                """)
            elif version == 0 and {"research_tasks", "evidence", "reports"} <= existing:
                connection.execute("ALTER TABLE research_tasks ADD COLUMN retrieval_mode TEXT NOT NULL DEFAULT 'web'")
                connection.execute("ALTER TABLE research_tasks ADD COLUMN knowledge_base_id TEXT")
                # v1 的 url 是 NOT NULL；文档证据允许空 URL，必须重建表而非直接加列。
                connection.execute(self._evidence_schema("evidence_v2"))
                connection.execute("""
                    INSERT INTO evidence_v2 (task_id, source_id, question_id, title,
                        url, content, source_type)
                    SELECT task_id, source_id, question_id, title, url, content, 'web'
                    FROM evidence
                """)
                connection.execute("DROP TABLE evidence")
                connection.execute("ALTER TABLE evidence_v2 RENAME TO evidence")
            else:
                raise ValueError("unsupported or incomplete database schema")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("database migration failed foreign-key validation")
            connection.execute("PRAGMA user_version = 2")

    @staticmethod
    def _evidence_schema(table_name: str) -> str:
        # table_name 只由本类传入固定字面量，不来自用户输入。
        return f"""
            CREATE TABLE {table_name} (
                task_id TEXT NOT NULL, source_id TEXT NOT NULL,
                question_id TEXT NOT NULL, title TEXT NOT NULL,
                url TEXT, content TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'web',
                document_name TEXT, page_number INTEGER, chunk_index INTEGER,
                PRIMARY KEY (task_id, source_id),
                FOREIGN KEY (task_id) REFERENCES research_tasks(task_id) ON DELETE CASCADE
            )
        """

    def save_state(self, state: ResearchState) -> None:
        """在一个事务中保存任务主记录，并替换该任务的Evidence快照。"""

        plan_json = state.plan.model_dump_json() if state.plan is not None else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO research_tasks (
                    task_id, topic, status, created_at, round_number,
                    plan_json, errors_json, usage_json, retrieval_mode, knowledge_base_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    topic = excluded.topic,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    round_number = excluded.round_number,
                    plan_json = excluded.plan_json,
                    errors_json = excluded.errors_json,
                    usage_json = excluded.usage_json,
                    retrieval_mode = excluded.retrieval_mode,
                    knowledge_base_id = excluded.knowledge_base_id
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
                    state.retrieval_mode.value,
                    state.knowledge_base_id,
                ),
            )
            connection.execute(
                "DELETE FROM evidence WHERE task_id = ?",
                (state.task_id,),
            )
            connection.executemany(
                """
                INSERT INTO evidence (
                    task_id, source_id, question_id, title, url, content,
                    source_type, document_name, page_number, chunk_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        state.task_id,
                        item.source_id,
                        item.question_id,
                        item.title,
                        item.url,
                        item.content,
                        item.source_type.value,
                        item.document_name,
                        item.page_number,
                        item.chunk_index,
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
                SELECT source_id, question_id, title, url, content,
                    source_type, document_name, page_number, chunk_index
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
            retrieval_mode=RetrievalMode(task_row["retrieval_mode"]),
            knowledge_base_id=task_row["knowledge_base_id"],
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
