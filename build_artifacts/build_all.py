#!/usr/bin/env python3
"""
Multi-platform build script for Apple Music Play History Converter
Builds executables for macOS, Windows, and Linux
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
import argparse
import time

class BuildManager:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.build_dir = self.project_root / "build_artifacts"
        self.dist_dir = self.project_root / "build_artifacts" / "dist"
        self.current_platform = platform.system().lower()
        
    def setup_environment(self):
        """Setup build environment"""
        print("🔧 Setting up build environment...")
        
        # Install/upgrade build dependencies
        dependencies = [
            "pyinstaller>=6.0.0",
            "pip>=23.0.0",
        ]
        
        for dep in dependencies:
            print(f"Installing {dep}...")
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", dep], 
                         check=True, capture_output=True)
        
        # Install project dependencies
        print("Installing project dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", 
                       str(self.project_root / "requirements.txt")], check=True)
        
        print("✅ Environment setup complete")
        
    def clean_build_artifacts(self):
        """Clean previous build artifacts"""
        print("🧹 Cleaning previous build artifacts...")
        
        cleanup_dirs = [
            self.build_dir / "build",
            self.build_dir / "dist", 
            self.project_root / "__pycache__",
        ]
        
        cleanup_files = [
            self.build_dir / "dist.zip",
        ]
        
        for directory in cleanup_dirs:
            if directory.exists():
                shutil.rmtree(directory)
                print(f"Removed {directory}")
                
        for file in cleanup_files:
            if file.exists():
                file.unlink()
                print(f"Removed {file}")
                
        print("✅ Cleanup complete")
        
    def build_platform(self, target_platform):
        """Build for specific platform"""
        spec_file = self.build_dir / f"build_{target_platform}.spec"
        
        if not spec_file.exists():
            print(f"❌ Spec file not found: {spec_file}")
            return False
            
        print(f"🏗️  Building for {target_platform}...")
        start_time = time.time()
        
        try:
            # Run PyInstaller
            cmd = [
                sys.executable, "-m", "PyInstaller",
                "--clean",
                "--noconfirm", 
                str(spec_file)
            ]
            
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                check=True
            )
            
            build_time = time.time() - start_time
            print(f"✅ {target_platform} build completed in {build_time:.1f}s")
            
            # Verify build output
            self.verify_build(target_platform)
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Build failed for {target_platform}")
            print(f"Error: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            return False
            
    def verify_build(self, target_platform):
        """Verify build output"""
        dist_path = self.build_dir / "dist"
        
        if target_platform == "macos":
            app_path = dist_path / "Apple Music History Converter.app"
            if app_path.exists():
                size = self.get_dir_size(app_path)
                print(f"✅ macOS app created: {app_path} ({size:.1f} MB)")
            else:
                print(f"❌ macOS app not found at {app_path}")
                
        else:
            exe_name = "Apple Music History Converter"
            if target_platform == "windows":
                exe_name += ".exe"
            exe_path = dist_path / exe_name
            
            if exe_path.exists():
                size = exe_path.stat().st_size / (1024 * 1024)
                print(f"✅ {target_platform} executable created: {exe_path} ({size:.1f} MB)")
            else:
                print(f"❌ {target_platform} executable not found at {exe_path}")
                
    def get_dir_size(self, path):
        """Get directory size in MB"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                total_size += os.path.getsize(file_path)
        return total_size / (1024 * 1024)
        
    def create_distribution_packages(self):
        """Create distribution packages"""
        print("📦 Creating distribution packages...")
        
        dist_path = self.build_dir / "dist"
        if not dist_path.exists():
            print("❌ No dist directory found")
            return
            
        # Create individual archives for each platform
        for item in dist_path.iterdir():
            if item.is_dir() or item.is_file():
                archive_name = f"{item.stem}_{self.current_platform}"
                archive_path = self.build_dir / f"{archive_name}.zip"
                
                print(f"Creating {archive_path}...")
                if item.is_dir():
                    shutil.make_archive(str(archive_path.with_suffix('')), 'zip', str(item.parent), item.name)
                else:
                    # For single files, create a zip with the file inside
                    import zipfile
                    with zipfile.ZipFile(archive_path, 'w') as zipf:
                        zipf.write(item, item.name)
                        
        print("✅ Distribution packages created")
        
    def run_tests(self):
        """Run basic tests to verify the build"""
        print("🧪 Running build verification tests...")
        
        # Check if main modules can be imported
        test_imports = [
            "apple_music_play_history_converter",
            "musicbrainz_manager", 
            "music_search_service",
            "database_dialogs",
            "progress_dialog"
        ]
        
        for module in test_imports:
            try:
                __import__(module)
                print(f"✅ {module} imports successfully")
            except ImportError as e:
                print(f"❌ Failed to import {module}: {e}")
                return False
                
        print("✅ All modules import successfully")
        return True
        
    def build_all(self, platforms=None):
        """Build for all specified platforms"""
        if platforms is None:
            platforms = ["macos", "windows", "linux"]
            
        print("🚀 Starting multi-platform build process...")
        print(f"Target platforms: {', '.join(platforms)}")
        print(f"Current platform: {self.current_platform}")
        
        # Setup and clean
        self.setup_environment()
        self.clean_build_artifacts()
        
        # Run tests first
        if not self.run_tests():
            print("❌ Pre-build tests failed")
            return False
            
        # Build for each platform
        successful_builds = []
        failed_builds = []
        
        for platform_name in platforms:
            if self.build_platform(platform_name):
                successful_builds.append(platform_name)
            else:
                failed_builds.append(platform_name)
                
        # Create distribution packages
        if successful_builds:
            self.create_distribution_packages()
            
        # Summary
        print("\n" + "="*50)
        print("BUILD SUMMARY")
        print("="*50)
        
        if successful_builds:
            print(f"✅ Successfully built for: {', '.join(successful_builds)}")
            
        if failed_builds:
            print(f"❌ Failed to build for: {', '.join(failed_builds)}")
            
        if successful_builds:
            print(f"\n📁 Build artifacts location: {self.build_dir}")
            print(f"📁 Executables location: {self.dist_dir}")
            
        return len(failed_builds) == 0

def main():
    parser = argparse.ArgumentParser(description="Build Apple Music Play History Converter for multiple platforms")
    parser.add_argument("--platforms", nargs="+", 
                       choices=["macos", "windows", "linux"],
                       default=["macos", "windows", "linux"],
                       help="Platforms to build for")
    parser.add_argument("--clean-only", action="store_true",
                       help="Only clean build artifacts without building")
    
    args = parser.parse_args()
    
    builder = BuildManager()
    
    if args.clean_only:
        builder.clean_build_artifacts()
        return
        
    success = builder.build_all(args.platforms)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
