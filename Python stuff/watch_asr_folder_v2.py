"""
watch_asr_folder.py
-------------------
Watches an input folder for incoming History Press CSV order files.
Two file formats are supported, detected from the filename:

  ASR format  (filename contains _ASR_)
    Structure : one HDR row + one DTL row per order; multiple orders per file
    Action    : remove any HDR+DTL pair where DTL qty >= threshold;
                write single output file with the same filename

  MOD format  (filename contains _MOD_)
    Structure : one HDR row + multiple DTL rows per order; multiple orders
                per file
    Action    : split into one output file per order; remove any DTL rows
                where qty >= threshold; if all DTL rows for an order are
                removed the order produces no output file
    Naming    : prefix from input filename + order number from HDR, e.g.
                20260330_MOD_HISTORYP.CSV  ->  20260330_MOD_4000000672.CSV

For both formats:
  - The source file is deleted from the input folder after processing.
  - All activity is written to both the console and a rotating log file.

Designed to run on Windows Server 2012 via Windows Task Scheduler,
starting automatically at system startup under a service account.

Requires: watchdog  (pip install watchdog)

Usage:
    python watch_asr_folder.py
    python watch_asr_folder.py --no-console   (suppress console output; use
                                               when running via Task Scheduler)

Configuration:
    Edit the constants below, or pass --input, --output and --log as arguments.
"""

import argparse
import logging
import logging.handlers
import signal
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
QTY_THRESHOLD         = 50          # DTL rows with qty >= this value are removed
SETTLE_DELAY          = 1.0         # seconds to wait after a file event before
                                    # processing (allows large files to finish
                                    # copying into the watch folder)
LOG_LEVEL             = logging.INFO
LOG_MAX_BYTES         = 5 * 1024 * 1024   # rotate at 5 MB
LOG_BACKUP_COUNT      = 5                 # keep 5 rotated files
# ---------------------------------------------------------------------------


def setup_logging(log_file: Path, no_console: bool = False) -> None:
    """Configure logging to a rotating log file, and optionally the console."""
    log_file.parent.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    if not no_console:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(fmt)
        root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File type detection
# ---------------------------------------------------------------------------

def detect_format(path: Path) -> str:
    """
    Return 'ASR', 'MOD', or 'UNKNOWN' based on the filename.
    Detection is case-insensitive.
    """
    name_upper = path.name.upper()
    if "_ASR_" in name_upper:
        return "ASR"
    if "_MOD_" in name_upper:
        return "MOD"
    return "UNKNOWN"


def is_csv(path: Path) -> bool:
    """Return True for any .csv file (case-insensitive)."""
    return path.suffix.lower() == ".csv"


# ---------------------------------------------------------------------------
# ASR format processing
# One HDR + one DTL per order; multiple orders per file.
# Output: single file, same name, HDR+DTL pairs with qty >= threshold removed.
# ---------------------------------------------------------------------------

def process_asr(src: Path, output_folder: Path, threshold: int) -> None:
    """Process an ASR-format file."""
    log.info("  Format: ASR")

    raw   = src.read_text(encoding="utf-8", errors="replace")
    lines = raw.split("\n")

    output_lines = []
    removed = 0
    kept    = 0
    i       = 0

    while i < len(lines):
        line     = lines[i]
        stripped = line.strip()

        if stripped.upper().startswith("HDR,"):
            next_line     = lines[i + 1] if i + 1 < len(lines) else ""
            next_stripped = next_line.strip()

            if next_stripped.upper().startswith("DTL,"):
                cols = next_stripped.split(",")
                try:
                    qty = int(cols[4].strip())
                except (IndexError, ValueError):
                    qty = 0

                if qty >= threshold:
                    log.debug("    Removing pair — PO %s, qty %d", cols[1].strip(), qty)
                    removed += 1
                    i += 2
                    continue
                else:
                    output_lines.append(line)
                    output_lines.append(next_line)
                    kept += 1
                    i += 2
                    continue

        output_lines.append(line)
        i += 1

    dst = output_folder / src.name
    dst.write_text("\n".join(output_lines), encoding="utf-8")

    if removed == 0:
        log.info(
            "  No high-qty orders — %d order(s) passed through unchanged → %s",
            kept, dst.name,
        )
    else:
        log.info(
            "  Removed %d order(s) with qty >= %d, kept %d → %s",
            removed, threshold, kept, dst.name,
        )


# ---------------------------------------------------------------------------
# MOD format processing
# One HDR + multiple DTLs per order; multiple orders per file.
# Output: one file per order, DTL rows with qty >= threshold removed.
# Naming: <prefix>_<order_number><ext>
#   e.g. 20260330_MOD_HISTORYP.CSV  ->  20260330_MOD_4000000672.CSV
# ---------------------------------------------------------------------------

def mod_output_filename(src: Path, order_number: str) -> str:
    """
    Build the output filename for a MOD split file.

    The last underscore-delimited token in the stem (the client identifier,
    e.g. HISTORYP) is replaced with the order number.

    e.g. "20260330_MOD_HISTORYP" + "4000000672"  ->  "20260330_MOD_4000000672"
    """
    stem   = src.stem                              # 20260330_MOD_HISTORYP
    parts  = stem.rsplit("_", 1)                   # ['20260330_MOD', 'HISTORYP']
    prefix = parts[0] if len(parts) > 1 else stem  # 20260330_MOD
    return f"{prefix}_{order_number}{src.suffix}"  # 20260330_MOD_4000000672.CSV


def parse_mod_orders(lines: list) -> list:
    """
    Parse lines from a MOD file into a list of order dicts:
        {
            'order_number': str,
            'hdr_line':     str,   # raw HDR line (preserving original whitespace)
            'dtl_lines':    list,  # raw DTL lines
        }
    """
    orders  = []
    current = None

    for line in lines:
        stripped = line.strip()

        if stripped.upper().startswith("HDR,"):
            if current is not None:
                orders.append(current)
            cols         = stripped.split(",")
            order_number = cols[1].strip() if len(cols) > 1 else "UNKNOWN"
            current      = {
                "order_number": order_number,
                "hdr_line":     line,
                "dtl_lines":    [],
            }

        elif stripped.upper().startswith("DTL,") and current is not None:
            current["dtl_lines"].append(line)

        # Blank / unexpected lines outside an order block are silently dropped

    if current is not None:
        orders.append(current)

    return orders


def process_mod(src: Path, output_folder: Path, threshold: int) -> None:
    """Process a MOD-format file, splitting into one output file per order."""
    log.info("  Format: MOD")

    raw    = src.read_text(encoding="utf-8", errors="replace")
    lines  = raw.split("\n")
    orders = parse_mod_orders(lines)

    total_orders  = len(orders)
    written       = 0
    skipped       = 0
    total_removed = 0
    total_kept    = 0

    for order in orders:
        order_number = order["order_number"]
        kept_dtls    = []
        removed_dtls = 0

        for dtl_line in order["dtl_lines"]:
            cols = dtl_line.strip().split(",")
            try:
                qty = int(cols[4].strip())
            except (IndexError, ValueError):
                qty = 0

            if qty >= threshold:
                log.debug(
                    "    Removing DTL — order %s, ISBN %s, qty %d",
                    order_number,
                    cols[3].strip() if len(cols) > 3 else "?",
                    qty,
                )
                removed_dtls += 1
            else:
                kept_dtls.append(dtl_line)

        total_removed += removed_dtls
        total_kept    += len(kept_dtls)

        if not kept_dtls:
            log.info(
                "    Order %s — all %d DTL row(s) removed, no output file written",
                order_number, removed_dtls,
            )
            skipped += 1
            continue

        out_name = mod_output_filename(src, order_number)
        dst      = output_folder / out_name
        content  = "\n".join([order["hdr_line"]] + kept_dtls)
        dst.write_text(content, encoding="utf-8")

        log.info(
            "    Order %s — kept %d DTL row(s)%s → %s",
            order_number,
            len(kept_dtls),
            f", removed {removed_dtls}" if removed_dtls else "",
            out_name,
        )
        written += 1

    log.info(
        "  %d order(s) in file — %d file(s) written, %d skipped "
        "(%d DTL row(s) removed, %d kept)",
        total_orders, written, skipped, total_removed, total_kept,
    )


# ---------------------------------------------------------------------------
# Unified file processor
# ---------------------------------------------------------------------------

def process_file(src: Path, output_folder: Path, threshold: int = QTY_THRESHOLD) -> None:
    """Detect file format and dispatch to the appropriate processor."""
    log.info("Processing: %s", src.name)

    fmt = detect_format(src)

    try:
        if fmt == "ASR":
            process_asr(src, output_folder, threshold)
        elif fmt == "MOD":
            process_mod(src, output_folder, threshold)
        else:
            log.warning(
                "  Unrecognised format (expected _ASR_ or _MOD_ in filename) "
                "— skipping: %s", src.name,
            )
            return
    except Exception as exc:
        log.error("  Failed to process %s: %s", src.name, exc)
        return

    # Delete source file after successful processing
    try:
        src.unlink()
        log.info("  Deleted source file: %s", src.name)
    except Exception as exc:
        log.warning("  Could not delete source file %s: %s", src.name, exc)


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------

class CSVHandler(FileSystemEventHandler):
    """Reacts to new CSV files appearing in the watched folder."""

    def __init__(self, input_folder: Path, output_folder: Path, threshold: int):
        self.input_folder  = input_folder
        self.output_folder = output_folder
        self.threshold     = threshold
        self._seen: set    = set()

    def _handle(self, path: Path) -> None:
        if is_csv(path) and path not in self._seen:
            self._seen.add(path)
            time.sleep(SETTLE_DELAY)
            process_file(path, self.output_folder, self.threshold)
            self._seen.discard(path)

    def on_created(self, event):
        if not event.is_directory:
            self._handle(Path(event.src_path))

    def on_moved(self, event):
        """Also catch files moved/renamed into the watch folder."""
        if not event.is_directory:
            self._handle(Path(event.dest_path))


# ---------------------------------------------------------------------------
# Startup — process files already in the input folder
# ---------------------------------------------------------------------------

def process_existing(input_folder: Path, output_folder: Path, threshold: int) -> None:
    """Process any CSV files already sitting in the input folder at startup."""
    existing = sorted(input_folder.glob("*.csv")) + sorted(input_folder.glob("*.CSV"))
    seen_names: set = set()
    for f in existing:
        if f.name not in seen_names:
            seen_names.add(f.name)
            log.info("Found existing file at startup: %s", f.name)
            process_file(f, output_folder, threshold)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Watch a folder for History Press CSV order files and process them."
    )
    parser.add_argument("--input",      default=DEFAULT_INPUT_FOLDER,  help="Folder to watch for incoming files")
    parser.add_argument("--output",     default=DEFAULT_OUTPUT_FOLDER, help="Folder to write processed files to")
    parser.add_argument("--log",        default=DEFAULT_LOG_FILE,      help="Path to the log file")
    parser.add_argument("--threshold",  type=int, default=QTY_THRESHOLD,
                        help=f"Remove DTL rows with qty >= this value (default: {QTY_THRESHOLD})")
    parser.add_argument("--no-console", action="store_true",
                        help="Suppress console output (use when running via Task Scheduler)")
    args = parser.parse_args()

    input_folder  = Path(args.input).resolve()
    output_folder = Path(args.output).resolve()
    log_file      = Path(args.log).resolve()

    setup_logging(log_file, no_console=args.no_console)

    input_folder.mkdir(parents=True, exist_ok=True)
    output_folder.mkdir(parents=True, exist_ok=True)

    log.info("History Press Order Watcher starting")
    log.info("  Input    : %s", input_folder)
    log.info("  Output   : %s", output_folder)
    log.info("  Log file : %s", log_file)
    log.info("  Threshold: qty >= %d will be removed", args.threshold)

    process_existing(input_folder, output_folder, args.threshold)

    handler  = CSVHandler(input_folder, output_folder, args.threshold)
    observer = Observer()
    observer.schedule(handler, str(input_folder), recursive=False)
    observer.start()

    log.info("Watching for new files — press Ctrl+C to stop")

    def shutdown(signum, frame):
        log.info("Shutdown signal received (%s) — stopping watcher...", signum)
        observer.stop()

    signal.signal(signal.SIGTERM, shutdown)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, shutdown)

    try:
        while observer.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Keyboard interrupt — stopping watcher...")
        observer.stop()

    observer.join()
    log.info("Watcher stopped.")


if __name__ == "__main__":
    main()
