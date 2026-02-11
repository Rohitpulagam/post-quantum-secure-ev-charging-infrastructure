# Railway Deployment Guide

## 🚂 Deploy to Railway (Free Tier)

Railway is the best free option for deploying your complete ISO 15118 + PQC system with all services.

### Prerequisites
- GitHub account
- Railway account (https://railway.app)
- This project pushed to GitHub

---

## Step-by-Step Deployment

### 1. Prepare Your Repository

```bash
# Initialize git (if not already)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - ISO 15118 PQC System"

# Create GitHub repo and push
git remote add origin https://github.com/YOUR_USERNAME/pqc-iso15118.git
git push -u origin main
```

### 2. Deploy to Railway

1. Go to https://railway.app
2. Sign in with GitHub
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose your `pqc-iso15118` repository
6. Railway will detect `docker-compose.yml` automatically

### 3. Configure Services

Railway will create separate services for each container:

**Streamlit Service:**
- Port: 8501
- Generate domain (e.g., yourapp.railway.app)

**Cloud Service:**
- Internal port: 9000
- No public domain needed

**Station Service:**
- Internal port: 15118
- No public domain needed

### 4. Access Your Application

Once deployed, Railway provides:
- **Public URL**: `https://your-app.railway.app`
- **Streamlit Interface**: Accessible from anywhere
- **Backend services**: Internal network communication

---

## Configuration Files

### railway.json (Optional)
Railway auto-detects settings, but you can customize:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "startCommand": "streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Environment Variables

Set in Railway dashboard:
- `PORT`: 8501 (Railway sets automatically)
- `PYTHONUNBUFFERED`: 1

---

## Estimated Costs

**Free Tier Includes:**
- $5 credit per month
- 500 execution hours
- 512 MB RAM per service
- 1 GB disk

**Your Usage:**
- 3 services × 730 hours = 2,190 hours/month
- At free tier: ~170 hours or 7 days/month
- Beyond that: ~$10-15/month

**Tips to Stay Free:**
- Deploy only when demoing
- Stop services when not in use
- Use "sleep" mode for inactive services

---

## Alternative: Single Container Deployment

To maximize free tier, deploy only Streamlit with embedded services:

### Create `railway.dockerfile`
```dockerfile
FROM pqc-iso15118:latest

# Run all services in one container
CMD bash -c "python main.py --mode cloud --host 0.0.0.0 --port 9000 & \
             python main.py --mode station --host 0.0.0.0 --port 15118 --cloud-host localhost --cloud-port 9000 --pqc & \
             streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port $PORT"
```

This runs all services in a single container, using less resources.

---

## Monitoring

Railway provides:
- Real-time logs
- CPU/Memory metrics
- Build logs
- Deployment history

Access via Railway dashboard.

---

## Custom Domain (Optional)

Railway allows custom domains on free tier:
1. Go to service settings
2. Add custom domain
3. Update DNS records
4. SSL certificate auto-generated

---

## Troubleshooting

### Build Fails
```bash
# Check Railway logs
# Common issues:
- Docker build timeout: Increase timeout in settings
- Out of memory: Optimize Dockerfile
```

### Services Can't Communicate
```bash
# Use Railway's internal networking
# Replace 'localhost' with service names:
--cloud-host cloud
--host station
```

### Port Issues
```bash
# Railway assigns $PORT variable
# Streamlit must use: --server.port $PORT
```

---

## Cost Optimization

### Run Only When Needed
```bash
# Stop services via Railway dashboard
# Or use Railway CLI:
railway down
```

### Use Starter Plan ($5/month)
- More resources
- No sleep
- Better for production demos

---

## Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Railway account created
- [ ] Project deployed
- [ ] Services running (check dashboard)
- [ ] Public URL accessible
- [ ] Streamlit interface loads
- [ ] Backend services connected
- [ ] Test vehicle session works

---

## Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- GitHub Issues: Your repo

---

**Your app will be live at: `https://your-app.railway.app`** 🚂⚡
