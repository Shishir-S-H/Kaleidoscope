# Monitoring Scripts

**Scripts for monitoring and health checking Kaleidoscope AI services**

---

## Scripts

### `monitor_services.sh`

Health check script for all Kaleidoscope AI services.

**Usage**:
```bash
./scripts/monitoring/monitor_services.sh
```

**What it checks**:
- Redis connectivity
- Elasticsearch health
- Docker services status
- Service logs (recent errors)

---

## Related Documentation

- **Troubleshooting**: [../../docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md)
- **Deployment**: [../deployment/README.md](../deployment/README.md)

