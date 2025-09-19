import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import random
import os
import json

# --- Helper Functions (Unchanged) ---
def random_delay(min_s=0.8, max_s=1.6):
    time.sleep(random.uniform(min_s, max_s))

def humanlike_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))

# --- Main Scraper Function ---
def search_nv(search_args):
    """
    Searches the Nevada SOS website using undetected_chromedriver with a warm-up routine.
    This version uses a robust JavaScript click to navigate to the details page.
    """
    entity_name_to_search = search_args.get("entity_name")
    if not entity_name_to_search:
        return {"error": "Entity name is required for Nevada search."}

    driver = None
    try:
        driver = uc.Chrome(version_main=139)
        wait = WebDriverWait(driver, 60)

        driver.get("https://www.google.com")
        random_delay()

        driver.get('https://esos.nv.gov/EntitySearch/OnlineEntitySearch')

        search_input_selector = (By.ID, 'BusinessSearch_Index_txtEntityName')
        wait.until(EC.visibility_of_element_located(search_input_selector))
        
        search_input = driver.find_element(*search_input_selector)
        humanlike_type(search_input, entity_name_to_search)
        random_delay()

        search_button_selector = (By.ID, 'btnSearch')
        driver.find_element(*search_button_selector).click()

        # --- THIS IS THE FIX ---
        # 1. Use a more robust wait condition: element_to_be_clickable.
        first_result_selector = (By.CSS_SELECTOR, 'tr.highlightRow a')
        wait.until(EC.element_to_be_clickable(first_result_selector))
        
        # 2. Find the element.
        element_to_click = driver.find_element(*first_result_selector)
        
        # 3. Use a direct JavaScript click for maximum reliability.
        driver.execute_script("arguments[0].click();", element_to_click)
        # --- END OF FIX ---
        
        details_page_selector = (By.XPATH, "//label[contains(text(), 'Entity Information')]")
        wait.until(EC.visibility_of_element_located(details_page_selector))

        js_get_value_by_label = """
            const label = arguments[0];
            const allLabels = document.querySelectorAll('label.control-label');
            for (const el of allLabels) {
                if (el.innerText.trim() === label) {
                    const valueDiv = el.parentElement.nextElementSibling;
                    return valueDiv ? valueDiv.innerText.trim() : null;
                }
            }
            return null;
        """

        def get_detail(label):
            return driver.execute_script(js_get_value_by_label, label)

        entity_status = get_detail("Entity Status:")
        
        try:
            address = driver.find_element(By.XPATH, "//label[contains(text(), 'Street Address:')]/parent::div/following-sibling::div").text
        except:
            address = None

        scraped_data = {
            "entity_name": get_detail("Entity Name:"),
            "registration_date": get_detail("Formation Date:"),
            "entity_type": get_detail("Entity Type:"),
            "business_identification_number": get_detail("Entity Number:"),
            "entity_status": entity_status,
            "statusActive": "active" in entity_status.lower() if entity_status else False,
            "address": address
        }
        
        return [scraped_data]

    except TimeoutException:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"nevada_timeout_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "A timeout occurred, likely due to a security challenge or a missing element.", "details": f"Screenshot saved to {screenshot_path}"}
        
    except Exception as e:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"nevada_unexpected_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "An unexpected error occurred.", "details": str(e)}
            
    finally:
        if driver:
            driver.quit()