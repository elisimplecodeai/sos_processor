import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from faker import Faker
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

# --- Main Scraper Function ---
def search_ok(search_args):
    """
    Searches the Oklahoma SOS website using undetected_chromedriver.
    This scraper bypasses a gatekeeper page by providing fake credentials.
    """
    entity_name_to_search = search_args.get("entity_name")
    if not entity_name_to_search:
        return {"error": "Entity name is required for Oklahoma search."}

    driver = None
    try:
        driver = uc.Chrome(version_main=139)
        wait = WebDriverWait(driver, 60)
        driver.maximize_window()
        
        fake = Faker()

        driver.get('https://www.sos.ok.gov/corp/corpInquiryFind.aspx')

        search_input_selector = (By.ID, 'ctl00_DefaultContent_CorpNameSearch1__singlename')
        wait.until(EC.visibility_of_element_located(search_input_selector))
        
        search_input = driver.find_element(*search_input_selector)
        humanlike_type(search_input, entity_name_to_search)
        
        random_delay(5, 8)

        search_button_selector = (By.ID, 'ctl00_DefaultContent_CorpNameSearch1_SearchButton')
        driver.find_element(*search_button_selector).click()

        first_result_selector = (By.CSS_SELECTOR, '#ctl00_DefaultContent_CorpNameSearch1_EntityGridView > div > table > tbody > tr:nth-child(1) > td:nth-child(1) > a')
        wait.until(EC.element_to_be_clickable(first_result_selector)).click()

        name_input_selector = (By.ID, 'ctl00_DefaultContent_txtName')
        wait.until(EC.visibility_of_element_located(name_input_selector))
        
        name_input = driver.find_element(*name_input_selector)
        email_input = driver.find_element(By.ID, 'ctl00_DefaultContent_txtUserName')
        
        humanlike_type(name_input, fake.name())
        random_delay()
        humanlike_type(email_input, fake.free_email())
        random_delay()

        continue_button_selector = (By.ID, 'ctl00_DefaultContent_Button1')
        driver.find_element(*continue_button_selector).click()

        details_page_selector = (By.ID, 'printDiv') 
        wait.until(EC.visibility_of_element_located(details_page_selector))
        
        def get_detail_by_label(label_text):
            try:
                element = driver.find_element(By.XPATH, f"//dt[normalize-space(.)='{label_text}']/following-sibling::dd[1]")
                return element.text.strip()
            except:
                return None
                
        try:
            entity_name = driver.find_element(By.CSS_SELECTOR, '#printDiv > h3').text.strip()
        except:
            entity_name = None

        entity_status = get_detail_by_label("Status:")
        
        try:
            address_line1 = get_detail_by_label("Address:")
            address_line2 = get_detail_by_label("City, State , ZipCode:")
            full_address = f"{address_line1}, {address_line2}" if address_line1 and address_line2 else (address_line1 or address_line2 or "")
        except:
            full_address = ""
            
        scraped_data = {
            "entity_name": entity_name,
            "registration_date": get_detail_by_label("Formation Date:"),
            "entity_type": get_detail_by_label("Corp type:"),
            "business_identification_number": get_detail_by_label("Filing Number:"),
            "entity_status": entity_status,
            "statusActive": "active" in entity_status.lower() if entity_status else False,
            "address": full_address
        }
        
        return [scraped_data]
        
    except TimeoutException:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"oklahoma_timeout_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "A timeout occurred, likely due to a page load issue or a missing element.", "details": f"Screenshot saved to {screenshot_path}"}
        
    except Exception as e:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"oklahoma_unexpected_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "An unexpected error occurred.", "details": str(e)}
            
    finally:
        if driver:
            driver.quit()