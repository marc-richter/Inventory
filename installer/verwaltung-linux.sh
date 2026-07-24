#!/bin/bash
# ============================================================
# Inventarprogramm - Verwaltung (Linux)
# Eine App fuer: Uebersicht, Starten/Stoppen, Erstinstallation/
# Update und Deinstallation.
# ============================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; BOLD="\033[1m"; NC="\033[0m"

BACKUPS_DIR="$PROJECT_DIR/backups"
CERTS_DIR="$PROJECT_DIR/certs"
VERSION_FILE="$PROJECT_DIR/VERSION"
MARKER_FILE="$BACKUPS_DIR/.installed_version"
AUTOSTART_UNIT="$HOME/.config/systemd/user/inventarprogramm.service"
SUDO=""

line() { echo "------------------------------------------------------------"; }
pause() { read -r -p "Enter druecken zum Fortfahren..." _; }
confirm() {
  local answer
  read -r -p "$1 [j/N]: " answer
  [ "$answer" = "j" ] || [ "$answer" = "J" ] || [ "$answer" = "y" ] || [ "$answer" = "Y" ]
}

# ------------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------------
docker_installed() { command -v docker >/dev/null 2>&1; }
compose_ready() { $SUDO docker compose version >/dev/null 2>&1; }

update_sudo_mode() {
  SUDO=""
  if ! docker info >/dev/null 2>&1; then
    if sudo -n docker info >/dev/null 2>&1; then
      SUDO="sudo"
    else
      SUDO="sudo"
    fi
  fi
}

docker_ready() {
  docker_installed || return 1
  update_sudo_mode
  $SUDO docker info >/dev/null 2>&1
}

ensure_docker_running() {
  if ! docker_installed; then
    echo -e "${YELLOW}Docker wurde auf diesem System nicht gefunden.${NC}"
    if confirm "Soll Docker jetzt automatisch installiert werden? (benoetigt sudo)"; then
      echo "Installiere Docker ueber das offizielle Installationsskript (get.docker.com)..."
      curl -fsSL https://get.docker.com | sudo sh
      if command -v docker >/dev/null 2>&1; then
        sudo usermod -aG docker "$USER"
        echo -e "${YELLOW}Bitte einmal ab-/anmelden (oder neu starten), damit die Gruppe aktiv wird,"
        echo -e "danach dieses Menue erneut oeffnen.${NC}"
      else
        echo -e "${RED}Docker-Installation fehlgeschlagen. Bitte manuell installieren:${NC}"
        echo "https://docs.docker.com/engine/install/"
      fi
    else
      echo "Bitte Docker manuell installieren: https://docs.docker.com/engine/install/"
    fi
    return 1
  fi

  if ! docker_ready; then
    echo -e "${YELLOW}Der Docker-Dienst laeuft nicht oder du hast keine Rechte dafuer.${NC}"
    echo "Versuche den Dienst zu starten (evtl. sudo-Passwort noetig)..."
    sudo systemctl start docker 2>/dev/null
    sleep 2
    if ! docker_ready; then
      echo -e "${RED}Docker ist weiterhin nicht erreichbar.${NC}"
      echo "Bitte pruefen: 'sudo systemctl status docker' bzw. Mitgliedschaft in Gruppe 'docker'."
      return 1
    fi
  fi

  if ! compose_ready; then
    echo -e "${RED}Das 'docker compose' Plugin wurde nicht gefunden.${NC}"
    echo "Bitte 'docker-compose-plugin' ueber die Paketverwaltung installieren."
    return 1
  fi
  return 0
}

get_local_ip() {
  local ip
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [ -z "$ip" ]; then ip="$(ip route get 1 2>/dev/null | awk '{print $7; exit}')"; fi
  echo "$ip"
}

open_browser() {
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$1" >/dev/null 2>&1 &
  fi
}

load_env() {
  if [ -f "$PROJECT_DIR/.env" ]; then
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env" 2>/dev/null || true
  fi
  WEB_PORT="${WEB_PORT:-8080}"
  WEB_TLS_PORT="${WEB_TLS_PORT:-8443}"
}

is_installed() { [ -f "$PROJECT_DIR/.env" ]; }

is_running() {
  docker_ready || return 1
  local state
  state="$($SUDO docker compose ps --status running -q 2>/dev/null)"
  [ -n "$state" ]
}

installed_version() {
  if [ -f "$MARKER_FILE" ]; then cat "$MARKER_FILE" 2>/dev/null; else echo "nicht installiert"; fi
}

available_version() {
  if [ -f "$VERSION_FILE" ]; then cat "$VERSION_FILE" 2>/dev/null | tr -d '[:space:]'; else echo "unbekannt"; fi
}

human_size() {
  if [ -e "$1" ]; then du -sh "$1" 2>/dev/null | awk '{print $1}'; else echo "-"; fi
}

data_volume_size() {
  docker_ready || { echo "-"; return; }
  local cid vol
  cid="$($SUDO docker compose ps -a -q backend 2>/dev/null)"
  [ -z "$cid" ] && { echo "-"; return; }
  vol="$($SUDO docker inspect "$cid" --format '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}' 2>/dev/null)"
  [ -z "$vol" ] && { echo "-"; return; }
  $SUDO docker run --rm -v "$vol:/data" alpine:3.19 du -sh /data 2>/dev/null | awk '{print $1}'
}

images_size() {
  docker_ready || { echo "-"; return; }
  $SUDO docker compose config --images 2>/dev/null | while IFS= read -r img; do
    [ -z "$img" ] && continue
    local size_kb
    size_kb="$($SUDO docker images "$img" --format '{{.Size}}' 2>/dev/null | head -n1)"
    [ -n "$size_kb" ] && echo "     - $img: $size_kb"
  done
}

wait_for_health() {
  local port="$1" tries="${2:-40}" i
  for i in $(seq 1 "$tries"); do
    if curl -sf -o /dev/null -m 2 "http://localhost:${port}/api/health"; then return 0; fi
    sleep 2
  done
  return 1
}

ensure_cert() {
  mkdir -p "$CERTS_DIR"
  if [ ! -f "$CERTS_DIR/cert.pem" ] || [ ! -f "$CERTS_DIR/key.pem" ]; then
    echo "Erzeuge selbstsigniertes HTTPS-Zertifikat (einmalig)..."
    local cert_ip; cert_ip="$(get_local_ip)"
    [ -z "$cert_ip" ] && cert_ip="127.0.0.1"
    $SUDO docker run --rm -v "$CERTS_DIR:/certs" alpine:3.19 sh -c "
      apk add --no-cache openssl >/dev/null 2>&1
      openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
        -keyout /certs/key.pem -out /certs/cert.pem \
        -subj '/CN=inventarprogramm' \
        -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1,IP:${cert_ip}'
    " >/dev/null 2>&1
  fi
}

write_marker() { mkdir -p "$BACKUPS_DIR"; available_version > "$MARKER_FILE" 2>/dev/null; }

print_access_info() {
  load_env
  local ip; ip="$(get_local_ip)"
  echo "Auf diesem Rechner erreichbar unter:"
  echo "   http://localhost:${WEB_PORT}"
  if [ -n "$ip" ]; then
    echo ""
    echo "Auf Handys/anderen Rechnern im selben Netzwerk erreichbar unter:"
    echo "   http://${ip}:${WEB_PORT}"
    echo ""
    echo "Fuer Kamera-/Barcode-Scan auf dem Handy bitte HTTPS verwenden:"
    echo "   https://${ip}:${WEB_TLS_PORT}"
    echo "   (Zertifikatswarnung einmalig bestaetigen: 'Erweitert' -> 'Trotzdem fortfahren')"
  fi
}

# ------------------------------------------------------------------
# Hauptaktionen
# ------------------------------------------------------------------
action_status() {
  clear
  line
  echo -e " ${BOLD}Inventarprogramm - Uebersicht${NC}"
  line
  echo "Projektverzeichnis: $PROJECT_DIR"
  echo ""

  if ! is_installed; then
    echo -e "${YELLOW}Es ist noch keine Installation vorhanden.${NC}"
    echo "Bitte zuerst im Menuepunkt 'Erweitert' -> 'Erstinstallation / Update' einrichten."
    echo ""; line; pause; return
  fi

  load_env
  local inst_ver avail_ver running_txt
  inst_ver="$(installed_version)"
  avail_ver="$(available_version)"
  if is_running; then running_txt="${GREEN}laeuft${NC}"; else running_txt="${YELLOW}gestoppt${NC}"; fi

  echo -e "Status:               ${running_txt}"
  echo   "Installierte Version: $inst_ver"
  echo   "Verfuegbare Version:  $avail_ver"
  if [ "$inst_ver" != "$avail_ver" ] && [ "$inst_ver" != "nicht installiert" ]; then
    echo -e "                       ${YELLOW}-> Update verfuegbar (siehe 'Erweitert')${NC}"
  fi
  echo ""
  echo "Adresse (lokal):       http://localhost:${WEB_PORT}"
  local ip; ip="$(get_local_ip)"
  if [ -n "$ip" ]; then
    echo "Adresse (Netzwerk):    http://${ip}:${WEB_PORT}"
    echo "Adresse (HTTPS/Kamera):https://${ip}:${WEB_TLS_PORT}"
  fi
  echo ""
  echo "Speicherbelegung:"
  echo "   Datenbank/Bilder (Docker-Volume): $(data_volume_size)"
  echo "   Backup-Ordner (./backups):        $(human_size "$BACKUPS_DIR")"
  echo "   HTTPS-Zertifikate (./certs):      $(human_size "$CERTS_DIR")"
  echo "   Docker-Images:"
  images_size
  echo ""
  line
  pause
}

action_start() {
  clear
  line
  echo -e " ${BOLD}Inventarprogramm - Starten${NC}"
  line
  if ! is_installed; then
    echo -e "${RED}Es ist noch keine Installation vorhanden.${NC}"
    echo "Bitte zuerst 'Erweitert' -> 'Erstinstallation / Update' ausfuehren."
    pause; return
  fi
  ensure_docker_running || { pause; return; }
  load_env
  ensure_cert
  echo "Starte die Anwendung..."
  $SUDO docker compose up -d
  echo ""
  echo "Warte, bis die Anwendung erreichbar ist..."
  if wait_for_health "$WEB_PORT" 40; then
    echo -e "${GREEN}Die Anwendung laeuft.${NC}"
  else
    echo -e "${YELLOW}Die Anwendung antwortet noch nicht ganz - kurz warten und Seite neu laden.${NC}"
  fi
  echo ""
  print_access_info
  echo ""
  open_browser "http://localhost:${WEB_PORT}"
  line
  pause
}

action_stop() {
  clear
  line
  echo -e " ${BOLD}Inventarprogramm - Stoppen${NC}"
  line
  if ! docker_ready || ! is_running; then
    echo "Die Anwendung laeuft bereits nicht (mehr)."
    pause; return
  fi
  echo "Die Anwendung wird gestoppt (Daten und Einstellungen bleiben erhalten)..."
  $SUDO docker compose stop
  echo -e "${GREEN}Die Anwendung wurde gestoppt.${NC}"
  pause
}

# --- Erweitert: Erstinstallation / Update -------------------------
run_fresh_install() {
  echo ""
  echo "Es wird eine neue Konfigurationsdatei (.env) erstellt."
  echo "Fuer jede Frage kann einfach Enter gedrueckt werden, um die"
  echo "vorgeschlagene Standardeinstellung zu uebernehmen."
  echo ""

  local secret_key default_admin_username generated_pw input_pw default_admin_password
  local input_port web_port input_backup backup_host_path input_tls_port web_tls_port

  secret_key="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c 48)"
  [ -z "$secret_key" ] && secret_key="$(date +%s)-$$-${RANDOM}-${RANDOM}"

  default_admin_username="admin"
  read -r -p "Administrator-Benutzername [admin]: " input_admin_user
  [ -n "$input_admin_user" ] && default_admin_username="$input_admin_user"

  generated_pw="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c 12)"
  read -r -s -p "Administrator-Passwort festlegen (Enter = zufaelliges Passwort erzeugen): " input_pw
  echo ""
  if [ -n "$input_pw" ]; then
    default_admin_password="$input_pw"
  else
    default_admin_password="$generated_pw"
    echo -e "${YELLOW}Es wurde folgendes Passwort erzeugt: ${default_admin_password}${NC}"
    echo "Bitte notieren! Es wird am Ende noch einmal angezeigt."
  fi

  read -r -p "Port fuer die Weboberflaeche im lokalen Netz [8080]: " input_port
  web_port="${input_port:-8080}"

  read -r -p "Verzeichnis fuer Backups [./backups]: " input_backup
  backup_host_path="${input_backup:-./backups}"

  read -r -p "Port fuer HTTPS-Zugriff (Kamera-/Barcode-Scan) [8443]: " input_tls_port
  web_tls_port="${input_tls_port:-8443}"

  # --- Personalisierung (optional, mit Zeitlimit) ---
  # Organisationsname und Logo lassen sich hier bereits vorbelegen, damit direkt
  # nach der Installation ein fertig personalisiertes Produkt bereitsteht. Erfolgt
  # binnen 60 Sekunden keine Eingabe, wird von einer unbeaufsichtigten
  # (Remote-)Installation ausgegangen und ohne diese Werte fortgefahren - der
  # Administrator wird dann spaeter in der App per Popup daran erinnert.
  local pers_org_name="" pers_logo_env="" input_org input_logo unattended=0
  echo ""
  echo "Personalisierung (optional - je 60 Sekunden Zeit, sonst wird uebersprungen):"
  if read -r -t 60 -p "Organisationsname (erscheint in Kopfzeile/Login), leer lassen fuer spaeter: " input_org; then
    pers_org_name="$input_org"
  else
    unattended=1
    echo ""
    echo -e "${YELLOW}Keine Eingabe - unbeaufsichtigte Installation, Personalisierung wird uebersprungen.${NC}"
  fi
  if [ "$unattended" -eq 0 ]; then
    if read -r -t 60 -p "Pfad zu einer Logo-Datei (PNG/JPG/SVG/WEBP), leer lassen fuer spaeter: " input_logo; then
      if [ -n "$input_logo" ] && [ -f "$input_logo" ]; then
        local logo_ext_lc logo_dest_ext
        logo_ext_lc="$(printf '%s' "${input_logo##*.}" | tr '[:upper:]' '[:lower:]')"
        case "$logo_ext_lc" in
          png) logo_dest_ext=".png";; jpg|jpeg) logo_dest_ext=".jpg";; svg) logo_dest_ext=".svg";; webp) logo_dest_ext=".webp";; *) logo_dest_ext="";;
        esac
        if [ -n "$logo_dest_ext" ]; then
          mkdir -p "$PROJECT_DIR/config"
          if cp "$input_logo" "$PROJECT_DIR/config/logo${logo_dest_ext}" 2>/dev/null; then
            pers_logo_env="/app/initial/logo${logo_dest_ext}"
            echo -e "${GREEN}Logo uebernommen.${NC}"
          else
            echo -e "${YELLOW}Logo konnte nicht kopiert werden - wird uebersprungen.${NC}"
          fi
        else
          echo -e "${YELLOW}Nicht unterstuetztes Format - Logo wird uebersprungen (nur PNG/JPG/SVG/WEBP).${NC}"
        fi
      elif [ -n "$input_logo" ]; then
        echo -e "${YELLOW}Datei nicht gefunden - Logo wird uebersprungen.${NC}"
      fi
    else
      echo ""
      echo -e "${YELLOW}Keine Eingabe - Logo wird uebersprungen (spaeter in der App nachtragbar).${NC}"
    fi
  fi

  cat > "$PROJECT_DIR/.env" << EOF
SECRET_KEY=${secret_key}
DEFAULT_ADMIN_USERNAME=${default_admin_username}
DEFAULT_ADMIN_PASSWORD=${default_admin_password}
ACCESS_TOKEN_EXPIRE_MINUTES=720
WEB_PORT=${web_port}
WEB_TLS_PORT=${web_tls_port}
BACKUP_HOST_PATH=${backup_host_path}
DEFAULT_ORG_NAME=${pers_org_name}
DEFAULT_LOGO_FILE=${pers_logo_env}
EOF

  echo -e "${GREEN}Konfigurationsdatei .env wurde erstellt.${NC}"
  echo ""

  ensure_cert

  echo "Container werden gebaut und gestartet - das kann beim ersten Mal"
  echo "einige Minuten dauern..."
  line
  $SUDO docker compose up -d --build
  local build_status=$?
  line
  if [ $build_status -ne 0 ]; then
    echo -e "${RED}Beim Starten der Container ist ein Fehler aufgetreten. Bitte Ausgabe oben pruefen.${NC}"
    return 1
  fi

  load_env
  echo "Warte, bis die Anwendung erreichbar ist..."
  if wait_for_health "$WEB_PORT" 60; then
    echo -e "${GREEN}Die Anwendung laeuft.${NC}"
  else
    echo -e "${YELLOW}Die Anwendung antwortet noch nicht ganz - kurz warten und Seite neu laden.${NC}"
  fi
  write_marker

  # Autostart optional einrichten (mit Zeitlimit fuer unbeaufsichtigte Installation)
  echo ""
  if command -v systemctl >/dev/null 2>&1; then
    if read -r -t 60 -p "Soll die Anwendung kuenftig automatisch beim Booten starten (Autostart)? [j/N]: " autostart_ans; then
      case "$autostart_ans" in j|J|y|Y) enable_autostart ;; esac
    else
      echo ""
      echo "(Keine Eingabe - Autostart nicht eingerichtet; jederzeit im Menue Punkt 5 aenderbar.)"
    fi
  fi

  echo ""
  if confirm "Moechtest du jetzt ein vorhandenes Komplett-Backup einspielen (statt der leeren Erstinstallation)?"; then
    action_restore
  fi

  echo ""
  line
  echo -e "${GREEN}Fertig! Das Inventarprogramm laeuft jetzt.${NC}"
  line
  print_access_info
  echo ""
  if [ -n "${default_admin_password:-}" ]; then
    echo "Erster Login:"
    echo "   Benutzername: ${default_admin_username}"
    echo "   Passwort:     ${default_admin_password}"
    echo ""
    echo "Bitte nach dem ersten Login unter 'Mein Konto' Passwort/PIN aendern!"
  fi
  open_browser "http://localhost:${web_port}"
}

run_update_existing() {
  echo ""
  echo "Update wird durchgefuehrt - alle Daten (Datenbank, Bilder, Backups,"
  echo "Konfiguration) bleiben vollstaendig erhalten."
  ensure_docker_running || return 1
  ensure_cert
  $SUDO docker compose up -d --build
  local status=$?
  if [ $status -ne 0 ]; then
    echo -e "${RED}Beim Update ist ein Fehler aufgetreten. Bitte Ausgabe oben pruefen.${NC}"
    return 1
  fi
  load_env
  echo "Warte, bis die Anwendung erreichbar ist..."
  wait_for_health "$WEB_PORT" 60 && echo -e "${GREEN}Update abgeschlossen. Die Anwendung laeuft.${NC}" \
    || echo -e "${YELLOW}Update abgeschlossen, Anwendung antwortet aber noch nicht ganz.${NC}"
  write_marker
}

run_reinstall_keep_data() {
  echo ""
  echo "Neuinstallation (Daten bleiben erhalten): Container und Images werden"
  echo "entfernt und komplett neu gebaut. Datenbank, Bilder, Backups und die"
  echo ".env-Konfiguration bleiben erhalten."
  ensure_docker_running || return 1
  $SUDO docker compose down --rmi all 2>/dev/null
  ensure_cert
  $SUDO docker compose up -d --build
  local status=$?
  if [ $status -ne 0 ]; then
    echo -e "${RED}Bei der Neuinstallation ist ein Fehler aufgetreten. Bitte Ausgabe oben pruefen.${NC}"
    return 1
  fi
  load_env
  echo "Warte, bis die Anwendung erreichbar ist..."
  wait_for_health "$WEB_PORT" 60 && echo -e "${GREEN}Neuinstallation abgeschlossen. Die Anwendung laeuft.${NC}" \
    || echo -e "${YELLOW}Neuinstallation abgeschlossen, Anwendung antwortet aber noch nicht ganz.${NC}"
  write_marker
}

run_reinstall_delete_data() {
  echo ""
  echo -e "${RED}Neuinstallation mit vollstaendigem Loeschen aller Daten.${NC}"
  echo "Dies entfernt unwiderruflich: Datenbank, Bilder, Artikel-Verlauf."
  if ! confirm "Wirklich ALLE Daten unwiderruflich loeschen und neu einrichten?"; then
    echo "Abgebrochen."
    return 1
  fi
  ensure_docker_running || return 1
  $SUDO docker compose down -v --rmi all 2>/dev/null
  if confirm "Auch den lokalen Backup-Ordner (./backups) loeschen?"; then
    rm -rf "$BACKUPS_DIR"
    echo "Backup-Ordner geloescht."
  fi
  rm -f "$PROJECT_DIR/.env"
  echo -e "${GREEN}Alte Daten entfernt. Es folgt die Neueinrichtung.${NC}"
  run_fresh_install
}

action_install_update() {
  clear
  line
  echo -e " ${BOLD}Inventarprogramm - Erstinstallation / Update${NC}"
  line
  if ! confirm "Diesen Bereich wirklich oeffnen?"; then return; fi
  ensure_docker_running || { pause; return; }

  if ! is_installed; then
    echo -e "${YELLOW}Es wurde noch keine Installation gefunden.${NC}"
    if confirm "Jetzt erstmalig einrichten?"; then run_fresh_install; fi
    pause; return
  fi

  local inst_ver avail_ver
  inst_ver="$(installed_version)"
  avail_ver="$(available_version)"
  echo "Es besteht bereits eine Installation."
  echo "   Installierte Version: $inst_ver"
  echo "   Verfuegbare Version:  $avail_ver"
  if [ "$inst_ver" = "$avail_ver" ]; then
    echo -e "   ${GREEN}(bereits aktuell)${NC}"
  else
    echo -e "   ${YELLOW}(Update verfuegbar)${NC}"
  fi
  echo ""
  echo "Was soll gemacht werden?"
  echo "  1) Update durchfuehren (Daten bleiben erhalten)"
  echo "  2) Neuinstallation - Daten behalten (Container/Images komplett neu)"
  echo "  3) Neuinstallation - Daten LOESCHEN (Datenbank, Bilder, Verlauf weg)"
  echo "  4) Abbrechen"
  local choice
  read -r -p "Auswahl [1-4]: " choice
  case "$choice" in
    1) confirm "Update wirklich durchfuehren?" && run_update_existing ;;
    2) confirm "Neuinstallation (Daten behalten) wirklich durchfuehren?" && run_reinstall_keep_data ;;
    3) run_reinstall_delete_data ;;
    *) echo "Abgebrochen." ;;
  esac
  pause
}

# --- Erweitert: Deinstallation -------------------------------------
action_uninstall() {
  clear
  line
  echo -e " ${BOLD}Inventarprogramm - Deinstallation${NC}"
  line
  if ! confirm "Diesen Bereich wirklich oeffnen?"; then return; fi
  if ! docker_installed; then
    echo "Docker wurde nicht gefunden - es laeuft vermutlich nichts mehr."
    pause; return
  fi
  if ! confirm "Anwendung wirklich stoppen und deinstallieren?"; then
    echo "Abgebrochen."; pause; return
  fi

  update_sudo_mode
  echo "Container werden gestoppt und entfernt..."
  $SUDO docker compose down
  echo ""

  local remove_volumes=0 remove_images=0
  confirm "Sollen auch alle Daten (Datenbank, Bilder, Artikel-Verlauf) unwiderruflich geloescht werden?" && remove_volumes=1
  confirm "Sollen auch die gebauten Docker-Images entfernt werden (spart Speicherplatz)?" && remove_images=1

  if [ "$remove_volumes" -eq 1 ] || [ "$remove_images" -eq 1 ]; then
    local args=""
    [ "$remove_volumes" -eq 1 ] && args="$args -v"
    [ "$remove_images" -eq 1 ] && args="$args --rmi all"
    echo "Fuehre aus: docker compose down $args"
    # shellcheck disable=SC2086
    $SUDO docker compose down $args
  fi

  if [ "$remove_volumes" -eq 1 ]; then
    if confirm "Auch den lokalen Backup-Ordner (./backups) loeschen?"; then
      rm -rf "$BACKUPS_DIR"
      echo "Backup-Ordner geloescht."
    fi
    if confirm "Auch die HTTPS-Zertifikate (./certs) loeschen?"; then
      rm -rf "$CERTS_DIR"
      echo "Zertifikatsordner geloescht."
    fi
    rm -f "$PROJECT_DIR/.env"
    echo -e "${GREEN}Alle Daten wurden entfernt.${NC}"
  else
    echo "Daten (Datenbank, Bilder, Backups) wurden NICHT geloescht und bleiben erhalten."
  fi

  echo ""
  echo -e "${GREEN}Deinstallation abgeschlossen.${NC}"
  echo "Der Projektordner selbst wurde nicht geloescht - dieser kann bei Bedarf"
  echo "manuell entfernt werden."
  pause
}

# --- Erweitert: Komplett-Backup einspielen (Wiederherstellung) -----
action_restore() {
  clear
  line
  echo -e " ${BOLD}Inventarprogramm - Komplett-Backup einspielen${NC}"
  line
  echo "Ein Komplett-Backup (.zip) ersetzt ALLE aktuellen Daten: Artikel,"
  echo "Personen/Benutzer, Einstellungen, Organisationsname, Logo, Status und Bilder."
  echo ""
  read -r -p "Pfad zur Backup-Datei (.zip) - oder leer zum Abbrechen: " restore_zip
  restore_zip="${restore_zip/#\~/$HOME}"
  if [ -z "$restore_zip" ]; then echo "Abgebrochen."; pause; return; fi
  if [ ! -f "$restore_zip" ]; then echo -e "${RED}Datei nicht gefunden: $restore_zip${NC}"; pause; return; fi
  echo ""
  if ! confirm "ALLE aktuellen Daten werden durch dieses Backup ERSETZT. Fortfahren?"; then echo "Abgebrochen."; pause; return; fi
  if ! confirm "Wirklich sicher? Diese Aktion kann NICHT rueckgaengig gemacht werden"; then echo "Abgebrochen."; pause; return; fi
  ensure_docker_running || { pause; return; }

  local rdir rname
  rdir="$(cd "$(dirname "$restore_zip")" && pwd)"
  rname="$(basename "$restore_zip")"
  echo ""
  echo "Spiele Komplett-Backup ein..."
  $SUDO docker compose stop backend >/dev/null 2>&1
  $SUDO docker compose run --rm --no-deps -T -e SRC="/restore_src/$rname" -v "$rdir:/restore_src:ro" backend \
    python -c '
import zipfile, shutil, os
src = os.environ["SRC"]; data = "/app/data"; tmp = "/tmp/_restore"
shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp, exist_ok=True)
zipfile.ZipFile(src).extractall(tmp)
if os.path.exists(tmp + "/inventar.db"):
    shutil.copy(tmp + "/inventar.db", data + "/inventar.db")
for d in ("images", "branding"):
    s = tmp + "/" + d
    if os.path.isdir(s):
        os.makedirs(data + "/" + d, exist_ok=True)
        for f in os.listdir(s):
            shutil.copy(s + "/" + f, data + "/" + d + "/" + f)
print("Wiederherstellung abgeschlossen.")
'
  local status=$?
  echo "Starte Anwendung neu..."
  $SUDO docker compose up -d >/dev/null 2>&1
  if [ $status -eq 0 ]; then
    echo -e "${GREEN}Komplett-Backup eingespielt. Die Anwendung wurde neu gestartet.${NC}"
  else
    echo -e "${RED}Beim Einspielen ist ein Fehler aufgetreten - bitte Ausgabe oben pruefen.${NC}"
  fi
  pause
}

action_advanced_menu() {
  while true; do
    clear
    line
    echo -e " ${BOLD}Inventarprogramm - Erweitert${NC}"
    line
    echo "  1) Erstinstallation / Update"
    echo "  2) Komplett-Backup einspielen (Wiederherstellung)"
    echo "  3) Server-Aus/Neustart per Web aktivieren/deaktivieren"
    echo "  4) Deinstallation"
    echo "  5) Zurueck zum Hauptmenue"
    echo ""
    local choice
    read -r -p "Auswahl [1-5]: " choice
    case "$choice" in
      1) action_install_update ;;
      2) action_restore ;;
      3) action_power_watcher ;;
      4) action_uninstall ;;
      5) return ;;
      *) ;;
    esac
  done
}

# ------------------------------------------------------------------
# Autostart (systemd-User-Service): startet die Anwendung automatisch beim Booten
# ------------------------------------------------------------------
autostart_enabled() { [ -f "$AUTOSTART_UNIT" ]; }

enable_autostart() {
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$AUTOSTART_UNIT" << UNIT
[Unit]
Description=Inventarprogramm automatisch starten
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=/bin/bash -lc 'docker compose up -d'

[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload >/dev/null 2>&1
  systemctl --user enable inventarprogramm.service >/dev/null 2>&1
  # Lingering, damit der Dienst auch ohne aktive Sitzung beim Booten startet
  command -v loginctl >/dev/null 2>&1 && $SUDO loginctl enable-linger "$USER" >/dev/null 2>&1
  echo -e "${GREEN}Autostart aktiviert - die Anwendung startet kuenftig automatisch beim Booten.${NC}"
}

disable_autostart() {
  systemctl --user disable inventarprogramm.service >/dev/null 2>&1
  rm -f "$AUTOSTART_UNIT"
  systemctl --user daemon-reload >/dev/null 2>&1
  echo -e "${YELLOW}Autostart deaktiviert.${NC}"
}

# --- Server-Aus/Neustart per Web (Host-Watcher) -------------------
# Der Backend-Container legt bei einem Klick in der Weboberflaeche eine
# Signaldatei unter PROJECT_DIR/control ab. Dieser systemd-Watcher laeuft mit
# Root-Rechten auf dem Host und fuehrt daraufhin poweroff/reboot aus - der
# Container selbst hat dazu bewusst keine Rechte.
POWER_SCRIPT="/usr/local/bin/inventarprogramm-power.sh"
POWER_PATH_UNIT="/etc/systemd/system/inventarprogramm-power.path"
POWER_SERVICE_UNIT="/etc/systemd/system/inventarprogramm-power.service"

power_watcher_enabled() { [ -f "$POWER_PATH_UNIT" ]; }

enable_power_watcher() {
  if ! command -v systemctl >/dev/null 2>&1; then
    echo -e "${YELLOW}systemd nicht gefunden - Funktion wird auf diesem System nicht unterstuetzt.${NC}"
    return 1
  fi
  mkdir -p "$PROJECT_DIR/control"
  $SUDO tee "$POWER_SCRIPT" >/dev/null << SCRIPT
#!/bin/bash
CTRL="$PROJECT_DIR/control"
if [ -f "\$CTRL/shutdown.request" ]; then rm -f "\$CTRL/shutdown.request"; /sbin/shutdown -h now; fi
if [ -f "\$CTRL/reboot.request" ]; then rm -f "\$CTRL/reboot.request"; /sbin/shutdown -r now; fi
SCRIPT
  $SUDO chmod +x "$POWER_SCRIPT"
  $SUDO tee "$POWER_SERVICE_UNIT" >/dev/null << UNIT
[Unit]
Description=Inventarprogramm Power Action

[Service]
Type=oneshot
ExecStart=$POWER_SCRIPT
UNIT
  $SUDO tee "$POWER_PATH_UNIT" >/dev/null << UNIT
[Unit]
Description=Inventarprogramm Power Signal Watcher

[Path]
PathModified=$PROJECT_DIR/control
Unit=inventarprogramm-power.service

[Install]
WantedBy=multi-user.target
UNIT
  $SUDO systemctl daemon-reload >/dev/null 2>&1
  $SUDO systemctl enable --now inventarprogramm-power.path >/dev/null 2>&1
  echo -e "${GREEN}Server-Aus/Neustart per Web aktiviert.${NC}"
  echo "In der Weboberflaeche kann nun ein Berechtigter (Rolle mit Recht 'Server herunterfahren') den Server ausschalten/neu starten."
}

disable_power_watcher() {
  $SUDO systemctl disable --now inventarprogramm-power.path >/dev/null 2>&1
  $SUDO rm -f "$POWER_PATH_UNIT" "$POWER_SERVICE_UNIT" "$POWER_SCRIPT"
  $SUDO systemctl daemon-reload >/dev/null 2>&1
  echo -e "${YELLOW}Server-Aus/Neustart per Web deaktiviert.${NC}"
}

action_power_watcher() {
  clear
  line
  echo -e " ${BOLD}Inventarprogramm - Server-Aus/Neustart per Web${NC}"
  line
  echo "Erlaubt das Herunterfahren/Neustarten des Servers ueber die Weboberflaeche"
  echo "(fuer Berechtigte). Es wird ein kleiner Systemdienst mit Root-Rechten eingerichtet."
  echo ""
  if power_watcher_enabled; then
    echo -e "Status: ${GREEN}AN${NC}"
    echo ""
    if confirm "Deaktivieren?"; then disable_power_watcher; fi
  else
    echo -e "Status: ${YELLOW}AUS${NC}"
    echo ""
    if confirm "Jetzt aktivieren (benoetigt sudo)?"; then enable_power_watcher; fi
  fi
  echo ""
  pause
}

action_autostart() {
  clear
  line
  echo -e " ${BOLD}Inventarprogramm - Autostart${NC}"
  line
  if ! command -v systemctl >/dev/null 2>&1; then
    echo -e "${YELLOW}systemd (systemctl) wurde nicht gefunden - Autostart wird auf diesem System nicht unterstuetzt.${NC}"
    pause; return
  fi
  if autostart_enabled; then
    echo -e "Autostart ist derzeit: ${GREEN}AN${NC}"
    echo ""
    if confirm "Autostart ausschalten?"; then disable_autostart; fi
  else
    echo -e "Autostart ist derzeit: ${YELLOW}AUS${NC}"
    echo ""
    if confirm "Autostart einschalten (Anwendung startet automatisch beim Booten)?"; then enable_autostart; fi
  fi
  echo ""
  pause
}

# ------------------------------------------------------------------
# Hauptmenue
# ------------------------------------------------------------------
while true; do
  clear
  line
  echo -e " ${BOLD}Inventarprogramm - Verwaltung (Linux)${NC}   Version: $(available_version)"
  line
  echo "Projektverzeichnis: $PROJECT_DIR"
  echo ""
  echo "  1) Uebersicht anzeigen"
  echo "  2) Starten"
  echo "  3) Stoppen"
  echo "  4) Erweitert (Erstinstallation/Update, Deinstallation)"
  echo "  5) Autostart ein-/ausschalten"
  echo "  6) Beenden"
  echo ""
  choice=""
  read -r -p "Auswahl [1-6]: " choice
  case "$choice" in
    1) action_status ;;
    2) action_start ;;
    3) action_stop ;;
    4) action_advanced_menu ;;
    5) action_autostart ;;
    6) exit 0 ;;
    *) ;;
  esac
done
