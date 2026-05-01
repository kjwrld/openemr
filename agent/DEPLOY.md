# Railway Deployment Guide

## Prerequisites

✅ Railway CLI installed: `railway --version`
✅ Linked to project: `railway link`
✅ All tests passing locally: `pytest tests/ -v`

## Required Environment Variables

Set these in Railway dashboard **before** deploying:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENEMR_FHIR_BASE_URL=https://openemr-production-83fe.up.railway.app/apis/default/fhir
SECRET_KEY=<generate-secure-random-string>

# Optional (OAuth - deferred to Final submission)
# OPENEMR_CLIENT_ID=<from-openemr-admin>
# OPENEMR_CLIENT_SECRET=<from-openemr-admin>
# OPENEMR_TOKEN_URL=https://openemr-production-83fe.up.railway.app/oauth2/default/token
```

## Deployment Steps

### 1. Navigate to agent directory
```bash
cd /Users/kj/dev/gauntlet/openemr/agent
```

### 2. Link to Railway project
```bash
railway link --project stunning-reverence
```

Select the production environment when prompted.

### 3. Deploy the agent
```bash
railway up
```

This will:
- Build the Docker image
- Push to Railway
- Deploy the service
- Run health checks

### 4. Set environment variables (if not already set)
```bash
# Via CLI
railway variables set ANTHROPIC_API_KEY="sk-ant-api03-..."
railway variables set OPENEMR_FHIR_BASE_URL="https://openemr-production-83fe.up.railway.app/apis/default/fhir"
railway variables set SECRET_KEY="$(openssl rand -hex 32)"

# OR via Railway dashboard:
# https://railway.app/project/stunning-reverence → agent service → Variables
```

### 5. Get deployed URL
```bash
railway domain
```

You'll get something like: `https://copilot-agent-production.up.railway.app`

### 6. Test health endpoint
```bash
AGENT_URL=$(railway domain)
curl $AGENT_URL/health
```

Expected:
```json
{
  "status": "healthy",
  "service": "clinical-copilot-agent",
  "version": "0.1.0"
}
```

### 7. Test chat endpoint
```bash
curl -X POST $AGENT_URL/chat \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 1,
    "message": "Give me a pre-visit summary"
  }'
```

Expected: HTTP 200 with response JSON

### 8. Update OpenEMR integration

Edit `/Users/kj/dev/gauntlet/openemr/interface/patient_file/summary/demographics.php`:

```javascript
// Line 2172 - Update this line:
const copilotAgentUrl = 'https://your-agent-url.up.railway.app';
```

Replace `your-agent-url.up.railway.app` with your actual Railway domain.

---

## Verification Checklist

After deployment:

- [ ] Health endpoint returns 200
- [ ] Chat endpoint accepts requests
- [ ] Static files accessible: `$AGENT_URL/static/chat.html`
- [ ] OpenEMR button opens chat widget
- [ ] Patient ID passes correctly from OpenEMR
- [ ] Messages sent to agent get responses
- [ ] Rate limiting works (10 req/min)
- [ ] Logs appear in Railway dashboard

---

## Troubleshooting

### Build fails
```bash
# Check build logs
railway logs --build

# Common issues:
# - Missing requirements.txt
# - Dockerfile syntax error
```

### Deployment fails
```bash
# Check runtime logs
railway logs

# Common issues:
# - Missing environment variables
# - Port binding (should use $PORT)
# - Import errors
```

### Health check fails
```bash
# Check if service is running
railway status

# View logs
railway logs --tail 100
```

### CORS errors in browser
- Check that CORS middleware is configured in `main.py`
- Verify `allow_origins` includes your OpenEMR URL

---

## Rollback

If deployment has issues:

```bash
# View previous deployments
railway status

# Rollback to previous version
railway rollback
```

---

## Cost Monitoring

Railway pricing:
- Free tier: $5 credit/month
- Agent service (always-on): ~$5/month
- Estimated total: $5-10/month for demo

Check usage:
```bash
railway status --usage
```

---

## Next Steps After Deployment

1. ✅ Record demo video showing the deployed agent
2. ✅ Update ARCHITECTURE.md with deployed URLs
3. ✅ Test with multiple patients
4. ✅ Monitor logs for errors
5. ⏭️ Implement OAuth for Final submission (Sunday)
