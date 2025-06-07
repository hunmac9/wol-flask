# WOL-Flask

A Flask-based Wake-on-LAN trigger and proxy for your NAS. Sends WOL packets on request, then proxies to your NAS once online.

## Setup

1. **Clone repository (requires Git):**
   ```bash
   git clone https://github.com/hunmac9/wol-flask.git
   cd wol-flask
   ```

2. **Configure NAS details in `docker-compose.yml`:**
   ```yaml
   environment:
     - NAS_MAC_ADDRESS=XX:XX:XX:XX:XX:XX  # Required
     - NAS_IP=192.168.1.100               # Required
     - NAS_PORT=5000                      # Required
     # Optional settings:
     - NAS_SCHEME=http                    # http/https
     - WOL_PORT=9                         # WOL port
     - REFRESH_DELAY_SECONDS=30           # Page refresh delay
     - QUICK_CHECK_TIMEOUT=0.5            # NAS check timeout
     # - TZ=Your/Timezone                # Timezone
   ```

3. **Start service:**
   ```bash
   docker compose up -d --build  # Use --build after code changes
   ```

4. **Access:**
   - Use `http://localhost:5000` (or your server's IP)
   - For domains, set up a reverse proxy (like Nginx or Caddy) pointing to this service

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `NAS_SCHEME` | `http` | NAS protocol (`http`/`https`) |
| `WOL_PORT` | `9` | WOL destination port |
| `REFRESH_DELAY_SECONDS` | `30` | Loading page refresh delay |
| `QUICK_CHECK_TIMEOUT` | `0.5` | NAS availability check timeout |
| `TZ` | - | Timezone (e.g. `America/New_York`) |

## Notes
- The `--build` flag is needed after making code changes
- For domain access, configure a reverse proxy (Nginx/Caddy recommended)
- Run behind authentication for security
