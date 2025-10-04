# GitHub Actions Test Plan - SAFE (No Public Release)

## ✅ Safety Check: The Workflow is Already Configured Safely

The `.github/workflows/build.yml` has **two separate triggers**:

1. **Manual Trigger (`workflow_dispatch`)**:
   - Builds all 3 platforms
   - Creates build artifacts
   - **DOES NOT create a release** ✅
   - **DOES NOT publish anything** ✅
   - Artifacts are only visible to you in GitHub Actions

2. **Tag Push (`push: tags: v*`)**:
   - Builds all 3 platforms
   - Creates build artifacts
   - **Creates a public GitHub release** ⚠️
   - Only runs when you `git push origin v1.3.1`

## Test Plan (100% Safe)

### Step 1: Add GitHub Secrets (Required for macOS Signing)

**Do this first** before pushing any code:

1. Go to: https://github.com/nerveband/Apple-Music-Play-History-Converter/settings/secrets/actions

2. Click "New repository secret" for each:
   - Name: `APPLE_ID` → Value: `nerveband@gmail.com`
   - Name: `APPLE_TEAM_ID` → Value: `7HQVB2S4BX`
   - Name: `APPLE_APP_SPECIFIC_PASSWORD` → Value: `enfg-cbng-xxzz-nxmb`

3. These are optional (workflow continues without them):
   - `MACOS_CERTIFICATE` (base64 p12 file - can skip for now)
   - `MACOS_CERTIFICATE_PASSWORD` (can skip for now)

### Step 2: Push Workflow File (Safe - No Build Yet)

```bash
cd "/Users/nerveband/wavedepth Dropbox/Ashraf Ali/Mac (2)/Documents/GitHub/Apple-Music-Play-History-Converter"

# The workflow file is already committed, just verify it exists
git status .github/workflows/build.yml

# If needed, commit and push (this doesn't trigger builds)
git add .github/workflows/build.yml
git commit -m "chore: update build workflow"
git push origin feature/ui-rewrite
```

**Note**: Pushing the workflow file does NOT trigger it. It only runs on manual trigger or tags.

### Step 3: Manually Trigger Test Build (Safe - No Release)

1. Go to: https://github.com/nerveband/Apple-Music-Play-History-Converter/actions

2. Click "Build Application with Briefcase" in the left sidebar

3. Click "Run workflow" button (top right)

4. Select branch: `feature/ui-rewrite` (or your current branch)

5. Click green "Run workflow" button

6. Wait ~20-30 minutes for all 3 platforms to build in parallel

### Step 4: Download and Test Artifacts (Private - Only You Can See)

1. When the workflow completes, click on the workflow run

2. Scroll down to "Artifacts" section

3. Download:
   - `macos-build` → DMG file
   - `windows-build` → MSI or EXE file
   - `linux-build` → AppImage + system package

4. Test each build on the respective platform

5. **These artifacts expire after 90 days** and are only visible to repo collaborators

### Step 5: Verify Nothing Was Published

✅ Check: https://github.com/nerveband/Apple-Music-Play-History-Converter/releases
- Should show **no new releases**
- Your test builds are private in GitHub Actions artifacts

## When Ready to Publish (Later)

Only when you've tested and are ready:

```bash
# Create and push a tag (this triggers public release)
git tag v1.3.1
git push origin v1.3.1
```

This will:
1. Build all 3 platforms
2. Create a **public** GitHub release
3. Upload all binaries to the release
4. Make everything publicly downloadable

## Troubleshooting Test Builds

### macOS Build Fails
- **Cause**: Missing secrets or invalid credentials
- **Fix**: Double-check GitHub secrets are correct
- **Workaround**: Workflow continues with `continue-on-error: true`
- **Note**: Without certificate, it will use ad-hoc signing (works for testing)

### Windows Build Fails
- **Cause**: Missing dependencies or Briefcase issues
- **Fix**: Check workflow logs for specific error
- **Expected**: Should create MSI without issues

### Linux Build Fails
- **Cause**: Missing system dependencies
- **Fix**: The workflow already installs required packages
- **Note**: AppImage build is optional, system package is fallback

## What Gets Built

| Platform | Output | Signed? | Size |
|----------|--------|---------|------|
| macOS | `.dmg` | ✅ Yes (with secrets) | ~113 MB |
| Windows | `.msi` | ❌ No (expected) | ~80-100 MB |
| Linux | `.AppImage` + `.tar.gz` | N/A | ~100-120 MB |

## Build Matrix (Runs in Parallel)

The workflow runs 3 jobs simultaneously:
- `macos-latest` → macOS 14 (Sonoma)
- `windows-latest` → Windows Server 2022
- `ubuntu-latest` → Ubuntu 22.04

Total time: ~20-30 minutes (all platforms in parallel)

## Cost

GitHub Actions is **free** for public repositories with generous limits:
- 2000 minutes/month for macOS runners
- Unlimited for Linux/Windows runners

Your test build will use ~60 minutes total (3 platforms × ~20 min each).

## Summary

✅ **100% Safe to Test**:
- Manual trigger creates artifacts only (private)
- No releases are created without tags
- Artifacts are only visible to you
- Test as many times as needed

⚠️ **Only Publish When Ready**:
- Push a tag to create public release
- This makes binaries publicly downloadable
- Only do this when you've tested everything

## Next Steps After Testing

1. Download all 3 artifacts from GitHub Actions
2. Test on each platform
3. Verify everything works
4. When ready, push a tag to create public release
5. Share the release URL with users
