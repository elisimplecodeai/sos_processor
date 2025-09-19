import requests
from datetime import datetime

def search_ny(search_args):
    """
    Searches the NY business database using their API.
    If multiple results are found, it returns the full details of the top result.
    """
    dos_id = search_args.get("state_filing_number")
    entity_name = search_args.get("entity_name")
    if not dos_id and not entity_name:
        return {"error": "DOS ID or entity name required for New York search."}

    # Reverted to the exact headers from the original script
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://apps.dos.ny.gov",
        "Referer": "https://apps.dos.ny.gov/publicInquiry/",
        "User-Agent": "Mozilla/5.0"
    }

    def format_date(raw):
        """Helper to format dates into a consistent mm/dd/yyyy format."""
        if not raw: return "N/A"
        try:
            dt = datetime.fromisoformat(raw); return f"{dt.month:02d}/{dt.day:02d}/{dt.year}"
        except (ValueError, TypeError):
            try:
                dt = datetime.strptime(raw, "%m/%d/%Y"); return f"{dt.month:02d}/{dt.day:02d}/{dt.year}"
            except (ValueError, TypeError):
                return raw or "N/A"

    def build_final_dict(name="N/A", reg_date="N/A", entity_type="N/A", dos_num="N/A", status="N/A", address="N/A"):
        """A simple helper to assemble the final dictionary, as per the original script's structure."""
        is_active = status and status.upper() == "ACTIVE"
        return {
            "entity_name": name if name else "N/A",
            "registration_date": reg_date if reg_date else "N/A",
            "entity_type": entity_type if entity_type else "N/A",
            "business_identification_number": dos_num if dos_num else "N/A",
            "entity_status": status if status else "N/A",
            "statusActive": is_active,
            "address": address.strip() if address and address.strip() else "N/A"
        }

    if dos_id:
        # --- Direct lookup by DOS ID. This logic is now restored to mirror the original script. ---
        dos_id = dos_id.strip()
        url = "https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetEntityRecordByID"
        for length in range(len(dos_id), 11):
            padded_id = dos_id.zfill(length)
            payload = {"AssumedNameFlag": "false", "SearchID": padded_id}
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=20)
                response.raise_for_status()
                data = response.json()
                
                if (data.get("requestStatus") == "Success" and data.get("resultIndicator") != "InvalidID" and data.get("entityGeneralInfo")):
                    entity_info = data.get("entityGeneralInfo")
                    
                    # Step 1: Extract general info
                    name = entity_info.get("entityName")
                    reg_date = format_date(entity_info.get("dateOfInitialDosFiling") or entity_info.get("effectiveDateInitialFiling"))
                    entity_type = entity_info.get("entityType")
                    dos_num = entity_info.get("dosID", padded_id)
                    status = entity_info.get("entityStatus")

                    # Step 2: Extract address info from its specific object
                    address_info = data.get("addressInformation", {})
                    business_address = (
                        address_info.get("serviceOfProcessAddress")
                        or address_info.get("principalExecutiveOfficeAddress")
                        or address_info.get("entityPrimaryLocationAddress")
                        or "N/A"
                    )

                    # Step 3: Build the final response from the extracted parts
                    return build_final_dict(name, reg_date, entity_type, dos_num, status, business_address)

            except requests.RequestException as e:
                return {"error": f"Request failed while fetching details by ID: {e}"}
        return {"error": f"No entity found for DOS ID '{dos_id}'."}

    elif entity_name:
        # --- Search by name, then use the ID of the top result ---
        entity_name = entity_name.strip()
        url = "https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetComplexSearchMatchingEntities"
        payload = {
            "searchValue": entity_name, "searchByTypeIndicator": "EntityName", "searchExpressionIndicator": "BeginsWith",
            "entityStatusIndicator": "AllStatuses", "entityTypeIndicator": ["Corporation", "LimitedLiabilityCompany", "LimitedPartnership", "LimitedLiabilityPartnership"],
            "listPaginationInfo": {"listStartRecord": 1, "listEndRecord": 50}
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()
            results = data.get("entitySearchResultList", [])

            if not results:
                return {"error": f"No results found for entity name '{entity_name}'."}

            top_result = results[0]
            top_dos_id = top_result.get("dosID")
            if not top_dos_id:
                return {"error": "Top search result was missing a DOS ID needed for detail lookup."}

            return search_ny({"state_filing_number": top_dos_id})

        except requests.RequestException as e:
            return {"error": f"Request failed during name search: {e}"}