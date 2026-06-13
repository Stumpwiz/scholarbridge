# ScholarBridge AWS Pilot Deployment Runbook (EC2 + Local PostgreSQL)

## 1. Scope

This runbook is for a small pilot deployment on AWS with:

- one ARM64 EC2 instance (recommended: `t4g.small`)
- PostgreSQL on the same instance
- Flask behind Gunicorn + Nginx
- DNS via IONOS CNAME to AWS, matching the existing `clerk.example.org` pattern
- HTTPS handled with the same mechanism used for `clerk.example.org`
- nightly backups retained for 30 days

This is intentionally a pilot setup, not a scaled production architecture.

## 1.1 Fixed Pilot Deployment Facts

- AWS Region: `us-east-1`
- Instance Type: `t4g.small`
- OS: `Ubuntu Server 24.04 LTS ARM64`
- Security Group: `scholarbridge-pilot`
- Deployment Model: `EC2 + local PostgreSQL + Gunicorn + Nginx`

## 1.2 Deployment Milestone Record (2026-06-12)

Deployment completed successfully on 2026-06-12.

- Public URL: `https://scholarbridge.example.org`
- Elastic IP configured
- DNS configured through IONOS
- HTTPS enabled and validated
- Automatic certificate renewal enabled
- Nightly PostgreSQL backups configured
- 30-day backup retention configured
- Deployed-environment validation completed:
  - login
  - partner management
  - contact management
  - campaign workflow
  - solicitation letter generation
  - PDF generation
  - PDF download

## 2. Prerequisites

Before starting, confirm:

- AWS account access with permissions to manage EC2, networking, and related resources.
- IONOS DNS access for `example.org` record management.
- SSH key access for the EC2 instance.
- GitHub repository access for ScholarBridge.
- Working familiarity with PostgreSQL administration basics (`psql`, `pg_dump`, `pg_restore`).
- `sudo` privileges on the EC2 instance.

## 3. Deployment Execution Map

```text
AWS CONSOLE
  -> SSH to EC2
  -> POSTGRESQL SHELL (psql) setup
  -> EC2 INSTANCE (SSH SESSION) application deployment
  -> EC2 INSTANCE (SSH SESSION) Nginx/systemd setup
  -> IONOS DNS CONSOLE configuration
  -> WEB BROWSER VALIDATION smoke tests
  -> EC2 INSTANCE (SSH SESSION) backup configuration
```

## 4. Target Architecture

```text
Internet
  -> HTTPS endpoint for scholarbridge.example.org (same TLS mechanism as clerk.example.org)
  -> EC2 ARM64 (Amazon Linux 2023 or Ubuntu 24.04)
     -> Nginx (reverse proxy on :80 local host)
     -> Gunicorn (127.0.0.1:8000)
     -> Flask app (run:app)
     -> PostgreSQL local (127.0.0.1:5432)
```

## 5. Infrastructure Provisioning

### 5.1 Create EC2 and Network Baseline

**Execution Context: AWS CONSOLE**

1. Launch one ARM64 EC2 instance in `us-east-1` using instance type `t4g.small`.
2. Use OS image `Ubuntu Server 24.04 LTS ARM64`.
3. Attach security group `scholarbridge-pilot`.
4. Attach or allocate networking that matches your existing pilot approach (public reachability and SSH access pattern).
5. Record the public hostname/IP that IONOS CNAME will point to.
6. Ensure SSH access works with your deployment key before proceeding.

## 6. Required Secrets and Environment

Create `/etc/scholarbridge/scholarbridge.env` from `.env.production.example`.

Required:

- `SECRET_KEY`: must be explicitly set to a strong random value.
- `DATABASE_URL`: must point to PostgreSQL, not SQLite.

Recommended minimum file:

```dotenv
APP_NAME=ScholarBridge
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=<strong-random-secret>
DATABASE_URL=postgresql+psycopg://scholarbridge_app:<password>@127.0.0.1:5432/scholarbridge
SQLITE_DATABASE_URL=sqlite:///instance/scholarbridge.db
```

## 7. Base Instance Setup

### 7.1 Install OS Packages (Ubuntu 24.04 ARM64 example)

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
sudo apt update
sudo apt install -y \
  python3.12 python3.12-venv python3-pip \
  postgresql postgresql-client \
  nginx git curl unzip \
  texlive-xetex texlive-latex-extra texlive-fonts-recommended
```

### 7.2 Install uv

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 7.3 Create Service User and Directories

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
sudo useradd --system --create-home --shell /bin/bash scholarbridge || true
sudo mkdir -p /opt/scholarbridge /etc/scholarbridge /var/backups/scholarbridge/{postgres,files}
sudo chown -R scholarbridge:scholarbridge /opt/scholarbridge /etc/scholarbridge /var/backups/scholarbridge
```

### 7.4 Checkout Application and Install Python Dependencies

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
sudo -u scholarbridge git clone <github-repo-url> /opt/scholarbridge
cd /opt/scholarbridge
sudo -u scholarbridge uv venv .venv
sudo -u scholarbridge uv sync
sudo -u scholarbridge /opt/scholarbridge/.venv/bin/pip install gunicorn
```

### 7.5 Configure Local PostgreSQL User and Database

Start `psql`:

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
sudo -u postgres psql
```

Then run:

**Execution Context: POSTGRESQL SHELL (psql)**

```sql
CREATE USER scholarbridge_app WITH PASSWORD '<strong-db-password>';
CREATE DATABASE scholarbridge OWNER scholarbridge_app;
```

### 7.6 Create Production Environment File

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
sudo cp /opt/scholarbridge/.env.production.example /etc/scholarbridge/scholarbridge.env
sudo chmod 640 /etc/scholarbridge/scholarbridge.env
sudo chown scholarbridge:scholarbridge /etc/scholarbridge/scholarbridge.env
sudoedit /etc/scholarbridge/scholarbridge.env
```

## 8. Migrations and Data Load

All commands below run from `/opt/scholarbridge` as `scholarbridge`, unless noted otherwise.

### 8.1 Run Alembic Migrations

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
cd /opt/scholarbridge
set -a
source /etc/scholarbridge/scholarbridge.env
set +a

uv run flask --app run.py db upgrade
```

### 8.2 Data Migration Option A (preferred): pg_dump / pg_restore from current PostgreSQL

On source machine (already-migrated PostgreSQL):

**Execution Context: LOCAL DEVELOPMENT MACHINE (Development Host)**

```bash
pg_dump -h <source-host> -U <source-user> -d <source-db> -F c -f scholarbridge_pilot.dump
```

Copy dump artifact to EC2:

**Execution Context: LOCAL DEVELOPMENT MACHINE (Development Host)**

```bash
scp scholarbridge_pilot.dump <ec2-user>@<ec2-host>:/tmp/
```

Restore dump on EC2:

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
pg_restore -h 127.0.0.1 -U scholarbridge_app -d scholarbridge --clean --if-exists /tmp/scholarbridge_pilot.dump
```

### 8.3 Data Migration Option B: SQLite -> PostgreSQL script

If you must migrate directly from SQLite on target:

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
cd /opt/scholarbridge
set -a
source /etc/scholarbridge/scholarbridge.env
set +a

SCHOLARBRIDGE_ALLOW_DATA_MUTATION=1 \
uv run python scripts/migrate_sqlite_to_postgres.py \
  --source-sqlite-url sqlite:///instance/scholarbridge.db \
  --target-postgres-url "$DATABASE_URL" \
  --truncate-target \
  --allow-data-mutation
```

## 9. Gunicorn + systemd

Install service file:

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
sudo cp /opt/scholarbridge/deploy/scholarbridge.service /etc/systemd/system/scholarbridge.service
sudo systemctl daemon-reload
sudo systemctl enable scholarbridge.service
sudo systemctl start scholarbridge.service
sudo systemctl status scholarbridge.service
```

Logs:

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
journalctl -u scholarbridge.service -n 200 --no-pager
```

## 10. Nginx Reverse Proxy

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
sudo cp /opt/scholarbridge/deploy/nginx-scholarbridge.conf /etc/nginx/sites-available/scholarbridge
sudo ln -sf /etc/nginx/sites-available/scholarbridge /etc/nginx/sites-enabled/scholarbridge
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
```

## 11. DNS and HTTPS

### 11.1 Create or Update DNS Record

**Execution Context: IONOS DNS CONSOLE**

1. Create/confirm CNAME `scholarbridge.example.org` to the AWS endpoint, mirroring the working `clerk.example.org` pattern.

### 11.2 Configure HTTPS

**Execution Context: AWS CONSOLE and/or EC2 INSTANCE (SSH SESSION)**

1. Apply the same HTTPS mechanism currently used for `clerk.example.org`.
2. Ensure the certificate is attached/active for `scholarbridge.example.org` using that existing mechanism.

## 12. Backup and Restore (30-day retention)

### 12.1 Backup Script

Use `scripts/backup_postgres.sh` to produce:

- `postgres/*.sql.gz` (PostgreSQL logical dump via `pg_dump | gzip`)
- `files/*.tar.gz` (generated letters and avatar uploads, if present)

Run manually:

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
sudo -u scholarbridge /opt/scholarbridge/scripts/backup_postgres.sh /etc/scholarbridge/backup.env
```

Example `/etc/scholarbridge/backup.env`:

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```dotenv
DB_NAME=scholarbridge
DB_USER=scholarbridge_app
DB_HOST=127.0.0.1
DB_PORT=5432
BACKUP_ROOT=/var/backups/scholarbridge
RETENTION_DAYS=30
APP_ROOT=/opt/scholarbridge
```

### 12.2 Daily Schedule (cron)

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
sudo crontab -u scholarbridge -e
```

Add:

```cron
15 2 * * * /opt/scholarbridge/scripts/backup_postgres.sh /etc/scholarbridge/backup.env >> /var/log/scholarbridge-backup.log 2>&1
```

### 12.3 Restore Script

**Execution Context: EC2 INSTANCE (SSH SESSION)**

```bash
sudo -u scholarbridge /opt/scholarbridge/scripts/restore_postgres.sh /var/backups/scholarbridge/postgres/<backup-file>.sql.gz /etc/scholarbridge/backup.env
```

## 13. Smoke Test Checklist

### 13.1 Service and Health Endpoint Checks

**Execution Context: EC2 INSTANCE (SSH SESSION)**

1. Verify service startup:
   - `systemctl status scholarbridge`
   - `curl -i http://127.0.0.1:8000/health`

### 13.2 Browser Workflow Validation

**Execution Context: WEB BROWSER VALIDATION**

1. Open app URL and confirm login page loads.
2. Confirm login works with pilot user account.
3. Confirm Partners page loads.
4. Confirm Partner detail and contact section load.
5. Confirm solicitation letter generation succeeds (PDF created and viewable).

### 13.3 Backup Validation

**Execution Context: EC2 INSTANCE (SSH SESSION)**

1. Run backup script once.
2. Verify newest `.sql.gz` exists and is non-zero size.
3. Verify file backup archive exists if generated letters or avatar uploads exist.

## 14. Rollback Notes

If deployment fails:

**Execution Context: EC2 INSTANCE (SSH SESSION)**

1. Keep current backup artifacts untouched.
2. Revert app code to previous known-good git tag/commit.
3. Re-run `uv sync` and `flask db upgrade` for that version.
4. Restart services:
   - `sudo systemctl restart scholarbridge`
   - `sudo systemctl restart nginx`
5. If database state is bad, restore the most recent `.sql.gz` backup with `scripts/restore_postgres.sh`.
6. Re-run smoke tests before reopening pilot access.

## 15. Pilot Operations Notes

- Keep this deployment single-node and simple for pilot period.
- Revisit architecture (managed DB, object storage, HA) only after pilot feedback and usage confirms need.
