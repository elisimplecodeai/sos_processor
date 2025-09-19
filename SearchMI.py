import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import os
import json

def search_mi(search_args):
    """
    Searches the Michigan Business Registry using the original, user-provided
    undetected_chromedriver logic, adapted to work within the main framework.
    """
    entity_name_to_search = search_args.get("entity_name")
    if not entity_name_to_search:
        return {"error": "Entity name is required for Michigan search."}

    driver = None
    try:
        # --- USING YOUR ORIGINAL, WORKING INITIALIZATION ---
        # This forces chromedriver to use a version compatible with Chrome 139
        driver = uc.Chrome(version_main=139)
        # --- END OF ORIGINAL INITIALIZATION ---

        driver.get("https://mibusinessregistry.lara.state.mi.us/search/business")

        wait = WebDriverWait(driver, 90)
        search_input_selector = 'input[placeholder="Search by name or file number"]'
        
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, search_input_selector)))
        
        search_input = driver.find_element(By.CSS_SELECTOR, search_input_selector)
        search_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Execute search"]')

        for char in entity_name_to_search:
            search_input.send_keys(char)
            time.sleep(0.1)

        time.sleep(1)
        search_button.click()

        results_selector = "div.table-wrapper"
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, results_selector)))

        first_result_selector = "table > tbody > tr:nth-child(1) > td:nth-child(1) > div"
        first_result_element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, first_result_selector)))
        first_result_element.click()

        details_table_selector = "div.drawer.show table.details-list" 
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, details_table_selector)))
        
        entity_name = driver.find_element(By.CSS_SELECTOR, "div.drawer.show h2").text
        
        js_get_value_by_label = """
            const label = arguments[0];
            const allLabels = document.querySelectorAll('div.drawer.show td.label');
            for (const el of allLabels) {
                if (el.innerText.trim() === label) {
                    const valueCell = el.nextElementSibling;
                    return valueCell ? valueCell.innerText.trim() : null;
                }
            }
            return null;
        """

        def get_detail(label):
            return driver.execute_script(js_get_value_by_label, label)

        entity_status = get_detail("Entity Status")
        
        scraped_data = {
            "entity_name": entity_name,
            "registration_date": get_detail("Initial Filing Date"),
            "entity_type": get_detail("Entity Type"),
            "business_identification_number": get_detail("Identification #"),
            "entity_status": entity_status,
            "statusActive": "active" in entity_status.lower() if entity_status else False,
            "address": get_detail("Registered Office Street Address")
        }
        
        # Return the data as a list with one item for consistency with other scrapers
        return [scraped_data]

    except TimeoutException:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"michigan_timeout_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "A timeout occurred, likely due to Cloudflare or a missing element.", "details": f"Screenshot saved to {screenshot_path}"}
        
    except Exception as e:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"michigan_unexpected_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "An unexpected error occurred.", "details": str(e)}
            
    finally:
        if driver:
            driver.quit()