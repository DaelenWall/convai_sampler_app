import os
import requests
import json
import pprint
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# === CONFIG ===
CONVAI_API_KEY = os.getenv("CONVAI_API_KEY", "")
CHARACTER_ID = os.getenv("CHARACTER_ID", "")

if not CONVAI_API_KEY:
    raise SystemExit("❌ CONVAI_API_KEY not set (env).")

BASE_URL = "https://api.convai.com/character/narrative"
HEADERS = {
    "CONVAI-API-KEY": CONVAI_API_KEY,
    "Content-Type": "application/json"
}
OUTPUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "narrative_map.json"))
pp = pprint.PrettyPrinter(indent=2)

# === API CALLS ===
def list_sections(character_id):
    url = f"{BASE_URL}/list-sections"
    payload = {"character_id": character_id}
    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    return response.json()  # This is a list

def get_section_details(character_id, section_id):
    url = f"{BASE_URL}/get-section"
    payload = {"character_id": character_id, "section_id": section_id}
    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    return response.json()  # This is a dict

def list_triggers(character_id):
    url = f"{BASE_URL}/list-triggers"
    payload = {"character_id": character_id}
    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    return response.json()  # List[dict] (each has trigger_id, trigger_name, trigger_message, destination_section, ...)

def get_trigger_details(character_id, trigger_id):
    url = f"{BASE_URL}/get-trigger"
    payload = {"character_id": character_id, "trigger_id": trigger_id}
    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    return response.json()  # dict

# === BUILD MAP ===
def build_narrative_map(character_id):
    print("📚 Fetching all narrative sections...")
    sections_list = list_sections(character_id)
    if not isinstance(sections_list, list):
        raise ValueError("❌ list_sections() did not return a list.")

    narrative_map = {
        "sections": {},          # section_id -> full_section (plus normalized fields)
        "triggers": [],          # flat list of trigger dicts
        "triggers_by_destination": {}  # dest_section_id -> [trigger dicts]
    }

    # ---------- Sections ----------
    for section in sections_list:
        section_id = section.get("section_id")
        section_name = section.get("section_name", "Unnamed Section")

        print(f"🔍 Pulling section: {section_name} ({section_id})")
        full_section = get_section_details(character_id, section_id)

        # Normalize a few fields we care about for ANA
        normalized = {
            "section_id": section_id,
            "section_name": full_section.get("section_name", section_name),
            "objective": full_section.get("objective", ""),  # sometimes empty
            "response_text": (full_section.get("response", {}) or {}).get("text", ""),
            # decisions: where Convai usually stores user-facing criteria & next section
            "decisions": []
        }

        decisions = full_section.get("decisions")
        if isinstance(decisions, list):
            for d in decisions:
                if not isinstance(d, dict):
                    continue
                crit = (d.get("criteria") or "").strip()
                next_sid = d.get("next_section") or d.get("destination_section")
                normalized["decisions"].append({
                    "decision_id": d.get("decision_id") or d.get("id"),
                    "criteria": crit,
                    "next_section": next_sid
                })
        else:
            print(f"⚠️ No decisions found for section {section_id}")

        # store the raw too (so we don’t lose anything)
        full_section["_normalized"] = normalized
        narrative_map["sections"][section_id] = full_section

    # ---------- Triggers ----------
    print("🔔 Fetching triggers...")
    trig_list = list_triggers(character_id)
    if not isinstance(trig_list, list):
        raise ValueError("❌ list_triggers() did not return a list.")

    for t in trig_list:
        tid = t.get("trigger_id")
        tname = t.get("trigger_name", "Unnamed Trigger")
        print(f"🔍 Pulling trigger: {tname} ({tid})")
        
        if not tid:
            continue
        trig = get_trigger_details(character_id, tid)

        # Normalize trigger fields for ANA
        norm_trig = {
            "trigger_id": trig.get("trigger_id"),
            "trigger_name": trig.get("trigger_name"),
            "message": trig.get("trigger_message", "") or "",
            "destination_section": trig.get("destination_section"),
            # Convai doesn’t expose source_section in examples; keep a placeholder
            "source_section": trig.get("source_section")  # may be None/absent
        }
        trig["_normalized"] = norm_trig
        narrative_map["triggers"].append(trig)

        # Index by destination for cheap lookups (useful for sanity checks)
        dest = norm_trig["destination_section"]
        if dest:
            narrative_map["triggers_by_destination"].setdefault(dest, []).append(trig)

    print("✅ Done building narrative map.")
    print(f"📊 Sections: {len(narrative_map['sections'])} | Triggers: {len(narrative_map['triggers'])}")
    return narrative_map


# === SAVE TO FILE ===
def save_to_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Narrative map saved to: {path}")

# === MAIN ===
if __name__ == "__main__":
    if CHARACTER_ID == "<YOUR_CHARACTER_ID>":
        print("❌ Please replace <YOUR_CHARACTER_ID> with your actual character ID.")
        exit(1)

    if not CONVAI_API_KEY:
        print("❌ Please set CONVAI_API_KEY in your environment.")
        exit(1)

    try:
        narrative_map = build_narrative_map(CHARACTER_ID)
        save_to_json(narrative_map, OUTPUT_PATH)
    except Exception as e:
        print("❌ Failed to export narrative map:")
        print(e)
