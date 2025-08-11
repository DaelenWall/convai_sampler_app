# server.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
import os, sys, subprocess, threading, time
from pathlib import Path

app = FastAPI(title="Convai Sampler API")

# === Paths ===
ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

PIPELINE = SCRIPTS / "app_pipeline.py"
SUMMARY_CSV = DATA / "app_nlp_summary.csv"
PIPELINE_LOG = DATA / "pipeline.log"

# === Shared job state ===
_current_job = {"running": False, "pid": None, "started_at": None, "ended_at": None}

def _filesize(p: Path) -> str:
    if not p.exists(): return "missing"
    n = p.stat().st_size
    units = ["B","KB","MB","GB"]
    i = 0
    while n >= 1024 and i < len(units)-1:
        n /= 1024.0; i += 1
    return f"{n:.2f} {units[i]}"

def _run_background(cmd, env):
    # fresh log
    PIPELINE_LOG.write_text("", encoding="utf-8")
    _current_job.update({"running": True, "pid": None, "started_at": time.time(), "ended_at": None})

    # make sure child uses UTF-8
    child_env = dict(os.environ)
    child_env.update(env or {})
    child_env["PYTHONIOENCODING"] = "utf-8"

    p = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
    )
    _current_job["pid"] = p.pid
    try:
        assert p.stdout is not None
        for line in p.stdout:
            with PIPELINE_LOG.open("a", encoding="utf-8") as f:
                f.write(line)
        p.wait()
    finally:
        _current_job.update({"running": False, "ended_at": time.time()})

@app.get("/")
def root():
    return {"ok": True, "msg": "Convai Sampler API running"}

# -------------------------------------------------------------------
# Start pipeline (background). api_key is REQUIRED and visible in docs
# -------------------------------------------------------------------
@app.post("/api/pipeline/start")
def pipeline_start(
    api_key: str = Query(..., description="Convai API Key (required)"),
    character_id: str = Query(..., description="Convai Character ID (required)"),
    start: str | None = Query(None, description="Start ISO date (optional, e.g. 2025-08-05)"),
    end: str | None = Query(None, description="End ISO date (optional, e.g. 2025-08-07)"),
    skip_export: bool = Query(False, description="Skip narrative export step"),
    skip_scrape: bool = Query(False, description="Skip chat history scrape step"),
    skip_analyze: bool = Query(False, description="Skip analyzer step"),
):
    if _current_job["running"]:
        raise HTTPException(409, detail="Pipeline already running")
    if not PIPELINE.exists():
        raise HTTPException(500, detail=f"Pipeline script not found at {PIPELINE}")

    # Build command
    cmd = [sys.executable, str(PIPELINE), "--character-id", character_id, "--api-key", api_key]
    if start: cmd += ["--start", start]
    if end:   cmd += ["--end", end]
    if skip_export:  cmd += ["--skip-export"]
    if skip_scrape:  cmd += ["--skip-scrape"]
    if skip_analyze: cmd += ["--skip-analyze"]

    # Pass API key + character id to child scripts via env too (belt & suspenders)
    child_env = {
        "CONVAI_API_KEY": api_key,
        "CHARACTER_ID": character_id,
    }

    t = threading.Thread(target=_run_background, args=(cmd, child_env), daemon=True)
    t.start()
    return {"ok": True, "message": "Pipeline started"}

@app.get("/api/pipeline/status")
def pipeline_status():
    return {
        "running": _current_job["running"],
        "pid": _current_job["pid"],
        "started_at": _current_job["started_at"],
        "ended_at": _current_job["ended_at"],
        "summary_exists": SUMMARY_CSV.exists(),
        "summary_size": _filesize(SUMMARY_CSV),
    }

@app.get("/api/pipeline/log")
def pipeline_log():
    if not PIPELINE_LOG.exists():
        return {"log": ""}
    text = PIPELINE_LOG.read_text(encoding="utf-8")
    if len(text) > 50_000:
        text = "…(truncated)…\n" + text[-50_000:]
    return {"log": text}

@app.get("/api/download/summary")
def download_summary():
    if not SUMMARY_CSV.exists():
        raise HTTPException(404, detail="Summary CSV not found")
    return FileResponse(SUMMARY_CSV, filename="app_nlp_summary.csv")
