import os
import signal
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web"
TRADING = ROOT / "services/trading"
VITE = WEB / "node_modules/vite/bin/vite.js"
TRADING_JAR = TRADING / "build/libs/trading-service-0.1.0.jar"


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def interrupt(_signal, _frame):
    raise KeyboardInterrupt


def main():
    for required in (VITE, TRADING_JAR):
        if not required.is_file():
            raise SystemExit(f"Build the first demo dependencies before starting: {required}")

    signal.signal(signal.SIGTERM, interrupt)
    services = (
        ("Python", [sys.executable, "-m", "services.research.research.server"], ROOT),
        ("Spring Boot", ["java", "-jar", str(TRADING_JAR)], TRADING),
        ("React", ["node", str(VITE), "--strictPort"], WEB),
    )
    with ExitStack() as cleanup:
        try:
            processes = {}
            for name, command, directory in services:
                process = subprocess.Popen(command, cwd=directory)
                cleanup.callback(stop, process)
                processes[name] = process
            print(
                "Starting first demo on http://127.0.0.1:5173/"
                f" (research delay: {os.environ.get('RESEARCH_SYNTHETIC_DELAY_MS', '0')} ms)",
                flush=True,
            )
            while True:
                for name, process in processes.items():
                    status = process.poll()
                    if status is not None:
                        raise SystemExit(f"{name} stopped with exit code {status}")
                time.sleep(0.25)
        except KeyboardInterrupt:
            return


if __name__ == "__main__":
    main()
