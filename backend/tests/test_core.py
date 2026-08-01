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


def test_type_min_stock(client, admin_headers, kleidung_type):
    _cat, type_id = kleidung_type
    r = client.put(f"/api/types/{type_id}/min-stock", json={"min_stock": 999}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["min_stock"] == 999
    dash = client.get("/api/stats/dashboard", headers=admin_headers).json()
    # bei Schwelle 999 duerfte der verfuegbare Bestand darunter liegen
    assert any(l["min_stock"] == 999 for l in dash["low_stock"])
    # wieder ausschalten
    client.put(f"/api/types/{type_id}/min-stock", json={"min_stock": 0}, headers=admin_headers)


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
