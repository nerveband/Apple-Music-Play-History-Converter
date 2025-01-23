# System Patterns

## Architecture Overview
The application follows a single-class GUI application pattern with the following components:

1. Main Application Class (`CSVProcessorApp`)
   - Handles GUI initialization and management
   - Manages file processing and data conversion
   - Controls iTunes API integration

## Key Technical Decisions

### GUI Framework
- Tkinter chosen for:
  - Native look and feel
  - Cross-platform compatibility
  - Built-in Python support
- sv_ttk theme for modern appearance

### Data Processing
- Chunked processing for large files (10,000 rows per chunk)
- Pandas DataFrame for efficient CSV manipulation
- Threading for non-blocking UI during processing

### Error Handling
- Graceful handling of large files
- User warnings for potentially long operations
- Progress tracking and status updates

## Design Patterns

### Observer Pattern
- Progress updates via progress bar
- Status messages in UI
- Preview table updates

### Command Pattern
- File operations (browse, save)
- Conversion process
- Clipboard operations

### Threading Pattern
- Background processing for CSV conversion
- Non-blocking UI during long operations
- Pause/Resume capability for iTunes searches 