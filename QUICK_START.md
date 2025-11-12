# Quick Start Guide - Production Deployment

## First Time Setup

### Step 1: Backup Existing Configs (if any)

```bash
cd kaleidoscope-ai
./scripts/deployment/backup-production-configs.sh
```

### Step 2: Set Up Production

```bash
# Fresh setup
./scripts/deployment/setup-production.sh

# OR restore from backup
./scripts/deployment/setup-production.sh 20250115_143022
```

## Regular Deployment Workflow

### When You Push Code Changes:

1. **Code is pushed** → GitHub Actions automatically builds and pushes images to Docker Hub
2. **Deploy to production**:
   ```bash
   cd kaleidoscope-ai
   ./scripts/deployment/deploy-production.sh
   ```

That's it! The script will:

- Pull latest images from Docker Hub
- Restart services gracefully
- Perform health checks
- Show service status

## Verify Deployment

```bash
# Check service status
ssh root@project-kaleidoscope.tech 'cd ~/kaleidoscope && docker-compose -f docker-compose.prod.yml ps'

# View logs
ssh root@project-kaleidoscope.tech 'cd ~/kaleidoscope && docker-compose -f docker-compose.prod.yml logs -f'

# Test backend
ssh root@project-kaleidoscope.tech 'curl http://localhost:8080/actuator/health'
```

## Troubleshooting

### Services won't start

```bash
# Check logs
ssh root@project-kaleidoscope.tech 'cd ~/kaleidoscope && docker-compose -f docker-compose.prod.yml logs'

# Check .env file exists
ssh root@project-kaleidoscope.tech 'ls -la ~/kaleidoscope/.env'
```

### Images not found

- Verify CI/CD workflow completed successfully
- Check Docker Hub: https://hub.docker.com/u/shishir01
- Verify images exist: `docker pull shishir01/kaleidoscope-content_moderation:latest`

### Restore from backup

```bash
./scripts/deployment/setup-production.sh {backup_timestamp}
```

## Important Files

- **docker-compose.prod.yml** - Unified production compose file
- **.env** - Environment variables (on server, not in repo)
- **nginx/nginx.conf** - Nginx configuration (on server)

## Need Help?

See detailed documentation:

- `scripts/deployment/README.md` - Script documentation
- `DEPLOYMENT_SETUP.md` - Complete setup guide
