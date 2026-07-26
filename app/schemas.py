from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class ProjectData(BaseModel):
    id: str
    key: str
    name: str
    description: str
    repository_url: str | None = None
    created_at: datetime


class SprintData(BaseModel):
    id: str
    project_id: str
    name: str
    goal: str
    start_date: date
    end_date: date
    status: str
    capacity_points: int = Field(ge=0)
    created_at: datetime


class TicketData(BaseModel):
    id: str
    project_id: str
    sprint_id: str | None = None
    title: str
    description: str
    type: str
    status: str
    priority: str
    assignee: str | None = None
    story_points: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    due_date: date | None = None
    blocked_since: datetime | None = None
    closed_at: datetime | None = None
    labels: list[str] = Field(default_factory=list)


class CommitData(BaseModel):
    id: str
    project_id: str
    ticket_id: str | None = None
    sha: str
    author: str
    message: str
    committed_at: datetime
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)


class PullRequestData(BaseModel):
    id: str
    project_id: str
    ticket_id: str | None = None
    number: int = Field(gt=0)
    title: str
    author: str
    status: str
    source_branch: str
    target_branch: str
    created_at: datetime
    merged_at: datetime | None = None
    review_count: int = Field(ge=0)
    changed_files: int = Field(ge=0)


class BuildData(BaseModel):
    id: str
    project_id: str
    sprint_id: str | None = None
    pull_request_id: str | None = None
    pipeline_name: str
    branch: str
    commit_sha: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0)


class TestResultData(BaseModel):
    id: str
    project_id: str
    build_id: str
    suite_name: str
    status: str
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    executed_at: datetime

    @model_validator(mode="after")
    def validate_counts(self):
        if self.passed + self.failed + self.skipped != self.total:
            raise ValueError("passed + failed + skipped must equal total")
        return self


class MetricData(BaseModel):
    id: str
    project_id: str
    sprint_id: str | None = None
    name: str
    value: float
    unit: str
    source: str
    measured_at: datetime


class RiskData(BaseModel):
    id: str
    analysis_id: str | None = None
    project_id: str
    sprint_id: str | None = None
    rule_id: str
    title: str
    description: str
    severity: str
    priority: int = Field(default=4, ge=1, le=4)
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    source_type: str
    source_id: str
    evidence: dict = Field(default_factory=dict)
    recommendation: str = ""
    requires_human_validation: bool = True
    status: str
    detected_at: datetime


class ReportData(BaseModel):
    id: str
    project_id: str
    sprint_id: str | None = None
    type: str
    status: str
    period_start: date
    period_end: date
    content_markdown: str
    generated_at: datetime
    validated_by: str | None = None
    validated_at: datetime | None = None


class ExpectedAnomaly(BaseModel):
    rule_id: str
    scenario: str
    severity: str
    source_type: str
    source_id: str
    description: str
    expected_signal: str


class DemoDataset(BaseModel):
    version: str
    generated_at: datetime
    reference_date: date
    project: ProjectData
    sprints: list[SprintData]
    tickets: list[TicketData]
    commits: list[CommitData]
    pull_requests: list[PullRequestData]
    builds: list[BuildData]
    test_results: list[TestResultData]
    metrics: list[MetricData]
    risks: list[RiskData] = Field(default_factory=list)
    reports: list[ReportData] = Field(default_factory=list)
    expected_anomalies: list[ExpectedAnomaly]

    @model_validator(mode="after")
    def validate_references(self):
        project_id = self.project.id
        collections = [
            self.sprints,
            self.tickets,
            self.commits,
            self.pull_requests,
            self.builds,
            self.test_results,
            self.metrics,
            self.risks,
            self.reports,
        ]
        if any(item.project_id != project_id for items in collections for item in items):
            raise ValueError("all records must reference the dataset project")

        self._assert_unique("sprint", [item.id for item in self.sprints])
        self._assert_unique("ticket", [item.id for item in self.tickets])
        self._assert_unique("commit", [item.id for item in self.commits])
        self._assert_unique("pull request", [item.id for item in self.pull_requests])
        self._assert_unique("build", [item.id for item in self.builds])

        sprint_ids = {item.id for item in self.sprints}
        ticket_ids = {item.id for item in self.tickets}
        pull_request_ids = {item.id for item in self.pull_requests}
        build_ids = {item.id for item in self.builds}

        self._check_optional_references("ticket.sprint_id", self.tickets, sprint_ids, "sprint_id")
        self._check_optional_references("commit.ticket_id", self.commits, ticket_ids, "ticket_id")
        self._check_optional_references(
            "pull_request.ticket_id", self.pull_requests, ticket_ids, "ticket_id"
        )
        self._check_optional_references("build.sprint_id", self.builds, sprint_ids, "sprint_id")
        self._check_optional_references(
            "build.pull_request_id", self.builds, pull_request_ids, "pull_request_id"
        )
        invalid_builds = [item.id for item in self.test_results if item.build_id not in build_ids]
        if invalid_builds:
            raise ValueError(f"test results reference unknown builds: {invalid_builds}")
        from app.dataset_validation import validate_dataset_consistency

        validate_dataset_consistency(self)
        return self

    @staticmethod
    def _assert_unique(label: str, values: list[str]) -> None:
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {label} identifiers")

    @staticmethod
    def _check_optional_references(label: str, items, valid_ids: set[str], attribute: str) -> None:
        invalid = [
            item.id
            for item in items
            if getattr(item, attribute) is not None and getattr(item, attribute) not in valid_ids
        ]
        if invalid:
            raise ValueError(f"{label} contains unknown references on: {invalid}")
