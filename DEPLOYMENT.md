# AvailSmart Production Deployment & Architecture Runbook

This guide outlines step-by-step instructions to deploy **AvailSmart** to a production Linux server (Ubuntu 22.04/24.04 LTS) using **Nginx**, **Gunicorn**, **MariaDB/MySQL**, and **Let's Encrypt SSL**.

---

## 1. Server Prerequisites & System Dependencies

Run the following on your clean server:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev build-essential \
    libssl-dev libffi-dev libmariadb-dev libmariadb-dev-compat \
    mariadb-server nginx git curl ufw
```

Enable the firewall allowing SSH, HTTP, and HTTPS:
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

## 2. Production Database Setup (MariaDB / MySQL)

Secure your database engine and create the AvailSmart user:

```bash
sudo mysql_secure_installation
```

Login to the database shell:
```bash
sudo mysql -u root -p
```

Execute SQL commands:
```sql
CREATE DATABASE availsmart_prod_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'availsmart_user'@'localhost' IDENTIFIED BY 'StrongServerPassword9921!';
GRANT ALL PRIVILEGES ON availsmart_prod_db.* TO 'availsmart_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

---

## 3. Clone Repository & Setup Virtual Environment

```bash
sudo mkdir -p /var/www/availsmart
sudo chown -R $USER:$USER /var/www/availsmart
cd /var/www/availsmart

git clone <YOUR_GIT_REPO_URL> .

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install production dependencies
pip install --upgrade pip
pip install -r requirements.txt gunicorn
```

---

## 4. Production Environment Configuration

Copy the production sample to `.env`:
```bash
cp .env.production.example .env
nano .env
```

Ensure the following variables are configured:
```ini
SECRET_KEY=generate-a-strong-random-50-character-secret-key-here
DEBUG=False
ALLOWED_HOSTS=availsmart.com,www.availsmart.com,YOUR_SERVER_IP

DB_ENGINE=django.db.backends.mysql
DB_NAME=availsmart_prod_db
DB_USER=availsmart_user
DB_PASSWORD=StrongServerPassword9921!
DB_HOST=127.0.0.1
DB_PORT=3306

SECURE_SSL_REDIRECT=True
```

---

## 5. Migrations, Static Collection & Seed Data

Run migrations and collect all static assets:

```bash
python manage.py migrate
python manage.py collectstatic --noinput

# Populate initial product catalog, categories, and brands
python manage.py seed_data
```

Ensure write permissions for media upload directories:
```bash
sudo chown -R www-data:www-data /var/www/availsmart/media
sudo chmod -R 775 /var/www/availsmart/media
```

---

## 6. Gunicorn Systemd Service

Create a systemd service file to manage the WSGI server:

```bash
sudo nano /etc/systemd/system/availsmart.service
```

Paste the following configuration:

```ini
[Unit]
Description=AvailSmart Gunicorn Daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/availsmart
ExecStart=/var/www/availsmart/.venv/bin/gunicorn \
          --access-logfile /var/log/availsmart-access.log \
          --error-logfile /var/log/availsmart-error.log \
          --workers 3 \
          --bind unix:/run/availsmart.sock \
          availsmart.wsgi:application

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Start and enable the service:
```bash
sudo systemctl daemon-reload
sudo systemctl start availsmart
sudo systemctl enable availsmart
sudo systemctl status availsmart
```

---

## 7. Nginx Reverse Proxy Configuration

Create an Nginx configuration file:

```bash
sudo nano /etc/nginx/sites-available/availsmart
```

Paste the following server block:

```nginx
server {
    listen 80;
    server_name availsmart.com www.availsmart.com;

    client_max_body_size 10M;

    # Static Assets Cache
    location /static/ {
        alias /var/www/availsmart/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
    }

    # Media Uploads (thumbnails and product photos)
    location /media/ {
        alias /var/www/availsmart/media/;
        expires 7d;
        add_header Cache-Control "public, max-age=604800";
    }

    # Proxy to Gunicorn
    location / {
        include proxy_params;
        proxy_pass http://unix:/run/availsmart.sock;
    }
}
```

Enable the site configuration and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/availsmart /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 8. SSL Certificate via Certbot

Install Certbot and provision a free Let's Encrypt SSL certificate:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d availsmart.com -d www.availsmart.com
```

Certbot will automatically update the Nginx configuration to enforce HTTP-to-HTTPS redirects and configure renewal timers.

---

## 9. Automated Database Backup Cron

Create an automated daily backup script:

```bash
sudo nano /usr/local/bin/backup-availsmart.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/availsmart"
mkdir -p $BACKUP_DIR
DATE=$(date +"%Y%m%d_%H%M%S")
mysqldump -u availsmart_user -p'StrongServerPassword9921!' availsmart_prod_db | gzip > "$BACKUP_DIR/availsmart_$DATE.sql.gz"
# Keep only last 14 days of backups
find $BACKUP_DIR -name "availsmart_*.sql.gz" -mtime +14 -delete
```

Make executable and add to crontab:
```bash
sudo chmod +x /usr/local/bin/backup-availsmart.sh
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/backup-availsmart.sh") | crontab -
```

---

## 10. Production Verification Checklist

1. **Security Headers**:
   - `X-Content-Type-Options: nosniff` active.
   - `X-Frame-Options: DENY` active (prevents clickjacking).
   - `CSRF_COOKIE_SECURE` and `SESSION_COOKIE_SECURE` active over HTTPS.
2. **SEO & Structured Data**:
   - Verify `https://availsmart.com/robots.txt` loads and points to `/sitemap.xml`.
   - Verify `https://availsmart.com/sitemap.xml` lists all catalog categories and products.
   - Verify Google Rich Results test on any product page detects `Product` and `Offer` schema.
3. **Database Performance**:
   - All slug, category, brand, price, is_active, and created_at fields are indexed.
4. **Image Optimization**:
   - Pillow automatically generates compressed WebP thumbnails on upload.
