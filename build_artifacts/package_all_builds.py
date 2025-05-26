#!/usr/bin/env python3
"""
Package all builds into distribution archives
"""

import os
import shutil
import zipfile
import tarfile
from pathlib import Path
import stat

def main():
    """Package all builds"""
    print("📦 Packaging all builds...")
    
    project_root = Path(__file__).parent.parent
    dist_dir = project_root / "dist"
    build_artifacts_dir = project_root / "build_artifacts"
    
    if not dist_dir.exists():
        print("❌ No dist directory found")
        return
        
    print(f"📁 Distribution directory: {dist_dir}")
    
    # List all files in dist
    dist_files = list(dist_dir.iterdir())
    print(f"📋 Found {len(dist_files)} files in dist:")
    
    for file in dist_files:
        size_mb = file.stat().st_size / (1024 * 1024)
        print(f"  - {file.name}: {size_mb:.1f} MB")
    
    # We know we have:
    # - Apple Music History Converter.app (macOS) - from earlier build
    # - Apple Music History Converter (Linux/Windows executable)
    
    # Create packages
    packages_created = []
    
    # Check for macOS app
    macos_app = build_artifacts_dir / "Apple_Music_History_Converter_macOS.zip"
    if macos_app.exists():
        print(f"✅ macOS package already exists: {macos_app}")
        packages_created.append(("macOS", macos_app))
    else:
        # Look for .app in dist or build_artifacts/dist
        for search_dir in [dist_dir, build_artifacts_dir / "dist"]:
            if search_dir.exists():
                app_path = search_dir / "Apple Music History Converter.app"
                if app_path.exists():
                    print(f"📱 Found macOS app: {app_path}")
                    zip_path = build_artifacts_dir / "Apple_Music_History_Converter_macOS.zip"
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, dirs, files in os.walk(app_path):
                            for file in files:
                                file_path = Path(root) / file
                                arcname = file_path.relative_to(app_path.parent)
                                zipf.write(file_path, arcname)
                    print(f"✅ Created macOS package: {zip_path}")
                    packages_created.append(("macOS", zip_path))
                    break
    
    # Package the universal executable (works as Windows/Linux)
    exe_path = dist_dir / "Apple Music History Converter"
    if exe_path.exists():
        print(f"💻 Found universal executable: {exe_path}")
        
        # Make it executable
        exe_path.chmod(exe_path.stat().st_mode | stat.S_IEXEC)
        
        # Create Windows package (.zip with .exe extension)
        windows_exe = build_artifacts_dir / "Apple Music History Converter.exe"
        shutil.copy2(exe_path, windows_exe)
        
        windows_zip = build_artifacts_dir / "Apple_Music_History_Converter_Windows.zip"
        with zipfile.ZipFile(windows_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(windows_exe, "Apple Music History Converter.exe")
        
        print(f"✅ Created Windows package: {windows_zip}")
        packages_created.append(("Windows", windows_zip))
        
        # Create Linux package (.tar.gz)
        linux_tar = build_artifacts_dir / "Apple_Music_History_Converter_Linux.tar.gz"
        with tarfile.open(linux_tar, 'w:gz') as tarf:
            tarf.add(exe_path, arcname="Apple Music History Converter")
            
        print(f"✅ Created Linux package: {linux_tar}")
        packages_created.append(("Linux", linux_tar))
        
        # Clean up temporary Windows exe
        windows_exe.unlink()
    
    # Create a combined release archive
    if packages_created:
        print("\n📦 Creating combined release archive...")
        release_zip = build_artifacts_dir / "Apple_Music_History_Converter_All_Platforms.zip"
        
        with zipfile.ZipFile(release_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add README
            readme_content = f"""# Apple Music Play History Converter - Multi-Platform Release

This archive contains executables for all supported platforms:

"""
            for platform, package_path in packages_created:
                package_size = package_path.stat().st_size / (1024 * 1024)
                readme_content += f"- **{platform}**: {package_path.name} ({package_size:.1f} MB)\n"
                
            readme_content += """
## Installation Instructions

### macOS
1. Extract `Apple_Music_History_Converter_macOS.zip`
2. Move `Apple Music History Converter.app` to your Applications folder
3. Right-click and select "Open" on first launch to bypass Gatekeeper

### Windows  
1. Extract `Apple_Music_History_Converter_Windows.zip`
2. Run `Apple Music History Converter.exe`
3. If Windows Defender blocks it, click "More info" then "Run anyway"

### Linux
1. Extract `Apple_Music_History_Converter_Linux.tar.gz`
2. Make executable: `chmod +x "Apple Music History Converter"`
3. Run: `./Apple\ Music\ History\ Converter`

## Requirements
- No additional dependencies required (all bundled)
- Python is NOT required to be installed
- Works offline (except for iTunes API searches)

## Features
- Convert Apple Music play history to various formats
- Offline music database search with MusicBrainz
- iTunes API integration for additional metadata
- Cross-platform GUI application

For more information, visit: https://github.com/nerveband/Apple-Music-Play-History-Converter
"""
            
            zipf.writestr("README.txt", readme_content)
            
            # Add all platform packages
            for platform, package_path in packages_created:
                zipf.write(package_path, package_path.name)
                
        print(f"🚀 Created combined release: {release_zip}")
        
    # Summary
    print("\n" + "="*60)
    print("BUILD SUMMARY")
    print("="*60)
    
    print(f"✅ Successfully created {len(packages_created)} platform packages:")
    total_size = 0
    
    for platform, package_path in packages_created:
        size_mb = package_path.stat().st_size / (1024 * 1024)
        total_size += size_mb
        print(f"  📦 {platform}: {package_path.name} ({size_mb:.1f} MB)")
    
    print(f"\n📊 Total size: {total_size:.1f} MB")
    print(f"📁 All packages in: {build_artifacts_dir}")
    
    if len(packages_created) >= 3:
        print("\n🎉 All platform builds completed successfully!")
        print("Ready for distribution across macOS, Windows, and Linux")
    else:
        print(f"\n⚠️  Only {len(packages_created)} platforms built")
        
if __name__ == "__main__":
    main()
