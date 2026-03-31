# History Press Order Watcher

A Python script that monitors an input folder for incoming History Press CSV order files. Two file formats are supported, detected automatically from the filename. The source file is deleted from the input folder after successful processing.

## Requirements

- Python 3.12
- [watchdog](https://pypi.org/project/watchdog/) library (already installed system-wide)

## Setup

1. Copy `watch_asr_folder.py` to a permanent location on the server, e.g. `C:\ASR\`.
2. Edit the `CONFIGURATION` block in `install_task.bat` (and optionally `start.bat`) to set your paths.
3. The input, output, and logs folders are created automatically on first run.

No virtual environment is required — watchdog is already installed into the system Python.

## Folder Structure

The following folders are created automatically on first run if they do not exist:

```
watch_asr_folder.py
input\          <- drop CSV files here
output\         <- processed files appear here
logs\
    asr_watcher.log
```

## Supported File Formats

The script detects the file format from the filename (case-insensitive).

### ASR format — filename contains `_ASR_`

**Structure:** one `HDR` row + one `DTL` row per order; multiple orders per file.

**Action:** any `HDR`+`DTL` pair where the `DTL` quantity is ≥50 is removed. The result is written as a single output file with the same filename.

Example:
```
Input:   20260330_ASR_HISTORYP.CSV
Output:  20260330_ASR_HISTORYP.CSV  (with high-qty pairs removed)
```

### MOD format — filename contains `_MOD_`

**Structure:** one `HDR` row + multiple `DTL` rows per order; multiple orders per file.

**Action:** the file is split into one output file per order. Any `DTL` rows with quantity ≥50 are removed. If all `DTL` rows for an order are removed, no output file is written for that order.

**Output filename:** the client identifier in the input filename is replaced with the order number from the `HDR` row.

Example:
```
Input:   20260330_MOD_HISTORYP.CSV  (contains orders 4000000672, 4000000673 ...)
Output:  20260330_MOD_4000000672.CSV
         20260330_MOD_4000000673.CSV
         ...
```

Files with neither `_ASR_` nor `_MOD_` in the filename are logged as unrecognised and skipped (source file is not deleted).

## Usage

### Run with defaults

```bat
python watch_asr_folder.py
```

### Run with custom paths

```bat
python watch_asr_folder.py ^
    --input  "C:\ASR\input" ^
    --output "C:\ASR\output" ^
    --log    "C:\ASR\logs\asr_watcher.log"
```

### All arguments

| Argument      | Default                    | Description                                      |
|---------------|----------------------------|--------------------------------------------------|
| `--input`     | `./input`                  | Folder to watch for incoming CSV files           |
| `--output`    | `./output`                 | Folder to write processed files to               |
| `--log`       | `./logs/asr_watcher.log`   | Path to the log file                             |
| `--threshold` | `50`                       | Remove DTL rows with qty >= this value           |
| `--no-console`|                            | Suppress console output (use with Task Scheduler)|

Stop the script at any time with **Ctrl+C**.

## Behaviour

- On startup, any CSV files already present in the input folder are processed immediately before watching begins.
- New files dropped into or moved into the input folder are detected automatically.
- A brief settle delay (1 second) is applied before reading each file to allow large files to finish copying.
- The source file is **deleted** from the input folder after successful processing.
- Unrecognised file formats are skipped and the source file is left in place.

## CSV File Format

### HDR row

| Column | Content           |
|--------|-------------------|
| 0      | `HDR`             |
| 1      | Order Number      |
| 2      | Date (`YYYYMMDD`) |

### DTL row

| Column | Content      |
|--------|--------------|
| 0      | `DTL`        |
| 1      | Order Number |
| 2      | Line Number  |
| 3      | ISBN         |
| 4      | Quantity     |

## Logging

All activity is written to both the console and a rotating log file.

- Default location: `./logs/asr_watcher.log`
- Rotates at **5 MB**, keeps **5** backup files

Example log output for a MOD file:

```
2026-03-30 09:15:01  INFO      Processing: 20260330_MOD_HISTORYP.CSV
2026-03-30 09:15:01  INFO        Format: MOD
2026-03-30 09:15:01  INFO          Order 4000000672 — kept 12 DTL row(s) → 20260330_MOD_4000000672.CSV
2026-03-30 09:15:01  INFO          Order 4000000673 — kept 11 DTL row(s), removed 1 → 20260330_MOD_4000000673.CSV
2026-03-30 09:15:01  INFO          Order 4000000674 — all 3 DTL row(s) removed, no output file written
2026-03-30 09:15:01  INFO        5 order(s) in file — 4 file(s) written, 1 skipped (4 DTL row(s) removed, 35 kept)
2026-03-30 09:15:01  INFO        Deleted source file: 20260330_MOD_HISTORYP.CSV
```

## Batch Files

Four batch files are provided for management on Windows:

| File                  | Requires Admin | Action                                                    |
|-----------------------|:--------------:|-----------------------------------------------------------|
| `start.bat`           |       No       | Starts the watcher in a minimised window                  |
| `stop.bat`            |       No       | Stops any running instance of the watcher                 |
| `install_task.bat`    |      Yes       | Registers the watcher with Task Scheduler to run at boot  |
| `uninstall_task.bat`  |      Yes       | Removes the scheduled task and stops the running watcher  |

Edit the `CONFIGURATION` block at the top of each batch file to match your installation before use.

## Windows Server 2012 — Auto-start via Task Scheduler

The recommended approach for automatic startup on Windows Server 2012 is to register the watcher as a scheduled task that triggers on system startup.

### Python version

This deployment uses **Python 3.12**, which works in practice on Windows Server 2012 despite Microsoft's extended support for Server 2012 having ended in October 2023. If Python ever needs to be reinstalled and the 3.12 installer refuses due to an OS version check, **Python 3.11.9** is the recommended fallback — it receives security updates until 2027.

- Python 3.12: https://www.python.org/downloads/release/python-3120/
- Python 3.11.9 (fallback): https://www.python.org/downloads/release/python-3119/

### Installation steps

1. Copy all files to a permanent location, e.g. `C:\ASR\`.
2. Edit the `CONFIGURATION` block in `install_task.bat` — set `SCRIPT_DIR`, `INPUT_DIR`, `OUTPUT_DIR`, `LOG_FILE`, and `RUN_AS_USER`.
3. Right-click `install_task.bat` and choose **Run as administrator**.
4. Verify in **Task Scheduler** (taskschd.msc) that the task `ASR Folder Watcher` appears under **Task Scheduler Library**.

The task is configured with a **1-minute startup delay** to allow network shares and dependent services to come online before the watcher starts.

### Running immediately without rebooting

After installing the task you can start the watcher straight away without rebooting:

```bat
schtasks /run /tn "ASR Folder Watcher"
```

Or simply double-click `start.bat`.

### Running account

| Option         | When to use                                                              |
|----------------|--------------------------------------------------------------------------|
| `SYSTEM`       | Simplest option; works well if input/output folders are on local drives  |
| Named account  | Required if input/output folders are on a network share (UNC path)       |

### `--no-console` flag

When launched by Task Scheduler the script runs without an interactive console. The `--no-console` flag suppresses the console log handler so all output goes to the log file only. Both `install_task.bat` and `start.bat` pass this flag automatically.

### Removing auto-start

Right-click `uninstall_task.bat` and choose **Run as administrator**.

## Notes

- Only `.csv` files (case-insensitive) are processed; all other file types are ignored.
- Files without `_ASR_` or `_MOD_` in the filename are skipped and left in place.
- Original file formatting is preserved exactly in all output files.
- If the source file cannot be deleted after processing, a warning is logged and the script continues.
- The watcher handles `SIGTERM` and `SIGBREAK` signals for clean shutdown when Task Scheduler or `taskkill` stops the process.

