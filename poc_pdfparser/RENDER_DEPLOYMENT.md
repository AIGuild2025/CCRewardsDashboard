# Render.com Deployment Guide

## Step 1: Prepare GitHub Repository

### 1.1 Initialize Git (if not already done)
```bash
cd C:\AIEngineer\Class1_Python\CCRewardsDashboard
git init
git add .
git commit -m "Initial commit - CC Statement Parser API"
```

### 1.2 Create GitHub Repository
1. Go to https://github.com/new
2. Repository name: `cc-rewards-dashboard` (or your choice)
3. Keep it **Private** (contains sensitive config structure)
4. Don't initialize with README (we already have one)
5. Click "Create repository"

### 1.3 Push to GitHub
```bash
git remote add origin https://github.com/YOUR_USERNAME/cc-rewards-dashboard.git
git branch -M main
git push -u origin main
```

---

## Step 2: Deploy on Render.com

### 2.1 Create Render Account
1. Go to https://render.com
2. Sign up with GitHub (easier deployment)
3. Authorize Render to access your repositories

### 2.2 Create New Web Service
1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository: `cc-rewards-dashboard`
3. Configure:
   - **Name**: `cc-rewards-api` (or your choice)
   - **Region**: Choose closest to your users
   - **Branch**: `main`
   - **Root Directory**: `poc_pdfparser`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api:app --host 0.0.0.0 --port $PORT`
   - **Plan**: **Free**

### 2.3 Add Environment Variables
Click **"Environment"** and add:

| Key | Value |
|-----|-------|
| `GROQ_API_KEY` | Your Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` |
| `LLM_TEMPERATURE` | `0.1` |
| `TEXTRACT_ENABLED` | `false` |
| `PII_MASKING_ENABLED` | `true` |

**Important:** Don't add `.encryption_key` or PDF passwords - these should be managed separately for security.

### 2.4 Deploy
1. Click **"Create Web Service"**
2. Wait for build (2-5 minutes)
3. Get your URL: `https://cc-rewards-api.onrender.com`

---

## Step 3: Configure Password Management (Optional)

Since Render uses ephemeral storage, you have two options:

### Option A: Remove Password Encryption (Simpler)
Modify API to accept password as optional parameter:
- Users provide password in upload request
- No encrypted storage needed

### Option B: Use Environment Variables
Store passwords as environment variables:
```
PDF_PASSWORD_4315=your_password_here
```

Update `password_manager.py` to read from env vars instead of encrypted file.

---

## Step 4: Test Deployment

### 4.1 Check Health
```bash
curl https://YOUR_APP.onrender.com/health
```

### 4.2 Update Postman Collection
Change base URL to: `https://YOUR_APP.onrender.com`

### 4.3 Test PDF Upload
Use Postman with your new URL:
```
POST https://YOUR_APP.onrender.com/api/v1/parse-pdf
Authorization: Bearer cc_user1_token_2026
Body: form-data with PDF file
```

---

## Important Notes

### Cold Starts
- Free tier sleeps after 15 minutes of inactivity
- First request after sleep takes ~30 seconds to wake up
- Subsequent requests are fast (3-6 seconds)

### File Storage
- Render uses **ephemeral storage** (resets on restart)
- `output/` folder data is lost on sleep/restart
- Consider using cloud storage (AWS S3, Cloudflare R2) for persistence

### SSL Certificate
- Automatically provided by Render
- HTTPS enabled by default
- No configuration needed

### Custom Domain (Optional - Free)
1. Go to **Settings** → **Custom Domain**
2. Add your domain
3. Update DNS records as instructed

---

## Monitoring

### View Logs
1. Go to your service on Render dashboard
2. Click **"Logs"** tab
3. Real-time logs of API requests

### Restart Service
- **Manual**: Dashboard → **"Manual Deploy"** → **"Clear build cache & deploy"**
- **Auto**: Push to GitHub main branch triggers auto-deploy

---

## Troubleshooting

### Build Fails
- Check `requirements.txt` versions
- Review build logs in Render dashboard
- Ensure Python 3.13 is specified in `runtime.txt`

### App Doesn't Start
- Verify start command: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- Check environment variables are set
- Review logs for errors

### PDF Parsing Fails
- Check GROQ_API_KEY is set correctly
- Verify `sample_pdfs` folder exists
- Consider password management strategy

---

## Upgrade Options (If Needed Later)

**Starter Plan ($7/month):**
- No cold starts
- Always-on
- More RAM/CPU
- Better for production

**Current Free Tier:**
- Perfect for testing and low-traffic APIs
- 750 hours/month = ~1 request every 2 minutes average
