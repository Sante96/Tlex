# Cloudflare Tunnel Setup

Cloudflare Tunnel permette di esporre TLEX su HTTPS senza port forwarding.

## Prerequisiti

1. Account Cloudflare (gratuito)
2. Dominio configurato su Cloudflare
3. `cloudflared` installato

## Installazione cloudflared

### Windows

```powershell
winget install Cloudflare.cloudflared
```

### Linux/macOS

```bash
# macOS
brew install cloudflared

# Linux (Debian/Ubuntu)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
```

## Setup Tunnel

### 1. Login a Cloudflare

```bash
cloudflared tunnel login
```

Questo apre il browser per autenticarti.

### 2. Crea il Tunnel

```bash
cloudflared tunnel create tlex
```

Output: `Created tunnel tlex with id <TUNNEL_ID>`

### 3. Configura il DNS

```bash
cloudflared tunnel route dns tlex tlex.tuodominio.com
```

### 4. Crea config file

Crea `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_ID>
credentials-file: ~/.cloudflared/<TUNNEL_ID>.json

ingress:
  # Backend API
  - hostname: api.tlex.tuodominio.com
    service: http://localhost:8000
  # Frontend
  - hostname: tlex.tuodominio.com
    service: http://localhost:3000
  # Catch-all (required)
  - service: http_status:404
```

### 5. Ottieni il Token

```bash
cloudflared tunnel token tlex
```

Copia il token e aggiungilo a `.env`:

```
CLOUDFLARE_TUNNEL_TOKEN=<il_tuo_token>
```

## Avvio

### Manuale

```bash
cloudflared tunnel run tlex
```

### Con Docker Compose

Il tunnel è già configurato in `docker-compose.yml`:

```bash
docker-compose up -d cloudflared
```

## Verifica

1. Vai su https://tlex.tuodominio.com
2. Verifica che il sito sia raggiungibile
3. Controlla i log: `docker logs tlex-cloudflared`

## Troubleshooting

### Tunnel non si connette

- Verifica il token in `.env`
- Controlla che il tunnel esista: `cloudflared tunnel list`

### 502 Bad Gateway

- Verifica che backend/frontend siano in esecuzione
- Controlla che le porte siano corrette nel config

### Certificato non valido

- Cloudflare genera automaticamente certificati SSL
- Se usi un dominio custom, verifica che sia su Cloudflare DNS
