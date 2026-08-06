import csv
import json
from pathlib import Path

SOURCE = Path("data/demo_dataset_v0.1.json")
OUTPUT = Path("data/demo_dataset_v0.1.csv")
COLLECTIONS = (
    "sprints",
    "tickets",
    "commits",
    "pull_requests",
    "builds",
    "test_results",
    "metrics",
    "risks",
    "reports",
    "expected_anomalies",
)


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    metadata = {
        "version": data["version"],
        "generated_at": data["generated_at"],
        "reference_date": data["reference_date"],
    }
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["entity", "payload"])
        writer.writeheader()
        writer.writerow({"entity": "metadata", "payload": json.dumps(metadata, ensure_ascii=False)})
        writer.writerow(
            {"entity": "project", "payload": json.dumps(data["project"], ensure_ascii=False)}
        )
        for collection in COLLECTIONS:
            for row in data[collection]:
                writer.writerow(
                    {"entity": collection, "payload": json.dumps(row, ensure_ascii=False)}
                )
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    main()
