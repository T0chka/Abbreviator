# Production deployment

The production instance runs Django under Gunicorn, proxied by nginx at
`/abbreviator/`. A systemd timer removes expired documents and Django
session records.

## Files

- `systemd/abbreviator.service` — Gunicorn service.
- `systemd/abbreviator-cleanup.service` — expired-document and Django session cleanup job.
- `systemd/abbreviator-cleanup.timer` — runs cleanup every 5 minutes.
- `nginx/abbreviator.conf` — nginx location block for the application.
- `deploy-abbreviator` — production update script.

The checked-in paths match the current production host and can be adjusted for
another deployment.

## Environment

Secrets are stored in the project `.env` file and are not committed. Production
requires `SECRET_KEY` and the GigaChat settings used by the application.

## systemd

Copy the units to `/etc/systemd/system/`, reload systemd, then enable the
application and cleanup timer:

```bash
sudo cp deploy/systemd/abbreviator.service /etc/systemd/system/
sudo cp deploy/systemd/abbreviator-cleanup.service /etc/systemd/system/
sudo cp deploy/systemd/abbreviator-cleanup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now abbreviator.service
sudo systemctl enable --now abbreviator-cleanup.timer
```

## nginx

Add the contents of `nginx/abbreviator.conf` to the HTTPS `server` block for
`datadelic.dev`, then validate and reload nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Static files are collected to
`/home/tonia/datadelic.dev/static-root/public/abbrstatic/`, which is under the
existing nginx document root.

## Deploy command

Install the deployment helper:

```bash
sudo cp deploy/deploy-abbreviator /usr/local/bin/deploy-abbreviator
sudo chmod +x /usr/local/bin/deploy-abbreviator
```

Deploy with:

```bash
deploy-abbreviator
```
