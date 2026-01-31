# Render.com Deployment Guide

## Step 1: Prepare GitHub Repository

### 1.1 Ensure Correct Branch Structure
This project uses a two-branch strategy:
- **main**: Clean branch without code (for documentation)
- **poc_pdfparser**: Deployment branch with all code at root level

### 1.2 Verify Repository Setup
Repository: `https://github.com/AIGuild2025/CCRewardsDashboard`
- Code is on **poc_pdfparser** branch
- All application files are at repository root (not in subfolder)

---

## Step 2: Deploy on Render.com

### 2.1 Create Render Account
1. Go to https://render.com
2. Sign up with GitHub (easier deployment)
3. Click **Settings** → **Authorized Apps** → **GitHub**

### 2.2 Authorize Render GitHub App
1. Click **Configure** next to GitHub
2. Choose **"Only select repositories"** or **"All repositories"**
3. If selecting specific repos, add: `AIGuild2025/CCRewardsDashboard`
4. Click **Install & Authorize**

### 2.3 Create New Web Service
1. Click **"New +"** → **"Web Service"**
2. Select repository: `AIGuild2025/CCRewardsDashboard`
3. Configure deployment settings:

| Field | Value | Notes |
|-------|-------|-------|
| **Name** | `cc-rewards-transaction-parser-api` | Your service name |
| **Region** | Singapore / Oregon | Choose closest to users |
| **Branch** | `poc_pdfparser` | **Important: Use poc_pdfparser, not main** |
| **Root Directory** | (leave empty) | Code is already at root |
| **Runtime** | `Python 3` | Auto-detected |
| **Build Command** | `pip install -r requirements.txt` | Installs dependencies |
| **Start Command** | `uvicorn api:app --host 0.0.0.0 --port $PORT` | Starts FastAPI server |
| **Plan** | **Free** | 750 hours/month |

### 2.4 Add Environment Variables
Click **"Advanced"** → **"Add Environment Variable"**, then add:

| Key | Value | Required |
|-----|-------|----------|
| `GROQ_API_KEY` | Your Groq API key from console | ✅ Required |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | ✅ Required |
| `LLM_TEMPERATURE` | `0.1` | Recommended |
| `TEXTRACT_ENABLED` | `false` | Optional |
| `PII_MASKING_ENABLED` | `true` | Optional |
| `ENCRYPTION_KEY` | Base64-encoded encryption key | ✅ Required for password-protected PDFs |

**To get ENCRYPTION_KEY value:**
```powershell
# On your local machine
$key = Get-Content .encryption_key -Raw
[System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($key.Trim()))
```

### 2.5 Deploy
1. Click **"Create Web Service"**
2. Wait for build (3-5 minutes)
3. Watch build logs for any errors
4. Get your URL: `https://cc-rewards-transaction-parser-api.onrender.com`

---

## Step 3: Password Management

The API now supports environment-based encryption key:

1. **Local development**: Uses `.encryption_key` file
2. **Render deployment**: Uses `ENCRYPTION_KEY` environment variable
3. Both decrypt the same `secrets.yaml.enc` file (which is in git)

**Security:**
- ✅ Encryption key never committed to git
- ✅ Encrypted passwords (`secrets.yaml.enc`) safe in git
- ✅ Key stored securely in Render environment variables

---

## Step 4: Test Deployment

### 4.1 Check Health (No Authentication Required)
```powershell
curl https://cc-rewards-transaction-parser-api.onrender.com/health
```

Expected response:
```json
{"status":"healthy","service":"Credit Card Rewards Parser API","version":"1.0.0"}
```

**Note:** First request after deployment or cold start may take 30-60 seconds.

### 4.2 Test with Postman
1. Import `CCRewardsDashboard_API_Render.postman_collection.json` into Postman
2. Collection is pre-configured with:
   - Base URL: `https://cc-rewards-transaction-parser-api.onrender.com`
   - Auth token: `cc_user1_token_2026`
3. Try these requests in order:
   - **Health Check** (fastest, no auth)
   - **Get All Categories** (lightweight test with auth)
   - **Parse PDF (Fast)** (full workflow test)

### 4.3 Test from PowerShell
```powershell
# Test authenticated endpoint
$headers = @{
    "Authorization" = "Bearer cc_user1_token_2026"
}

Invoke-RestMethod -Uri "https://cc-rewards-transaction-parser-api.onrender.com/api/v1/categories" -Headers $headers
```

---

## Important Notes

### Cold Starts
- **Free tier sleeps after 15 minutes of inactivity**
- First request after sleep takes **30-60 seconds** to wake up
- Subsequent requests are fast (3-6 seconds for parsing)
- Consider **Starter Plan ($7/month)** for always-on service

### File Storage
- Render uses **ephemeral storage** (resets on restart)
- `temp_uploads/` folder data is cleared periodically
- Uploaded PDFs are processed and deleted immediately
- No persistent file storage on free tier

### Python Version
- Uses **Python 3.13** (as specified in `runtime.txt`)
- Updated to Python 3.13-compatible packages:
  - `pydantic>=2.10.0`
  - `cryptography>=44.0.0`
  - `pydantic-settings>=2.7.0`

### SSL Certificate
- Automatically provided by Render
- HTTPS enabled by default
- No configuration needed

### Auto-Deploy
- Pushing to `poc_pdfparser` branch triggers automatic redeployment
- Build typically takes 2-3 minutes
- Monitor in **Logs** tab

---

## Monitoring & Management

### View Logs
1. Go to your service on Render dashboard
2. Click **"Logs"** tab
3. Real-time logs show:
   - API requests
   - LLM processing time
   - Error messages
   - Cold start events

### Manual Deploy
**Dashboard → Manual Deploy → "Clear build cache & deploy"**

Use this when:
- Build cache causes issues
- Environment variables changed
- Need to force fresh deployment

### Update Environment Variables
1. Go to **Environment** tab
2. Add/edit variables
3. Click **"Save Changes"**
4. Service automatically redeploys

---

## Troubleshooting

### Build Fails with Rust/Cargo Errors
**Problem:** Old package versions don't have Python 3.13 wheels

**Solution:** Upgrade packages in `requirements.txt`:
```
pydantic>=2.10.0
cryptography>=44.0.0
pydantic-settings>=2.7.0
```

### App Doesn't Start
- Verify start command: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- Check **all required** environment variables are set:
  - `GROQ_API_KEY` (critical)
  - `GROQ_MODEL`
  - `ENCRYPTION_KEY` (for password-protected PDFs)
- Review logs for errors

### PDF Parsing Fails
- Check `GROQ_API_KEY` is valid (test at https://console.groq.com)
- Verify `ENCRYPTION_KEY` is set (for password-protected PDFs)
- Check Groq API quota (free tier: 30 requests/minute)
- Review logs for specific error messages

### 401 Unauthorized Errors
- Ensure Bearer token is correct: `cc_user1_token_2026`
- Token is case-sensitive
- Check Postman Authorization tab is set to "Bearer Token"

### Slow First Request (30-60s)
- **Expected behavior** on free tier (cold start)
- Service spins down after 15 minutes of inactivity
- Upgrade to Starter Plan ($7/month) for always-on service

---

## Local Development Setup

For developers cloning the repository:

### 1. Clone and Setup
```powershell
git clone https://github.com/AIGuild2025/CCRewardsDashboard.git
cd CCRewardsDashboard
git checkout poc_pdfparser
```

### 2. Create Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create `.env` File
Create `.env` in project root:
```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0.1
TEXTRACT_ENABLED=false
PII_MASKING_ENABLED=true
```

**Get Groq API Key:** https://console.groq.com/keys

### 4. Encryption Key (Optional)
**Option A:** Auto-generate on first run
- App creates `.encryption_key` automatically
- Encrypt your PDF passwords using the password manager

**Option B:** Skip encryption
- Provide passwords directly in API requests
- No encryption setup needed

### 5. Run Locally
```powershell
uvicorn api:app --host 0.0.0.0 --port 8000
```

### 6. Test Locally
- Import `CCRewardsDashboard_API.postman_collection.json` into Postman
- Use `http://localhost:8000` as base URL
- Test with your PDF files

---

## Upgrade Options

### Starter Plan ($7/month)
**Benefits:**
- ✅ No cold starts (always-on)
- ✅ 512 MB RAM (vs 512 MB shared on free)
- ✅ Better performance
- ✅ Suitable for production use

**Recommended when:**
- Using in production
- Need consistent response times
- More than a few requests per hour

### Free Tier
**Perfect for:**
- Testing and development
- Low-traffic APIs
- Personal projects
- 750 hours/month = ~1 request every 2 minutes average
