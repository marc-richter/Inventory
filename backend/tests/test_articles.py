def test_create_article(client, auth_headers, test_category, test_type, test_organization, test_storage_location):
    """Test creating an article."""
    response = client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id,
        "type_id": test_type.id,
        "size": "M",
        "organization_id": test_organization.id,
        "storage_location_id": test_storage_location.id,
        "condition_notes": "Neu",
        "remarks": "Test artikel"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["category_id"] == test_category.id
    assert data["type_id"] == test_type.id
    assert data["size"] == "M"
    assert data["status"] == "verfuegbar"
    assert "artikelnummer" in data
    assert data["artikelnummer"].startswith("20")  # Year prefix


def test_create_article_minimal(client, auth_headers, test_category, test_type):
    """Test creating an article with minimal required fields."""
    response = client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id,
        "type_id": test_type.id,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["category_id"] == test_category.id
    assert data["type_id"] == test_type.id
    assert data["status"] == "verfuegbar"


def test_list_articles(client, auth_headers, test_category, test_type):
    """Test listing articles."""
    # Create a few articles first
    for i in range(3):
        client.post("/api/v1/articles", headers=auth_headers, json={
            "category_id": test_category.id,
            "type_id": test_type.id,
            "size": f"Size{i}",
        })
    
    response = client.get("/api/v1/articles", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


def test_get_article(client, auth_headers, test_category, test_type):
    """Test getting a single article."""
    # Create article
    create_resp = client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id,
        "type_id": test_type.id,
        "size": "L",
    })
    article_id = create_resp.json()["id"]
    
    # Get article
    response = client.get(f"/api/v1/articles/{article_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == article_id
    assert data["size"] == "L"


def test_update_article(client, auth_headers, test_category, test_type):
    """Test updating an article."""
    create_resp = client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id,
        "type_id": test_type.id,
        "size": "S",
    })
    article_id = create_resp.json()["id"]
    
    response = client.put(f"/api/v1/articles/{article_id}", headers=auth_headers, json={
        "size": "XL",
        "remarks": "Updated"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["size"] == "XL"
    assert data["remarks"] == "Updated"


def test_delete_article(client, auth_headers, test_category, test_type):
    """Test deleting an article."""
    create_resp = client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id,
        "type_id": test_type.id,
    })
    article_id = create_resp.json()["id"]
    
    response = client.delete(f"/api/v1/articles/{article_id}", headers=auth_headers)
    assert response.status_code == 200
    
    # Verify it's gone
    response = client.get(f"/api/v1/articles/{article_id}", headers=auth_headers)
    assert response.status_code == 404


def test_bulk_create_articles(client, auth_headers, test_category, test_type):
    """Test bulk article creation."""
    response = client.post("/api/v1/articles/bulk", headers=auth_headers, json={
        "category_id": test_category.id,
        "type_id": test_type.id,
        "size": "M",
        "quantity": 3,
    })
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3
    # Check all have sequential artikelnummer
    nums = [a["artikelnummer"] for a in data]
    assert len(set(nums)) == 3  # All unique


def test_bulk_create_with_custom_numbers(client, auth_headers, test_category, test_type):
    """Test bulk creation with custom article numbers."""
    response = client.post("/api/v1/articles/bulk", headers=auth_headers, json={
        "category_id": test_category.id,
        "type_id": test_type.id,
        "size": "L",
        "artikelnummern": ["CUSTOM-001", "CUSTOM-002"],
    })
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    nums = [a["artikelnummer"] for a in data]
    assert "CUSTOM-001" in nums
    assert "CUSTOM-002" in nums


def test_article_filters(client, auth_headers, test_category, test_type, test_organization):
    """Test article filtering."""
    # Create articles with different properties
    client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id, "type_id": test_type.id, "size": "M", "organization_id": test_organization.id
    })
    client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id, "type_id": test_type.id, "size": "L", "organization_id": test_organization.id
    })
    
    # Filter by size
    response = client.get("/api/v1/articles", headers=auth_headers, params={"size": "M"})
    assert response.status_code == 200
    data = response.json()
    assert all(a["size"] == "M" for a in data["items"])
    
    # Filter by status
    response = client.get("/api/v1/articles", headers=auth_headers, params={"status": ["verfuegbar"]})
    assert response.status_code == 200
    data = response.json()
    assert all(a["status"] == "verfuegbar" for a in data["items"])


def test_article_search(client, auth_headers, test_category, test_type):
    """Test article search by query."""
    client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id, "type_id": test_type.id, "remarks": "SPECIAL_ITEM"
    })
    
    response = client.get("/api/v1/articles", headers=auth_headers, params={"q": "SPECIAL_ITEM"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1
    assert any("SPECIAL_ITEM" in a.get("remarks", "") for a in data["items"])