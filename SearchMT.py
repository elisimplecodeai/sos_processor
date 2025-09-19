import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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
AUDIO_MP3_PATH = os.path.join(DOWNLOAD_PATH, 'captcha_audio_mt.mp3')
SAMPLE_RATE = 16000

# --- Helper Functions ---
def random_delay(min_s=0.8, max_s=1.6):
    time.sleep(random.uniform(min_s, max_s))

def humanlike_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))

def transcribe_audio(file_path):
    # ... (full transcribe_audio logic) ...
    wav_file_path = os.path.join(os.path.dirname(file_path), 'audio_mt.wav')
    ffmpeg_command = f'ffmpeg -i "{file_path}" -ar {SAMPLE_RATE} -ac 1 "{wav_file_path}" -y'
    subprocess.run(ffmpeg_command, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    model = vosk.Model(VOSK_MODEL_PATH)
    rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    with open(wav_file_path, "rb") as wf:
        while True:
            data = wf.read(4000)
            if len(data) == 0: break
            rec.AcceptWaveform(data)
    result = json.loads(rec.FinalResult())
    os.remove(wav_file_path)
    return result['text']

def solve_google_captcha(driver, wait):
    # ... (full solve_google_captcha logic) ...
    try:
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, 'iframe[title="reCAPTCHA"]')))
        wait.until(EC.element_to_be_clickable((By.ID, 'recaptcha-anchor'))).click()
        driver.switch_to.default_content()
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, 'iframe[title*="recaptcha challenge"]')))
        wait.until(EC.element_to_be_clickable((By.ID, 'recaptcha-audio-button'))).click()
        audio_link_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.rc-audiochallenge-tdownload-link')))
        audio_url = audio_link_element.get_attribute('href')
        response = requests.get(audio_url, stream=True)
        with open(AUDIO_MP3_PATH, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk: f.write(chunk)
        solution_text = transcribe_audio(AUDIO_MP3_PATH)
        if not solution_text: raise Exception("Audio transcription failed.")
        driver.find_element(By.ID, 'audio-response').send_keys(solution_text)
        wait.until(EC.element_to_be_clickable((By.ID, 'recaptcha-verify-button'))).click()
        driver.switch_to.default_content()
        wait.until(EC.visibility_of_element_located((By.ID, 'search')))
    except Exception as e:
        raise Exception(f"An error occurred during CAPTCHA solving: {e}")

def check_montana_dependencies():
    """Checks for dependencies required by the Montana scraper."""
    if not os.path.exists(VOSK_MODEL_PATH):
        return { "error": "Dependency Missing: Vosk Model", "details": "The folder 'vosk-model-small-en-us-0.15' was not found." }
    if not shutil.which('ffmpeg'):
        return { "error": "Dependency Missing: FFmpeg", "details": "FFmpeg could not be found in your system's PATH." }
    return None

# --- Main Scraper Function ---
def search_mt(search_args):
    dependency_error = check_montana_dependencies()
    if dependency_error:
        return dependency_error
        
    entity_name_to_search = search_args.get("entity_name")
    if not entity_name_to_search:
        return {"error": "Entity name is required for Montana search."}

    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    driver = None
    
    try:
        driver = uc.Chrome(version_main=139)
        wait = WebDriverWait(driver, 60)

        # Warm-up routine
        driver.get("https://www.google.com")
        search_bar = wait.until(EC.visibility_of_element_located((By.NAME, 'q')))
        humanlike_type(search_bar, "montana secretary of state business search")
        search_bar.submit()
        time.sleep(2.5)
        if "/sorry/index" in driver.current_url:
            solve_google_captcha(driver, wait)
        
        google_result_selector = (By.CSS_SELECTOR, "a[href*='biz.sosmt.gov']")
        wait.until(EC.element_to_be_clickable(google_result_selector)).click()

        # Interaction on target site
        search_input_selector = (By.CSS_SELECTOR, 'input[placeholder*="Search by name"]')
        wait.until(EC.visibility_of_element_located(search_input_selector))
        
        search_input = driver.find_element(*search_input_selector)
        humanlike_type(search_input, entity_name_to_search)
        random_delay()

        driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Execute search"]').click()

        first_result_row_selector = (By.CSS_SELECTOR, 'tr.div-table-row:nth-of-type(1)')
        no_results_selector = (By.XPATH, "//p[contains(text(), 'No results found matching your criteria')]")
        wait.until(EC.any_of(EC.visibility_of_element_located(first_result_row_selector), EC.visibility_of_element_located(no_results_selector)))

        try:
            clickable_button_selector = (By.CSS_SELECTOR, 'tr.div-table-row:nth-of-type(1) .interactive-cell-button')
            element_to_click = wait.until(EC.element_to_be_clickable(clickable_button_selector))
            driver.execute_script("arguments[0].click();", element_to_click)
            
            details_table_selector = (By.CSS_SELECTOR, '.inner-drawer table.details-list')
            wait.until(EC.visibility_of_element_located(details_table_selector))

            def get_detail_by_label(label):
                try:
                    element = driver.find_element(By.XPATH, f"//table[contains(@class, 'details-list')]//td[normalize-space()='{label}']/following-sibling::td[1]")
                    return element.text.strip()
                except: return None
            
            status = get_detail_by_label('Status')
            address = get_detail_by_label('Mailing Address') or get_detail_by_label('Principal Address') or ''
            
            scraped_data = {
                "entity_name": driver.find_element(By.CSS_SELECTOR, "div.drawer.show h4").text,
                "registration_date": get_detail_by_label('Registration Date'),
                "entity_type": get_detail_by_label('Entity Type'),
                "business_identification_number": get_detail_by_label('Filing Number'),
                "entity_status": status,
                "statusActive": status and 'active' in status.lower(),
                "address": address if address != 'N/A' else ''
            }
            return [scraped_data]

        except (NoSuchElementException, TimeoutException):
            return [] # Return empty list for no results
        
    except Exception as e:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"montana_unexpected_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "An unexpected error occurred.", "details": str(e)}
            
    finally:
        if driver:
            driver.quit()