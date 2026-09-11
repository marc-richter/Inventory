def test_issue_article(client, auth_headers, test_category, test_type, test_organization):
    """Test issuing an article to a person."""
    # Create article
    art_resp = client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id, "type_id": test_type.id, "size": "M",
        "organization_id": test_organization.id,
    })
    article_id = art_resp.json()["id"]
    assert art_resp.json()["status"] == "verfuegbar"
    
    # Create person
    person_resp = client.post("/api/v1/persons", headers=auth_headers, json={
        "first_name": "Hans", "last_name": "Müller"
    })
    person_id = person_resp.json()["id"]
    
    # Issue article
    response = client.post("/api/v1/issues/issue", headers=auth_headers, json={
        "article_id": article_id,
        "person_id": person_id,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["article_id"] == article_id
    assert data["person_id"] == person_id
    assert data["return_date"] is None
    
    # Verify article status changed
    art_resp = client.get(f"/api/v1/articles/{article_id}", headers=auth_headers)
    assert art_resp.json()["status"] == "ausgegeben"


def test_return_article(client, auth_headers, test_category, test_type, test_organization):
    """Test returning an article."""
    # Create article
    art_resp = client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id, "type_id": test_type.id, "size": "L",
        "organization_id": test_organization.id,
    })
    article_id = art_resp.json()["id"]
    
    # Create person
    person_resp = client.post("/api/v1/persons", headers=auth_headers, json={
        "first_name": "Anna", "last_name": "Schmidt"
    })
    person_id = person_resp.json()["id"]
    
    # Issue article
    issue_resp = client.post("/api/v1/issues/issue", headers=auth_headers, json={
        "article_id": article_id, "person_id": person_id
    })
    issue_id = issue_resp.json()["id"]
    
    # Return article
    response = client.post(f"/api/v1/issues/{issue_id}/return", headers=auth_headers, json={
        "condition_at_return": "Gut",
        "notes": "Alles ok",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["return_date"] is not None
    assert data["condition_at_return"] == "Gut"
    
    # Verify article status changed back
    art_resp = client.get(f"/api/v1/articles/{article_id}", headers=auth_headers)
    assert art_resp.json()["status"] == "verfuegbar"


def test_batch_issue(client, auth_headers, test_category, test_type, test_organization):
    """Test batch issuing multiple articles."""
    # Create multiple articles
    article_ids = []
    for i in range(3):
        art_resp = client.post("/api/v1/articles", headers=auth_headers, json={
            "category_id": test_category.id, "type_id": test_type.id, "size": "M",
            "organization_id": test_organization.id,
        })
        article_ids.append(art_resp.json()["id"])
    
    # Create person
    person_resp = client.post("/api/v1/persons", headers=auth_headers, json={
        "first_name": "Batch", "last_name": "User"
    })
    person_id = person_resp.json()["id"]
    
    # Batch issue
    response = client.post("/api/v1/issues/batch", headers=auth_headers, json={
        "person_id": person_id,
        "items": [{"article_id": aid} for aid in article_ids],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["issued"] == 3
    
    # Verify all articles are now issued
    for aid in article_ids:
        art_resp = client.get(f"/api/v1/articles/{aid}", headers=auth_headers)
        assert art_resp.json()["status"] == "ausgegeben"


def test_list_issues(client, auth_headers):
    """Test listing issue records."""
    response = client.get("/api/v1/issues/open", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_open_issues(client, auth_headers):
    """Test getting open issues."""
    response = client.get("/api/v1/issues/open", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # All should be currently issued (no return_date)
    for issue in data:
        assert issue["return_date"] is None


def test_issue_with_freetext_recipient(client, auth_headers, test_category, test_type):
    """Test issuing to a freetext recipient (not in person DB)."""
    art_resp = client.post("/api/v1/articles", headers=auth_headers, json={
        "category_id": test_category.id, "type_id": test_type.id,
    })
    article_id = art_resp.json()["id"]
    
    response = client.post("/api/v1/issues/issue", headers=auth_headers, json={
        "article_id": article_id,
        "recipient_name_freetext": "Externer Gast",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["recipient_name_freetext"] == "Externer Gast"
    assert data["person_id"] is None