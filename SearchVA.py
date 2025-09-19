import subprocess
import json
import os
import sys

def get_chrome_executable_path():
    """Tries to find the default path for Google Chrome on the current OS."""
    if sys.platform == 'win32':
        for path in [
            os.path.join(os.environ["ProgramFiles"], "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ["ProgramFiles(x86)"], "Google", "Chrome", "Application", "chrome.exe"),
        ]:
            if os.path.exists(path):
                return path
    elif sys.platform == 'darwin': # macOS
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(path):
            return path
    elif sys.platform == 'linux':
        path = "/usr/bin/google-chrome"
        if os.path.exists(path):
            return path
    return None

def search_va(search_args):
    """
    Calls the Node.js script to scrape the Virginia SCC website.
    This script requires a local installation of Google Chrome.
    """
    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name is required for Virginia search."}

    chrome_path = get_chrome_executable_path()
    if not chrome_path:
        return {"error": "Google Chrome installation not found. Puppeteer-core requires Chrome to be installed in its default location."}

    script_dir = os.path.dirname(__file__)
    script_path = os.path.join(script_dir, 'SearchVA.js')
    output_filename = os.path.join(script_dir, 'virginia_output.json')

    command = f'node "{script_path}" "{entity_name}" "{output_filename}" "{chrome_path}"'

    try:
        subprocess.run(
            command, check=True, capture_output=True, text=True,
            timeout=180, shell=True
        )
        if os.path.exists(output_filename):
            with open(output_filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {"error": "Node.js script did not produce an output file."}

    except subprocess.CalledProcessError as e:
        return {"error": "Node.js script for VA failed.", "details": e.stderr}
    except subprocess.TimeoutExpired:
        return {"error": "Scraping process for VA timed out after 3 minutes."}
    except FileNotFoundError:
        return {"error": "The 'node' command was not found. Please ensure Node.js is installed."}
    finally:
        if os.path.exists(output_filename):
            os.remove(output_filename)