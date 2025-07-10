# macOS Installation Guide

## Opening the App

Since this app is not signed with an Apple Developer certificate, macOS will show a security warning. Here's how to open it:

### Method 1: Right-click to Open (Recommended)
1. Download and unzip the app
2. **Right-click** (or Control-click) on the app
3. Select **Open** from the context menu
4. Click **Open** in the dialog that appears
5. The app will now open and be remembered as safe

### Method 2: Security & Privacy Settings
1. Try to open the app normally (double-click)
2. When blocked, go to **System Settings** > **Privacy & Security**
3. Look for the message about the blocked app
4. Click **Open Anyway**
5. Enter your password if prompted

### Method 3: Terminal Command (Advanced)
If the above methods don't work, you can remove the quarantine flag:
```bash
xattr -cr "/Applications/Apple Music History Converter.app"
```

## Why This Happens

macOS uses Gatekeeper to protect users from potentially harmful software. Apps from unidentified developers (those without an Apple Developer certificate) are blocked by default. This is a security feature, not a problem with the app itself.

## For Developers

If you want to sign the app yourself:
1. Run the ad-hoc signing script: `./build_artifacts/adhoc_sign.sh`
2. This will remove the warning on YOUR machine only
3. For proper distribution, you'll need an Apple Developer account ($99/year)