import os
import subprocess
import logging
import time
import socket
from flask import Flask, request, Response, make_response
import requests
import urllib3

# --- Configuration from Environment Variables ---
try:
    NAS_MAC_ADDRESS = os.environ['NAS_MAC_ADDRESS']
    NAS_IP = os.environ['NAS_IP']
    NAS_PORT = int(os.environ['NAS_PORT']) # Convert port to integer
    NAS_SCHEME = os.environ.get('NAS_SCHEME', 'http').lower()
    WOL_PORT = int(os.environ.get('WOL_PORT', '9')) # Default to 9

    REFRESH_DELAY_SECONDS = int(os.environ.get('REFRESH_DELAY_SECONDS', '30')) # Delay before browser auto-refreshes
    QUICK_CHECK_TIMEOUT = float(os.environ.get('QUICK_CHECK_TIMEOUT', '0.5')) # Very short timeout for initial check (seconds)

    LISTEN_PORT = 5000
    WAKE_COMMAND = '/usr/bin/wakeonlan'

except KeyError as e:
    logging.error(f"FATAL: Missing mandatory environment variable: {e}")
    exit(1)
except ValueError as e:
    logging.error(f"FATAL: Configuration error: Port/Timeout/Delay variable is not a valid number - {e}")
    exit(1)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')

# --- Disable InsecureRequestWarning if using self-signed certs ---
if NAS_SCHEME == 'https':
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logging.warning("Disabled InsecureRequestWarning for upstream HTTPS requests.")
    except Exception:
        logging.error("Could not disable InsecureRequestWarning.")

# --- Flask App ---
app = Flask(__name__)

def is_nas_available_quick():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(QUICK_CHECK_TIMEOUT) # Use the very short timeout
        try:
            # Connect_ex returns 0 on success
            if sock.connect_ex((NAS_IP, NAS_PORT)) == 0:
                logging.info(f"Quick Check SUCCESS: NAS ({NAS_IP}:{NAS_PORT}) is available.")
                return True
            else:
                logging.info(f"Quick Check FAIL: NAS ({NAS_IP}:{NAS_PORT}) is not available yet.")
                return False
        except socket.error as e:
            logging.warning(f"Quick Check ERROR: Socket error checking {NAS_IP}:{NAS_PORT}: {e}")
            return False

def create_loading_page(requested_url):
    """Generates the static HTML loading page with a meta refresh tag."""
    logging.info(f"Generating Loading Page. Will refresh '{requested_url}' in {REFRESH_DELAY_SECONDS}s.")
    # Ensure URL is properly quoted for HTML attribute
    safe_url = requested_url.replace("'", "%27").replace('"', "%22")
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="{REFRESH_DELAY_SECONDS};url={safe_url}">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NAS Starting Up...</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen-Sans, Ubuntu, Cantarell, "Helvetica Neue", sans-serif; line-height: 1.6; text-align: center; padding: 40px 20px; background-color: #f4f4f4; color: #333; }}
            .container {{ max-width: 650px; margin: auto; padding: 30px; border: 1px solid #ddd; border-radius: 8px; background-color: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            h2 {{ color: #2c3e50; margin-bottom: 15px; }}
            p {{ margin-bottom: 20px; color: #555; }}
            .spinner {{ border: 5px solid #e0e0e0; border-top: 5px solid #3498db; border-radius: 50%; width: 45px; height: 45px; animation: spin 1.5s linear infinite; margin: 25px auto; }}
            code {{ background-color: #eee; padding: 2px 5px; border-radius: 3px; font-family: monospace; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>NAS Starting Up...</h2>
            <p>Attempting to wake your NAS at <code>{NAS_IP}</code>. This page will automatically refresh.</p>
            <div class="spinner"></div>
            <p>Please wait. If this page persists for more than a few minutes, please check the NAS directly.</p>
            <p><small>Refreshing to: <code>{safe_url}</code></small></p>
        </div>
    </body>
    </html>
    """
    response = make_response(html)
    response.status_code = 200 # Serve the loading page with a 200 OK status
    response.headers['Content-Type'] = 'text/html'
    response.headers['Cache-Control'] = 'no-store, must-revalidate' # Prevent caching
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# --- Proxy Function (Extracted for clarity) ---
def proxy_request_to_nas(request_id, original_request):
    target_path = original_request.path[1:] if original_request.path and original_request.path != '/' else '' # Get path relative to root
    target_url = f"{NAS_SCHEME}://{NAS_IP}:{NAS_PORT}/{target_path}"
    if original_request.query_string:
        target_url += '?' + original_request.query_string.decode('utf-8', 'ignore')

    logging.info(f"[{request_id}] Proxying request to target URL: {target_url}")

    try:
        # Prepare headers
        proxied_headers = {key: value for (key, value) in original_request.headers if key.lower() not in ['host', 'connection', 'keep-alive']}
        proxied_headers['Host'] = f"{NAS_IP}:{NAS_PORT}" # Set Host header for backend
        proxied_headers['X-Forwarded-For'] = original_request.headers.get('X-Forwarded-For', original_request.remote_addr)
        proxied_headers['X-Forwarded-Proto'] = original_request.scheme
        proxied_headers['X-Forwarded-Host'] = original_request.headers.get('Host', '')

        logging.debug(f"[{request_id}] Proxy Headers: {proxied_headers}")

        # Make the request to the NAS service
        resp = requests.request(
            method=original_request.method,
            url=target_url,
            headers=proxied_headers,
            data=original_request.get_data(),
            cookies=original_request.cookies,
            stream=True,
            verify=(NAS_SCHEME == 'https'), # Only verify if HTTPS
            timeout=(10, 120) # Connect timeout=10s, Read timeout=120s
        )

        logging.info(f"[{request_id}] Proxy RESPONSE: Received status {resp.status_code} from NAS.")

        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'server', 'date']
        response_headers = [(name, value) for (name, value) in resp.raw.headers.items()
                            if name.lower() not in excluded_headers]

        # Stream the response back
        response = Response(resp.raw, status=resp.status_code, headers=response_headers)
        logging.info(f"[{request_id}] Request END: Successfully proxied.")
        return response

    except requests.exceptions.ConnectionError as e:
        logging.error(f"[{request_id}] Proxying ERROR (Connection): {e}")
        # Maybe NAS went down *after* check? Return Bad Gateway.
        return "Bad Gateway: Connection Error while proxying to the NAS.", 502
    except requests.exceptions.Timeout as e:
        logging.error(f"[{request_id}] Proxying ERROR (Timeout): {e}")
        return "Gateway Timeout: Timeout while proxying to the NAS.", 504
    except requests.exceptions.RequestException as e:
        logging.error(f"[{request_id}] Proxying ERROR (Request): {e}", exc_info=True)
        return "Bad Gateway: General error while proxying to the NAS.", 502
    except Exception as e:
        logging.error(f"[{request_id}] Proxying ERROR (Unexpected): {e}", exc_info=True)
        return "Internal Server Error during proxy.", 500


# --- Main Request Handler ---
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
def catch_all(path):
    req_id = os.urandom(4).hex() # Simple request identifier
    # Get full original path including query string for redirects
    requested_url = request.full_path if request.full_path and request.full_path.startswith('/') else '/'
    logging.info(f"[{req_id}] Request START: {request.method} {requested_url} from {request.remote_addr}")

    # 1. Send Wake-on-LAN packet FIRST (Every time a request comes in)
    logging.info(f"[{req_id}] Sending WOL to {NAS_MAC_ADDRESS} on port {WOL_PORT}")
    try:
        cmd = [WAKE_COMMAND, '-p', str(WOL_PORT), NAS_MAC_ADDRESS]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
        logging.info(f"[{req_id}] WOL command finished. RC={result.returncode}")
        if result.stdout: logging.debug(f"[{req_id}] WOL Stdout: {result.stdout.strip()}")
        if result.stderr: logging.warning(f"[{req_id}] WOL Stderr: {result.stderr.strip()}") # Log stderr as warning
    except Exception as e:
        logging.error(f"[{req_id}] Non-fatal ERROR during WOL execution: {e}", exc_info=True)

    # 2. Perform QUICK check for NAS availability
    if is_nas_available_quick():
        # NAS is available, PROXY the request directly
        logging.info(f"[{req_id}] NAS Detected UP. Proceeding directly to proxy.")
        return proxy_request_to_nas(req_id, request)
    else:
        # NAS is NOT available (or check failed), return the LOADING PAGE
        logging.info(f"[{req_id}] NAS Detected DOWN or check failed. Returning loading page.")
        # Pass the *original requested URL* (e.g., '/files?id=123') to the loading page
        return create_loading_page(requested_url)

if __name__ == '__main__':
    logging.info(f"Starting WOL Trigger Service (Static Page Mode). NAS={NAS_SCHEME}://{NAS_IP}:{NAS_PORT}, MAC={NAS_MAC_ADDRESS}")
    logging.info(f"Config: WOL Port={WOL_PORT}, Refresh Delay={REFRESH_DELAY_SECONDS}s, Quick Check Timeout={QUICK_CHECK_TIMEOUT}s")
    app.run(host='0.0.0.0', port=LISTEN_PORT, threaded=True)