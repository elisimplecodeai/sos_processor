import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import random
import os
import sys # Import sys to check the operating system
import json
import subprocess
import vosk
import requests
import shutil

# --- Configuration (kept for CAPTCHA routine) ---
VOSK_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'vosk-model-small-en-us-0.15')
DOWNLOAD_PATH = os.path.join(os.path.dirname(__file__), 'downloads')
AUDIO_MP3_PATH = os.path.join(DOWNLOAD_PATH, 'captcha_audio_md.mp3')
SAMPLE_RATE = 16000

# --- Helper Functions ---
def humanlike_type(driver, selector, text):
    element = driver.find_element(*selector)
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.12))

def transcribe_audio(file_path):
    wav_file_path = os.path.join(os.path.dirname(file_path), 'audio_md.wav')
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

def check_maryland_dependencies():
    """Checks for dependencies required by the CAPTCHA routine."""
    if not os.path.exists(VOSK_MODEL_PATH):
        return { "error": "Dependency Missing: Vosk Model", "details": "The folder 'vosk-model-small-en-us-0.15' was not found." }
    if not shutil.which('ffmpeg'):
        return { "error": "Dependency Missing: FFmpeg", "details": "FFmpeg could not be found in your system's PATH." }
    return None

# --- *** NEW HELPER FUNCTION TO FIND CHROME *** ---
def get_chrome_executable_path():
    """Finds the default path for Google Chrome to help undetected_chromedriver."""
    if sys.platform == 'win32': # For Windows
        for path in [
            os.path.join(os.environ["ProgramFiles(x86)"], "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ["ProgramFiles"], "Google", "Chrome", "Application", "chrome.exe"),
        ]:
            if os.path.exists(path):
                return path
    elif sys.platform == 'linux': # For Linux (including WSL)
        for path in ["/usr/bin/google-chrome-stable", "/usr/bin/google-chrome"]:
             if os.path.exists(path):
                return path
    # Add macOS path if needed
    # elif sys.platform == 'darwin':
    #     path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    #     if os.path.exists(path):
    #         return path
    return None

# --- Main Scraper Function ---
def search_md(search_args):
    dependency_error = check_maryland_dependencies()
    if dependency_error:
        return dependency_error

    entity_name_to_search = search_args.get("entity_name")
    if not entity_name_to_search:
        return {"error": "Entity name is required for Maryland search."}

    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    driver = None
    
    try:
        chrome_path = get_chrome_executable_path()
        if not chrome_path:
            return {"error": "Could not find Google Chrome executable. Please ensure it is installed."}

        # --- THIS IS THE FIX ---
        # We now explicitly provide the path to the Chrome browser.
        driver = uc.Chrome(browser_executable_path=chrome_path)
        # --- END OF FIX ---
        
        wait = WebDriverWait(driver, 45)

        driver.get('https://egov.maryland.gov/BusinessExpress/EntitySearch')

        humanlike_type(driver, (By.ID, 'BusinessName'), entity_name_to_search)
        driver.find_element(By.ID, 'searchBus1').click()

        results_table_selector = (By.ID, 'newTblBusSearch')
        try:
            WebDriverWait(driver, 15).until(EC.visibility_of_element_located(results_table_selector))
        except TimeoutException:
            try:
                # ... (rest of the CAPTCHA logic remains the same) ...
                try:
                    short_wait = WebDriverWait(driver, 5)
                    anchor_frame = short_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'iframe[src*="api2/anchor"]')))
                    driver.switch_to.frame(anchor_frame)
                    wait.until(EC.element_to_be_clickable((By.ID, 'recaptcha-anchor'))).click()
                    driver.switch_to.default_content()
                except TimeoutException:
                    driver.switch_to.default_content()
                
                bframe_handle = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'iframe[src*="api2/bframe"]')))
                driver.switch_to.frame(bframe_handle)
                audio_button_element = wait.until(EC.element_to_be_clickable((By.ID, 'recaptcha-audio-button')))
                driver.execute_script("arguments[0].click();", audio_button_element)
                time.sleep(3) 
                driver.switch_to.default_content()
                driver.switch_to.frame(bframe_handle)
                
                audio_url = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.rc-audiochallenge-tdownload-link'))).get_attribute('href')
                response = requests.get(audio_url, stream=True)
                with open(AUDIO_MP3_PATH, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk: f.write(chunk)
                solution_text = transcribe_audio(AUDIO_MP3_PATH)
                if not solution_text: raise Exception("Transcription failed.")
                
                driver.find_element(By.ID, 'audio-response').send_keys(solution_text)
                wait.until(EC.element_to_be_clickable((By.ID, 'recaptcha-verify-button'))).click()
                driver.switch_to.default_content()
                wait.until(EC.visibility_of_element_located(results_table_selector))
            except Exception as e:
                raise Exception(f"CAPTCHA solver failed: {e}")

        original_window = driver.current_window_handle
        first_result_selector = (By.CSS_SELECTOR, '#newTblBusSearch > tbody > tr:nth-child(1) > td:nth-child(2) > a')
        wait.until(EC.element_to_be_clickable(first_result_selector)).click()
        
        wait.until(EC.number_of_windows_to_be(2))
        for window_handle in driver.window_handles:
            if window_handle != original_window:
                driver.switch_to.window(window_handle)
                break
        
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.fp_formItemGroup')))
        
        js_get_value_by_label = """
            const label = arguments[0];
            const allLabels = document.querySelectorAll('div.fp_formItem strong');
            for (const strongEl of allLabels) {
                if (strongEl.innerText.trim().replace(':', '') === label) {
                    let valueEl = strongEl.parentElement.nextElementSibling;
                    if (valueEl && (valueEl.classList.contains('fp_formItemData') || valueEl.querySelector('.fp_formItemData'))) {
                         valueEl = valueEl.querySelector('.fp_formItemData') || valueEl;
                    }
                    if (valueEl) {
                        return valueEl.innerHTML.replace(/<br\\s*[/]?>/gi, ' ').replace(/\\s+/g, ' ').trim();
                    }
                }
            }
            return null;
        """

        def get_detail(label):
            return driver.execute_script(js_get_value_by_label, label)

        entity_name_b = get_detail("Business Name")
        owner_details = get_detail("Owner")
        address_po = get_detail("Principal Office")
        entity_status = get_detail("Status")
        entity_name, address = None, None

        if entity_name_b:
            entity_name = entity_name_b
        elif owner_details:
            parts = owner_details.split(); name_parts = []; address_start_index = -1
            for i, part in enumerate(parts):
                if part.isdigit() and len(part) > 2:
                    address_start_index = i; break
                name_parts.append(part)
            if address_start_index != -1:
                entity_name = ' '.join(name_parts); address = ' '.join(parts[address_start_index:])
            else:
                entity_name = owner_details
        if address_po:
            address = address_po

        scraped_data = {
            "entity_name": entity_name,
            "registration_date": get_detail("Date of Formation/ Registration"),
            "entity_type": get_detail("Business Type"),
            "business_identification_number": get_detail("Department ID Number"),
            "entity_status": entity_status,
            "statusActive": entity_status and 'active' in entity_status.lower(),
            "address": address or ""
        }
        
        driver.close()
        driver.switch_to.window(original_window)
        
        return [scraped_data]
            
    except Exception as e:
        error_dir = os.path.join(os.path.dirname(__file__), "errors")
        os.makedirs(error_dir, exist_ok=True)
        screenshot_path = os.path.join(error_dir, f"maryland_unexpected_error_{int(time.time())}.png")
        if driver: driver.save_screenshot(screenshot_path)
        return {"error": "An unexpected error occurred.", "details": str(e)}
            
    finally:
        if driver:
            driver.quit()