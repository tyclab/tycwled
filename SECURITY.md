# Security Policy

## Reporting a vulnerability

Please report security issues privately rather than opening a public issue.

- Preferred: open a private GitHub security advisory on this repository
  (Security tab → "Report a vulnerability").
- Alternative: email <security@tyclab.ai>.

Please do not file a public issue for a suspected vulnerability until it has
been triaged.

## Scope and expectations

This is a personal tool set, published so other lamp owners can use and check
it — not a supported product. There is no SLA and no bug bounty. Reports are
acknowledged on a best-effort basis, target within a week.

## What must never land in this repository

A WLED `cfg.json` carries the Wi-Fi SSID, the mDNS name (device MAC), the
NTP coordinates, integration IPs and paired remote MACs. The factory copy in
`glorb/factory-0.14.4-GLORB.1.3/cfg.json` is scrubbed; keep it that way, and
never commit a lamp's live cfg, a recording, a device backup or an API token.
`wledlab.py` writes neither the lamp's address nor its Wi-Fi details into a
capture; a capture is still a recording and stays in private storage.
`.gitignore` excludes `captures/`. `tools/check_private_lamp_data.py` reads the
content of every commit, at commit, at push and in CI, and refuses recordings,
backups and network details (MAC addresses, private addresses, Wi-Fi names,
coordinates); gitleaks scans content and history for credentials, which is all
it looks for. If you find such data in this repository's history, report it
the same way as any other vulnerability.
