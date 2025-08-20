# Convai Sampler App

A FastAPI-based web app for running the **Convai Narrative Testing Pipeline** with a user-friendly Swagger UI.
Lets you:

* Export a narrative map for a Convai character
* Scrape recent chat history
* View results in CSV format
* Perform NLP Analysis on recent chat history

---

## 🚀 Setup & Installation

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/DaelenWall/convai_sampler_app.git
cd convai_sampler_app
```

### 2️⃣ Create a Virtual Environment

**Windows (PowerShell)**:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

**Mac/Linux**:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Running the App

Once your virtual environment is activated:

```bash
uvicorn server:app --reload --port 8000
```

### Access the UI

Open your browser and go to:
📍 **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

You’ll see the Swagger UI, where you can:

* Enter your **Convai API Key**
* Provide a **Character ID**
* (Optionally) set **Start** and **End** dates
* Run the pipeline and get CSV results

---

## 📂 Output Files

The pipeline saves outputs in the `data/` folder:

* `narrative_map.json` – Exported narrative map
* `selected_history.csv` – Filtered chat history
* `summary.csv` – NLP analysis summary

---

## 🛑 Stopping the App

Press **CTRL + C** in the terminal to stop the server.

---

## 💡 Notes

* Make sure you have a **valid Convai API key** to use the endpoints.
* You do **not** need to touch the command line after initial setup — everything runs from the browser.
