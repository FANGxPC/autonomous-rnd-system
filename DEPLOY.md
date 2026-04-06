# Deploy to Cloud Run (one URL: UI + API)

The container serves **FastAPI** and static files from **`frontend/`** on the same origin. The browser calls **`POST /trigger-pipeline`** with a relative URL (no CORS hassle). **MCP** (Model Context Protocol) is on the **same URL** at **`/mcp/`** ( **`/mcp`** redirects with **307** ) — judges use one Cloud Run host for UI, API, and MCP.

## What the image expects

- **Port:** Cloud Run sets **`PORT`** (often `8080`). The Dockerfile defaults `PORT=8080`; `uvicorn` uses `"${PORT}"`.
- **Secrets:** Do **not** bake `.env` or `token.json` into the image. Use **Secret Manager** references on the Cloud Run service (see below).
- **GCP auth:** Omit **`GOOGLE_APPLICATION_CREDENTIALS`**. Grant the **Cloud Run service account** roles such as **Vertex AI User** (if using Vertex) and access to **Firestore**.

## Build the image locally (smoke test)

From the repo root (requires Docker):

```bash
docker build -t deep-tech-sprint:local .
docker run --rm -p 8080:8080 \
  --env-file .env \
  -v "$(pwd)/token.json:/app/token.json:ro" \
  deep-tech-sprint:local
```

Then:

1. **Health:** `curl -s http://127.0.0.1:8080/health` → should print JSON with `"status":"ok"`.
2. **UI:** Open **http://127.0.0.1:8080/** — form should load; footer shows API base **same origin (this host)**.
3. **API info:** `curl -s http://127.0.0.1:8080/api` → JSON service metadata.
4. **Swagger:** **http://127.0.0.1:8080/docs**
5. **Pipeline (optional):** Submit the form or:

```bash
curl -s -X POST http://127.0.0.1:8080/trigger-pipeline \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello test","deadline":"2026-12-31","project_key":"smoke_test"}'
```

6. **MCP (optional):** Base URL is **`http://127.0.0.1:8080/mcp/`** (same on Cloud Run: **`https://YOUR-SERVICE-URL/mcp/`**).  
   - If **`MCP_AUTH_TOKEN`** is set, unauthenticated requests get **401**:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/mcp/
# expect 401 when MCP_AUTH_TOKEN is non-empty
```

   - With token (example):

```bash
curl -s -H "Authorization: Bearer YOUR_MCP_TOKEN" http://127.0.0.1:8080/mcp/
```

   From a machine with **`fastmcp`** installed: `fastmcp list http://127.0.0.1:8080/mcp/ -t http` — if the service sets **`MCP_AUTH_TOKEN`**, add **`--auth <same token>`** (Bearer under the hood).

If the container exits on import with **Notion** errors, ensure **`NOTION_TOKEN`** (and other required env vars) are passed in via `--env-file` or `-e`.

## Google Cloud Run (outline)

1. **Enable APIs:** Cloud Run, Artifact Registry (or Container Registry), Secret Manager, Firestore, Vertex (if used).
2. **Create secrets** in Secret Manager (examples): `notion-token`, `google-oauth-client-secret`, optional `calendar-refresh-token` / copy of needed values — **never** commit them.
3. **Grant** the Cloud Run runtime service account **`secretmanager.secretAccessor`** on those secrets.
4. **Build & push** (replace `PROJECT` and region):

```bash
gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT/REPO/deep-tech-sprint:latest
```

5. **Deploy:**

```bash
gcloud run deploy deep-tech-sprint \
  --image REGION-docker.pkg.dev/PROJECT/REPO/deep-tech-sprint:latest \
  --region REGION \
  --port 8080 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=1,GOOGLE_CLOUD_PROJECT=PROJECT,GOOGLE_CLOUD_LOCATION=us-central1,..." \
  --set-secrets "NOTION_TOKEN=notion-token:latest,GOOGLE_CLIENT_SECRET=oauth-client-secret:latest"
```

Adjust **`--set-env-vars`** / **`--set-secrets`** to match your app (see `.env.example`). Add **`CORS_ALLOW_ORIGINS`** only if the browser origin differs from the service URL (same-origin deploys usually do not need it).

**MCP on Cloud Run:** Set **`MCP_AUTH_TOKEN`** via **`--set-env-vars`** or a Secret Manager reference (e.g. **`--set-secrets MCP_AUTH_TOKEN=mcp-judge-token:latest`**). Share the **exact URL** **`https://YOUR-SERVICE-URL/mcp/`** with judges and the header scheme (**`Authorization: Bearer`** or **`X-MCP-API-Key`**). Leaving **`MCP_AUTH_TOKEN`** unset exposes an unauthenticated MCP endpoint — avoid on public services.

6. **Verify after deploy**

- `curl -s https://YOUR-SERVICE-URL/health`
- Open **`https://YOUR-SERVICE-URL/`** in a browser (form + submit).
- Optional: **`/docs`** for Swagger.

## Optional CORS

If you ever split UI and API across origins, set:

- **`CORS_ALLOW_ORIGINS`** — comma-separated list (e.g. `https://your-frontend.example.com`).
- Or **`CORS_ALLOW_ORIGIN_REGEX`** — e.g. `https://.*\.run\.app` (use with care).

## Route reference

| Path | Purpose |
|------|---------|
| **`/`** | Web UI (`frontend/index.html`) |
| **`/health`** | Liveness / readiness JSON |
| **`/api`** | JSON service info (formerly `GET /`) |
| **`/docs`** | Swagger |
| **`POST /trigger-pipeline`** | Agent pipeline |
| **`/mcp/`** | **MCP** (FastMCP Streamable HTTP) — same tools as agents; optional **`MCP_AUTH_TOKEN`** (see README) |
| **`/mcp`** | **307** redirect to **`/mcp/`** |
