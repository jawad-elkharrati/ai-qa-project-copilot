from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _compose() -> dict:
    return yaml.safe_load(_text("compose.yml"))


def test_compose_contains_only_api_and_dashboard_from_one_image() -> None:
    compose = _compose()
    services = compose["services"]

    assert set(services) == {"api", "dashboard"}
    assert services["api"]["image"] == services["dashboard"]["image"]
    assert services["api"]["build"] == services["dashboard"]["build"]
    assert services["api"]["read_only"] is True
    assert services["dashboard"]["read_only"] is True
    assert services["api"]["security_opt"] == ["no-new-privileges:true"]
    assert services["dashboard"]["security_opt"] == ["no-new-privileges:true"]


def test_sqlite_volume_migrations_and_service_dependency_are_explicit() -> None:
    compose = _compose()
    api = compose["services"]["api"]
    dashboard = compose["services"]["dashboard"]
    entrypoint = _text("docker/api-entrypoint.sh")

    assert api["volumes"] == ["sqlite_data:/data"]
    assert "sqlite+pysqlite:////data/copilote_qa.db" in api["environment"]["DATABASE_URL"]
    assert api["command"] == ["/app/docker/api-entrypoint.sh"]
    assert entrypoint.index("alembic upgrade head") < entrypoint.index("exec uvicorn")
    assert dashboard["depends_on"]["api"]["condition"] == "service_healthy"
    assert dashboard["environment"]["API_URL"].endswith("http://api:8000}")
    assert dashboard["environment"]["PYTHONPATH"] == "/app"
    assert "sqlite_data" in compose["volumes"]


def test_both_services_have_real_http_healthchecks() -> None:
    services = _compose()["services"]
    api_health = " ".join(str(item) for item in services["api"]["healthcheck"]["test"])
    dashboard_health = " ".join(str(item) for item in services["dashboard"]["healthcheck"]["test"])

    assert "http://127.0.0.1:8000/health" in api_health
    assert "http://127.0.0.1:8501/_stcore/health" in dashboard_health
    for service in services.values():
        assert service["healthcheck"]["retries"] >= 3
        assert service["healthcheck"]["start_period"]


def test_image_runs_as_non_root_and_contains_no_embedded_secret() -> None:
    dockerfile = _text("Dockerfile")
    compose = _text("compose.yml")
    environment = _text(".env.example")
    combined = "\n".join((dockerfile, compose, environment)).lower()

    assert "user 10001:10001" in dockerfile.lower()
    assert dockerfile.index("USER 10001:10001") < dockerfile.index("CMD [")
    assert "password=" not in combined
    assert "secret=" not in combined
    assert "copilote:copilote@" not in combined
    assert "postgresql+psycopg://" not in environment


def test_docker_context_excludes_local_state_and_secret_files() -> None:
    ignored = set(_text(".dockerignore").splitlines())

    assert {".git", ".env", "*.db", ".venv", "tests", ".ua"} <= ignored
    assert "!.env.example" in ignored


def test_docker_documentation_covers_startup_access_and_persistence() -> None:
    readme = _text("README.md")

    for expected in (
        "docker compose up --build -d",
        "http://localhost:8000/docs",
        "http://localhost:8501",
        "docker compose down",
        "docker compose up -d",
        "docker compose exec api alembic current",
        "DATABASE_URL",
        "DASHBOARD_API_URL",
    ):
        assert expected in readme


def test_docker_configuration_does_not_enable_external_actions() -> None:
    combined = "\n".join(
        _text(path) for path in ("Dockerfile", "compose.yml", "docker/api-entrypoint.sh")
    ).lower()

    assert "jira" not in combined
    assert "github" not in combined
    assert "external_action_executed=true" not in combined
    assert "external_action_executed: true" not in combined
