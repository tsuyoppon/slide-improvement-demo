import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright_context:
        browser = playwright_context.chromium.launch(headless=True)
        yield browser
        browser.close()
