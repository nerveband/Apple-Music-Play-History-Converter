# Free Build Services for Windows & Linux

## Problem Statement

GitHub Actions on Ubuntu 24.04 has dependency conflicts with Toga/PyGObject, blocking automated Linux builds. We need free alternatives to build Windows and Linux versions without managing physical machines.

---

## ✅ Best Free Solutions (Ranked)

### 1. **AppVeyor** ⭐⭐⭐⭐⭐ RECOMMENDED FOR WINDOWS

**Free Tier**: Unlimited for public repos
**Platforms**: Windows (excellent), Linux (good)
**Best For**: Windows builds

**Why It's Great**:
- ✅ **FREE for public GitHub repos** (unlimited)
- ✅ **Excellent Windows support** (best-in-class)
- ✅ **Multiple Windows versions** (Server 2022, 2019, 2016)
- ✅ **Linux support** (Ubuntu 22.04, 20.04, 18.04)
- ✅ **Direct GitHub integration**
- ✅ **Simple YAML configuration**

**Setup**:
1. Go to https://ci.appveyor.com/
2. Sign in with GitHub
3. Add your repository
4. Create `appveyor.yml`:

```yaml
version: 1.3.1.{build}

image:
  - Visual Studio 2022  # Windows
  - Ubuntu2204          # Linux

environment:
  matrix:
    - PLATFORM: windows
      APPVEYOR_BUILD_WORKER_IMAGE: Visual Studio 2022
    - PLATFORM: linux
      APPVEYOR_BUILD_WORKER_IMAGE: Ubuntu2204

install:
  - python -m pip install --upgrade pip
  - pip install briefcase

build_script:
  - cmd: briefcase create windows
  - cmd: briefcase build windows
  - cmd: briefcase package windows --adhoc-sign

  - sh: briefcase create linux appimage
  - sh: briefcase build linux appimage
  - sh: briefcase package linux appimage

artifacts:
  - path: 'dist\*.msi'
    name: WindowsInstaller
  - path: 'dist/*.AppImage'
    name: LinuxAppImage
```

**Pros**:
- ✅ Unlimited builds for public repos
- ✅ Windows builds work perfectly
- ✅ Can use older Ubuntu versions (22.04)

**Cons**:
- ⚠️ No macOS support
- ⚠️ Private repos require paid plan

---

### 2. **GitLab CI/CD** ⭐⭐⭐⭐

**Free Tier**: 400 CI/CD minutes/month
**Platforms**: Linux (free), Windows (limited), macOS (self-hosted only)
**Best For**: Linux builds

**Why It's Good**:
- ✅ **400 minutes/month free**
- ✅ **Linux runners always available**
- ✅ **Can use Ubuntu 22.04** (avoid 24.04 issues)
- ✅ **Self-hosted runners supported**
- ✅ **Built-in container registry**

**Setup**:
1. Create `.gitlab-ci.yml`:

```yaml
stages:
  - build

build-linux:
  stage: build
  image: ubuntu:22.04
  script:
    - apt-get update
    - apt-get install -y python3 python3-pip libgirepository1.0-dev libcairo2-dev
    - pip install briefcase
    - briefcase create linux appimage
    - briefcase build linux appimage
    - briefcase package linux appimage
  artifacts:
    paths:
      - dist/*.AppImage

build-windows:
  stage: build
  tags:
    - windows  # Requires self-hosted runner
  script:
    - pip install briefcase
    - briefcase create windows
    - briefcase build windows
    - briefcase package windows --adhoc-sign
  artifacts:
    paths:
      - dist/*.msi
```

**Pros**:
- ✅ Linux builds work well
- ✅ Can mirror from GitHub automatically
- ✅ 400 minutes usually enough

**Cons**:
- ⚠️ Windows/macOS require self-hosted runners on free tier
- ⚠️ Minutes limit (vs unlimited on AppVeyor)

---

### 3. **CircleCI** ⭐⭐⭐

**Free Tier**: 6,000 build minutes/month
**Platforms**: Linux (free), macOS (medium tier), Windows (medium tier)
**Best For**: Linux builds with generous minutes

**Why It's Decent**:
- ✅ **6,000 minutes/month** (very generous!)
- ✅ **Excellent Linux support**
- ✅ **Good caching/parallelism**
- ✅ **GitHub integration**

**Setup**:
1. Sign up at https://circleci.com/
2. Create `.circleci/config.yml`:

```yaml
version: 2.1

jobs:
  build-linux:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run:
          name: Install dependencies
          command: |
            sudo apt-get update
            sudo apt-get install -y libgirepository1.0-dev libcairo2-dev
            pip install briefcase
      - run:
          name: Build Linux AppImage
          command: |
            briefcase create linux appimage
            briefcase build linux appimage
            briefcase package linux appimage
      - store_artifacts:
          path: dist

workflows:
  build:
    jobs:
      - build-linux
```

**Pros**:
- ✅ 6,000 minutes/month (most generous)
- ✅ Great for Linux
- ✅ Excellent documentation

**Cons**:
- ⚠️ Windows/macOS require paid tier
- ⚠️ More complex configuration

---

### 4. **Self-Hosted Runners (Free VPS)** ⭐⭐⭐⭐

**Cost**: FREE
**Platforms**: Any (Windows, Linux, macOS)
**Best For**: Full control, any platform

**Free VPS Providers**:

| Provider | Free Tier | Platforms | Duration |
|----------|-----------|-----------|----------|
| **Oracle Cloud** | 2 VMs (ARM/x86) | Linux only | Forever |
| **Google Cloud** | $300 credit | Windows/Linux | 90 days |
| **Azure** | $200 credit | Windows/Linux | 30 days |
| **AWS** | EC2 t2.micro | Linux only | 12 months |

**Oracle Cloud Free Tier** (BEST):
- ✅ **FREE FOREVER** (not a trial!)
- ✅ 2 AMD VMs (1GB RAM each)
- ✅ 4 ARM VMs (24GB RAM total!)
- ✅ Can run Linux builds indefinitely

**Setup with GitHub Actions**:
1. Create Oracle Cloud account (always free)
2. Launch Ubuntu 22.04 instance
3. Install GitHub Actions runner:

```bash
# On your Oracle Cloud VM
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.311.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.311.0.tar.gz
./config.sh --url https://github.com/nerveband/Apple-Music-Play-History-Converter --token YOUR_TOKEN
sudo ./svc.sh install
sudo ./svc.sh start
```

4. Update GitHub Actions workflow:

```yaml
jobs:
  build-linux:
    runs-on: self-hosted  # Uses your Oracle Cloud VM
    steps:
      - uses: actions/checkout@v4
      - run: pip install briefcase
      - run: briefcase package linux appimage
```

**Pros**:
- ✅ Completely FREE (Oracle forever, others for trial period)
- ✅ Full control over environment
- ✅ Can use Ubuntu 22.04 (avoid 24.04 issues)
- ✅ Works with GitHub Actions

**Cons**:
- ⚠️ Requires setup and maintenance
- ⚠️ VM management overhead

---

## 🎯 My Recommendation: Hybrid Strategy

### **For Your Use Case**:

**Windows Builds**: Use **AppVeyor** (FREE, unlimited, excellent Windows support)
**Linux Builds**: Use **Oracle Cloud Free Tier** with GitHub Actions (FREE forever, full control)
**macOS Builds**: Keep using GitHub Actions (already working!)

### **Implementation Plan**:

**Step 1: AppVeyor for Windows (10 minutes)**
1. Sign up at https://ci.appveyor.com/
2. Connect GitHub repo
3. Add `appveyor.yml` (see above)
4. Done! Free Windows builds forever

**Step 2: Oracle Cloud for Linux (30 minutes)**
1. Create Oracle Cloud account (https://cloud.oracle.com/free)
2. Create Ubuntu 22.04 instance (always free tier)
3. Install GitHub Actions self-hosted runner
4. Update `.github/workflows/build.yml` to use `runs-on: self-hosted` for Linux
5. Done! Free Linux builds forever

**Step 3: Keep macOS on GitHub Actions**
- Already working
- No changes needed
- Fully automated

**Result**:
- ✅ All 3 platforms build automatically
- ✅ Completely FREE
- ✅ No monthly limits (AppVeyor unlimited, Oracle forever free)
- ✅ Full automation via GitHub/AppVeyor

---

## Comparison Table

| Service | Free Windows | Free Linux | Free macOS | Minutes/Month | Best For |
|---------|--------------|------------|------------|---------------|----------|
| **AppVeyor** | ✅ Unlimited | ✅ Unlimited | ❌ | Unlimited | **Windows** |
| **GitLab CI** | ⚠️ Self-hosted | ✅ 400 min | ⚠️ Self-hosted | 400 | Linux |
| **CircleCI** | ❌ Paid | ✅ 6000 min | ❌ Paid | 6,000 | Linux (generous) |
| **Travis CI** | ⚠️ Limited | ✅ Limited | ❌ Paid | Limited | Open source |
| **Oracle Cloud + GH** | ⚠️ Setup | ✅ Unlimited | ❌ | Unlimited | **Linux forever** |
| **GitHub Actions** | ✅ 2000 min | ✅ 2000 min | ✅ 2000 min | 2,000 | **macOS** |

---

## Quick Setup Guide

### AppVeyor (Windows)

```bash
# 1. Go to https://ci.appveyor.com/
# 2. Sign in with GitHub
# 3. Add your repo
# 4. Create appveyor.yml (see above)
# 5. Push to GitHub
# Done! Builds start automatically
```

### Oracle Cloud (Linux)

```bash
# 1. Create account: https://cloud.oracle.com/free
# 2. Create Ubuntu 22.04 instance (Always Free tier)
# 3. SSH into instance and run:
sudo apt-get update
sudo apt-get install -y python3 python3-pip git
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.311.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.311.0.tar.gz

# 4. Get runner token from:
# https://github.com/nerveband/Apple-Music-Play-History-Converter/settings/actions/runners/new

# 5. Configure runner:
./config.sh --url https://github.com/nerveband/Apple-Music-Play-History-Converter --token YOUR_TOKEN
sudo ./svc.sh install
sudo ./svc.sh start

# 6. Update .github/workflows/build.yml:
# Change ubuntu-latest to self-hosted for Linux job

# Done! Free Linux builds forever
```

---

## Cost Analysis

| Solution | Setup Time | Monthly Cost | Maintenance | Best Use Case |
|----------|-----------|--------------|-------------|---------------|
| AppVeyor | 10 min | $0 | None | Windows builds |
| Oracle Cloud | 30 min | $0 | Minimal | Linux builds |
| GitLab CI | 15 min | $0 (400 min) | None | Simple Linux |
| CircleCI | 15 min | $0 (6000 min) | None | High-volume Linux |

**Winner for This Project**: AppVeyor (Windows) + Oracle Cloud (Linux) + GitHub Actions (macOS)

---

## Summary

You have **completely FREE** options to build all platforms:

1. ✅ **Windows**: AppVeyor (FREE unlimited, public repos)
2. ✅ **Linux**: Oracle Cloud Free Tier (FREE forever) + GitHub Actions self-hosted runner
3. ✅ **macOS**: GitHub Actions (already working)

**Total Cost**: $0/month
**Total Setup Time**: ~40 minutes
**Result**: Fully automated builds for all 3 platforms

No expensive VPS, no monthly fees, no limits.
