# WOL-Flask

A Flask application that acts as a Wake-on-LAN trigger and proxy for your NAS. When you access the service, it sends a WOL packet to wake up your NAS, then proxies requests to it once it's online. If the NAS is still booting, it shows a loading page that auto-refreshes.

## Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/hunmac9/wol-flask.git
   cd wol-flask
   ```

2. **Configure your NAS details:**
   Edit `docker-compose.yml` and set the required environment variables:
   ```yaml
   environment:
     - NAS_MAC_ADDRESS=XX:XX:XX:XX:XX:XX  # Your NAS MAC address
     - NAS_IP=192.168.1.100              # Your NAS IP address  
     - NAS_PORT=5000                     # Your NAS service port
   ```

3. **Run with Docker Compose:**
   ```bash
   docker compose up -d
   ```

4. **Access the service:**
   Navigate to `http://localhost:5000` (or your server's IP) to trigger WOL and access your NAS. Reverse proxy this (prefferably behind auth) to remotely trigger wol. 
