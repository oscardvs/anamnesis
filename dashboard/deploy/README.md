# Hub deployment (PWA over the tailnet)

Run one always-on instance on the hub (odesha) and reach it from your phone and
laptop as an installable PWA.

## One-time setup

1. Build the standalone server:

   ```
   cd ~/anamnesis/dashboard && npm install && npm run build
   ```

2. Config:

   ```
   mkdir -p ~/.config/anamnesis
   cp deploy/dashboard.env.example ~/.config/anamnesis/dashboard.env
   # edit dashboard.env: fix PATH, ANAMNESIS_SERVER, ANAMNESIS_MACHINE_ID
   ```

3. Service:

   ```
   mkdir -p ~/.config/systemd/user
   cp deploy/anamnesis-dashboard.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now anamnesis-dashboard
   loginctl enable-linger "$USER"   # run without an active login
   ```

4. Publish on the tailnet (one-time; needs HTTPS certificates enabled in the
   Tailscale admin console):

   ```
   tailscale serve --bg 3000
   tailscale serve status   # shows https://odesha.tail4f2a4b.ts.net -> 127.0.0.1:3000
   ```

## Install as an app

- iPhone (Safari): open https://odesha.tail4f2a4b.ts.net, Share, Add to Home Screen.
- Laptop (Chrome/Edge): open the same URL, Install app from the address bar.

## Update

```
cd ~/anamnesis/dashboard && git pull && npm run build && \
  systemctl --user restart anamnesis-dashboard
```

## Security

The server binds `127.0.0.1` only (`scripts/serve.cjs` forces `HOSTNAME=127.0.0.1`),
so it is never on your LAN or the public internet. The only off-machine access is
`tailscale serve` (tailnet-only, authenticated by your tailnet). Do not use
`tailscale funnel`, which would expose it publicly.
