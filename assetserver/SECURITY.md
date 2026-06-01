# Security Model — Medieval Pixel Art Image Service

Security considerations, authentication model, and known limitations for
production deployments.

---

## Authentication Model

### Optional API Key

Authentication is **optional** and controlled by `SERVER__API_KEY`:

- **When empty** (default): All endpoints are publicly accessible. Suitable for
  development, internal networks, or when a reverse proxy handles auth.
- **When set**: Every request must include the `X-API-Key` header with the
  matching value. Invalid or missing keys receive `401 Unauthorized`.

**Exempt endpoints** (always accessible, even with an API key configured):
- `GET /health` — needed by load balancers and monitoring
- `GET /assets/{filename}` — needed for serving generated images to clients

### API Key Format

The key is a plain string compared with `==`. There is no hashing, no key
rotation, and no scoping. Treat it as a shared secret.

**Recommendation**: Generate a 64-character hex string:

```bash
openssl rand -hex 32
```

Set it in `.env`:

```bash
SERVER__API_KEY=3f8a9b2c...your-64-char-hex-key...
```

### Transport Security

The `X-API-Key` header is sent in plain text. **Always use HTTPS** in
production to prevent key interception. Terminate TLS at the reverse proxy
(see [DEPLOYMENT.md](DEPLOYMENT.md)).

---

## CORS Configuration

CORS origins are configured via `SERVER__CORS_ORIGINS` (a JSON array):

```bash
# .env
SERVER__CORS_ORIGINS='["https://mygame.example.com","https://admin.example.com"]'
```

### Production Recommendations

- **Never use `["*"]`** in production. The server will emit a warning at
  startup, and `DEPLOYMENT_MODE=production` will refuse to start if `*` is
  the only origin.
- **List exact origins** — no trailing slashes, no wildcard subdomains.
- **`allow_credentials` is `false`** — the service does not use cookies or
  session-based auth, so credentials are not needed.
- **`allow_methods` is `["*"]`** — all HTTP methods are permitted. This is
  safe because CORS only controls browser cross-origin requests, not direct
  API calls.
- **`allow_headers` is `["*"]`** — all headers are permitted. This simplifies
  client integration (e.g., custom tracing headers).

---

## Rate Limiting Design

The built-in rate limiter uses a **token-bucket algorithm** and is **global** —
it limits total requests across all clients, not per-IP.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RATE_LIMIT__POST_RPS` | `2.0` | Max POST requests/second globally |
| `RATE_LIMIT__GET_RPS` | `50.0` | Max GET requests/second globally |
| `RATE_LIMIT__BURST_SIZE` | `5` | Max burst for POST before throttling |
| `RATE_LIMIT__ENABLED` | `true` | Toggle on/off |

Exceeding the limit returns `429 Too Many Requests`:
```json
{"detail": "Rate limit exceeded. Slow down."}
```

### Why Global, Not Per-IP?

The global limiter protects the ComfyUI GPU from overload — only one
generation can run at a time on a single GPU. Per-IP limiting is the
responsibility of the **reverse proxy** (nginx `limit_req_zone` or
Caddy `rate_limit`). See [DEPLOYMENT.md](DEPLOYMENT.md) for examples.

### Disabling Rate Limiting

Set `RATE_LIMIT__ENABLED=false` to disable. This is useful for testing
environments. In production, keep it enabled and add per-IP limits at
the reverse proxy.

---

## Security Considerations

### Path Traversal Protection

All file operations that accept user-supplied filenames use
`os.path.basename()` to strip directory components:

- `GET /assets/{filename}` — the `filename` parameter is sanitized via
  `_safe_filename()` before any filesystem access.
- Asset storage (`src/storage.py`) — all save/load/delete operations
  sanitize filenames.

This prevents attacks like `GET /assets/../../../etc/passwd`.

### Atomic Writes

All image files are written atomically (temp file + `os.rename`). This
prevents:
- **Corrupted files** — if the process crashes mid-write, the temp file is
  orphaned (not the target path).
- **Partial reads** — concurrent readers never see a half-written file
  because the rename is atomic on POSIX filesystems.

### Input Validation

- **Pydantic schemas** validate all request bodies at the FastAPI layer
  before any business logic runs. Invalid enums, missing required fields,
  and type mismatches return `422 Unprocessable Entity`.
- **Description length limits** — `leader_description` and
  `action_description` have maximum character limits enforced by Pydantic.
- **Request body size limit** — `RequestSizeLimitMiddleware` rejects bodies
  exceeding `SERVER__MAX_REQUEST_BODY_MB` (default 10 MB) with `413 Payload
  Too Large`. Requests without `Content-Length` on POST/PUT/PATCH return
  `411 Length Required`.

### Database

- **SQLite WAL mode** — Write-Ahead Logging provides crash safety and
  concurrent read/write access.
- **Foreign key constraints** — enabled via `PRAGMA foreign_keys=ON`.
  Cascading deletes are configured (`ondelete="CASCADE"`) so that deleting
  an asset record cleans up its family-specific record automatically.
- **Busy timeout** — 5-second `busy_timeout` plus application-level retry
  (3 attempts with exponential backoff) for write contention.
- **`DATABASE_RESET` blocked in production** — setting
  `DATABASE_RESET=true` with `DEPLOYMENT_MODE=production` is refused to
  prevent accidental data loss.

### Deployment Mode Safety Checks

When `DEPLOYMENT_MODE=production`:
- CORS `*` wildcard is rejected at startup
- Schema mismatches are fatal (service refuses to start)
- `DATABASE_RESET=true` is blocked
- Missing ComfyUI workflow nodes are fatal errors
- Workflow–template LoRA mismatches are logged at CRITICAL level

---

## Known Limitations

### API Key is a Single Shared Secret

There is no multi-user auth, no role-based access control, and no key
rotation mechanism. The API key is a single string shared by all clients.
For internal services behind a VPN, this is usually sufficient. For
multi-tenant or public-facing deployments, add an auth proxy (e.g.,
OAuth2 Proxy, AWS API Gateway) in front of the service.

### Rate Limiting is Global

A single abusive client can exhaust the global token bucket and deny
service to all other clients. Always add per-IP rate limiting at the
reverse proxy level.

### No Audit Logging

The service does not log which API key (if any) was used for each request.
For audit trails, capture access logs at the reverse proxy.

### No Content Security Policy Headers

The service does not set `Content-Security-Policy`, `X-Content-Type-Options`,
or other security headers. These should be added at the reverse proxy:

```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

### SQLite Not Suitable for High-Write Loads

SQLite serializes all writes. Under high concurrent write load, expect
`SQLITE_BUSY` errors (mitigated by busy timeout + retry logic). For
high-throughput deployments, consider migrating to PostgreSQL. See
[next_steps.md](docs/project/next_steps.md) for the distributed scaling roadmap.

---

## Reporting Security Vulnerabilities

If you discover a security vulnerability in this service, please:

1. **Do not open a public issue.**
2. Email the maintainers directly with a detailed description.
3. Allow reasonable time for a fix before disclosing publicly.

---

## See Also

- [DEPLOYMENT.md](DEPLOYMENT.md) — Production deployment guide
- [architecture.md](docs/architecture/architecture.md) — Full system architecture
- [README.md](../README.md) — Project overview
