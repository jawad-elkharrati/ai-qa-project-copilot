import sqlite3
from contextlib import closing

from alembic.config import Config

from alembic import command


def alembic_config(database_path) -> Config:
    config = Config("alembic.ini")
    url = database_path.resolve().as_posix()
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{url}")
    return config


def test_migrations_create_snapshot_and_contribution_schema(tmp_path) -> None:
    database_path = tmp_path / "fresh.db"
    config = alembic_config(database_path)

    command.upgrade(config, "head")

    with closing(sqlite3.connect(database_path)) as connection:
        revision = connection.execute("select version_num from alembic_version").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute("select name from sqlite_master where type='table'")
        }
        snapshot_columns = {
            row[1] for row in connection.execute("pragma table_info(risk_analyses)")
        }
    assert revision == "20260724_0006"
    assert {"risk_contributions", "risk_evidence", "risk_decisions"} <= tables
    assert {
        "policy_hash",
        "input_fingerprint",
        "result_fingerprint",
        "previous_snapshot_id",
        "confidence_score",
        "confidence_details",
        "missing_information",
    } <= snapshot_columns


def test_migration_upgrades_existing_qa_analysis_schema(tmp_path) -> None:
    database_path = tmp_path / "upgrade.db"
    config = alembic_config(database_path)
    command.upgrade(config, "20260718_0003")

    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            """
            insert into projects(id,key,name,description,created_at)
            values ('PRJ-LEGACY','LEGACY','Legacy','Legacy snapshot','2026-07-13')
            """
        )
        connection.execute(
            """
            insert into risk_analyses(
                id,project_id,sprint_id,ruleset_version,reference_date,score,severity,
                breakdown,finding_count,agent_name,analyzed_at
            ) values (
                'QAA-LEGACY','PRJ-LEGACY',null,'qa-rules-v1.0','2026-07-13',
                25,'medium','[]',1,'qa-agent-v1','2026-07-13'
            )
            """
        )
        connection.commit()

    command.upgrade(config, "head")

    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            select score,policy_hash,input_fingerprint,confidence_score
            from risk_analyses where id='QAA-LEGACY'
            """
        ).fetchone()
    assert row == (25.0, "legacy", "legacy", 1.0)


def test_human_decision_migration_downgrades_and_upgrades(tmp_path) -> None:
    database_path = tmp_path / "decision-cycle.db"
    config = alembic_config(database_path)
    command.upgrade(config, "head")

    with closing(sqlite3.connect(database_path)) as connection:
        tables = {
            row[0]
            for row in connection.execute("select name from sqlite_master where type='table'")
        }
        indexes = {row[1] for row in connection.execute("pragma index_list(risk_decisions)")}
    assert "risk_decisions" in tables
    assert "ix_risk_decisions_risk_created" in indexes

    command.downgrade(config, "20260723_0005")
    with closing(sqlite3.connect(database_path)) as connection:
        table = connection.execute(
            "select name from sqlite_master where type='table' and name='risk_decisions'"
        ).fetchone()
    assert table is None

    command.upgrade(config, "head")
    with closing(sqlite3.connect(database_path)) as connection:
        revision = connection.execute("select version_num from alembic_version").fetchone()[0]
    assert revision == "20260724_0006"
