import subprocess
import sys
import webbrowser
import time

# Git push
subprocess.run(["git", "add", "."], check=True)
subprocess.run(["git", "commit", "-m", "Fix label layout: larger fonts, tighter packing, QR-bound text"], check=True)
subprocess.run(["git", "push", "origin", "main"], check=True)

# Start Streamlit
print("Starting Streamlit dashboard...")
process = subprocess.Popen(
    [sys.executable, "-m", "streamlit", "run", "dsm_label_generator_improved.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

# Wait for server to start and auto-open browser
for line in process.stdout:
    print(line, end="")
    if "Local URL:" in line or "Network URL:" in line:
        url = line.split(":")[-1].strip()
        if "http" not in url:
            url = "http://localhost:8501"
        print(f"Opening browser: {url}")
        webbrowser.open(url)
        break

# Keep running
process.wait()