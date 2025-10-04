# GitHub Actions Monitoring Tools

## Current Monitoring (Built-in GitHub CLI)

You're currently using the official **GitHub CLI (`gh`)** which is the best option:

```bash
# Watch a workflow run in real-time
gh run watch 18247243103

# List recent runs
gh run list --workflow="Build Application with Briefcase" --limit 5

# View detailed run status
gh run view 18247243103

# View failed logs
gh run view 18247243103 --log-failed

# Open in browser
gh run view 18247243103 --web
```

## Alternative Monitoring Tools

### 1. **act3** - Terminal UI for Last 3 Runs
```bash
# Install
brew install act3  # macOS
cargo install act3  # With Rust

# Usage
cd your-repo
act3
```
Shows a quick glance at the last 3 GitHub Actions runs in a terminal UI.

### 2. **Lazygit** - Git TUI with Actions Support
```bash
# Install
brew install lazygit  # macOS

# Usage
lazygit
```
Provides a terminal UI for git operations, including GitHub Actions status.

### 3. **ghat** - GitHub Actions Terminal
```bash
# Install (Node.js required)
npm install -g @ghat/cli

# Usage
ghat watch
```
Terminal-based monitoring for GitHub Actions workflows.

### 4. **Web-Based Monitoring**

**Best option for detailed monitoring:**
```bash
# Open current run in browser
gh run view 18247243103 --web
```

URL format:
```
https://github.com/nerveband/Apple-Music-Play-History-Converter/actions/runs/18247243103
```

## Recommended Workflow

### For Quick Status Checks:
```bash
# One-liner to check latest run
gh run list --workflow="Build Application with Briefcase" --limit 1
```

### For Active Monitoring (What You're Using Now):
```bash
# Watch in real-time with auto-refresh every 3 seconds
gh run watch 18247243103
```

### For Debugging Failures:
```bash
# View only failed job logs
gh run view 18247243103 --log-failed

# View specific job logs
gh run view 18247243103 --log --job=51956723822
```

### For Visual Monitoring:
```bash
# Open in browser for full visual interface
gh run view 18247243103 --web
```

## Real-Time Notifications

### macOS Notification when Build Completes:
```bash
#!/bin/bash
# Save as: watch_and_notify.sh

RUN_ID=$1
gh run watch $RUN_ID

# When complete, send notification
STATUS=$(gh run view $RUN_ID --json conclusion -q '.conclusion')
if [ "$STATUS" = "success" ]; then
    osascript -e 'display notification "GitHub Actions build succeeded! ✅" with title "Build Complete"'
else
    osascript -e 'display notification "GitHub Actions build failed ❌" with title "Build Failed"'
fi
```

Usage:
```bash
chmod +x watch_and_notify.sh
./watch_and_notify.sh 18247243103
```

## Advanced: Monitor Multiple Runs

```bash
#!/bin/bash
# Monitor all in-progress runs

while true; do
  clear
  echo "=== In-Progress GitHub Actions ==="
  gh run list --status in_progress --limit 5
  sleep 5
done
```

## Current Build Status

**Run ID**: `18247243103`
**URL**: https://github.com/nerveband/Apple-Music-Play-History-Converter/actions/runs/18247243103

**Watch Command** (already running in background):
```bash
gh run watch 18247243103
```

**Check Status**:
```bash
gh run view 18247243103
```

**Open in Browser**:
```bash
gh run view 18247243103 --web
```

## Tips

1. **GitHub CLI** is the official tool and works best for most use cases
2. **Web interface** is best for detailed debugging with full logs
3. **act3** is great for a quick terminal dashboard
4. **Notifications** (above script) are useful for long-running builds

## Troubleshooting

If `gh` commands aren't working:
```bash
# Login to GitHub
gh auth login

# Verify authentication
gh auth status

# Set repo context
cd /path/to/repo
```
