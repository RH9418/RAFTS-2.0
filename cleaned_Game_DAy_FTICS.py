import re

from playwright.sync_api import Page, expect





def test_example(page: Page) -> None:
    # --- MFA & Login Wait Block ---
    try: page.goto("https://stage.ftics.esp.antuit.ai/dp/demand-planning/executive-dashboard?workbookId=5&tabIndex=2", timeout=0)
    except: pass
    print("\n" + "="*60)
    input("ACTION REQUIRED: Log in, pass MFA, then PRESS [ENTER]...\n")
    print("="*60 + "\n")




    # ============================================================
    # SECTION: Global Filters
    # ============================================================


    page.locator("#filter-toggle-iconId").click()

    page.locator("div").filter(has_text=re.compile(r"^Hierarchy$")).nth(2).click()

    page.locator("div:nth-child(4) > esp-filter-sub-accordion-v1 > .sub-accordion-element > .d-flex").click()

    page.locator("div").filter(has_text=re.compile(r"^HEADWEAR$")).click()

    page.get_by_role("button", name="Apply Filters").click()


