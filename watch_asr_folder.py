"""
watch_asr_folder.py
-------------------
Watches an input folder for incoming History Press ASR CSV files.
For each file found:
  - If any DTL rows have qty >= 50, those HDR+DTL pairs are removed
    and the filtered file is written to the output folder.
  - If no rows meet the threshold, the file is copied to the output
    folder unchanged.
  - The source file is deleted from the input folder after successful
    processing.
  - All activity is written to both the console and a rotating log file.

Requires: watchdog
    pip install watchdog

Usage:
    python watch_asr_folder.py

Configuration:
    Edit the constants below, or pass --input, --output and --log as arguments.
"""

import argparse
import logging
import logging.handlers
import os
import shutil
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ---------------------------------------------------------------------------
# Configuration — edit these defaults or use command-line arguments
# ---------------------------------------------------------------------------
DEFAULT_INPUT_FOLDER  = "./input"
DEFAULT_OUTPUT_FOLDER = "./output"
DEFAULT_LOG_FILE      = "./logs/asr_watcher.log"
QTY_THRESHOLD         = 50          # orders with qty >= this value are removed
SETTLE_DELAY          = 1.0         # seconds to wait after a file event before
                                    # processing (allows large files to finish
                                    # copying into the watch folder)
LOG_LEVEL             = logging.INFO
LOG_MAX_BYTES         = 5 * 1024 * 1024   # rotate at 5 MB
LOG_BACKUP_COUNT      = 5                 # keep 5 rotated files
# ---------------------------------------------------------------------------

def setup_logging(log_file: Path) -> None:
    """Configure logging to both console and a rotating log file."""
    log_file.parent.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


log = logging.getLogger(__name__)


def is_asr_csv(path: Path) -> bool:
    """Return True if the file looks like an ASR CSV (case-insensitive .csv extension)."""
    return path.suffix.lower() == ".csv"


def filter_asr_file(src: Path, dst: Path, threshold: int = QTY_THRESHOLD) -> dict:
    """
    Read src, remove HDR+DTL pairs where DTL quantity >= threshold,
    and write the result to dst.

    Returns a dict with:
        removed   (int)  – number of order pairs removed
        kept      (int)  – number of order pairs kept
        unchanged (bool) – True if no pairs were removed
    """
    raw = src.read_text(encoding="utf-8", errors="replace")
    lines = raw.split("\n")

    output_lines = []
    removed = 0
    kept = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.upper().startswith("HDR,"):
            # Look ahead for the paired DTL row
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            next_stripped = next_line.strip()

            if next_stripped.upper().startswith("DTL,"):
                cols = next_stripped.split(",")
                try:
                    qty = int(cols[4].strip())
                except (IndexError, ValueError):
                    qty = 0

                if qty >= threshold:
                    log.debug("  Removing pair — PO %s, qty %d", cols[1].strip(), qty)
                    removed += 1
                    i += 2
                    continue
                else:
                    output_lines.append(line)
                    output_lines.append(next_line)
                    kept += 1
                    i += 2
                    continue

        # Pass through any other lines (blank lines, unexpected content)
        output_lines.append(line)
        i += 1

    dst.write_text("\n".join(output_lines), encoding="utf-8")

    return {"removed": removed, "kept": kept, "unchanged": removed == 0}


def process_file(src: Path, output_folder: Path) -> None:
    """Process a single incoming CSV file and write the result to output_folder."""
    dst = output_folder / src.name

    log.info("Processing: %s", src.name)

    try:
        result = filter_asr_file(src, dst)
    except Exception as exc:
        log.error("Failed to process %s: %s", src.name, exc)
        return

    if result["unchanged"]:
        log.info(
            "  No high-qty orders found — %d order(s) passed through unchanged → %s",
            result["kept"],
            dst,
        )
    else:
        log.info(
            "  Removed %d order(s) with qty ≥ %d, kept %d — written to %s",
            result["removed"],
            QTY_THRESHOLD,
            result["kept"],
            dst,
        )

    # Clean up the source file now that it has been safely written to output
    try:
        src.unlink()
        log.info("  Deleted source file: %s", src)
    except Exception as exc:
        log.warning("  Could not delete source file %s: %s", src, exc)


class ASRHandler(FileSystemEventHandler):
    """Watchdog event handler — reacts to new files in the watched folder."""

    def __init__(self, input_folder: Path, output_folder: Path):
        self.input_folder = input_folder
        self.output_folder = output_folder
        self._seen: set[Path] = set()  # guard against duplicate events

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if is_asr_csv(path) and path not in self._seen:
            self._seen.add(path)
            # Brief pause so the file is fully written before we read it
            time.sleep(SETTLE_DELAY)
            process_file(path, self.output_folder)
            self._seen.discard(path)

    def on_moved(self, event):
        """Also catch files moved/renamed into the watch folder."""
        if event.is_directory:
            return
        path = Path(event.dest_path)
        if is_asr_csv(path) and path not in self._seen:
            self._seen.add(path)
            time.sleep(SETTLE_DELAY)
            process_file(path, self.output_folder)
            self._seen.discard(path)


def process_existing(input_folder: Path, output_folder: Path) -> None:
    """Process any CSV files already sitting in the input folder at startup."""
    existing = sorted(input_folder.glob("*.csv")) + sorted(input_folder.glob("*.CSV"))
    # Deduplicate (case-insensitive filesystems may list twice)
    seen_names = set()
    for f in existing:
        if f.name not in seen_names:
            seen_names.add(f.name)
            log.info("Found existing file at startup: %s", f.name)
            process_file(f, output_folder)


def main():
    parser = argparse.ArgumentParser(description="Watch a folder for ASR CSV files and filter high-qty orders.")
    parser.add_argument("--input",     default=DEFAULT_INPUT_FOLDER,  help="Folder to watch for incoming files")
    parser.add_argument("--output",    default=DEFAULT_OUTPUT_FOLDER, help="Folder to write processed files to")
    parser.add_argument("--log",       default=DEFAULT_LOG_FILE,      help="Path to the log file")
    parser.add_argument("--threshold", type=int, default=QTY_THRESHOLD,
                        help=f"Remove orders with qty >= this value (default: {QTY_THRESHOLD})")
    args = parser.parse_args()

    input_folder  = Path(args.input).resolve()
    output_folder = Path(args.output).resolve()
    log_file      = Path(args.log).resolve()

    setup_logging(log_file)

    # Create folders if they don't exist
    input_folder.mkdir(parents=True, exist_ok=True)
    output_folder.mkdir(parents=True, exist_ok=True)

    log.info("ASR Folder Watcher starting")
    log.info("  Input    : %s", input_folder)
    log.info("  Output   : %s", output_folder)
    log.info("  Log file : %s", log_file)
    log.info("  Threshold: qty >= %d will be removed", args.threshold)

    # Handle files already in the input folder before the watcher starts
    process_existing(input_folder, output_folder)

    handler  = ASRHandler(input_folder, output_folder)
    observer = Observer()
    observer.schedule(handler, str(input_folder), recursive=False)
    observer.start()

    log.info("Watching for new files — press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping watcher...")
        observer.stop()

    observer.join()
    log.info("Watcher stopped.")


if __name__ == "__main__":
    main()