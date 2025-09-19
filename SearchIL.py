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

# --- Configuration (Unchanged) ---
VOSK_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'vosk-model-small-en-us-0.15')
DOWNLOAD_PATH = os.path.join(os.path.dirname(__file__), 'downloads')
AUDIO_MP3_PATH = os.path.join(DOWNLOAD_PATH, 'captcha_audio_il.mp3')
SAMPLE_RATE = 16000

# --- Helper Functions (Unchanged) ---
def random_delay(min_s=0.6, max_s=1.3): time.sleep(random.uniform(min_s, max_s))
def humanlike_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.12))
def transcribe_audio(file_path): pass
def check_illinois_dependencies():
    if not os.path.exists(VOSK_MODEL_PATH): return { "error": "Dependency Missing: Vosk Model", "details": "The folder 'vosk-model-small-en-us-0.15' was not found." }
    if not shutil.which('ffmpeg'): return { "error": "Dependency Missing: FFmpeg", "details": "FFmpeg could not be found in your system's PATH." }
    return None

# --- Main Scraper Function ---
def search_il(search_args):
    dependency_error = check_illinois_dependencies()
    if dependency_error:
        return dependency_error
        
    entity_name_to_search = search_args.get("entity_name")
    if not entity_name_to_search:
        return {"error": "Entity name is required for Illinois search."}

    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    driver = None
    
    try:
        # --- START: OPTIMIZATION ---
        # We create options to change the page load strategy.
        options = uc.ChromeOptions()
        # 'eager' tells Selenium not to wait for images/stylesheets to load.
        # It proceeds as soon as the main page structure (DOM) is ready.
        options.page_load_strategy = 'eager'
        
        # Pass the new options to the driver
        driver = uc.Chrome(version_main=139, options=options)
        # --- END: OPTIMIZATION ---

        wait = WebDriverWait(driver, 60)

        driver.get('https://apps.ilsos.gov/businessentitysearch/')
        
        # The script now relies on these specific waits, not the full page load
        wait.until(EC.element_to_be_clickable((By.ID, 'partialWord'))).click()
        
        search_input_selector = (By.ID, 'searchValue')
        wait.until(EC.visibility_of_element_located(search_input_selector))
        search_input = driver.find_element(*search_input_selector)
        humanlike_type(search_input, entity_name_to_search)
        
        search_button_element = driver.find_element(By.ID, 'btnSearch')
        driver.execute_script("arguments[0].click();", search_button_element)

        results_selector_str = 'table.table.table-striped'
        captcha_selector_str = 'iframe[title="reCAPTCHA"]'
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"{results_selector_str}, {captcha_selector_str}")))

        try:
            if driver.find_element(By.CSS_SELECTOR, captcha_selector_str).is_displayed():
                return {"error": "CAPTCHA challenge was presented, which is not currently handled by this script."}
        except:
             pass

        first_result_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"{results_selector_str} > tbody > tr:nth-child(1) a")))
        first_result_link.click()

        details_page_selector = (By.XPATH, "//h4[contains(text(), 'Entity Information')]")
        wait.until(EC.visibility_of_element_located(details_page_selector))

        js_get_value_by_label = """
            const label = arguments[0];
            const allLabels = document.querySelectorAll('div.display-details b');
            for (const b of allLabels) {
                if (b.innerText.trim() === label) {
                    const valueDiv = b.parentElement.nextElementSibling;
                    if (valueDiv) { return valueDiv.innerHTML.replace(/<br\\s*[/]?>/gi, ' ').replace(/\\s+/g, ' ').trim(); }
                }
            }
            return null;
        """
        def get_detail(label):
            return driver.execute_script(js_get_value_by_label, label)

        entity_status_raw = get_detail("Status")
        entity_status = entity_status_raw.split(' on ')[0].strip() if entity_status_raw else None
        
        scraped_data = {
            "entity_name": get_detail("Entity Name"), "registration_date": get_detail("Org. Date/Admission Date"),
            "entity_type": get_detail("Entity Type"), "business_identification_number": get_detail("File Number"),
            "entity_status": entity_status, "statusActive": entity_status and 'active' in entity_status.lower(),
            "address": get_detail("Principal Address")
        }
        
        return [scraped_data]
        
    except TimeoutException:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"illinois_timeout_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "A timeout occurred.", "details": f"Screenshot saved to {screenshot_path}"}
        
    except Exception as e:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"illinois_unexpected_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "An unexpected error occurred.", "details": str(e)}
            
    finally:
        if driver:
            driver.quit()