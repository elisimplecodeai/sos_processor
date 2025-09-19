import subprocess
import json
import os
import shutil

def check_kansas_dependencies():
    """Checks for dependencies required by the Kansas scraper (ffmpeg, Vosk model)."""
    script_dir = os.path.dirname(__file__)
    model_path = os.path.join(script_dir, 'vosk-model-small-en-us-0.15')
    if not os.path.exists(model_path):
        return {
            "error": "Dependency Missing: Vosk Model",
            "details": "The folder 'vosk-model-small-en-us-0.15' was not found. "
                       "Please download the small English model from the Vosk website and "
                       "unzip it into the same directory as the scripts."
        }
    
    if not shutil.which('ffmpeg'):
        return {
            "error": "Dependency Missing: FFmpeg",
            "details": "FFmpeg could not be found in your system's PATH. "
                       "Please install FFmpeg and ensure it's accessible from your command line."
        }
    
    return None # All dependencies are present

def search_ks(search_args):
    """
    Calls the Node.js script to scrape the Kansas SOS website.
    This is a complex scraper that solves an audio reCAPTCHA.
    """
    dependency_error = check_kansas_dependencies()
    if dependency_error:
        return dependency_error

    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name is required for Kansas search."}

    script_dir = os.path.dirname(__file__)
    script_path = os.path.join(script_dir, 'SearchKS.js')
    output_filename = os.path.join(script_dir, 'kansas_output.json')

    command = f'node "{script_path}" "{entity_name}" "{output_filename}"'

    try:
        subprocess.run(
            command, check=True, capture_output=True, text=True,
            timeout=240, shell=True # 4-minute timeout for this complex task
        )
        if os.path.exists(output_filename):
            with open(output_filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {"error": "Node.js script did not produce an output file."}

    except subprocess.CalledProcessError as e:
        return {"error": "Node.js script for KS failed.", "details": e.stderr}
    except subprocess.TimeoutExpired:
        return {"error": "Scraping process for KS timed out after 4 minutes."}
    except FileNotFoundError:
        return {"error": "The 'node' command was not found. Please ensure Node.js is installed."}
    finally:
        if os.path.exists(output_filename):
            os.remove(output_filename)