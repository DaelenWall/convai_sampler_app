import subprocess
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(os.path.dirname(SCRIPT_DIR), "venv", "Scripts", "python.exe")

print("🔁 Running sampler...")
subprocess.run([VENV_PYTHON, os.path.join(SCRIPT_DIR, "manual_chat_sampler.py")], check=True)

print("🔍 Running variability analysis...")
subprocess.run([VENV_PYTHON, os.path.join(SCRIPT_DIR, "manual_nlp_analyzer.py")], check=True)

print("✅ Done.")

