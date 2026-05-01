# Deployment Guide

## Railway Deployment

### Prerequisites
- Railway account
- Anthropic API key
- OpenEMR instance deployed (FHIR API accessible)

### Step 1: Create Railway Service

1. In your Railway project (same project as OpenEMR):
   ```bash
   railway link
   ```

2. Create new service:
   ```bash
   cd agent
   railway up
   ```

   Or use Railway dashboard:
   - Click "New Service"
   - Select "GitHub Repo"
   - Choose path: `/agent`

### Step 2: Set Environment Variables

In Railway dashboard, add these variables:

**Required:**
```
ANTHROPIC_API_KEY=sk-ant-...
OPENEMR_FHIR_BASE_URL=https://your-openemr.up.railway.app/apis/default/fhir
SECRET_KEY=generate-random-secret-key
```

**Optional:**
```
LOG_LEVEL=INFO
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

Railway automatically sets `PORT`.

### Step 3: Deploy

Railway will auto-deploy on git push. Or manually:
```bash
railway up
```

### Step 4: Verify Deployment

```bash
# Get your service URL
railway domain

# Test health endpoint
curl https://your-agent-service.up.railway.app/health

# Test chat endpoint
curl -X POST https://your-agent-service.up.railway.app/chat \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 1,
    "message": "Give me a pre-visit summary"
  }'
```

## Local Development

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for testing

# Copy env template
cp .env.example .env
# Edit .env with your values
```

### Run Locally

```bash
# Start server
uvicorn main:app --reload --port 8000

# In another terminal, run tests
pytest tests/ -v

# Run evals
python evals/run_evals.py http://localhost:8000
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| ANTHROPIC_API_KEY | Yes | - | Anthropic API key |
| OPENEMR_FHIR_BASE_URL | Yes | `http://localhost:8300/apis/default/fhir` | OpenEMR FHIR API base URL |
| SECRET_KEY | Yes | - | Secret for hashing patient IDs in logs |
| LOG_LEVEL | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| ANTHROPIC_MODEL | No | `claude-sonnet-4-20250514` | Claude model to use |
| PORT | No | `8000` | Server port (Railway sets this automatically) |

## Monitoring

### View Logs

Railway dashboard shows real-time logs. Look for structured JSON logs:

```json
{
  "timestamp": 1714512000.0,
  "trace_id": "abc-123",
  "patient_id_hash": "sha256:e3b0c44...",
  "tool_calls": [...],
  "latency_ms": 4200
}
```

### Key Metrics to Monitor

- **Latency**: Should be < 6 seconds (target from USERS.md)
- **Error rate**: Should be < 1%
- **Cost per request**: ~$0.02 (varies by data volume)
- **Rate limit hits**: 429 responses

## Troubleshooting

### Health check fails
- Check environment variables are set
- Verify OPENEMR_FHIR_BASE_URL is accessible from Railway

### Chat endpoint returns 500
- Check logs for specific error
- Verify Anthropic API key is valid
- Ensure FHIR API is responding

### Rate limit too restrictive
- Adjust in `main.py`: `@limiter.limit("10/minute")`
- Deploy new version

## Cost Estimation

At 10 requests/day per physician:

- Claude Sonnet 4: ~$0.02/request
- Railway Hobby plan: $5/month
- **Total**: ~$11/month for 100 physicians

See README.md for scaling considerations.
