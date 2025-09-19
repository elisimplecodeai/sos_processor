import subprocess
import json
import os

def search_az(search_args):
    """
    Calls the Node.js script to scrape the Arizona Corporation Commission website.
    This scraper handles 'too many results' and targets the first result found.
    """
    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name is required for Arizona search."}

    script_dir = os.path.dirname(__file__)
    script_path = os.path.join(script_dir, 'SearchAZ.js')
    output_filename = os.path.join(script_dir, 'arizona_output.json')

    command = f'node "{script_path}" "{entity_name}" "{output_filename}"'

    try:
        subprocess.run(
            command, check=True, capture_output=True, text=True,
            timeout=120, shell=True # 2-minute timeout
        )
        if os.path.exists(output_filename):
            with open(output_filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {"error": "Node.js script did not produce an output file."}

    except subprocess.CalledProcessError as e:
        # Check if the Node.js script explicitly returned an error (e.g., "Too many results")
        if "Too many results" in e.stdout or "Too many results" in e.stderr:
            return {"error": "Search returned too many results. Please refine your search for Arizona."}
        return {"error": "Node.js script for AZ failed.", "details": e.stderr}
    except subprocess.TimeoutExpired:
        return {"error": "Scraping process for AZ timed out after 2 minutes."}
    except FileNotFoundError:
        return {"error": "The 'node' command was not found. Please ensure Node.js is installed."}
    finally:
        if os.path.exists(output_filename):
            os.remove(output_filename)