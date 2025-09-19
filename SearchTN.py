import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import random
import os
import json
import subprocess
import vosk
import requests
import shutil

# --- Configuration ---
VOSK_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'vosk-model-small-en-us-0.15')
DOWNLOAD_PATH = os.path.join(os.path.dirname(__file__), 'downloads')
AUDIO_MP3_PATH = os.path.join(os.path.dirname(__file__), 'captcha_audio_tn.mp3')
SAMPLE_RATE = 16000

# --- Helper Functions ---
def random_delay(min_s=0.8, max_s=1.6):
    time.sleep(random.uniform(min_s, max_s))

def humanlike_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))

def check_tennessee_dependencies():
    """Checks for dependencies required by the Tennessee scraper."""
    # Kept for robustness in case the site re-enables a more complex CAPTCHA
    if not os.path.exists(VOSK_MODEL_PATH):
        return { "error": "Dependency Missing: Vosk Model", "details": "The folder 'vosk-model-small-en-us-0.15' was not found." }
    if not shutil.which('ffmpeg'):
        return { "error": "Dependency Missing: FFmpeg", "details": "FFmpeg could not be found in your system's PATH." }
    return None

# --- Main Scraper Function ---
def search_tn(search_args):
    """
    Searches the Tennessee SOS website using undetected_chromedriver.
    """
    dependency_error = check_tennessee_dependencies()
    if dependency_error:
        return dependency_error
        
    entity_name_to_search = search_args.get("entity_name")
    if not entity_name_to_search:
        return {"error": "Entity name is required for Tennessee search."}

    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    driver = None
    
    try:
        driver = uc.Chrome(version_main=139)
        wait = WebDriverWait(driver, 60)
        driver.maximize_window()

        driver.get('https://tncab.tnsos.gov/business-entity-search')

        iframe_selector = (By.ID, 'search-iframe')
        try:
            WebDriverWait(driver, 7).until(EC.frame_to_be_available_and_switch_to_it(iframe_selector))
        except TimeoutException:
            pass # No iframe detected, proceed on main page.

        search_input_selector = (By.CSS_SELECTOR, 'input[placeholder="Business Name"]')
        search_input = wait.until(EC.visibility_of_element_located(search_input_selector))
        humanlike_type(search_input, entity_name_to_search)
        
        time.sleep(6)

        search_button_selector = (By.CSS_SELECTOR, 'button[title="Search"]')
        driver.find_element(*search_button_selector).click()
        
        first_result_button_selector = (By.CSS_SELECTOR, 'table.k-grid-table > tbody > tr:nth-child(1) > td:nth-child(1) > button')
        wait.until(EC.element_to_be_clickable(first_result_button_selector)).click()

        details_modal_selector = (By.ID, 'KendoWindowLevel1')
        wait.until(EC.visibility_of_element_located(details_modal_selector))
        
        def get_detail(label):
            try:
                element = driver.find_element(By.XPATH, f"//div[@id='KendoWindowLevel1']//h4[contains(., '{label}')]")
                return element.text.replace(label, '').replace(':', '').strip()
            except:
                return None
        
        entity_name = driver.find_element(By.CSS_SELECTOR, '#KendoWindowLevel1 h2').text.strip()
        entity_status = get_detail("Status")
        
        try:
            address_header = driver.find_element(By.XPATH, "//div[@id='KendoWindowLevel1']//h4[contains(., 'Principal Office Address')]")
            address_line1 = address_header.find_element(By.XPATH, "./following-sibling::h4[1]").text.strip()
            address_line2 = address_header.find_element(By.XPATH, "./following-sibling::h4[2]").text.strip()
            full_address = f"{address_line1} {address_line2}"
        except:
            full_address = ""
            
        scraped_data = {
            "entity_name": entity_name,
            "registration_date": get_detail("Initial Filing Date"),
            "entity_type": get_detail("Entity Type"),
            "business_identification_number": get_detail("Control Number"),
            "entity_status": entity_status,
            "statusActive": entity_status and 'active' in entity_status.lower(),
            "address": full_address
        }
            
        return [scraped_data]
        
    except TimeoutException:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"tennessee_timeout_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "A timeout occurred, likely due to a page load issue or a missing element.", "details": f"Screenshot saved to {screenshot_path}"}
        
    except Exception as e:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"tennessee_unexpected_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "An unexpected error occurred.", "details": str(e)}
            
    finally:
        if driver:
            driver.quit()