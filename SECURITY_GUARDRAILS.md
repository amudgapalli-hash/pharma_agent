# Security Guard Rails Documentation

## Overview

This document describes the comprehensive security guard rails implemented across your pharmaceutical compliance application. The system protects against common web vulnerabilities, enforces regulatory compliance (HIPAA, FDA), and provides audit logging.

---

## 1. Security Components

### 1.1 Input Validation & Sanitization (`app/security.py` - `InputValidator`)

**Purpose**: Prevent injection attacks (SQL, XSS) and malformed input.

#### Features:
- **SQL Injection Prevention**: Detects and blocks common SQL patterns
  - Blocked keywords: UNION, SELECT, INSERT, UPDATE, DELETE, DROP, CREATE, ALTER
  - Blocked operators: --, #, /*, */, xp_, sp_
  - Blocked logic: OR/AND boolean patterns
  
- **XSS Prevention**: Detects and blocks script injection
  - Blocked: `<script>` tags, `javascript:` URLs
  - Blocked: Event handlers (onclick, onerror, etc.)
  - Blocked: `<iframe>` tags

- **String Validation**:
  ```python
  # Example usage
  from app.security import InputValidator
  
  # Validates string, checks length, sanitizes
  validated_input = InputValidator.validate_string(
      user_input,
      max_length=1000,
      field_name="research_query"
  )
  ```

- **Email Validation**: RFC-compliant email format checking
- **Username Validation**: Alphanumeric, underscore, dash only (3-32 chars)

#### Configuration:
```python
# In FastAPI main.py
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        username = InputValidator.validate_username(form_data.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

### 1.2 Protected Health Information (PHI) Detection (`app/security.py` - `PHIDetector`)

**Purpose**: Identify and prevent HIPAA violations by detecting sensitive patient data.

#### Detects:
- **SSN Patterns**: `XXX-XX-XXXX` or 9-digit numbers
- **Medical Record Numbers (MRN)**: `MRN: <value>`
- **Phone Numbers**: `(XXX) XXX-XXXX`, `XXX-XXX-XXXX`, etc.
- **Specific Dates**: Month + day + year combinations
- **ZIP Codes**: 5-digit and ZIP+4 formats
- **Email Addresses**: Standard email patterns
- **IP Addresses**: IPv4 address patterns

#### Usage:

```python
from app.security import PHIDetector

# Scan for PHI
text = "Patient John Smith (SSN: 123-45-6789) admitted on January 15, 2024"
detected_phi = PHIDetector.detect_phi(text)
print(detected_phi)
# Output: {'SSN': ['123-45-6789'], 'DATE_SPECIFIC': ['January 15, 2024']}

# Check compliance (raises exception if PHI found and not allowed)
is_compliant, detected = PHIDetector.scan_for_phi_violations(text, allow_detected_phi=False)
if not is_compliant:
    # Log violation for audit
    logger.error(f"HIPAA violation: {detected}")
```

#### Integration in Pipeline:

```python
# In src/app.py
@app.post("/api/v1/generate-protocol")
async def process_pipeline_endpoint(request: Request, payload: PipelineRequest):
    # Scan for PHI in input
    phi_compliant, detected_phi = PHIDetector.scan_for_phi_violations(
        query,
        allow_detected_phi=True  # Log but don't block
    )
    if detected_phi:
        logger.warning(f"PHI detected in query: {list(detected_phi.keys())}")
    
    # Scan for PHI in generated draft
    draft_phi_compliant, draft_phi = PHIDetector.scan_for_phi_violations(
        result["generated_draft"],
        allow_detected_phi=True
    )
    
    # Store in audit log
    audit_entry.phi_leaks_found = draft_phi
```

---

### 1.3 Rate Limiting (`app/security.py` - `RateLimiter`)

**Purpose**: Prevent abuse and DoS attacks through token bucket algorithm.

#### Configuration:

```python
from app.security import RateLimiter

# Initialize rate limiter: 100 requests per 60 seconds
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

# Check if request is allowed
if not rate_limiter.is_allowed(identifier):
    raise HTTPException(status_code=429, detail="Rate limit exceeded")

# Get remaining requests
remaining = rate_limiter.get_remaining(identifier)
```

#### Endpoints & Limits:

| Endpoint | Limit | Window | Identifier |
|----------|-------|--------|------------|
| `/token` | 100 | 60s | `login_{ip}` |
| `/compliance/audits` | 100 | 60s | `audits_{username}` |
| `/api/v1/generate-protocol` | 50 | 60s | `protocol_{ip}` |
| `/api/v1/audit-trail` | 50 | 60s | `audit_{ip}` |

#### Response Headers:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-Request-ID: a1b2c3d4e5f6g7h8
```

---

### 1.4 CORS (Cross-Origin Resource Sharing)

**Purpose**: Restrict API access to trusted frontend origins.

#### Configuration:

```python
# In app/main.py and src/app.py
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8501,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600,
)
```

#### Environment Variable:
```bash
# .env
ALLOWED_ORIGINS=http://localhost:8501,http://localhost:3000,https://yourdomain.com
```

---

### 1.5 Security Headers

**Purpose**: Add HTTP security headers to all responses.

#### Headers Applied:

```
X-Content-Type-Options: nosniff           # Prevent MIME type sniffing
X-Frame-Options: DENY                     # Prevent clickjacking
X-XSS-Protection: 1; mode=block           # Enable browser XSS filter
Strict-Transport-Security: max-age=31536000  # Enforce HTTPS
Content-Security-Policy: default-src 'self'; script-src 'self'
Referrer-Policy: strict-origin-when-cross-origin
```

---

### 1.6 Authentication & JWT

**Purpose**: Secure user authentication and authorization.

#### JWT Configuration:

```python
# In app/main.py
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-scientific-key-12345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
```

⚠️ **IMPORTANT**: In production, set `JWT_SECRET` environment variable:
```bash
export JWT_SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
```

#### Login Flow:
```python
@app.post("/token", response_model=Token)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # 1. Rate limit check
    if not rate_limiter.is_allowed(f"login_{request.client.host}"):
        raise HTTPException(status_code=429, detail="Too many login attempts")
    
    # 2. Validate input
    username = InputValidator.validate_username(form_data.username)
    
    # 3. Verify credentials
    user = USER_DB.get(username)
    if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
        logger.warning(f"Failed login: {username}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # 4. Create JWT
    access_token = create_access_token({"sub": username, "team": user["team"]})
    logger.info(f"User {username} authenticated")
    return {"access_token": access_token, "token_type": "bearer"}
```

#### Session Management (Streamlit):
```python
# In app/app.py
SESSION_TIMEOUT_MINUTES = 60

# Check timeout
if st.session_state.token:
    current_time = datetime.utcnow()
    login_time = datetime.fromisoformat(st.session_state.login_time)
    
    if (current_time - login_time).total_seconds() > SESSION_TIMEOUT_MINUTES * 60:
        st.session_state.token = None
        st.warning("Session expired")
```

---

### 1.7 Request Tracing & Audit Logging

**Purpose**: Track all requests for security audit and compliance.

#### Request ID Generation:
```python
from app.security import generate_request_id

request_id = generate_request_id()  # Returns 32-character hex string
```

#### Middleware:
```python
@app.middleware("http")
async def add_request_logging(request: Request, call_next):
    request_id = generate_request_id()
    request.state.request_id = request_id
    logger.info(f"[{request_id}] {request.method} {request.url.path}")
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

#### Audit Log Entry:
```python
# In CriticAuditLog (src/app.py)
audit_entry = CriticAuditLog(
    request_id=request_id,              # Track request
    query_topic=query[:255],            # Sanitized query
    iteration_number=result["iteration_count"],
    is_fda_compliant=...,
    is_hipaa_compliant=...,
    phi_leaks_found=draft_phi,          # Detected PHI
    raw_critique_json=...,
    evaluated_draft_text=result["generated_draft"][:2000]
)
db.add(audit_entry)
db.commit()
```

---

## 2. Deployment Security Checklist

### Environment Variables

Create `.env` file with:
```bash
# JWT Secret (generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))')
JWT_SECRET=your-generated-secret-key

# CORS Origins (restrict in production)
ALLOWED_ORIGINS=http://localhost:8501,https://yourdomain.com

# Database (use PostgreSQL in production, NOT SQLite)
DATABASE_URL=postgresql://user:password@localhost:5432/pharma_audit

# API Backend URL
API_URL=http://fastapi_backend:8000
```

### Production Hardening

#### 1. Enable HTTPS
```yaml
# docker-compose.yml
fastapi_backend:
  environment:
    - REQUIRE_HTTPS=true
```

#### 2. Use PostgreSQL (not SQLite)
```yaml
postgres_db:
  image: postgres:15-alpine
  environment:
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

#### 3. Network Isolation
```yaml
networks:
  sci_network:
    driver: bridge
    ipam:
      config:
        - subnet: 192.168.100.0/24
```

#### 4. Secret Management
```bash
# Use Docker secrets (Swarm) or env files
docker secret create jwt_secret /path/to/secret

# Or use .env file (not committed to git)
echo "JWT_SECRET=$(openssl rand -hex 32)" > .env.prod
chmod 600 .env.prod
```

---

## 3. HIPAA & FDA Compliance

### HIPAA Safe Harbor Compliance

The PHI detector ensures Safe Harbor de-identification by detecting:
- Direct identifiers (names, SSN, dates of birth, medical records)
- Geographic identifiers (ZIP codes for areas < 20K population)
- Contact information (phone, email, IP addresses)

### FDA Guidance Compliance

The LLM critic evaluates compliance with:
- **E6(R2) GCP Guidelines**: Good Clinical Practice requirements
- **21 CFR Part 11**: Electronic records authenticity
- **ICH Guidelines**: International harmonization

### Audit Trail

All protocol generations are logged with:
```
- Timestamp (ISO 8601 format)
- Request ID (unique tracing)
- User information (anonymous in audit logs)
- Query topic
- Iteration count
- FDA compliance status
- HIPAA compliance status
- Detected PHI
- Generated draft (truncated)
```

---

## 4. Logging & Monitoring

### Log Format
```
[REQUEST_ID] LEVEL MESSAGE
[a1b2c3d4e5f6g7h8] INFO User dr_smith retrieved 5 audits for team BioGenomics
[x9y8z7w6v5u4t3s2] WARNING Rate limit exceeded for IP: 192.168.1.100
[m1n2o3p4q5r6s7t8] ERROR Pipeline execution failed: Connection timeout
```

### Important Events to Monitor
- Failed login attempts (potential brute force)
- Rate limit exceeded events
- PHI detection warnings
- API errors (500 status)
- FDA/HIPAA compliance failures

---

## 5. Security Best Practices

### For Developers

1. **Never commit secrets**:
   ```bash
   echo ".env" >> .gitignore
   echo "*.key" >> .gitignore
   ```

2. **Always validate input**:
   ```python
   from app.security import InputValidator
   
   value = InputValidator.validate_string(user_input, max_length=1000)
   ```

3. **Check for PHI**:
   ```python
   from app.security import PHIDetector
   
   phi_safe, detected = PHIDetector.scan_for_phi_violations(text)
   ```

4. **Log security events**:
   ```python
   logger.warning(f"[{request_id}] Potential security issue: {event}")
   ```

### For Operators

1. **Rotate secrets regularly**:
   ```bash
   # Monthly secret rotation
   NEW_SECRET=$(openssl rand -hex 32)
   docker secret create jwt_secret_v2 /dev/stdin <<< "$NEW_SECRET"
   # Update services to use jwt_secret_v2
   ```

2. **Monitor audit logs**:
   ```sql
   -- Find failed compliance checks
   SELECT * FROM critic_audit_logs 
   WHERE is_hipaa_compliant = false 
   ORDER BY timestamp DESC;
   ```

3. **Review rate limit patterns**:
   - Multiple failed logins from same IP → potential attack
   - Rapid API requests from single user → legitimate or abuse?

4. **Test security headers**:
   ```bash
   curl -I http://localhost:8000/compliance/audits | grep -i "X-"
   ```

---

## 6. Incident Response

### Suspected Breach

1. **Check logs**:
   ```bash
   grep "PHI" app.log | tail -100
   grep "HIPAA" app.log | tail -100
   ```

2. **Query audit database**:
   ```sql
   SELECT * FROM critic_audit_logs 
   WHERE phi_leaks_found IS NOT NULL 
   AND phi_leaks_found != '{}';
   ```

3. **Audit affected requests**:
   ```sql
   SELECT * FROM critic_audit_logs 
   WHERE request_id IN ('list-of-suspicious-ids');
   ```

4. **Rotate secrets**:
   ```bash
   export JWT_SECRET=$(openssl rand -hex 32)
   docker compose restart fastapi_backend
   ```

### Rate Limit Abuse

```bash
# Monitor in real-time
tail -f app.log | grep "Rate limit exceeded"

# Block IP if necessary
iptables -A INPUT -s 192.168.1.100 -j DROP
```

---

## 7. Testing Security

### Test SQL Injection Prevention
```bash
curl -X POST http://localhost:8000/token \
  -d "username=admin' OR '1'='1&password=test"
# Should return: 400 Bad Request - "Invalid characters detected"
```

### Test XSS Prevention
```bash
curl -X POST http://localhost:8000/token \
  -d "username=<script>alert('xss')</script>&password=test"
# Should return: 400 Bad Request - "Invalid HTML/script detected"
```

### Test Rate Limiting
```bash
for i in {1..105}; do
  curl -X GET http://localhost:8000/compliance/audits \
    -H "Authorization: Bearer $TOKEN"
done
# Requests 101-105 should return: 429 Too Many Requests
```

### Test PHI Detection
```python
from app.security import PHIDetector

text = "Patient SSN: 123-45-6789, DOB: January 15, 1985, Phone: (555) 123-4567"
phi = PHIDetector.detect_phi(text)
assert 'SSN' in phi
assert 'PHONE' in phi
print("PHI Detection: PASSED")
```

---

## 8. Support & Documentation

### Additional Resources
- [OWASP Top 10](https://owasp.org/Top10/)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [FDA E6(R2) Guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/e6r2-good-clinical-practice-integrated-addendum-ich-e6r1)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

### Questions?
Contact your security team or refer to individual module docstrings in `app/security.py`.
