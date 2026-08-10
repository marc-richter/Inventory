"""Integrationstests für die Kernabläufe: Auth, Rechte, Artikel/Ausgabe/Rücknahme,
Inventur (Fortschritt, Stationen, Bericht) und DSGVO-Anonymisierung."""


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --------------------------- Auth -------------------------------------------

def test_login_success_and_failure(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin1234"})
    assert r.status_code == 200, r.text
    assert r.json().get("access_token")

    bad = client.post("/api/auth/login", json={"username": "admin", "password": "falsch"})
    assert bad.status_code == 401


def test_me_requires_token(client, admin_headers):
    assert client.get("/api/auth/me").status_code == 401
    me = client.get("/api/auth/me", headers=admin_headers)
    assert me.status_code == 200
    assert me.json()["username"] == "admin"


# --------------------------- Rechteprüfung ----------------------------------

def test_restricted_user_cannot_access_admin(client, admin_headers):
    # 'lesend'-Benutzer anlegen
    payload = {"username": "leser1", "full_name": "Nur Lesen", "roles": ["lesend"], "password": "geheim123"}
    r = client.post("/api/users", json=payload, headers=admin_headers)
    assert r.status_code in (200, 201), r.text

    login = client.post("/api/auth/login", json={"username": "leser1", "password": "geheim123"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    # Admin-Endpunkt (Benutzerverwaltung) muss für 'lesend' gesperrt sein.
    forbidden = client.get("/api/users", headers=_auth(token))
    assert forbidden.status_code == 403
    # Admin selbst darf.
    assert client.get("/api/users", headers=admin_headers).status_code == 200


# --------------------------- Artikel + Ausgabe/Rücknahme --------------------

def _create_article(client, admin_headers, kleidung_type, **extra):
    cat_id, type_id = kleidung_type
    body = {"category_id": cat_id, "type_id": type_id, "size": "M"}
    body.update(extra)
    r = client.post("/api/articles", json=body, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_article_create_and_list(client, admin_headers, kleidung_type):
    art = _create_article(client, admin_headers, kleidung_type)
    assert art["status"] == "verfuegbar"
    assert art["artikelnummer"]

    lst = client.get("/api/articles", headers=admin_headers).json()
    assert any(a["id"] == art["id"] for a in lst)


def test_issue_and_return_flow(client, admin_headers, kleidung_type):
    art = _create_article(client, admin_headers, kleidung_type)

    person = client.post("/api/persons", json={"first_name": "Max", "last_name": "Muster"},
                         headers=admin_headers)
    assert person.status_code == 200, person.text
    pid = person.json()["id"]

    issue = client.post("/api/issues/issue",
                        json={"article_id": art["id"], "person_id": pid},
                        headers=admin_headers)
    assert issue.status_code == 200, issue.text
    issue_id = issue.json()["id"]

    after = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert after["status"] == "ausgegeben"

    ret = client.post(f"/api/issues/{issue_id}/return", json={}, headers=admin_headers)
    assert ret.status_code == 200, ret.text

    back = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert back["status"] == "verfuegbar"


# --------------------------- Inventur ---------------------------------------

def _create_node(client, admin_headers, name):
    r = client.post("/api/storage-nodes", json={"name": name, "level": "standort"},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_inventory_progress_and_scan(client, admin_headers, kleidung_type):
    node_id = _create_node(client, admin_headers, "Testhalle")
    art = _create_article(client, admin_headers, kleidung_type, storage_node_id=node_id)

    camp = client.post("/api/inventory/campaigns",
                       json={"name": "Testinventur", "scope_type": "nodes",
                             "scope_node_ids": [node_id]},
                       headers=admin_headers)
    assert camp.status_code == 200, camp.text
    cid = camp.json()["id"]
    assert camp.json()["expected_count"] >= 1

    started = client.post(f"/api/inventory/campaigns/{cid}/status?action=start",
                          headers=admin_headers)
    assert started.status_code == 200, started.text

    scan = client.post(f"/api/inventory/campaigns/{cid}/scan",
                       json={"article_ids": [art["id"]], "storage_node_id": node_id},
                       headers=admin_headers)
    assert scan.status_code == 200, scan.text
    assert scan.json()["found_total"] >= 1

    detail = client.get(f"/api/inventory/campaigns/{cid}", headers=admin_headers).json()
    assert detail["found_count"] >= 1


def test_inventory_steps_and_report(client, admin_headers, kleidung_type):
    n1 = _create_node(client, admin_headers, "Raum A")
    n2 = _create_node(client, admin_headers, "Raum B")
    _create_article(client, admin_headers, kleidung_type, storage_node_id=n1)

    camp = client.post("/api/inventory/campaigns",
                       json={"name": "Rundgang", "scope_type": "nodes", "scope_node_ids": [n1, n2]},
                       headers=admin_headers)
    cid = camp.json()["id"]

    # Stationen aus dem Geltungsbereich erzeugen
    gen = client.post(f"/api/inventory/campaigns/{cid}/steps/generate",
                      json={"node_ids": [], "replace": True}, headers=admin_headers)
    assert gen.status_code == 200, gen.text
    steps = gen.json()
    assert len(steps) == 2

    # Reihenfolge umdrehen
    reordered = client.put(f"/api/inventory/campaigns/{cid}/steps/reorder",
                           json={"ordered_ids": [steps[1]["id"], steps[0]["id"]]},
                           headers=admin_headers)
    assert reordered.status_code == 200
    assert reordered.json()[0]["id"] == steps[1]["id"]

    # Eine Station als erledigt markieren
    done = client.post(f"/api/inventory/campaigns/{cid}/steps/{steps[0]['id']}/status",
                       json={"status": "done"}, headers=admin_headers)
    assert done.status_code == 200
    assert any(s["status"] == "done" for s in done.json())

    # Abschlussbericht (PDF + CSV) muss ausliefern
    pdf = client.get(f"/api/inventory/campaigns/{cid}/report?format=pdf", headers=admin_headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"

    csv_r = client.get(f"/api/inventory/campaigns/{cid}/report?format=csv", headers=admin_headers)
    assert csv_r.status_code == 200
    assert b"Abschlussbericht" in csv_r.content


def test_inventory_template_and_campaign_from_template(client, admin_headers):
    n = _create_node(client, admin_headers, "Vorlagenraum")
    tpl = client.post("/api/inventory/templates",
                      json={"name": "Standardrundgang", "steps": [{"node_id": n, "label": ""}]},
                      headers=admin_headers)
    assert tpl.status_code == 200, tpl.text
    tid = tpl.json()["id"]
    assert len(tpl.json()["steps"]) == 1

    camp = client.post("/api/inventory/campaigns/from-templates",
                       json={"name": "Aus Vorlage", "template_ids": [tid]},
                       headers=admin_headers)
    assert camp.status_code == 200, camp.text
    cid = camp.json()["id"]
    steps = client.get(f"/api/inventory/campaigns/{cid}/steps", headers=admin_headers).json()
    assert len(steps) == 1


def test_mark_missing_sets_verschollen(client, admin_headers, kleidung_type):
    node_id = _create_node(client, admin_headers, "Fehlraum")
    art = _create_article(client, admin_headers, kleidung_type, storage_node_id=node_id)

    camp = client.post("/api/inventory/campaigns",
                       json={"name": "Fehlinventur", "scope_type": "nodes", "scope_node_ids": [node_id]},
                       headers=admin_headers)
    cid = camp.json()["id"]
    client.post(f"/api/inventory/campaigns/{cid}/status?action=start", headers=admin_headers)

    # Ohne Scan bleibt der Artikel offen/fehlend -> als verschollen markieren.
    r = client.post(f"/api/inventory/campaigns/{cid}/mark-missing", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["marked"] >= 1

    got = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert got["status"] == "verschollen"


def test_report_is_archived_on_finish(client, admin_headers, kleidung_type):
    node_id = _create_node(client, admin_headers, "Archivraum")
    _create_article(client, admin_headers, kleidung_type, storage_node_id=node_id)
    camp = client.post("/api/inventory/campaigns",
                       json={"name": "Archivinventur", "scope_type": "nodes", "scope_node_ids": [node_id]},
                       headers=admin_headers)
    cid = camp.json()["id"]
    client.post(f"/api/inventory/campaigns/{cid}/status?action=start", headers=admin_headers)
    fin = client.post(f"/api/inventory/campaigns/{cid}/status?action=finish", headers=admin_headers)
    assert fin.status_code == 200, fin.text

    reports = client.get("/api/inventory/reports", headers=admin_headers).json()
    mine = [r for r in reports if r["campaign_id"] == cid]
    assert mine, "Beim Abschluss sollte ein Bericht archiviert werden"
    rid = mine[0]["id"]

    pdf = client.get(f"/api/inventory/reports/{rid}/pdf", headers=admin_headers)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_psa_inspection_on_return(client, admin_headers, kleidung_type):
    _cat, type_id = kleidung_type
    cl = client.post("/api/inspection/checklists",
                     json={"name": "Sichtprüfung", "items": [{"label": "Nähte ok"}, {"label": "Sauber"}]},
                     headers=admin_headers).json()
    rr = client.post("/api/inspection/rules",
                     json={"type_id": type_id, "trigger": "return", "checklist_id": cl["id"]},
                     headers=admin_headers)
    assert rr.status_code == 200, rr.text
    art = _create_article(client, admin_headers, kleidung_type, is_psa=True)
    person = client.post("/api/persons", json={"first_name": "PSA", "last_name": "Test"},
                         headers=admin_headers).json()
    iss = client.post("/api/issues/issue", json={"article_id": art["id"], "person_id": person["id"]},
                      headers=admin_headers).json()
    client.post(f"/api/issues/{iss['id']}/return", json={}, headers=admin_headers)
    a = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert a["status"] == "zu_pruefen"
    assert a["pending_checklist_id"] == cl["id"]
    assert a["loan_count"] == 1
    # Ausgabe im Status „zu prüfen" gesperrt
    r = client.post("/api/issues/issue", json={"article_id": art["id"], "person_id": person["id"]},
                    headers=admin_headers)
    assert r.status_code == 400
    # Gewaschen zählt
    w = client.post(f"/api/articles/{art['id']}/washed", json={}, headers=admin_headers).json()
    assert w["wash_count"] == 1


def test_inspection_workflow(client, admin_headers, kleidung_type):
    _cat, type_id = kleidung_type
    cl = client.post("/api/inspection/checklists",
                     json={"name": "Vollcheck", "items": [{"label": "A"}, {"label": "B"}]},
                     headers=admin_headers).json()
    client.post("/api/inspection/rules",
                json={"type_id": type_id, "trigger": "return", "checklist_id": cl["id"]},
                headers=admin_headers)
    art = _create_article(client, admin_headers, kleidung_type, is_psa=True)
    person = client.post("/api/persons", json={"first_name": "W", "last_name": "F"},
                         headers=admin_headers).json()
    iss = client.post("/api/issues/issue", json={"article_id": art["id"], "person_id": person["id"]},
                      headers=admin_headers).json()
    client.post(f"/api/issues/{iss['id']}/return", json={}, headers=admin_headers)
    assert any(p["id"] == art["id"] for p in client.get("/api/inspection/pending", headers=admin_headers).json())
    insp = client.post("/api/inspection/start", json={"article_id": art["id"]}, headers=admin_headers).json()
    assert len(insp["results"]) == 2
    for it in insp["results"]:
        client.post(f"/api/inspection/{insp['id']}/item", json={"item_id": it["id"], "ok": True}, headers=admin_headers)
    fin = client.post(f"/api/inspection/{insp['id']}/finish", json={"result": "passed", "overall_note": "ok"},
                      headers=admin_headers)
    assert fin.status_code == 200 and fin.json()["status"] == "done"
    a = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert a["status"] == "verfuegbar" and a["pending_checklist_id"] is None and a["needs_inspection"] is False
    prot = client.get(f"/api/inspection/by-article/{art['id']}", headers=admin_headers).json()
    assert any(x["status"] == "done" for x in prot)
    pdf = client.get(f"/api/inspection/{insp['id']}/protocol.pdf", headers=admin_headers)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_psa_inspection_while_issued(client, admin_headers, kleidung_type):
    """PSA soll auch während der Ausgabe geprüft werden können: Auslöser „nach X
    Ausleihen" markiert den Artikel prüfpflichtig, ohne die laufende Ausleihe zu
    beenden; bestandene Prüfung lässt den Artikel ausgegeben."""
    _cat, type_id = kleidung_type
    cl = client.post("/api/inspection/checklists",
                     json={"name": "L", "items": [{"label": "Sicht"}]}, headers=admin_headers).json()
    client.post("/api/inspection/rules",
                json={"type_id": type_id, "trigger": "loans", "threshold": 1, "checklist_id": cl["id"]},
                headers=admin_headers)
    art = _create_article(client, admin_headers, kleidung_type, is_psa=True)
    person = client.post("/api/persons", json={"first_name": "I", "last_name": "P"},
                         headers=admin_headers).json()
    client.post("/api/issues/issue", json={"article_id": art["id"], "person_id": person["id"]},
                headers=admin_headers)
    a = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert a["status"] == "ausgegeben" and a["needs_inspection"] is True
    pend = client.get("/api/inspection/pending", headers=admin_headers).json()
    row = next(p for p in pend if p["id"] == art["id"])
    assert row["issued"] is True
    insp = client.post("/api/inspection/start", json={"article_id": art["id"]}, headers=admin_headers).json()
    for it in insp["results"]:
        client.post(f"/api/inspection/{insp['id']}/item", json={"item_id": it["id"], "ok": True}, headers=admin_headers)
    client.post(f"/api/inspection/{insp['id']}/finish", json={"result": "passed"}, headers=admin_headers)
    a = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert a["status"] == "ausgegeben" and a["needs_inspection"] is False


def test_article_inspection_override(client, admin_headers, kleidung_type):
    """Einzelartikel-Override: eigene Regel „einmalig bei Rückgabe" greift statt der
    Typ-Regel und feuert nur ein einziges Mal."""
    _cat, type_id = kleidung_type
    # Typ-Regel „nach 1 Ausleihe" – soll durch Override ausgehebelt werden
    tcl = client.post("/api/inspection/checklists",
                      json={"name": "Typ", "items": [{"label": "T"}]}, headers=admin_headers).json()
    client.post("/api/inspection/rules",
                json={"type_id": type_id, "trigger": "loans", "threshold": 1, "checklist_id": tcl["id"]},
                headers=admin_headers)
    acl = client.post("/api/inspection/checklists",
                      json={"name": "Einzel", "items": [{"label": "E"}]}, headers=admin_headers).json()
    art = _create_article(client, admin_headers, kleidung_type, is_psa=True)
    # Override aktivieren + eigene Regel „return_once"
    client.put(f"/api/inspection/article-rules/{art['id']}/override", json={"enabled": True}, headers=admin_headers)
    client.post(f"/api/inspection/article-rules/{art['id']}",
                json={"trigger": "return_once", "checklist_id": acl["id"]}, headers=admin_headers)
    person = client.post("/api/persons", json={"first_name": "O", "last_name": "R"}, headers=admin_headers).json()
    # 1. Ausleihe: Typ-Regel würde feuern, Override verhindert das (kein return)
    iss = client.post("/api/issues/issue", json={"article_id": art["id"], "person_id": person["id"]},
                      headers=admin_headers).json()
    a = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert a["needs_inspection"] is False   # Typ-loans-Regel greift NICHT (Override aktiv)
    # Rückgabe -> return_once feuert
    client.post(f"/api/issues/{iss['id']}/return", json={}, headers=admin_headers)
    a = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert a["status"] == "zu_pruefen" and a["needs_inspection"] is True
    insp = client.post("/api/inspection/start", json={"article_id": art["id"]}, headers=admin_headers).json()
    for it in insp["results"]:
        client.post(f"/api/inspection/{insp['id']}/item", json={"item_id": it["id"], "ok": True}, headers=admin_headers)
    client.post(f"/api/inspection/{insp['id']}/finish", json={"result": "passed"}, headers=admin_headers)
    # 2. Ausleihe + Rückgabe -> return_once feuert NICHT erneut (einmalig)
    iss2 = client.post("/api/issues/issue", json={"article_id": art["id"], "person_id": person["id"]},
                       headers=admin_headers).json()
    client.post(f"/api/issues/{iss2['id']}/return", json={}, headers=admin_headers)
    a = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert a["needs_inspection"] is False


def test_maintenance_types(client, admin_headers):
    """Prüf-/Terminarten: anlegen mit Erfassungsfeldern, archivieren, gefiltert listen."""
    cl = client.post("/api/inspection/checklists",
                     json={"name": "TÜV-Check", "items": [{"label": "Bremsen"}]}, headers=admin_headers).json()
    r = client.post("/api/maintenance/types", json={
        "name": "TÜV", "checklist_id": cl["id"], "interval_months": 24,
        "km_based": True, "interval_km": 20000, "trigger_event": "",
        "fields": ["Prüfstelle", "Kilometerstand"]}, headers=admin_headers)
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["interval_months"] == 24 and t["km_based"] is True and len(t["fields"]) == 2
    # archivieren -> nicht in Standardliste
    client.put(f"/api/maintenance/types/{t['id']}", json={"active": False}, headers=admin_headers)
    active = client.get("/api/maintenance/types", headers=admin_headers).json()
    assert all(x["id"] != t["id"] for x in active)
    allt = client.get("/api/maintenance/types?include_archived=true", headers=admin_headers).json()
    assert any(x["id"] == t["id"] for x in allt)


def test_size_field_options(client, admin_headers):
    """Größenart mit erlaubten Werten anlegen und ändern."""
    f = client.post("/api/size-fields", json={"label": "Shirt", "options": ["S", "M", "L", "XL"]},
                    headers=admin_headers)
    assert f.status_code == 200, f.text
    fid = f.json()["id"]
    assert f.json()["options"] == ["S", "M", "L", "XL"]
    upd = client.put(f"/api/size-fields/{fid}", json={"options": ["6", "7", "8", "9"]}, headers=admin_headers)
    assert upd.status_code == 200 and upd.json()["options"] == ["6", "7", "8", "9"]
    got = client.get("/api/size-fields", headers=admin_headers).json()
    assert any(x["id"] == fid and x["options"] == ["6", "7", "8", "9"] for x in got)


def test_subcategory_inherits(client, admin_headers):
    """Unterkategorie: erbt Ausgebbar-Standard beim Anlegen; Wartungs-Zuweisung an der
    Oberkategorie gilt auch für Artikel der Unterkategorie."""
    parent = client.post("/api/categories", json={"name": "Funk"}, headers=admin_headers).json()
    client.put(f"/api/categories/{parent['id']}/issuable", json={"issuable": False}, headers=admin_headers)
    sub = client.post("/api/categories", json={"name": "Digital", "parent_id": parent["id"]}, headers=admin_headers).json()
    cats = client.get("/api/categories", headers=admin_headers).json()
    subc = next(c for c in cats if c["id"] == sub["id"])
    assert subc["parent_id"] == parent["id"] and subc["parent_name"] == "Funk"
    assert subc["issuable_default"] is False   # von Oberkategorie geerbt
    # nur eine Ebene: Unter-Unterkategorie wird abgelehnt
    r = client.post("/api/categories", json={"name": "DMR", "parent_id": sub["id"]}, headers=admin_headers)
    assert r.status_code == 400
    # Wartungs-Zuweisung an Oberkategorie -> gilt für Artikel der Unterkategorie
    mt = client.post("/api/maintenance/types", json={"name": "Inspektion"}, headers=admin_headers).json()
    client.post("/api/maintenance/assignments", json={"mtype_id": mt["id"], "category_id": parent["id"]}, headers=admin_headers)
    typ = client.post("/api/types", json={"name": "HRT", "category_id": sub["id"]}, headers=admin_headers).json()
    art = client.post("/api/articles", json={"category_id": sub["id"], "type_id": typ["id"]}, headers=admin_headers).json()
    items = client.get(f"/api/maintenance/article/{art['id']}", headers=admin_headers).json()
    assert any(i["mtype_id"] == mt["id"] and i["source"] == "category" for i in items)


def test_maintenance_assignment_and_schedule(client, admin_headers, kleidung_type):
    """Zuweisung je Kategorie greift für Artikel; Artikel-Ausschluss hebt sie auf;
    Termin je Artikel setzbar."""
    cat_id, type_id = kleidung_type
    mt = client.post("/api/maintenance/types", json={"name": "Inspektion", "interval_months": 12},
                     headers=admin_headers).json()
    art = _create_article(client, admin_headers, kleidung_type)
    # Kategorie-Zuweisung -> gilt für den Artikel (Quelle: category)
    client.post("/api/maintenance/assignments", json={"mtype_id": mt["id"], "category_id": cat_id},
                headers=admin_headers)
    items = client.get(f"/api/maintenance/article/{art['id']}", headers=admin_headers).json()
    assert any(i["mtype_id"] == mt["id"] and i["source"] == "category" for i in items)
    # Termin setzen
    sch = client.post(f"/api/maintenance/article/{art['id']}/schedule",
                      json={"mtype_id": mt["id"], "due_date": "2027-01-01T00:00:00"}, headers=admin_headers)
    assert sch.status_code == 200 and sch.json()["due_date"] is not None
    # Artikel-Ausschluss -> verschwindet
    client.post("/api/maintenance/assignments",
                json={"mtype_id": mt["id"], "article_id": art["id"], "mode": "exclude"}, headers=admin_headers)
    items2 = client.get(f"/api/maintenance/article/{art['id']}", headers=admin_headers).json()
    assert all(i["mtype_id"] != mt["id"] for i in items2)


def test_vehicle_as_storage_node(client, admin_headers, kleidung_type):
    """Ein Fahrzeug ist Artikel UND Lagerort-Knoten: aktivierbar unter einem Standort,
    kann eigene Unterknoten (Schrank) enthalten."""
    art = _create_article(client, admin_headers, kleidung_type, is_vehicle=True, license_plate="XX-DRK 1")
    assert art["is_vehicle"] is True and art["vehicle_node_id"] is None
    standort = client.post("/api/storage-nodes", json={"name": "Gerätehaus", "level": "standort"},
                           headers=admin_headers).json()
    node = client.post(f"/api/articles/{art['id']}/vehicle-node", json={"parent_id": standort["id"]},
                       headers=admin_headers)
    assert node.status_code == 200, node.text
    node = node.json()
    assert node["level"] == "fahrzeug" and node["vehicle_article_id"] == art["id"] and node["parent_id"] == standort["id"]
    a = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert a["vehicle_node_id"] == node["id"]
    # Unterknoten (Schrank) im Fahrzeug anlegen
    child = client.post("/api/storage-nodes", json={"name": "Schrank A", "parent_id": node["id"]},
                        headers=admin_headers).json()
    assert child["parent_id"] == node["id"] and child["level"] == "schrank"


def test_damage_report(client, admin_headers, kleidung_type):
    """Schadensmeldung setzt Artikel auf Reparatur, erscheint im Eingang, PDF abrufbar;
    Erledigen schließt sie. Verlustmeldung setzt auf verschollen."""
    art = _create_article(client, admin_headers, kleidung_type)
    # Ohne Pflichtangaben -> unvollständig
    r = client.post("/api/reports", json={"article_id": art["id"], "kind": "damage",
                                          "description": "Riss im Stoff"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["complete"] is False
    a = client.get(f"/api/articles/{art['id']}", headers=admin_headers).json()
    assert a["status"] == "reparatur"
    inbox = client.get("/api/reports?inbox=true", headers=admin_headers).json()
    assert any(x["id"] == rep["id"] for x in inbox)
    cnt = client.get("/api/reports/inbox-count", headers=admin_headers).json()
    assert cnt["incomplete"] >= 1
    # Vervollständigen -> complete True
    upd = client.put(f"/api/reports/{rep['id']}", json={
        "incident_at": "2026-08-01T10:00:00", "incident_location": "Gerätehaus",
        "police_reference": "AZ 123"}, headers=admin_headers)
    assert upd.status_code == 200 and upd.json()["complete"] is True
    pdf = client.get(f"/api/reports/{rep['id']}/pdf", headers=admin_headers)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    done = client.post(f"/api/reports/{rep['id']}/resolve", json={"resolution_note": "genäht"}, headers=admin_headers)
    assert done.status_code == 200 and done.json()["status"] == "done"
    assert client.get("/api/reports?inbox=true", headers=admin_headers).json() == [] or \
        all(x["id"] != rep["id"] for x in client.get("/api/reports?inbox=true", headers=admin_headers).json())
    # Verlust
    art2 = _create_article(client, admin_headers, kleidung_type)
    client.post("/api/reports", json={"article_id": art2["id"], "kind": "loss"}, headers=admin_headers)
    a2 = client.get(f"/api/articles/{art2['id']}", headers=admin_headers).json()
    assert a2["status"] == "verschollen"


def test_inspection_abort(client, admin_headers, kleidung_type):
    _cat, type_id = kleidung_type
    cl = client.post("/api/inspection/checklists",
                     json={"name": "A", "items": [{"label": "X"}]}, headers=admin_headers).json()
    client.post("/api/inspection/rules",
                json={"type_id": type_id, "trigger": "return", "checklist_id": cl["id"]}, headers=admin_headers)
    art = _create_article(client, admin_headers, kleidung_type, is_psa=True)
    person = client.post("/api/persons", json={"first_name": "A", "last_name": "B"}, headers=admin_headers).json()
    iss = client.post("/api/issues/issue", json={"article_id": art["id"], "person_id": person["id"]},
                      headers=admin_headers).json()
    client.post(f"/api/issues/{iss['id']}/return", json={}, headers=admin_headers)
    insp = client.post("/api/inspection/start", json={"article_id": art["id"]}, headers=admin_headers).json()
    r = client.post(f"/api/inspection/{insp['id']}/abort", headers=admin_headers)
    assert r.status_code == 200
    # Artikel bleibt prüfpflichtig, Prüfung ist weg
    assert client.get(f"/api/inspection/{insp['id']}", headers=admin_headers).status_code == 404
    assert any(p["id"] == art["id"] for p in client.get("/api/inspection/pending", headers=admin_headers).json())


def test_revoke_capability(client, admin_headers, kleidung_type):
    _cat, type_id = kleidung_type
    client.post("/api/users", json={"username": "revuser", "full_name": "Rev",
                                    "roles": ["helfer"], "password": "geheim123"}, headers=admin_headers)
    uid = next(u["id"] for u in client.get("/api/users", headers=admin_headers).json() if u["username"] == "revuser")
    tok = client.post("/api/auth/login", json={"username": "revuser", "password": "geheim123"}).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    assert "requests" in client.get("/api/auth/me", headers=hdr).json()["capabilities"]
    # Recht persoenlich entziehen
    client.put(f"/api/users/{uid}/revoked-capabilities", json={"revoked": ["requests"]}, headers=admin_headers)
    me = client.get("/api/auth/me", headers=hdr).json()
    assert "requests" not in me["capabilities"]
    assert me["revoked_capabilities"] == ["requests"]
    # Anfrage jetzt gesperrt
    assert client.post("/api/requests", json={"type_id": type_id, "quantity": 1}, headers=hdr).status_code == 403


def test_material_requests(client, admin_headers, kleidung_type):
    _cat, type_id = kleidung_type
    r = client.post("/api/requests", json={"type_id": type_id, "size": "M", "quantity": 3, "note": "für Übung"},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert r.json()["status"] == "open"
    mine = client.get("/api/requests?mine=true", headers=admin_headers).json()
    assert any(x["id"] == rid for x in mine)
    # Admin ist zuständig -> im Eingang und entscheidbar
    inbox = client.get("/api/requests?inbox=true", headers=admin_headers).json()
    assert any(x["id"] == rid for x in inbox)
    d = client.post(f"/api/requests/{rid}/decision", json={"status": "approved"}, headers=admin_headers)
    assert d.status_code == 200 and d.json()["status"] == "approved"


def test_receipts(client, admin_headers, kleidung_type):
    art = _create_article(client, admin_headers, kleidung_type)
    p = client.post("/api/persons", json={"first_name": "Quitt", "last_name": "Ung"},
                    headers=admin_headers).json()
    client.post("/api/issues/issue", json={"article_id": art["id"], "person_id": p["id"]},
                headers=admin_headers)
    # Unsignierte Quittung (2 Ausfertigungen)
    g = client.get(f"/api/receipts/generate?person_id={p['id']}&kind=issue&copies=2", headers=admin_headers)
    assert g.status_code == 200 and g.content[:4] == b"%PDF"
    # Digital ablegen (ohne echte Unterschrift)
    d = client.post("/api/receipts/digital", json={"person_id": p["id"], "kind": "issue", "copies": 1},
                    headers=admin_headers)
    assert d.status_code == 200, d.text
    rid = d.json()["id"]
    lst = client.get(f"/api/receipts?person_id={p['id']}", headers=admin_headers).json()
    assert any(x["id"] == rid for x in lst)
    f = client.get(f"/api/receipts/{rid}/file", headers=admin_headers)
    assert f.status_code == 200


def test_person_material_pdf(client, admin_headers, kleidung_type):
    art = _create_article(client, admin_headers, kleidung_type)
    person = client.post("/api/persons", json={"first_name": "Lena", "last_name": "Helfer"},
                         headers=admin_headers)
    pid = person.json()["id"]
    client.post("/api/issues/issue", json={"article_id": art["id"], "person_id": pid},
                headers=admin_headers)

    pdf = client.get(f"/api/export/person/{pid}/pdf", headers=admin_headers)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_personal_reminder_setting(client, admin_headers):
    r = client.post("/api/auth/reminder", json={"days": 5}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["reminder_days_before"] == 5
    me = client.get("/api/auth/me", headers=admin_headers).json()
    assert me["reminder_days_before"] == 5
    # Zurueck auf Standard (None)
    r2 = client.post("/api/auth/reminder", json={"days": None}, headers=admin_headers)
    assert r2.status_code == 200
    me2 = client.get("/api/auth/me", headers=admin_headers).json()
    assert me2["reminder_days_before"] is None


def test_campaign_reminder_default(client, admin_headers):
    camp = client.post("/api/inventory/campaigns",
                       json={"name": "Erinnerungstest", "scope_type": "full", "reminder_days_before": 7},
                       headers=admin_headers)
    assert camp.status_code == 200, camp.text
    assert camp.json()["reminder_days_before"] == 7


def test_issue_with_expected_return(client, admin_headers, kleidung_type):
    art = _create_article(client, admin_headers, kleidung_type)
    person = client.post("/api/persons", json={"first_name": "Timo", "last_name": "Frist"},
                         headers=admin_headers).json()
    due = "2020-01-01T00:00:00"   # bewusst in der Vergangenheit -> ueberfaellig
    r = client.post("/api/issues/issue",
                    json={"article_id": art["id"], "person_id": person["id"], "expected_return_date": due},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["expected_return_date"] is not None
    # taucht in der Ueberfaellig-Liste des Dashboards auf
    dash = client.get("/api/stats/dashboard", headers=admin_headers).json()
    assert any(o["article_id"] == art["id"] for o in dash["overdue"])


def test_issuable_flag(client, admin_headers, kleidung_type):
    cat_id, _t = kleidung_type
    # Einzelartikel-Override „nicht ausgebbar" → Ausgabe gesperrt
    art = _create_article(client, admin_headers, kleidung_type, issuable_override=False)
    assert art["is_issuable"] is False
    person = client.post("/api/persons", json={"first_name": "Nix", "last_name": "Ausgabe"},
                         headers=admin_headers).json()
    r = client.post("/api/issues/issue", json={"article_id": art["id"], "person_id": person["id"]},
                    headers=admin_headers)
    assert r.status_code == 400

    # Klassen-Default auf „nicht ausgebbar"; Artikel ohne Override erbt das
    client.put(f"/api/categories/{cat_id}/issuable", json={"issuable": False}, headers=admin_headers)
    art2 = _create_article(client, admin_headers, kleidung_type)
    assert art2["is_issuable"] is False
    client.put(f"/api/categories/{cat_id}/issuable", json={"issuable": True}, headers=admin_headers)


def test_person_sizes(client, admin_headers):
    fields = client.get("/api/size-fields", headers=admin_headers).json()
    assert fields, "Standard-Größenarten sollten geseedet sein"
    fid = str(fields[0]["id"])
    p = client.post("/api/persons", json={"first_name": "Gina", "last_name": "Groesse"},
                    headers=admin_headers).json()
    r = client.put(f"/api/persons/{p['id']}", json={"sizes": {fid: "M"}}, headers=admin_headers)
    assert r.status_code == 200, r.text
    got = client.get(f"/api/persons/{p['id']}", headers=admin_headers).json()
    assert got["sizes"].get(fid) == "M"


def test_size_field_admin(client, admin_headers):
    r = client.post("/api/size-fields", json={"label": "Krawatte"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    fid = r.json()["id"]
    lst = client.get("/api/size-fields", headers=admin_headers).json()
    assert any(f["label"] == "Krawatte" for f in lst)
    client.delete(f"/api/size-fields/{fid}", headers=admin_headers)


def test_min_stock_rule_breach(client, admin_headers, kleidung_type):
    _cat, type_id = kleidung_type
    r = client.post("/api/stats/min-stock-rules",
                    json={"type_id": type_id, "size": "", "min_stock": 9999}, headers=admin_headers)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    dash = client.get("/api/stats/dashboard", headers=admin_headers).json()
    assert any(l["min_stock"] == 9999 for l in dash["low_stock"])
    client.delete(f"/api/stats/min-stock-rules/{rid}", headers=admin_headers)


def test_analytics_access_and_scope(client, admin_headers, kleidung_type):
    cat_id, _t = kleidung_type
    client.post("/api/users", json={"username": "noana", "full_name": "Kein Zugriff",
                                    "roles": ["helfer"], "password": "geheim123"}, headers=admin_headers)
    tok = client.post("/api/auth/login", json={"username": "noana", "password": "geheim123"}).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/stats/access", headers=hdr).json()["can_view"] is False
    assert client.get("/api/stats/dashboard", headers=hdr).status_code == 403

    uid = next(u["id"] for u in client.get("/api/users", headers=admin_headers).json() if u["username"] == "noana")
    r = client.post("/api/stats/material-managers", json={"user_id": uid, "category_id": cat_id}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert client.get("/api/stats/access", headers=hdr).json()["can_view"] is True
    assert client.get("/api/stats/dashboard", headers=hdr).status_code == 200


def test_dashboard_and_data_quality(client, admin_headers, kleidung_type):
    _create_article(client, admin_headers, kleidung_type)   # ohne Lagerort/Foto

    dash = client.get("/api/stats/dashboard", headers=admin_headers)
    assert dash.status_code == 200, dash.text
    body = dash.json()
    assert body["total"] >= 1
    assert isinstance(body["by_status"], list)
    assert isinstance(body["by_location"], list)

    dq = client.get("/api/stats/data-quality", headers=admin_headers)
    assert dq.status_code == 200, dq.text
    qb = dq.json()
    # der eben angelegte Artikel hat weder Lagerort noch Foto
    assert qb["no_location"]["count"] >= 1
    assert qb["no_photo"]["count"] >= 1
    assert "duplicates" in qb


# --------------------------- DSGVO ------------------------------------------

def test_person_anonymize(client, admin_headers):
    person = client.post("/api/persons", json={"first_name": "Erika", "last_name": "Geheim"},
                         headers=admin_headers)
    pid = person.json()["id"]

    res = client.post(f"/api/persons/{pid}/anonymize", headers=admin_headers)
    assert res.status_code == 200, res.text

    got = client.get(f"/api/persons/{pid}", headers=admin_headers).json()
    assert got["first_name"].startswith("Anonymisiert") or got["last_name"].startswith("Anonymisiert") \
        or "Anonym" in (got["first_name"] + got["last_name"])
    assert got["active"] is False
