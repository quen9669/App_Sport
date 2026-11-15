# The app's own door to your tailnet. It joins Tailscale as a separate device
# ("app-sport") and serves https://app-sport.<tailnet>.ts.net with a real
# certificate, then passes requests to the app container.
# No port is published on the VPS: nothing here touches the host or other projects.
FROM tailscale/tailscale:v1.90.6
# Coolify cannot mount single files (they become empty folders), so the
# HTTPS configuration is baked into the image instead.
COPY serve.json /config/serve.json
