import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import os
import json

def search_ga(search_args):
    """
    Searches the Georgia SOS website using the updated, robust version of the
    undetected_chromedriver scraper.
    """
    entity_name_to_search = search_args.get("entity_name")
    if not entity_name_to_search:
        return {"error": "Entity name is required for Georgia search."}

    driver = None
    try:
        options = uc.ChromeOptions()
        options.page_load_strategy = 'eager'
        driver = uc.Chrome(version_main=139, options=options)
        
        wait = WebDriverWait(driver, 60)

        driver.get('https://ecorp.sos.ga.gov/businesssearch')

        search_input_selector = (By.ID, 'txtBusinessName')
        wait.until(EC.visibility_of_element_located(search_input_selector))
        
        search_input = driver.find_element(*search_input_selector)
        search_input.send_keys(entity_name_to_search)
        time.sleep(0.5)

        search_button_selector = (By.ID, 'btnSearch')
        driver.find_element(*search_button_selector).click()

        # --- Using your new, more robust clicking logic ---
        first_result_selector = (By.CSS_SELECTOR, '#grid_businessList > tbody > tr:nth-child(1) > td > a')
        wait.until(EC.element_to_be_clickable(first_result_selector))
        
        element_to_click = driver.find_element(*first_result_selector)
        driver.execute_script("arguments[0].click();", element_to_click)
        # --- End of robust clicking logic ---
        
        details_loaded_selector = (By.XPATH, "//td[contains(text(), 'Business Information')]")
        wait.until(EC.visibility_of_element_located(details_loaded_selector))

        js_get_value_by_label = """
            const label = arguments[0];
            const allTds = document.querySelectorAll('td');
            for (let i = 0; i < allTds.length; i++) {
                if (allTds[i].innerText.trim() === label) {
                    if (allTds[i + 1]) {
                        return allTds[i + 1].innerText.trim();
                    }
                }
            }
            return null;
        """
        
        def get_detail(label):
            return driver.execute_script(js_get_value_by_label, label)

        entity_status = get_detail("Business Status:")
        
        scraped_data = {
            "entity_name": get_detail("Business Name:"),
            "registration_date": get_detail("Date of Formation / Registration Date:"),
            "entity_type": get_detail("Business Type:"),
            "business_identification_number": get_detail("Control Number:"),
            "entity_status": entity_status,
            "statusActive": "active" in entity_status.lower() if entity_status else False,
            "address": get_detail("Physical Address:")
        }
        
        # Return the data as a list for consistency with other multi-result scrapers
        return [scraped_data]

    except TimeoutException:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"georgia_timeout_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "A timeout occurred, likely due to a page load issue or a missing element.", "details": f"Screenshot saved to {screenshot_path}"}
        
    except Exception as e:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"georgia_unexpected_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "An unexpected error occurred.", "details": str(e)}
            
    finally:
        if driver:
            driver.quit()