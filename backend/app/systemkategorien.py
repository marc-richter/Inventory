"""Die vom Programm mitgelieferten Materialklassen.

Warum das so ist
----------------
Frueher konnte jeder, der Artikel erfassen durfte, nebenbei eine neue Kategorie
anlegen. Das fuehrte zu "Kleidung", "kleidung" und "Bekleidung" nebeneinander und
zu Kategorien ohne jede Struktur. Jetzt bringt das Programm die gaengigen Klassen
samt passender Felder, Status und Pruefarten mit, und nur ein Administrator darf
weitere anlegen - dort baut er die Felder dann selbst zusammen.

Was hier steht, wird bei jedem Start abgeglichen (idempotent):
* fehlende Kategorien werden angelegt,
* fehlende Standardfelder werden ergaenzt,
* bereits vorhandene werden NICHT ueberschrieben - was der Administrator
  umbenannt oder ausgeblendet hat, bleibt so.

Bestehende Installationen behalten ihre selbst angelegten Kategorien; sie sind
einfach keine Systemkategorien und tragen keine Standardfelder.
"""

# Feldtypen: text | number | select | bool | date

# (system_key, Name, Elternklasse|None, Schliessanlage, Sortierung, Schloesser)
#
# Schliessanlage = Artikel dieser Klasse SIND Schluessel.
# Schloesser     = Artikel dieser Klasse HABEN Schloesser (Fahrzeug: Fahrertuer,
#                  Heckklappe, Geraeteraeume, Zuendschloss; Kiste: Vorhaengeschloss).
# Beides ist unabhaengig voneinander und laesst sich je Klasse umstellen.
KATEGORIEN = [
    ("kleidung", "Kleidung", None, False, 10, False),
    ("schluessel", "Schlüssel", None, True, 20, False),
    ("funk", "Funk", None, False, 30, False),
    ("funk_akkus", "Funk-Akkus", "funk", False, 31, False),
    ("funk_zubehoer", "Funk-Zubehör", "funk", False, 32, False),
    ("fahrzeuge", "Fahrzeuge", None, False, 40, True),
    ("behaelter", "Behälter", None, False, 50, True),
    ("elektrogeraete", "Elektrogeräte", None, False, 60, False),
    ("sonstiges", "Sonstiges", None, False, 90, False),
]

# system_key der Kategorie -> Liste der Standardfelder
# (feld_key, Bezeichnung, Typ, Auswahlwerte, Pflicht, Sortierung)
FELDER = {
    "kleidung": [
        ("farbe", "Farbe", "text", [], False, 10),
        ("persoenlich", "Persönlich zugeordnet", "bool", [], False, 20),
        ("ablaufdatum", "Ablaufdatum (PSA)", "date", [], False, 30),
    ],
    # Schluessel: Alias, Schliessgruppe, Schluesseltyp und Seriennummer sind
    # feste Artikelfelder (siehe models.Article) - hier braucht es nichts.
    "schluessel": [],
    "funk": [
        ("rufname", "Funkrufname", "text", [], False, 10),
        ("opta", "OPTA", "text", [], False, 20),
        ("issi", "ISSI", "text", [], False, 30),
        ("seriennummer", "Seriennummer", "text", [], False, 40),
        ("betriebsart", "Betriebsart", "select", ["analog", "digital", "analog + digital"], False, 50),
        ("firmware", "Firmware-Version", "text", [], False, 60),
        ("akkutyp", "Akkutyp", "text", [], False, 70),
        ("programmiert_am", "Zuletzt programmiert", "date", [], False, 80),
    ],
    "funk_akkus": [
        ("kapazitaet", "Kapazität (mAh)", "number", [], False, 10),
        ("bauform", "Bauform", "text", [], False, 20),
        ("baujahr", "Baujahr", "number", [], False, 30),
        ("ladezyklen", "Ladezyklen", "number", [], False, 40),
        ("kapazitaetstest", "Letzter Kapazitätstest", "date", [], False, 50),
    ],
    "funk_zubehoer": [
        ("zubehoerart", "Zubehörart", "select",
         ["Handmonophon", "Ladegerät", "Antenne", "Trageriemen", "Headset", "Akkudeckel", "Sonstiges"],
         False, 10),
        ("passend_zu", "Passend zu", "text", [], False, 20),
        ("seriennummer", "Seriennummer", "text", [], False, 30),
    ],
    "fahrzeuge": [
        ("kennzeichen", "Kennzeichen", "text", [], False, 10),
        ("funkrufname", "Funkrufname", "text", [], False, 20),
        ("fin", "Fahrgestellnummer (FIN)", "text", [], False, 30),
        ("erstzulassung", "Erstzulassung", "date", [], False, 40),
        ("indienststellung", "Indienststellung", "date", [], False, 50),
        ("kmstand", "Kilometerstand", "number", [], False, 60),
        ("sitzplaetze", "Sitzplätze", "number", [], False, 70),
        ("zggm", "Zulässiges Gesamtgewicht (kg)", "number", [], False, 80),
        ("fuehrerschein", "Erforderliche Führerscheinklasse", "select",
         ["B", "BE", "C1", "C1E", "C", "CE", "sonstige"], False, 90),
    ],
    "behaelter": [
        ("behaelterart", "Behälterart", "select",
         ["Kiste", "Rucksack", "Tasche", "Rollcontainer", "Schrank", "Sonstiges"], False, 10),
        ("masse", "Außenmaße (L×B×H cm)", "text", [], False, 20),
        ("leergewicht", "Leergewicht (kg)", "number", [], False, 30),
        ("ladegewicht", "Beladenes Gewicht (kg)", "number", [], False, 40),
        ("plombe", "Plombennummer", "text", [], False, 50),
    ],
    "elektrogeraete": [
        ("hersteller", "Hersteller", "text", [], False, 10),
        ("typbezeichnung", "Typbezeichnung", "text", [], False, 20),
        ("seriennummer", "Seriennummer", "text", [], False, 30),
        ("baujahr", "Baujahr", "number", [], False, 40),
        # Die Schutzklasse entscheidet, welche Messungen bei der Prüfung
        # überhaupt anfallen - bei Schutzklasse II gibt es keinen Schutzleiter.
        ("schutzklasse", "Schutzklasse", "select", ["I", "II", "III"], False, 50),
        ("betriebsmittel", "Art des Betriebsmittels", "select",
         ["ortsveränderlich", "ortsfest", "Verlängerungsleitung", "Mehrfachsteckdose"],
         False, 60),
        # Das Prüfintervall nach DGUV V3 hängt an der Umgebung; das Feld hält
        # fest, wovon man ausgegangen ist.
        ("einsatzumgebung", "Einsatzumgebung", "select",
         ["Verwaltung / Unterrichtsraum", "Werkstatt", "Einsatz / im Freien", "Baustelle"],
         False, 70),
        ("leistung", "Leistungsaufnahme (W)", "number", [], False, 80),
        ("spannung", "Betriebsspannung", "text", [], False, 90),
        ("pruefplakette", "Prüfplakette angebracht", "bool", [], False, 100),
    ],
    "sonstiges": [],
}

# Status, die das Programm mitbringt.
# (key, Bezeichnung, Sortierung, Kategorien|None=alle, Notiz-Pflicht, Bild moeglich, Ausgabe)
# Ausgabe: direct = ohne Rueckfrage, confirm = mit Rueckfrage, blocked = gesperrt
STATUS = [
    # fuer alle Klassen
    # "Vorgemerkt" setzt das Programm selbst, sobald ein Artikel auf einer
    # offenen Bereitstellung steht. Ausgabe-Regel "confirm": es ist ein Hinweis,
    # kein Verbot - nach Rueckfrage laesst sich der Artikel trotzdem an jemand
    # anderen ausgeben. Ueber die zugehoerige Bereitstellung selbst wird nicht
    # gefragt, dort ist die Vormerkung ja gerade der Zweck.
    ("vorgemerkt", "Vorgemerkt", 45, None, False, False, "confirm"),
    ("entwendet", "Entwendet", 46, None, True, True, "blocked"),
    # Kleidung
    ("zu_waschen", "Zu waschen", 50, ["kleidung"], False, False, "confirm"),
    ("beschaedigt", "Beschädigt", 60, ["kleidung"], True, True, "confirm"),
    ("infektioes", "Infektiös", 70, ["kleidung"], False, False, "confirm"),
    # Schluessel
    ("schluessel_abgebrochen", "Abgebrochen", 110, ["schluessel"], True, True, "blocked"),
    ("schluessel_verloren", "Verloren", 111, ["schluessel"], True, False, "blocked"),
    ("schluessel_nachgefertigt", "Nachgefertigt", 112, ["schluessel"], False, False, "direct"),
    ("schluessel_entwertet", "Entwertet / gesperrt", 113, ["schluessel"], True, False, "blocked"),
    ("schluessel_schlosser", "Beim Schlosser", 114, ["schluessel"], False, False, "blocked"),
    # Funk
    ("funk_teildefekt", "Teildefekt", 120, ["funk", "funk_akkus", "funk_zubehoer"], True, True, "confirm"),
    ("funk_gesperrt", "Gesperrt", 121, ["funk", "funk_akkus", "funk_zubehoer"], False, False, "blocked"),
    # Fahrzeuge
    ("kfz_ausser_dienst", "Außer Dienst", 130, ["fahrzeuge"], False, False, "blocked"),
    ("kfz_unfall", "Unfall", 131, ["fahrzeuge"], True, True, "blocked"),
    ("kfz_unvollstaendig", "Unvollständig", 132, ["fahrzeuge"], True, False, "confirm"),
    # Elektrogeraete
    ("elektro_nicht_bestanden", "Prüfung nicht bestanden", 150, ["elektrogeraete"],
     True, True, "blocked"),
    ("elektro_reparatur_elektro", "Bei der Elektrofachkraft", 151, ["elektrogeraete"],
     False, False, "blocked"),
    # Behaelter
    ("behaelter_defekt", "Defekt / beschädigt", 140, ["behaelter"], True, True, "confirm"),
    ("behaelter_abgelaufen", "Abgelaufen", 141, ["behaelter"], True, False, "confirm"),
]

# Startfassung der Funk-Funktionspruefung. Der Administrator passt sie unter
# Einstellungen -> Stammdaten -> Prueflisten an; die Punkte hier sind ein
# brauchbarer Anfang, kein Regelwerk.
CHECKLISTEN = {
    "Funk-Funktionsprüfung": [
        "Gehäuse, Antenne und Anschlüsse unbeschädigt",
        "Display und alle Tasten funktionsfähig",
        "Akku lädt und hält die Ladung",
        "Sende- und Empfangsprobe erfolgreich",
        "Lautstärke und Rauschsperre in Ordnung",
        "Notruftaste funktionsfähig",
        "Rufname / OPTA / ISSI stimmen mit der Kennzeichnung überein",
        "Zubehör vollständig (Akku, Handmonophon, Trageriemen)",
    ],
    "Fahrzeug-Abfahrtkontrolle": [
        "Beleuchtung rundum funktionsfähig",
        "Reifendruck und Profiltiefe geprüft",
        "Öl-, Kühlwasser- und Waschwasserstand geprüft",
        "Blaulicht und Signalhorn funktionsfähig",
        "Verbandkasten, Warndreieck und Warnweste vorhanden",
        "Beladung vollständig und gesichert",
        "Keine sichtbaren Schäden",
    ],
    "DGUV V3 – Prüfung elektrischer Betriebsmittel": [
        "Sichtprüfung: Gehäuse, Leitung, Stecker und Zugentlastung unbeschädigt",
        "Keine unzulässigen Änderungen oder Reparaturen erkennbar",
        "Schutzleiterwiderstand gemessen und innerhalb des Grenzwerts",
        "Isolationswiderstand gemessen und innerhalb des Grenzwerts",
        "Schutzleiter- bzw. Berührungsstrom gemessen und innerhalb des Grenzwerts",
        "Funktionsprüfung bestanden",
        "Prüfplakette angebracht, nächster Termin vermerkt",
    ],
    "Behälter-Vollständigkeitsprüfung": [
        "Inhalt gemäß Inhaltsliste vollständig",
        "Kein abgelaufenes Material enthalten",
        "Behälter unbeschädigt und sauber",
        "Plombe vorhanden und unversehrt",
    ],
}

# Pruef- und Terminarten, die das Programm mitbringt.
# (Name, Beschreibung, Kategorien, Monate|None, km|None, km-basiert, Checkliste|None,
#  Art, Erfassungsfelder)
#
# Erfassungsfelder werden beim Abhaken ausgefuellt und im Protokoll festgehalten -
# bei der DGUV-V3-Pruefung sind das die Messwerte, ohne die das Protokoll
# wertlos waere.
# Art: "funktion" (arbeitet es noch?) oder "verfall" (ist es noch haltbar?). Die
# Inhaltslisten faerben danach ein - blau fuer Funktion, gelb fuer Verfall - und
# der Vordruck erklaert die beiden Farben in seiner Fusszeile.
PRUEFARTEN = [
    ("Funk-Funktionsprüfung", "Jährliche Funktionsprüfung der Funkgeräte.",
     ["funk"], 12, None, False, "Funk-Funktionsprüfung", "funktion", []),
    ("Akku-Kapazitätstest", "Prüfung, ob der Akku seine Kapazität noch hält.",
     ["funk_akkus"], 12, None, False, None, "funktion", []),
    ("Hauptuntersuchung (HU)", "Hauptuntersuchung nach § 29 StVZO. Das Intervall lässt "
     "sich je Fahrzeug abweichend einstellen (z.B. 12 statt 24 Monate).",
     ["fahrzeuge"], 24, None, False, None, "funktion", []),
    ("Sicherheitsprüfung (SP)", "Sicherheitsprüfung; nur für Fahrzeuge nötig, die ihr "
     "unterliegen. Je Fahrzeug ein- und ausschaltbar.",
     ["fahrzeuge"], 12, None, False, None, "funktion", []),
    ("Ölwechsel", "Nach Laufleistung oder Zeit, je nachdem was zuerst eintritt.",
     ["fahrzeuge"], 12, 15000, True, None, "funktion", []),
    ("UVV-Prüfung", "Jährliche Prüfung nach Unfallverhütungsvorschrift.",
     ["fahrzeuge"], 12, None, False, None, "funktion", []),
    ("Abfahrtkontrolle", "Sichtprüfung vor der Fahrt.",
     ["fahrzeuge"], None, None, False, "Fahrzeug-Abfahrtkontrolle", "funktion", []),
    ("Vollständigkeitsprüfung", "Inhalt gegen die Inhaltsliste prüfen.",
     ["behaelter"], 6, None, False, "Behälter-Vollständigkeitsprüfung", "funktion", []),
    ("Verfallsdatum prüfen", "Haltbarkeit des Inhalts kontrollieren - Sanitätsmaterial, "
     "Batterien, Lebensmittel. Diese Art ist der Anker für das später folgende "
     "Verbrauchsmaterial und färbt die Inhaltslisten gelb.",
     ["behaelter"], 6, None, False, None, "verfall", []),
    ("DGUV V3 – Prüfung elektrischer Betriebsmittel",
     "Wiederkehrende Prüfung ortsveränderlicher elektrischer Betriebsmittel nach "
     "DGUV Vorschrift 3 (früher BGV A3), durchzuführen von einer Elektrofachkraft. "
     "Das Intervall hängt von der Einsatzumgebung ab - die zwölf Monate hier sind "
     "ein brauchbarer Ausgangswert und lassen sich je Gerät ändern (z.B. drei "
     "Monate auf Baustellen, vierundzwanzig in der Verwaltung). Maßgeblich ist die "
     "Gefährdungsbeurteilung des Vereins, nicht dieser Vorschlag.",
     ["elektrogeraete"], 12, None, False, "DGUV V3 – Prüfung elektrischer Betriebsmittel",
     "funktion",
     ["Schutzleiterwiderstand (Ω)", "Isolationswiderstand (MΩ)",
      "Schutzleiterstrom (mA)", "Berührungsstrom (mA)",
      "Prüfgerät", "Prüfende Elektrofachkraft"]),
]
