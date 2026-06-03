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

`FEISHU_EVENT_MODE=websocket` uses the official Feishu/Lark SDK long connection
for message events, so the app does not need a public webhook URL for `@ bot`
triggers. Bitable change events can still use the old webhook endpoint:

- `websocket`: message events use the SDK long connection; message webhooks are skipped.
- `webhook`: public callback URL only; useful when you do not want SDK connections.
- `both`: enable both receivers. Avoid this unless you intentionally want both,
  because the same event can be received twice if both are configured in Feishu.

Start the app:

```bash
docker compose up -d --build
docker compose ps
```

Open:

```text
http://127.0.0.1:8088
```

Health check:

```bash
curl http://127.0.0.1:8088/api/health
```

When the server already hosts other projects, keep host Nginx on ports 80/443
and proxy the Feishu management domain to this app:

```nginx
server {
    listen 80;
    server_name your-feishu-domain.example.com;

    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
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
