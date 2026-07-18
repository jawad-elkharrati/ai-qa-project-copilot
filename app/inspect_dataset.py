import argparse
import json
from pathlib import Path

from app.dataset import dataset_summary, load_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and summarize the demo dataset")
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/demo_dataset_v0.1.json")
    )
    args = parser.parse_args()
    dataset = load_dataset(args.dataset)
    result = dataset_summary(dataset)
    result["scenario_distribution"] = {
        sprint.name: sum(ticket.sprint_id == sprint.id for ticket in dataset.tickets)
        for sprint in dataset.sprints
    }
    result["anomaly_rules"] = sorted({item.rule_id for item in dataset.expected_anomalies})
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

