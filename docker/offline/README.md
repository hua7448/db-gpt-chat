# K-ICS Offline Deployment

Target architecture: Linux x86-64 (linux/amd64). Python is managed with UV.
Two images: `k-ics:20260909` and `k-ics-python:20260909`.

## Install

1. Verify the delivery archive using its SHA256 file, then extract it.
2. Run `docker load -i images.tar.gz` (Docker supports gzip archives).
3. Copy `site.env.example` to `site.env`, set SITE_APP_KEY and SITE_APP_SECRET,
   then run `chmod 600 site.env`. Never put credentials in the images.
4. Put the gateway CA chain in `certs/customer-ca.pem` and set
   `SITE_CA_FILE=/app/certs/customer-ca.pem` in site.env. The certificate must
   match the gateway hostname/IP. For a controlled test only, `verify_tls`
   in site.toml can be set to false explicitly.
5. Run `bash start.sh`. Default URL: http://127.0.0.1:5670.
   For approved LAN access use `KICS_BIND_ADDRESS=<server-IP> bash start.sh`.
6. Add Oracle in the UI: host 172.16.176.154, port 1530, service_name LSRSDB.
   Use the site's database credentials. Do not use the developer tunnel's
   127.0.0.1:11530 address in the container.

Docker Engine must already be installed. Compose is not required. The supplied
start script uses the host Docker socket to create sibling analysis containers;
the application therefore needs a trusted host and trusted administrators.
The socket is never mounted into the analysis sandbox.

## Services and Storage

LLM: https://10.146.16.36:8898/aiApi/workflow/llmProxy, model qwen3.8_27b.
Embedding: http://10.84.97.104:8000/v1/embeddings,
model Qwen3-Embedding-0.6B. Both must be reachable from the application container.
The context limit defaults to 32768; adjust only after the site's limit is known.
Authentication timestamps require the host clock to be correct.

The application uses SQLite metadata and local Chroma storage in data/pilot.
Oracle is a business data source, not the platform metadata database.
data/logs contains logs. Back up both directories and the local configuration.
Keep the deployment directory fixed: sandbox bind mounts use its absolute path.
Uploaded inputs are mounted read-only, each execution working directory read-write.
Sandbox containers have no network, no application secrets or Docker socket,
a read-only root filesystem, 1 GiB memory, 2 CPU and 128 process limits.
They are removed after execution, including timeout failures.

Python, shell, file analysis and the subagent Python/shell tools use the Docker
backend. Skill script files also use Docker. Legacy Lyric script execution and
AWEL Lyric operators fail closed in Docker mode; they are not part of this
deployment's supported execution path. Notebook, browser automation and GPU
execution are not included. New skills may require additional packages baked
into the sandbox image; installing packages at runtime is not supported offline.

## OpenAI Compatibility

The existing `proxy/openai` provider is unchanged. To use it instead, replace
the LLM block in site.toml with the standard OpenAI example's block (api_base,
api_key, name), removing gateway-only app_key/app_secret/CA fields.
The customer provider is selected independently as `proxy/customer_gateway`.

## Operations

- Logs: `docker logs --tail 100 k-ics`
- Stop: `docker stop k-ics`
- Restart: `docker start k-ics`
- Apply changed environment: stop/remove only the k-ics container, then rerun
  start.sh. The bind-mounted data persists. Never remove data/ to upgrade.
- Health: `curl http://127.0.0.1:5670/api/health`

Offline smoke checks cover client loading, cached tokenizers and sandbox
analysis. Actual customer gateway, Oracle login, schema reflection and query
results still require acceptance on the customer network with real credentials.
Oracle 19.32 Basic is bundled for Oracle 11.2.0.4 Thick mode. Keep the Oracle
license/notice files shipped with Instant Client in the delivered image.
