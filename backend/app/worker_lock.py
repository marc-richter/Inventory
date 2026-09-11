"""Sorgt dafuer, dass Hintergrundaufgaben nur in einem einzigen Prozess laufen.

Das Backend wird in der Produktion mit mehreren Gunicorn-Workern gestartet.
Zeitgesteuerte Aufgaben (automatische Sicherung, Erinnerungen, Mindestbestands-
und Terminpruefung) und der Telegram-Poller duerfen es aber nur einmal geben:
sonst wird mehrfach gesichert, Benachrichtigungen kommen doppelt an, und beim
Telegram-Long-Polling ueberschreiben sich die Worker gegenseitig die
Update-Offsets, sodass Nachrichten verloren gehen.

Jeder Worker versucht beim Start, eine exklusive Dateisperre zu bekommen.
Genau einer bekommt sie und uebernimmt die Hintergrundaufgaben; die uebrigen
bedienen nur Anfragen. Faellt der Inhaber weg, gibt das Betriebssystem die
Sperre frei und der naechste startende Worker uebernimmt.
"""

import os

from .config import DATA_DIR

# Das Dateiobjekt muss fuer die gesamte Prozesslaufzeit offen bleiben - mit dem
# Schliessen der Datei wuerde auch die Sperre verfallen.
_lock_file = None


def acquire_background_lock(name: str = "background-jobs") -> bool:
    """True, wenn dieser Prozess die Hintergrundaufgaben uebernehmen soll."""
    global _lock_file
    if _lock_file is not None:
        return True
    try:
        import fcntl
    except ImportError:
        # Nicht-POSIX (z.B. Entwicklung unter Windows ohne Container): dort
        # laeuft ohnehin nur ein Prozess.
        return True
    handle = None
    try:
        handle = open(DATA_DIR / f".{name}.lock", "w", encoding="utf-8")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if handle is not None:
            handle.close()
        return False
    try:
        handle.write(str(os.getpid()))
        handle.flush()
    except OSError:
        pass
    _lock_file = handle
    return True
