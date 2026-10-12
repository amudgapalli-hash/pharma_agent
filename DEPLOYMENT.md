# Pharma Agent - Deployment Guide

## Table of Contents
1. [Deployment Overview](#deployment-overview)
2. [Local Development Deployment](#local-development-deployment)
3. [Docker Compose Production Deployment](#docker-compose-production-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Platform Deployments](#cloud-platform-deployments)
6. [Database Migration & Setup](#database-migration--setup)
7. [SSL/TLS Configuration](#ssltls-configuration)
8. [Health Checks & Readiness](#health-checks--readiness)
9. [Backup & Recovery](#backup--recovery)
10. [Performance Tuning](#performance-tuning)
11. [Rollback Procedures](#rollback-procedures)

---

## Deployment Overview

### Deployment Scenarios

| Scenario | Environment | Scale | Use Case |
|----------|-------------|-------|----------|
| **Development** | Laptop/Workstation | Single host | Feature development, testing |
| **Staging** | Docker Compose | 1-2 instances | Pre-production validation |
| **Production** | Docker Compose (Small) | Single host | Small teams (<50 users) |
| **Production** | Kubernetes (Medium) | Multi-node cluster | Medium deployments (50-500 users) |
| **Production** | Kubernetes (Large) | Multi-zone cluster | Enterprise (500+ users) |

### Pre-Deployment Checklist

```bash
# Environment
□ Docker 20.10+
□ Docker Compose 1.29+
□ Git repository access
□ SSH keys for deployment
□ SSL certificates (if using HTTPS)

# Secrets & Configuration
□ Generate strong JWT_SECRET (256-bit)
□ Generate strong database passwords
□ Prepare email/notification credentials
□ Configure OIDC/SAML (if applicable)
□ Enable secret scanning in CI/CD

# Infrastructure
□ DNS records configured
□ Load balancer setup (if needed)
□ Network security groups configured
□ Storage volumes allocated
□ Backup location identified

# Compliance
□ HIPAA/GDPR audit trail enabled
□ Data retention policies documented
□ Encryption at rest enabled
□ Encryption in transit enabled
□ Incident response plan updated
```

---

## Local Development Deployment

### Single-Host Docker Compose (Quickest)

#### Prerequisites
```bash
# Check Docker version
docker --version
# Expected: Docker version 20.10.0 or higher

# Check Docker Compose
docker compose version
# Expected: Docker Compose version v2.0.0 or higher
```

#### Step 1: Clone and Setup

```bash
# Clone repository
git clone https://github.com/youorg/pharma_agent.git
cd pharma_agent

# Create environment file
cp .env.example .env

# Edit environment variables (optional for dev)
nano .env  # or use your editor
```

#### Step 2: Build & Start Services

```bash
# Pull latest images and start all services
docker compose up --pull always -d

# Verify all containers started
docker compose ps
# Expected output:
# STATUS: all containers showing "Up"
```

**Expected Output:**
```
NAME                              COMMAND                  SERVICE
pharma_agent-postgres_db-1        "docker-entrypoint.s…"  postgres_db
pharma_agent-qdrant_vector-1      "/qdrant"                qdrant_vector
pharma_agent-ollama_llm-1         "/bin/ollama serve"      ollama_llm
pharma_agent-fastapi_backend-1    "uvicorn app.main:ap…"  fastapi_backend
pharma_agent-streamlit_dashboard  "streamlit run app/ap…"  streamlit_dashboard
```

#### Step 3: Verify Deployment

```bash
# Check service health
curl http://localhost:8000/docs           # FastAPI Swagger UI
curl http://localhost:8501                # Streamlit dashboard
curl http://localhost:5432                # PostgreSQL (test with psql)
curl http://localhost:6333/health         # Qdrant health
curl http://localhost:11434/api/tags      # Ollama status
```

#### Step 4: Test Authentication

```bash
# Login to get JWT token
curl -X POST http://localhost:8000/token \
  -d "username=dr_smith&password=password123"

# Expected response:
# { "access_token": "eyJ...", "token_type": "bearer" }

# Store token for next request
TOKEN="eyJ..."

# Fetch compliance data
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/compliance/audits

# Expected response:
# { "team": "BioGenomics", "audits": [...] }
```

#### Step 5: Access Dashboard

```
Browser: http://localhost:8501
Username: dr_smith or dr_jones
Password: password123
```

### Troubleshooting Local Deployment

| Issue | Cause | Solution |
|-------|-------|----------|
| Port already in use | Another service on port 8000/8501 | `lsof -i :8000` then kill process |
| Pull rate limit | Docker Hub rate limiting | Add Docker authentication or use mirror |
| Out of disk space | Large images accumulate | `docker system prune -a` |
| Containers won't start | Insufficient memory | Increase Docker memory allocation |
| Database connection fails | PostgreSQL not ready | `docker compose logs postgres_db` |

---

## Docker Compose Production Deployment

### Environment: Single Host with Persistent Storage

#### Prerequisites
```bash
# Production-grade system requirements
- OS: Ubuntu 20.04 LTS or higher
- CPU: 4+ cores
- Memory: 16 GB RAM (8 GB minimum)
- Storage: 100 GB SSD (fast I/O for databases)
- Network: 100 Mbps+ connection
- SSH access to host
```

#### Step 1: Prepare Production Environment

```bash
# SSH into production host
ssh ubuntu@prod-server.example.com

# Create deployment directory
sudo mkdir -p /opt/pharma_agent
sudo chown $USER:$USER /opt/pharma_agent
cd /opt/pharma_agent

# Create data directories
mkdir -p data/postgres
mkdir -p data/qdrant
mkdir -p data/ollama
mkdir -p backups
mkdir -p logs
```

#### Step 2: Deploy with Production Configuration

```bash
# Clone with specific branch/tag
git clone -b v1.0.0 https://github.com/youorg/pharma_agent.git .

# Create production .env file
cat > .env << EOF
# JWT Configuration
JWT_SECRET=$(openssl rand -hex 32)

# Database Configuration
POSTGRES_USER=pharma_prod
POSTGRES_PASSWORD=$(openssl rand -hex 16)
POSTGRES_DB=compliance_prod

# Qdrant Configuration
QDRANT_API_KEY=$(openssl rand -hex 16)

# API Configuration
API_PORT=8000
API_HOST=0.0.0.0

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
EOF

# Secure .env file
chmod 600 .env

# Print credentials to secure location
echo "Backup these credentials to secure storage:"
cat .env
```

#### Step 3: Configure Persistent Volumes

**Update `docker-compose.yml` for production:**

```yaml
version: '3.8'

services:
  fastapi_backend:
    # ... existing config ...
    volumes:
      - ./logs:/app/logs
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/docs"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  postgres_db:
    # ... existing config ...
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pharma_prod"]
      interval: 10s
      timeout: 5s
      retries: 5
    command:
      - "postgres"
      - "-c"
      - "max_connections=200"
      - "-c"
      - "shared_buffers=256MB"

  qdrant_vector:
    # ... existing config ...
    volumes:
      - ./data/qdrant:/qdrant/storage
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  ollama_llm:
    # ... existing config ...
    volumes:
      - ./data/ollama:/root/.ollama
    restart: always

  streamlit_dashboard:
    # ... existing config ...
    restart: always
```

#### Step 4: Launch Production Stack

```bash
# Start with production configuration
docker compose -f docker-compose.yml up -d --remove-orphans

# Wait for services to be ready (5-10 minutes)
docker compose logs -f

# Verify all services are healthy
docker compose ps
# All STATUS should show "healthy" or "Up"

# Check logs for errors
docker compose logs --tail=50 fastapi_backend
docker compose logs --tail=50 postgres_db
```

#### Step 5: Set Up Log Rotation

**Create `/opt/pharma_agent/logging.yml`:**

```yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
  detailed:
    format: "%(asctime)s [%(process)d] [%(levelname)s] %(name)s: %(message)s"

handlers:
  console:
    class: logging.StreamHandler
    formatter: standard
    level: INFO
  file:
    class: logging.handlers.RotatingFileHandler
    filename: /app/logs/pharma_agent.log
    maxBytes: 10485760  # 10MB
    backupCount: 10
    formatter: detailed

root:
  level: INFO
  handlers: [console, file]
```

#### Step 6: Configure Nginx Reverse Proxy

**Install Nginx:**
```bash
sudo apt update
sudo apt install -y nginx
sudo systemctl start nginx
```

**Create `/etc/nginx/sites-available/pharma_agent`:**

```nginx
upstream fastapi_backend {
    server localhost:8000;
}

upstream streamlit_dashboard {
    server localhost:8501;
}

server {
    listen 80;
    server_name pharma.example.com;
    
    client_max_body_size 200M;
    
    # API endpoints
    location /api {
        proxy_pass http://fastapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Streamlit dashboard
    location / {
        proxy_pass http://streamlit_dashboard;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Streamlit WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

**Enable and restart Nginx:**
```bash
sudo ln -s /etc/nginx/sites-available/pharma_agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### Step 7: Enable SSL/TLS with Let's Encrypt

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Generate certificate
sudo certbot certonly --standalone -d pharma.example.com

# Update Nginx config to use HTTPS
sudo certbot --nginx -d pharma.example.com

# Auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### Production Docker Compose Deployment Checklist

```bash
# Infrastructure
□ Host meets minimum specs (4 CPU, 16GB RAM, 100GB SSD)
□ Network connectivity tested
□ SSH access verified
□ Firewall rules configured (80, 443, 5432 as needed)

# Services
□ All containers start without errors
□ Health checks passing
□ Log files created and rotatable
□ Volumes mounted and writable
□ Network connectivity between containers

# Security
□ .env file permissions restricted (600)
□ JWT_SECRET is cryptographically secure
□ Database passwords strong (16+ chars)
□ Nginx SSL/TLS configured
□ Firewall only allows necessary ports

# Monitoring
□ Log aggregation configured
□ Health check endpoints verified
□ Monitoring alerts set up
□ Backup schedule confirmed

# Verification
□ API responds at https://pharma.example.com/api/docs
□ Dashboard accessible at https://pharma.example.com
□ Login test successful
□ Data retrieval test successful
```

---

## Kubernetes Deployment

### Prerequisites

```bash
# Kubernetes cluster (1.20+)
kubectl cluster-info

# Helm 3.0+
helm version

# kubectl configured
kubectl config current-context
```

### Step 1: Create Namespace

```bash
# Create isolated namespace
kubectl create namespace pharma-prod

# Set as default namespace
kubectl config set-context --current --namespace=pharma-prod
```

### Step 2: Create Secrets

```bash
# Generate secure values
JWT_SECRET=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 16)

# Create secrets
kubectl create secret generic pharma-secrets \
  --from-literal=jwt-secret="$JWT_SECRET" \
  --from-literal=db-password="$DB_PASSWORD" \
  -n pharma-prod

# Verify
kubectl get secrets -n pharma-prod
```

### Step 3: Create ConfigMap

**Create `configmap.yaml`:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: pharma-config
  namespace: pharma-prod
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  API_PORT: "8000"
  POSTGRES_DB: "compliance_prod"
  POSTGRES_USER: "pharma_prod"
  QDRANT_URL: "http://qdrant-service:6333"
  OLLAMA_URL: "http://ollama-service:11434"
```

Apply:
```bash
kubectl apply -f configmap.yaml
```

### Step 4: Create PersistentVolumeClaims

**Create `storage.yaml`:**

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: pharma-prod
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: fast-ssd
  resources:
    requests:
      storage: 50Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: qdrant-pvc
  namespace: pharma-prod
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: fast-ssd
  resources:
    requests:
      storage: 100Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ollama-pvc
  namespace: pharma-prod
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: standard
  resources:
    requests:
      storage: 50Gi
```

Apply:
```bash
kubectl apply -f storage.yaml
```

### Step 5: Deploy PostgreSQL

**Create `postgres.yaml`:**

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: pharma-prod
spec:
  serviceName: postgres-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          valueFrom:
            configMapKeyRef:
              name: pharma-config
              key: POSTGRES_DB
        - name: POSTGRES_USER
          valueFrom:
            configMapKeyRef:
              name: pharma-config
              key: POSTGRES_USER
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: pharma-secrets
              key: db-password
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        livenessProbe:
          exec:
            command:
            - /bin/sh
            - -c
            - pg_isready -U $POSTGRES_USER
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - /bin/sh
            - -c
            - pg_isready -U $POSTGRES_USER
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: pharma-prod
spec:
  selector:
    app: postgres
  ports:
  - protocol: TCP
    port: 5432
    targetPort: 5432
  type: ClusterIP
```

Apply:
```bash
kubectl apply -f postgres.yaml
```

### Step 6: Deploy FastAPI Backend

**Create `fastapi.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi-backend
  namespace: pharma-prod
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fastapi-backend
  template:
    metadata:
      labels:
        app: fastapi-backend
    spec:
      containers:
      - name: fastapi
        image: pharma-agent:fastapi-latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
        env:
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: pharma-secrets
              key: jwt-secret
        - name: POSTGRES_URL
          value: "postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@postgres-service:5432/$(POSTGRES_DB)"
        envFrom:
        - configMapRef:
            name: pharma-config
        resources:
          requests:
            cpu: 250m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        livenessProbe:
          httpGet:
            path: /docs
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /docs
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: fastapi-service
  namespace: pharma-prod
spec:
  selector:
    app: fastapi-backend
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-hpa
  namespace: pharma-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

Apply:
```bash
kubectl apply -f fastapi.yaml
```

### Step 7: Deploy Streamlit Dashboard

**Create `streamlit.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: streamlit-dashboard
  namespace: pharma-prod
spec:
  replicas: 2
  selector:
    matchLabels:
      app: streamlit-dashboard
  template:
    metadata:
      labels:
        app: streamlit-dashboard
    spec:
      containers:
      - name: streamlit
        image: pharma-agent:streamlit-latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8501
        env:
        - name: STREAMLIT_SERVER_PORT
          value: "8501"
        - name: STREAMLIT_SERVER_HEADLESS
          value: "true"
        resources:
          requests:
            cpu: 250m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        livenessProbe:
          httpGet:
            path: /
            port: 8501
          initialDelaySeconds: 30
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: streamlit-service
  namespace: pharma-prod
spec:
  selector:
    app: streamlit-dashboard
  ports:
  - protocol: TCP
    port: 8501
    targetPort: 8501
  type: LoadBalancer
```

Apply:
```bash
kubectl apply -f streamlit.yaml
```

### Step 8: Create Ingress

**Create `ingress.yaml`:**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: pharma-ingress
  namespace: pharma-prod
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - pharma.example.com
    secretName: pharma-tls
  rules:
  - host: pharma.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: fastapi-service
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: streamlit-service
            port:
              number: 8501
```

Apply:
```bash
kubectl apply -f ingress.yaml
```

### Step 9: Verify Kubernetes Deployment

```bash
# Check all resources
kubectl get all -n pharma-prod

# Check pods
kubectl get pods -n pharma-prod
# Expected: All pods showing "Running" and ready

# Check services
kubectl get svc -n pharma-prod

# Check ingress
kubectl get ingress -n pharma-prod

# View logs
kubectl logs -f deployment/fastapi-backend -n pharma-prod

# Port forward for testing
kubectl port-forward svc/fastapi-service 8000:8000 -n pharma-prod
# Access: http://localhost:8000/docs
```

---

## Cloud Platform Deployments

### AWS ECS + RDS Deployment

#### Step 1: Create RDS PostgreSQL Instance

```bash
# Via AWS CLI
aws rds create-db-instance \
  --db-instance-identifier pharma-postgres \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 15.1 \
  --allocated-storage 100 \
  --storage-type gp3 \
  --master-username pharma_admin \
  --master-user-password <STRONG_PASSWORD> \
  --db-name compliance_prod \
  --publicly-accessible false \
  --multi-az \
  --backup-retention-period 30 \
  --region us-east-1
```

#### Step 2: Create ECS Cluster

```bash
# Create cluster
aws ecs create-cluster --cluster-name pharma-prod

# Register FastAPI task definition (task-definition.json)
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
  --cluster pharma-prod \
  --service-name fastapi-backend \
  --task-definition fastapi-backend:1 \
  --desired-count 3 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}"
```

#### Step 3: Setup Elasticache for Redis (Optional Caching)

```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id pharma-cache \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1 \
  --auto-minor-version-upgrade true
```

### Google Cloud Run Deployment

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT_ID/pharma-agent:latest

# Deploy FastAPI
gcloud run deploy pharma-api \
  --image gcr.io/PROJECT_ID/pharma-agent:latest \
  --platform managed \
  --region us-central1 \
  --memory 1Gi \
  --cpu 2 \
  --set-env-vars JWT_SECRET=xxx,POSTGRES_URL=xxx \
  --allow-unauthenticated

# Deploy Streamlit
gcloud run deploy pharma-dashboard \
  --image gcr.io/PROJECT_ID/pharma-agent:latest \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --allow-unauthenticated
```

### Azure Container Instances (ACI) Deployment

```bash
# Create resource group
az group create --name pharma-rg --location eastus

# Deploy via docker-compose
az container create \
  --resource-group pharma-rg \
  --name pharma-agent \
  --image pharma-agent:latest \
  --cpu 4 --memory 16 \
  --ports 8000 8501 \
  --environment-variables \
    JWT_SECRET=xxx \
    POSTGRES_URL=xxx \
  --secure-environment-variables \
    DB_PASSWORD=xxx
```

---

## Database Migration & Setup

### Initial Database Schema Creation

```bash
# Connect to PostgreSQL
docker exec -it pharma_agent-postgres_db-1 psql -U sci_user -d compliance_db

# Create tables
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(255) UNIQUE NOT NULL,
  hashed_password VARCHAR(255) NOT NULL,
  team VARCHAR(255) NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS compliance_audits (
  id SERIAL PRIMARY KEY,
  team VARCHAR(255) NOT NULL REFERENCES users(team),
  metric VARCHAR(255) NOT NULL,
  score INT CHECK (score >= 0 AND score <= 100),
  status VARCHAR(50) NOT NULL,
  date DATE NOT NULL,
  details JSONB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id),
  action VARCHAR(255) NOT NULL,
  resource_type VARCHAR(255),
  resource_id INT,
  details JSONB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_compliance_team ON compliance_audits(team);
CREATE INDEX idx_compliance_date ON compliance_audits(date);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);
```

### Data Migration from Legacy System

```bash
# Export from legacy system
psql -h old-db-host -U legacy_user -d legacy_db \
  -c "COPY compliance_audits TO STDOUT" > legacy_audits.sql

# Import to new system
psql -h localhost -U pharma_prod -d compliance_prod < legacy_audits.sql

# Verify migration
psql -h localhost -U pharma_prod -d compliance_prod \
  -c "SELECT COUNT(*) FROM compliance_audits;"
```

---

## SSL/TLS Configuration

### Self-Signed Certificate (Development)

```bash
# Generate private key
openssl genrsa -out server.key 2048

# Generate certificate signing request
openssl req -new -key server.key -out server.csr

# Generate self-signed certificate
openssl x509 -req -days 365 -in server.csr \
  -signkey server.key -out server.crt

# Verify certificate
openssl x509 -in server.crt -text -noout
```

### Let's Encrypt Certificate (Production)

```bash
# Using Certbot
sudo apt install -y certbot

# Generate certificate (standalone)
sudo certbot certonly --standalone \
  -d pharma.example.com \
  -d api.pharma.example.com

# Certificate location
/etc/letsencrypt/live/pharma.example.com/fullchain.pem
/etc/letsencrypt/live/pharma.example.com/privkey.pem

# Auto-renewal
sudo certbot renew --dry-run
```

### Configure FastAPI with SSL

```python
# Run with SSL
import uvicorn

uvicorn.run(
    app,
    host="0.0.0.0",
    port=8443,
    ssl_keyfile="/path/to/privkey.pem",
    ssl_certfile="/path/to/fullchain.pem",
    ssl_version=ssl.PROTOCOL_TLSv1_2,
    ssl_cert_reqs=ssl.CERT_NONE,
    ssl_ciphers="TLSv1_2:!aNULL:!eNULL"
)
```

---

## Health Checks & Readiness

### Implement Health Check Endpoints

```python
# In app/main.py
@app.get("/health", tags=["monitoring"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/readiness", tags=["monitoring"])
async def readiness_check():
    """Check if service is ready to handle traffic."""
    checks = {
        "database": False,
        "vector_store": False,
        "llm": False
    }
    
    # Check PostgreSQL
    try:
        async with db.connection() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = True
    except:
        pass
    
    # Check Qdrant
    try:
        qdrant_client.get_collections()
        checks["vector_store"] = True
    except:
        pass
    
    # Check Ollama
    try:
        ollama_client.list_models()
        checks["llm"] = True
    except:
        pass
    
    ready = all(checks.values())
    return {
        "ready": ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Configure Kubernetes Probes

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /readiness
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2
```

---

## Backup & Recovery

### Automated PostgreSQL Backups

```bash
# Create backup script
cat > /opt/pharma_agent/backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/opt/pharma_agent/backups"
DB_NAME="compliance_prod"
DB_USER="pharma_prod"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/postgres_$TIMESTAMP.sql.gz"

# Perform backup
docker exec pharma_agent-postgres_db-1 \
  pg_dump -U $DB_USER $DB_NAME | \
  gzip > $BACKUP_FILE

# Keep only last 30 days
find $BACKUP_DIR -name "postgres_*.sql.gz" -mtime +30 -delete

# Verify backup
if [ -f "$BACKUP_FILE" ]; then
  echo "Backup successful: $BACKUP_FILE"
  # Optional: upload to S3
  # aws s3 cp $BACKUP_FILE s3://backup-bucket/
else
  echo "Backup failed!"
  exit 1
fi
EOF

chmod +x /opt/pharma_agent/backup.sh
```

### Schedule Backups with Cron

```bash
# Add to crontab
crontab -e

# Add line for daily backup at 2 AM
0 2 * * * /opt/pharma_agent/backup.sh >> /var/log/pharma_backup.log 2>&1
```

### Restore from Backup

```bash
# List available backups
ls -la /opt/pharma_agent/backups/

# Restore specific backup
BACKUP_FILE="/opt/pharma_agent/backups/postgres_20240101_020000.sql.gz"

# Stop services
docker compose stop fastapi_backend streamlit_dashboard

# Restore database
zcat $BACKUP_FILE | \
  docker exec -i pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_prod

# Start services
docker compose up -d
```

### Backup Verification

```bash
# Test restore on separate database
docker exec -i pharma_agent-postgres_db-1 \
  createdb -U pharma_prod compliance_test

zcat $BACKUP_FILE | \
  docker exec -i pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_test

# Verify data integrity
docker exec pharma_agent-postgres_db-1 \
  psql -U pharma_prod -d compliance_test \
  -c "SELECT COUNT(*) FROM compliance_audits;"

# Clean up test database
docker exec pharma_agent-postgres_db-1 \
  dropdb -U pharma_prod compliance_test
```

---

## Performance Tuning

### PostgreSQL Optimization

```sql
-- Analyze query performance
EXPLAIN ANALYZE
SELECT * FROM compliance_audits WHERE team = 'BioGenomics';

-- Add missing indexes
CREATE INDEX CONCURRENTLY idx_compliance_team_date 
  ON compliance_audits(team, date DESC);

-- Vacuum and analyze
VACUUM ANALYZE compliance_audits;

-- Check database size
SELECT pg_size_pretty(pg_database_size('compliance_prod'));

-- Check index sizes
SELECT indexname, pg_size_pretty(pg_relation_size(indexrelid))
FROM pg_indexes WHERE tablename = 'compliance_audits';
```

### FastAPI Performance Tuning

```python
# Enable gzip compression
from fastapi.middleware.gzip import GZIPMiddleware
app.add_middleware(GZIPMiddleware, minimum_size=1000)

# Add CORS headers properly
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pharma.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connection pooling
from sqlalchemy.pool import NullPool, StaticPool
DATABASE_URL = "postgresql://user:pass@host/db"
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # For AWS Lambda
    connect_args={"timeout": 10}
)
```

### Docker Resource Limits

```yaml
services:
  fastapi_backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

---

## Rollback Procedures

### Container Image Rollback

```bash
# Check deployment history
docker image ls | grep pharma-agent

# Rollback to previous tag
docker compose down
docker compose up -d --force-recreate

# Or manually pull previous version
docker pull pharma-agent:v1.0.0
# Update docker-compose.yml to use v1.0.0
docker compose up -d
```

### Kubernetes Rollback

```bash
# View rollout history
kubectl rollout history deployment/fastapi-backend -n pharma-prod

# Rollback to previous version
kubectl rollout undo deployment/fastapi-backend -n pharma-prod

# Rollback to specific revision
kubectl rollout undo deployment/fastapi-backend \
  --to-revision=2 -n pharma-prod

# Check status
kubectl rollout status deployment/fastapi-backend -n pharma-prod
```

### Database Rollback

```bash
# Using backup
# (See Backup & Recovery section above)

# Or using PostgreSQL point-in-time recovery
# Configure wal_level = replica in postgresql.conf
# Enable WAL archiving to S3/backup location

# Recover to specific point in time
RECOVERY_TARGET_TIME = '2024-01-15 14:30:00'
```

---

## Deployment Verification Checklist

### Post-Deployment Tests

```bash
# 1. Service Health
□ curl http://localhost:8000/health                  # API health
□ curl http://localhost:8000/readiness               # Readiness
□ curl http://localhost:8501                         # Dashboard loads
□ curl http://localhost:5432 (via psql)              # Database responsive

# 2. Authentication
□ Login succeeds with valid credentials
□ Login fails with invalid credentials
□ JWT token is valid and not expired
□ Token includes required claims (sub, team)

# 3. Data Access
□ Retrieve compliance data for authorized team
□ Cannot retrieve data for unauthorized team
□ Pagination works if implemented
□ Filtering by date works

# 4. External Integrations
□ Qdrant connectivity confirmed
□ Ollama model availability confirmed
□ Email notifications working (if enabled)

# 5. Performance
□ API responds in <200ms (p95)
□ Dashboard renders in <2s
□ Database queries optimized

# 6. Logging & Monitoring
□ Logs captured in central location
□ Metrics exported to monitoring system
□ Alerts configured for critical issues

# 7. Backup & Recovery
□ Daily backups completing successfully
□ Backup restoration tested
□ Recovery RTO/RPO documented
```

