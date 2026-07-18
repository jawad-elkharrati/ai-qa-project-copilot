import argparse
import json
from pathlib import Path

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.dataset import dataset_summary, load_dataset
from app.db import SessionLocal
from app.models import (
    Build,
    Commit,
    IngestionLog,
    Metric,
    Project,
    PullRequest,
    Report,
    Risk,
    Sprint,
    TestResult,
    Ticket,
)
from app.schemas import DemoDataset


def _clear_project(session: Session, project_id: str) -> None:
    session.execute(
        update(IngestionLog).where(IngestionLog.project_id == project_id).values(project_id=None)
    )
    for model in (TestResult, Build, PullRequest, Commit, Risk, Report, Metric, Ticket, Sprint):
        session.execute(delete(model).where(model.project_id == project_id))
    session.execute(delete(Project).where(Project.id == project_id))
    session.flush()


def _rows(items) -> list[dict]:
    return [item.model_dump() for item in items]


def seed_dataset(session: Session, dataset: DemoDataset, reset: bool = False) -> dict[str, object]:
    existing = session.get(Project, dataset.project.id)
    if existing and not reset:
        return {"status": "already_seeded", **dataset_summary(dataset)}
    if existing:
        _clear_project(session, dataset.project.id)

    session.add(Project(**dataset.project.model_dump()))
    session.add_all(Sprint(**row) for row in _rows(dataset.sprints))
    session.add_all(Ticket(**row) for row in _rows(dataset.tickets))
    session.add_all(Commit(**row) for row in _rows(dataset.commits))
    session.add_all(PullRequest(**row) for row in _rows(dataset.pull_requests))
    session.add_all(Build(**row) for row in _rows(dataset.builds))
    session.add_all(TestResult(**row) for row in _rows(dataset.test_results))
    session.add_all(Metric(**row) for row in _rows(dataset.metrics))
    session.add_all(Risk(**row) for row in _rows(dataset.risks))
    session.add_all(Report(**row) for row in _rows(dataset.reports))
    session.commit()
    return {"status": "seeded", **dataset_summary(dataset)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the demo dataset into the database")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/demo_dataset_v0.1.json"),
        help="Path to the versioned JSON dataset",
    )
    parser.add_argument("--reset", action="store_true", help="Replace the existing demo project")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    with SessionLocal() as session:
        result = seed_dataset(session, dataset, reset=args.reset)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
