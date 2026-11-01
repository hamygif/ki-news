# KI News

Eine kleine Web-App mit den KI-Nachrichten der letzten 24 Stunden – optimiert fürs iPhone.

- `ki_news.py` – holt die Artikel aus mehreren RSS-Feeds und baut `site/index.html` (nur Python-Standardbibliothek)
- `make_icons.py` – erzeugt einmalig die App-Icons
- `.github/workflows/update.yml` – läuft jeden Morgen um 6:00 Uhr (deutsche Zeit) und veröffentlicht die Seite auf GitHub Pages; auch manuell startbar

Lokal ausprobieren: `python3 ki_news.py` und dann `site/index.html` öffnen.
