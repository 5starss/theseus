# Theseus Production Nginx

This directory contains the production reverse proxy bootstrap config.

## Bootstrap HTTP

Start the HTTP-only proxy first. This serves the frontend and the ACME webroot
without requiring certificate files to exist.

```bash
docker compose --env-file .env -f docker-compose.prod.yml config --quiet
docker compose --env-file .env -f docker-compose.prod.yml up -d --build theseus-nginx
```

Check the frontend and ACME webroot:

```bash
curl -I http://k14a308.p.ssafy.io
mkdir -p certbot/www/.well-known/acme-challenge
echo ok > certbot/www/.well-known/acme-challenge/test
curl -i http://k14a308.p.ssafy.io/.well-known/acme-challenge/test
```

## Issue Certificate

Run certbot from `infra/docker/prod`:

```bash
docker compose --env-file .env -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  -d k14a308.p.ssafy.io \
  --email <admin-email> \
  --agree-tos \
  --no-eff-email
```

## Enable HTTPS

After the certificate exists, replace the active HTTP bootstrap config with the
HTTPS config:

```bash
mv nginx/conf.d/theseus.http.conf nginx/conf.d/theseus.http.conf.disabled
cp nginx/conf.d/theseus.https.conf.example nginx/conf.d/theseus.https.conf
docker compose --env-file .env -f docker-compose.prod.yml restart theseus-nginx
```

Verify:

```bash
curl -I https://k14a308.p.ssafy.io
curl -i https://k14a308.p.ssafy.io/api/v1/auth/login
curl -i -X POST https://k14a308.p.ssafy.io/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"loginId":"admin001","password":"1234"}'
```

`GET /api/v1/auth/login` may return `405` or `403`; the important part is that
it reaches Nginx/API instead of failing with connection refused.

Certificate renewal can reuse the same webroot volume:

```bash
docker compose --env-file .env -f docker-compose.prod.yml run --rm certbot renew
docker compose --env-file .env -f docker-compose.prod.yml restart theseus-nginx
```
