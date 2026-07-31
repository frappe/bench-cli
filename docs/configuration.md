# Configuration

`bench.toml` is the source of truth for a bench. Read and write it through the config model and TOML store. `BenchConfig` is also the sole reader/writer of `common_config.toml`, the host-shared file described in [Common Config](#common-config).

## Minimal Example

```toml
[bench]
name = "main"
python = "3.11"
http_port = 8000
socketio_port = 9000
socketio_backend = "node"
db_type = "mariadb"

[[apps]]
name = "frappe"
repo = "https://github.com/frappe/frappe"
branch = "version-15"

[redis]
cache_port = 13000
queue_port = 11000

[[workers]]
queues = ["default", "short", "long"]
count = 1
```

## `[bench]`

- `name`: required bench name.
- `python`: required Python version.
- `http_port`: web port for local runtime.
- `socketio_port`: websocket port.
- `socketio_backend`: `node` or `python`.
- `db_type`: `mariadb`, `postgres`, or `sqlite`.
- `default_branch`: optional branch default for new apps.
- `allow_developer_mode`: allows developer mode to be toggled per site. Developer mode itself stays in each site's `site_config.json`.
- `watch_apps_js`, `watch_admin_js`, `reload_python`: development toggles.

## Apps

Each `[[apps]]` entry records one app:

```toml
[[apps]]
name = "erpnext"
repo = "https://github.com/frappe/erpnext"
branch = "version-15"
branches = ["version-15", "develop"]
```

The first app is treated as the framework app when code needs that distinction.

## Databases

`config.mariadb` and `config.postgres` describe how a bench connects to the chosen engine. `existing = true` means the user supplied the service and Pilot should not infer or manage it as owned state. Both live in `common_config.toml`, not `bench.toml` - see [Common Config](#common-config).

One bench uses one database engine for its sites. Pick it with `bench.db_type`.

## Redis And Workers

`[redis]` has separate cache and queue ports. They must be distinct.

Workers use `[[workers]]` array entries:

```toml
[[workers]]
queues = ["default", "short", "long"]
count = 2
```

## Production

```toml
[production]
enabled = true
process_manager = "systemd"
use_companion_manager = false
```

Supported process managers are `systemd` and `supervisor`.

## Admin

```toml
[admin]
enabled = true
port = 7000
domain = "admin.example.com"
tls = true
allow_bench_management = true
```

`admin.internal_port` is derived as `port + 1` for the localhost Gunicorn service behind nginx.

`jwt_secret` is this bench's own local token signing secret, kept in `bench.toml`. `jwks_url` and `jwks_audience` trust a remote issuer instead and are host-shared - see [Common Config](#common-config).

## Other Groups

- `[monitor]`: per-bench `log_path` for this bench's own application metrics. The host-wide system/DB/slow-query log paths are fixed at `cli_root()/system/logs/*` and not configurable anywhere.
- `[gunicorn]`: Gunicorn process settings.
- `[central]`: Central endpoint and Pilot auth token.
- `[firewall]`: firewall behavior.
- `[waf]`: WAF behavior.
- `[s3]`: S3 backup credentials and bucket settings.
- `[llm]`: LLM provider settings used by the admin assistant.

Nginx has no per-bench `bench.toml` section - `config.nginx` always holds its compiled-in defaults (ports 80/443, platform-default `config_dir`, etc.); nothing in `bench.toml` can override it.

Unknown fields are ignored by normal loads for compatibility. Strict validation can report unknown config paths.

## Common Config

Some settings are shared by every bench under one benches directory, not owned by any single bench: one MariaDB server, one Postgres server, one ACME account, one trusted admin JWKS issuer. These live in `common_config.toml`, next to the bench folders, not in any bench's own `bench.toml`:

```toml
[mariadb]
host = "localhost"
port = 3306
admin_user = "root"
root_password = ""
socket_path = ""
existing = false

[postgres]
host = "localhost"
port = 5432
admin_user = "postgres"
root_password = ""
existing = false

[letsencrypt]
email = "ops@example.com"
webroot_path = "/var/www/letsencrypt"

[admin]
jwks_url = "https://issuer.example.com/jwks.json"
jwks_audience = "bench-fleet"
```

`BenchConfig` is the only reader/writer of this file - it merges these values into `config.mariadb`, `config.postgres`, `config.letsencrypt`, and `config.admin.jwks_url`/`jwks_audience` on every read, and writes them back on save. Other code reaches these values through a bench's own `BenchConfig`, never by reading `common_config.toml` directly. `admin.tls` is not part of this file - it stays a per-bench choice in `bench.toml`.

The host-wide system/DB/slow-query monitor log paths (`system_log_path`/`db_log_path`/`slow_query_log_path`) are not configurable at all, in `bench.toml` or `common_config.toml` - they're fixed at `cli_root()/system/logs/{system-stats.log,db-stats.log,slow-queries.json}` (see `pilot/config/monitor.py`).

A pre-upgrade bench whose `bench.toml` still carries these fields directly is migrated by the `merge_common_config` patch - see [pilot/patches](../pilot/patches) and `pilot admin run-patches`. Until that patch runs, a host with no `common_config.toml` reads these tables from each bench's own `bench.toml`, so an unmigrated bench keeps the servers and credentials it was set up with instead of falling back to the defaults.
