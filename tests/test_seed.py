from sqlalchemy import func, select

from app.dataset import load_dataset
from app.models import Build, Project, Sprint, Ticket
from app.seed import seed_dataset


def test_seed_loads_the_reference_dataset(db_session) -> None:
    dataset = load_dataset("data/demo_dataset_v0.1.json")
    result = seed_dataset(db_session, dataset)

    assert result["status"] == "seeded"
    assert db_session.scalar(select(func.count()).select_from(Project)) == 1
    assert db_session.scalar(select(func.count()).select_from(Sprint)) == 3
    assert db_session.scalar(select(func.count()).select_from(Ticket)) == 50
    assert db_session.scalar(select(func.count()).select_from(Build)) == 12


def test_seed_is_idempotent_and_can_reset(db_session) -> None:
    dataset = load_dataset("data/demo_dataset_v0.1.json")
    assert seed_dataset(db_session, dataset)["status"] == "seeded"
    assert seed_dataset(db_session, dataset)["status"] == "already_seeded"
    assert db_session.scalar(select(func.count()).select_from(Ticket)) == 50

    assert seed_dataset(db_session, dataset, reset=True)["status"] == "seeded"
    assert db_session.scalar(select(func.count()).select_from(Project)) == 1
    assert db_session.scalar(select(func.count()).select_from(Ticket)) == 50
