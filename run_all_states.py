import asyncio
import json
import os
from datetime import datetime

# Import every state's primary search function
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
from SearchLA import search_la
from SearchMA import search_ma
from SearchMD import search_md
from SearchME import search_me
from SearchMI import search_mi
from SearchMN import search_mn
from SearchMO import search_mo
from SearchMS import search_ms
from SearchMT import search_mt
from SearchNC import search_nc
from SearchND import search_nd
from SearchNE import search_ne
from SearchNH import search_nh
from SearchNJ import search_nj
from SearchNM import search_nm
from SearchNV import search_nv
from SearchNY import search_ny
from SearchOH import search_oh
from SearchOK import search_ok
from SearchOR import search_or
from SearchPA import search_pa
from SearchRI import search_ri
from SearchSC import search_sc
from SearchSD import search_sd
from SearchTN import search_tn
from SearchTX import search_tx
from SearchUT import search_ut
from SearchVA import search_va
from SearchVT import search_vt
from SearchWA import search_wa
from SearchWI import search_wi
from SearchWV import search_wv
from SearchWY import search_wy

# The dispatch table remains the same
STATE_SEARCH_FUNCTIONS = {
    "ak": search_ak, "al": search_al, "ar": search_ar, "az": search_az, "ca": search_ca,
    "co": search_co, "ct": search_ct, "de": search_de, "fl": search_fl, "ga": search_ga,
    "hi": search_hi, "ia": search_ia, "id": search_id, "il": search_il, "in": search_in,
    "ks": search_ks, "ky": search_ky, "la": search_la, "ma": search_ma, "md": search_md,
    "me": search_me, "mi": search_mi, "mn": search_mn, "mo": search_mo, "ms": search_ms,
    "mt": search_mt, "nc": search_nc, "nd": search_nd, "ne": search_ne, "nh": search_nh,
    "nj": search_nj, "nm": search_nm, "nv": search_nv, "ny": search_ny, "oh": search_oh,
    "ok": search_ok, "or": search_or, "pa": search_pa, "ri": search_ri, "sc": search_sc,
    "sd": search_sd, "tn": search_tn, "tx": search_tx, "ut": search_ut, "va": search_va,
    "vt": search_vt, "wa": search_wa, "wi": search_wi, "wv": search_wv, "wy": search_wy,
}

async def run_scraper(state_code, search_function, search_args):
    """Asynchronously runs a single scraper and handles its errors."""
    print(f"Searching in {state_code.upper()}...")
    try:
        # We now 'await' the result from every scraper function
        result = await search_function(search_args)
        print(f"Finished search in {state_code.upper()}.")
        return state_code, result
    except Exception as e:
        print(f"Error searching in {state_code.upper()}: {e}")
        return state_code, {"error": f"An unexpected error occurred: {e}"}

async def main():
    """
    Asynchronously runs all state scrapers for a given entity name.
    """
    # Replace with user input if desired
    entity_name_input = "google" 
    print(f"--- Starting All-State Search for: '{entity_name_input}' ---")
    
    search_args = {"entity_name": entity_name_input}
    
    # Create a list of tasks to run concurrently
    tasks = [run_scraper(code, func, search_args) for code, func in STATE_SEARCH_FUNCTIONS.items()]

    # Run all tasks at once
    results = await asyncio.gather(*tasks)
    
    # Process the results into a final dictionary
    all_results = {state_code: result for state_code, result in results}

    # Save the final aggregated results
    output_dir = os.path.join(os.path.dirname(__file__), "all_state_results")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_filename = os.path.join(output_dir, f"results_{timestamp}.json")

    with open(output_filename, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n--- Search Complete. All results saved to: {output_filename} ---")

# This is the standard way to run a top-level async function
if __name__ == "__main__":
    # On Windows, a specific policy is needed for asyncio to work with subprocesses
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())