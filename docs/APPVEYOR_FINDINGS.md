# AppVeyor Research Findings

## Free Tier for Open Source: CONFIRMED ✅

**Official Pricing** (verified from https://www.appveyor.com/pricing/):

### Free Tier (Open-source)
- ✅ **Unlimited public projects**
- ✅ **1 concurrent job**
- ✅ **5 self-hosted jobs**
- ✅ **Community support**
- ✅ **No credit card required**
- ✅ **14 day trial** available

### Paid Tiers
- **Basic**: $29/month (1 private project, 1 concurrent job)
- **Pro**: $59/month (Unlimited private projects, 1 concurrent job)
- **Premium**: $99/month (Unlimited private projects, 2 concurrent jobs)

---

## macOS Support: EXISTS, Free Tier UNCLEAR ⚠️

### What We Know:

**✅ Confirmed**:
1. AppVeyor **DOES support macOS builds**
2. macOS images available: Sonoma (14.2.1), Ventura (13.6.4), Monterey (12.7.3)
3. macOS images updated as recently as February 2024
4. Pre-installed: Xcode, Python, .NET, Node.js, etc.
5. Multi-platform build matrix works (Windows + Linux + macOS)

**❓ Unclear**:
1. **Does the free tier include macOS builds?**
   - Pricing page doesn't explicitly confirm
   - Documentation shows macOS exists, but not pricing specifics
   - Self-hosted jobs definitely work on macOS (free tier: 5 jobs)

**📧 Official Recommendation**:
- Pricing page says: "For details, [contact them](mailto:team@appveyor.com)"

---

## Research Analysis

### Evidence FOR macOS Being Free:

1. **Free tier says "unlimited public projects"** - doesn't exclude any platforms
2. **macOS was added specifically for multi-platform support** (2019)
3. **Build matrix examples include macOS** in public documentation
4. **Self-hosted macOS jobs are free** (5 jobs included)
5. **AppVeyor's value prop is "multi-platform"** - would be odd to exclude it from free tier

### Evidence AGAINST macOS Being Free:

1. **macOS VMs are expensive to host** (cloud providers charge 2-3x more)
2. **Pricing page doesn't explicitly list platform support**
3. **Some CI services restrict macOS to paid plans** (CircleCI, Travis CI)
4. **"Contact us" message suggests custom pricing**

### Probability Estimate:

**60-70% chance macOS is free for open-source**

**Why**: AppVeyor's entire value proposition is multi-platform CI, and they explicitly market "Windows, Linux and macOS" together. Excluding macOS from the free tier would undermine their competitive advantage.

---

## AppVeyor CLI: LIMITED ⚠️

### What Exists:

**✅ Build Worker API** (`appveyor.exe`):
- **Purpose**: Available INSIDE builds (not for triggering builds)
- **Location**: Pre-installed in build environment
- **Commands**:
  - `Add-AppveyorMessage` - Add build messages
  - `Add-AppveyorCompilationMessage` - Report compilation errors
  - `Set-AppveyorBuildVariable` - Set variables
  - `Add-AppveyorTest` - Report test results
  - `Update-AppveyorBuild` - Update build status

**Example**:
```powershell
# Inside an AppVeyor build
appveyor AddMessage "Build started" -Category Information
appveyor SetVariable -Name MY_VAR -Value "test"
```

### What DOESN'T Exist:

**❌ No External CLI** for:
- Triggering builds from your terminal
- Viewing build status
- Downloading artifacts
- Managing projects

### Workarounds:

**Option 1: REST API**
```bash
# Trigger build via API
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  https://ci.appveyor.com/api/builds \
  -d '{"accountName":"nerveband","projectSlug":"apple-music-converter","branch":"main"}'
```

**Option 2: GitHub Integration**
- Connect AppVeyor to GitHub
- Builds trigger automatically on push
- View builds at https://ci.appveyor.com/

**Option 3: Community Tools**
- Some third-party CLI tools exist but not officially supported

---

## Comparison: AppVeyor vs GitHub Actions

| Feature | AppVeyor Free | GitHub Actions Free |
|---------|---------------|---------------------|
| **Windows** | ✅ Unlimited | ✅ 2,000 min/month |
| **Linux** | ✅ Unlimited | ✅ 2,000 min/month |
| **macOS** | ❓ Unknown | ✅ 2,000 min/month |
| **Concurrent Jobs** | 1 | Unlimited |
| **Private Repos** | ❌ No | ✅ Yes |
| **CLI Tool** | ⚠️ Limited (in-build only) | ✅ Full (`gh` CLI) |
| **Monitoring** | 🌐 Web only | ✅ CLI + Web |
| **Setup** | Simple YAML | Simple YAML |

---

## Recommendation

### Immediate Action: TEST IT (5 minutes)

**Why test instead of asking support?**
1. Faster than waiting for email response
2. Definitive answer
3. No commitment (free account, no credit card)
4. Can start using immediately if it works

**How to test**:

```yaml
# Create appveyor.yml
version: 1.0.{build}
image: macos-monterey

install:
  - pip3 install --version

build_script:
  - echo "macOS build works!"
  - python3 --version
  - sw_vers
```

**Test Steps**:
1. Go to https://ci.appveyor.com/
2. Sign up with GitHub (free, no credit card)
3. Add your repo
4. Create `appveyor.yml` above
5. Push to GitHub
6. Watch build at https://ci.appveyor.com/

**If it runs** → macOS is FREE! 🎉
**If it blocks** → macOS requires paid plan

### Best Case Scenario (macOS is free):

**AppVeyor becomes your single CI/CD solution**:
- Windows: ✅ Free unlimited
- Linux: ✅ Free unlimited
- macOS: ✅ Free unlimited
- **One YAML file** to maintain
- **One system** to monitor (web interface)

**Downside**: No full-featured CLI (but you have web interface)

### Worst Case Scenario (macOS requires paid):

**Decision Matrix**:

| Your Priority | Recommended Solution |
|---------------|---------------------|
| **Simplicity > Cost** | Pay $29/month for AppVeyor (all platforms, one system) |
| **Cost > Simplicity** | Hybrid: AppVeyor (Win/Linux) + GitHub Actions (macOS) = FREE |
| **Best of Both** | Fix GitHub Actions (Ubuntu 22.04) = All FREE, one system |

---

## AppVeyor Setup Guide (If You Test)

### 1. Sign Up (2 minutes)
```
https://ci.appveyor.com/signup
→ "Sign up with GitHub"
→ Authorize AppVeyor
```

### 2. Add Repository (1 minute)
```
→ Click "New Project"
→ Select your repo
→ Click "Add"
```

### 3. Create appveyor.yml (2 minutes)
```yaml
version: 1.3.1.{build}

# Test all 3 platforms
image:
  - Visual Studio 2022
  - Ubuntu2204
  - macos-monterey

install:
  - cmd: pip install briefcase
  - sh: pip3 install briefcase || pip install briefcase

build_script:
  - cmd: briefcase --version
  - sh: briefcase --version

test_script:
  - cmd: echo "Windows build works!"
  - sh: echo "Unix build works!"
```

### 4. Push and Watch
```bash
git add appveyor.yml
git commit -m "test: add AppVeyor CI"
git push origin feature/ui-rewrite
```

Then watch at: `https://ci.appveyor.com/project/[username]/[repo]`

---

## CLI Alternative: Web Dashboard

Since AppVeyor doesn't have a full CLI, you'll use:

**✅ Web Dashboard**:
- Live build logs: https://ci.appveyor.com/
- Build history
- Artifact downloads
- Re-run builds
- Cancel builds

**✅ Email Notifications**: Configure in project settings

**✅ Slack/Discord**: Webhook integrations available

**⚠️ No terminal-based monitoring** like `gh run watch`

---

## Summary

### What We Confirmed:

✅ **Free tier exists**: Unlimited public projects
✅ **Windows & Linux free**: Definitely included
✅ **macOS support exists**: Confirmed via documentation
❓ **macOS free tier**: Unknown - NEEDS TESTING
⚠️ **CLI limited**: In-build only, no external trigger/monitoring

### Next Step:

**TEST APPVEYOR WITH macOS** (5 minutes)
- Best way to get definitive answer
- Faster than waiting for support email
- Can start using immediately if it works

### Fallback Plans:

If macOS isn't free:
1. **Pay $29/month** (if simplicity worth it)
2. **Use hybrid**: AppVeyor (Win/Linux) + GitHub Actions (macOS)
3. **Fix GitHub Actions**: Change to Ubuntu 22.04 (all free)

---

## Contact Info

**Email**: team@appveyor.com
**Support Forum**: https://help.appveyor.com/
**Documentation**: https://www.appveyor.com/docs/

If you want to ask before testing, email:
> "Hi, does the free open-source tier include macOS builds for public repositories? We're considering AppVeyor for our multi-platform Python project."

---

## Files Created

- `docs/APPVEYOR_ALL_PLATFORMS.md` - Complete multi-platform setup guide
- `docs/APPVEYOR_FINDINGS.md` - This file (research findings)
- `docs/FREE_BUILD_SERVICES.md` - Comparison of all free CI services
- `docs/GITHUB_ACTIONS_LINUX_ISSUE.md` - GitHub Actions Ubuntu 24.04 issues

All documentation committed to `feature/ui-rewrite` branch.
