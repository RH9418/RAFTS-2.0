import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://stage.bbu.esp.antuit.ai/dp/demand-planning/executive-dashboard?workbookId=4&tabIndex=1")
    page.locator(".zeb-filter").click()
    page.get_by_text("Hierarchy").click()
    page.get_by_text("Brand Level 4").click()
    page.get_by_role("button", name="Apply Filters").click()
    page.locator(".zeb-filter").click()
    page.locator(".filter-icon-wrapper").click()
    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.background-primary-color").click()
    page.get_by_role("button", name="Apply Filters").click()
    page.locator(".navigation-icon.zeb-circle-chevron-right").click()
    page.locator(".navigation-icon.zeb-circle-chevron-right").click()
    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.locator(".ag-icon.ag-icon-small-down").click()
    page.get_by_role("option", name="Does not equal").click()
    page.get_by_role("spinbutton", name="Filter Value").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("1000")
    page.get_by_role("button", name="Apply", exact=True).click()
    page.get_by_text("User Bias").click()
    page.get_by_text("User Bias").click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
