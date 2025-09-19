import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import random
import os
import json

# --- Helper Functions ---
def random_delay(min_s=0.8, max_s=1.5):
    time.sleep(random.uniform(min_s, max_s))

def humanlike_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))

# --- Custom Wait Condition Class ---
# This reliably waits for AJAX content to populate in an input field.
class wait_for_value_to_populate(object):
    def __init__(self, locator):
        self.locator = locator

    def __call__(self, driver):
        try:
            element = driver.find_element(*self.locator)
            element_value = element.get_attribute("value")
            # Return the element only if the value is not "Loading" and not empty
            if element_value and element_value.strip().lower() != "loading":
                return element
            else:
                return False
        except:
            return False

# --- Main Scraper Function ---
def search_oh(search_args):
    """
    Searches the Ohio SOS website using undetected_chromedriver with a custom
    wait condition for AJAX-loaded content.
    """
    entity_name_to_search = search_args.get("entity_name")
    if not entity_name_to_search:
        return {"error": "Entity name is required for Ohio search."}

    driver = None
    try:
        driver = uc.Chrome(version_main=139)
        wait = WebDriverWait(driver, 60)
        driver.maximize_window()

        driver.get('https://businesssearch.ohiosos.gov/#BusinessNameDiv')

        search_input_selector = (By.ID, 'bSearch')
        wait.until(EC.visibility_of_element_located(search_input_selector))
        
        search_input = driver.find_element(*search_input_selector)
        humanlike_type(search_input, entity_name_to_search)
        random_delay()

        search_button_selector = (By.CSS_SELECTOR, '#BusinessNameDiv input.srchBtn')
        driver.find_element(*search_button_selector).click()

        results_table_selector = (By.ID, 'srch-table')
        wait.until(EC.visibility_of_element_located(results_table_selector))
        
        first_result_button_selector = (By.CSS_SELECTOR, 'table#srch-table > tbody > tr:nth-child(1) > td:last-child > a')
        wait.until(EC.element_to_be_clickable(first_result_button_selector)).click()

        details_modal_selector = (By.ID, 'busDialog')
        wait.until(EC.visibility_of_element_located(details_modal_selector))
        
        # Use the custom wait condition for the charter number field
        wait.until(wait_for_value_to_populate((By.ID, 'charter_num')))

        def get_value_from_input(element_id):
            try:
                return driver.find_element(By.ID, element_id).get_attribute('value')
            except:
                return None

        entity_status = get_value_from_input('status')
        
        scraped_data = {
            "entity_name": get_value_from_input('business_name'),
            "registration_date": get_value_from_input('effect_date'),
            "entity_type": get_value_from_input('business_type'),
            "business_identification_number": get_value_from_input('charter_num'),
            "entity_status": entity_status,
            "statusActive": "active" in entity_status.lower() if entity_status else False,
            "address": get_value_from_input('business_locationcountystate') or ""
        }
        
        # Return the data as a list for consistency
        return [scraped_data]
        
    except TimeoutException:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"ohio_timeout_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "A timeout occurred, likely due to a page load issue or a missing element.", "details": f"Screenshot saved to {screenshot_path}"}
        
    except Exception as e:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"ohio_unexpected_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "An unexpected error occurred.", "details": str(e)}
            
    finally:
        if driver:
            driver.quit()