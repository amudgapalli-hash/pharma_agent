# Pharma Agent - Operational Runbooks

## Table of Contents
1. [Daily Operations](#daily-operations)
2. [Incident Response](#incident-response)
3. [Scaling Operations](#scaling-operations)
4. [Troubleshooting Guide](#troubleshooting-guide)
5. [Database Maintenance](#database-maintenance)
6. [Container Management](#container-management)
7. [Security Operations](#security-operations)
8. [Compliance & Audit](#compliance--audit)
9. [Disaster Recovery](#disaster-recovery)
10. [On-Call Procedures](#on-call-procedures)

---

## Daily Operations

### Morning Health Check (8:00 AM)

**Checklist:**

```bash
# 1. SSH to production host
ssh ubuntu@prod-server.example.com
cd /opt/pharma_agent

# 2. Check container status
docker compose ps
# Expected: All containers showing "Up" or "healthy"

# 3. Test API health
curl http://localhost:8000/health | jq .
# Expected: { "status": "healthy", ... }

# 4. Check log files
tail -50 logs/pharma_agent.log
# Look for: No ERROR or CRITICAL lines

# 5. Check disk space
df -h
# Expected: <80% usage on all partitions

# 6. Check PostgreSQL
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod -c \
  "SELECT COUNT(*) FROM compliance_audits;"
# Expected: Positive integer count

# 7. Check Qdrant
curl http://localhost:6333/health | jq .

# 8. Send confirmation to team
# If all checks pass: "✓ All systems operational"
# If issues found: Create incident ticket
```

### Routine Maintenance (Weekly)

**Monday Mornings:**

```bash
# 1. Database backup verification
ls -la backups/
# Expected: backup file from Sunday 2:00 AM

# 2. Verify backup integrity
docker exec pharma_agent-postgres_db-1 \
  pg_dump -U pharma_prod compliance_prod > /tmp/verify.sql
# If succeeds: Backup working

# 3. Log rotation
docker exec pharma_agent-fastapi_backend-1 \
  logrotate -f /etc/logrotate.d/pharma_agent

# 4. Security updates
sudo apt update
sudo apt list --upgradable
# If updates available: Plan maintenance window

# 5. Certificate expiry check
openssl x509 -in /etc/letsencrypt/live/pharma.example.com/cert.pem \
  -noout -dates
# Expected: notAfter > 30 days away
```

### End-of-Day Check (5:00 PM)

```bash
# 1. Check for errors in logs
docker compose logs --since=8h | grep ERROR
# Expected: No ERROR lines (or expected errors documented)

# 2. Review audit logs
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod -c \
  "SELECT COUNT(*) FROM audit_logs WHERE created_at > NOW() - INTERVAL '1 day';"
# Expected: Positive number (users were active)

# 3. Check resource usage
docker stats --no-stream
# Expected: CPU <50%, Memory <80%

# 4. Verify database size hasn't grown unexpectedly
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod -c \
  "SELECT pg_size_pretty(pg_database_size(current_database()));"

# 5. Send summary to team
# "Daily summary: [X audits processed, Y users active, Z errors]"
```

---

## Incident Response

### Critical Alert: Service Down

**Timeline: 0-5 minutes**

```bash
# STEP 1: VERIFY THE ISSUE
docker compose ps
# If containers not running:
docker compose up -d

# If containers running but not responding:
docker compose logs -f fastapi_backend

# STEP 2: IMMEDIATE MITIGATION
# Option A: Restart affected service
docker compose restart fastapi_backend

# Option B: Full restart (if Option A fails after 2 minutes)
docker compose restart

# Option C: Emergency rollback (if restart fails)
# See "Rollback" section below

# STEP 3: NOTIFY STAKEHOLDERS
# Email: ops-alert@example.com
# Subject: [CRITICAL] Pharma Agent API - Service Restored
# Message: Service was down for [X minutes]. Root cause: [X]. Actions taken: [X].
```

**Timeline: 5-15 minutes**

```bash
# STEP 4: INVESTIGATE ROOT CAUSE
# Check for common causes:

# 1. Out of disk space
df -h /opt/pharma_agent

# 2. Out of memory
free -h
docker stats

# 3. Database connection issues
docker compose logs postgres_db | tail -20

# 4. Network connectivity
docker network inspect pharma_agent_sci_network

# 5. Check for OOM kills
dmesg | grep -i oom | tail -10
```

### Critical Alert: High Error Rate

**Threshold: >10 errors/minute or >1% error rate**

```bash
# STEP 1: COLLECT METRICS
# Count errors in last 5 minutes
docker compose logs --since=5m | grep ERROR | wc -l

# STEP 2: IDENTIFY ERROR PATTERN
# Get representative errors
docker compose logs --since=10m | grep ERROR | head -10

# STEP 3: CORRELATE WITH CHANGES
# What changed in last 30 minutes?
git log --since="30 minutes ago" --oneline

# STEP 4: REMEDIATION
# If recent code deployed:
docker compose pull
docker compose up -d

# If database issue:
docker exec pharma_agent-postgres_db-1 \
  pg_stat_statements | head -20

# If memory leak suspected:
docker stats --no-stream
# Check if memory keeps growing on one container
```

### Critical Alert: Database Unavailable

**Symptoms: Connection refused, timeout, pool exhausted**

```bash
# STEP 1: CHECK DATABASE SERVICE
docker compose ps postgres_db

# If NOT running:
docker compose start postgres_db
# Wait 30 seconds for startup

# If running but not responding:
docker exec pharma_agent-postgres_db-1 \
  pg_isready -U pharma_prod -d compliance_prod

# STEP 2: CHECK DISK SPACE (PostgreSQL bloat)
df -h /var/lib/postgresql/data

# If <10% free:
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod -c "VACUUM ANALYZE;"

# STEP 3: CHECK CONNECTIONS
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod -c \
  "SELECT COUNT(*) FROM pg_stat_activity;"
# If >100: Likely connection pool issue

# SOLUTION: Restart connection pooler
docker compose restart pgbouncer  # if using PgBouncer

# STEP 4: EMERGENCY RESTORE FROM BACKUP
# See "Disaster Recovery" section
```

### Incident Communication Template

```
INCIDENT REPORT: [Incident Type]
Severity: [Critical/High/Medium/Low]
Duration: [Start time] - [End time] ([X minutes])
Impact: [X users affected, Y audits delayed]

TIMELINE:
- [Time]: Incident started (alert triggered)
- [Time]: Mitigation initiated
- [Time]: Service restored
- [Time]: Root cause identified

ROOT CAUSE:
[Description of what went wrong]

REMEDIATION:
[Actions taken to fix]

PREVENTION:
[Changes to prevent recurrence]
- [Action Item 1] - Owner: [Name] - Due: [Date]
- [Action Item 2] - Owner: [Name] - Due: [Date]
```

---

## Scaling Operations

### Horizontal Scaling (Add More Instances)

**Add FastAPI Backend Instance:**

```bash
# In docker-compose.yml, add:
services:
  fastapi_backend_2:
    build:
      context: .
      dockerfile: Dockerfile.fastapi
    ports:
      - "8001:8000"  # Different port
    depends_on:
      - postgres_db
      - qdrant_vector
    environment:
      # Same as fastapi_backend_1
    networks:
      - sci_network

# Start new instance
docker compose up -d fastapi_backend_2

# Configure Nginx load balancer
# Add to /etc/nginx/sites-available/pharma_agent:
upstream fastapi_backend {
    server localhost:8000;  # Instance 1
    server localhost:8001;  # Instance 2
    # Add more as needed
}
```

### Vertical Scaling (More Resources)

**Increase Docker memory limits:**

```yaml
# docker-compose.yml
services:
  fastapi_backend:
    deploy:
      resources:
        limits:
          cpus: '4'         # Changed from 2
          memory: 4G        # Changed from 2G
        reservations:
          cpus: '2'         # Changed from 1
          memory: 2G        # Changed from 1G
```

**Apply changes:**

```bash
docker compose down
docker compose up -d
```

### Scaling Decision Tree

```
Load increasing?
├─ CPU usage >80%?
│  └─ YES: Scale horizontally (add instances)
├─ Memory usage >80%?
│  ├─ YES: Check for memory leaks
│  │  ├─ Leaks found: Deploy fix + restart
│  │  └─ No leaks: Scale vertically (increase memory)
├─ I/O latency high?
│  └─ YES: Upgrade storage (SSD), increase IOPS
└─ User complaints of slowness?
   ├─ Peak hours: Scale horizontally
   └─ Off-peak too: Check for inefficient queries
```

---

## Troubleshooting Guide

### Issue: "Connection refused" when accessing API

**Diagnosis:**

```bash
# Is the container running?
docker compose ps fastapi_backend
# Expected: Up

# Is port 8000 listening?
netstat -tulpn | grep 8000
# Expected: LISTEN 0.0.0.0:8000

# Is Nginx proxying correctly?
curl -v http://localhost/api/health
# Check for X-Original-URI header
```

**Resolution:**

```bash
# 1. Check logs
docker compose logs fastapi_backend | tail -30

# 2. Restart container
docker compose restart fastapi_backend

# 3. If still failing, check dependencies
docker compose logs postgres_db | grep ERROR
docker compose logs qdrant_vector | grep ERROR

# 4. Verify network
docker network inspect pharma_agent_sci_network
```

### Issue: "Token expired" or "Invalid token"

**Diagnosis:**

```bash
# Decode JWT to check expiration
python3 << 'EOF'
import jwt
token = "YOUR_TOKEN_HERE"
try:
    decoded = jwt.decode(token, options={"verify_signature": False})
    print(decoded)
except jwt.ExpiredSignatureError:
    print("Token expired")
except Exception as e:
    print(f"Error: {e}")
EOF
```

**Resolution:**

```bash
# 1. Re-authenticate
curl -X POST http://localhost:8000/token \
  -d "username=dr_smith&password=password123"

# 2. Update client to use new token
# (See API Client SDKs documentation)

# 3. For production, consider using refresh tokens
```

### Issue: Database queries are slow

**Diagnosis:**

```bash
# Enable query logging
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod << 'EOF'
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries >1s
SELECT pg_reload_conf();
EOF

# Check slow query log
docker exec pharma_agent-postgres_db-1 \
  tail -100 /var/log/postgresql/postgresql.log | grep "duration:"
```

**Resolution:**

```bash
# 1. Analyze query plan
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod << 'EOF'
EXPLAIN ANALYZE
SELECT * FROM compliance_audits WHERE team = 'BioGenomics' ORDER BY date DESC;
EOF

# 2. Add missing indexes
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod << 'EOF'
CREATE INDEX CONCURRENTLY idx_team_date 
  ON compliance_audits(team, date DESC);
EOF

# 3. Vacuum and analyze
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod << 'EOF'
VACUUM ANALYZE compliance_audits;
EOF
```

### Issue: Disk space filling up

**Diagnosis:**

```bash
# Check space usage
df -h /opt/pharma_agent

# Find large files
du -sh /opt/pharma_agent/data/*

# Check Docker images
docker system df

# Check log file sizes
ls -lah /opt/pharma_agent/logs/
```

**Resolution:**

```bash
# 1. Clean old logs
find /opt/pharma_agent/logs -name "*.log" -mtime +30 -delete

# 2. Vacuum PostgreSQL
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod -c "VACUUM FULL;"

# 3. Clean Docker
docker system prune -a
# WARNING: Removes all unused images/containers/volumes

# 4. Archive to external storage
tar -czf pharma_agent_backup_$(date +%Y%m%d).tar.gz \
  /opt/pharma_agent/data/
aws s3 cp pharma_agent_backup_*.tar.gz s3://backup-bucket/
```

### Issue: Container keeps restarting

**Diagnosis:**

```bash
# Check restart count
docker inspect pharma_agent-fastapi_backend-1 | grep RestartCount

# Check logs for crash reason
docker compose logs fastapi_backend | tail -50

# Check systemd (if using systemd)
journalctl -u docker -n 50
```

**Common causes and solutions:**

```bash
# 1. OOM (Out of Memory)
# Error: "Killed" or "exit code 137"
# Solution: Increase memory limit in docker-compose.yml

# 2. Import error
# Error: "ModuleNotFoundError: No module named 'X'"
# Solution: Rebuild image
docker compose build --no-cache fastapi_backend

# 3. Configuration error
# Error: "KeyError: 'X'"
# Solution: Check .env file
cat .env | grep -i x_variable

# 4. Port already in use
# Error: "Address already in use"
# Solution: Check what's using port
lsof -i :8000
kill -9 <PID>
```

---

## Database Maintenance

### Daily Vacuum (Auto)

```bash
# Already configured in docker-compose.yml:
# -c "autovacuum=on" -c "autovacuum_naptime=30s"

# Verify it's running
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod -c \
  "SELECT schemaname, tablename, last_vacuum, last_analyze FROM pg_stat_user_tables;"
```

### Weekly ANALYZE

```bash
# Run manually on low-traffic time (e.g., Sunday 2 AM)
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod << 'EOF'
ANALYZE compliance_audits;
ANALYZE audit_logs;
ANALYZE users;
EOF

# Verify statistics updated
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod -c \
  "SELECT tablename, n_live_tup, n_dead_tup FROM pg_stat_user_tables;"
```

### Monthly REINDEX

```bash
# Run during maintenance window
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod << 'EOF'
REINDEX INDEX CONCURRENTLY idx_compliance_team;
REINDEX INDEX CONCURRENTLY idx_compliance_date;
REINDEX INDEX CONCURRENTLY idx_audit_logs_user;
EOF

# Verify indexes
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod -c \
  "SELECT schemaname, tablename, indexname, idx_scan FROM pg_stat_user_indexes;"
```

### Export Data (Compliance)

```bash
# Export audit logs for compliance audit
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod \
  -c "COPY audit_logs TO STDOUT WITH CSV HEADER" \
  > audit_logs_$(date +%Y%m%d).csv

# Export compliance audits
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod \
  -c "COPY compliance_audits TO STDOUT WITH CSV HEADER" \
  > compliance_audits_$(date +%Y%m%d).csv

# Verify integrity
wc -l *.csv
```

---

## Container Management

### Upgrade Container Image

**When a new version is released:**

```bash
# 1. Test in staging
docker pull pharma-agent:v1.1.0
docker tag pharma-agent:v1.1.0 pharma-agent:staging

# Run tests...

# 2. Update docker-compose.yml
# Change: image: pharma-agent:latest
# To: image: pharma-agent:v1.1.0

# 3. Perform rolling update
docker compose pull
docker compose up -d --no-deps --scale fastapi_backend=2 fastapi_backend

# Wait for new instance to be healthy
docker compose ps

# Remove old instance
docker compose up -d --no-deps --scale fastapi_backend=1 fastapi_backend

# 4. Verify
curl http://localhost:8000/docs
```

### View Container Logs

```bash
# Real-time logs
docker compose logs -f fastapi_backend

# Last N lines
docker compose logs --tail=100 fastapi_backend

# Since timestamp
docker compose logs --since=2024-01-15T10:00:00 fastapi_backend

# Specific service and time range
docker compose logs --since 1h fastapi_backend postgres_db

# Export to file
docker compose logs > combined_logs.txt

# Search for errors
docker compose logs | grep ERROR
```

### Execute Commands in Container

```bash
# Interactive shell
docker exec -it pharma_agent-fastapi_backend-1 /bin/bash

# Run Python script
docker exec pharma_agent-fastapi_backend-1 python -c "print('Hello')"

# Run database query
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod -c "SELECT NOW();"

# Check environment
docker exec pharma_agent-fastapi_backend-1 env | grep JWT
```

---

## Security Operations

### Rotate JWT Secret

**Critical: Do not lose access!**

```bash
# 1. Generate new secret
NEW_SECRET=$(openssl rand -hex 32)
echo "New JWT_SECRET: $NEW_SECRET"

# 2. Update .env file
sed -i "s/JWT_SECRET=.*/JWT_SECRET=$NEW_SECRET/" .env

# 3. Restart FastAPI
docker compose restart fastapi_backend

# 4. Invalidate existing tokens
# (Requires implementation of token blacklist)
# All users must re-authenticate

# 5. Notify all users
# Email: "Session expired - please log in again"

# 6. Verify new secret works
curl -X POST http://localhost:8000/token \
  -d "username=dr_smith&password=password123"
```

### Rotate Database Password

```bash
# 1. Generate new password
NEW_PASSWORD=$(openssl rand -hex 16)
echo "New POSTGRES_PASSWORD: $NEW_PASSWORD"

# 2. Update in database
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod << EOF
ALTER USER pharma_prod WITH PASSWORD '$NEW_PASSWORD';
EOF

# 3. Update .env and docker-compose.yml
sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$NEW_PASSWORD/" .env

# 4. Restart services
docker compose restart fastapi_backend

# 5. Verify connectivity
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod -c "SELECT 1;"
```

### Check for Unauthorized Access

```bash
# 1. Review authentication logs
docker compose logs fastapi_backend | grep "401\|403\|unauthorized" | tail -20

# 2. Check audit logs
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod << 'EOF'
SELECT * FROM audit_logs 
WHERE action IN ('unauthorized_access', 'failed_login')
ORDER BY created_at DESC LIMIT 20;
EOF

# 3. List active sessions
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod \
  -c "SELECT * FROM pg_stat_activity WHERE usename = 'pharma_prod';"

# 4. If suspicious activity found:
# - Change passwords immediately
# - Review logs for data access patterns
# - Consider rolling back from backup
```

### SSL Certificate Management

```bash
# Check certificate expiration
openssl x509 -in /etc/letsencrypt/live/pharma.example.com/cert.pem \
  -noout -dates

# Check days until expiry
echo | openssl s_client -connect pharma.example.com:443 2>/dev/null | \
  openssl x509 -noout -dates

# Renew certificate
sudo certbot renew

# Force renewal (testing)
sudo certbot renew --force-renewal --dry-run

# Auto-renewal check (should happen daily)
sudo systemctl list-timers | grep certbot
```

---

## Compliance & Audit

### Generate Audit Report

```bash
# Daily audit summary
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod << 'EOF'
SELECT 
  DATE(created_at) as date,
  COUNT(*) as total_actions,
  COUNT(DISTINCT user_id) as unique_users
FROM audit_logs
WHERE created_at >= NOW() - INTERVAL '1 day'
GROUP BY DATE(created_at)
ORDER BY date DESC;
EOF

# Export for compliance
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod \
  -c "COPY audit_logs TO STDOUT WITH CSV HEADER" \
  > audit_logs_$(date +%Y%m).csv

# Email to compliance team
mail -s "Monthly Audit Report" compliance@example.com < audit_logs_*.csv
```

### Data Retention Cleanup

```bash
# Archive old audit logs (retention policy: 12 months)
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod << 'EOF'
-- Create archive table
CREATE TABLE audit_logs_archive AS 
SELECT * FROM audit_logs 
WHERE created_at < NOW() - INTERVAL '12 months';

-- Delete from main table
DELETE FROM audit_logs 
WHERE created_at < NOW() - INTERVAL '12 months';

-- Verify
SELECT COUNT(*) FROM audit_logs_archive;
SELECT COUNT(*) FROM audit_logs;
EOF

# Export archive to cold storage
docker exec pharma_agent-postgres_db-1 \
  pg_dump -U pharma_prod -d compliance_prod -t audit_logs_archive | \
  gzip > audit_logs_archive_$(date +%Y%m).sql.gz

aws s3 cp audit_logs_archive_*.sql.gz s3://cold-storage/audit/
```

---

## Disaster Recovery

### RTO/RPO Targets

```
Recovery Time Objective (RTO): 1 hour
Recovery Point Objective (RPO): 15 minutes
```

### Full System Recovery

**Scenario: Complete data loss, need to restore everything**

```bash
# STEP 1: Prepare new infrastructure
# (Assumed to be similar to original)

# STEP 2: Find latest backup
BACKUP_FILE="/opt/pharma_agent/backups/postgres_$(date -d '1 day ago' +%Y%m%d)_020000.sql.gz"
ls -la $BACKUP_FILE

# STEP 3: Stop services
docker compose down

# STEP 4: Restore database
zcat $BACKUP_FILE | \
  docker exec -i pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod

# STEP 5: Restore Qdrant (if available)
# (Qdrant data is persisted in volume, already restored)

# STEP 6: Verify integrity
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod \
  -c "SELECT COUNT(*) FROM compliance_audits;"

# STEP 7: Start services
docker compose up -d

# STEP 8: Verify access
curl http://localhost:8000/health
```

### Point-in-Time Recovery

**Scenario: Need to restore to specific time (e.g., before accidental deletion)**

```bash
# STEP 1: Stop writes to database
docker compose stop fastapi_backend streamlit_dashboard

# STEP 2: Configure PITR settings (must be done beforehand)
# In docker-compose.yml:
# command:
#   - "-c"
#   - "wal_level=replica"
#   - "-c"
#   - "max_wal_senders=3"

# STEP 3: Restore to point in time
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod << 'EOF'
-- This requires WAL recovery, typically done at initdb time
-- If already configured, restart with recovery target:
EOF

# STEP 4: Re-enable writes
docker compose up -d

# STEP 5: Verify state at recovery time
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod \
  -c "SELECT * FROM compliance_audits ORDER BY created_at DESC LIMIT 5;"
```

### Failover to Standby (High Availability)

**Scenario: Primary database fails, failover to replica**

```bash
# STEP 1: Detect primary is down
docker exec pharma_agent-postgres_db-1 pg_isready
# Expected: rejecting connections

# STEP 2: Promote replica to primary
docker exec pharma_agent-postgres_db-replica-1 \
  pg_ctl promote -D /var/lib/postgresql/data

# STEP 3: Update connection string
sed -i "s/postgres_db:5432/postgres_db-replica-1:5432/" .env

# STEP 4: Restart FastAPI to use new primary
docker compose restart fastapi_backend

# STEP 5: Verify connectivity
docker exec pharma_agent-fastapi_backend-1 \
  python -c "import psycopg2; psycopg2.connect('...')"

# STEP 6: Set up new replica from new primary
# (Contact your DBA or follow provider-specific procedure)
```

---

## On-Call Procedures

### On-Call Checklist

**When you take on-call duty:**

```bash
# 1. Familiarize yourself with current state
./daily_health_check.sh

# 2. Review recent changes
git log --since="24 hours ago" --oneline

# 3. Check monitoring dashboards
open https://monitoring.example.com/pharma_agent

# 4. Ensure you have:
□ SSH key for production server
□ VPN access if needed
□ Phone number for escalation
□ List of team members to contact
□ Access to runbooks and documentation

# 5. Set up alert channels
open https://slack.com  # or your monitoring tool
```

### Escalation Path

```
⚠️ Alert Triggered
     ↓
[Your Name] (On-Call)
 ├─ Can resolve? → Fix it
 ├─ Unsure? → Call [Senior Engineer]
 └─ Can't reach? → Call [Manager]
     ↓
Senior Engineer ([Name])
 ├─ Can resolve? → Fix it
 └─ Can't? → Call [Principal/Lead]
     ↓
Principal/Lead
 └─ Handles critical/complex issues
```

### Critical Issue Handover

**When handing off duty:**

```bash
# Create handover document
cat > handover_$(date +%Y%m%d_%H%M%S).md << 'EOF'
# On-Call Handover

**Date**: $(date)
**Outgoing**: [Your Name]
**Incoming**: [Next On-Call Name]

## Incidents This Shift
- [Incident 1]: Brief description, resolution
- [Incident 2]: Brief description, status (ongoing/resolved)

## Open Items
- [ ] Item 1 - [Owner] - Due: [Date]
- [ ] Item 2 - [Owner] - Due: [Date]

## Current Status
- API Status: ✓ Healthy / ⚠️ Degraded / ✗ Down
- Database Status: ✓ Healthy / ⚠️ Degraded / ✗ Down
- Recent Alerts: [List any]

## Known Issues
- [Issue 1]: Description, workaround (if any)

## Useful Commands
\`\`\`
# Health check
./scripts/health_check.sh

# View logs
docker compose logs -f fastapi_backend
\`\`\`

EOF

# Share with incoming on-call
slack_user @next_oncall < handover_*.md
```

### Post-Incident Review (PIR)

**Conduct within 48 hours of critical incident:**

```bash
# 1. Gather timeline
# What happened?
# When did it start?
# When was it detected?
# When was it resolved?
# How long was user impact?

# 2. Root cause analysis
# What was the underlying cause?
# Why wasn't this caught earlier?
# Are there similar risks elsewhere?

# 3. Action items
# What can we do to prevent recurrence?
# What can we do to detect sooner?
# What can we do to resolve faster?

# Document in shared location
# Schedule follow-up for each action item
# Distribute PIR to all team members
```

---

## Runbook Automation

### Create Automated Health Check Script

**File: `scripts/health_check.sh`**

```bash
#!/bin/bash
set -e

HEALTH_REPORT="health_report_$(date +%Y%m%d_%H%M%S).txt"

{
    echo "=== Pharma Agent Health Check ==="
    echo "Timestamp: $(date)"
    echo ""
    
    echo "1. Container Status:"
    docker compose ps
    echo ""
    
    echo "2. API Health:"
    curl -s http://localhost:8000/health | jq . || echo "FAILED"
    echo ""
    
    echo "3. Database:"
    docker exec pharma_agent-postgres_db-1 \
      psql -U pharma_prod -d compliance_prod -c "SELECT COUNT(*) as audit_count FROM compliance_audits;" || echo "FAILED"
    echo ""
    
    echo "4. Disk Usage:"
    df -h /opt/pharma_agent
    echo ""
    
    echo "5. Memory Usage:"
    free -h
    echo ""
    
    echo "6. Recent Errors:"
    docker compose logs --tail=20 | grep -i error || echo "No errors found"
    
} | tee "$HEALTH_REPORT"

echo "Report saved to: $HEALTH_REPORT"
```

**Make executable and schedule:**

```bash
chmod +x scripts/health_check.sh

# Add to crontab (daily at 8 AM)
crontab -e
# Add: 0 8 * * * /opt/pharma_agent/scripts/health_check.sh
```

---

## Conclusion

This runbook provides step-by-step procedures for:
- ✅ Daily operations and monitoring
- ✅ Incident response and escalation
- ✅ Scaling and performance management
- ✅ Troubleshooting common issues
- ✅ Database maintenance
- ✅ Security operations
- ✅ Compliance and audit
- ✅ Disaster recovery
- ✅ On-call procedures

**Keep updated:**
- Review and update annually
- Add new procedures as patterns emerge
- Share learnings from incidents
- Regularly practice disaster recovery

**Questions?** Contact ops@example.com or refer to DEPLOYMENT.md and IMPLEMENTATION.md for more details.
