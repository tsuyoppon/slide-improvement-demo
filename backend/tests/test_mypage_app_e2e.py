import json
from pathlib import Path

import pytest


@pytest.fixture()
def app_page(browser):
    page = browser.new_page()
    index_path = Path(__file__).resolve().parents[2] / "index.html"

    page.add_init_script(
        """
        window.API_BASE = 'http://localhost.test';
        window.sessionStorage.setItem('auth.idToken', 'test-token');
        """
    )

    quiz_ids = [f"quiz-{idx}" for idx in range(1, 16)]

    def fulfill_json(route, payload, status=200):
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(payload),
        )

    page.route(
        "**/api/quiz_ids",
        lambda route, request: fulfill_json(route, quiz_ids),
    )

    def quiz_handler(route, request):
        quiz_id = request.url.rsplit("/", 1)[-1]
        payload = {
            "id": quiz_id,
            "image_url": None,
            "improvements": [
                "配色を整える",
                "文字サイズを調整",
                "レイアウトを揃える",
                "アイコンの統一",
            ],
        }
        fulfill_json(route, payload)

    page.route("**/api/quiz/*", quiz_handler)
    page.route("**/api/quiz", quiz_handler)

    stats_payload = {
        "stats": {
            "user_id": "user-1",
            "total_sessions": 6,
            "total_questions_answered": 90,
            "total_correct_answers": 68,
            "average_score": 75.6,
            "best_score": 92.0,
            "last_quiz_date": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "improvement_item_stats": {
                "配色を整える": {"attempts": 12, "correct": 10},
                "文字サイズを調整": {"attempts": 15, "correct": 9},
                "レイアウトを揃える": {"attempts": 14, "correct": 11},
                "アイコンの統一": {"attempts": 8, "correct": 5},
            },
        },
        "recent_sessions": [],
    }

    page.route("**/api/stats", lambda route, request: fulfill_json(route, stats_payload))
    page.route(
        "**/api/session/save",
        lambda route, request: fulfill_json(route, {"status": "ok"}),
    )

    page.goto(index_path.as_uri())
    page.wait_for_load_state("networkidle")
    yield page
    page.close()


def test_mypage_displays_backend_stats(app_page):
    app_page.wait_for_selector("text=マイページ")
    app_page.click("text=マイページ")

    app_page.wait_for_selector("text=改善項目別の正答率")
    app_page.wait_for_selector("text=配色を整える")

    cards = app_page.locator("div.border.border-gray-200.rounded-lg.p-4")
    assert cards.count() == 4

    expectations = {
        "配色を整える": {"attempts": 12, "correct": 10, "accuracy": 83, "status": "得意"},
        "文字サイズを調整": {"attempts": 15, "correct": 9, "accuracy": 60, "status": "要復習"},
        "レイアウトを揃える": {"attempts": 14, "correct": 11, "accuracy": 79, "status": "伸びしろ"},
        "アイコンの統一": {"attempts": 8, "correct": 5, "accuracy": 63, "status": "要復習"},
    }

    for label, expect in expectations.items():
        card = cards.filter(has_text=label)
        assert card.count() == 1
        text_content = card.inner_text()
        assert f"正答 {expect['correct']} / {expect['attempts']}" in text_content
        assert f"{expect['accuracy']}%" in text_content
        assert expect["status"] in text_content

        bar = card.locator("div.bg-indigo-500")
        assert bar.count() == 1
        style = bar.first.get_attribute("style") or ""
        assert f"width: {expect['accuracy']}%" in style
