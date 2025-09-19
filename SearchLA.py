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

# --- Configuration (kept for warm-up routine) ---
VOSK_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'vosk-model-small-en-us-0.15')
DOWNLOAD_PATH = os.path.join(os.path.dirname(__file__), 'downloads')
AUDIO_MP3_PATH = os.path.join(DOWNLOAD_PATH, 'captcha_audio_la.mp3')
SAMPLE_RATE = 16000

# --- Helper Functions ---
def random_delay(min_s=0.8, max_s=1.6):
    time.sleep(random.uniform(min_s, max_s))

def humanlike_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))

def transcribe_audio(file_path):
    wav_file_path = os.path.join(os.path.dirname(file_path), 'audio_la.wav')
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
    try:
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, 'iframe[title="reCAPTCHA"]')))
        wait.until(EC.element_to_be_clickable((By.ID, 'recaptcha-anchor'))).click()
        driver.switch_to.default_content()
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, 'iframe[title*="recaptcha challenge"]')))
        wait.until(EC.element_to_be_clickable((By.ID, 'recaptcha-audio-button'))).click()
        audio_url = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.rc-audiochallenge-tdownload-link'))).get_attribute('href')
        response = requests.get(audio_url, stream=True)
        with open(AUDIO_MP3_PATH, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk: f.write(chunk)
        solution_text = transcribe_audio(AUDIO_MP3_PATH)
        if not solution_text: raise Exception("Audio transcription failed.")
        driver.find_element(By.ID, 'audio-response').send_keys(solution_text)
        wait.until(EC.element_to_be_clickable((By.ID, 'recaptcha-verify-button'))).click()
        driver.switch_to.default_content()
    except Exception as e:
        raise Exception(f"An error occurred during CAPTCHA solving: {e}")

def check_louisiana_dependencies():
    """Checks for dependencies required by the warm-up routine."""
    if not os.path.exists(VOSK_MODEL_PATH):
        return { "error": "Dependency Missing: Vosk Model", "details": "The folder 'vosk-model-small-en-us-0.15' was not found." }
    if not shutil.which('ffmpeg'):
        return { "error": "Dependency Missing: FFmpeg", "details": "FFmpeg could not be found in your system's PATH." }
    return None

# --- Main Scraper Function ---
def search_la(search_args):
    dependency_error = check_louisiana_dependencies()
    if dependency_error:
        return dependency_error

    entity_name_to_search = search_args.get("entity_name")
    if not entity_name_to_search:
        return {"error": "Entity name is required for Louisiana search."}

    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    driver = None
    
    try:
        driver = uc.Chrome(version_main=139)
        wait = WebDriverWait(driver, 60)
        driver.maximize_window()

        driver.get("https://www.google.com")
        search_bar = wait.until(EC.visibility_of_element_located((By.NAME, 'q')))
        humanlike_type(search_bar, "louisiana secretary of state business search")
        search_bar.submit()
        time.sleep(2.5)
        if "/sorry/index" in driver.current_url:
            solve_google_captcha(driver, wait)

        google_result_selector = (By.CSS_SELECTOR, "a[href*='coraweb.sos.la.gov']")
        wait.until(EC.element_to_be_clickable(google_result_selector)).click()

        search_input_selector = (By.ID, 'ctl00_cphContent_txtEntityName')
        wait.until(EC.visibility_of_element_located(search_input_selector))
        
        search_input = driver.find_element(*search_input_selector)
        humanlike_type(search_input, entity_name_to_search)
        
        search_button_selector = (By.ID, 'btnSearch')
        search_button = driver.find_element(*search_button_selector)
        driver.execute_script("arguments[0].click();", search_button)
        
        results_list_selector = (By.ID, 'ctl00_cphContent_pnlSearchResults')
        details_page_selector = (By.ID, 'ctl00_cphContent_lblDetails')
        no_results_selector = (By.ID, 'ctl00_cphContent_lblNoRecords')

        wait.until(EC.any_of(
            EC.visibility_of_element_located(results_list_selector),
            EC.visibility_of_element_located(details_page_selector),
            EC.visibility_of_element_located(no_results_selector)
        ))

        try:
            driver.find_element(*results_list_selector)
            first_result_selector = (By.CSS_SELECTOR, 'table[id*="grdSearchResults"] > tbody > tr:nth-child(2) input[type="submit"]')
            wait.until(EC.element_to_be_clickable(first_result_selector)).click()
        except NoSuchElementException:
            try:
                driver.find_element(*no_results_selector)
                return []
            except NoSuchElementException:
                pass # Landed directly on details page
        
        wait.until(EC.visibility_of_element_located(details_page_selector))

        def get_text_by_id(element_id):
            try:
                return driver.find_element(By.ID, element_id).text.strip()
            except:
                return None

        entity_status = get_text_by_id('ctl00_cphContent_lblCurrentStatus')
        address1 = get_text_by_id('ctl00_cphContent_lblApplicantAddress1')
        address2 = get_text_by_id('ctl00_cphContent_lblApplicantCSZ')
        full_address = f"{address1} {address2}".replace('  ', ' ').strip() if address1 and address2 else ""

        scraped_data = {
            "entity_name": get_text_by_id('ctl00_cphContent_lblServiceName'),
            "registration_date": get_text_by_id('ctl00_cphContent_lblRegistrationDate'),
            "entity_type": get_text_by_id('ctl00_cphContent_lblTypesRegistered'),
            "business_identification_number": get_text_by_id('ctl00_cphContent_lblBookNumber'),
            "entity_status": entity_status,
            "statusActive": entity_status and 'active' in entity_status.lower(),
            "address": full_address
        }
        
        return [scraped_data]
            
    except Exception as e:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"louisiana_unexpected_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "An unexpected error occurred.", "details": str(e)}
            
    finally:
        if driver:
            driver.quit()