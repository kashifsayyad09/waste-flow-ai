# WasteFlow AI — AWS deployment (Amazon Linux)

```
Browser ──HTTP──▶ Frontend EC2 (Nginx :80) ──/api/, /health──▶ Backend EC2 (Uvicorn :8000) ──TCP 3306──▶ RDS MySQL
                  serves the Vite build                         systemd service                          private
```

Three separate resources. Nothing here creates AWS resources for you; you create them in the console (or your own tooling) and use the files in this folder.

| File | Goes to |
|---|---|
| `nginx/wasteflow-frontend.conf.template` | Frontend EC2 → `/etc/nginx/conf.d/wasteflow.conf` (rendered by the script) |
| `frontend/deploy-frontend.sh`, `rollback-frontend.sh` | Frontend EC2 |
| `backend/wasteflow-backend.service` | Backend EC2 → `/etc/systemd/system/` |
| `backend/backend.env.example` | Backend EC2 → `/etc/wasteflow/backend.env` (real values, never committed) |
| `backend/deploy-backend.sh`, `rollback-backend.sh` | Backend EC2 |
| `sql/verify.sql` | Read-only database checks |

**Placeholders you must fill in** (nothing here is a real value): `<FRONTEND_SG>`, `<BACKEND_SG>`, `<RDS_SG>`, `<BACKEND_PRIVATE_IP_OR_DNS>`, `<FRONTEND_PRIVATE_IP>`, `<FRONTEND_PUBLIC_DNS_OR_DOMAIN>`, `<RDS_ENDPOINT>`, `<RDS_APP_USER>`, `<RDS_APP_PASSWORD>`, `<YOUR_ADMIN_IP>`.

## 0. Check the OS on BOTH instances first

```
cat /etc/os-release
```

- **Amazon Linux 2023 (`ID="amzn"`, `VERSION_ID="2023"`)**: supported by everything below (`dnf`).
- **Amazon Linux 2 (`VERSION_ID="2"`)**: **not supported here.** The backend needs Python 3.10+ (it uses `X | None` types), AL2 ships older Python, and AWS's end-of-support date for AL2 (30 June 2026 when this was written) has passed. Launch AL2023 instead.

## 1. Network and security groups

Create three security groups in the same VPC.

| Security group | Inbound | Outbound (minimum) |
|---|---|---|
| `<FRONTEND_SG>` | TCP **80** (and 443 once TLS is set up) from `0.0.0.0/0`. **No SSH**: use SSM Session Manager, or TCP 22 from `<YOUR_ADMIN_IP>/32` only | TCP 8000 to `<BACKEND_SG>`; 443 for packages |
| `<BACKEND_SG>` | TCP **8000** from `<FRONTEND_SG>` only. No SSH (SSM) | TCP 3306 to `<RDS_SG>`; 443 for packages / RDS CA download |
| `<RDS_SG>` | TCP **3306** from `<BACKEND_SG>` only | none needed |

Rules that must hold: nothing is open to the internet except 80/443 on the frontend; **8000 and 3306 are never public**; RDS has **Publicly accessible = No** and sits in private subnets (a DB subnet group with private subnets).

The backend instance needs outbound internet only to install packages (NAT gateway, or a public subnet with no inbound rules). It does not need a public IP to serve traffic.

## 2. RDS MySQL

Preserve the existing instance/schema. If you are creating it fresh: engine **MySQL 8.x**, Publicly accessible **No**, security group `<RDS_SG>`, initial database `wasteflow`, encryption at rest on, automated backups on, deletion protection on.

Create a least-privilege application user (run once as the master user, from the backend EC2, see step 3):

```sql
CREATE USER '<RDS_APP_USER>'@'%' IDENTIFIED BY '<RDS_APP_PASSWORD>';
GRANT SELECT, UPDATE ON wasteflow.bins TO '<RDS_APP_USER>'@'%';
GRANT SELECT, INSERT ON wasteflow.collection_records TO '<RDS_APP_USER>'@'%';
```

The application never runs DDL, so it needs no `CREATE/ALTER/DROP`. Import `schema.sql` once with the **master** user (it is additive and never drops data):

```
mysql -h <RDS_ENDPOINT> -P 3306 -u <MASTER_USER> -p --ssl-ca=/etc/wasteflow/certs/global-bundle.pem wasteflow < schema.sql
```

Run `deploy/sql/verify.sql` (read-only) to confirm tables, foreign key and row counts.

## 3. Backend EC2 (Amazon Linux 2023)

```
cat /etc/os-release
sudo dnf install -y git python3.11 python3.11-pip mariadb105     # mariadb105 = mysql CLI client only
python3.11 --version                                             # must be 3.10+
```

(If `python3.11` is unavailable, run `dnf list available 'python3*'` and use any 3.10+ package; set `PYTHON=python3.x` for the deploy script.)

Service user, config directories and the RDS CA bundle:

```
sudo useradd --system --home /opt/wasteflow --shell /sbin/nologin wasteflow
sudo install -d -o wasteflow -g wasteflow /opt/wasteflow /opt/wasteflow/releases
sudo install -d -m 0750 -o root -g wasteflow /etc/wasteflow /etc/wasteflow/certs
sudo curl -fsSL -o /etc/wasteflow/certs/global-bundle.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
sudo chmod 0644 /etc/wasteflow/certs/global-bundle.pem
```

Protected configuration (edit with real values; the password is typed into the file, never on a command line):

```
sudo cp deploy/backend/backend.env.example /etc/wasteflow/backend.env
sudo chown root:wasteflow /etc/wasteflow/backend.env && sudo chmod 0640 /etc/wasteflow/backend.env
sudo nano /etc/wasteflow/backend.env
```

`APP_ENV=production` makes the backend **refuse to start the database connection without `DB_SSL_CA`**, so the RDS certificate and hostname are always verified. Wrap values containing `$`, `#` or spaces in single quotes.

*Alternative: AWS Secrets Manager.* Attach an instance role allowing `secretsmanager:GetSecretValue` on one secret, then generate the env file at boot (not tested in this repo):

```
umask 077; aws secretsmanager get-secret-value --secret-id <SECRET_ID> --query SecretString --output text > /etc/wasteflow/backend.env
```

Install the service and deploy:

```
sudo cp deploy/backend/wasteflow-backend.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable wasteflow-backend
git clone <YOUR_REPO_URL> ~/waste-flow-ai && cd ~/waste-flow-ai
sudo bash deploy/backend/deploy-backend.sh
```

The script builds an immutable release with its own virtualenv, runs the unit tests, switches `/opt/wasteflow/current`, restarts the service, waits for `/health`, and **automatically switches back** if the new release is not healthy.

Verify on the backend:

```
systemctl status wasteflow-backend --no-pager
sudo journalctl -u wasteflow-backend -n 50 --no-pager
curl -s http://127.0.0.1:8000/health          # {"status":"ok","database":"connected",...}
curl -s http://127.0.0.1:8000/api/v1/priorities | head -c 300
ss -ltnp | grep 8000
```

## 3b. Phase 3 on the backend EC2: MCP server and AI configuration

The MCP server runs **on this same instance**, bound to `127.0.0.1:8001`. No security-group rule is needed for it, and the frontend Nginx never proxies it. See [`docs/phase3-ai.md`](../docs/phase3-ai.md).

1. Backend security group: allow **outbound TCP 443** to `api.groq.com` (NAT gateway or public subnet).
2. Create a **SELECT-only** database user for MCP (as the master user): `CREATE USER '<RDS_READONLY_USER>'@'%' IDENTIFIED BY '<RDS_READONLY_PASSWORD>'; GRANT SELECT ON wasteflow.* TO '<RDS_READONLY_USER>'@'%';`
3. Generate the shared token once: `python3.11 -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. Add the Phase 3 variables (`GROQ_*`, `MCP_SERVER_URL`, `MCP_API_TOKEN`) to `/etc/wasteflow/backend.env`, and create `/etc/wasteflow/mcp.env` from `deploy/backend/mcp.env.example` with the **same** `MCP_API_TOKEN` (both files: `root:wasteflow`, mode `0640`).
5. Install the service: `sudo cp deploy/backend/wasteflow-mcp.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable wasteflow-mcp`.
6. Deploy as usual (`sudo bash deploy/backend/deploy-backend.sh`). It now ships `mcp-server/`, runs both unit-test suites, restarts MCP before the backend, and rolls both back if `/health` fails.
7. Verify (on the backend EC2):

```
systemctl status wasteflow-mcp --no-pager
ss -ltn | grep 8001                                   # must show 127.0.0.1:8001, never 0.0.0.0
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8001/mcp   # 401 without the token
curl -s http://127.0.0.1:8000/api/v1/ai/status        # which AI features are configured
cd ~/waste-flow-ai/backend && .venv/bin/python scripts/check_groq.py --live    # your real Groq account
```

Rollback: `rollback-backend.sh` switches both services to the previous release. The AI features are optional; leaving the Groq variables unset disables them without affecting anything else.

The production Nginx template already routes `/api/v1/ai/` with a 5 MB upload limit and a 90 s read timeout (the rest of the site keeps the 1 MB limit); re-run `deploy-frontend.sh` to install it.

## 4. Frontend EC2 (Amazon Linux 2023)

```
cat /etc/os-release
sudo dnf install -y git nginx
sudo systemctl enable --now nginx
node -v && npm -v          # needs Node ^20.19 or >=22.12 (Vite 8). Check: dnf list available 'nodejs*'
```

If the repository's Node is too old, either install a newer Node or **build elsewhere** (laptop/CI: `cd frontend && npm ci && npm run build`), copy `frontend/dist/` to the instance, and run the deploy script with `SKIP_BUILD=yes DIST_DIR=/path/to/dist`.

The stock `/etc/nginx/nginx.conf` has its own default `server` on port 80; our config declares `default_server`, so it takes precedence (no edits needed). If `nginx -t` complains, comment out the stock `server { ... }` block. If SELinux is enforcing, allow proxying: `sudo setsebool -P httpd_can_network_connect 1`.

Deploy (use the backend's **private** IP or private DNS name):

```
git clone <YOUR_REPO_URL> ~/waste-flow-ai && cd ~/waste-flow-ai
sudo -E env BACKEND_HOST=<BACKEND_PRIVATE_IP_OR_DNS> bash deploy/frontend/deploy-frontend.sh
```

It builds, installs an immutable release under `/var/www/wasteflow/releases/`, renders `/etc/nginx/conf.d/wasteflow.conf`, runs `nginx -t`, switches the `current` symlink atomically and reloads Nginx. On any error it restores the previous release and config. It refuses `localhost`/`127.*` as the backend host.

Routing (all through the frontend's own origin, so the browser never sees the backend address): static files from `/var/www/wasteflow/current`; `/api/...` → `http://<backend>:8000/api/...` (path preserved, no duplicate prefix); `/health` → backend `/health`; any other path → `index.html` (SPA fallback). Swagger (`/docs`) is not exposed publicly.

HTTPS: not configured. Before real users, add TLS (a domain + Let's Encrypt/certbot on this instance, or an Application Load Balancer with an ACM certificate in front) and then open 443 in `<FRONTEND_SG>`.

## 5. End-to-end verification

From your machine (replace the host):

```
curl -s  http://<FRONTEND_PUBLIC_DNS_OR_DOMAIN>/health
curl -s  http://<FRONTEND_PUBLIC_DNS_OR_DOMAIN>/api/v1/bins | head -c 300
curl -s  http://<FRONTEND_PUBLIC_DNS_OR_DOMAIN>/api/v1/collection-plan | head -c 300
curl -sI http://<FRONTEND_PUBLIC_DNS_OR_DOMAIN>/some/spa/route      # 200, index.html
curl -m 5 http://<BACKEND_PUBLIC_OR_PRIVATE_IP>:8000/health          # must FAIL / time out from the internet
```

Then open the site in a browser and check the browser console for errors.

## 6. Rollback

| What | Command |
|---|---|
| Frontend build | `sudo bash deploy/frontend/rollback-frontend.sh` (previous release) or `... <release-name>`; releases are listed with `ls -t /var/www/wasteflow/releases` |
| Frontend Nginx config | Re-run the deploy from the previous git tag/commit (it re-renders the config), or restore your saved copy of `/etc/nginx/conf.d/wasteflow.conf`, then `sudo nginx -t && sudo systemctl reload nginx` |
| Backend version | `sudo bash deploy/backend/rollback-backend.sh` (previous release) or `... <release-name>`; the deploy script already rolls back by itself if `/health` fails |
| Service config | Restore `/etc/systemd/system/wasteflow-backend.service` and/or `/etc/wasteflow/backend.env` from your backup, `sudo systemctl daemon-reload && sudo systemctl restart wasteflow-backend` |
| Data | The application never alters tables. Restore only via an RDS snapshot / point-in-time restore if data itself is damaged. |

The last 5 releases are kept on each instance.

## 7. Rotate the exposed database password (do this before going live)

Treat the previously exposed password as compromised. Do **not** reuse it anywhere.

1. Generate a new strong password in a password manager.
2. RDS console → your instance → **Modify** → new master password → apply immediately (or `aws rds modify-db-instance --db-instance-identifier <ID> --master-user-password` with the value read from a protected prompt, not typed into history).
3. If you created an application user: `ALTER USER '<RDS_APP_USER>'@'%' IDENTIFIED BY '<NEW_PASSWORD>';`
4. Edit `/etc/wasteflow/backend.env` on the backend EC2 (and the Secrets Manager secret, if used), then `sudo systemctl restart wasteflow-backend` and check `/health`.
5. Remove the old password from anywhere it was pasted (chat logs, terminal history, notes, any local `.env` shared outside your machine). `history -c` is not enough for shared logs.
6. Check CloudTrail / RDS logs for unfamiliar connections during the exposure window.

## 8. CI/CD

The repository has no GitHub Actions workflows, and none were added. When you want them: run `npm ci && npm run typecheck && npm test && npm run build` and `pytest -m "not integration"` on each pull request; deploy over AWS SSM `SendCommand` using GitHub OIDC role assumption (no long-lived AWS keys); keep production deploys behind a manual approval.
