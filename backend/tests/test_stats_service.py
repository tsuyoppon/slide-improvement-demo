import pytest

from app.models import (
    ImprovementItemResult,
    QuestionResult,
    QuizSession,
    UserStats,
)
from app import db_service


class _DummyTable:
    def __init__(self):
        self.items = []

    def put_item(self, Item):
        self.items.append(Item)


class _DummyDynamoDB:
    def __init__(self, table):
        self._table = table

    def Table(self, name):
        return self._table


@pytest.fixture()
def stats_service(monkeypatch):
    monkeypatch.setenv("USER_STATS_TABLE_NAME", "test-table")
    monkeypatch.setattr(db_service, "USER_STATS_TABLE_NAME", "test-table")
    table = _DummyTable()
    monkeypatch.setattr(db_service, "dynamodb", _DummyDynamoDB(table))
    service = db_service.StatsService()
    return service, table


def _make_session(improvement_sets):
    questions = []
    for idx, improvements in enumerate(improvement_sets, start=1):
        questions.append(
            QuestionResult(
                question_id=f"q{idx}",
                user_answer="dummy",
                correct_answer="dummy",
                is_correct=True,
                improvements=improvements,
            )
        )
    return QuizSession(
        user_id="user-1",
        session_end_ts="2024-01-01T00:00:00Z",
        session_start_ts="2024-01-01T00:00:00Z",
        total_questions=len(questions),
        correct_answers=len(questions),
        score_percentage=100.0,
        questions=questions,
    )


def test_update_user_stats_aggregates_improvements(stats_service):
    service, table = stats_service
    stats = UserStats(user_id="user-1")

    session = _make_session(
        [
            [
                ImprovementItemResult(
                    label="structure", answered=True, correct=True, is_correct=True
                ),
                ImprovementItemResult(
                    label="", answered=True, correct=False, is_correct=False
                ),
            ],
            [
                ImprovementItemResult(
                    label="structure", answered=True, correct=False, is_correct=False
                ),
                ImprovementItemResult(
                    label="delivery", answered=True, correct=True, is_correct=True
                ),
            ],
        ]
    )

    service.update_user_stats(stats, session)

    assert stats.improvement_item_stats == {
        "structure": {"attempts": 2, "correct": 1},
        "delivery": {"attempts": 1, "correct": 1},
    }
    assert table.items
    saved_item = table.items[0]
    assert saved_item["improvement_item_stats"] == stats.improvement_item_stats


def test_update_user_stats_merges_existing_counts(stats_service):
    service, table = stats_service
    stats = UserStats(
        user_id="user-1",
        improvement_item_stats={"structure": {"attempts": 3, "correct": 2}},
    )

    session = _make_session(
        [
            [
                ImprovementItemResult(
                    label="structure", answered=True, correct=True, is_correct=True
                )
            ]
        ]
    )

    service.update_user_stats(stats, session)

    assert stats.improvement_item_stats == {
        "structure": {"attempts": 4, "correct": 3}
    }
    assert table.items
    assert table.items[0]["improvement_item_stats"] == stats.improvement_item_stats


def test_update_user_stats_skips_questions_without_improvements(stats_service):
    service, table = stats_service
    stats = UserStats(user_id="user-1")

    session = _make_session([
        [],
        [
            ImprovementItemResult(
                label="", answered=True, correct=False, is_correct=False
            )
        ],
    ])

    service.update_user_stats(stats, session)

    assert stats.improvement_item_stats == {}
    assert table.items
    assert table.items[0]["improvement_item_stats"] == {}
