import subprocess
import json
import os
import shutil # Used to check for ffmpeg

def check_nebraska_dependencies():
    """Checks for dependencies required by the Nebraska scraper."""
    # 1. Check for Vosk model folder
    script_dir = os.path.dirname(__file__)
    model_path = os.path.join(script_dir, 'vosk-model-small-en-us-0.15')
    if not os.path.exists(model_path):
        return {
            "error": "Dependency Missing: Vosk Model",
            "details": "The folder 'vosk-model-small-en-us-0.15' was not found. "
                       "Please download the small English model from the Vosk website and "
                       "unzip it into the same directory as the scripts."
        }
    
    # 2. Check if ffmpeg is in the system's PATH
    if not shutil.which('ffmpeg'):
        return {
            "error": "Dependency Missing: FFmpeg",
            "details": "FFmpeg could not be found in your system's PATH. "
                       "Please install FFmpeg and ensure it's accessible from your command line."
        }
    
    return None # All dependencies are present

def search_ne(search_args):
    """
    Calls the Node.js script to scrape the Nebraska SOS website.
    This is a complex scraper that solves an audio reCAPTCHA.
    """
    # First, check for external dependencies
    dependency_error = check_nebraska_dependencies()
    if dependency_error:
        return dependency_error

    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name is required for Nebraska search."}

    script_dir = os.path.dirname(__file__)
    script_path = os.path.join(script_dir, 'SearchNE.js')
    output_filename = os.path.join(script_dir, 'nebraska_output.json')

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
        return {"error": "Node.js script for NE failed.", "details": e.stderr}
    except subprocess.TimeoutExpired:
        return {"error": "Scraping process for NE timed out after 4 minutes."}
    except FileNotFoundError:
        return {"error": "The 'node' command was not found. Please ensure Node.js is installed."}
    finally:
        if os.path.exists(output_filename):
            os.remove(output_filename)