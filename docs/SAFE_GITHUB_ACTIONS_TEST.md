# Safe GitHub Actions Testing - Step-by-Step Guide

## ✅ Safety Guarantee: This Process Will NOT Create Any Public Releases

The workflow is configured with two separate triggers:
- **`workflow_dispatch`** (manual trigger) → Builds apps, creates artifacts, **NO PUBLIC RELEASE**
- **`push: tags: v*`** (tag push) → Builds apps, **CREATES PUBLIC RELEASE**

We will use `workflow_dispatch` to safely test without any public release.

---

## Step 1: Add GitHub Secrets (Required for macOS Signing)

These are needed for the workflow to sign and notarize the macOS build.

### 1.1: Go to Repository Secrets Page

**URL**: https://github.com/nerveband/Apple-Music-Play-History-Converter/settings/secrets/actions

(Or navigate: Repository → Settings → Secrets and variables → Actions)

### 1.2: Add Each Secret

Click **"New repository secret"** for each of the following:

| Secret Name | Value |
|-------------|-------|
| `APPLE_ID` | `nerveband@gmail.com` |
| `APPLE_TEAM_ID` | `7HQVB2S4BX` |
| `APPLE_APP_SPECIFIC_PASSWORD` | `enfg-cbng-xxzz-nxmb` |

**Note**: The certificate secrets (`MACOS_CERTIFICATE` and `MACOS_CERTIFICATE_PASSWORD`) are optional. The workflow will use the stored keychain credentials from the notarytool setup instead.

### 1.3: Verify Secrets Added

After adding all 3 secrets, you should see them listed on the Secrets page (values are hidden for security).

---

## Step 2: Manually Trigger the Workflow (100% Safe)

### 2.1: Go to Actions Page

**URL**: https://github.com/nerveband/Apple-Music-Play-History-Converter/actions

### 2.2: Select the Workflow

Click **"Build Application with Briefcase"** in the left sidebar

### 2.3: Trigger the Workflow

1. Click the **"Run workflow"** dropdown button (top right, blue button)
2. Select branch: **`feature/ui-rewrite`**
3. Click **"Run workflow"** button

### 2.4: Monitor Progress

The workflow will start immediately. You'll see:
- **3 parallel jobs**: macOS, Windows, Linux
- **Live logs** for each platform
- **Progress indicators** showing build steps

**Expected Duration**: ~20-30 minutes total (all platforms build in parallel)

---

## Step 3: Wait for Builds to Complete

### What Happens During the Build

**macOS Job** (~25-30 minutes):
- ✅ Checks out code
- ✅ Sets up Python 3.12
- ✅ Installs dependencies (toga, pandas, duckdb, etc.)
- ✅ Runs `briefcase create macOS`
- ✅ Runs `briefcase build macOS`
- ✅ Signs with Developer ID certificate
- ✅ Creates DMG
- ✅ Submits to Apple for notarization (5-10 min wait)
- ✅ Staples notarization ticket
- ✅ Uploads DMG as artifact

**Windows Job** (~15-20 minutes):
- ✅ Checks out code
- ✅ Sets up Python 3.12
- ✅ Installs dependencies
- ✅ Runs `briefcase create windows`
- ✅ Runs `briefcase build windows`
- ✅ Creates MSI installer (unsigned, expected)
- ✅ Uploads MSI as artifact

**Linux Job** (~20-25 minutes):
- ✅ Checks out code
- ✅ Sets up Python 3.12
- ✅ Installs system dependencies (GTK, Cairo, etc.)
- ✅ Installs Python dependencies
- ✅ Runs `briefcase create linux appimage`
- ✅ Runs `briefcase build linux appimage`
- ✅ Creates AppImage
- ✅ Creates system package (tar.gz)
- ✅ Uploads both as artifacts

---

## Step 4: Download Build Artifacts (Private - Only You Can See)

### 4.1: When Workflow Completes

All 3 jobs should show green checkmarks ✅

If any job fails, click on it to see the logs and troubleshoot.

### 4.2: Scroll Down to "Artifacts" Section

At the bottom of the workflow run page, you'll see:
- **macos-build** (113-120 MB)
- **windows-build** (80-100 MB)
- **linux-build** (100-120 MB)

### 4.3: Download Each Artifact

Click each artifact name to download a ZIP file containing:
- `macos-build.zip` → contains `Apple_Music_History_Converter_macOS.dmg`
- `windows-build.zip` → contains `Apple_Music_History_Converter_Windows.msi`
- `linux-build.zip` → contains `Apple_Music_History_Converter_Linux.AppImage` + `.tar.gz`

### 4.4: Extract and Test

Extract each ZIP and test the apps on the respective platforms.

---

## Step 5: Verify No Public Release Was Created

### Check Releases Page

**URL**: https://github.com/nerveband/Apple-Music-Play-History-Converter/releases

**Expected Result**: No new releases should appear.

The artifacts are **private** and only visible to:
- Repository collaborators
- Anyone with access to the repository

Artifacts **expire after 90 days** and are not publicly downloadable.

---

## Step 6: Test the Downloaded Builds

### macOS Testing:
```bash
# Extract the DMG from the ZIP
unzip macos-build.zip

# Mount the DMG
open Apple_Music_History_Converter_macOS.dmg

# Drag app to Applications
# Launch from Applications folder

# Should launch with NO security warnings ✅
```

### Windows Testing:
```powershell
# Extract MSI from ZIP
Expand-Archive windows-build.zip

# Run the MSI installer
.\Apple_Music_History_Converter_Windows.msi

# When SmartScreen appears (expected):
# 1. Click "More info"
# 2. Click "Run anyway"
# 3. Complete installation
# 4. Launch from Start Menu
```

### Linux Testing:
```bash
# Extract AppImage from ZIP
unzip linux-build.zip

# Make it executable
chmod +x Apple_Music_History_Converter_Linux.AppImage

# Run it
./Apple_Music_History_Converter_Linux.AppImage

# Should launch on any modern Linux distribution ✅
```

---

## Troubleshooting

### macOS Build Fails with "Notarization Error"

**Cause**: Missing or incorrect Apple secrets

**Fix**:
1. Double-check GitHub secrets are correct
2. Verify Apple app-specific password is still valid
3. Check if Developer ID certificate is valid

**Workaround**: The workflow continues even if notarization fails (with `continue-on-error: true`). You'll get an unsigned DMG that still works for testing.

### Windows Build Fails

**Common Causes**:
- Missing dependencies
- Briefcase version issues

**Fix**: Check the workflow logs for specific errors. Most issues are transient and can be fixed by re-running the workflow.

### Linux Build Fails

**Common Causes**:
- Missing system dependencies
- AppImage build issues

**Fix**: The workflow installs required dependencies automatically. If AppImage build fails, it falls back to system package (tar.gz).

### Artifacts Not Appearing

**Cause**: Build failed before packaging step

**Fix**:
1. Check workflow logs for errors
2. Look for red ❌ indicators in job steps
3. Re-run failed jobs

---

## When Ready to Create Public Release (Later)

**⚠️ Only do this when you've tested everything and are ready for public release!**

### Option 1: Create Release from Tag

```bash
# Create and push a tag
git tag v1.3.1
git push origin v1.3.1
```

This will:
1. ✅ Build all 3 platforms
2. ✅ Create a **public** GitHub release
3. ✅ Upload all binaries to the release
4. ✅ Make everything publicly downloadable

### Option 2: Create Release Manually

1. Download artifacts from successful workflow run
2. Go to https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/new
3. Create tag `v1.3.1`
4. Upload all 3 build files
5. Add release notes (use `docs/RELEASE_NOTES_TEMPLATE.md`)
6. Publish release

---

## Summary

✅ **Safe Testing Complete When**:
- All 3 platforms built successfully
- Downloaded and tested each build
- No public releases were created
- Everything works as expected

✅ **Ready for Public Release When**:
- Tested on all platforms
- No major bugs found
- Ready for users to download
- Release notes prepared

⚠️ **Remember**:
- **Manual workflow trigger** = Private artifacts only
- **Tag push** = Public release
- Artifacts expire after 90 days
- Only you can see workflow artifacts

---

## Build Costs (GitHub Actions)

**Free for Public Repositories**:
- 2000 minutes/month for macOS runners
- Unlimited for Linux/Windows runners

**This Test Build Will Use**:
- ~25 minutes macOS
- ~15 minutes Windows
- ~20 minutes Linux
- **Total**: ~60 minutes (~3% of free monthly limit)

You can run ~33 test builds per month for free.

---

## Questions?

If you encounter any issues:
1. Check the workflow logs in GitHub Actions
2. Look for specific error messages
3. Check this guide's troubleshooting section
4. Re-run the workflow (often fixes transient issues)
