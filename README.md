# WasteFlow AI — Complete AWS Rebuild & Operations Guide

> **Purpose:** Recreate the WasteFlow AI application from a fresh AWS account/VPC, or troubleshoot the existing deployment. This documents the **observed deployed topology** (three EC2 instances and two Application Load Balancers), which differs from some older repository deployment instructions. **Never commit real passwords, Groq API keys, MCP bearer tokens, or SSH private keys.**

**Repository:** https://github.com/kashifsayyad09/waste-flow-ai  
**Region used in original deployment:** `us-east-1`  
**Original public entry point (may change if resources are recreated):** `http://wasteflow-external-alb-751904982.us-east-1.elb.amazonaws.com`  
**Current TLS status:** HTTP only; configure ACM + HTTPS before production use.

## 1. What the application does

WasteFlow AI helps waste collection teams prioritize bins with an explainable **0–100** score. The priority engine is deterministic, not LLM-generated. The React dashboard displays bins and collection priorities; FastAPI exposes REST endpoints; MySQL stores bins and collection records. Groq-hosted AI supports chat and waste-image features, while a Model Context Protocol (MCP) server supplies application tools/data to the assistant. Route optimization with real GPS routing and live IoT sensors are **future improvements**, not prerequisites for this deployment.

**Components:** React 19 + TypeScript + Vite 8; Nginx; Python 3.11+ + FastAPI + Uvicorn; SQLAlchemy/PyMySQL; MySQL 8.x on Amazon RDS; MCP server; Groq API; Amazon EC2, VPC, security groups, and two ALBs.

## 2. Deployed architecture

```text
Internet / Browser
       |
       v
External internet-facing ALB :80 (wasteflow-external-alb)
       |
       v
Frontend EC2 :80 (Nginx, React static build)
       | /api/* and /health reverse proxy
       v
Internal ALB :80 (wasteflow-internal-alb)
       |
       v
Backend EC2 :8000 (FastAPI, wasteflow-backend.service)
       |                             \
       | TCP 3306                     \ MCP HTTP :8001
       v                               v
Amazon RDS MySQL                   MCP EC2 (read-only tools)
                                       |
                                       +--> RDS MySQL (read-only DB user)

Backend EC2 --> Groq API over outbound HTTPS :443
```

**Important:** The checked-in `deploy/README.md` describes a different/older deployment in which MCP shares the backend instance on `127.0.0.1:8001`, and its frontend script uses a direct backend host. The **actual deployed setup** has a separate MCP EC2 and frontend Nginx proxies to the **internal ALB**. Adjust those templates/scripts accordingly; do not blindly run them unchanged.

### Original deployment reference (not portable IDs)

| Resource | Original value |
|---|---|
| Frontend EC2 private IP | `10.0.2.80` |
| Backend EC2 private IP | `10.0.4.96` |
| MCP EC2 private IP | `10.0.5.89` |
| External ALB DNS | `wasteflow-external-alb-751904982.us-east-1.elb.amazonaws.com` |
| Internal ALB DNS | `internal-wasteflow-internal-alb-1557040077.us-east-1.elb.amazonaws.com` |
| Backend target group | `wasteflow-backend-tg` -> backend port `8000` |
| Frontend target group | `wasteflow-frontend-tg` -> frontend port `80` |
| RDS endpoint | `database-1.cojs2queopr9.us-east-1.rds.amazonaws.com` |
| Database name | `wasteflow` |
| Text model used in deployment | `openai/gpt-oss-20b` |
| Vision model used in deployment | `qwen/qwen3.8-27b` (confirm exact model ID and availability in your Groq account) |
| MCP URL in original topology | `http://10.0.5.89:8001/mcp` |

IPs, DNS names, security group IDs, model availability and instance IDs are **environment-specific**. Replace them when recreating resources. Use private DNS names or service discovery rather than hard-coded private IPs when possible.

## 3. Prerequisites

1. AWS account with permission to create VPC, subnets, EC2, ALBs, target groups, security groups, RDS, and IAM roles.
2. One VPC with subnets across **at least two Availability Zones** for ALBs and RDS subnet groups. Use public subnets for the external ALB, and private subnets for internal ALB, backend, MCP and RDS. Plan outbound NAT/VPC endpoints as needed.
3. Three **Amazon Linux 2023** EC2 instances: frontend, backend, MCP. Size based on your workload; confirm current AWS pricing.
4. A private RDS MySQL 8.x instance with DB name `wasteflow`, automated backups, and encryption.
5. Git, Python **3.11+**, Node **22.12+** (or a compatible `^20.19`), Nginx, MySQL/MariaDB CLI, and an API key from Groq.
6. Prefer SSM Session Manager for administration. Use IAM instance profiles rather than storing AWS access keys on instances.

## 4. VPC and security groups

Create separate security groups. The following is the **recommended minimal HTTP-based network design**, not an assertion that all these exact rules are currently present:

| Security group | Required inbound rules |
|---|---|
| External ALB SG | TCP `80` from `0.0.0.0/0` (add `443` when TLS configured) |
| Frontend EC2 SG | TCP `80` **from external ALB SG** |
| Internal ALB SG | TCP `80` **from frontend EC2 SG** |
| Backend EC2 SG | TCP `8000` **from internal ALB SG** |
| MCP EC2 SG | TCP `8001` **from backend EC2 SG only** |
| RDS SG | TCP `3306` **from backend EC2 SG and MCP EC2 SG** |

Outbound rules must allow the corresponding response/application connections; backend needs HTTPS `443` to Groq and package repositories (via NAT where required). Avoid public access to ports `8000`, `8001`, `3306`. For MCP, require a bearer token even on the private network; prefer HTTPS or another protected channel for inter-instance traffic in production.

**Original security group IDs for reference:** external ALB `sg-0fab11d81c40e8b20`, frontend `sg-03d1763085b624592`, internal ALB `sg-0a501b73fd206a4de`, backend `sg-0e32a4f9d662ce02e`. These IDs will be different after recreation.

## 5. Clone the source code

On each instance that needs code (or on a CI/build machine):

```bash
sudo dnf update -y
sudo dnf install -y git
cd ~
git clone https://github.com/kashifsayyad09/waste-flow-ai.git
cd waste-flow-ai
```

Relevant repository files:

```text
schema.sql                           # MySQL schema and demo rows
backend/requirements.txt             # FastAPI dependencies
backend/.env.example                 # backend configuration template
backend/app/main.py                  # API application
backend/app/services/priority_engine.py
mcp-server/requirements.txt          # MCP dependencies
mcp-server/.env.example              # MCP configuration template
frontend/package.json                # React/Vite scripts
nginx/nginx.conf                     # LOCAL development config (not production)
deploy/README.md                     # older deployment reference
 deploy/backend/*                     # backend systemd/deploy helpers
 deploy/frontend/*                    # frontend deploy helpers
 deploy/nginx/*                       # frontend Nginx template
 docs/phase3-ai.md                    # AI/MCP details
```

## 6. Create and initialize RDS MySQL

In **AWS Console → RDS → Create database**:

- Engine: **MySQL 8.x** (original was MySQL 8.4.x).
- Database: `wasteflow`.
- VPC: same VPC as backend/MCP EC2.
- **Publicly accessible: No**.
- DB subnet group: private subnets spanning at least two AZs.
- Security group: allow `3306` from backend and MCP security groups.
- Enable encryption at rest and automated backups; store master credentials securely.

On a machine that can reach the RDS endpoint (such as backend EC2):

```bash
sudo dnf install -y mariadb105
sudo mkdir -p /etc/wasteflow/certs
sudo curl -fsSL https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
  -o /etc/wasteflow/certs/global-bundle.pem
# From the cloned repo root; enter the password interactively:
mysql -h <NEW_RDS_ENDPOINT> -P 3306 -u <MASTER_USER> -p \
  --ssl-ca=/etc/wasteflow/certs/global-bundle.pem wasteflow < schema.sql
```

If the `wasteflow` database was not created at instance creation, create it first with `CREATE DATABASE wasteflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`.

Create **separate database users** (replace placeholders; use a secure interactive client and do not commit SQL containing passwords):

```sql
CREATE USER 'wasteflow_app'@'%' IDENTIFIED BY '<STRONG_APP_PASSWORD>';
GRANT SELECT, UPDATE ON wasteflow.bins TO 'wasteflow_app'@'%';
GRANT SELECT, INSERT ON wasteflow.collection_records TO 'wasteflow_app'@'%';

CREATE USER 'wasteflow_mcp'@'%' IDENTIFIED BY '<STRONG_READONLY_PASSWORD>';
GRANT SELECT ON wasteflow.* TO 'wasteflow_mcp'@'%';
```

Verify:

```bash
mysql -h <NEW_RDS_ENDPOINT> -u <MASTER_USER> -p wasteflow \
  -e 'SHOW TABLES; SELECT COUNT(*) AS bin_count FROM bins;'
```

**Data preservation:** `schema.sql` seeds demo data. If rebuilding a real deployment, restore from a tested RDS backup/snapshot instead of assuming demo seed data represents the current database.

## 7. Backend EC2 — FastAPI on port 8000

Install Python and dependencies:

```bash
sudo dnf install -y python3.11 python3.11-pip git
cd ~/waste-flow-ai/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create a protected backend environment file, based on `backend/.env.example`:

```dotenv
APP_ENV=production
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://<EXTERNAL_ALB_DNS>
DB_HOST=<NEW_RDS_ENDPOINT>
DB_PORT=3306
DB_NAME=wasteflow
DB_USER=wasteflow_app
DB_PASSWORD=<STRONG_APP_PASSWORD>
DB_SSL_CA=/etc/wasteflow/certs/global-bundle.pem
GROQ_API_KEY=<YOUR_GROQ_API_KEY>
GROQ_TEXT_MODEL=openai/gpt-oss-20b
GROQ_VISION_MODEL=<AVAILABLE_GROQ_VISION_MODEL_ID>
MCP_SERVER_URL=http://<MCP_PRIVATE_IP_OR_DNS>:8001/mcp
MCP_API_TOKEN=<GENERATED_SHARED_TOKEN>
```

**Do not commit this file.** In production use `/etc/wasteflow/backend.env` with owner `root:wasteflow` and mode `0640`, as described in `deploy/README.md`. The sample `HOST=0.0.0.0` is needed when ALB targets the backend private IP; the checked-in example uses loopback for local development.

Generate MCP token:

```bash
python3.11 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Use the same generated token on backend and MCP, stored only in protected environment files. **Do not use the sample placeholder as a token.**

For an initial manual smoke test (from the backend directory, with environment variables loaded securely):

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For persistent operation use the checked-in `deploy/backend/wasteflow-backend.service` and `deploy/backend/deploy-backend.sh`, **after checking their paths and assumptions**. The repository's deployment helper also expects MCP to run locally; adapt it for a separate MCP EC2 or deploy the backend independently. Never run a script unchanged without reviewing it against this topology.

Check service:

```bash
sudo systemctl status wasteflow-backend --no-pager
sudo journalctl -u wasteflow-backend -n 100 --no-pager
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/v1/ai/status
```

Expected healthy backend includes `"status":"ok"` and `"database":"connected"`.

## 8. MCP EC2 — separate tool server on port 8001

The repository's original Phase 3 guide assumes MCP is colocated with the backend. For this deployed topology, install MCP on **its own EC2** and bind it to a private interface.

```bash
sudo dnf install -y git python3.11 python3.11-pip
cd ~/waste-flow-ai/mcp-server
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a **protected** MCP environment file from `mcp-server/.env.example`:

```dotenv
APP_ENV=production
MCP_HOST=0.0.0.0
MCP_PORT=8001
MCP_API_TOKEN=<SAME_GENERATED_SHARED_TOKEN_AS_BACKEND>
DB_HOST=<NEW_RDS_ENDPOINT>
DB_PORT=3306
DB_NAME=wasteflow
DB_USER=wasteflow_mcp
DB_PASSWORD=<STRONG_READONLY_PASSWORD>
DB_SSL_CA=/etc/wasteflow/certs/global-bundle.pem
# Set MCP_ALLOWED_HOSTS to the private hostname(s) actually used, if required by host validation.
```

**Security note:** `0.0.0.0` means listen on all interfaces. Use it **only** with SG inbound `8001` restricted to the backend SG, bearer-token authentication, and preferably encrypted transport. If the MCP server supports binding directly to the private IP, use that instead. Check `docs/phase3-ai.md` and actual MCP server host validation for your deployed version.

Start manually for testing:

```bash
cd ~/waste-flow-ai/mcp-server
.venv/bin/python -m wasteflow_mcp
```

Create a dedicated systemd unit on the MCP instance based on the repository's `deploy/backend/wasteflow-mcp.service`, but **edit the paths, user, environment file and working directory** for the separate instance before enabling it.

From backend EC2, test reachability (unauthenticated requests should not return successful tool data):

```bash
curl -i -X POST http://<MCP_PRIVATE_IP_OR_DNS>:8001/mcp
```

A `401` without a token is a useful authentication check; the MCP protocol may also validate request headers and return other 4xx responses.

## 9. Internal ALB — backend routing

In **EC2 → Target Groups** create:

- Name: `wasteflow-backend-tg`
- Target type: **Instance** (or IP, if intentionally using IP targets)
- Protocol/port: HTTP `8000`
- Register backend EC2 on port `8000`
- Health check path: `/health`; success `200`

Then in **EC2 → Load Balancers** create an **Application Load Balancer**:

- Name: `wasteflow-internal-alb`
- Scheme: **Internal**
- VPC: application VPC; subnets across at least two AZs
- Listener: HTTP `80` -> `wasteflow-backend-tg`
- SG: port `80` from frontend SG

Wait for target status **healthy**. Check from frontend EC2:

```bash
curl -i http://<INTERNAL_ALB_DNS>/health
curl -i http://<INTERNAL_ALB_DNS>/api/v1/ai/status
```

## 10. Frontend EC2 — Nginx and React

```bash
sudo dnf install -y git nginx
sudo systemctl enable --now nginx
node --version
npm --version
```

Install Node 22.12+ if not already present; ensure `node --version` meets `frontend/package.json` engine requirements. Build:

```bash
cd ~/waste-flow-ai/frontend
npm ci
npm run build
sudo mkdir -p /usr/share/nginx/html
sudo cp -a dist/. /usr/share/nginx/html/
```

The **observed deployed frontend** serves `/usr/share/nginx/html` (the repo's deployment script may instead use `/var/www/wasteflow/current`). Keep Nginx `root` consistent with your actual build destination.

Create `/etc/nginx/conf.d/wasteflow.conf` and replace `<INTERNAL_ALB_DNS>`:

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location /api/v1/ai/ {
        client_max_body_size 5m;
        proxy_pass http://<INTERNAL_ALB_DNS>;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout 90s;
        proxy_send_timeout 90s;
    }

    location /api/ {
        proxy_pass http://<INTERNAL_ALB_DNS>;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /health {
        proxy_pass http://<INTERNAL_ALB_DNS>;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

**Nginx warning:** Amazon Linux's stock `/etc/nginx/nginx.conf` may already define a default server on port 80. Ensure your new server handles the intended host and remove/adjust any conflicting default server block. If SELinux is enforcing and proxy requests fail, check SELinux logs; where appropriate, `sudo setsebool -P httpd_can_network_connect 1` may be required.

```bash
sudo nginx -t
sudo systemctl reload nginx
curl -I http://127.0.0.1/
curl -i http://127.0.0.1/health
```

**Do not point the frontend browser directly at the internal ALB DNS**: browsers outside the VPC cannot reach it. Browser calls should use relative `/api/...` paths through the external website origin.

## 11. External ALB — public website

Create target group:

- Name: `wasteflow-frontend-tg`
- Protocol/port: HTTP `80`
- Register frontend EC2 on port `80`
- Health check path: `/` (expects `200`)

Create **internet-facing Application Load Balancer**:

- Name: `wasteflow-external-alb`
- Scheme: **Internet-facing**
- Public subnets in at least two AZs
- Listener: HTTP `80` -> `wasteflow-frontend-tg`
- SG: inbound `80` from internet

Wait for the frontend target to become healthy. Use the **new** external ALB DNS if recreating the resources. Original example:

```text
http://wasteflow-external-alb-751904982.us-east-1.elb.amazonaws.com
```

## 12. End-to-end verification

Run from your laptop (replace `<PUBLIC_ALB_DNS>`):

```bash
curl -I http://<PUBLIC_ALB_DNS>/
curl -i http://<PUBLIC_ALB_DNS>/health
curl -i http://<PUBLIC_ALB_DNS>/api/v1/bins
curl -i http://<PUBLIC_ALB_DNS>/api/v1/priorities
curl -i http://<PUBLIC_ALB_DNS>/api/v1/collection-plan
curl -i http://<PUBLIC_ALB_DNS>/api/v1/ai/status
```

Expected:

- Website returns HTTP `200` and loads in a browser.
- `/health` returns healthy status and database connected.
- `/api/v1/ai/status` reports chat/classification availability and MCP configuration when credentials/models are valid.
- AI assistant can retrieve priorities via MCP (example test: BIN-004 previously returned priority `97`, but data can change).
- Both ALB target groups show **healthy** registered targets.

Test frontend and backend directly **from their respective instances** if public requests fail.

## 13. Troubleshooting

| Symptom | Checks |
|---|---|
| External ALB 503 / unhealthy target | Frontend EC2 port 80; SG from external ALB; `sudo nginx -t`; `systemctl status nginx`; target health path `/` |
| Website loads but `/api` returns 502 | Nginx `proxy_pass` must target internal ALB DNS; internal ALB SG; backend target health; backend listens on `0.0.0.0:8000` |
| Backend unhealthy / database disconnected | RDS endpoint, `3306` SG, private routing, DB credentials, database `wasteflow`, RDS CA bundle |
| AI says unavailable | Check `GROQ_API_KEY`, valid model IDs, backend outbound HTTPS, `/api/v1/ai/status`, backend logs |
| MCP tool calls fail | MCP EC2 running/listening on `8001`, SG source backend SG, matching token, `MCP_SERVER_URL`, allowed Host headers, MCP DB credentials |
| SPA deep links show 404 | Ensure `try_files $uri $uri/ /index.html` |
| Frontend updates not visible | Rebuild `npm ci && npm run build`, recopy `dist`, check browser caching |
| Nginx duplicate default server | Inspect `/etc/nginx/nginx.conf` and `conf.d`; keep one appropriate default server |

Useful commands:

```bash
sudo systemctl status nginx --no-pager
sudo nginx -t
sudo tail -n 100 /var/log/nginx/error.log
sudo systemctl status wasteflow-backend --no-pager
sudo journalctl -u wasteflow-backend -n 100 --no-pager
ss -ltnp | grep -E ':80|:8000|:8001'
```

## 14. Security, production readiness and operations

- **HTTPS is not yet configured in the original deployment.** Attach a domain name and ACM certificate to the external ALB, add an HTTPS `443` listener, and redirect HTTP to HTTPS. Tighten CORS and cookie policies accordingly.
- Do not expose RDS, MCP or backend ports publicly.
- Use separate least-privilege DB users; keep MCP database access read-only.
- Keep `backend.env`, MCP env files, and Groq credentials outside Git. Prefer AWS Secrets Manager/SSM Parameter Store with IAM instance roles.
- Rotate any secrets that have previously been shared in logs, screenshots, chat, or committed files.
- Enable RDS backups; regularly test restore procedures. Add CloudWatch logs, metrics, alarms and access logs as appropriate.
- Configure IAM roles, patching, monitoring, scaling and cost budgets before production use.
- ALB target groups do **not** automatically make an app highly available with only one target per tier. Add more instances and autoscaling for HA.
- An external ALB and an internal ALB, EC2 instances, NAT, and RDS incur AWS charges. Remove unused resources when done.

## 15. Deployment checklist

- [ ] VPC, public/private subnets, route tables and NAT/egress configured
- [ ] Frontend, backend, MCP EC2 launched with Amazon Linux 2023
- [ ] All six security group relationships configured
- [ ] Private RDS MySQL provisioned, schema imported, least-privilege users created
- [ ] Backend Python dependencies installed, protected env configured, service healthy
- [ ] MCP dependencies installed, token matches backend, service reachable privately
- [ ] Internal ALB listener, backend target group and `/health` check healthy
- [ ] Frontend React built, Nginx static root and internal-ALB proxy configured
- [ ] External ALB listener, frontend target group and `/` check healthy
- [ ] Public site, `/health`, priorities, and AI status tested
- [ ] HTTPS, secrets management, backups, monitoring and budget reviewed

## 16. Further documentation

- [Original project README](https://github.com/kashifsayyad09/waste-flow-ai/blob/main/README.md)
- [Repository deployment scripts and instructions](https://github.com/kashifsayyad09/waste-flow-ai/tree/main/deploy)
- [AI/MCP implementation notes](https://github.com/kashifsayyad09/waste-flow-ai/blob/main/docs/phase3-ai.md)
- [Database schema](https://github.com/kashifsayyad09/waste-flow-ai/blob/main/schema.sql)

---

**Rebuild note:** The original AWS private IPs, resource IDs, and DNS names are included for orientation, **not** as fixed settings for a new installation. This guide combines checked-in repository instructions with details of the previously tested three-EC2/two-ALB deployment; review application configuration and deployment scripts against the current commit before using in production.
