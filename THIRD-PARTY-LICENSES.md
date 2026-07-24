# Drittanbieter-Lizenzen

Dieses Projekt (Inventarprogramm) steht unter der **GNU Affero General Public
License v3.0 or later (AGPL-3.0-or-later)** – siehe Datei `LICENSE`.

Es verwendet die folgenden Open-Source-Komponenten. Alle stehen unter
permissiven Lizenzen (MIT / BSD / Apache-2.0 / HPND), die mit der AGPLv3
kompatibel sind. Die jeweilige Lizenz gilt weiterhin für die betreffende
Komponente; die Auflistung dient der Transparenz. Maßgeblich ist jeweils der
Lizenztext im Original-Projekt.

## Backend (Python)

| Paket | Lizenz |
|---|---|
| FastAPI | MIT |
| Uvicorn | BSD-3-Clause |
| SQLAlchemy | MIT |
| pydantic / pydantic-settings | MIT |
| python-jose | MIT |
| passlib | BSD-2-Clause |
| bcrypt | Apache-2.0 |
| python-multipart | Apache-2.0 |
| Pillow | HPND (MIT-CMU) |
| qrcode | BSD |
| reportlab | BSD-3-Clause |
| APScheduler | MIT |
| python-dotenv | BSD-3-Clause |

## Frontend (JavaScript)

| Paket | Lizenz |
|---|---|
| React / react-dom | MIT |
| react-router-dom | MIT |
| html5-qrcode | Apache-2.0 |
| Vite / @vitejs/plugin-react | MIT |
| Tailwind CSS | MIT |
| PostCSS / autoprefixer | MIT |

## Container-Basis-Images (nur zur Ausführung, nicht Teil des Quellcodes)

| Image | Lizenz(en) |
|---|---|
| python:3.11-slim | PSF-2.0 (Python) + Debian-Paketlizenzen |
| node:20-alpine | MIT (Node.js) + Alpine/MIT-Style |
| nginx:1.27-alpine | BSD-2-Clause (nginx) + Alpine |

Hinweis: Dies ist keine Rechtsberatung. Bei kommerzieller Weitergabe oder
Unsicherheiten empfiehlt sich eine juristische Prüfung der Lizenzpflichten
(insbesondere der AGPL-Netzwerk-Klausel, § 13).
