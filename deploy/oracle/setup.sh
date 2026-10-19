#!/bin/bash
# Prepara una VM Ubuntu (Oracle Cloud) para el backend: Docker + puertos 80/443 abiertos.
set -e
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi
# Las imágenes Ubuntu de Oracle traen reglas iptables que bloquean todo salvo SSH
for port in 80 443; do
  sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
    || sudo iptables -I INPUT 5 -p tcp --dport "$port" -j ACCEPT
done
sudo apt-get install -y iptables-persistent >/dev/null 2>&1 || true
sudo netfilter-persistent save 2>/dev/null || true
echo "Listo. Cierra la sesión SSH y vuelve a entrar para usar docker sin sudo."
