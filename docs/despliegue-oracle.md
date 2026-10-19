# Despliegue del backend en Oracle Cloud (Always Free)

Backend FastAPI + Ollama en una VM ARM gratuita, con HTTPS por Caddy y un subdominio de DuckDNS. El frontend sigue en Vercel.

## 1. Crear la VM
1. Cuenta en https://cloud.oracle.com (pide tarjeta solo para verificar; no se cobra en Always Free). Elige una *home region* con capacidad ARM.
2. *Compute → Instances → Create instance*:
   - Imagen: **Ubuntu 22.04** (aarch64).
   - Shape: **VM.Standard.A1.Flex** con **4 OCPU y 24 GB** (el máximo gratuito).
   - Genera y descarga la clave SSH. Anota la **IP pública**.
   - Si da "Out of capacity", reintenta más tarde o prueba otra zona de disponibilidad.
3. Volumen de arranque: 100 GB (límite gratuito 200 GB en total).
4. *Networking → Virtual Cloud Network → Security Lists → Add Ingress Rules*: origen `0.0.0.0/0`, TCP, puertos **80** y **443**.

## 2. Subdominio gratuito (necesario para HTTPS)
1. En https://www.duckdns.org crea un subdominio, p.ej. `hextech-archive.duckdns.org`, apuntando a la IP pública de la VM.

## 3. Preparar la VM
```bash
ssh -i <clave> ubuntu@<IP>
git clone https://github.com/0racleX/HextechArchive.git && cd HextechArchive
bash deploy/oracle/setup.sh        # instala Docker y abre 80/443 en iptables
exit                               # vuelve a entrar para usar docker sin sudo
```

## 4. Configurar y arrancar
```bash
ssh -i <clave> ubuntu@<IP> && cd HextechArchive/deploy/oracle
cp .env.example .env && nano .env  # DOMAIN, DATABASE_URL, JWKS/JWT, CORS_ORIGINS
docker compose up -d --build       # el primer build tarda (descarga los modelos)
docker compose logs -f backend
```
Comprobación: `curl https://<DOMAIN>/health` → `{"status":"ok","auth_configured":true}`.

## 5. Datos y frontend
- En Supabase aplica `001_init.sql` y `002_content_hash.sql`.
- Carga el corpus: `docker compose exec backend python -m scripts.seed_corpus`.
- En Vercel: `VITE_API_URL=https://<DOMAIN>`; en `CORS_ORIGINS` pon la URL exacta de Vercel y ejecuta `docker compose up -d` para recargar.

## Notas
- La inferencia en ARM de 4 núcleos es más lenta que en GPU: espera unos segundos hasta el primer token.
- Actualizar: `git pull && docker compose up -d --build`.
- Nunca subas `.env` al repositorio (está en `.gitignore`).
