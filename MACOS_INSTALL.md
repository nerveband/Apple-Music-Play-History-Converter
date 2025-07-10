# macOS Installation Guide

## Opening the App

Since this app is not signed with an Apple Developer certificate, macOS will show a security warning. Here's how to open it:

### Method 1: Remove Extended Attributes + Right-click (Recommended)
1. Download and unzip the app
2. **Remove extended attributes** (quarantine flags):
   ```bash
   xattr -cr "/path/to/Apple Music History Converter.app"
   ```
   Replace `/path/to/` with the actual path where you extracted the app
3. **Right-click** (or Control-click) on the app
4. Select **Open** from the context menu
5. Click **Open** in the dialog that appears
6. The app will now open and be remembered as safe

### Method 2: Security & Privacy Settings
1. Try to open the app normally (double-click)
2. When blocked, go to **System Settings** > **Privacy & Security**
3. Look for the message about the blocked app
4. Click **Open Anyway**
5. Enter your password if prompted

### Method 3: Terminal Command Only (Alternative)
If you prefer using only the terminal:
```bash
# Remove quarantine attributes
xattr -cr "/path/to/Apple Music History Converter.app"
# Then launch the app
open "/path/to/Apple Music History Converter.app"
```

## Troubleshooting

### App Bounces in Dock and Closes
If the app briefly appears in the dock but then closes immediately:

1. **First, try the xattr command**:
   ```bash
   xattr -cr "/path/to/Apple Music History Converter.app"
   ```

2. **If that doesn't work, run the executable directly**:
   ```bash
   "/path/to/Apple Music History Converter.app/Contents/MacOS/Apple Music History Converter"
   ```

3. **Check Console for error messages**:
   - Open Console.app (Applications > Utilities)
   - Look for crash reports or error messages related to the app

### Still Having Issues?
If the app bundle continues to fail but the direct executable works, you can create a simple launcher script:

```bash
#!/bin/bash
"/path/to/Apple Music History Converter.app/Contents/MacOS/Apple Music History Converter"
```

Save this as a `.command` file and make it executable with `chmod +x`.

## Why This Happens

macOS uses Gatekeeper to protect users from potentially harmful software. Apps from unidentified developers (those without an Apple Developer certificate) are blocked by default. This is a security feature, not a problem with the app itself.

## For Developers

If you want to sign the app yourself:
1. Run the ad-hoc signing script: `./build_artifacts/adhoc_sign.sh`
2. This will remove the warning on YOUR machine only
3. For proper distribution, you'll need an Apple Developer account ($99/year)