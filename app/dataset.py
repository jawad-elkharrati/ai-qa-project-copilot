import json
from pathlib import Path

from app.schemas import DemoDataset


def load_dataset(path: str | Path) -> DemoDataset:
    dataset_path = Path(path)
    with dataset_path.open(encoding="utf-8") as stream:
        return DemoDataset.model_validate(json.load(stream))


def dataset_summary(dataset: DemoDataset) -> dict[str, int | str]:
    return {
        "version": dataset.version,
        "projects": 1,
        "sprints": len(dataset.sprints),
        "tickets": len(dataset.tickets),
        "commits": len(dataset.commits),
        "pull_requests": len(dataset.pull_requests),
        "builds": len(dataset.builds),
        "test_results": len(dataset.test_results),
        "metrics": len(dataset.metrics),
        "risks": len(dataset.risks),
        "reports": len(dataset.reports),
        "expected_anomalies": len(dataset.expected_anomalies),
    }

