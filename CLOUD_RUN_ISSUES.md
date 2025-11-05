# Cloud Run Deployment Issues and Solutions

## Current Issues

### 1. SQLite Database Write Errors
**Problem**: BufferedWriteHandler.OutOfOrderError when writing to sessions.db-journal
- GCSFuse doesn't handle SQLite's journal mode well
- Concurrent writes cause offset mismatches

**Solution Options**:
1. **Use WAL mode for SQLite** (Recommended)
   - Add SQLite WAL (Write-Ahead Logging) mode configuration
   - More compatible with distributed filesystems
   
2. **Switch to Cloud SQL or Firestore**
   - More reliable for production workloads
   - Better concurrency handling

3. **Use in-memory SQLite with periodic backups**
   - Store session data in memory
   - Periodically sync to GCS

### 2. Request Timeout Issues
**Problem**: Cloud Run has a 5-minute timeout, but complex agent operations may take longer

**Solution**: Increase timeout to maximum (60 minutes)
```bash
gcloud run services update cagent-api \
  --region us-central1 \
  --timeout 3600
```

### 3. Context Cancellation
**Problem**: Sessions are being cancelled prematurely

**Possible Causes**:
- Client disconnection
- Cloud Run instance scaling down
- Timeout reached

**Solutions**:
1. Implement better error handling and retry logic
2. Use Cloud Run's always-allocated CPU for background processing
3. Implement session persistence and recovery

## Immediate Fix Commands

### 1. Update Service with Extended Timeout
```bash
gcloud run services update cagent-api \
  --region us-central1 \
  --timeout 3600 \
  --max-instances 10 \
  --min-instances 1
```

### 2. Update Environment Variables for SQLite WAL Mode
```bash
# Add to cloudrun-env.yaml:
DATABASE_URL: "sqlite:///work/sessions.db?_journal_mode=WAL&_busy_timeout=5000"

# Then update service:
gcloud run services update cagent-api \
  --region us-central1 \
  --env-vars-file cloudrun-env.yaml
```

### 3. Monitor Logs
```bash
# Watch for errors
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=cagent-api AND severity>=WARNING" --project=chkp-gcp-prd-kenobi-box

# Check specific session
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=cagent-api AND textPayload:SESSION_ID" --limit=50 --project=chkp-gcp-prd-kenobi-box
```

## Long-term Solutions

1. **Migrate to Cloud SQL PostgreSQL**
   - Better concurrency
   - Managed backups
   - Connection pooling

2. **Implement Pub/Sub for async processing**
   - Decouple long-running tasks
   - Better scalability

3. **Use Cloud Tasks for background jobs**
   - Handle timeouts gracefully
   - Retry failed operations

4. **Implement WebSockets or Server-Sent Events**
   - Maintain persistent connections
   - Better real-time communication