# GitHub Secrets Setup for CI/CD

This document explains how to configure GitHub Secrets for automated builds with code signing and notarization.

## Required Secrets

The following secrets must be added to your GitHub repository for the CI/CD workflow to function properly:

### macOS Code Signing & Notarization

| Secret Name | Description | How to Get It |
|-------------|-------------|---------------|
| `MACOS_CERTIFICATE` | Base64-encoded .p12 certificate file | See instructions below |
| `MACOS_CERTIFICATE_PASSWORD` | Password for the .p12 certificate | Password you set when exporting certificate |
| `APPLE_ID` | Your Apple Developer account email | Your Apple ID email (e.g., nerveband@gmail.com) |
| `APPLE_TEAM_ID` | Your Apple Developer Team ID | Found in Apple Developer account (e.g., 7HQVB2S4BX) |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password for notarization | Generate from appleid.apple.com |

---

## Step-by-Step Setup Instructions

### 1. Export Your Code Signing Certificate

**On your Mac:**

1. Open **Keychain Access**
2. Select **My Certificates** in the left sidebar
3. Find your "Developer ID Application: Ashraf Ali (7HQVB2S4BX)" certificate
4. Right-click the certificate → **Export**
5. Save as: `certificate.p12`
6. Set a strong password (you'll need this for `MACOS_CERTIFICATE_PASSWORD`)
7. Save the file to a secure location

### 2. Encode the Certificate to Base64

**On your Mac terminal:**

```bash
# Encode the certificate
base64 -i ~/path/to/certificate.p12 | pbcopy
```

This copies the base64-encoded certificate to your clipboard. This will be the value for `MACOS_CERTIFICATE`.

### 3. Generate App-Specific Password

1. Go to https://appleid.apple.com/account/manage
2. Sign in with your Apple ID (nerveband@gmail.com)
3. Navigate to **Security** → **App-Specific Passwords**
4. Click **Generate an app-specific password**
5. Enter a label: "GitHub Actions Notarization"
6. Copy the generated password (format: `xxxx-xxxx-xxxx-xxxx`)
7. This is your `APPLE_APP_SPECIFIC_PASSWORD`

### 4. Find Your Team ID

**Option A: From Apple Developer Website**
1. Go to https://developer.apple.com/account
2. Click on **Membership** in the sidebar
3. Your Team ID is displayed (e.g., 7HQVB2S4BX)

**Option B: From Terminal**
```bash
# List all certificates and find the Team ID
security find-identity -v -p codesigning
# Output includes: "Developer ID Application: Your Name (TEAM_ID)"
```

### 5. Add Secrets to GitHub Repository

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each of the following secrets:

#### MACOS_CERTIFICATE
- Name: `MACOS_CERTIFICATE`
- Value: Paste the base64-encoded certificate (from Step 2)

#### MACOS_CERTIFICATE_PASSWORD
- Name: `MACOS_CERTIFICATE_PASSWORD`
- Value: The password you set when exporting the .p12 file

#### APPLE_ID
- Name: `APPLE_ID`
- Value: `nerveband@gmail.com`

#### APPLE_TEAM_ID
- Name: `APPLE_TEAM_ID`
- Value: `7HQVB2S4BX`

#### APPLE_APP_SPECIFIC_PASSWORD
- Name: `APPLE_APP_SPECIFIC_PASSWORD`
- Value: The app-specific password from Step 3 (e.g., `enfg-cbng-xxzz-nxmb`)

---

## Verification

After adding all secrets, you can verify they're configured:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. You should see all 5 secrets listed:
   - `MACOS_CERTIFICATE`
   - `MACOS_CERTIFICATE_PASSWORD`
   - `APPLE_ID`
   - `APPLE_TEAM_ID`
   - `APPLE_APP_SPECIFIC_PASSWORD`

---

## Local Testing (Before CI/CD)

Before pushing to GitHub, test the notarization process locally:

### Store Notarization Credentials Locally

```bash
# Load credentials from .env file
source .env

# Store credentials for Briefcase (one-time setup)
xcrun notarytool store-credentials "briefcase-macOS-$APPLE_TEAM_ID" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD"
```

### Build and Notarize Locally

```bash
# Create the app structure
briefcase create macOS

# Build the app
briefcase build macOS

# Package with signing and notarization
briefcase package macOS \
  --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"
```

### Verify Notarization

```bash
# Check code signature
codesign -vvv "build/apple-music-history-converter/macos/app/Apple Music History Converter.app"

# Check notarization status
spctl -a -t exec -vv "build/apple-music-history-converter/macos/app/Apple Music History Converter.app"

# Should output: "accepted, source=Notarized Developer ID"
```

---

## Troubleshooting

### "Certificate not found" Error

**Problem**: GitHub Actions can't find the certificate.

**Solution**:
- Verify `MACOS_CERTIFICATE` is properly base64-encoded
- Ensure `MACOS_CERTIFICATE_PASSWORD` matches the export password
- Check that the certificate hasn't expired in Keychain Access

### "Notarization failed" Error

**Problem**: Apple rejected the notarization.

**Solutions**:
- Verify `APPLE_ID` is correct
- Ensure `APPLE_APP_SPECIFIC_PASSWORD` is valid (not your regular Apple ID password)
- Check that `APPLE_TEAM_ID` matches your Developer account
- Verify your Apple Developer membership is active

### "Identity not found" Error

**Problem**: The signing identity doesn't match.

**Solution**:
- Verify the identity string exactly matches: `Developer ID Application: Ashraf Ali (7HQVB2S4BX)`
- Check your certificate is installed in Keychain Access
- Ensure the certificate hasn't expired

### Testing Notarization Credentials

```bash
# Test if credentials are stored correctly
xcrun notarytool history \
  --apple-id "nerveband@gmail.com" \
  --team-id "7HQVB2S4BX" \
  --password "your-app-specific-password"
```

---

## Security Best Practices

1. ✅ **Never commit** `.env` file or certificates to git
2. ✅ **Rotate** app-specific passwords periodically
3. ✅ **Use separate** app-specific passwords for different services
4. ✅ **Delete** the exported .p12 file after encoding it
5. ✅ **Backup** your certificate in a secure password manager
6. ⚠️ **Certificate expires**: Developer ID certificates are valid for 5 years - renew before expiration

---

## Reference: Current Configuration

Based on your `.env` file and `pyproject.toml`:

```bash
APPLE_ID=nerveband@gmail.com
APPLE_TEAM_ID=7HQVB2S4BX
APPLE_APP_SPECIFIC_PASSWORD=enfg-cbng-xxzz-nxmb
DEVELOPER_ID_APPLICATION="Developer ID Application: Ashraf Ali (7HQVB2S4BX)"
```

**Certificate Details:**
- Type: Developer ID Application
- Name: Ashraf Ali
- Team ID: 7HQVB2S4BX
- Use: Code signing and notarization for distribution outside Mac App Store

---

## Next Steps

After setting up GitHub Secrets:

1. ✅ Commit and push the updated `.github/workflows/build.yml`
2. ✅ Create a new git tag: `git tag -a v1.4.0 -m "Release v1.4.0"`
3. ✅ Push the tag: `git push origin v1.4.0`
4. ✅ GitHub Actions will automatically build, sign, notarize, and create a release

---

## Support

For issues with:
- **Certificate problems**: Check Apple Developer account and Keychain Access
- **Notarization issues**: Review Apple's notarization logs via `xcrun notarytool log`
- **GitHub Actions failures**: Check the workflow logs in the Actions tab

**Useful Commands:**

```bash
# View notarization log for a submission
xcrun notarytool log <submission-id> \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD"

# List recent notarization submissions
xcrun notarytool history \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD"
```
