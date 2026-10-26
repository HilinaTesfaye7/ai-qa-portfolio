"""Playwright UI tests for the approval step on the priority tracker."""
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.ui, pytest.mark.usefixtures("clean_state")]


def create_item(page: Page, base_url: str, title: str):
    page.goto(f"{base_url}/tracker")
    page.fill("#title", title)
    page.click("#create")
    expect(page.locator("#status")).to_have_text("Created")


def test_submit_is_disabled_until_reviewed(page: Page, base_url):
    create_item(page, base_url, "Acquire Blue Harbor")
    expect(page.locator("#submit")).to_be_disabled()


def test_happy_path_review_then_submit(page: Page, base_url):
    create_item(page, base_url, "Acquire Summit Physio")
    page.click("#review")
    expect(page.locator("#submit")).to_be_enabled()
    page.click("#submit")
    expect(page.locator("#status")).to_have_text("Submitted")


def test_enabling_the_button_in_devtools_does_not_bypass_review(page: Page, base_url):
    """A user who force-enables the button must still be blocked by the server."""
    create_item(page, base_url, "Acquire Lakeside")
    page.evaluate("document.querySelector('#submit').disabled = false")
    page.click("#submit")
    expect(page.locator("#status")).to_have_text("Blocked: review required")
