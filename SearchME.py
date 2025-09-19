import subprocess
import json
import os
from typing import Dict, Any

def search_me(search_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls a Node.js script to scrape the Maine SOS website by passing the
    entity name as a command-line argument and capturing the JSON output.
    """
    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name is required for Maine search."}

    # Construct the path to the Node.js script relative to this Python file
    script_dir = os.path.dirname(__file__) 
    script_path = os.path.join(script_dir, 'SearchME.js')

    # The command to execute: node SCRIPT_PATH "ENTITY_NAME"
    command = ['node', script_path, entity_name]

    try:
        # Execute the command.
        # - check=True: raises an exception if the script returns a non-zero exit code (i.e., fails)
        # - capture_output=True: captures stdout and stderr
        # - text=True: decodes stdout and stderr as text
        # - timeout: sets a timeout in seconds
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=180 
        )
        
        # The Node.js script's console.log output is in result.stdout
        # We parse this JSON string into a Python dictionary
        return json.loads(result.stdout)

    except subprocess.CalledProcessError as e:
        # This error occurs if the Node.js script exits with an error
        return {
            "error": "The Node.js script for ME failed to execute.",
            "details": e.stderr.strip() # stderr contains error messages from the script
        }
    except subprocess.TimeoutExpired:
        return {"error": "Scraping process for ME timed out after 3 minutes."}
    except FileNotFoundError:
        # This error occurs if 'node' is not installed or not in the system's PATH
        return {"error": "The 'node' command was not found. Please ensure Node.js is installed and in your PATH."}
    except json.JSONDecodeError:
        # This error occurs if the Node.js script outputs something that isn't valid JSON
        return {"error": "Failed to decode JSON from the Node.js script output."}
    except Exception as e:
        # Catch any other unexpected errors
        return {"error": f"An unexpected error occurred: {e}"}