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

# ------------------------------------------------------------------
# Online-Pruefung auf neue Programmversionen
# ------------------------------------------------------------------
# Bisher verglich die Verwaltungs-App nur zwei oertliche Angaben: die Version
# im Programmordner (Datei VERSION) und die zuletzt tatsaechlich gebaute. War
# der Programmordner selbst veraltet, konnte das niemand sehen. Zusaetzlich
# wird deshalb beim Projekt-Repository nachgefragt, welche Version dort zuletzt
# veroeffentlicht wurde.
#
# Abschalten: UPDATE_CHECK=0 in der .env oder als Umgebungsvariable. Eigene
# Quelle: UPDATE_REPO / UPDATE_BRANCH bzw. direkt UPDATE_VERSION_URL.
UPDATE_CHECK="${UPDATE_CHECK:-1}"
UPDATE_REPO="${UPDATE_REPO:-marc-richter/Inventory}"
UPDATE_BRANCH="${UPDATE_BRANCH:-main}"
UPDATE_VERSION_URL="${UPDATE_VERSION_URL:-https://raw.githubusercontent.com/${UPDATE_REPO}/${UPDATE_BRANCH}/VERSION}"
UPDATE_TARBALL_URL="${UPDATE_TARBALL_URL:-https://codeload.github.com/${UPDATE_REPO}/tar.gz/refs/heads/${UPDATE_BRANCH}}"

_ONLINE_VERSION_CACHE=""

online_version() {
  # Version im Projekt-Repository. Gibt eine leere Zeichenkette zurueck, wenn
  # die Pruefung abgeschaltet ist, kein Netz besteht oder die Antwort nicht wie
  # eine Versionsnummer aussieht. Bricht nie ab und wartet hoechstens wenige
  # Sekunden - ein Geraet ohne Internet soll dadurch nicht ausgebremst werden.
  [ "$UPDATE_CHECK" = "1" ] || { echo ""; return 0; }
  if [ -n "$_ONLINE_VERSION_CACHE" ]; then echo "$_ONLINE_VERSION_CACHE"; return 0; fi
  command -v curl >/dev/null 2>&1 || { echo ""; return 0; }
  local v
  v="$(curl -fsSL --connect-timeout 3 --max-time 6 "$UPDATE_VERSION_URL" 2>/dev/null | tr -d '[:space:]')"
  case "$v" in
    [0-9]*.[0-9]*.[0-9]*) _ONLINE_VERSION_CACHE="$v"; echo "$v" ;;
    *) echo "" ;;
  esac
}

version_newer() {
  # Rueckgabewert 0, wenn $1 neuer ist als $2. Rein numerischer Vergleich je
  # Stelle, damit 1.96.0 groesser als 1.100.0 nicht faelschlich gewinnt.
  local a="${1:-}" b="${2:-}"
  [ -n "$a" ] && [ -n "$b" ] || return 1
  local i ai bi aa bb
  local IFS='.'
  aa=($a); bb=($b)
  unset IFS
  for i in 0 1 2; do
    ai="${aa[$i]:-0}"; bi="${bb[$i]:-0}"
    ai="${ai%%[!0-9]*}"; bi="${bi%%[!0-9]*}"
    [ -n "$ai" ] || ai=0
    [ -n "$bi" ] || bi=0
    if [ "$ai" -gt "$bi" ] 2>/dev/null; then return 0; fi
    if [ "$ai" -lt "$bi" ] 2>/dev/null; then return 1; fi
  done
  return 1
}

print_online_version_line() {
  # Zeile fuer die Uebersicht. Schweigt, wenn nichts abgefragt werden konnte.
  local onl avail
  onl="$(online_version)"
  [ -n "$onl" ] || return 0
  avail="$(available_version)"
  echo   "Online verfuegbar:    $onl"
  if version_newer "$onl" "$avail"; then
    echo -e "                       ${YELLOW}-> Neuere Programmdateien vorhanden${NC}"
    echo -e "                       ${YELLOW}   ('Erweitert' -> 'Programmdateien aktualisieren')${NC}"
  fi
}

is_git_checkout() {
  [ -d "$PROJECT_DIR/.git" ] && command -v git >/dev/null 2>&1
}

backup_program_files() {
  # Sicherungskopie der jetzigen Programmdateien, bevor sie ersetzt werden.
  # Daten, Zertifikate und Konfiguration bleiben aussen vor - die werden nicht
  # angefasst und liegen ohnehin in eigenen Sicherungen.
  mkdir -p "$BACKUPS_DIR"
  local target
  target="$BACKUPS_DIR/programmdateien-$(available_version)-$(date +%Y%m%d-%H%M%S).tar.gz"
  tar czf "$target" \
    --exclude='./backups' --exclude='./certs' --exclude='./control' \
    --exclude='./config' --exclude='./.git' --exclude='./frontend/node_modules' \
    --exclude='./frontend/dist' \
    -C "$PROJECT_DIR" . 2>/dev/null
  echo "$target"
}

update_program_files() {
  # Holt die neuen Programmdateien in den Programmordner. Zwei Wege:
  # Git-Arbeitskopie -> git pull; sonst Archiv von GitHub.
  # In beiden Faellen bleiben .env, backups/, certs/, control/ und config/
  # unberuehrt.
  clear
  line
  echo -e " ${BOLD}Programmdateien aktualisieren${NC}"
  line

  local onl avail
  avail="$(available_version)"
  onl="$(online_version)"
  echo "Programmordner:       $PROJECT_DIR"
  echo "Version im Ordner:    $avail"
  if [ -z "$onl" ]; then
    echo ""
    echo -e "${YELLOW}Die Online-Abfrage hat nicht geantwortet.${NC}"
    echo "Moegliche Gruende: keine Internetverbindung, die Pruefung ist per"
    echo "UPDATE_CHECK=0 abgeschaltet, oder die Quelle ist nicht erreichbar."
    echo "Quelle: $UPDATE_VERSION_URL"
    echo ""
    pause
    return
  fi
  echo "Online verfuegbar:    $onl"
  echo ""
  if ! version_newer "$onl" "$avail"; then
    echo -e "${GREEN}Der Programmordner ist aktuell. Es gibt nichts zu holen.${NC}"
    echo ""
    pause
    return
  fi

  echo "Die neuen Programmdateien werden geholt. Datenbank, Bilder, Backups,"
  echo "HTTPS-Zertifikate und die .env-Konfiguration bleiben unberuehrt."
  echo "Von den bisherigen Programmdateien wird vorher eine Sicherungskopie im"
  echo "Backup-Ordner abgelegt."
  echo ""
  echo -e "${YELLOW}Hinweis: Eigene Aenderungen an den Programmdateien gehen dabei verloren.${NC}"
  echo ""
  if ! confirm "Programmdateien auf $onl aktualisieren?"; then
    echo "Abgebrochen."
    pause
    return
  fi

  local saved
  echo ""
  echo "Lege Sicherungskopie der bisherigen Programmdateien an..."
  saved="$(backup_program_files)"
  if [ -f "$saved" ]; then
    echo -e "${GREEN}Gesichert:${NC} $saved"
  else
    echo -e "${YELLOW}Sicherungskopie konnte nicht angelegt werden - trotzdem weiter.${NC}"
  fi
  echo ""

  if is_git_checkout; then
    echo "Der Programmordner ist eine Git-Arbeitskopie - hole die Aenderungen per git."
    if ! git -C "$PROJECT_DIR" pull --ff-only 2>&1; then
      echo ""
      echo -e "${RED}git pull ist fehlgeschlagen.${NC}"
      echo "Haeufigste Ursache: oertliche Aenderungen im Programmordner oder ein"
      echo "abgewichener Zweig. Bitte im Terminal pruefen:"
      echo "   cd \"$PROJECT_DIR\" && git status"
      echo ""
      pause
      return
    fi
  else
    echo "Lade Archiv von $UPDATE_TARBALL_URL ..."
    local tmp src entry
    tmp="$(mktemp -d)" || { echo -e "${RED}Kein temporaeres Verzeichnis moeglich.${NC}"; pause; return; }
    if ! curl -fsSL --connect-timeout 5 --max-time 180 "$UPDATE_TARBALL_URL" -o "$tmp/programm.tar.gz"; then
      echo -e "${RED}Der Download ist fehlgeschlagen.${NC}"
      rm -rf "$tmp"; pause; return
    fi
    if ! tar xzf "$tmp/programm.tar.gz" -C "$tmp"; then
      echo -e "${RED}Das Archiv liess sich nicht entpacken.${NC}"
      rm -rf "$tmp"; pause; return
    fi
    src="$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -1)"
    if [ -z "$src" ] || [ ! -f "$src/VERSION" ]; then
      echo -e "${RED}Das Archiv sieht nicht wie der Programmordner aus - nichts geaendert.${NC}"
      rm -rf "$tmp"; pause; return
    fi
    echo "Ersetze die Programmdateien..."
    # Je Eintrag ersetzen statt nur darueberkopieren: so verschwinden auch
    # Dateien, die es im neuen Stand nicht mehr gibt. Alles, was zur
    # Installation vor Ort gehoert, wird uebersprungen.
    for entry in $(ls -A "$src"); do
      case "$entry" in
        .env|.env.*|backups|certs|control|config|data) continue ;;
      esac
      rm -rf "${PROJECT_DIR:?}/$entry"
      cp -R "$src/$entry" "$PROJECT_DIR/" || {
        echo -e "${RED}Fehler beim Kopieren von $entry.${NC}"
        echo "Die Sicherungskopie liegt unter: $saved"
        rm -rf "$tmp"; pause; return
      }
    done
    rm -rf "$tmp"
    chmod +x "$SCRIPT_DIR"/*.command "$SCRIPT_DIR"/*.sh 2>/dev/null
  fi

  echo ""
  echo -e "${GREEN}Programmdateien sind jetzt auf Version $(available_version).${NC}"
  echo ""
  echo "Damit die Aenderungen wirksam werden, muss die Anwendung noch neu"
  echo "gebaut werden (Daten bleiben dabei erhalten)."
  echo ""
  if confirm "Update jetzt durchfuehren?"; then
    run_update_existing
  else
    echo "Spaeter ueber 'Erweitert' -> 'Erstinstallation / Update' -> 'Update durchfuehren'."
  fi
  echo ""
  pause
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
  # Was der laufende Server tatsaechlich meldet. Ohne diese Zeile konnte man
  # nicht erkennen, ob ein Update wirklich angekommen ist - der Vermerk auf der
  # Platte sagt nur, was zuletzt gebaut werden SOLLTE.
  local run_ver; run_ver="$(running_version)"
  if [ -n "$run_ver" ]; then
    echo "Laufende Version:     $run_ver (vom Server gemeldet)"
    if [ "$run_ver" != "$avail_ver" ]; then
      echo -e "                       ${YELLOW}-> Der laufende Server ist aelter als die Programmdateien.${NC}"
      echo -e "                       ${YELLOW}   'Erweitert' -> 'Erstinstallation / Update' ausfuehren.${NC}"
    fi
  fi
  print_online_version_line
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

running_version() {
  # Version, die der LAUFENDE Server meldet. Leer, wenn er nicht antwortet.
  command -v curl >/dev/null 2>&1 || { echo ""; return 0; }
  load_env
  curl -fsS --connect-timeout 2 --max-time 4 "http://localhost:${WEB_PORT}/api/version" 2>/dev/null \
    | sed -n 's/.*"version" *: *"\([^"]*\)".*/\1/p'
}

# ------------------------------------------------------------------
# Protokoll ansehen
# ------------------------------------------------------------------
# Wenn etwas nicht funktioniert, steht der Grund fast immer im Protokoll des
# Servers. Bisher musste man dafuer ein Terminal oeffnen und den richtigen
# docker-Befehl kennen. Diese Ansicht nimmt das ab - einschliesslich einer
# Ansicht, die nur Fehlermeldungen zeigt, und der Moeglichkeit, alles in eine
# Datei zu schreiben, die man weitergeben kann.
# ------------------------------------------------------------------
action_logs() {
  while true; do
    clear
    line
    echo -e " ${BOLD}Inventarprogramm - Protokoll${NC}"
    line
    if ! docker_ready; then
      echo -e "${YELLOW}Docker laeuft nicht - es gibt kein Protokoll zu zeigen.${NC}"
      pause
      return
    fi
    echo "  1) Letzte 100 Zeilen (alle Teile)"
    echo "  2) Nur Fehler und Warnungen"
    echo "  3) Live mitlesen (mit Strg+C beenden)"
    echo "  4) Protokoll in eine Datei schreiben (zum Weitergeben)"
    echo "  5) Zurueck"
    echo ""
    local w=""
    read -r -p "Auswahl [1-5]: " w
    case "$w" in
      1)
        clear; line; echo -e " ${BOLD}Letzte 100 Zeilen${NC}"; line
        docker compose logs --tail=100 2>&1 | tail -200
        echo ""; line; pause ;;
      2)
        clear; line; echo -e " ${BOLD}Fehler und Warnungen${NC}"; line
        # -i: Gross-/Kleinschreibung egal. Faengt die deutschen wie die
        # englischen Schreibweisen ab, die in den Bibliotheken vorkommen.
        local treffer
        treffer="$(docker compose logs --tail=2000 2>&1 \
          | grep -i -E "error|exception|traceback|critical|fehler|warn" | tail -60)"
        if [ -z "$treffer" ]; then
          echo -e "${GREEN}Keine Fehler oder Warnungen in den letzten 2000 Zeilen.${NC}"
        else
          echo "$treffer"
        fi
        echo ""; line; pause ;;
      3)
        clear; line
        echo -e " ${BOLD}Live-Protokoll${NC} - Beenden mit Strg+C"
        line
        docker compose logs -f --tail=20 2>&1 || true
        echo ""; pause ;;
      4)
        local ziel="$PROJECT_DIR/protokoll-$(date +%Y%m%d-%H%M%S).txt"
        {
          echo "Inventarprogramm - Protokoll vom $(date)"
          echo "Installierte Version: $(installed_version)"
          echo "Verfuegbare Version:  $(available_version)"
          echo "Laufende Version:     $(running_version)"
          echo "------------------------------------------------------------"
          docker compose logs --tail=2000 2>&1
        } > "$ziel" 2>/dev/null
        echo ""
        echo -e "${GREEN}Gespeichert:${NC} $ziel"
        echo "Diese Datei enthaelt Server-Meldungen - vor dem Weitergeben kurz durchsehen."
        echo ""
        pause ;;
      5|"") return ;;
      *) ;;
    esac
  done
}

# ------------------------------------------------------------------
# Selbsttest
# ------------------------------------------------------------------
# Prueft der Reihe nach alles, was erfahrungsgemaess schiefgeht, und sagt zu
# jedem Punkt in einem Satz, was zu tun ist. Gedacht fuer den Moment, in dem
# jemand sagt "es geht nicht" - dann muss niemand raten.
# ------------------------------------------------------------------
_pruef_ok=0
_pruef_fehl=0
_pruefe() {
  # $1 = Beschreibung, $2 = ok|warnung|fehler, $3 = Hinweis bei Problem
  case "$2" in
    ok)      echo -e "  ${GREEN}[ok]${NC}      $1"; _pruef_ok=$((_pruef_ok+1)) ;;
    warnung) echo -e "  ${YELLOW}[Hinweis]${NC} $1"; [ -n "${3:-}" ] && echo "            $3" ;;
    *)       echo -e "  ${RED}[Problem]${NC} $1"; [ -n "${3:-}" ] && echo "            $3"
             _pruef_fehl=$((_pruef_fehl+1)) ;;
  esac
}

action_selftest() {
  clear
  line
  echo -e " ${BOLD}Inventarprogramm - Selbsttest${NC}"
  line
  _pruef_ok=0; _pruef_fehl=0

  if docker_installed; then _pruefe "Docker ist installiert" ok
  else _pruefe "Docker ist installiert" fehler "Docker Desktop installieren und starten."; fi

  if docker_ready; then _pruefe "Docker laeuft" ok
  else _pruefe "Docker laeuft" fehler "Docker Desktop oeffnen und warten, bis das Symbol ruhig steht."; fi

  if is_installed; then _pruefe "Installation vorhanden (.env)" ok
  else _pruefe "Installation vorhanden (.env)" fehler "'Erweitert' -> 'Erstinstallation / Update' ausfuehren."; fi

  load_env

  if is_running; then _pruefe "Container laufen" ok
  else _pruefe "Container laufen" fehler "Im Hauptmenue 'Starten' waehlen."; fi

  # Erreichbarkeit + Antwortzeit
  if command -v curl >/dev/null 2>&1; then
    local t0 t1 ms
    t0="$(date +%s)"
    if curl -fsS --connect-timeout 3 --max-time 8 "http://localhost:${WEB_PORT}/api/health" >/dev/null 2>&1; then
      t1="$(date +%s)"; ms=$(( (t1 - t0) ))
      _pruefe "Server antwortet auf http://localhost:${WEB_PORT} (${ms}s)" ok
    else
      _pruefe "Server antwortet auf http://localhost:${WEB_PORT}" fehler \
        "Protokoll ansehen (Hauptmenue) - dort steht meist der Grund."
    fi
  else
    _pruefe "Pruefung der Erreichbarkeit" warnung "curl ist nicht vorhanden - uebersprungen."
  fi

  # Versionen
  local inst avail run
  inst="$(installed_version)"; avail="$(available_version)"; run="$(running_version)"
  if [ -n "$run" ] && [ "$run" = "$avail" ]; then
    _pruefe "Laufende Version passt zu den Programmdateien ($run)" ok
  elif [ -n "$run" ]; then
    _pruefe "Laufende Version $run, Programmdateien $avail" warnung \
      "'Erweitert' -> 'Erstinstallation / Update' uebernimmt die neuen Dateien."
  fi

  # Plattenplatz
  local frei_mb
  frei_mb="$(df -m "$PROJECT_DIR" 2>/dev/null | awk 'NR==2 {print $4}')"
  if [ -n "$frei_mb" ] && [ "$frei_mb" -lt 500 ] 2>/dev/null; then
    _pruefe "Freier Speicherplatz: ${frei_mb} MB" fehler "Unter 500 MB wird es eng - aufraeumen."
  elif [ -n "$frei_mb" ]; then
    _pruefe "Freier Speicherplatz: ${frei_mb} MB" ok
  fi

  # Backups
  if [ -d "$BACKUPS_DIR" ]; then
    local anzahl juengste
    anzahl="$(find "$BACKUPS_DIR" -name "*.zip" -o -name "*.db" 2>/dev/null | wc -l | tr -d ' ')"
    if [ "${anzahl:-0}" -gt 0 ] 2>/dev/null; then
      juengste="$(find "$BACKUPS_DIR" -type f -mtime -14 2>/dev/null | head -1)"
      if [ -n "$juengste" ]; then _pruefe "Sicherungen vorhanden ($anzahl, juengste unter 14 Tage alt)" ok
      else _pruefe "Sicherungen vorhanden ($anzahl), aber keine aus den letzten 14 Tagen" warnung \
        "In den Einstellungen die automatische Sicherung einschalten."; fi
    else
      _pruefe "Keine Sicherung gefunden" warnung "In den Einstellungen -> Backup eine Sicherung anlegen."
    fi
  fi

  # Zertifikat
  if [ -f "$CERTS_DIR/server.crt" ] && command -v openssl >/dev/null 2>&1; then
    if openssl x509 -checkend 604800 -noout -in "$CERTS_DIR/server.crt" >/dev/null 2>&1; then
      _pruefe "HTTPS-Zertifikat gueltig" ok
    else
      _pruefe "HTTPS-Zertifikat laeuft in weniger als 7 Tagen ab" warnung \
        "Beim naechsten Start wird es automatisch neu erzeugt."
    fi
  fi

  # Fehler im Protokoll
  if docker_ready && is_running; then
    local fehlerzeilen
    fehlerzeilen="$(docker compose logs --tail=500 2>&1 | grep -c -i -E "error|exception|traceback|critical" || true)"
    if [ "${fehlerzeilen:-0}" -gt 0 ] 2>/dev/null; then
      _pruefe "$fehlerzeilen Fehlermeldungen in den letzten 500 Protokollzeilen" warnung \
        "Hauptmenue -> 'Protokoll' -> 'Nur Fehler und Warnungen'."
    else
      _pruefe "Keine Fehlermeldungen im Protokoll" ok
    fi
  fi

  echo ""
  line
  if [ "$_pruef_fehl" -eq 0 ]; then
    echo -e " ${GREEN}Alles in Ordnung - $_pruef_ok Pruefungen bestanden.${NC}"
  else
    echo -e " ${RED}$_pruef_fehl Punkt(e) brauchen Aufmerksamkeit${NC} (siehe oben)."
  fi
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
    write_marker
  else
    echo -e "${RED}Die Anwendung antwortet nicht.${NC}"
    echo "Der Installationsvermerk wird deshalb NICHT fortgeschrieben - die"
    echo "Uebersicht zeigt weiterhin die zuletzt lauffaehige Version."
    echo "Bitte die Ursache pruefen:"
    echo "   docker compose logs --tail=60 backend"
  fi

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

  offer_update_watcher

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
  if [ -d "$PROJECT_DIR/.git" ] && command -v git >/dev/null 2>&1; then
    echo "Hole die neueste Version von GitHub (git pull)..."
    git -C "$PROJECT_DIR" pull --ff-only 2>&1 \
      || echo -e "${YELLOW}git pull nicht moeglich (evtl. lokale Aenderungen/ander Branch) - fahre mit vorhandenem Stand fort.${NC}"
  fi
  ensure_cert
  $SUDO docker compose up -d --build
  local status=$?
  if [ $status -ne 0 ]; then
    echo -e "${RED}Beim Update ist ein Fehler aufgetreten. Bitte Ausgabe oben pruefen.${NC}"
    return 1
  fi
  load_env
  echo "Warte, bis die Anwendung erreichbar ist..."
  if wait_for_health "$WEB_PORT" 60; then
    echo -e "${GREEN}Update abgeschlossen. Die Anwendung laeuft.${NC}"
    write_marker
  else
    echo -e "${RED}Die Anwendung antwortet nicht.${NC}"
    echo "Der Installationsvermerk wird deshalb NICHT fortgeschrieben - die"
    echo "Uebersicht zeigt weiterhin die zuletzt lauffaehige Version."
    echo "Bitte die Ursache pruefen:"
    echo "   docker compose logs --tail=60 backend"
  fi
  offer_update_watcher
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
  if wait_for_health "$WEB_PORT" 60; then
    echo -e "${GREEN}Neuinstallation abgeschlossen. Die Anwendung laeuft.${NC}"
    write_marker
  else
    echo -e "${RED}Die Anwendung antwortet nicht.${NC}"
    echo "Der Installationsvermerk wird deshalb NICHT fortgeschrieben - die"
    echo "Uebersicht zeigt weiterhin die zuletzt lauffaehige Version."
    echo "Bitte die Ursache pruefen:"
    echo "   docker compose logs --tail=60 backend"
  fi
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
    echo "  4) Software-Update per Web aktivieren/deaktivieren"
    echo "  5) Deinstallation"
    echo "  6) Programmdateien aktualisieren (aus dem Internet)"
    echo "  7) Zurueck zum Hauptmenue"
    echo ""
    local choice
    read -r -p "Auswahl [1-7]: " choice
    case "$choice" in
      1) action_install_update ;;
      2) action_restore ;;
      3) action_power_watcher ;;
      4) action_update_watcher ;;
      5) action_uninstall ;;
      6) update_program_files ;;
      7) return ;;
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

# --- Software-Update per Weboberflaeche (Host-Dienst als Projekt-Benutzer) --------
UPDATE_SCRIPT="/usr/local/bin/inventarprogramm-update.sh"
UPDATE_PATH_UNIT="/etc/systemd/system/inventarprogramm-update.path"
UPDATE_SERVICE_UNIT="/etc/systemd/system/inventarprogramm-update.service"

update_watcher_enabled() { [ -f "$UPDATE_PATH_UNIT" ]; }

enable_update_watcher() {
  if ! command -v systemctl >/dev/null 2>&1; then
    echo -e "${YELLOW}systemd nicht gefunden - Funktion wird auf diesem System nicht unterstuetzt.${NC}"
    return 1
  fi
  mkdir -p "$PROJECT_DIR/control"
  $SUDO tee "$UPDATE_SCRIPT" >/dev/null << SCRIPT
#!/bin/bash
REQ="$PROJECT_DIR/control/update.request"
LOG="$PROJECT_DIR/control/update.log"
[ -f "\$REQ" ] || exit 0
REF="\$(head -n1 "\$REQ" | tr -d ' \t\r\n')"
rm -f "\$REQ"
[ -n "\$REF" ] || exit 0
cd "$PROJECT_DIR" || exit 1
{
  echo "=== Update auf '\$REF' gestartet \$(date) ==="
  echo "--- git fetch ---"; git fetch --all --tags --prune 2>&1
  echo "--- git checkout \$REF ---"
  if ! git checkout -f "\$REF" 2>&1; then echo "FEHLER: checkout fehlgeschlagen"; echo "=== abgebrochen \$(date) ==="; exit 1; fi
  git symbolic-ref -q HEAD >/dev/null 2>&1 && git pull --ff-only 2>&1
  echo "--- docker compose up -d --build (kann einige Minuten dauern) ---"
  if docker compose up -d --build 2>&1; then echo "=== Update erfolgreich \$(date) ==="; else echo "FEHLER: docker compose Build fehlgeschlagen"; echo "=== abgebrochen \$(date) ==="; exit 1; fi
} > "\$LOG" 2>&1
SCRIPT
  $SUDO chmod +x "$UPDATE_SCRIPT"
  $SUDO tee "$UPDATE_SERVICE_UNIT" >/dev/null << UNIT
[Unit]
Description=Inventarprogramm Software-Update

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$UPDATE_SCRIPT
UNIT
  $SUDO tee "$UPDATE_PATH_UNIT" >/dev/null << UNIT
[Unit]
Description=Inventarprogramm Update-Signal-Watcher

[Path]
PathModified=$PROJECT_DIR/control
Unit=inventarprogramm-update.service

[Install]
WantedBy=multi-user.target
UNIT
  $SUDO systemctl daemon-reload >/dev/null 2>&1
  $SUDO systemctl enable --now inventarprogramm-update.path >/dev/null 2>&1
  echo -e "${GREEN}Software-Update per Weboberflaeche aktiviert.${NC}"
  echo "Ein Berechtigter (Recht 'Software-Updates') kann nun in den Einstellungen"
  echo "unter 'Update' neue Versionen (oder den dev-Branch) installieren."
}

disable_update_watcher() {
  $SUDO systemctl disable --now inventarprogramm-update.path >/dev/null 2>&1
  $SUDO rm -f "$UPDATE_PATH_UNIT" "$UPDATE_SERVICE_UNIT" "$UPDATE_SCRIPT"
  $SUDO systemctl daemon-reload >/dev/null 2>&1
  echo -e "${YELLOW}Software-Update per Weboberflaeche deaktiviert.${NC}"
}

# Wird nach Erstinstallation UND nach jedem Terminal-Update aufgerufen: erklaert den
# Update-Dienst und richtet ihn moeglichst automatisch ein (opt-out).
offer_update_watcher() {
  command -v systemctl >/dev/null 2>&1 || return 0
  if update_watcher_enabled; then
    echo -e "${GREEN}Software-Update per Web ist aktiv - kuenftige Updates gehen per Klick in der Weboberflaeche.${NC}"
    return 0
  fi
  echo ""
  line
  echo -e " ${BOLD}Kuenftige Updates ohne Terminal${NC}"
  line
  echo "Ab dieser Version kannst du neue Versionen direkt in der Weboberflaeche"
  echo "installieren (Einstellungen -> Update, bzw. Hinweis an der Glocke oben rechts)."
  echo "Dafuer wird EINMALIG ein kleiner Update-Dienst eingerichtet, der die gewaehlte"
  echo "Version holt und die Anwendung neu baut. Der Dienst laeuft als dein Benutzer,"
  echo "nicht als root; zum Einrichten wird ggf. einmal dein sudo-Passwort abgefragt."
  echo ""
  local ans
  if read -r -t 60 -p "Update-Dienst jetzt einrichten? [J/n]: " ans; then
    case "$ans" in
      n|N) echo "Uebersprungen - jederzeit nachholbar unter 'Erweitert -> Software-Update per Web'." ;;
      *) enable_update_watcher ;;
    esac
  else
    echo ""
    echo "(Keine Eingabe - Update-Dienst wird eingerichtet.)"
    enable_update_watcher
  fi
}

action_update_watcher() {
  clear
  line
  echo -e " ${BOLD}Inventarprogramm - Software-Update per Weboberflaeche${NC}"
  line
  echo "Erlaubt Berechtigten, neue Versionen (oder den dev-Branch) direkt aus der"
  echo "Weboberflaeche zu installieren. Richtet einen kleinen Dienst ein, der die"
  echo "gewaehlte Version holt (git) und die Container neu baut."
  echo ""
  if update_watcher_enabled; then
    echo -e "Status: ${GREEN}AN${NC}"
    echo ""
    if confirm "Deaktivieren?"; then disable_update_watcher; fi
  else
    echo -e "Status: ${YELLOW}AUS${NC}"
    echo ""
    if confirm "Jetzt aktivieren (benoetigt sudo)?"; then enable_update_watcher; fi
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
  echo "  4) Selbsttest (prueft, ob alles laeuft)"
  echo "  5) Protokoll ansehen (bei Problemen)"
  echo "  6) Erweitert (Erstinstallation/Update, Deinstallation)"
  echo "  7) Autostart ein-/ausschalten"
  echo "  8) Beenden"
  echo ""
  choice=""
  read -r -p "Auswahl [1-8]: " choice
  case "$choice" in
    1) action_status ;;
    2) action_start ;;
    3) action_stop ;;
    4) action_selftest ;;
    5) action_logs ;;
    6) action_advanced_menu ;;
    7) action_autostart ;;
    8) exit 0 ;;
    *) ;;
  esac
done
