# Streamlit Cloud Deployment Guide

## ☁️ Deploy to Streamlit Community Cloud (100% Free)

**Best for**: Quick UI demo without backend services

---

## Quick Deploy (3 Steps)

### 1. Push to GitHub

```bash
# Create public repository on GitHub
# Push your code
git init
git add .
git commit -m "Streamlit PQC Demo"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/pqc-iso15118.git
git push -u origin main
```

### 2. Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io
2. Sign in with GitHub
3. Click "New app"
4. Select repository: `YOUR_USERNAME/pqc-iso15118`
5. Branch: `main`
6. Main file: `streamlit_app.py`
7. Click "Deploy"

### 3. Access Your App

Your app will be live at:
```
https://YOUR_USERNAME-pqc-iso15118.streamlit.app
```

---

## ⚠️ Limitations

**Streamlit Cloud only runs the Streamlit interface.**

Backend services (Cloud, Station, Vehicle) won't work because:
- Can't run multiple processes
- Can't open ports 9000 and 15118
- No subprocess management

**What works:**
- ✅ Streamlit UI displays
- ✅ Configuration forms
- ✅ Buttons and controls

**What doesn't work:**
- ❌ Starting backend services
- ❌ Running charging sessions
- ❌ Real-time logs from services

---

## 💡 Solution: Mock Mode

Create a demo mode for Streamlit Cloud that simulates the system:

### Add Mock Mode to streamlit_app.py

Add this at the top of the file:

```python
# Detect if running on Streamlit Cloud
STREAMLIT_CLOUD = os.getenv('STREAMLIT_CLOUD', 'false').lower() == 'true'
DEMO_MODE = STREAMLIT_CLOUD

if DEMO_MODE:
    st.info("🎭 Running in DEMO MODE - Simulated output for demonstration")
```

Then wrap subprocess calls:

```python
if not DEMO_MODE:
    # Real subprocess execution
    process = subprocess.Popen(...)
else:
    # Simulated output
    st.success("✅ [DEMO] Service started successfully")
    # Show pre-recorded logs
```

---

## Alternative: Use Streamlit Cloud for UI Only

Deploy just the UI and point it to a backend hosted elsewhere:

**Setup:**
1. Host backend services on Railway/Render/VPS
2. Update Streamlit app to connect to remote backend
3. Deploy UI to Streamlit Cloud

**Configuration:**
```python
# In streamlit_app.py
BACKEND_URL = os.getenv('BACKEND_URL', 'https://your-backend.railway.app')
```

---

## Comparison

| Feature | Streamlit Cloud | Railway | Render |
|---------|----------------|---------|--------|
| **Cost** | Free | $5/month credit | Free tier |
| **Streamlit UI** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Backend Services** | ❌ No | ✅ Yes | ✅ Yes |
| **Custom Domain** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Always On** | ✅ Yes | ⚠️ Limited | ❌ Sleeps |
| **RAM** | 1 GB | 512 MB/service | 512 MB |
| **Setup** | Easiest | Easy | Medium |

---

## Recommendation

**For your project (full stack):**
👉 **Use Railway** - It supports all services

**For UI demo only:**
👉 **Use Streamlit Cloud** - Quick and easy

**For production:**
👉 **Use VPS** (DigitalOcean, Linode, AWS EC2) - Full control

---

## Resources

- Streamlit Cloud Docs: https://docs.streamlit.io/streamlit-community-cloud
- Deployment Guide: https://docs.streamlit.io/streamlit-community-cloud/get-started

---

**Your Streamlit Cloud URL will be:**
`https://YOUR_USERNAME-pqc-iso15118.streamlit.app`
