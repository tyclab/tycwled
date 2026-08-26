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
never commit a lamp's live cfg, a capture with hostnames, or an API token.
`.gitignore` excludes `captures/`; the pre-commit and CI gitleaks jobs scan
content and history. If you find such data in this repository's history,
report it the same way as any other vulnerability.
