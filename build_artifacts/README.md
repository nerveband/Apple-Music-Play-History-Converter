# Build Artifacts Directory

This directory contains files related to building and packaging the application.

## Files

### PyInstaller Spec Files
- `Apple Music History Converter.spec` - Original PyInstaller spec
- `mac_build.spec` - macOS-specific build configuration  
- `pyinstaller_config.spec` - General PyInstaller configuration

### Build Assets
- `tkinter_hook.py` - Custom hook for tkinter in PyInstaller builds
- `dist.zip` - Packaged distribution archive

## Usage

### Building the Application

```bash
pyinstaller Apple\ Music\ History\ Converter.spec
```

### macOS Build
```bash
pyinstaller mac_build.spec
```

### Custom Configuration
```bash
pyinstaller pyinstaller_config.spec
```

## Notes

- Spec files contain platform-specific configurations
- tkinter_hook.py helps with GUI packaging issues
- Built applications will appear in the `dist/` directory
- Make sure all dependencies are installed before building
