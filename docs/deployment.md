# Deployment Guide — FASL SOFI QDOTS

This guide covers production deployment of the FASL SOFI QDOTS FastAPI
application in three common environments:

1. **cPanel Passenger** (shared hosting, Python App manager)
2. **Uvicorn + Nginx** (VPS or bare-metal, reverse proxy)
3. **systemd** (process supervision under a `fasl-sofi` unit)

It also includes guidance on static asset caching, log rotation, and
post-deploy smoke tests using the `/health` and `/api/version`
endpoints.

> **Service slug:** `sofi` &nbsp;·&nbsp; **Port:** `8007` (see
> [CAOS_MANAGE port ledger](../../../\_Web\_Projects/CAOS_MANAGE/infrastructure/vps/hetzner-fasl-prod/README.md))

---

## 1. cPanel Passenger (Python App)

The repo ships `passenger_wsgi.py` that exposes `application = app.main:app`.
cPanel's "Setup Python App" feature reads this file automatically.

### 1.1 Create the Python App

In cPanel → **Setup Python App**:

| Field | Value |
|---|---|
| Python version | 3.12+ |
| Application root | `/home/<user>/apps/sofi` |
| Application URL | `sofi.<domain>` (or a path) |
| Application startup file | `passenger_wsgi.py` |
| Application entry point | `application` |
| Passenger log file | `/home/<user>/logs/sofi.log` |

### 1.2 Deploy source

```bash
cd ~/apps/sofi
git clone https://github.com/fsantibanezleal/FASL_SOFI_QDOTS.git .
source /home/<user>/virtualenv/apps/sofi/3.12/bin/activate
pip install -r requirements.txt
```

### 1.3 Restart

Hit **Restart** in the Python App manager, or `touch tmp/restart.txt` at the
app root.

### 1.4 Smoke test

```bash
curl -s https://sofi.<domain>/health
# {"status":"ok","service":"FASL SOFI QDOTS","version":"2.0.0"}

curl -s https://sofi.<domain>/api/version
# {"version":"2.0.0","service":"FASL SOFI QDOTS"}
```

### 1.5 Passenger notes

- Passenger handles ASGI protocol negotiation automatically when the startup
  file is `passenger_wsgi.py` and the callable resolves to a FastAPI app.
- WebSocket (`/ws`) support depends on the cPanel server's Passenger build.
  If the upgrade handshake fails, fall back to polling or move the
  WebSocket-heavy frontend routes behind the Nginx deployment below.

---

## 2. Uvicorn + Nginx (VPS)

For any non-shared environment, run Uvicorn directly behind Nginx. This
is the preferred topology for production: it gives you clean WebSocket
support, clear process ownership, and per-endpoint log separation.

### 2.1 Install

```bash
sudo useradd -r -s /usr/sbin/nologin fasl-sofi
sudo mkdir -p /opt/fasl-sofi
sudo chown fasl-sofi:fasl-sofi /opt/fasl-sofi
sudo -u fasl-sofi git clone https://github.com/fsantibanezleal/FASL_SOFI_QDOTS.git /opt/fasl-sofi
sudo -u fasl-sofi python3.12 -m venv /opt/fasl-sofi/.venv
sudo -u fasl-sofi /opt/fasl-sofi/.venv/bin/pip install -r /opt/fasl-sofi/requirements.txt
```

### 2.2 Run Uvicorn

Bind to `127.0.0.1:8007` so only Nginx can reach it:

```bash
sudo -u fasl-sofi /opt/fasl-sofi/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8007 --workers 2 --proxy-headers
```

### 2.3 Nginx server block

```nginx
server {
    listen 443 ssl http2;
    server_name sofi.fasl-work.com;

    ssl_certificate     /etc/letsencrypt/live/sofi.fasl-work.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sofi.fasl-work.com/privkey.pem;

    # ----- Static assets (served by Uvicorn, but cache aggressively) -----
    location /static/ {
        proxy_pass http://127.0.0.1:8007;
        proxy_set_header Host $host;
        expires 7d;
        add_header Cache-Control "public, max-age=604800, immutable";
    }

    # ----- WebSocket upgrade for /ws -----
    location /ws {
        proxy_pass http://127.0.0.1:8007;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # ----- Everything else (REST API + SPA) -----
    location / {
        proxy_pass http://127.0.0.1:8007;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 200m;    # TIFF stacks can be large
    }

    # ----- Health probes (bypass upstream logs) -----
    location = /health {
        proxy_pass http://127.0.0.1:8007;
        access_log off;
    }
}
```

Reload:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 3. systemd unit template

Save as `/etc/systemd/system/fasl-sofi.service`:

```ini
[Unit]
Description=FASL SOFI QDOTS (FastAPI + Uvicorn, port 8007)
After=network.target

[Service]
Type=simple
User=fasl-sofi
Group=fasl-sofi
WorkingDirectory=/opt/fasl-sofi
Environment="PATH=/opt/fasl-sofi/.venv/bin"
ExecStart=/opt/fasl-sofi/.venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 --port 8007 --workers 2 --proxy-headers \
    --log-level info
Restart=on-failure
RestartSec=5s

# Hardening
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fasl-sofi
sudo systemctl status fasl-sofi
```

### 3.1 Log rotation

Uvicorn logs to stdout/stderr → journald. To archive them:

```bash
sudo journalctl -u fasl-sofi --since "yesterday" > /var/log/fasl-sofi.$(date +%F).log
```

Or add a `/etc/logrotate.d/fasl-sofi` rule if you redirect logs to a file
via `StandardOutput=append:/var/log/fasl-sofi.log`.

---

## 4. Static asset caching

Static files under `app/static/` are served by the FastAPI mount
`/static`. In the Nginx block above the `expires 7d` + `Cache-Control:
public, max-age=604800, immutable` directives let browsers cache JS/CSS
for a week. For hash-busted assets bump the version suffix in the
filename to invalidate caches.

For dev parity, Uvicorn already sends ETags on `StaticFiles` responses —
no extra config needed.

---

## 5. Post-deploy smoke tests

After each deploy, run these three probes:

```bash
# 1. Liveness
curl -fsS https://sofi.<domain>/health

# 2. Version pin
curl -fsS https://sofi.<domain>/api/version

# 3. REST round-trip (simulate -> process)
curl -fsS -X POST https://sofi.<domain>/api/simulate \
  -H 'content-type: application/json' \
  -d '{"num_frames":60,"image_size":32,"num_emitters":4,"seed":42}' | head -c 200
```

The API test suite covers these flows end-to-end:

```bash
python -m pytest tests/test_api.py -v
```

---

## 6. Cross-references

- [System Architecture](architecture.md) — runtime component diagram
- [User Guide](user_guide.md) — operator workflows once deployed
- [CAOS_MANAGE deployments/sofi.md](../../../\_Web\_Projects/CAOS_MANAGE/deployments/sofi.md) — environment-specific secrets and host notes
- [CAOS_MANAGE VPS ledger](../../../\_Web\_Projects/CAOS_MANAGE/infrastructure/vps/hetzner-fasl-prod/README.md) — global port + service ownership
