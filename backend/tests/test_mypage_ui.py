from pathlib import Path

import pytest


@pytest.fixture()
def sample_page(browser):
    page = browser.new_page()
    html_path = Path(__file__).resolve().parents[2] / "mypage_sample.html"
    page.goto(html_path.as_uri())
    page.wait_for_selector("text=改善項目別の正答率")
    yield page
    page.close()


def test_improvement_cards_render_expected_metrics(sample_page):
    cards = sample_page.locator("div.border.border-gray-200.rounded-lg.p-4.bg-white")
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
