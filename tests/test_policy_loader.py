import json
from pathlib import Path

import pytest

from app.policy_evaluator import evaluate_policy
from app.policy_loader import PolicyConfigurationError, load_policy_set

POLICY_PATH = Path("policies/qa-rules-v1.0.json")


def load_payload() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def write_payload(tmp_path, payload: dict) -> Path:
    path = tmp_path / "policies.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_versioned_policy_file_loads_all_five_rules() -> None:
    policy_set = load_policy_set(POLICY_PATH)

    assert policy_set.ruleset_version == "qa-rules-v1.0"
    assert len(policy_set.policies) == 5
    assert sum(policy.weight for policy in policy_set.policies if policy.enabled) == 100
    assert len(policy_set.content_hash) == 64
    assert policy_set.by_id("QA-COVERAGE-LOW").condition.value == 70.0


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda payload: payload["policies"].append(payload["policies"][0].copy()),
            "identifiers must be unique",
        ),
        (
            lambda payload: payload["policies"][0]["condition"].update(
                {"operator": "execute_python"}
            ),
            "invalid policy file",
        ),
        (
            lambda payload: payload["policies"][0].update({"weight": -1}),
            "invalid policy file",
        ),
        (
            lambda payload: payload["policies"][0]["condition"].update(
                {"operator": "in", "value": 72}
            ),
            "invalid policy file",
        ),
        (
            lambda payload: payload["policies"][0].update({"entity_type": "build"}),
            "invalid policy file",
        ),
    ],
)
def test_invalid_policy_definitions_fail_closed(tmp_path, mutation, expected: str) -> None:
    payload = load_payload()
    mutation(payload)

    with pytest.raises(PolicyConfigurationError, match=expected):
        load_policy_set(write_payload(tmp_path, payload))


def test_enabled_policy_weight_above_one_hundred_is_rejected(tmp_path) -> None:
    payload = load_payload()
    payload["policies"][0]["weight"] = 21

    with pytest.raises(PolicyConfigurationError, match="invalid policy file"):
        load_policy_set(write_payload(tmp_path, payload))


def test_disabled_policy_is_versioned_but_not_evaluated(tmp_path) -> None:
    payload = load_payload()
    payload["policies"][0]["enabled"] = False

    policy_set = load_policy_set(write_payload(tmp_path, payload))
    policy = policy_set.by_id("QA-BLOCKED-LONG")

    assert policy.enabled is False
    assert sum(item.weight for item in policy_set.policies if item.enabled) == 80
    assert evaluate_policy(policy, []) == []


def test_missing_policy_file_has_a_controlled_error(tmp_path) -> None:
    with pytest.raises(PolicyConfigurationError, match="unable to read policy file"):
        load_policy_set(tmp_path / "missing.json")


def test_different_ids_with_same_active_semantics_are_rejected(tmp_path) -> None:
    payload = load_payload()
    duplicate = payload["policies"][0].copy()
    duplicate["id"] = "QA-BLOCKED-LONG-ALIAS"
    duplicate["weight"] = 0
    payload["policies"].append(duplicate)

    with pytest.raises(
        PolicyConfigurationError,
        match=("Duplicate semantic policy detected: QA-BLOCKED-LONG and QA-BLOCKED-LONG-ALIAS"),
    ):
        load_policy_set(write_payload(tmp_path, payload))


def test_similar_policy_with_different_threshold_is_accepted(tmp_path) -> None:
    payload = load_payload()
    candidate = payload["policies"][0].copy()
    candidate["condition"] = candidate["condition"].copy()
    candidate.update({"id": "QA-BLOCKED-VERY-LONG", "weight": 0})
    candidate["condition"]["value"] = 96
    payload["policies"].append(candidate)

    policy_set = load_policy_set(write_payload(tmp_path, payload))
    assert policy_set.by_id("QA-BLOCKED-VERY-LONG").condition.value == 96


def test_disabled_semantic_duplicate_is_kept_but_not_evaluated(tmp_path) -> None:
    payload = load_payload()
    duplicate = payload["policies"][0].copy()
    duplicate.update(
        {
            "id": "QA-BLOCKED-LONG-DRAFT",
            "weight": 0,
            "enabled": False,
        }
    )
    payload["policies"].append(duplicate)

    policy_set = load_policy_set(write_payload(tmp_path, payload))
    draft = policy_set.by_id("QA-BLOCKED-LONG-DRAFT")
    assert draft.enabled is False
    assert evaluate_policy(draft, []) == []


def test_canonical_semantics_do_not_depend_on_json_field_order(tmp_path) -> None:
    payload = load_payload()
    duplicate = payload["policies"][0].copy()
    duplicate["condition"] = {
        "value": duplicate["condition"]["value"],
        "operator": duplicate["condition"]["operator"],
        "metric": duplicate["condition"]["metric"],
    }
    duplicate.update({"id": "QA-BLOCKED-REORDERED", "weight": 0})
    payload["policies"].append(duplicate)

    with pytest.raises(PolicyConfigurationError, match="Duplicate semantic policy"):
        load_policy_set(write_payload(tmp_path, payload))


def test_different_operator_is_not_a_semantic_duplicate(tmp_path) -> None:
    payload = load_payload()
    candidate = payload["policies"][0].copy()
    candidate["condition"] = candidate["condition"].copy()
    candidate.update({"id": "QA-BLOCKED-AT-LEAST", "weight": 0})
    candidate["condition"]["operator"] = "greater_or_equal"
    payload["policies"].append(candidate)

    policy_set = load_policy_set(write_payload(tmp_path, payload))
    assert policy_set.by_id("QA-BLOCKED-AT-LEAST").condition.operator == "greater_or_equal"
