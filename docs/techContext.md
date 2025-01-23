# Technical Context

## Technologies Used
- Python 3.x
- Tkinter for GUI
- pandas for data processing
- sv_ttk for theming
- requests for iTunes API integration

## Dependencies
- pandas: Data manipulation and CSV processing
- tkinter: GUI framework
- sv_ttk: Sun Valley theme for modern UI
- requests: HTTP requests for iTunes API

## Development Setup
1. Python 3.x environment
2. Install required packages:
   ```
   pip install pandas tkinter sv_ttk requests
   ```

## Technical Constraints
1. File size limitations based on system memory (large CSV files may require chunked processing)
2. iTunes API rate limiting may affect artist lookup speed
3. Local processing only - no server-side components
4. GUI is desktop-based using Tkinter

## Build Process
- Uses PyInstaller for creating standalone executables
- Build configuration in `Apple Music History Converter.spec`
- GitHub Actions workflow for automated builds 