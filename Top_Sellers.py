import re
from playwright.sync_api import Page, expect


def test_example(page: Page) -> None:
    page.locator(".zeb-filter").first.click()
    page.get_by_text("Hierarchy").click()
    page.locator("#SideFilterproducthierarchyId").get_by_text("League").click()
    page.get_by_role("radio", name="MLS").check()
    page.locator("#SideFilterproducthierarchyId").get_by_text("Team").click()
    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first.click()
    page.locator("#SideFilterproducthierarchyId").get_by_text("Team", exact=True).click()
    page.get_by_text("Department").click()
    page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()
    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()
    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()
    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()
    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()
    page.get_by_text("Attribute").click()
    page.locator("#SideFilterproductattributeId").get_by_text("Product Line").click()
    page.get_by_text("Player").click()
    page.locator(".aggrigate-panel > .custom-checkbox-wrapper > .pointer").click()
    page.get_by_role("button", name="Apply Filters").click()
    page.locator(".zeb-filter").first.click()
    page.get_by_role("textbox", name="e.g. Global Filters").click()
    page.get_by_role("textbox", name="e.g. Global Filters").fill("Top Seller Filters and Dropdowns")
    page.get_by_role("button", name="Add Section").click()
    page.locator(".dropdown-caret.p-l-16").first.click()
    page.locator(".d-flex.flex-column.justify-content-center").first.click()
    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()
    page.locator("#location-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()
    page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()
    page.locator(".d-flex.flex-column.justify-content-center").first.click()
    page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()
    page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()
    page.get_by_role("button", name="Apply").click()
    page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()
    page.get_by_text("View 10 row(s)").click()
    page.get_by_role("button", name="columns").click()
    page.get_by_role("checkbox", name="Toggle All Columns Visibility").check()
    page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()
    page.get_by_role("treeitem", name="League Column").get_by_label("Press SPACE to toggle").check()
    page.get_by_role("treeitem", name="Department Column").get_by_label("Press SPACE to toggle").check()
    page.get_by_title("Filter").nth(2).click()
    page.get_by_role("textbox", name="Filter Value").fill("MENS")
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.get_by_title("Filter").nth(2).click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.get_by_role("treeitem", name="Department Column").get_by_label("Press SPACE to toggle").uncheck()
    page.get_by_role("treeitem", name="Class Column").get_by_label("Press SPACE to toggle").check()
    page.get_by_title("Filter").nth(2).click()
    page.get_by_role("textbox", name="Filter Value").press("CapsLock")
    page.get_by_role("textbox", name="Filter Value").press("CapsLock")
    page.get_by_role("textbox", name="Filter Value").fill("SS TEES")
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.get_by_title("Filter").nth(2).click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.get_by_role("treeitem", name="Product Line Column").get_by_label("Press SPACE to toggle").check()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_role("textbox", name="Filter Value").fill("CORE")
    page.locator(".ag-icon.ag-icon-small-down").first.click()
    page.get_by_role("option", name="Does not contain").click()
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.get_by_role("treeitem", name="Product Line Column").get_by_label("Press SPACE to toggle").uncheck()
    page.get_by_role("treeitem", name="PID Column").get_by_label("Press SPACE to toggle").check()
    page.get_by_role("treeitem", name="PID Column").get_by_label("Press SPACE to toggle").uncheck()
    page.get_by_role("treeitem", name="LW Retail Sales Column", exact=True).get_by_label("Press SPACE to toggle").check()
    page.get_by_role("treeitem", name="LW Retail Sales Column", exact=True).get_by_label("Press SPACE to toggle").uncheck()
    page.get_by_role("treeitem", name="LY LW Retail Sales Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_role("spinbutton", name="Filter Value").fill("10")
    page.locator(".ag-icon.ag-icon-small-down").first.click()
    page.get_by_role("option", name="Greater than or equal to").click()
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.get_by_role("treeitem", name="LY LW Retail Sales Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()
    page.get_by_role("treeitem", name="LY to TY LW Retail % Var").get_by_label("Press SPACE to toggle visibility (hidden)").check()
    page.get_by_role("treeitem", name="LY to TY LW Retail % Var").get_by_label("Press SPACE to toggle visibility (hidden)").uncheck()
    page.locator("#ag-937-input").check()
    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()
    page.get_by_role("treeitem", name="L2W Unit Sales Column", exact=True).get_by_label("Press SPACE to toggle").check()
    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()
    page.get_by_role("treeitem", name="LY L2W Unit Sales Column").get_by_label("Press SPACE to toggle").check()
    page.get_by_role("treeitem", name="LY L2W Unit Sales Column").get_by_label("Press SPACE to toggle").uncheck()
    page.get_by_role("treeitem", name="LY L4W Unit Sales Column").click()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_role("spinbutton", name="Filter Value").fill("20")
    page.locator(".ag-icon.ag-icon-small-down").first.click()
    page.get_by_role("option", name="Greater than or equal to").click()
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()
    page.locator("#ag-955-input").check()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_role("spinbutton", name="Filter Value").fill("200")
    page.locator(".ag-icon.ag-icon-small-down").first.click()
    page.get_by_role("option", name="Less than or equal to").click()
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()
    page.get_by_role("treeitem", name="+ PIDS Column").click()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_role("spinbutton", name="Filter Value").fill("1")
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()
    page.locator("#ag-1794-input").check()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_role("spinbutton", name="Filter Value").fill("0")
    page.locator(".ag-icon.ag-icon-small-down").first.click()
    page.get_by_role("option", name="Does not equal").click()
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()
    page.locator("#ag-2449-input").check()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_role("spinbutton", name="Filter Value").fill("100")
    page.locator(".ag-icon.ag-icon-small-down").first.click()
    page.get_by_role("option", name="Greater than or equal to").click()
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)").uncheck()
    page.get_by_role("treeitem", name="Over/Under Column").click()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_role("spinbutton", name="Filter Value").fill("75")
    page.locator(".ag-icon.ag-icon-small-down").first.click()
    page.get_by_role("option", name="Does not equal").click()
    page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()
    page.get_by_title("Filter").nth(3).click()
    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()
    page.get_by_role("treeitem", name="In Stock % Column").click()
    page.get_by_role("treeitem", name="In Stock Weighted % Column").click()
    page.locator(".pointer.zeb-adjustments").click()
    page.get_by_text("Save Preference").click()
    page.locator(".icon-color-toolbar-active.zeb-download-underline").click()
    page.locator("div").filter(has_text="Loading...").nth(5).click()
    page.locator("a").filter(has_text="2").click()
    page.get_by_role("treegrid").get_by_text("League").click()
    page.get_by_text("Over/Under").click()
    page.get_by_text("In Stock %").click()
    page.get_by_text("Over/Under").click()
    page.locator("a").filter(has_text="3").click()
    page.locator("a").filter(has_text="...").click()
    page.get_by_role("tooltip", name="Go to").get_by_role("textbox").click()
    page.get_by_role("tooltip", name="Go to").get_by_role("textbox").fill("100")
    page.get_by_role("tooltip", name="Go to").get_by_role("textbox").press("Enter")
    page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()
    page.locator("div").filter(has_text=re.compile(r"^View 20 row\(s\)$")).nth(1).click()
    page.locator(".pointer.zeb-adjustments").click()
    page.get_by_role("button", name="columns").click()
    page.get_by_role("checkbox", name="Toggle All Columns Visibility").check()
    page.get_by_role("button", name="columns").click()
    page.locator(".pointer.zeb-adjustments").click()
    page.get_by_text("Save Preference").click()
