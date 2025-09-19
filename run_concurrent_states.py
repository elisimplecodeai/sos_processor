# --- IMPORTS ---
import concurrent.futures
import json
import time

# All state search functions from the provided files
from SearchAL import search_al
from SearchAR import search_ar
from SearchAZ import search_az
from SearchCA import search_ca
from SearchCO import search_co
from SearchCT import search_ct
from SearchDE import search_de
from SearchFL import search_fl
from SearchHI import search_hi
from SearchID import search_id
from SearchKY import search_ky
from SearchLA import search_la
from SearchMA import search_ma
from SearchMD import search_md
from SearchME import search_me
from SearchMN import search_mn
from SearchMO import search_mo
from SearchMS import search_ms
from SearchNC import search_nc
from SearchND import search_nd
from SearchNE import search_ne
from SearchNJ import search_nj
from SearchNM import search_nm
from SearchNY import search_ny
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
from SearchWA import search_wa
from SearchWI import search_wi
from SearchWV import search_wv
from SearchWY import search_wy
from SearchAK import search_ak
from SearchGA import search_ga
from SearchIL import search_il
from SearchIN import search_in
from SearchIA import search_ia
from SearchKS import search_ks
from SearchMI import search_mi
from SearchMT import search_mt
from SearchNV import search_nv
from SearchNH import search_nh
from SearchOH import search_oh
from SearchVT import search_vt

# List of all 50 U.S. states
STATE_CODES = [
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
    "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wi", "wv", "wy"
]

# This dictionary maps state codes directly to the search functions.
STATE_SEARCH_FUNCTIONS = {
    "al": search_al,
    "ar": search_ar,
    "az": search_az,
    "ca": search_ca,
    "co": search_co,
    "ct": search_ct,
    "de": search_de,
    "fl": search_fl,
    "hi": search_hi,
    "id": search_id,
    "ky": search_ky,
    "la": search_la,
    "ma": search_ma,
    "md": search_md,
    "me": search_me,
    "mn": search_mn,
    "mo": search_mo,
    "ms": search_ms,
    "nc": search_nc,
    "nd": search_nd,
    "ne": search_ne,
    "nj": search_nj,
    "nm": search_nm,
    "ny": search_ny,
    "or": search_or,
    "pa": search_pa,
    "ri": search_ri,
    "sc": search_sc,
    "tx": search_tx,
    "ut": search_ut,
    "va": search_va,
    "wa": search_wa,
    "wi": search_wi,
    "wv": search_wv,
    "wy": search_wy,
    "ak": search_ak,
    "ga": search_ga,
    "il": search_il,
    "in": search_in,
    "ia": search_ia,
    "ks": search_ks,
    "mi": search_mi,
    "mt": search_mt,
    "nv": search_nv,
    "nh": search_nh,
    "oh": search_oh,
    "ok": search_ok,
    "sd": search_sd,
    "tn": search_tn,
    "vt": search_vt
}

def worker_function(state_code, search_args):
    """A worker function to perform the search for a single state."""
    try:
        print(f"Starting search for {state_code.upper()}...")
        result_data = STATE_SEARCH_FUNCTIONS.get(state_code.lower())(search_args)
        return (state_code, result_data)
    except Exception as e:
        return (state_code, {"error": f"An unexpected error occurred: {str(e)}"})

def main():
    """
    Iterates through all 50 states concurrently and saves all results to a single JSON file.
    """
    search_args = {
        "entity_name": "Google",
        # Add other potential args here if needed
    }
    
    all_results = {}
    
    print(f"Starting concurrent business search for '{search_args['entity_name']}' across all 50 states...")

    # We use a ThreadPoolExecutor for I/O-bound tasks
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Map the worker function to the state codes
        future_to_state = {executor.submit(worker_function, state, search_args): state for state in STATE_CODES}
        
        for future in concurrent.futures.as_completed(future_to_state):
            state_code = future_to_state[future]
            try:
                state_code, result_data = future.result()
                all_results[state_code] = result_data
                print(f"Finished search for {state_code.upper()}.")
            except Exception as exc:
                print(f"Error while processing {state_code.upper()}: {exc}")

    output_filename = "all_states_results_concurrent.json"
    with open(output_filename, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\nAll search results have been saved to '{output_filename}'.")

if __name__ == "__main__":
    main()