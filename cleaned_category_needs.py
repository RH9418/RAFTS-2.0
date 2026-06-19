import re

from playwright.sync_api import Page, expect





def test_example(page: Page) -> None:
    # --- MFA & Login Wait Block ---
    try: page.goto("https://stage.ftics.esp.antuit.ai/dp/demand-planning/executive-dashboard?workbookId=5&tabIndex=4", timeout=0)
    except: pass
    print("\n" + "="*60)
    input("ACTION REQUIRED: Log in, pass MFA, then PRESS [ENTER]...\n")
    print("="*60 + "\n")




    # ============================================================
    # SECTION: Global Filters
    # ============================================================


    page.locator(".zeb-filter").first.click()

    page.get_by_text("Hierarchy").click()

    page.get_by_text("League").click()

    page.get_by_role("radio", name="MLS").check()

    page.get_by_text("League").click()

    page.get_by_text("Team", exact=True).click()

    page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.get_by_text("Team 6 selected").click()

    page.get_by_text("Department").click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first.click()

    page.get_by_text("Department").click()

    page.get_by_text("Attribute").click()

    page.get_by_text("Product Line").click()

    page.locator(".pointer.custom-checkbox-checked").first.click()

    page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.get_by_text("Player").click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first.click()

    page.locator(".aggrigate-panel > .custom-checkbox-wrapper > .pointer").click()

    page.get_by_role("button", name="Apply Filters").click()

    page.locator(".zeb-filter").first.click()



    # ============================================================
    # SECTION: Category Filters and DropDown
    # ============================================================


    page.locator(".dropdown-caret.p-l-16").first.click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator("#location-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.get_by_role("button", name="Apply").click()



    # ============================================================
    # SECTION: Monthly Summary Grid
    # ============================================================


    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(4) > .d-flex").click()

    page.locator("div:nth-child(5) > .d-flex").click()

    page.locator("div:nth-child(6) > .d-flex").click()

    page.locator("div:nth-child(7) > .d-flex").click()

    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100").click()

    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator("div:nth-child(8) > .d-flex").click()

    page.locator("div:nth-child(9) > .d-flex").click()

    page.locator("div:nth-child(10) > .d-flex").click()

    page.locator("div:nth-child(11) > .d-flex").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.get_by_role("button", name="columns").click()

    page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()

    page.get_by_role("treeitem", name="Feb-26 Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Mar-26 Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Apr-26 Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Apr-26 Column").get_by_label("Press SPACE to toggle").uncheck()

    page.get_by_role("treeitem", name="May-26 Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="May-26 Column").get_by_label("Press SPACE to toggle").uncheck()

    page.get_by_role("treeitem", name="Jul-26 Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Jul-26 Column").get_by_label("Press SPACE to toggle").uncheck()

    page.get_by_role("treeitem", name="Aug-26 Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Aug-26 Column").get_by_label("Press SPACE to toggle").uncheck()

    page.get_by_role("treeitem", name="Sep-26 Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.get_by_role("treeitem", name="Sep-26 Column").get_by_label("Press SPACE to toggle visibility (hidden)").uncheck()

    page.get_by_role("treeitem", name="Oct-26 Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.get_by_role("treeitem", name="Oct-26 Column").get_by_label("Press SPACE to toggle visibility (hidden)").uncheck()

    page.locator("#ag-1797-input").check()

    page.get_by_role("treeitem", name="Nov-26 Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()

    page.locator("#ag-1797-input").check()

    page.get_by_role("button", name="columns").click()

    page.get_by_role("button", name="columns").click()

    page.get_by_role("checkbox", name="Toggle All Columns Visibility").check()

    page.get_by_role("button", name="columns").click()

    page.locator(".pointer.zeb-adjustments").click()

    page.get_by_text("Save Preference").click()

    with page.expect_download() as download_info:

        page.locator(".icon-color-toolbar-active.zeb-download-underline").click()

    download = download_info.value

    page.locator(".dropdown-caret.p-l-16").first.click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.get_by_text("ResetApply").click()

    page.get_by_role("button", name="Apply").click()

    page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container").click()

