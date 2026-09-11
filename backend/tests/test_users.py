def test_list_users(client, auth_headers):
    """Test listing users."""
    response = client.get("/api/v1/users", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1  # admin user


def test_create_user(client, auth_headers):
    """Test creating a user."""
    response = client.post("/api/v1/users", headers=auth_headers, json={
        "username": "newuser",
        "full_name": "New User",
        "roles": ["helfer"],
        "password": "password123",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert data["full_name"] == "New User"
    assert "helfer" in data["roles"]
    assert data["has_password"] is True


def test_create_user_with_pin(client, auth_headers):
    """Test creating a user with PIN."""
    response = client.post("/api/v1/users", headers=auth_headers, json={
        "username": "pinuser",
        "full_name": "PIN User",
        "roles": ["helfer"],
        "pin": "1234",
        "pin_length": 4,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "pinuser"
    assert data["has_pin"] is True
    assert data["pin_length"] == 4


def test_update_user(client, auth_headers):
    """Test updating a user."""
    # Create user first
    create_resp = client.post("/api/v1/users", headers=auth_headers, json={
        "username": "updateuser", "full_name": "Update User", "roles": ["helfer"]
    })
    user_id = create_resp.json()["id"]
    
    response = client.put(f"/api/v1/users/{user_id}", headers=auth_headers, json={
        "full_name": "Updated Name",
        "roles": ["verwalter"],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Name"
    assert "verwalter" in data["roles"]


def test_deactivate_user(client, auth_headers):
    """Test deactivating a user."""
    create_resp = client.post("/api/v1/users", headers=auth_headers, json={
        "username": "todeactivate", "full_name": "To Deactivate", "roles": ["helfer"]
    })
    user_id = create_resp.json()["id"]
    
    response = client.put(f"/api/v1/users/{user_id}", headers=auth_headers, json={
        "active": False,
    })
    assert response.status_code == 200
    assert response.json()["active"] is False


def test_list_persons(client, auth_headers):
    """Test listing persons."""
    response = client.get("/api/v1/persons", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_create_person(client, auth_headers, test_organization):
    """Test creating a person."""
    response = client.post("/api/v1/persons", headers=auth_headers, json={
        "first_name": "Max",
        "last_name": "Mustermann",
        "organization_id": test_organization.id,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Max"
    assert data["last_name"] == "Mustermann"
    assert data["organization_id"] == test_organization.id


def test_update_person(client, auth_headers, test_organization):
    """Test updating a person."""
    create_resp = client.post("/api/v1/persons", headers=auth_headers, json={
        "first_name": "Original", "last_name": "Name", "organization_id": test_organization.id
    })
    person_id = create_resp.json()["id"]
    
    response = client.put(f"/api/v1/persons/{person_id}", headers=auth_headers, json={
        "first_name": "Geändert",
        "notes": "Test note",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Geändert"
    assert data["notes"] == "Test note"


def test_person_sizes(client, auth_headers):
    """Test person size fields."""
    create_resp = client.post("/api/v1/persons", headers=auth_headers, json={
        "first_name": "Size", "last_name": "Test"
    })
    person_id = create_resp.json()["id"]
    
    response = client.put(f"/api/v1/persons/{person_id}", headers=auth_headers, json={
        "sizes": {"top": "L", "bottom": "32", "shoes": "42"}
    })
    assert response.status_code == 200
    data = response.json()
    assert data["sizes"]["top"] == "L"
    assert data["sizes"]["bottom"] == "32"
    assert data["sizes"]["shoes"] == "42"