# Production Configuration Backups

This directory stores backups of production configuration files from `root@project-kaleidoscope.tech`.

## Directory Structure

```
production-configs/
└── {timestamp}/
    ├── .env                    # Environment variables
    ├── nginx.conf             # Nginx configuration
    ├── nginx/                 # Nginx directory (if exists)
    │   └── nginx.conf
    ├── certbot/               # SSL certificates (if backed up)
    ├── docker-compose.prod.yml # Docker Compose file (if exists)
    ├── file_listing.txt       # List of files on server
    └── BACKUP_MANIFEST.txt    # Backup metadata
```

## Usage

### Backup Production Configs

```bash
cd kaleidoscope-ai
./scripts/deployment/backup-production-configs.sh
```

This will:

- Connect to `root@project-kaleidoscope.tech`
- Backup `.env`, `nginx/nginx.conf`, certbot certificates
- Save everything to `production-configs/{timestamp}/`

### Restore from Backup

```bash
cd kaleidoscope-ai
./scripts/deployment/setup-production.sh {timestamp}
```

Example:

```bash
./scripts/deployment/setup-production.sh 20250115_143022
```

### Fresh Setup

```bash
cd kaleidoscope-ai
./scripts/deployment/setup-production.sh
```

This will set up a fresh environment (you'll need to provide `.env` and `nginx.conf` manually if not restoring from backup).

## Important Notes

- **Never commit `.env` files** - They contain sensitive credentials
- **Backup before making changes** - Always run backup script before deployment
- **Certbot certificates** - May need manual restoration to Docker volumes
- **SSH Access** - Scripts require SSH access to production server

## Security

All backups contain sensitive information:

- Database credentials
- API keys
- JWT secrets
- SSL certificates

Keep this directory secure and never commit it to version control.
