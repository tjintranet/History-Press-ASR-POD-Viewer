# History Press ASR-POD Viewer

A web-based application for viewing and managing History Press ASR (Advanced Shipping Request) and POD (Print on Demand) data.

## Features

- CSV file parsing and display
- Interactive data table with row selection
- High quantity filtering (≥50)
- Copy selected rows with formatting
- Download template functionality
- Responsive design

## Setup

1. Place the following files in your web server root directory:
   - `index.html`
   - `HistoryPressPO_template.docx`
   - `favicon-32x32.png` (optional)
   - `apple-touch-icon.png` (optional)

2. No additional setup required - the application uses CDN-hosted dependencies:
   - Bootstrap 5.3.2
   - PapaParse 5.4.1

## Usage

### Loading Data
1. Click the "Choose File" button
2. Select a CSV file with HDR and DTL rows
3. The data will automatically load and display in the table

### Filtering Data
- Use the "Show ≥50 only" toggle switch to filter rows with quantities of 50 or more
- The filter can be toggled on/off at any time

### Selecting and Copying Rows
1. Use checkboxes to select individual rows
2. Use the "Select All" checkbox to select all visible rows
3. Click "Copy Selected" to copy the selected rows as a formatted HTML table
4. Paste the copied data into applications that support HTML formatting (e.g., Microsoft Word, Google Docs)

### Downloading Template
- Click the "Download Template" button to download the PO template file
- The template file (`HistoryPressPO_template.docx`) must be present in the root directory

### Clearing Data
- Click the "Clear Data" button to reset the application
- This will clear all loaded data and selections

## CSV File Format

The application expects CSV files with the following structure:

### HDR (Header) Row
- Column 0: "HDR"
- Column 2: Date in YYYYMMDD format

### DTL (Detail) Rows
- Column 0: "DTL"
- Column 1: PO Number
- Column 3: ISBN
- Column 4: Quantity

## Browser Support

The application uses modern web features including:
- Fetch API
- Blob API
- ClipboardItem API
- HTML5 File API

Recommended browsers:
- Chrome (latest)
- Firefox (latest)
- Edge (latest)
- Safari (latest)

## Dependencies

- Bootstrap 5.3.2 - UI framework
- PapaParse 5.4.1 - CSV parsing library

## Notes

- Quantities ≥50 are highlighted in green
- Dates are displayed in DD/MM/YY format
- The application processes client-side data only - no server communication required
- All data is cleared when the page is refreshed