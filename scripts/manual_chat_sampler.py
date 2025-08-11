import requests
import csv
import time

# === CONFIGURATION ===
API_KEY = "38d5a3e2db0d1ef967973ea2e6e7cd96"
CHARACTER_ID = "2dd49c8a-0053-11f0-9e5c-42010a7be01a"

MESSAGES = [
    "Hello, DK.",
    "I found both the oxygen and batteries!"
]

NUM_CONVERSATIONS = 3
OUTPUT_CSV = "../data/manual_chat_responses.csv"
API_URL = "https://api.convai.com/character/getResponse"

# === FUNCTION TO GET A RESPONSE ===
def get_response(session_id, user_input):
    headers = {
        "accept": "application/json",
        "CONVAI-API-KEY": API_KEY,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    payload = {
        "charID": CHARACTER_ID,
        "sessionID": session_id,
        "userText": user_input,
    }

    try:
        response = requests.post(API_URL, headers=headers, data=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error: {e} — Status code: {getattr(response, 'status_code', 'N/A')}")
        return {"text": "ERROR", "sessionID": session_id}

# === Safe API call ===
MAX_RETRIES = 5
BASE_BACKOFF = 2  # seconds

def safe_post(url, payload, timeout=60):
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            wait = BASE_BACKOFF * (2 ** attempt)  # exponential: 2s, 4s, 8s, ...
            print(f"⚠️ Retry {attempt + 1}/{MAX_RETRIES} failed: {e} — retrying in {wait}s")
            time.sleep(wait)
    print("❌ All retries failed.")
    return {"error": "Failed after retries"}

# === MAIN SCRIPT ===
def run_sampling():
    with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Conversation #", "Session ID", "Prompt #", "Prompt", "Response"])

        for i in range(NUM_CONVERSATIONS):
            print(f"[Conversation {i+1}/{NUM_CONVERSATIONS}] Starting session...")

            # First message: initialize session with '-1'
            first_payload = get_response("-1", MESSAGES[0])
            session_id = first_payload.get("sessionID", "UNKNOWN")
            writer.writerow([i+1, session_id, 1, MESSAGES[0], first_payload.get("text")])
            time.sleep(1)

            # Send remaining messages using returned session ID
            for j, prompt in enumerate(MESSAGES[1:], start=2):
                print(f" → Sending message {j}: {prompt}")
                response_payload = get_response(session_id, prompt)
                writer.writerow([i+1, session_id, j, prompt, response_payload.get("text")])
                time.sleep(2)

    print(f"\n✅ Done! Saved {NUM_CONVERSATIONS * len(MESSAGES)} responses to '{OUTPUT_CSV}'.")

if __name__ == "__main__":
    run_sampling()