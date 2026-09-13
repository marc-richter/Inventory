"""Behaelter: Artikel, die zugleich Lagerort sind.

Eine Kiste, ein Rucksack oder eine Tasche ist beides - ein Gegenstand, den man
inventarisiert und ausgibt, UND ein Ort, in dem anderes liegt. Technisch ist das
dieselbe Loesung wie beim Fahrzeug: der Artikel bekommt einen eigenen Knoten im
Lagerort-Baum (StorageNode.node_article_id).

Daraus folgt zweierlei, und beides ist beabsichtigt:

* Wandert die Kiste, wandert ihr Inhalt automatisch mit - der Inhalt haengt am
  Knoten, nicht am Raum. Beim Scannen waehrend einer Raum-Inventur muss deshalb
  nur der Knoten umgehaengt werden.
* Wird die Kiste ausgegeben, geht ihr Inhalt mit. Jeder Artikel darin bekommt
  einen eigenen Ausgabe-Eintrag, der auf den Eintrag der Kiste zeigt. Sonst
  zeigte die Uebersicht Material als verfuegbar an, das laengst unterwegs ist.
  In der Ausgabeliste erscheint trotzdem nur die Kiste - mit einem Vermerk,
  falls sie nicht vollstaendig hinausging.

Verschachtelung ist ausdruecklich erlaubt und beliebig tief: Kiste in Kiste in
Fahrzeug.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from . import models
from .logging_config import get_logger

log = get_logger("behaelter")

# Reissleine gegen einen im Kreis zeigenden Baum. Erreicht die Tiefe diesen Wert,
# stimmt etwas mit den Daten nicht - dann lieber abbrechen als endlos laufen.
MAX_TIEFE = 50


def knoten_von(db: Session, artikel: models.Article) -> Optional[models.StorageNode]:
    """Der Lagerort-Knoten, den dieser Artikel darstellt (Fahrzeug oder Behaelter)."""
    if artikel is None:
        return None
    return (db.query(models.StorageNode)
            .filter(models.StorageNode.node_article_id == artikel.id).first())


def teilbaum_ids(db: Session, node_id: int) -> List[int]:
    """Der Knoten selbst und alles darunter - beliebig tief."""
    gesammelt, offen, tiefe = [], [node_id], 0
    while offen and tiefe < MAX_TIEFE:
        gesammelt.extend(offen)
        kinder = [k.id for k in db.query(models.StorageNode.id)
                  .filter(models.StorageNode.parent_id.in_(offen)).all()]
        offen = [k for k in kinder if k not in gesammelt]
        tiefe += 1
    if tiefe >= MAX_TIEFE:
        log.warning("Lagerort-Baum ab Knoten %s ist ungewoehnlich tief - abgebrochen", node_id)
    return gesammelt


def inhalt(db: Session, artikel: models.Article) -> List[models.Article]:
    """Alle Artikel, die (auch mittelbar) in diesem Behaelter liegen.

    Der Behaelter selbst ist nicht dabei. Weitere Behaelter darin schon - und
    deren Inhalt ebenfalls, denn der liegt ja mit in der Kiste.
    """
    node = knoten_von(db, artikel)
    if node is None:
        return []
    ids = teilbaum_ids(db, node.id)
    if not ids:
        return []
    return (db.query(models.Article)
            .filter(models.Article.storage_node_id.in_(ids),
                    models.Article.id != artikel.id)
            .order_by(models.Article.artikelnummer).all())


def ist_behaelter(artikel: models.Article) -> bool:
    return bool(artikel is not None and artikel.is_container)


def liegt_in_ausgegebenem_behaelter(db: Session, artikel: models.Article) -> Optional[models.Article]:
    """Der ausgegebene Behaelter, in dem dieser Artikel steckt - oder None.

    Wird gebraucht, um beim Einzelausgeben eines Stuecks aus einer unterwegs
    befindlichen Kiste nachfragen zu koennen.
    """
    node = db.get(models.StorageNode, artikel.storage_node_id) if artikel.storage_node_id else None
    tiefe = 0
    while node is not None and tiefe < MAX_TIEFE:
        if node.node_article_id:
            traeger = db.get(models.Article, node.node_article_id)
            if traeger is not None and traeger.status == models.ArticleStatus.ausgegeben.value:
                return traeger
        node = db.get(models.StorageNode, node.parent_id) if node.parent_id else None
        tiefe += 1
    return None
