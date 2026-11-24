# ClaimSense Deployment Guide: Streamlit Community Cloud

This guide provides instructions for deploying ClaimSense as a public, zero-cost web application on Streamlit Community Cloud.

---

## 1. Prerequisites
1. A **Public GitHub Repository** containing the ClaimSense codebase.
2. An account on **[share.streamlit.io](https://share.streamlit.io)** (free tier, connects with GitHub).

---

## 2. Deployment Steps

### Step A: Push Code to Public GitHub Repository
```bash
git remote add origin https://github.com/<your-username>/claimsense.git
git branch -M main
git push -u origin main
```

### Step B: Create New App on Streamlit Cloud
1. Log in to [share.streamlit.io](https://share.streamlit.io).
2. Click **New app**.
3. Select your repository: `<your-username>/claimsense`.
4. Branch: `main`.
5. Main file path: `app/main.py`.
6. Click **Advanced settings...** before deploying.

### Step C: Configure Secrets
In the **Secrets** text area, paste the contents of `.streamlit/secrets.toml.example`:
```toml
BACKEND_MODE = "inprocess"
OFFLINE_MODE = "false"

# Databricks Credentials (leave empty or fill when workspace is ready)
DATABRICKS_HOST = ""
DATABRICKS_TOKEN = ""
DATABRICKS_HTTP_PATH = ""
DATABRICKS_CATALOG = "workspace"
DATABRICKS_SCHEMA = "claimsense"

# Groq API Key (optional - uses deterministic reasoning if empty)
GROQ_API_KEY = "gsk_your_free_key_from_console_groq_com"
GROQ_FAST_MODEL = "llama-3.1-8b-instant"
GROQ_REASONING_MODEL = "llama-3.3-70b-versatile"

FASTAPI_API_KEY = "claimsense_secret_key"
```
7. Click **Deploy!**.

---

## 3. Incognito & Mobile Verification Checklist

* [ ] **Public Access**: Open the public URL in a private/incognito browser window. Confirm the app loads **without requiring any login prompt**.
* [ ] **Cold-Start Handling**: Observe that loading spinners display while data is loaded.
* [ ] **Pipeline Page**: Click "Run Pipeline Now" and verify reconciliation displays `PASS`.
* [ ] **AI Triage Page**: Select a claim, click "Run LangGraph Agent Triage", and verify decisions, confidence score, and policy clause citations display cleanly.
* [ ] **Mobile Responsiveness**: Open the URL on a mobile device (iOS/Android). Verify KPI cards wrap gracefully, tables scroll horizontally, and buttons remain accessible.
