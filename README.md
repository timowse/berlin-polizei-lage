# Polizei Berlin – Meldungen

Eine klare, mobil-zuerst gedachte Ansicht der offiziellen Polizeimeldungen aus Berlin.

- Quelle: offizieller RSS-Feed der Polizei Berlin
- Aktualisierung: `scripts/update_feed.py`, per GitHub Action alle 10 Minuten
- Hosting: GitHub Pages aus dem Repo-Root

Live: `https://timowse.github.io/berlin-polizei-lage/`

## Oberfläche

Die App ist eine einzelne, build-freie Datei (`index.html`) mit Design-Tokens,
hellem und dunklem Modus, Tagesgruppierung, Kategoriefiltern mit Trefferzahlen,
Suche mit Treffer-Hervorhebung, Teilen-Funktion, Pull-to-Refresh und
Offline-Hinweisen. Sie läuft als PWA über `manifest.webmanifest` und `sw.js`.

## Kategorien

`scripts/update_feed.py` ordnet jeder Meldung eine Kategorie zu; `index.html`
enthält dieselbe Logik als Rückfallebene. Die Keyword-Listen in beiden Dateien
müssen synchron bleiben. Keywords greifen nur am Wortanfang, damit deutsche
Komposita weiterhin matchen ("Verkehrsunfall"), Zufallstreffer im Wortinneren
aber nicht ("Restaurant" enthält "stau").
