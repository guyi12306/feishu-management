# Docker deployment

## Server requirements

- Docker Engine
- Docker Compose plugin

## First deployment

```bash
cd /opt/feishu-management
cp deploy/production.env.example deploy/production.env
openssl rand -hex 32
```

Put the generated value into `SESSION_SECRET`, then set the admin password and any LLM or Feishu values.

Start the app:

```bash
docker compose up -d --build
docker compose ps
```

Open:

```text
http://154.64.230.23
```

Health check:

```bash
curl http://154.64.230.23/api/health
```

## Update deployment

```bash
cd /opt/feishu-management
git pull
docker compose up -d --build
```

## Data

SQLite data is stored in the `backend_data` Docker volume and survives container rebuilds.

## Stop

```bash
docker compose down
```
