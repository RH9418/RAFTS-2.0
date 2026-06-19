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
    # SECTION: Default Initialization
    # ============================================================
    page.locator(".zeb-filter").first.click()

    page.get_by_text("Hierarchy").click()

    page.get_by_text("League").click()

    page.get_by_role("radio", name="MLS").check()

    page.get_by_text("League").click()

    page.locator("#SideFilterproducthierarchyId").get_by_text("Team").click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first.click()

    page.locator("#SideFilterproducthierarchyId").get_by_text("Team", exact=True).click()

    page.get_by_text("Department").click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first.click()

    page.get_by_text("Department").click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").click()

    page.get_by_role("button", name="Apply Filters").click()

    page.locator(".zeb-filter").first.click()



    # ============================================================
    # SECTION: Forecast Filters
    # ============================================================


    page.locator(".dropdown-caret.p-l-16").first.click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator("#location-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()

    page.locator("#location-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.get_by_role("button", name="Apply").click()



    # ============================================================
    # SECTION: Forecast Total Grid
    # ============================================================


    page.locator(".pointer.chevron.zeb-chevron-right.m-r-12.collapsed").click()

    page.locator(".ag-body-horizontal-scroll-container").first.click()

    page.locator("esp-card-component").filter(has_text="Forecast Total columns (0)").get_by_role("button").click()

    page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()

    page.get_by_role("treeitem", name="Stat Unit Sales Fcst Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Stat Sales Fcst ($) Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Sales Fcst Adjusted ($) Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Actual Sales & ROY Fcst ($)").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Actual Sales ($) Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="LY Sales ($) Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Sales ($) Change vs LY Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="LLY Sales ($) Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Sales ($) Change vs LLY Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Actual Sales & ROY Fcst Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Actual Sales Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="LY Sales Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Sales Change vs LY Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="LLY Sales Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (hidden)").check()

    page.locator("esp-card-component").filter(has_text="Forecast Total columns (0)").get_by_role("button").click()

    page.locator(".pointer.zeb-adjustments").first.click()

    page.get_by_text("Save Preference").click()

    with page.expect_download() as download_info:

        page.locator(".icon-color-toolbar-active.zeb-download-underline").first.click()

    download = download_info.value



    # ============================================================
    # SECTION: Daily Forecast Event Grid
    # ============================================================


    page.locator("esp-card-component").filter(has_text="Daily Forecast by Event").get_by_role("button").click()

    page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()

    page.get_by_role("treeitem", name="Game # Column").get_by_label("Press SPACE to toggle").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("1")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("treeitem", name="Series # Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Season Type Column").get_by_label("Press SPACE to toggle").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("textbox", name="Filter Value").fill("On Season")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.locator("#ag-3446-input").fill("Regular")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("treeitem", name="Result Column").get_by_label("Press SPACE to toggle").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("textbox", name="Filter Value").fill("Win")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("treeitem", name="Result Column").get_by_label("Press SPACE to toggle").uncheck()

    page.get_by_role("treeitem", name="Date Column", exact=True).get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Date Column", exact=True).get_by_label("Press SPACE to toggle").uncheck()

    page.get_by_role("treeitem", name="Game/Non-Game Day Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("textbox", name="Filter Value").fill("Game Day")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("treeitem", name="Game/Non-Game Day Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="Month Column", exact=True).get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("textbox", name="Filter Value").fill("March")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("treeitem", name="Month Column", exact=True).get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="DoW Column", exact=True).get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("textbox", name="Filter Value").fill("Monday")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("treeitem", name="DoW Column", exact=True).get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="Opp Column", exact=True).get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.get_by_role("treeitem", name="Opp Column", exact=True).get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.locator("#ag-3569-input").check()

    page.locator("#ag-3569-input").uncheck()

    page.locator("#ag-3571-input").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.locator(".ag-icon.ag-icon-small-down").click()

    page.get_by_role("option", name="Greater than or equal to").click()

    page.get_by_role("spinbutton", name="Filter Value").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("25")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("treeitem", name="Stat Unit Sales Fcst Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.locator("#ag-3573-input").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("100")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_role("option", name="Less than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()

    page.locator("#ag-3575-input").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("1")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_role("option", name="Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="Initial Per Cap Stat Fcst").get_by_label("Press SPACE to toggle").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("10")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_role("option", name="Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="GD Sales Fcst Override ($) Column", exact=True).get_by_label("Press SPACE to toggle").check()

    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()

    page.locator("#ag-7836-input").check()

    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()

    page.locator("#ag-7838-input").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("20")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_role("option", name="Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("treeitem", name="Season Type Column").get_by_label("Press SPACE to toggle").uncheck()

    page.get_by_role("checkbox", name="Toggle All Columns Visibility").check()

    page.get_by_text("Daily Forecast by Event columns (0) TopBottom").click()

    page.locator("esp-card-component").filter(has_text="Daily Forecast by Event").get_by_role("button").click()

    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("2000")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_role("option", name="Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.locator("div:nth-child(4) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()

    page.get_by_text("Save Preference").click()

    with page.expect_download() as download1_info:

        page.locator("div:nth-child(3) > #export-iconId > .icon-color-toolbar-active").click()

    download1 = download1_info.value

    page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator("div").filter(has_text=re.compile(r"^View 10 row\(s\)$")).nth(1).click()

    page.locator("a").filter(has_text=re.compile(r"^2$")).click()

    page.get_by_role("gridcell", name="D.C. UNITED").first.click(button="right")

    page.get_by_label("Context Menu").get_by_text("Dept Penetration Pivots").click()

