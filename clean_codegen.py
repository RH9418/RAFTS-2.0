import re

from playwright.sync_api import Page, expect





def test_example(page: Page) -> None:
    # --- MFA & Login Wait Block ---
    try: page.goto("https://stage.bbu.esp.antuit.ai/dp/demand-planning/executive-dashboard?workbookId=4&tabIndex=1", timeout=0)
    except: pass
    print("\n" + "="*60)
    input("ACTION REQUIRED: Log in, pass MFA, then PRESS [ENTER]...\n")
    print("="*60 + "\n")

    # ============================================================
    # SECTION: Global Filters
    # ============================================================
    page.locator(".zeb-filter").click()
    page.get_by_text("Hierarchy").click()
    page.get_by_text("Brand Level 4").click()
    page.locator(".pointer.custom-checkbox-checked").first.click()
    page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()
    page.locator(".pointer.custom-checkbox-unchecked").first.click()
    page.locator(".pointer.custom-checkbox-unchecked").first.click()
    page.locator(".pointer.custom-checkbox-unchecked").first.click()
    page.locator(".pointer.custom-checkbox-unchecked").first.click()
    page.get_by_text("Brand Level 4").click()
    page.get_by_text("Brand Level 3").click()
    page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()
    page.locator(".pointer.partial-selected").click()
    page.get_by_text("Brand Level 3").click()
    page.get_by_text("Attribute").click()
    page.get_by_text("Product Level 4").click()
    page.locator(".pointer.custom-checkbox-checked").first.click()
    page.locator(".pointer.custom-checkbox-unchecked").first.click()
    page.get_by_text("Product Level 4").click()
    page.locator("esp-simple-side-filter-panel-v1").get_by_text("Location").click()
    page.get_by_text("Hierarchy").click()
    page.get_by_text("Sales Level 6").click()
    page.locator(".pointer.custom-checkbox-checked").first.click()
    page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()
    page.locator(".pointer.custom-checkbox-unchecked").first.click()
    page.locator("div:nth-child(5) > .custom-checkbox-wrapper > .pointer").click()
    page.get_by_text("Sales Level 6").click()
    page.get_by_text("Sales Level 5").click()
    page.locator(".pointer.custom-checkbox-unchecked").first.click()
    page.get_by_text("Sales Level 5").click()
    page.get_by_text("Sales Level 4").click()
    page.locator(".pointer.custom-checkbox-unchecked").first.click()
    page.get_by_text("Sales Level 4").click()
    page.locator("esp-simple-side-filter-panel-v1").get_by_text("Customer").click()
    page.get_by_text("Hierarchy").click()
    page.get_by_text("Customer Level 4").click()
    page.get_by_text("Customer Level 4").click()
    page.locator(".pointer.zeb-check").click()
    page.get_by_role("button", name="Apply Filters").click()
    page.locator(".pointer.custom-checkbox-unchecked").click()
    page.get_by_role("button", name="Apply Filters").click()
    page.locator(".filter-icon-wrapper").click()

    # ============================================================
    # SECTION: Alert Types
    # ============================================================
    page.locator(".dropdown-caret").first.click()
    page.locator("div").filter(has_text=re.compile(r"^Under Bias$")).nth(1).click()
    page.locator(".dropdown-caret").first.click()
    page.locator("div").filter(has_text=re.compile(r"^MAPE$")).nth(1).click()

    # ============================================================
    # SECTION: Alerts Sumary
    # ============================================================
    page.get_by_role("button", name="columns").click()
    page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()
    page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()
    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("129406")
    page.get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_role("button", name="Reset").click()
    page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()
    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("-6.5")
    page.get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_role("button", name="Reset").click()
    page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()
    page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()
    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("21")
    page.locator(".ag-icon.ag-icon-small-down").first.click()
    page.get_by_role("option", name="Greater than or equal to").click()
    page.get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_role("button", name="Reset").click()
    page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()
    page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()
    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("7.2")
    page.get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_role("button", name="Reset").click()
    page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()
    page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)").check()
    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("10")
    page.locator(".ag-icon.ag-icon-small-down").first.click()
    page.get_by_role("option", name="Less than or equal to").click()
    page.get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_role("button", name="Reset").click()
    page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()
    page.locator("div:nth-child(7) > .ag-column-select-column").click()
    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("380906")
    page.get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_role("button", name="Reset").click()
    page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()
    page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()
    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("spinbutton", name="Filter Value").fill("384298")
    page.get_by_role("button", name="Apply").click()
    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()
    page.get_by_role("button", name="Reset").click()
    page.locator("div:nth-child(14) > .ag-column-select-column > .ag-column-select-checkbox > .ag-wrapper").check()
    page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.get_by_role("button", name="columns").click()

    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("100")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_role("option", name="Greater than or equal to").click()

    page.get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()

    page.get_by_role("button", name="Reset").click()

    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("200")

    page.get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()

    page.get_by_role("button", name="Reset").click()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("383")

    page.get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()

    page.get_by_role("button", name="Reset").click()

    page.locator("a").filter(has_text="2").click()

    page.locator("a").filter(has_text="1").click()

    page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.get_by_text("View 20 row(s)").click()

    page.get_by_role("button", name="columns").click()

    page.get_by_role("checkbox", name="Toggle All Columns Visibility").check()

    page.get_by_role("button", name="columns").click()

    page.locator(".pointer.zeb-adjustments").click()

    page.get_by_text("Save Preference").click()

    with page.expect_download() as download_info:

        page.locator(".icon-color-toolbar-active.zeb-download-underline").click()

    download = download_info.value

    page.locator(".pointer.zeb-adjustments").click()

    page.get_by_text("Reset Preference").click()

    page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked)   WALMART STORES HQ").get_by_label("Press Space to toggle row").check()

    page.locator("span").filter(has_text="WALMART STORES HQ").first.click(button="right")

    page.get_by_text("Drill down").click()

    page.locator("span").filter(has_text="WALMART").first.click(button="right")

    page.get_by_text("Drill up").click()

    page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked)   WALMART STORES HQ").get_by_label("Press Space to toggle row").check()

    page.get_by_role("button", name="columns").nth(1).click()

    page.get_by_role("button", name="columns").nth(1).click()

    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("10000")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_role("option", name="Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("20")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_role("option", name="Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("20")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_text("Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("button", name="columns").nth(1).click()

    page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("1000")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_text("Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("20000")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()

    page.get_by_text("Apply Reset Clear").click()

    page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("100000")

    page.locator(".ag-icon.ag-icon-small-down").first.click()

    page.get_by_text("Greater than or equal to").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("65000")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()

    page.get_by_role("spinbutton", name="Filter Value").fill("10000")

    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()

    page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").uncheck()

    page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.locator("div:nth-child(12) > .ag-column-select-column").click()

    page.locator("div:nth-child(3) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()

    page.locator("div").filter(has_text=re.compile(r"^Save Preference$")).first.click()

    page.locator(".checkbox-primary-color").first.check()

    page.locator("span").filter(has_text="BARCEL").first.click(button="right")

    page.get_by_text("Drill down").click()

    page.locator("span").filter(has_text="BARCEL").first.click(button="right")

    page.get_by_text("Drill up").click()

    page.get_by_role("button", name="Apply").click()



    # ============================================================
    # SECTION: Weekly Summary Section
    # ============================================================


    page.locator("#time-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator("div").filter(has_text=re.compile(r"^Latest 5 Next 4$")).nth(1).click()

    page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()

    page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()

    page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()

    page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").click()

    page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").click()

    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(4) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(5) > .d-flex").click()

    page.locator("div:nth-child(6) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(7)").click()

    page.locator("div:nth-child(8) > .d-flex").click()

    page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.zeb-check").first.click()

    page.locator("div:nth-child(9) > .d-flex").click()

    page.locator("div:nth-child(10) > .d-flex").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.get_by_text("All").nth(3).click()

    page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button").click()

    page.get_by_role("treeitem", name="-12-21 (52) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="-12-28 (01) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.get_by_role("treeitem", name="-01-04 (02) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button").click()

    page.locator("svg").get_by_text("User Forecast Total").click()

    page.locator("svg").get_by_text("User Override Total").click()

    page.locator("svg").get_by_text("Aged Net Units").click()

    page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()

    page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()

    page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()

    page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()

    page.locator(".overflow-auto > div:nth-child(7)").click()

    page.locator(".overflow-auto > div:nth-child(8)").click()

    page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()

    page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()

    page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator("path:nth-child(78)").click()

    page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()

    page.get_by_text("Save Preference").click()

    page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()

    page.get_by_text("Reset Preference").click()

    page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-1.ag-row-position-absolute.ag-row-hover > div:nth-child(4) > span > div").click()

    # ============================================================
    # SECTION: Events Grid
    # ============================================================
    page.locator("div:nth-child(4) > span > .align-middle").click()
    page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content").click()
    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("textbox", name="Filter Value").fill("Promotion-WM BARCEL TAKIS 10CT ROLLBACK 122925 TO 033026")
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1).click(button="right")
    page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1).click()
    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()
    page.get_by_role("textbox", name="Filter Value").fill("TOR")
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.locator("a").nth(2).click()
    page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button").click()
    page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()
    page.get_by_role("treeitem", name="Event Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()
    page.get_by_role("treeitem", name="UPC 12 Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()
    page.get_by_role("treeitem", name="Customer Level 2 Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()
    page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button").click()
    page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content > esp-row-dimentional-grid > div > #paginationId > esp-pagination-v2 > .d-flex.w-100 > span:nth-child(3) > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()
    page.locator("div").filter(has_text=re.compile(r"^View 20 row\(s\)$")).nth(1).click()

