import sys
import os

# --- IMPORTS ---
# It's good practice to group imports and sort them alphabetically
from SearchAK import search_ak
from SearchAL import search_al
from SearchAR import search_ar
from SearchAZ import search_az
from SearchCA import search_ca
from SearchCO import search_co
from SearchCT import search_ct
from SearchDE import search_de
from SearchFL import search_fl
from SearchGA import search_ga
from SearchHI import search_hi
from SearchIA import search_ia
from SearchID import search_id
from SearchIL import search_il
from SearchIN import search_in 
from SearchKS import search_ks
from SearchKY import search_ky
from SearchLA import search_la # Note: Python convention is lowercase filenames (search_la.py)
from SearchMA import search_ma
from SearchMD import search_md
from SearchME import search_me
from SearchMI import search_mi 
from SearchMN import search_mn
from SearchMO import search_mo
from SearchMS import search_ms
from SearchMT import search_mt
from SearchNM import search_nm
from SearchNC import search_nc
from SearchND import search_nd
from SearchNE import search_ne
from SearchNH import search_nh
from SearchNJ import search_nj
from SearchNY import search_ny
from SearchNV import search_nv
from SearchOH import search_oh
from SearchOK import search_ok
from SearchOR import search_or
from SearchPA import search_pa
from SearchRI import search_ri
from SearchSC import search_sc
from SearchSD import search_sd # Not working yet
from SearchTN import search_tn
from SearchTX import search_tx
from SearchUT import search_ut
from SearchVA import search_va
from SearchVT import search_vt 
from SearchWA import search_wa
from SearchWI import search_wi
from SearchWV import search_wv
from SearchWY import search_wy

import json

# --- DISPATCH TABLE ---
# This dictionary maps state codes directly to the functions that handle them.
# This replaces the entire if/elif chain.
STATE_SEARCH_FUNCTIONS = {
    "ak": search_ak,
    "al": search_al,
    "ar": search_ar,
    "az": search_az,
    "ca": search_ca,
    "co": search_co,
    "ct": search_ct,
    "de": search_de,
    "fl": search_fl,
    "ga": search_ga,
    "hi": search_hi,
    "ia": search_ia,
    "id": search_id,
    "il": search_il,
    "in": search_in,
    "ks": search_ks,
    "ky": search_ky,
    "la": search_la,
    "ma": search_ma,
    "md": search_md,
    "me": search_me,
    "mi": search_mi,
    "mn": search_mn,
    "mo": search_mo,
    "ms": search_ms,
    "mt": search_mt,
    "nc": search_nc,
    "nd": search_nd,
    "ne": search_ne,
    "nh": search_nh,
    "nj": search_nj,
    "nm": search_nm,
    "nv": search_nv,
    "ny": search_ny,
    "oh": search_oh,
    "ok": search_ok,
    "or": search_or,
    "pa": search_pa,
    "ri": search_ri,
    "sd": search_sd,
    "sc": search_sc,
    "tn": search_tn,
    "tx": search_tx,
    "ut": search_ut,
    "va": search_va,
    "vt": search_vt,
    "wa": search_wa,
    "wi": search_wi,
    "wv": search_wv,
    "wy": search_wy,
    # Add new states here - it's clean and easy!
}

def search_business_by_state(state_code, search_args):
    """
    Looks up the state code in the dispatch table and calls the correct function.
    """
    state_code = state_code.lower()
    
    # Get the function from the dictionary. If not found, 'None' is returned.
    search_function = STATE_SEARCH_FUNCTIONS.get(state_code)
    
    if search_function:
        # If the function was found, call it
        return search_function(search_args)
    else:
        # If not found, return a consistent error dictionary
        return {"error": f"State {state_code.upper()} is not supported."}

def main():
    """
    Prompts the user for a state and entity name, then runs the search,
    displaying only the clean final result.
    """
    while True:
        state_code_input = input("Enter the two-letter state code: ").lower().strip()
        if len(state_code_input) == 2 and state_code_input.isalpha():
            break
        print("Invalid input. Please enter a two-letter state code.")

    while True:
        entity_name_input = input("Enter the business entity name to search for: ").strip()
        if entity_name_input:
            break
        print("Entity name cannot be empty.")

    print(f"\nSearching for '{entity_name_input}' in {state_code_input.upper()}...")
    
    search_args = {
        "entity_name": entity_name_input,
    }

    # --- THIS IS THE UPDATED LOGIC ---
    # Save the original standard error stream
    original_stderr = sys.stderr
    # Redirect stderr to a null device to hide tracebacks from libraries
    sys.stderr = open(os.devnull, 'w')

    try:
        # The result will now always be a Python dictionary or list
        result_data = search_business_by_state(state_code_input, search_args)
    finally:
        # CRITICAL: Always restore the original stderr, even if the scraper crashes.
        # This ensures your program can report other errors normally.
        sys.stderr.close()
        sys.stderr = original_stderr
    # --- END OF UPDATED LOGIC ---

    # Directly convert the final Python object to a formatted JSON string for printing
    print(json.dumps(result_data, indent=2))

if __name__ == "__main__":
    main()