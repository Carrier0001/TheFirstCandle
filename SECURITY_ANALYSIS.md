# THE VOW LEDGER - Security & Infrastructure Analysis
Date: 2026-01-06 | Analyst: Docker Agent Team

---

## 🎯 EXECUTIVE SUMMARY

**What You Have Built:**
- A whistleblowing platform ("Vow Ledger v1.0") with a jury consensus system
- PostgreSQL database tracking submissions, entries, evidence, and systemic patterns
- Harm quantification system: Life Years (LY), Financial USD, Ecosystem Years (ECY)
- Docker containerized FastAPI application
- Privacy features: hashed IPs, hashed submitter keys
- Evidence file storage with S3 references

**Your Threat Model:**
- DDoS attacks
- State actors attempting shutdown
- Powerful entities seeking to suppress data
- Data integrity attacks
- Infrastructure takedown attempts

**Current State:** Development / Early Production
**Readiness for Adversarial Environment:** ⚠️ NOT READY (30% prepared)

---

## 🚨 CRITICAL SECURITY VULNERABILITIES

### 1. CORS Configuration - CRITICAL
**Issue:** `allow_origins=["*"]` in development mode
**Risk Level:** 🔴 CRITICAL
**Impact:** Any website can make requests to your API, enabling XSS attacks
**Fix:**```python
# In main.py, replace:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domains only
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only needed methods
    allow_headers=["Content-Type", "X-Submitter-Pubkey"],
)
```

### 2. Hardcoded Secrets in docker-compose.yml - CRITICAL
**Issue:** Default passwords visible in compose file
**Risk Level:** 🔴 CRITICAL
**Current:**
```yaml
POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme123}
JWT_SECRET: ${JWT_SECRET:-super-secret-jwt-key-change-in-prod}
```
**Fix:** Use Docker secrets or external secret manager```bash
# Generate strong secrets
openssl rand -hex 32 > db_password.txt
openssl rand -hex 64 > jwt_secret.txt
```

### 3. Database Exposed on Host - HIGH
**Issue:** Port 5432 mapped to host in docker-compose
**Risk Level:** 🟠 HIGH
**Impact:** Database accessible from outside Docker network
**Fix:**
```yaml
# Remove from docker-compose.yml:
ports:
  - "5432:5432"  # DELETE THIS LINE
# Only API should access database via internal Docker network
```

### 4. No Rate Limiting - CRITICAL
**Issue:** No protection against spam submissions or brute force
**Risk Level:** 🔴 CRITICAL
**Impact:** Easy DDoS via API endpoints, database flooding
**Fix:** Implement rate limiting middleware
```python
# Install: pip install slowapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/submit")
@limiter.limit("5/minute")  # 5 submissions per minute per IP
async def submit_testimony(...):
    ...
```

### 5. Evidence Storage Not Implemented - HIGH
**Issue:** References S3 paths but no actual upload mechanism
**Risk Level:** 🟠 HIGH
**Current Code:**
```python
storage_path = f"s3://vow-evidence/{submission_id}/{file_hash}{ext}"
# But no actual S3 upload happens
```
**Fix:** Implement actual S3/R2/Backblaze B2 integration

### 6. No Authentication on Admin Endpoints - CRITICAL
**Issue:** Admin endpoints return 404 but exist in code
**Risk Level:** 🔴 CRITICAL
**Impact:** Once implemented, likely no auth protection
**Fix:** Implement JWT-based admin authentication BEFORE enabling

### 7. SQL Injection Protection - GOOD ✅
**Status:** Using parameterized queries correctly
**Example:** `conn.fetchval("SELECT 1 FROM submissions WHERE submission_hash = $1", submission_hash)`

### 8. No HTTPS Enforcement - CRITICAL
**Issue:** Running on HTTP (port 8000)
**Risk Level:** 🔴 CRITICAL in production
**Fix:** Use reverse proxy (Nginx/Caddy) with TLS termination

---

## 📋 INFRASTRUCTURE HARDENING REQUIREMENTS

### Docker Security Improvements

1. **Run as Non-Root User**
```dockerfile
# Add to Dockerfile:
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser
```

2. **Multi-Stage Build for Smaller Image**
```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

3. **Docker Compose Health Checks**
```yaml
api:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

4. **Resource Limits**
```yaml
api:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 512M
```

### Database Security

1. **Backup Strategy**
```yaml
# Add to docker-compose.yml
backup:
  image: postgres:15-alpine
  volumes:
    - ./backups:/backups
    - postgres_data:/var/lib/postgresql/data:ro
  environment:
    PGPASSWORD: ${DB_PASSWORD}
  command: >
    sh -c "while true; do
      pg_dump -h postgres -U vow -d vow -Fc > /backups/vow_$(date +%Y%m%d_%H%M%S).dump
      find /backups -name '*.dump' -mtime +7 -delete
      sleep 86400
    done"
```

2. **Connection Pooling Already Configured** ✅
```python
db_pool = await asyncpg.create_pool(
    config.DATABASE_URL,
    min_size=5,
    max_size=20,  # Good for handling concurrent requests
    command_timeout=60,
)
```

---

## 🛡️ DDoS MITIGATION STRATEGY

### Layer 7 (Application Layer)
**Current Status:** ❌ No protection
**Required:**

1. **Cloudflare Free Tier** (Recommended for start)
   - Automatic DDoS protection
   - Bot management
   - Rate limiting (5 rules free)
   - HTTPS/TLS termination
   - CDN for static assets

2. **Nginx Reverse Proxy**
```nginx
# /etc/nginx/nginx.conf
http {
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_conn_zone $binary_remote_addr zone=addr:10m;
    
    server {
        listen 443 ssl http2;
        server_name yourdomain.com;
        
        ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
        
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            limit_conn addr 10;
            proxy_pass http://localhost:8000;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }
}
```

3. **FastAPI Middleware**
```python
# app/middleware/security.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import time

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

### Layer 4 (Transport Layer)
**Solutions:**
- Cloudflare Spectrum (paid)
- AWS Shield Standard (free with AWS)
- DigitalOcean DDoS protection (included)

### Layer 3 (Network Layer)
**Cloud Provider Protection:**
- All major cloud providers include this
- Ensure your hosting has this enabled

---

## 🌐 DEPLOYMENT ARCHITECTURE RECOMMENDATIONS

### Option 1: Budget-Friendly ($10-30/month)
**Stack:**
- DigitalOcean Droplet ($12/month, 2GB RAM)
- Cloudflare Free Tier (DDoS + CDN)
- Backblaze B2 for evidence storage ($0.005/GB)
- Docker Compose deployment

**Pros:** Cheap, simple, good for start
**Cons:** Single point of failure, manual scaling

### Option 2: Resilient ($50-100/month)
**Stack:**
- Railway.app or Render.com (managed containers)
- Cloudflare Pro ($20/month)
- PostgreSQL managed database (separate from app)
- Cloudflare R2 for evidence storage

**Pros:** Auto-scaling, managed backups, better uptime
**Cons:** More expensive, less control

### Option 3: Enterprise-Grade ($200+/month)
**Stack:**
- Kubernetes cluster (EKS/GKE/DO)
- Multi-region deployment
- AWS Shield Advanced
- Dedicated database cluster
- Professional backup solution

**Pros:** Maximum resilience, can handle state actors
**Cons:** Complex, requires DevOps expertise, expensive

### Recommended for Your Use Case: **Option 2**
**Reasoning:**
- Balance of cost and resilience
- Managed infrastructure reduces attack surface
- Automatic scaling handles traffic spikes
- Focus on application, not infrastructure

---

## 📊 DATABASE OPTIMIZATION

### Current Schema Analysis
**✅ Good Practices:**
- UUIDs for primary keys (good for distributed systems)
- Proper indexes on frequently queried columns
- JSONB for flexible data (consensus_data)
- Constraints for data integrity
- Cascading deletes configured

**⚠️ Improvements Needed:**

1. **Add Database Monitoring**
```sql
-- Enable pg_stat_statements
CREATE EXTENSION pg_stat_statements;

-- Query to find slow queries
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

2. **Partitioning for Audit Log** (when you have >1M records)
```sql
-- Partition by month
CREATE TABLE audit_log_2026_01 PARTITION OF audit_log
FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

3. **Connection Pooling Outside Container**
Consider PgBouncer for production:
```yaml
pgbouncer:
  image: edoburu/pgbouncer
  environment:
    DATABASE_URL: "postgres://vow:${DB_PASSWORD}@postgres/vow"
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 1000
    DEFAULT_POOL_SIZE: 20
```

---

## 🔐 SECRETS MANAGEMENT

### Current State: ⚠️ INSECURE
Environment variables in `.env` file

### Production Solution:

**Option A: Docker Secrets** (Docker Swarm)
```yaml
secrets:
  db_password:
    external: true
  jwt_secret:
    external: true

services:
  api:
    secrets:
      - db_password
      - jwt_secret
    environment:
      DB_PASSWORD_FILE: /run/secrets/db_password
```

**Option B: External Secret Manager**
- AWS Secrets Manager
- HashiCorp Vault
- Doppler
- 1Password Secrets Automation

**Option C: Encrypted ENV** (simple start)
```bash
# Use git-crypt or sops for encrypted .env files
brew install sops
sops -e .env > .env.enc
```

---

## 🔍 MONITORING & ALERTING (CRITICAL FOR ADVERSARIAL ENVIRONMENT)

### What You Need:

1. **Application Monitoring**
```python
# Add to requirements.txt
sentry-sdk[fastapi]==1.39.0

# In main.py
import sentry_sdk
sentry_sdk.init(
    dsn="your-sentry-dsn",
    traces_sample_rate=0.1,
    environment="production",
)
```

2. **Log Aggregation**
```yaml
# Add Loki for log collection
loki:
  image: grafana/loki:2.9.0
  ports:
    - "3100:3100"
  volumes:
    - ./loki-config.yml:/etc/loki/config.yml

grafana:
  image: grafana/grafana:10.0.0
  ports:
    - "3000:3000"
  environment:
    GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
```

3. **Uptime Monitoring**
- UptimeRobot (free tier: 50 monitors)
- Better Uptime (free tier: 10 monitors)
- Freshping (free)

4. **Security Monitoring**
```python
# Log all submission attempts
from app.core.logging import log_audit

log_audit("SUBMISSION_ATTEMPT", 
          submitter_hash, 
          "SUBMITTER",
          ip_hash=ip_hash,
          success=True/False)
```

---

## 🚀 PRE-LAUNCH CHECKLIST

### Security
- [ ] Change all default passwords
- [ ] Implement rate limiting on all public endpoints
- [ ] Configure CORS to specific domains only
- [ ] Remove database port exposure
- [ ] Add HTTPS/TLS (Let's Encrypt)
- [ ] Implement admin authentication
- [ ] Set up Cloudflare DDoS protection
- [ ] Configure security headers middleware
- [ ] Enable audit logging for all sensitive operations
- [ ] Set up automated backups (test restore!)

### Infrastructure
- [ ] Set up monitoring (Sentry, Grafana, or similar)
- [ ] Configure log aggregation
- [ ] Set up uptime monitoring
- [ ] Implement database connection pooling
- [ ] Configure resource limits for containers
- [ ] Set up automated backups to offsite location
- [ ] Create disaster recovery runbook
- [ ] Document deployment process
- [ ] Set up staging environment

### Application
- [ ] Implement actual evidence file storage (S3/R2)
- [ ] Add file virus scanning (ClamAV)
- [ ] Test jury consensus system under load
- [ ] Validate all user inputs
- [ ] Add CAPTCHA to submission form
- [ ] Implement email notifications
- [ ] Create admin dashboard
- [ ] Add data export functionality
- [ ] Test aggregation system with real data

### Legal & Operational
- [ ] Terms of Service
- [ ] Privacy Policy
- [ ] Data retention policy
- [ ] GDPR compliance review (if EU users)
- [ ] Legal counsel consultation
- [ ] Incident response plan
- [ ] Backup administrator access
- [ ] Canary deployment strategy

---

## 💰 ESTIMATED COSTS

### Minimum Viable Production
- Domain: $15/year
- DigitalOcean Droplet: $12/month
- Backblaze B2: ~$5/month (for 1TB)
- Cloudflare: Free
- Sentry: Free tier
**Total: ~$17/month + $15/year**

### Recommended Production
- Domain: $15/year
- Railway/Render: $50/month
- Managed PostgreSQL: $15/month
- Cloudflare Pro: $20/month
- Sentry Pro: $26/month
- Cloudflare R2: $15/month (1TB)
**Total: ~$126/month + $15/year**

### Enterprise Grade
- Domain: $15/year
- Kubernetes cluster: $100+/month
- Managed DB cluster: $50+/month
- Cloudflare Business: $200/month
- AWS Shield Advanced: $3000/month
- Professional monitoring: $100+/month
**Total: $3450+/month**

---

## 🎓 REQUIRED SKILLS FOR PRODUCTION DEPLOYMENT

As a game dev, you'll need help with:
1. **DevOps/SRE** - Infrastructure, monitoring, incident response
2. **Security Engineer** - Threat modeling, penetration testing
3. **Backend Developer** - Python/FastAPI optimization
4. **Legal Counsel** - Whistleblower protection laws, liability

**Recommendation:** Find a technical co-founder or hire a senior backend engineer with security experience.

---

## 📝 IMMEDIATE NEXT STEPS (Priority Order)

1. **This Week:**
   - Change all default passwords
   - Remove database port exposure
   - Implement basic rate limiting
   - Sign up for Cloudflare (free)

2. **This Month:**
   - Deploy to managed platform (Railway/Render)
   - Implement evidence storage (R2/B2)
   - Add monitoring (Sentry free tier)
   - Create backup strategy
   - Write disaster recovery plan

3. **Before Public Launch:**
   - Security audit (hire professional)
   - Penetration testing
   - Load testing
   - Legal review
   - Create incident response team

---

## 🤝 RESOURCES & SUPPORT

### Learning Resources
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- Docker Security Best Practices: https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html
- FastAPI Security: https://fastapi.tiangolo.com/tutorial/security/

### Community
- /r/netsec
- OWASP Slack
- FastAPI Discord

### Professional Services (Consider When Funded)
- Trail of Bits (security audit)
- Cure53 (penetration testing)
- CloudFlare Professional Services

---

## ⚖️ FINAL ASSESSMENT

**Current State:** You have a solid foundation with good database design and basic security practices.

**Gap to Production:** Significant infrastructure and security work needed.

**Can a game dev do this alone?** Technically possible, but **not recommended** for a high-threat environment.

**Recommended Path:**
1. Use managed platforms (Railway, Render) to reduce operational burden
2. Partner with or hire experienced backend/security engineer
3. Use Cloudflare for DDoS protection (non-negotiable)
4. Start small, iterate with security first
5. Get professional security audit before significant traffic

**Timeline to Secure Launch:** 2-3 months with proper resources

---

**Generated by Docker Agent Team | 2026-01-06**
