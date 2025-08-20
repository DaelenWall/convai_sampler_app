import os
import json
import polars as pl
from sentence_transformers import SentenceTransformer, util

# === Path Configuration ===
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INPUT_CSV = os.path.join(BASE_DIR, "data", "app_selected_history.csv")
NARRATIVE_JSON = os.path.join(BASE_DIR, "data", "narrative_map.json")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "app_nlp_summary.csv")
SECTION_EVENTS = os.path.join(BASE_DIR, "data", "section_events.jsonl")
events_by_session = {}

if os.path.exists(SECTION_EVENTS):
    with open(SECTION_EVENTS, "r", encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
                events_by_session.setdefault(ev["session_id"], []).append(ev["section_id"])
            except Exception:
                pass


# === Load data ===
print(f"📅 Loading chat history from: {INPUT_CSV}")
df = pl.read_csv(INPUT_CSV)

print(f"📖 Loading narrative map from: {NARRATIVE_JSON}")
with open(NARRATIVE_JSON, "r", encoding="utf-8") as f:
    narrative_map = json.load(f)

# === Initialize embedding model ===
model = SentenceTransformer("all-MiniLM-L6-v2")

# === Helpers ===
def get_decisions_for_section(n_map, section_id):
    section_obj = n_map.get("sections", {}).get(section_id, {})
    norm = section_obj.get("_normalized", {})
    return norm.get("decisions", []) if isinstance(norm, dict) else []

def get_triggers_for_section(n_map, section_id):
    all_trigs = n_map.get("triggers", [])
    scoped = [t for t in all_trigs if t.get("_normalized", {}).get("source_section") == section_id]
    if scoped:
        return scoped
    return all_trigs

def get_expected_response(n_map, section_id):
    """Safely get expected DK line from a section, with fallbacks."""
    sec_obj = n_map.get("sections", {}).get(section_id, {})
    if not sec_obj:
        return ""
    # Try response.text
    resp = sec_obj.get("response", {})
    if isinstance(resp, dict):
        txt = resp.get("text", "")
        if txt and txt.strip():
            return txt
    # Fallback: objective
    obj = sec_obj.get("objective", "")
    if obj and obj.strip():
        return obj
    # Fallback: normalized objective
    norm = sec_obj.get("_normalized", {})
    if isinstance(norm, dict):
        obj2 = norm.get("objective", "")
        if obj2 and obj2.strip():
            return obj2
    return ""

# === Matching ===
def semantic_match(user_input, n_map, current_section_id=None):
    input_embedding = model.encode(user_input, convert_to_tensor=True)

    best_match = None
    best_score = -1
    from_section = current_section_id
    to_section = None
    expected_response = None

    candidates = []

    # Decisions
    if current_section_id:
        decisions = get_decisions_for_section(n_map, current_section_id)
        for d in decisions:
            crit = (d.get("criteria") or "").strip()
            nxt = d.get("next_section")
            if crit:
                candidates.append({
                    "type": "decision",
                    "text": crit,
                    "from_section": current_section_id,
                    "to_section": nxt
                })

    # Triggers
    triggers = get_triggers_for_section(n_map, current_section_id)
    for t in triggers:
        norm = t.get("_normalized", {})
        msg = (norm.get("message") or "").strip()
        dest = norm.get("destination_section")
        if msg:
            candidates.append({
                "type": "trigger",
                "text": msg,
                "from_section": norm.get("source_section"),
                "to_section": dest
            })

    # Score candidates
    for c in candidates:
        crit_embedding = model.encode(c["text"], convert_to_tensor=True)
        score = util.pytorch_cos_sim(input_embedding, crit_embedding).item()

        if score > best_score:
            best_score = score
            best_match = c
            from_section = c["from_section"]
            to_section = c["to_section"]
            expected_response = get_expected_response(n_map, to_section)

    return {
        "matched_criteria": best_match["text"] if best_match else None,
        "match_score": best_score,
        "from_section": from_section,
        "to_section": to_section,
        "expected_response": expected_response or ""
    }

# === Group and Analyze ===
session_ids = df.select("Session ID").unique().to_series().to_list()
results = []
print(f"🧾 Analyzing {len(session_ids)} unique sessions...")

for session_id in session_ids:
    session_df = df.filter(pl.col("Session ID") == session_id)

    # Track active section per session (we advance this as we infer/receive hops)
    current_section_id = None

    event_queue = list(events_by_session.get(session_id, []))
    current_section_id = event_queue.pop(0) if event_queue else None

    for row in session_df.iter_rows(named=True):
        user_input = row.get("User Input", "")
        char_response = row.get("Character Response", "")

        if not isinstance(user_input, str) or not isinstance(char_response, str):
            continue

        # Infer the best matching decision/trigger from the *current* section
        match = semantic_match(user_input, narrative_map, current_section_id)
        expected = match["expected_response"] or ""
        from_section = match["from_section"]
        to_section = match["to_section"]

        print(f"🧭 Session {session_id} | '{user_input}' → '{match['matched_criteria']}' | "
              f"{from_section} -> {to_section} (score={round(match['match_score'], 3)})")

        # Compute semantic deviation (Actual vs Expected)
        if expected.strip():
            response_embeds = model.encode([char_response, expected], convert_to_tensor=True)
            similarity = util.pytorch_cos_sim(response_embeds[0], response_embeds[1]).item()
            similarity = round(float(similarity), 3)
        else:
            similarity = None  # no expected line to compare

        # ✅ Append rich row
        results.append({
            "Session ID": session_id,
            "User Input": user_input,
            "Matched Criteria": match["matched_criteria"] or "",
            "From Section": from_section or "",
            "To Section": to_section or "",
            "Expected DK Response": expected,
            "Actual DK Response": char_response,
            "Deviation Score (cosine sim)": similarity if similarity is not None else "",
            "Input → Trigger Match Score": round(match["match_score"], 3) if match["match_score"] != -1 else ""
        })

        # 🔁 Advance the narrative pointer if we have a destination
        # If you want UE to be the source of truth:
        if event_queue:
            current_section_id = event_queue.pop(0)
        elif to_section:
            current_section_id = to_section

        if to_section:
            current_section_id = to_section

# === Save results ===
summary = pl.DataFrame(results)
summary.write_csv(OUTPUT_CSV)
print(f"\n✅ Narrative deviation summary saved to: {OUTPUT_CSV}")
