#!/bin/bash
# Quick Setup Script for The Vow Ledger
# Run this on a fresh Ubuntu 22.04 server

set -e

echo "=========================================="
echo "The Vow Ledger - Production Setup"
echo "=========================================="
echo ""

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "This script should not be run as root" 
   exit 1
fi

# Update system
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "Docker installed. Please log out and back in for group changes to take effect."
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Install essential tools
echo "Installing essential tools..."
sudo apt install -y ufw certbot curl git

# Generate secrets
echo ""
echo "Generating secrets..."
mkdir -p secrets
openssl rand -hex 32 > secrets/db_password.txt
openssl rand -hex 64 > secrets/jwt_secret.txt
openssl rand -hex 32 > secrets/phone_salt.txt
openssl rand -hex 32 > secrets/ip_salt.txt
chmod 600 secrets/*

echo "✓ Secrets generated in ./secrets/"

# Create directories
echo "Creating required directories..."
mkdir -p backups nginx/ssl static templates evidence
chmod 755 backups evidence

# Configure firewall
echo ""
read -p "Configure firewall? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow 22/tcp
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    echo "y" | sudo ufw enable
    echo "✓ Firewall configured"
fi

# Get SSL certificate
echo ""
read -p "Enter your domain name (or skip): " domain
if [[ ! -z "$domain" ]]; then
    read -p "Get Let's Encrypt certificate for $domain? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo certbot certonly --standalone -d $domain -d www.$domain
        sudo cp /etc/letsencrypt/live/$domain/fullchain.pem nginx/ssl/
        sudo cp /etc/letsencrypt/live/$domain/privkey.pem nginx/ssl/
        sudo chown $USER:$USER nginx/ssl/*
        chmod 644 nginx/ssl/fullchain.pem
        chmod 600 nginx/ssl/privkey.pem
        
        # Update nginx config
        sed -i "s/yourdomain.com/$domain/g" nginx/nginx.conf
        
        echo "✓ SSL certificate installed"
    fi
fi

# Display secrets
echo ""
echo "=========================================="
echo "IMPORTANT: Save these credentials!"
echo "=========================================="
echo "Database Password: $(cat secrets/db_password.txt)"
echo "JWT Secret: $(cat secrets/jwt_secret.txt | cut -c1-20)..."
echo ""
echo "Full secrets are in ./secrets/ directory"
echo "=========================================="
echo ""

# Final instructions
cat << 'EOF'
Setup complete! Next steps:

1. Review and update configuration files:
   - nginx/nginx.conf (update domain names)
   - docker-compose.production.yml
   - main.py (CORS settings)

2. Build and start services:
   docker build -f Dockerfile.production -t vow-api:latest .
   docker-compose -f docker-compose.production.yml up -d

3. Check logs:
   docker-compose -f docker-compose.production.yml logs -f

4. Verify deployment:
   curl http://localhost:8000/api/v1/health
   
5. Set up monitoring and backups (see DEPLOYMENT_GUIDE.md)

For detailed instructions, see DEPLOYMENT_GUIDE.md
EOF

echo ""
echo "Setup script completed successfully!"
