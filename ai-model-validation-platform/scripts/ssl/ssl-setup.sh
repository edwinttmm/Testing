#!/bin/bash

# SSL Certificate Setup Script for AI Model Validation Platform
# Supports both Let's Encrypt and self-signed certificates

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SSL_DIR="/etc/nginx/ssl"
CERTBOT_DIR="/etc/letsencrypt"
ENV_FILE="$PROJECT_ROOT/.env.vultr"

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"; exit 1; }
info() { echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"; }

# Check if running as root or with sudo
check_permissions() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run with sudo privileges for SSL certificate management"
    fi
}

# Install required packages
install_requirements() {
    log "Installing SSL requirements..."
    
    apt update
    apt install -y \
        certbot \
        openssl \
        curl \
        nginx-common
    
    log "Requirements installed"
}

# Create SSL directory structure
create_ssl_directories() {
    log "Creating SSL directory structure..."
    
    mkdir -p "$SSL_DIR"
    mkdir -p "/var/www/certbot"
    mkdir -p "/var/log/ssl"
    
    # Set proper permissions
    chmod 700 "$SSL_DIR"
    chmod 755 "/var/www/certbot"
    
    log "SSL directories created"
}

# Generate DH parameters
generate_dhparam() {
    log "Generating DH parameters..."
    
    if [[ ! -f "$SSL_DIR/dhparam.pem" ]]; then
        info "Generating 2048-bit DH parameters (this may take several minutes)..."
        openssl dhparam -out "$SSL_DIR/dhparam.pem" 2048
        chmod 644 "$SSL_DIR/dhparam.pem"
        log "DH parameters generated"
    else
        info "DH parameters already exist"
    fi
}

# Generate self-signed certificate
generate_self_signed() {
    local domain="${1:-155.138.239.131}"
    
    log "Generating self-signed certificate for $domain..."
    
    # Generate private key
    openssl genrsa -out "$SSL_DIR/private.key" 2048
    chmod 600 "$SSL_DIR/private.key"
    
    # Generate certificate
    openssl req -new -x509 -key "$SSL_DIR/private.key" -out "$SSL_DIR/cert.pem" -days 365 -subj "
        /C=US
        /ST=New Jersey
        /L=Piscataway
        /O=AI Model Validation Platform
        /OU=IT Department
        /CN=$domain
        /emailAddress=admin@$domain
    " 2>/dev/null
    
    chmod 644 "$SSL_DIR/cert.pem"
    
    # Create certificate chain (self-signed doesn't have intermediate certs)
    cp "$SSL_DIR/cert.pem" "$SSL_DIR/fullchain.pem"
    
    log "Self-signed certificate generated for $domain"
    info "Certificate location: $SSL_DIR/cert.pem"
    info "Private key location: $SSL_DIR/private.key"
    
    # Display certificate information
    openssl x509 -in "$SSL_DIR/cert.pem" -text -noout | grep -E "(Subject|Issuer|Not Before|Not After)"
}

# Setup Let's Encrypt certificate
setup_letsencrypt() {
    local domain="$1"
    local email="$2"
    
    log "Setting up Let's Encrypt certificate for $domain..."
    
    # Validate domain and email
    if [[ -z "$domain" || "$domain" == "your-domain.com" ]]; then
        error "Please provide a valid domain name"
    fi
    
    if [[ -z "$email" || "$email" == "admin@your-domain.com" ]]; then
        error "Please provide a valid email address"
    fi
    
    # Check if domain resolves to current server
    info "Checking DNS resolution for $domain..."
    DOMAIN_IP=$(dig +short "$domain" | tail -n1)
    SERVER_IP=$(curl -s ifconfig.me || curl -s icanhazip.com || echo "unknown")
    
    if [[ "$DOMAIN_IP" != "$SERVER_IP" ]]; then
        warn "Domain $domain resolves to $DOMAIN_IP but server IP is $SERVER_IP"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            error "Please update DNS records first"
        fi
    fi
    
    # Stop nginx if running to free port 80
    if systemctl is-active --quiet nginx; then
        info "Stopping nginx temporarily..."
        systemctl stop nginx
        RESTART_NGINX=true
    fi
    
    # Stop Docker nginx if running
    if docker ps --format "table {{.Names}}" | grep -q ai_validation_nginx; then
        info "Stopping Docker nginx temporarily..."
        docker stop ai_validation_nginx || true
        RESTART_DOCKER=true
    fi
    
    # Get certificate using standalone method
    info "Requesting certificate from Let's Encrypt..."
    certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$email" \
        --domains "$domain" \
        --keep-until-expiring \
        --expand
    
    # Copy certificates to nginx directory
    if [[ -d "$CERTBOT_DIR/live/$domain" ]]; then
        cp "$CERTBOT_DIR/live/$domain/fullchain.pem" "$SSL_DIR/cert.pem"
        cp "$CERTBOT_DIR/live/$domain/fullchain.pem" "$SSL_DIR/fullchain.pem"
        cp "$CERTBOT_DIR/live/$domain/privkey.pem" "$SSL_DIR/private.key"
        
        # Set proper permissions
        chmod 644 "$SSL_DIR/cert.pem" "$SSL_DIR/fullchain.pem"
        chmod 600 "$SSL_DIR/private.key"
        
        log "Let's Encrypt certificate installed successfully"
        
        # Display certificate information
        openssl x509 -in "$SSL_DIR/cert.pem" -text -noout | grep -E "(Subject|Issuer|Not Before|Not After)"
    else
        error "Certificate generation failed"
    fi
    
    # Restart services if they were stopped
    if [[ "${RESTART_NGINX:-}" == "true" ]]; then
        info "Restarting nginx..."
        systemctl start nginx
    fi
    
    if [[ "${RESTART_DOCKER:-}" == "true" ]]; then
        info "Restarting Docker nginx..."
        docker start ai_validation_nginx || true
    fi
}

# Setup certificate renewal
setup_renewal() {
    local domain="${1:-}"
    
    log "Setting up certificate renewal..."
    
    if [[ -n "$domain" && "$domain" != "your-domain.com" ]]; then
        # Let's Encrypt renewal
        info "Setting up Let's Encrypt auto-renewal..."
        
        # Test renewal
        certbot renew --dry-run
        
        # Create renewal script
        cat > /usr/local/bin/renew-ssl.sh << 'EOF'
#!/bin/bash
# SSL Certificate Renewal Script

LOG_FILE="/var/log/ssl/renewal.log"
mkdir -p "$(dirname "$LOG_FILE")"

{
    echo "[$(date)] Starting certificate renewal check..."
    
    # Try to renew certificates
    certbot renew --quiet --post-hook "
        # Copy renewed certificates
        for domain in \$(ls /etc/letsencrypt/live/); do
            if [[ -d \"/etc/letsencrypt/live/\$domain\" ]]; then
                cp \"/etc/letsencrypt/live/\$domain/fullchain.pem\" \"/etc/nginx/ssl/cert.pem\"
                cp \"/etc/letsencrypt/live/\$domain/fullchain.pem\" \"/etc/nginx/ssl/fullchain.pem\"
                cp \"/etc/letsencrypt/live/\$domain/privkey.pem\" \"/etc/nginx/ssl/private.key\"
                chmod 644 /etc/nginx/ssl/cert.pem /etc/nginx/ssl/fullchain.pem
                chmod 600 /etc/nginx/ssl/private.key
                echo 'Certificates updated'
            fi
        done
        
        # Reload nginx
        docker kill -s HUP ai_validation_nginx 2>/dev/null || systemctl reload nginx 2>/dev/null || true
        echo 'Nginx reloaded'
    "
    
    echo "[$(date)] Certificate renewal check completed"
    
} >> "$LOG_FILE" 2>&1
EOF
        
        chmod +x /usr/local/bin/renew-ssl.sh
        
        # Add to cron
        CRON_JOB="0 2 * * 0 /usr/local/bin/renew-ssl.sh"
        (crontab -l 2>/dev/null | grep -v renew-ssl; echo "$CRON_JOB") | crontab -
        
        log "Let's Encrypt auto-renewal configured (weekly check)"
    else
        # Self-signed certificate renewal
        info "Setting up self-signed certificate renewal..."
        
        cat > /usr/local/bin/renew-ssl.sh << 'EOF'
#!/bin/bash
# Self-signed Certificate Renewal Script

LOG_FILE="/var/log/ssl/renewal.log"
mkdir -p "$(dirname "$LOG_FILE")"

{
    echo "[$(date)] Checking self-signed certificate expiration..."
    
    CERT_FILE="/etc/nginx/ssl/cert.pem"
    
    if [[ -f "$CERT_FILE" ]]; then
        # Check if certificate expires in the next 30 days
        if openssl x509 -checkend 2592000 -noout -in "$CERT_FILE"; then
            echo "Certificate is valid for more than 30 days"
        else
            echo "Certificate expires soon, regenerating..."
            
            # Regenerate self-signed certificate
            DOMAIN=$(openssl x509 -noout -subject -in "$CERT_FILE" | sed -n 's/.*CN=\([^,]*\).*/\1/p')
            
            openssl genrsa -out /etc/nginx/ssl/private.key 2048
            chmod 600 /etc/nginx/ssl/private.key
            
            openssl req -new -x509 -key /etc/nginx/ssl/private.key -out /etc/nginx/ssl/cert.pem -days 365 -subj "/C=US/ST=New Jersey/L=Piscataway/O=AI Model Validation Platform/OU=IT Department/CN=$DOMAIN/emailAddress=admin@$DOMAIN"
            chmod 644 /etc/nginx/ssl/cert.pem
            
            cp /etc/nginx/ssl/cert.pem /etc/nginx/ssl/fullchain.pem
            
            # Reload nginx
            docker kill -s HUP ai_validation_nginx 2>/dev/null || systemctl reload nginx 2>/dev/null || true
            
            echo "Self-signed certificate renewed"
        fi
    fi
    
    echo "[$(date)] Certificate check completed"
    
} >> "$LOG_FILE" 2>&1
EOF
        
        chmod +x /usr/local/bin/renew-ssl.sh
        
        # Add to cron (monthly check for self-signed)
        CRON_JOB="0 2 1 * * /usr/local/bin/renew-ssl.sh"
        (crontab -l 2>/dev/null | grep -v renew-ssl; echo "$CRON_JOB") | crontab -
        
        log "Self-signed certificate renewal configured (monthly check)"
    fi
}

# Verify SSL configuration
verify_ssl() {
    log "Verifying SSL configuration..."
    
    # Check certificate files
    if [[ ! -f "$SSL_DIR/cert.pem" ]]; then
        error "Certificate file not found: $SSL_DIR/cert.pem"
    fi
    
    if [[ ! -f "$SSL_DIR/private.key" ]]; then
        error "Private key not found: $SSL_DIR/private.key"
    fi
    
    if [[ ! -f "$SSL_DIR/dhparam.pem" ]]; then
        error "DH parameters not found: $SSL_DIR/dhparam.pem"
    fi
    
    # Verify certificate and key match
    CERT_HASH=$(openssl x509 -noout -modulus -in "$SSL_DIR/cert.pem" | openssl md5)
    KEY_HASH=$(openssl rsa -noout -modulus -in "$SSL_DIR/private.key" | openssl md5)
    
    if [[ "$CERT_HASH" != "$KEY_HASH" ]]; then
        error "Certificate and private key do not match"
    fi
    
    # Check certificate validity
    if ! openssl x509 -checkend 86400 -noout -in "$SSL_DIR/cert.pem"; then
        warn "Certificate expires within 24 hours"
    fi
    
    # Display certificate information
    info "Certificate Information:"
    openssl x509 -in "$SSL_DIR/cert.pem" -text -noout | grep -E "(Subject|Issuer|Not Before|Not After|DNS:|IP Address:)"
    
    log "SSL configuration verified successfully"
}

# Test SSL connection
test_ssl_connection() {
    local domain="${1:-155.138.239.131}"
    local port="${2:-443}"
    
    log "Testing SSL connection to $domain:$port..."
    
    # Test with openssl
    info "Testing SSL handshake..."
    if echo | openssl s_client -connect "$domain:$port" -servername "$domain" 2>/dev/null | grep -q "CONNECTED"; then
        log "✓ SSL handshake successful"
    else
        warn "✗ SSL handshake failed"
    fi
    
    # Test with curl if available
    if command -v curl &> /dev/null; then
        info "Testing HTTPS connection with curl..."
        if curl -I -s --connect-timeout 10 "https://$domain/health" | grep -q "200\|301\|302"; then
            log "✓ HTTPS connection successful"
        else
            warn "✗ HTTPS connection failed"
        fi
    fi
}

# Display SSL summary
display_summary() {
    log "SSL Setup Summary"
    echo "=================================="
    echo "SSL Directory: $SSL_DIR"
    echo "Certificate: $SSL_DIR/cert.pem"
    echo "Private Key: $SSL_DIR/private.key"
    echo "DH Parameters: $SSL_DIR/dhparam.pem"
    echo ""
    
    if [[ -f "$SSL_DIR/cert.pem" ]]; then
        echo "Certificate Details:"
        openssl x509 -in "$SSL_DIR/cert.pem" -text -noout | grep -E "(Subject|Issuer|Not Before|Not After)" | sed 's/^/  /'
        echo ""
    fi
    
    echo "Renewal Script: /usr/local/bin/renew-ssl.sh"
    echo "Renewal Logs: /var/log/ssl/renewal.log"
    echo ""
    echo "Next Steps:"
    echo "1. Test SSL connection from external client"
    echo "2. Verify certificate in browser"
    echo "3. Check automatic renewal setup"
    echo "4. Monitor renewal logs"
    echo "=================================="
}

# Main function
main() {
    log "Starting SSL certificate setup..."
    
    check_permissions
    install_requirements
    create_ssl_directories
    generate_dhparam
    
    # Read configuration from environment file
    if [[ -f "$ENV_FILE" ]]; then
        source "$ENV_FILE"
        DOMAIN="${DOMAIN_NAME:-155.138.239.131}"
        EMAIL="${SSL_EMAIL:-admin@example.com}"
    else
        warn "Environment file not found: $ENV_FILE"
        DOMAIN="155.138.239.131"
        EMAIL="admin@example.com"
    fi
    
    # Choose certificate type
    if [[ "$DOMAIN" != "your-domain.com" && "$DOMAIN" != "155.138.239.131" && "$EMAIL" != "admin@your-domain.com" ]]; then
        info "Domain and email configured, using Let's Encrypt"
        setup_letsencrypt "$DOMAIN" "$EMAIL"
    else
        info "Using self-signed certificate"
        generate_self_signed "$DOMAIN"
    fi
    
    setup_renewal "$DOMAIN"
    verify_ssl
    test_ssl_connection "$DOMAIN"
    display_summary
    
    log "SSL certificate setup completed successfully!"
}

# Help function
show_help() {
    echo "SSL Setup Script for AI Model Validation Platform"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -d, --domain DOMAIN Specify domain name"
    echo "  -e, --email EMAIL   Specify email for Let's Encrypt"
    echo "  -s, --self-signed   Force self-signed certificate"
    echo "  -t, --test-only     Only test existing certificate"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Auto-detect from .env.vultr"
    echo "  $0 -d example.com -e admin@example.com # Let's Encrypt"
    echo "  $0 -s                                 # Self-signed certificate"
    echo "  $0 -t                                 # Test existing certificate"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--domain)
            DOMAIN_NAME="$2"
            shift 2
            ;;
        -e|--email)
            SSL_EMAIL="$2"
            shift 2
            ;;
        -s|--self-signed)
            FORCE_SELF_SIGNED=true
            shift
            ;;
        -t|--test-only)
            TEST_ONLY=true
            shift
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Run appropriate function
if [[ "${TEST_ONLY:-}" == "true" ]]; then
    verify_ssl
    test_ssl_connection "${DOMAIN_NAME:-155.138.239.131}"
elif [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi