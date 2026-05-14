# DEPLOYMENT GUIDE - The Vow Ledger v1.0
# Security-First Production Deployment

## Prerequisites
- Linux server (Ubuntu 22.04 LTS recommended)
- Docker & Docker Compose installed
- Domain name with DNS configured
- SSL certificate (Let's Encrypt)

## STEP 1: Generate Secrets

```bash
# Create secrets directory
mkdir -p secrets

# Generate strong secrets
openssl rand -hex 32 > secrets/db_password.txt
openssl rand -hex 64 > secrets/jwt_secret.txt
openssl rand -hex 32 > secrets/phone_salt.txt
openssl rand -hex 32 > secrets/ip_salt.txt

# Secure the secrets
chmod 600 secrets/*
```

## STEP 2: Configure Firewall

```bash
# Ubuntu/Debian with UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Optional: Change SSH port for additional security
# Edit /etc/ssh/sshd_config: Port 2222
# Then: sudo ufw allow 2222/tcp && sudo ufw delete allow 22/tcp
```

## STEP 3: SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt update
sudo apt install certbot

# Get certificate (DNS or HTTP challenge)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy to project
mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/

# Set permissions
sudo chown $USER:$USER nginx/ssl/*
chmod 644 nginx/ssl/fullchain.pem
chmod 600 nginx/ssl/privkey.pem

# Auto-renewal
sudo systemctl enable certbot.timer
```

## STEP 4: Update Configuration

1. Edit `nginx/nginx.conf`:
   - Replace `yourdomain.com` with your actual domain

2. Edit `docker-compose.production.yml`:
   - Verify all paths are correct
   - Adjust resource limits based on your server

3. Update `main.py` CORS configuration:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com", "https://www.yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Submitter-Pubkey"],
)
```

## STEP 5: Build and Deploy

```bash
# Build the production image
docker build -f Dockerfile.production -t vow-api:latest .

# Start services
docker-compose -f docker-compose.production.yml up -d

# Check logs
docker-compose -f docker-compose.production.yml logs -f

# Verify health
curl http://localhost:8000/api/v1/health
curl https://yourdomain.com/api/v1/health
```

## STEP 6: Verify Security

```bash
# Check running containers
docker ps

# Verify database is NOT exposed
netstat -tuln | grep 5432  # Should NOT show 0.0.0.0:5432

# Test rate limiting
for i in {1..20}; do curl -s -o /dev/null -w "%{http_code}\n" https://yourdomain.com/; done
# Should see 429 errors after exceeding limits

# Check SSL configuration
curl -I https://yourdomain.com | grep -i "strict-transport"
```

## STEP 7: Monitoring Setup

```bash
# Install monitoring tools (optional but recommended)
docker run -d --name=cadvisor \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  --publish=8080:8080 \
  --detach=true \
  --name=cadvisor \
  google/cadvisor:latest
```

## STEP 8: Backup Verification

```bash
# Test backup creation
docker exec vow_postgres pg_dump -U vow -Fc vow > test_backup.dump

# Test backup restore (on test database)
docker exec -i vow_postgres pg_restore -U vow -d vow_test < test_backup.dump

# Set up offsite backup sync (to S3/B2/etc)
# Example with rclone:
rclone sync ./backups remote:vow-backups --progress
```

## STEP 9: Post-Deployment Checklist

- [ ] All secrets are unique and secure
- [ ] Database port is NOT exposed
- [ ] HTTPS is working with valid certificate
- [ ] Rate limiting is active (test with curl loop)
- [ ] CORS is configured for specific domains only
- [ ] Security headers are present (check with curl -I)
- [ ] Backups are running and can be restored
- [ ] Monitoring/alerting is configured
- [ ] Error logging is working (check Sentry/logs)
- [ ] Admin endpoints are protected
- [ ] File uploads are working correctly
- [ ] Evidence storage is configured
- [ ] DNS is pointing to server
- [ ] Firewall rules are active

## STEP 10: Ongoing Maintenance

```bash
# Update containers (weekly)
docker-compose -f docker-compose.production.yml pull
docker-compose -f docker-compose.production.yml up -d

# Check logs for errors (daily)
docker-compose -f docker-compose.production.yml logs --tail=100 api

# Monitor disk usage
df -h
docker system df

# Clean old Docker images (monthly)
docker system prune -a --volumes
```

## Emergency Procedures

### Container Won't Start
```bash
docker-compose -f docker-compose.production.yml logs api
docker-compose -f docker-compose.production.yml restart api
```

### Database Issues
```bash
# Check database logs
docker-compose -f docker-compose.production.yml logs postgres

# Access database shell
docker exec -it vow_postgres psql -U vow -d vow

# Restore from backup
docker exec -i vow_postgres pg_restore -U vow -d vow -c < backups/latest.dump
```

### Under DDoS Attack
```bash
# Enable Cloudflare "Under Attack" mode (if using Cloudflare)
# Increase rate limits temporarily:
# Edit nginx/nginx.conf, reduce rate=10r/s to rate=5r/s

# Block specific IPs
sudo ufw deny from <ATTACKER_IP>

# Monitor in real-time
watch -n 1 'docker-compose -f docker-compose.production.yml logs --tail=20 nginx'
```

### Data Breach Response
1. Immediately take site offline
2. Rotate all secrets
3. Analyze logs for intrusion vectors
4. Restore from known-good backup
5. Patch vulnerabilities
6. Notify affected users (if personal data compromised)

## Performance Tuning

### If experiencing high load:

```bash
# Scale API workers
# Edit Dockerfile.production: --workers 4 -> --workers 8

# Increase database connections
# Edit docker-compose.production.yml:
# postgres -> deploy -> resources -> limits -> memory: 2G

# Enable Redis caching
docker run -d --name redis --network vow_internal redis:alpine
```

## Security Hardening Beyond This Guide

1. **Implement Cloudflare** (free tier provides DDoS protection)
2. **Add fail2ban** for automated IP banning
3. **Enable audit logging** for all admin actions
4. **Set up intrusion detection** (OSSEC, Wazuh)
5. **Regular security audits** (quarterly)
6. **Penetration testing** before major releases
7. **Bug bounty program** when funded

## Compliance & Legal

- Ensure GDPR compliance if serving EU users
- Implement data export functionality
- Create clear Terms of Service
- Consult legal counsel for whistleblower protections
- Document incident response procedures

---

**REMEMBER:** Security is an ongoing process, not a one-time setup.
Review and update these procedures quarterly.

Generated: 2026-01-06
