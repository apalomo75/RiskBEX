# RISKBEX single-VPS deployment runbook

Sprint 10B prepares infrastructure only. No VPS, public endpoint, certificate,
backup of live data, or new scheduler was created. Continuous unattended operation
is not established. Commands below are future operator procedures, not evidence
that deployment has occurred. Run VPS commands only on the new VPS.

## Architecture and release gates

Use Ubuntu 24.04 LTS amd64, initially 2 vCPU / 4 GB RAM / about 40 GB SSD.
The size is an estimate: the previous 82/66/159 MiB API/dashboard/updater readings
were idle/startup observations, not peak measurements.

Internet -> Caddy (80/443 TCP) -> dashboard:8501 -> api:8000.
Only updater can write the shared publication bind mount. API reads the same
store; dashboard consumes API responses and has no store mount. Inputs are
read-only. No Docker socket is mounted. Existing Dockerfiles, model package,
calendar and scheduler are reused. Caddy is the only additional container.

The production override removes the dashboard host port. API and updater have
no host ports. Private validation uses `docker compose exec` or an SSH-carried
request, never a temporary public 8000/8501 mapping. Caddy's `public` profile and
the updater's `scheduled` profile are opt-in. Do not run a bare `up` with profiles:
name the intended services explicitly. Do not use the local project name.

Public launch requires an approved data-display scope, private smoke tests,
verified backup/restore, reboot recovery, and observed unattended trading-session
updates on the VPS. Yahoo/IBEX redistribution rights remain unresolved. No chart,
dataset, simulator or indicator is changed here. Attribution and an educational
disclaimer alone do not establish rights. Resolve this separately before launch.

## 1. Provision and secure the host

Create the VPS only after authorization. Select supported Ubuntu amd64; keep
provider console recovery available. Set a provider firewall: deny inbound by
default, allow SSH only from the administrator's actual IP/CIDR. Keep 80/443
closed until public launch is authorized. Do not publish an AAAA record unless
IPv6 firewall and reachability have also been validated.

Create a dedicated `riskbex` account with an SSH public key. Use its actual UID
and primary GID below (`id -u riskbex`, `id -g riskbex`), not an assumed 1000.
Confirm a second key-authenticated SSH connection works before disabling root
and password login in `/etc/ssh/sshd_config.d/60-riskbex.conf`:

```text
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
```

```bash
sudo sshd -t
sudo systemctl reload ssh
# Replace ADMIN_CIDR with the real administrator IP/CIDR first.
export ADMIN_CIDR='REPLACE_WITH_ADMIN_IP/32'
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from "$ADMIN_CIDR" to any port 22 proto tcp
sudo ufw enable
```

Do not rely only on UFW for Docker-published ports: Docker can bypass UFW.
Use the provider firewall as the ingress boundary and externally check IPv4
and IPv6 exposure. Restrict Docker-group membership: it is root-equivalent.
Keep OS security updates enabled; schedule reboots with operational checks.

## 2. Install Docker (future VPS only)

Follow the current official instructions linked below; resolve conflicting distro
Docker packages first if present. On a clean Ubuntu 24.04 host:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git python3 rsync
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' "$(dpkg --print-architecture)" "$VERSION_CODENAME" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker riskbex
```

Log in again as `riskbex`. Require Compose >= 2.24.4 for `!reset`; verify
`docker compose version`. Never mount the daemon socket in application containers.

## 3. Checkout, environment and empty infrastructure directories

As `riskbex`, clone into `/opt/riskbex` (have the administrator create/chown that
empty directory first). Select a reviewed commit containing Sprint 10B; `068fff8`
does not contain these new files. No commit has been made by this sprint.

```bash
sudo install -d -o riskbex -g "$(id -gn riskbex)" -m 0750 /opt/riskbex
sudo install -d -o riskbex -g "$(id -gn riskbex)" -m 0700 /etc/riskbex /srv/riskbex
sudo install -d -o riskbex -g "$(id -gn riskbex)" -m 0700 /var/backups/riskbex
sudo install -d -o riskbex -g "$(id -gn riskbex)" -m 0700 /srv/riskbex/tls/data /srv/riskbex/tls/config
sudo -u riskbex git clone https://github.com/apalomo75/RiskBEX.git /opt/riskbex
cd /opt/riskbex
umask 077
cp deploy/production/.env.example /etc/riskbex/production.env
chmod 600 /etc/riskbex/production.env
export RISKBEX_PROD_ENV=/etc/riskbex/production.env
```

Edit that file explicitly: set UID/GID to the dedicated account, release to the
reviewed Git SHA, and confirm all absolute paths. Keep `example.invalid` until a
real domain is configured. Do not source the env as shell code. The wrapper uses
an explicit env file and project `riskbex-prod`; it never loads local `.env`.
Environment exports override Compose env-file values: use a clean login shell and
remove any inherited `RISKBEX_*` values except `RISKBEX_PROD_ENV`.

Do **not** create an empty `/srv/riskbex/state/store`, seed or receipt. Missing
bind sources fail instead of silently shadowing data. The restore procedure
creates a new state tree from validated input. Historical data must also be
transferred: the ignored `backend/data` is not supplied by Git. Required figures
are build inputs from ignored `backend/figures`; transfer them into that exact
checkout path before building. Neither transfer downloads new market data.

## 4. Consistent migration without changing local publications

The live local environment must stay running. In a separately authorized migration
window, run the backup as the existing store owner, choosing a new archive outside
the store and input directories. The nonblocking `update.lock` rejects overlap
with a running update. A successful backup briefly holds that same lock: an
update attempted during the copy can fail busy and retry next slot. Schedule
backup outside 20:15/21:15/22:15 Madrid; never hold a scheduler lock yourself.

Example on the source host, using the validated paths from Sprint 9B:

```bash
umask 077
mkdir -p /tmp/riskbex-transfer
python3 deploy/production/storage.py backup \
  --store backend/runtime/main-wsl-test \
  --seed backend/runtime/inputs/seed.csv \
  --receipt backend/runtime/inputs/receipt.json \
  --output /tmp/riskbex-transfer/migration.tar.gz \
  > /tmp/riskbex-transfer/migration.json
```

This command is NOT authorized/executed as part of Sprint 10B. It reads publications
under the existing lock; it does not modify the pointer, seed or receipt. The
archive includes all retained version directories, active pointer, status,
attempt diagnostics and both inputs. It excludes lock files, staging and temporary
orphans. It verifies file digests for every retained version. An incomplete orphan
version causes backup failure and requires review, not automatic deletion.

Use SSH/SCP with verified host keys. Replace `VPS_HOST` with the actual SSH host:

```bash
scp /tmp/riskbex-transfer/migration.tar.gz /tmp/riskbex-transfer/migration.json riskbex@VPS_HOST:/var/backups/riskbex/
# From the source checkout; only into a new VPS checkout with no running services:
rsync -a --chmod=D750,F640 backend/data/ riskbex@VPS_HOST:/srv/riskbex/historical-data/
rsync -a --chmod=D750,F640 backend/figures/ riskbex@VPS_HOST:/opt/riskbex/backend/figures/
```

Install `rsync` on the two hosts separately if needed and authorized. Verify copied
historical data/figures with `rsync -nrc` before building. Keep transfer archives
private; do not put them in Git or a web-served path. No data is copied in this sprint.

On the VPS, obtain the expected archive SHA-256 from the source JSON over the
verified SSH channel. Replace `ARCHIVE_SHA256` below with that 64-character value:

```bash
python3 deploy/production/storage.py restore \
  --archive /var/backups/riskbex/migration.tar.gz \
  --sha256 ARCHIVE_SHA256 --destination /srv/riskbex/state
chmod -R u=rwX,go= /srv/riskbex/state
python3 deploy/production/preflight.py
sh deploy/production/compose.sh --profile scheduled --profile public config --quiet
```

Restore accepts only a new destination, verifies archive and member inventory,
rejects traversal/links/special files, checks the pointer and version file hashes,
and recreates only the update lock. It does not claim quantitative validation.
Run as configured UID/GID; the API/updater share that identity. Host root/owner
remain trusted; container read-only mounts do not prevent authorized host writes.

## 5. Build and verify privately (no scheduler)

```bash
sh deploy/production/compose.sh build api dashboard
```

Offline verification in a new one-shot production container; no network fetch.
Use updater because API intentionally has no receipt mount:

```bash
sh deploy/production/compose.sh --profile scheduled run --rm --no-deps updater \
  python -B -c 'from src.riskbex.engine.package import load_main_package; from src.riskbex.pipeline.service import verify_gate; p=load_main_package("/app/model_packages/main-v1"); verify_gate("/inputs/receipt.json",p)'
sh deploy/production/compose.sh up -d --wait api dashboard
sh deploy/production/compose.sh exec -T dashboard python -B -c \
 'import urllib.request,json; print(json.dumps(json.load(urllib.request.urlopen("http://api:8000/latest-risk",timeout=30))["publication"],indent=2))'
sh deploy/production/compose.sh exec -T api python -B -c \
 'from src.riskbex.api.operational import snapshot; print(snapshot()["publication"]["version"])'
sh deploy/production/compose.sh ps
```

The explicit one-shot command overrides the updater entry point and never invokes
its scheduler/provider. Check MAIN package/runtime, receipt gate, migrated version,
metadata and freshness. A stale migrated publication is expected until authorized
catch-up; never relabel it current. Confirm `/run-update` remains 403 using an
internal HTTP request. Validate historical routes, Performance and simulator.

For a private browser session without host port exposure, use SSH stdio forwarding:
`ssh -L 18501:CONTAINER_IP:8501 riskbex@VPS_HOST`, where `CONTAINER_IP` is obtained
on the VPS using `docker inspect` for the production dashboard's default network.
Open `http://localhost:18501`; this IP is private and can change on recreation.
Inspect all six views and simulator; no UI or calculation changes are intended.

## 6. Scheduler authorization and unattended validation

Before activation, inspect `systemctl list-timers --all`,
`systemctl --user list-timers --all`, user/root crontabs, `/etc/cron.d`, process
listings and all Docker projects. Resolve duplicate scheduling through a separate
authorized operator action. Exactly one production timer may target this store.
Local WSL services must not be interrupted by this sprint or these VPS steps.

After explicit production activation authorization:

```bash
sh deploy/production/compose.sh --profile scheduled up -d updater
sh deploy/production/compose.sh logs --timestamps --tail=100 updater
```

Existing scheduler uses Europe/Madrid wall time (CET/CEST), slots 20:15/21:15/22:15,
a lifetime timer lock, per-update lock, 30-minute timeout and atomic publication.
Non-trading days can legitimately produce `unchanged`. Failed Yahoo responses,
incomplete/missing sessions and historical revisions fail closed and preserve the
last valid pointer. A restarted timer waits for the next slot; pipeline requests
missing sessions then, not immediately at boot. `unless-stopped` requires a running
Docker daemon; manually stopped containers stay stopped after reboot.

Observe at least three consecutive trading-session publications without operator
intervention. Record `timer_wait`, terminal `daily_update`, `timer_result`, market
session, publication version and read-time freshness. Verify graceful failure and
catch-up with offline tests first; do not manufacture provider failures in live
production. A one-shot successful update is not evidence of daily reliability.

Calendar coverage is 2026 only; uncovered dates fail closed. Before the last 2026
session needs a 2027 target, review official BME/Sociedad de Bolsas instructions,
record source and review metadata in the existing calendar, test year-boundary
eligibility/next-session behavior, and rebuild API/updater from the same release.
Do not infer dates from civil holidays or another exchange. This sprint adds no dates.

## 7. Domain, TLS and public gate

Buy/configure a domain only when authorized. Set `RISKBEX_DOMAIN` to a hostname
without scheme/path/port. DNS A must point at VPS IPv4. Add AAAA only for working,
protected IPv6; remove stale records. No actual domain is assumed.

Caddy uses unprivileged 8080/8443 internally, mapped to host 80/443. Automatic TLS
and HTTP redirect use standard external ports. WebSocket upgrade is automatic;
there is no stream timeout. Header read timeout is 15 seconds, upstream connection
5 seconds, response header 60 seconds. No FastAPI route is proxied. Caddy admin
API is disabled. HSTS is limited to this host (no preload/includeSubDomains).
TLS state is persistent, private and writable only by its container identity.

Before starting Caddy, validate without acquiring certificates on the VPS:

```bash
python3 deploy/production/preflight.py --public
sh deploy/production/compose.sh --profile public run --rm --no-deps caddy \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

Only after all launch gates, data-scope decision and public access authorization:
open provider firewall/UFW 80/443 TCP and run:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sh deploy/production/compose.sh --profile public up -d caddy
sh deploy/production/compose.sh logs --tail=100 caddy
```

Verify HTTP redirects, valid hostname/certificate, renewal storage, response
security headers and all six views externally. In browser developer tools confirm
`/_stcore/stream` upgrades to 101 and remains connected during interaction.
Externally check 8000/8501 are closed on IPv4 and IPv6. No certificate acquisition
or Caddy startup was attempted during Sprint 10B. Caddy binary validation is a
mandatory pre-launch check if unavailable during development.

## 8. Backups, retention and restoration

Run backups as the store owner outside update slots. Example daily command:

```bash
umask 077
stamp=$(date -u +%Y%m%dT%H%M%SZ)
python3 deploy/production/storage.py backup \
  --store /srv/riskbex/state/store --seed /srv/riskbex/state/inputs/seed.csv \
  --receipt /srv/riskbex/state/inputs/receipt.json \
  --output "/var/backups/riskbex/state-$stamp.tar.gz" \
  > "/var/backups/riskbex/state-$stamp.json"
```

Nonzero exit means backup failed, including lock contention: alert and retry later;
never delete older backups after failure. Schedule independently at 03:30 Madrid
only after authorization. A backup timer must not invoke the updater. Store archives
outside app-writable directories and encrypt before transfer to a separate server
or private object store using a separately configured tool/destination. No external
credentials or destination are configured here. Keep encryption recovery keys off
VPS; verify a remote restore before treating backup as established.

Policy: retain 7 daily, 4 weekly and 3 monthly verified off-server snapshots; retain
at least 7 verified local archives if space permits. Keep checksum JSON with each
archive. Rotation is operator-reviewed, never automatic in these scripts. Protect
active recovery points until newer off-server restores have passed. Back up the
reviewed commit/release record, private production env and TLS directories separately
with mode 0600 and encryption; historical data/figures must remain recoverable too.
Certificates can be reissued, but repeated loss can encounter CA rate limits.

Restore to a **new** tree with the `storage.py restore` command from section 4,
then run preflight and runtime/package/gate checks. Never restore over the live
store. To switch to a restored tree, obtain maintenance authorization, stop only
the VPS updater, ensure it exited, change production env store/input paths, recreate
VPS readers/updater as appropriate and confirm active version/freshness. Preserve
old tree for rollback. These maintenance actions are not performed in this sprint.

Application versions/attempts have no automatic deletion: this deliberately
preserves validated history. Disk monitoring and capacity expansion are the initial
safeguards. Proposed policy, requiring explicit approval before implementation:
keep every active publication and rollback chain; archive old attempts after 90 days;
archive older publication versions off-server before any pruning. No source version,
attempt, staging file or archive is deleted by these tools. Review growth monthly;
public readiness requires an operator to act on disk warnings. `/tmp` is bounded
by existing tmpfs; Docker logs are capped at about 30 MB per service.

## 9. Monitoring and resource checks

Run on the VPS with the production env exported:

```bash
python3 deploy/production/monitor.py --disk-path /var/backups/riskbex
# After public launch:
python3 deploy/production/monitor.py --disk-path /var/backups/riskbex --public
```

JSON `ok=false` and exit 1 indicate failed/incomplete checks. The probe checks
container states/health/restarts, actual API and dashboard HTTP responses, API
freshness and latest pipeline status, last 30 hours of scheduler completion events,
missing timer slots (35-minute grace), runtime calendar expiry, and free space on
bind-mount/backup filesystems. Alert at <15% or <2 GiB free. It never downloads data,
writes state, starts containers or invokes an update. Treat a missing/stopped updater
as unhealthy even if readers work. Recently started containers are flagged until
10 minutes have elapsed; lack of scheduled evidence remains a warning until observed.

Install a five-minute monitoring-only cron/systemd timer only with authorization.
Use its exit code to notify an explicitly authorized destination or local journal.
External delivery is disabled: no destination, token or outbound notification code
is supplied. A probe without an operator/alert consumer is not active monitoring.
Docker health checks alone neither detect stale data nor restart unhealthy services.
Supplement with an external HTTPS uptime probe after public authorization; a local
probe cannot report total host loss. Log rotation can remove older evidence; keep
milestone publication records outside container logs.

Initial hard RAM ceilings: API 768 MiB, dashboard 1 GiB, updater 1.5 GiB, Caddy
128 MiB (3.375 GiB total), plus bounded tmpfs within cgroup accounting. CPU ceilings
are 0.75/0.75/1/0.25 respectively; oversubscription is intentional on two cores.
PID limits and single-threaded BLAS/OpenMP updater settings limit contention.
These are conservative starting safeguards, not measured peak guarantees; an OOM
kills work and must alert. Validate inference under these settings and adjust
before launch. Docker image build memory is not constrained by service limits:
build in a maintenance window or off-host if capacity is insufficient.

During a future authorized update and concurrent representative browser sessions:

```bash
sh deploy/production/compose.sh stats --no-stream
# Interactive sampling; stop with Ctrl-C (does not stop containers):
sh deploy/production/compose.sh stats
sh deploy/production/compose.sh logs --timestamps --tail=100 updater
```

Capture samples through the entire run, including process startup, historical
catch-up and simulator interaction. Inspect `docker inspect` State.OOMKilled,
RestartCount and host `free -h`/`df -h`. Persist measurements privately with times;
idle readings must not be presented as peak capacity validation.

## 10. Reboot, upgrade and rollback

Before a separately authorized VPS reboot, verify backup, `systemctl is-enabled
docker`, restart policy and enabled intended profiles. After reboot, use `ps`,
preflight and monitor; inspect next `timer_wait`. Wait for the next real scheduled
completion. RestartCount can reset after container recreation and does not prove
host uptime. Record reboot/release events separately. Never test reboots on WSL
as part of this sprint.

For an application upgrade: record current Git SHA and production env/image tags;
make and verify a backup; `git fetch origin`; review the diff and select a tested
SHA. Preserve ignored data/figures and private env. Verify the frozen receipt gate
before scheduling; implementation hash changes may invalidate the receipt. Never
edit hashes to bypass the gate. Generate a new receipt only after an authorized
regression check succeeds, into a separate file, preserving the historical receipt.

In an authorized VPS maintenance window, stop only the production updater:

```bash
sh deploy/production/compose.sh --profile scheduled stop updater
# Check out the reviewed new SHA; update RISKBEX_RELEASE in private env.
sh deploy/production/compose.sh build api dashboard
python3 deploy/production/preflight.py
# Repeat offline gate check from section 5 before starting the updater.
sh deploy/production/compose.sh up -d --wait api dashboard
# Only if previously authorized and gate passed:
sh deploy/production/compose.sh --profile scheduled up -d updater
```

Do not prune previous tagged images. On failure, select the prior reviewed checkout
and `RISKBEX_RELEASE`, verify prior images and compatible data/gate, recreate readers
and resume the authorized updater. If store format/receipt compatibility changed,
restore the matching backup to a new tree and switch explicit paths. Never blindly
reset `current.json`, overwrite a store or run `down -v`. Rollback must preserve
last valid artifacts and visibly stale status where applicable.

## Security limits and remaining acceptance checks

FastAPI GETs/docs/OpenAPI remain unauthenticated but network-internal. `/run-update`
remains disabled. No debug/reload mode, socket mount, privileged service or added
Linux capability is introduced. Caddy is non-root with all capabilities dropped.
Streamlit CORS/XSRF protection stays enabled, file watching is disabled and client
traceback details are suppressed only in production. Existing application errors
and provenance still include internal metadata; the proxy exposes only Streamlit,
but UI disclosure should be checked during private smoke tests. Do not expose
API docs as a public route or assume CORS is authentication.

No universal rate limiter is added. Long-lived WebSockets and expensive API snapshot
validation remain potential availability risks. Resource/PID limits and provider
firewall restrict damage; private concurrent-use tests must establish acceptable
capacity. Consider additional connection controls only if measurements warrant them.
Review pinned Caddy/base-image/dependency security updates before building; do not
upgrade quantitative dependencies without frozen-runtime validation. No vulnerability
scan or claim of vulnerability-free images is made by this sprint.

Pending on the VPS: actual builds, Caddy validation, TLS/renewal, HTTP/WebSocket
smoke tests, six-view compatibility, runtime permissions, loaded peak memory,
remote backup/restore drill, external alert destination, reboot/catch-up and
multi-day unattended evidence. Public-data scope and 2027 calendar remain separate
pre-launch/expiry gates.

References checked for infrastructure preparation:
- [Docker installation and firewall caveats](https://docs.docker.com/engine/install/ubuntu/)
- [Compose merge and reset behavior](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
- [Caddy global ports/timeouts](https://caddyserver.com/docs/caddyfile/options)
- [Caddy reverse proxy and WebSocket support](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)

## Sprint 10B local validation evidence

Fourteen focused infrastructure checks passed, including rendered production/local
Compose, missing environment rejection, mount policy, bounded logs, temporary-store
backup/restore, concurrent lock rejection, corrupted data, unsafe archives, public
placeholder rejection and monitoring failure states. The first Compose assertion
was corrected to accept numeric limits serialized as text; it then passed.
Twenty-five existing targeted calendar/provider/scheduler/pipeline tests passed,
including failure preservation, incomplete sessions and catch-up. No full suite ran.

Reproduce only when needed, from `backend`, using the existing approved Python
3.11.14 environment (replace the interpreter path on another host):

```bash
/home/apalo/miniconda3/envs/fin-forecasting/bin/python -B -m unittest \
  tests.test_production_infrastructure tests.test_container_scheduler \
  tests.test_scheduled_update tests.test_daily_pipeline.CalendarAndProviderTests \
  tests.test_daily_pipeline.PipelineTests.test_provider_failure_retains_current \
  tests.test_daily_pipeline.PipelineTests.test_incomplete_response \
  tests.test_daily_pipeline.PipelineTests.test_multi_session_catchup_and_interior_gap -v
```

Caddy is not installed locally and no image was pulled or started. Its binary
configuration validation and runtime TLS/WebSocket checks remain pending; text
inspection is not a substitute for that validation. Local containers retained
their 14 November start timestamps and zero restart counts at the final read-only
inspection. Local configuration, publications and operational inputs were not edited.
