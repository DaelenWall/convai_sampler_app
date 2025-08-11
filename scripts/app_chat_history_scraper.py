import requests
import csv
import os
import time
import json
import shutil
from datetime import datetime

API_KEY = os.getenv("CONVAI_API_KEY", "")
CHAR_ID = os.getenv("CHARACTER_ID", "")

if not API_KEY or not CHAR_ID:
    raise ValueError("Missing CONVAI_API_KEY or CHARACTER_ID. Set them as environment variables or pass them in.")

HEADERS = {
    "CONVAI-API-KEY": API_KEY,
    "Content-Type": "application/json"
}

SESSIONS_URL = "https://api.convai.com/character/chatHistory/list"
DETAILS_URL = "https://api.convai.com/character/chatHistory/details"

# === STEP 1: Fetch sessions on or after start_date ===
def fetch_recent_sessions(start_date=""):
    response = requests.post(SESSIONS_URL, headers=HEADERS, json={
        "charID": CHAR_ID,
        "limit": "-1"
    })
    response.raise_for_status()
    all_sessions = response.json()

    cutoff = datetime.fromisoformat(start_date)
    filtered_sessions = []

    print(f"🔍 Checking timestamps for {len(all_sessions)} sessions since {start_date}...\n")

    for idx, sess in enumerate(all_sessions):
        sid = sess["sessionID"]
        try:
            details = fetch_session_details(sid)
            if not details:
                print(f"[{idx+1}/{len(all_sessions)}] ⏭️ Skipping session {sid} (empty details)")
                continue

            first_msg_time = details[0].get("timestamp")
            if not first_msg_time:
                print(f"[{idx+1}/{len(all_sessions)}] ⚠️ Skipping session {sid} (missing timestamp)")
                continue

            ts_obj = datetime.fromisoformat(first_msg_time.replace("Z", "+00:00"))

            if ts_obj >= cutoff:
                print(f"[{idx+1}/{len(all_sessions)}] ✅ Included session {sid} ({ts_obj})")
                filtered_sessions.append(sess)
            else:
                print(f"[{idx+1}/{len(all_sessions)}] 🛑 Hit first session before {start_date}, stopping at {ts_obj}")
                break  # EARLY EXIT

        except Exception as e:
            print(f"[{idx+1}/{len(all_sessions)}] ❌ Error checking session {sid}: {e}")
            continue

        time.sleep(0.2)

    print(f"\n✅ Finished filtering. {len(filtered_sessions)} sessions match criteria.\n")
    return filtered_sessions


# === STEP 2: Fetch chat details for a given session ID ===
def fetch_session_details(session_id):
    response = requests.post(DETAILS_URL, headers=HEADERS, json={
        "charID": CHAR_ID,
        "sessionID": session_id
    })
    response.raise_for_status()
    return response.json()  # This returns a list of message dicts

# === STEP 3: Write results to CSV ===
def write_transcripts_to_csv(sessions):

    os.makedirs("../data", exist_ok=True)
    filepath = "../data/convai_full_history.csv"

    with open(filepath, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)

        writer.writerow([
            "Session ID", "Timestamp", "User Input", "Character Response",
            "Is Trigger Input"
        ])

        for session in sessions:
            sid = session["sessionID"]
            print(f"📦 Fetching session: {sid}")

            try:
                details = fetch_session_details(sid)

                for turn in details:
                    user_input = ""
                    character_response = ""

                    for entry in turn.get("interaction", []):
                        if entry["speaker"] == "User":
                            user_input = entry["message"]
                        elif entry["speaker"] == "Character":
                            character_response = entry["message"]

                    writer.writerow([
                        sid,
                        turn.get("timestamp", "UNKNOWN"),
                        user_input.replace('\n', ' ').strip(),
                        character_response.replace('\n', ' ').strip(),
                        turn.get("is_trigger_input", False)
                    ])

                # Debug one sample
                # print(json.dumps(turn, indent=2))
                # exit()

            except Exception as e:
                print(f"❌ Error fetching details: {e}")

            time.sleep(0.2)

    print(f"\n✅ CSV export complete → {filepath}")

# === MAIN ===
if __name__ == "__main__":
    from datetime import datetime
    import shutil

    start_date = "2025-08-05"  # Change this to your desired start date
    print(f"🔄 Fetching sessions from {start_date} onward...")
    sessions = fetch_recent_sessions(start_date=start_date)

    print(f"✅ Found {len(sessions)} recent sessions. Downloading transcripts...")
    write_transcripts_to_csv(sessions)
    print("📁 All transcripts saved to: exports/convai_full_history.csv")

    # === 📦 Save snapshot with timestamp and range ===
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    timestamp = f"{start_date}_to_{now}"

    os.makedirs("exports", exist_ok=True)
    snapshot_filename = f"exports/convai_history_{timestamp}.csv"

    shutil.copyfile("../data/convai_full_history.csv", snapshot_filename)
    print(f"📁 Snapshot saved as: {snapshot_filename}")
