import re
from playwright.sync_api import Page, expect


def test_example(page: Page) -> None:
    page.get_by_role("textbox", name="e.g. Global Filters").click()
    page.get_by_role("textbox", name="e.g. Global Filters").fill("Global Filters")
    page.get_by_role("button", name="Add Section").click()
    page.locator("#filter-toggle-iconId").click()
    page.locator("div").filter(has_text=re.compile(r"^Hierarchy$")).nth(2).click()
    page.locator("div:nth-child(4) > esp-filter-sub-accordion-v1 > .sub-accordion-element > .d-flex").click()
    page.locator("div").filter(has_text=re.compile(r"^HEADWEAR$")).click()
    page.get_by_role("button", name="Apply Filters").click()
    page.get_by_role("textbox", name="e.g. Global Filters").click()
