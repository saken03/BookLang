# BookLand PDF Translator

A Django application for uploading and translating PDF files to Russian using Google Cloud Translation API.

## Features
- PDF file upload with drag-and-drop support
- Text extraction from PDF files
- Word-by-word translation to Russian
- Clean, responsive UI
- Translation progress tracking
- Word frequency analysis
- User profiles with customizable settings
- Flashcard system for language learning

## Prerequisites
- Python 3.8 or higher
- Google Cloud account with Translation API enabled
- Google Cloud service account credentials
- PostgreSQL (for production)
- Redis (for caching in production)

## Setup Instructions

1. Clone the repository:
```bash
git clone <repository-url>
cd BookLand_B
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
```
Edit `.env` file with your configuration settings.

5. Set up Google Cloud credentials:
- Create a service account in Google Cloud Console
- Download the credentials JSON file
- Save it as `google_cred.json` in the project root
- Make sure the Translation API is enabled in your Google Cloud project

6. Apply database migrations:
```bash
python manage.py migrate
```

7. Create a superuser (optional):
```bash
python manage.py createsuperuser
```

8. Collect static files:
```bash
python manage.py collectstatic
```

9. Run the development server:
```bash
python manage.py runserver
```

The application will be available at http://127.0.0.1:8000/

## Usage

1. Upload a PDF:
   - Click "Upload PDF" in the navigation
   - Drag and drop a PDF file or click to choose
   - Wait for processing and translation

2. View translations:
   - Go to "PDF List"
   - Click "View Translations" for any document
   - See word-by-word translations with page numbers

3. User Profile:
   - Click on your username in the top-right corner
   - Select "Profile" from the dropdown
   - Update your personal information, profile photo, and language preferences
   - Change your password securely

## Word Frequency Analysis

The application handles duplicate words in the following ways:
- Words are stored with their page numbers and positions
- The UI shows frequency counts for repeated words
- Translations are cached to avoid redundant API calls
- Words are case-insensitive for better grouping

## Production Deployment

### Option 1: Docker Deployment

The easiest way to deploy BookLand is using Docker and Docker Compose:

1. Configure environment variables:
```bash
cp .env.example .env
```
Edit the `.env` file with your production settings.

2. Build and start the containers:
```bash
docker-compose up -d
```

3. Run migrations and create a superuser:
```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

### Option 2: Manual Deployment

For manual deployment to a production server:

1. Set up a production server (e.g., Ubuntu 22.04 LTS)

2. Install required system packages:
```bash
sudo apt update
sudo apt install python3-pip python3-venv postgresql nginx redis-server
```

3. Create a PostgreSQL database and user:
```bash
sudo -u postgres psql
postgres=# CREATE DATABASE bookland;
postgres=# CREATE USER bookland_user WITH PASSWORD 'your-password';
postgres=# ALTER ROLE bookland_user SET client_encoding TO 'utf8';
postgres=# ALTER ROLE bookland_user SET default_transaction_isolation TO 'read committed';
postgres=# ALTER ROLE bookland_user SET timezone TO 'UTC';
postgres=# GRANT ALL PRIVILEGES ON DATABASE bookland TO bookland_user;
postgres=# \q
```

4. Clone the repository and set up the application:
```bash
git clone <repository-url> /var/www/bookland
cd /var/www/bookland
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

5. Configure environment variables:
```bash
cp .env.example .env
```
Edit the `.env` file with your production settings.

6. Set up the production settings:
```bash
export DJANGO_SETTINGS_MODULE=bookland.settings_prod
```

7. Apply migrations and collect static files:
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

8. Set up Gunicorn as a systemd service:
```bash
sudo nano /etc/systemd/system/bookland.service
```

Add the following content:
```
[Unit]
Description=BookLand Gunicorn daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/bookland
ExecStart=/var/www/bookland/venv/bin/gunicorn --access-logfile - --workers 3 --bind unix:/var/www/bookland/bookland.sock bookland.wsgi_prod:application
Environment="DJANGO_SETTINGS_MODULE=bookland.settings_prod"
EnvironmentFile=/var/www/bookland/.env

[Install]
WantedBy=multi-user.target
```

9. Start and enable the Gunicorn service:
```bash
sudo systemctl start bookland
sudo systemctl enable bookland
```

10. Configure Nginx:
```bash
sudo nano /etc/nginx/sites-available/bookland
```

Add the following content:
```
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /var/www/bookland;
    }
    
    location /media/ {
        root /var/www/bookland;
    }
    
    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/bookland/bookland.sock;
    }
}
```

11. Enable the Nginx site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/bookland /etc/nginx/sites-enabled
sudo systemctl restart nginx
```

12. Set up SSL with Let's Encrypt:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### Option 3: Cloud Deployment

For deployment to cloud platforms:

#### AWS Elastic Beanstalk

1. Install the EB CLI:
```bash
pip install awsebcli
```

2. Initialize EB application:
```bash
eb init -p python-3.11 bookland
```

3. Create an environment and deploy:
```bash
eb create bookland-production
```

4. Configure environment variables:
```bash
eb setenv DJANGO_SETTINGS_MODULE=bookland.settings_prod DJANGO_SECRET_KEY=your-secret-key ...
```

#### Heroku

1. Install the Heroku CLI and log in:
```bash
heroku login
```

2. Create a Heroku app:
```bash
heroku create bookland-app
```

3. Add PostgreSQL add-on:
```bash
heroku addons:create heroku-postgresql:hobby-dev
```

4. Configure environment variables:
```bash
heroku config:set DJANGO_SETTINGS_MODULE=bookland.settings_prod DJANGO_SECRET_KEY=your-secret-key ...
```

5. Deploy the application:
```bash
git push heroku main
```

6. Run migrations:
```bash
heroku run python manage.py migrate
```

## Maintenance and Monitoring

### Backup Strategy

1. Database backups:
```bash
# For PostgreSQL
pg_dump -U bookland_user bookland > bookland_backup_$(date +%Y%m%d).sql
```

2. Media files backups:
```bash
tar -czf media_backup_$(date +%Y%m%d).tar.gz /var/www/bookland/media
```

3. Set up automated backups with cron:
```bash
crontab -e
```

Add:
```
0 2 * * * pg_dump -U bookland_user bookland > /path/to/backups/bookland_backup_$(date +%Y%m%d).sql
0 3 * * * tar -czf /path/to/backups/media_backup_$(date +%Y%m%d).tar.gz /var/www/bookland/media
```

### Monitoring

1. Set up Sentry for error tracking:
   - Create an account at sentry.io
   - Add your Sentry DSN to your environment variables
   - Errors will be automatically reported to Sentry

2. Set up server monitoring with tools like:
   - Prometheus + Grafana
   - New Relic
   - Datadog

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 