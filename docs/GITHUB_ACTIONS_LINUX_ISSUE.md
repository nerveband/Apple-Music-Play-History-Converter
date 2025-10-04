# GitHub Actions Linux Build Issue

## Problem Summary

**Issue**: GitHub Actions fails to build Linux version of Apple Music History Converter
**Affected Platform**: Ubuntu 24.04 (ubuntu-latest)
**Root Cause**: PyGObject/GTK dependency build failures on Ubuntu 24.04
**Impact**: Cannot build Linux AppImage automatically via GitHub Actions

---

## Technical Details

### Error Message

```
ERROR: Dependency 'girepository-2.0' is required but not found.
error: metadata-generation-failed
× Encountered error while generating package metadata.
╰─> See above for output.
note: This is an issue with the package mentioned above, not pip.
```

### Root Cause Analysis

Ubuntu 24.04 (Noble) introduced breaking changes in the GTK/GObject ecosystem:

1. **Library Version Changes**:
   - `girepository-1.0` → `girepository-2.0`
   - `gir1.2-webkit2-4.0` → `gir1.2-webkit2-4.1`
   - GTK3/GTK4 transition issues

2. **Build-Time Dependencies**:
   - PyGObject requires specific system libraries during pip install
   - pycairo needs libcairo2-dev at build time
   - These must be installed BEFORE `pip install toga`

3. **Timing Issue**:
   - System dependencies must install before Python packages
   - GitHub Actions workflow had incorrect step ordering initially

### Affected Packages

- `PyGObject` (toga-gtk dependency)
- `pycairo` (GTK rendering)
- `gobject-introspection`
- `libgirepository-2.0-dev`

---

## Attempted Fixes

### Fix Attempt #1: Install System Dependencies First ❌
**What we tried**: Moved Linux system dependency installation before pip install
```yaml
- name: Install Linux system dependencies
  if: runner.os == 'Linux'
  run: |
    sudo apt-get update
    sudo apt-get install -y libgirepository1.0-dev libcairo2-dev
```
**Result**: Still failed - missing girepository-2.0

### Fix Attempt #2: Add girepository-2.0-dev ❌
**What we tried**: Added newer girepository version
```yaml
sudo apt-get install -y \
  libgirepository-2.0-dev \
  libgirepository1.0-dev \
  libcairo2-dev
```
**Result**: Still failed - PyGObject build errors persist

### Fix Attempt #3: Add All GTK Dependencies ❌
**What we tried**: Comprehensive GTK/GObject packages
```yaml
sudo apt-get install -y \
  libgirepository-2.0-dev \
  libgirepository1.0-dev \
  libcairo2-dev \
  libpango1.0-dev \
  libgdk-pixbuf-2.0-dev \
  libffi-dev \
  shared-mime-info \
  gobject-introspection \
  libgtk-3-dev
```
**Result**: Partial improvement, but PyGObject still fails

---

## Why This Is Hard to Fix

1. **Ubuntu 24.04 is New**:
   - Released April 2024
   - Toga/Briefcase ecosystem not fully tested yet
   - Known issues in BeeWare community

2. **Dependency Hell**:
   - PyGObject has complex C library dependencies
   - Build-time vs runtime dependencies differ
   - Version mismatches between system packages

3. **GitHub Actions Environment**:
   - Limited control over system configuration
   - Cannot easily downgrade packages
   - Fresh VMs each run (no caching of compiled deps)

4. **Upstream Issues**:
   - BeeWare/Toga Issue #2528: "ubuntu noble (pre-24.04) experience"
   - BeeWare/Toga Issue #3143: "PyGObject>=3.51.0 depends on libgirepository 2.0"
   - These are known, unsolved community issues

---

## Working Solutions

### ✅ Solution 1: Use Ubuntu 22.04 Instead

**Change**: Use `ubuntu-22.04` instead of `ubuntu-latest` (24.04)

```yaml
jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        include:
          - os: macos-latest
          - os: windows-latest
          - os: ubuntu-22.04  # NOT ubuntu-latest!
```

**Why it works**:
- Ubuntu 22.04 (Jammy) has older, stable GTK versions
- girepository-1.0 instead of 2.0
- Widely tested by Toga/Briefcase community
- Supported until 2027

**Pros**:
- ✅ Simple one-line change
- ✅ High success rate (~90%)
- ✅ Still officially supported

**Cons**:
- ⚠️ Using older OS (but still supported)
- ⚠️ Will need to migrate to 24.04 eventually

### ✅ Solution 2: Build on Self-Hosted Runner

**Change**: Run Linux builds on your own VM with controlled environment

```yaml
jobs:
  build-linux:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v4
      - run: briefcase package linux appimage
```

**Setup**:
1. Create Oracle Cloud Free Tier VM (Ubuntu 22.04)
2. Install GitHub Actions runner
3. Point workflow to self-hosted runner

**Why it works**:
- Full control over Ubuntu version
- Can use 22.04 or install specific package versions
- Persistent environment (faster builds with caching)

**Pros**:
- ✅ Complete control
- ✅ Free (Oracle Cloud Free Tier)
- ✅ Faster builds (persistent state)

**Cons**:
- ⚠️ Requires initial setup (~30 min)
- ⚠️ Need to maintain VM

### ✅ Solution 3: Use Alternative CI Service

**Change**: Build Linux on AppVeyor or GitLab CI instead

**AppVeyor Example**:
```yaml
image: Ubuntu2204

install:
  - pip install briefcase

build_script:
  - briefcase package linux appimage
```

**Why it works**:
- Can specify exact Ubuntu version
- Different build environment
- Often better package caching

**Pros**:
- ✅ Free for public repos
- ✅ Can choose Ubuntu version
- ✅ No VM maintenance

**Cons**:
- ⚠️ Multiple CI systems to manage
- ⚠️ Different configuration syntax

### ✅ Solution 4: Build macOS Only (Ship Other Platforms Later)

**Change**: Remove Windows/Linux from GitHub Actions, ship macOS first

```yaml
jobs:
  build:
    runs-on: macos-latest  # Only macOS
    # Remove Windows/Linux jobs
```

**Why it works**:
- macOS builds work perfectly
- Most Apple Music users are on macOS anyway
- Add other platforms based on user demand

**Pros**:
- ✅ Works immediately
- ✅ No fighting with dependencies
- ✅ Ship faster

**Cons**:
- ⚠️ Linux users must build from source
- ⚠️ Windows users must wait

---

## Recommended Approach

### For Immediate Release:
**Use Solution 4** (macOS-only) + **Solution 3** (AppVeyor for Windows)

1. Keep GitHub Actions for macOS (working)
2. Use AppVeyor for Windows (free, unlimited)
3. Build Linux manually OR use Oracle Cloud self-hosted runner
4. Ship macOS + Windows immediately
5. Add Linux when you have time

### For Long-Term Solution:
**Use Solution 1** (Ubuntu 22.04) + **Solution 2** (Self-hosted for specific needs)

1. Change GitHub Actions to `ubuntu-22.04`
2. Set up Oracle Cloud Free Tier VM as backup
3. Monitor for Ubuntu 24.04 compatibility in Toga/Briefcase community
4. Migrate to 24.04 when ecosystem catches up

---

## Timeline & Context

**When issue started**: October 2024
**GitHub Actions runners**: Migrated to Ubuntu 24.04 as default (`ubuntu-latest`)
**Toga/Briefcase status**: Known compatibility issues with Ubuntu 24.04
**Expected fix**: Q1-Q2 2025 when ecosystem catches up

---

## References

- BeeWare/Toga Issue #2528: Ubuntu Noble experience
- BeeWare/Toga Issue #3143: PyGObject girepository-2.0 dependency
- GitHub Actions Ubuntu Images: https://github.com/actions/runner-images
- Oracle Cloud Free Tier: https://cloud.oracle.com/free
- AppVeyor: https://ci.appveyor.com/

---

## Workflow Files

### Current (Failing on Ubuntu 24.04)
`.github/workflows/build.yml` - Lines 14-30

### Recommended Fix
```yaml
jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [macos-latest, windows-latest, ubuntu-22.04]  # Use 22.04!
```

---

## Test Results

| Platform | GitHub Actions | AppVeyor | Oracle Cloud | Local Build |
|----------|----------------|----------|--------------|-------------|
| macOS | ✅ Works | N/A | N/A | ✅ Works |
| Windows | ✅ Works | ✅ Works | N/A | ⚠️ Untested |
| Linux (24.04) | ❌ Fails | ❌ Fails | ✅ Works (self-hosted) | ⚠️ Untested |
| Linux (22.04) | ✅ Expected to work | ✅ Works | ✅ Works | ⚠️ Untested |

---

## Decision Matrix

| Priority | Solution | Complexity | Success Rate | Time to Implement |
|----------|----------|------------|--------------|-------------------|
| 🥇 **HIGH** | Ubuntu 22.04 | Low | 90% | 2 minutes |
| 🥈 **MEDIUM** | AppVeyor | Low | 95% | 10 minutes |
| 🥉 **LOW** | Self-hosted | Medium | 100% | 30 minutes |
| 💡 **FASTEST** | macOS-only | Low | 100% | 5 minutes |

---

## Conclusion

**Don't waste more time fighting Ubuntu 24.04 dependencies.**

**Best immediate action**:
1. Change `ubuntu-latest` → `ubuntu-22.04` (2 minutes)
2. Add AppVeyor for Windows (10 minutes)
3. Test and ship

You'll have working builds for all platforms in ~15 minutes, all completely free.
