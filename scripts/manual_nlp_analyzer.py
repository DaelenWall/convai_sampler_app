import polars as pl
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# === CONFIGURATION ===
CSV_PATH = "../data/manual_chat_responses.csv"
EMBED_MODEL = "all-MiniLM-L6-v2"

# === LOAD CSV DATA ===
df = pl.read_csv(CSV_PATH)
model = SentenceTransformer(EMBED_MODEL)

# === GROUP RESPONSES BY SESSION ===
results = []
response_indices = df.select("Prompt #").unique().to_series().to_list()

for idx in response_indices:
    group = df.filter(pl.col("Prompt #") == idx)
    responses = group.select("Response").to_series().to_list()

    responses = [r for r in responses if isinstance(r, str) and r.strip()]
    if len(responses) < 2:
        continue  # not enough to measure variability

    # Convert responses to embeddings
    embeddings = model.encode(responses)

    # Calculate cosine similarity matrix
    sim_matrix = cosine_similarity(embeddings)

    # Get upper triangle of matrix (pairwise similarities)
    upper_tri_indices = np.triu_indices(len(sim_matrix), k=1)
    similarities = sim_matrix[upper_tri_indices]

    results.append({
        "Prompt #": idx,
        "Average Similarity": float(np.mean(similarities)),
        "Min Similarity": float(np.min(similarities)),
        "Max Similarity": float(np.max(similarities)),
        "Response Count": len(responses)
    })

# === OUTPUT TO TERMINAL ===
summary_df = pl.DataFrame(results)
print("\n🔍 Top 10 Most Varied Sessions (Lowest Avg Similarity):\n")
print(summary_df.sort("Average Similarity").head(10))

# === OPTIONAL: SAVE TO CSV ===
summary_df.write_csv("../data/manual_nlp_summary.csv")
print("\n✅ Saved summary to ../data/manual_nlp_summary.csv")
