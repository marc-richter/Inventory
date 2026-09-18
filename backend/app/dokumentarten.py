"""Die Arten von Dokumenten, die an Artikeln haengen koennen.

Bewusst eine feste Liste und keine frei erweiterbare Lookup-Tabelle: bei den
Materialklassen hat die freie Anlage frueher zu "Kleidung", "kleidung" und
"Bekleidung" nebeneinander gefuehrt, und hier waere es genauso. Die sieben
Arten decken ab, was in einem Verein wirklich vorkommt; wer eine achte braucht,
nimmt "Sonstiges" und schreibt es in den Titel.

Die Art steuert nur Sortierung und Symbol in der Anzeige - fachlich haengt an ihr
nichts. Deshalb ist das Hinzufuegen einer Art eine Zeile hier und sonst nichts.
"""

# (key, Bezeichnung, Sortierung, Symbol)
ARTEN = [
    ("pflege", "Pflegehinweis", 10, "🧺"),
    ("desinfektion", "Desinfektionshinweis", 20, "🧴"),
    ("anleitung", "Bedienungsanleitung", 30, "📖"),
    ("sicherheit", "Sicherheitsdatenblatt", 40, "⚠️"),
    ("pruefung", "Prüfvorschrift", 50, "🔍"),
    ("nachweis", "Nachweis / Zertifikat", 60, "📜"),
    ("sonstiges", "Sonstiges", 90, "📄"),
]

KEYS = {a[0] for a in ARTEN}
STANDARD = "sonstiges"


def normalisieren(art: str) -> str:
    """Unbekanntes faellt auf "Sonstiges" zurueck statt die Ablage zu verweigern."""
    art = (art or "").strip().lower()
    return art if art in KEYS else STANDARD


def bezeichnung(art: str) -> str:
    for key, label, _sort, _sym in ARTEN:
        if key == art:
            return label
    return "Sonstiges"


def katalog() -> list:
    return [{"key": k, "label": lb, "sort_order": so, "symbol": sy} for k, lb, so, sy in ARTEN]
