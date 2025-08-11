# server.py
from fastapi import FastAPI, HTTPException
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

# === Environment fix for Unicode on Windows ===
UTF8_ENV = dict(os.environ)
UTF8_ENV["PYTHONIOENCODING"] = "utf-8"

# === Shared job state ===
_current_job = {"running": False, "pid": None, "started_at": None, "ended_at": None}

def _run_background(cmd):
    PIPELINE_LOG.write_text("", encoding="utf-8")
    _current_job.update({"running": True, "pid": None, "started_at": time.time(), "ended_at": None})
    p = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=UTF8_ENV,
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

def _filesize(p: Path) -> str:
    if not p.exists(): return "missing"
    n = p.stat().st_size
    units = ["B","KB","MB","GB"]
    i = 0
    while n >= 1024 and i < len(units)-1:
        n /= 1024.0; i += 1
    return f"{n:.2f} {units[i]}"

@app.get("/")
def root():
    return {"ok": True, "msg": "Convai Sampler API running"}

# ---------- require API KEY here ----------
@app.post("/api/pipeline/start")
def pipeline_start(
    character_id: str,
    api_key: str,                       # REQUIRED: shows in Swagger now
    start: str | None = None,
    end: str | None = None,
    skip_export: bool = False,
    skip_scrape: bool = False,
    skip_analyze: bool = False,
):
    if _current_job["running"]:
        raise HTTPException(409, detail="Pipeline already running")
    if not PIPELINE.exists():
        raise HTTPException(500, detail=f"Pipeline script not found at {PIPELINE}")
    if not api_key.strip():
        raise HTTPException(400, detail="Missing api_key")

    # pass args to pipeline (pipeline will set env vars for child scripts)
    cmd = [sys.executable, str(PIPELINE),
           "--character-id", character_id,
           "--api-key", api_key]
    if start: cmd += ["--start", start]
    if end:   cmd += ["--end", end]
    if skip_export:  cmd += ["--skip-export"]
    if skip_scrape:  cmd += ["--skip-scrape"]
    if skip_analyze: cmd += ["--skip-analyze"]

    t = threading.Thread(target=_run_background, args=(cmd,), daemon=True)
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
