"""Leere Werte statt Serverfehler bei nachtraeglich hinzugefuegten JSON-Spalten.

Warum es das gibt
-----------------
Eine JSON-Spalte, die per ``ALTER TABLE ... ADD COLUMN`` dazukommt, steht bei
allen bereits vorhandenen Zeilen auf NULL - SQLite kennt keinen nachtraeglichen
Standardwert fuer Bestandszeilen. Das Feld im Ausgabeschema ist aber als
``dict`` oder ``list`` deklariert, und Pydantic lehnt None dafuer ab. Ergebnis:
die Abfrage liefert 500, und zwar erst beim Verein und nie im Test, weil Tests
jede Datenbank frisch aufbauen.

Genau so ist es nach 1.114.0 passiert: der Lagerort-Baum liess sich nicht mehr
laden ("interner Serverfehler"), weil ``storage_nodes.watermark`` bei allen
Zeilen von vor 1.103.0 NULL war. Mit hing die halbe Oberflaeche: ohne Baum kein
Lagerort in der Artikelmaske, also kamen auch neu angelegte Lagerorte nicht an.

Die Migration raeumt die vorhandenen NULL-Werte weg. Diese Helfer sind der
zweite Riegel: selbst wenn kuenftig eine Spalte ohne Nacharbeit dazukommt, wird
daraus eine leere Liste bzw. ein leeres Objekt und kein Serverfehler.
"""
from pydantic import field_validator


def _leer_dict(v):
    return {} if v is None else v


def _leer_liste(v):
    return [] if v is None else v


def leeres_dict(*felder: str):
    """NULL -> {} fuer die genannten Felder (im Klassenrumpf zuweisen)."""
    return field_validator(*felder, mode="before")(_leer_dict)


def leere_liste(*felder: str):
    """NULL -> [] fuer die genannten Felder (im Klassenrumpf zuweisen)."""
    return field_validator(*felder, mode="before")(_leer_liste)
