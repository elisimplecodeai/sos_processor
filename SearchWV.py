import subprocess
import json
import os

def search_wv(search_args):
    """
    Calls the Node.js script to scrape the West Virginia SOS website.
    This implementation scrapes the details of up to the first 5 results found.
    """
    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name is required for West Virginia search."}

    script_dir = os.path.dirname(__file__)
    script_path = os.path.join(script_dir, 'SearchWV.js')
    output_filename = os.path.join(script_dir, 'west_virginia_output.json')

    # IMPORTANT: The command must now be a single string when using shell=True
    # We need to properly quote the arguments to handle spaces in names or paths.
    command = f'node "{script_path}" "{entity_name}" "{output_filename}"'

    try:
        # Execute the Node.js script within a system shell
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
            shell=True  # <-- THIS IS THE FIX
        )

        if os.path.exists(output_filename):
            with open(output_filename, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
            return result_data
        else:
            return {"error": "Node.js script did not produce an output file."}

    except subprocess.CalledProcessError as e:
        # Include stderr in the error for better debugging
        return {"error": "Node.js script failed", "details": e.stderr}
    except subprocess.TimeoutExpired:
        return {"error": "Scraping process timed out after 3 minutes."}
    except FileNotFoundError:
        return {"error": "The 'node' command was not found. Please ensure Node.js is installed and in your system's PATH."}
    finally:
        if os.path.exists(output_filename):
            os.remove(output_filename)