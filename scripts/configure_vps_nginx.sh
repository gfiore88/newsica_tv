#!/usr/bin/env bash
set -euo pipefail

NEWSICA_DOMAIN="${NEWSICA_DOMAIN:?NEWSICA_DOMAIN is required, e.g. regia.newsicatv.it}"
NEWSICA_ADMIN_EMAIL="${NEWSICA_ADMIN_EMAIL:-}"
NEWSICA_APP_PORT="${NEWSICA_APP_PORT:-5050}"
NEWSICA_ENABLE_TLS="${NEWSICA_ENABLE_TLS:-false}"

if [ "$(id -u)" -ne 0 ]; then
  exec sudo NEWSICA_DOMAIN="$NEWSICA_DOMAIN" \
    NEWSICA_ADMIN_EMAIL="$NEWSICA_ADMIN_EMAIL" \
    NEWSICA_APP_PORT="$NEWSICA_APP_PORT" \
    NEWSICA_ENABLE_TLS="$NEWSICA_ENABLE_TLS" \
    bash "$0"
fi

apt-get update
apt-get install -y --no-install-recommends nginx ufw

cat > /etc/nginx/sites-available/newsica-regia <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${NEWSICA_DOMAIN};

    client_max_body_size 512m;

    location / {
        proxy_pass http://127.0.0.1:${NEWSICA_APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
        proxy_send_timeout 300;
    }
}
NGINX

ln -sfn /etc/nginx/sites-available/newsica-regia /etc/nginx/sites-enabled/newsica-regia
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

ufw allow 80/tcp
ufw allow 443/tcp
ufw delete allow 5050/tcp >/dev/null 2>&1 || true
ufw --force enable

if [ "$NEWSICA_ENABLE_TLS" = "true" ]; then
  if [ -z "$NEWSICA_ADMIN_EMAIL" ]; then
    echo "NEWSICA_ADMIN_EMAIL is required when NEWSICA_ENABLE_TLS=true" >&2
    exit 30
  fi
  apt-get install -y --no-install-recommends certbot python3-certbot-nginx
  certbot --nginx \
    --non-interactive \
    --agree-tos \
    --redirect \
    --email "$NEWSICA_ADMIN_EMAIL" \
    -d "$NEWSICA_DOMAIN"
fi

systemctl enable --now nginx
systemctl status nginx --no-pager --lines=8
