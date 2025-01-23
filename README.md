# ASR History Viewer

Web application for viewing and managing ASR (Automatic Stock Replenishment) history data with row selection and copying capabilities.

## Features

- CSV file upload and parsing
- Interactive data table with row selection
- Bulk selection/deselection via checkboxes
- Copy selected rows as formatted HTML table
- Visual highlighting of quantities ≥ 50
- Data clearing functionality
- Status notifications

## Technical Details

### File Format Requirements

CSV files must contain:
- Header row (HDR): Contains order date in position 3
- Detail rows (DTL): Contains PO number, ISBN, and quantity information
```
HDR,1234,20240123,...
DTL,PO001,20240123,9781234567890,45,...
DTL,PO002,20240123,9780987654321,52,...
```

### Data Processing Features

- Date formatting (DDMMYY to DD/MM/YY)
- Row selection with checkboxes
- "Select All" functionality
- HTML table generation for clipboard
- Responsive design

### Dependencies

- Bootstrap 5.3.2
- PapaParse 5.4.1

## Usage

1. Open in web browser
2. Upload CSV file
3. Select rows using checkboxes
4. Click "Copy Selected" to copy rows as HTML table
5. Use "Clear Data" to reset

## Browser Requirements

- Modern web browsers supporting ES6+
- Clipboard API support required for copy functionality