import re

from playwright.sync_api import Page, expect





def test_example(page: Page) -> None:
    # --- MFA & Login Wait Block ---
    try: page.goto("https://stage.ftics.esp.antuit.ai/dp/demand-planning/executive-dashboard?workbookId=5&tabIndex=1", timeout=30000)
    except: pass
    print("\n" + "="*60)
    input("ACTION REQUIRED: Log in, pass MFA, then PRESS [ENTER]...\n")
    print("="*60 + "\n")



    # ============================================================
    # SECTION: Default Initialization
    # ============================================================
    page.locator(".zeb-filter").first.click()



    # ============================================================
    # SECTION: Global Filters
    # ============================================================


    page.locator("div").filter(has_text=re.compile(r"^Hierarchy$")).nth(2).click()

    page.get_by_text("League").click()

    page.get_by_text("League").click()

    page.get_by_text("Team", exact=True).click()

    page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.get_by_text("Team", exact=True).click()

    page.get_by_text("Department").click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first.click()

    page.get_by_text("Department").click()

    page.get_by_text("Class").click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first.click()

    page.get_by_text("Class").click()

    page.get_by_text("Attribute").click()

    page.get_by_text("Product Line").click()

    page.get_by_text("Color", exact=True).click()

    page.get_by_role("button", name="Apply Filters").click()

    page.locator(".pill-nav-btn.pointer").click()

    page.locator(".zeb-filter").first.click()

    page.locator(".dropdown-caret.p-l-16").first.click()



    # ============================================================
    # SECTION: Alert and Season Types
    # ============================================================


    page.locator(".dropdown-caret.p-l-16").first.click()

    page.locator("div").filter(has_text=re.compile(r"^All Alerts$")).nth(1).click()

    page.locator(".dropdown-caret.p-l-16").first.click()

    page.locator("div").filter(has_text=re.compile(r"^Over Stock$")).nth(1).click()

    page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()

    page.get_by_role("button", name="Apply").click()

    page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.get_by_role("button", name="Apply").click()

    page.locator(".dropdown-caret.p-l-16").first.click()

    page.get_by_text("All Alerts").click()

    page.get_by_role("button", name="Apply").click()

    page.get_by_role("button", name="columns").click()

    page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()

    page.get_by_role("button", name="columns").click()

    page.get_by_role("button", name="columns").click()

    page.get_by_role("treeitem", name="First OOS Week Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="No OOS Weeks Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_title("Filter").nth(2).click()

    page.get_by_role("spinbutton", name="Filter Value").fill("5")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_role("option", name="Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.get_by_title("Filter").nth(2).click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("treeitem", name="Est Lost Units Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_title("Filter").nth(3).click()

    page.get_by_role("spinbutton", name="Filter Value").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("4")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_role("option", name="Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.get_by_title("Filter").nth(3).click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("treeitem", name="Estimated Lost Sales ($)").get_by_label("Press SPACE to toggle").check()

    page.get_by_title("Filter").nth(4).click()

    page.get_by_role("spinbutton", name="Filter Value").fill("50")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_role("option", name="Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.get_by_title("Filter").nth(4).click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("checkbox", name="Toggle All Columns Visibility").check()

    page.get_by_role("button", name="columns").click()

    page.locator(".pointer.zeb-adjustments").click()

    page.locator("div").filter(has_text=re.compile(r"^Save Preference$")).nth(1).click()

    with page.expect_download() as download_info:

        page.locator(".icon-color-toolbar-active.zeb-download-underline").click()

    download = download_info.value

    page.locator("a").filter(has_text="2").click()

    page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator("div").filter(has_text=re.compile(r"^View 20 row\(s\)$")).nth(1).click()

    page.get_by_role("gridcell", name=" Baltimore Orioles|LICENSE FRAME COLOR CHROME|N/A|ORANGE").get_by_role("radio").check()



    # ============================================================
    # SECTION: Locations 
    # ============================================================


    page.get_by_text("Show All Locations").click()

    page.get_by_role("button", name="columns").nth(1).click()

    page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()

    page.get_by_role("treeitem", name="First OOS Week Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="No OOS Weeks Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Est Lost Units Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Estimated Lost Sales ($)").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Unrecoverable Lost Units").get_by_label("Press SPACE to toggle").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("100")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("checkbox", name="Toggle All Columns Visibility").check()

    page.get_by_role("button", name="columns").nth(1).click()

    page.locator("div:nth-child(3) > div > .componentParentWrapper > esp-grid-container > esp-card-component > .card-container > .title > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div:nth-child(2) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()

    page.get_by_text("Save Preference").click()

    page.get_by_role("row", name="Location").get_by_role("checkbox").check()

    page.get_by_role("button", name="Apply").nth(1).click()



    # ============================================================
    # SECTION: Monthly Trends
    # ============================================================


    page.locator("svg").get_by_text("Actual Sales & ROY Fcst ($)").click()

    page.locator("svg").get_by_text("Sales Fcst Adjusted ($)", exact=True).click()

    page.get_by_text("GD Sales Fcst Adjusted ($)", exact=True).click()

    page.get_by_text("Non GD Sales Fcst Adjusted ($)").click()

    page.locator("svg").get_by_text("TY Actual Sales ($)").click()

    page.locator("svg").get_by_text("System Sales Fcst ($)").click()

    page.get_by_text("GD Sales Fcst ($)", exact=True).click()

    page.get_by_text("Non GD Sales Fcst ($)").click()

    page.locator("svg").get_by_text("% Change vs LLY").click()

    page.locator("svg").get_by_text("LLY Sales ($)").click()

    page.locator("svg").get_by_text("LY Sales ($)", exact=True).click()

    page.locator("svg").get_by_text("% Change vs LY").click()

    page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()

    page.locator("div:nth-child(6) > .d-flex").first.click()

    page.locator("div:nth-child(6) > .d-flex").first.click()

    page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator("span:nth-child(7) > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").first.click()

    page.get_by_text("Save Preference").click()



    # ============================================================
    # SECTION: Monthly Summary
    # ============================================================


    page.locator("i").nth(3).click()

    page.locator(".ag-row-odd.ag-row-no-focus > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()

    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(4) > .d-flex").click()

    page.locator("div:nth-child(5) > .d-flex").click()

    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100").click()

