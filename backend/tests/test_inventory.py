def test_create_inventory_campaign(client, auth_headers):
    """Test creating an inventory campaign."""
    response = client.post("/api/v1/inventory/campaigns", headers=auth_headers, json={
        "name": "Test Inventur",
        "scope_type": "full",
        "ignore_status": ["ausgegeben", "reparatur", "ausgemustert"],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Inventur"
    assert data["scope_type"] == "full"
    assert data["status"] == "planned"


def test_list_inventory_campaigns(client, auth_headers):
    """Test listing inventory campaigns."""
    client.post("/api/v1/inventory/campaigns", headers=auth_headers, json={
        "name": "Inventur 1", "scope_type": "full"
    })
    client.post("/api/v1/inventory/campaigns", headers=auth_headers, json={
        "name": "Inventur 2", "scope_type": "nodes"
    })
    
    response = client.get("/api/v1/inventory/campaigns", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2


def test_get_inventory_campaign(client, auth_headers):
    """Test getting a single campaign."""
    create_resp = client.post("/api/v1/inventory/campaigns", headers=auth_headers, json={
        "name": "Detail Test", "scope_type": "full"
    })
    campaign_id = create_resp.json()["id"]
    
    response = client.get(f"/api/v1/inventory/campaigns/{campaign_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == campaign_id
    assert data["name"] == "Detail Test"


def test_start_inventory_campaign(client, auth_headers):
    """Test starting an inventory campaign."""
    create_resp = client.post("/api/v1/inventory/campaigns", headers=auth_headers, json={
        "name": "Start Test", "scope_type": "full"
    })
    campaign_id = create_resp.json()["id"]
    
    response = client.post(f"/api/v1/inventory/campaigns/{campaign_id}/status?action=start", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["started_at"] is not None


def test_inventory_scan(client, auth_headers, test_category, test_type):
    """Test scanning articles during inventory."""
    # Create article
    art_resp = client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id, "type_id": test_type.id, "size": "M"
    })
    article_id = art_resp.json()["id"]
    
    # Create and start campaign
    camp_resp = client.post("/api/v1/inventory/campaigns", headers=auth_headers, json={
        "name": "Scan Test", "scope_type": "full"
    })
    campaign_id = camp_resp.json()["id"]
    client.post(f"/api/v1/inventory/campaigns/{campaign_id}/status?action=start", headers=auth_headers)
    
    # Scan article
    response = client.post(f"/api/v1/inventory/campaigns/{campaign_id}/scan", headers=auth_headers, json={
        "article_ids": [article_id],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["updated"] == 1
    assert data["found_total"] == 1


def test_create_storage_node(client, auth_headers):
    """Test creating a storage node."""
    response = client.post("/api/v1/storage-nodes", headers=auth_headers, json={
        "name": "Lagerhalle A",
        "level": "standort",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Lagerhalle A"
    assert data["level"] == "standort"


def test_create_nested_storage_node(client, auth_headers):
    """Test creating nested storage nodes (standort -> etage -> raum)."""
    # Create standort
    standort_resp = client.post("/api/v1/storage-nodes", headers=auth_headers, json={
        "name": "Hauptgebäude", "level": "standort"
    })
    standort_id = standort_resp.json()["id"]
    
    # Create etage under standort
    etage_resp = client.post("/api/v1/storage-nodes", headers=auth_headers, json={
        "name": "1. Obergeschoss", "level": "etage", "parent_id": standort_id
    })
    assert etage_resp.status_code == 200
    assert etage_resp.json()["parent_id"] == standort_id
    
    # Create raum under etage
    raum_resp = client.post("/api/v1/storage-nodes", headers=auth_headers, json={
        "name": "Büro 101", "level": "raum", "parent_id": etage_resp.json()["id"]
    })
    assert raum_resp.status_code == 200
    assert raum_resp.json()["level"] == "raum"


def test_list_storage_nodes(client, auth_headers):
    """Test listing storage nodes."""
    client.post("/api/v1/storage-nodes", headers=auth_headers, json={"name": "Node 1", "level": "standort"})
    client.post("/api/v1/storage-nodes", headers=auth_headers, json={"name": "Node 2", "level": "standort"})
    
    response = client.get("/api/v1/storage-nodes", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2