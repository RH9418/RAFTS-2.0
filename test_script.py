import re
from playwright.sync_api import Page, expect


def test_example(page: Page) -> None:
    page.get_by_role("textbox", name="e.g. Global Filters").click()
    page.get_by_role("textbox", name="e.g. Global Filters").fill("Filter Section Test")
    page.get_by_role("button", name="Add Section").click()
    page.locator(".ag-icon.ag-icon-filter").first.click()
    page.get_by_role("textbox", name="Filter Value").fill("WALMART")
    page.get_by_role("button", name="Apply").click()
    page.locator(".ag-icon.ag-icon-filter").first.click()
    page.get_by_role("button", name="Reset").click()
    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("10496")
    page.locator(".ag-icon.ag-icon-small-down").first.click()
    page.get_by_role("option", name="Greater than or equal to").click()
    page.get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_role("button", name="Reset").click()
    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("328.8")
    page.get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_role("button", name="Reset").click()
    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("373.7")
    page.get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_role("button", name="Reset").click()
    page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked)   WALMART STORES HQ").get_by_label("Press Space to toggle row").check()
    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("2840")
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("110.1")
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("4")
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.locator(".checkbox-primary-color").first.check()
    page.get_by_role("button", name="Apply").click()
    page.locator("#time-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()
    page.locator("div").filter(has_text=re.compile(r"^Latest 5 Next 4$")).nth(1).click()
