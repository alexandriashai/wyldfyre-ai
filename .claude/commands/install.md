# Wyld Fyre AI Installation Assistant

You are helping the user install Wyld Fyre AI on their server. This is a multi-agent AI infrastructure system that requires several services to be set up.

## Pre-Installation Assessment

Before proceeding with installation, you must run a pre-flight check to assess the server state. Run the script:

```bash
bash infrastructure/scripts/preflight-check.sh
```

This will analyze:
- Existing services (PostgreSQL, Redis, Nginx, Docker)
- Port availability (3000, 5432, 6333, 6379, 8000, 8001, 9090, 3001, 3100)
- Disk space and memory
- Existing data that might conflict
- Environment configuration

## Installation Decision Tree

Based on the pre-flight check results:

### Scenario 1: Clean Server (Recommended)
If no conflicting services are found, proceed with full installation.

### Scenario 2: Existing Services Detected
Ask the user:
1. **Merge**: Keep existing services (PostgreSQL, Redis) and configure Wyld Fyre to use them
2. **Parallel**: Run Wyld Fyre services alongside existing ones (different ports)
3. **Replace**: Backup and replace existing services (data loss risk)

### Scenario 3: Partial Installation Exists
If a previous Wyld Fyre installation is detected:
1. **Upgrade**: Keep data, update code and configs
2. **Fresh**: Backup data, clean install
3. **Reset**: Complete reset (all data will be lost)

## Installation Steps

Once you've assessed the server and confirmed the approach with the user, follow these steps:

### Step 1: Clone Repository (if not already cloned)
```bash
git clone https://github.com/alexandriashai/AI-Infrastructure.git
cd AI-Infrastructure
```

### Step 2: Run Pre-flight Check
```bash
bash infrastructure/scripts/preflight-check.sh
```
Review results with user and decide on installation approach.

### Step 3: Configure Environment
```bash
cp .env.example .env
# Then help user fill in required values
```

Required environment variables:
- `ANTHROPIC_API_KEY` - For Claude AI agents
- `OPENAI_API_KEY` - For embeddings and speech services
- `POSTGRES_PASSWORD` - Database password
- `REDIS_PASSWORD` - Cache password
- `JWT_SECRET` - Authentication secret

Optional but recommended:
- `CLOUDFLARE_API_KEY` - For DNS management
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` - For secrets management
- `GITHUB_PAT` - For agent Git operations

### Step 4: Run Installer
```bash
bash infrastructure/scripts/install.sh
```

### Step 5: Verify Installation
```bash
bash infrastructure/scripts/verify-install.sh
```

### Step 6: Initialize Database
```bash
docker-compose exec api python -m alembic upgrade head
docker-compose exec api python scripts/seed-db.py
```

### Step 7: Start Services
```bash
docker-compose up -d
```

## Post-Installation

After successful installation:
1. Access web portal at http://localhost:3000
2. Create admin account
3. Configure agents in the dashboard
4. Test agent communication

## Troubleshooting

Common issues and solutions:

### Port Conflicts
If ports are in use, either stop conflicting services or modify `docker-compose.yml` port mappings.

### Permission Errors
Ensure docker permissions: `sudo usermod -aG docker $USER`

### Memory Issues
The system requires minimum 16GB RAM. If low on memory, reduce agent count in config.

### Database Connection Issues
Check PostgreSQL is running: `docker-compose logs db`

## Important Notes

- Always backup existing data before making changes
- The installation process is non-destructive by default
- Use `--force` flag only when you explicitly want to overwrite
- Check logs at `/var/log/wyld-fyre/` for detailed troubleshooting
