def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_endpoint(client):
    """Test version endpoint."""
    response = client.get("/api/version")
    assert response.status_code == 200
    assert "version" in response.json()


def test_login_success(client, admin_user):
    """Test successful login with password."""
    response = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin1234"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_with_pin(client, admin_user):
    """Test successful login with PIN."""
    response = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "pin": "1234"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


def test_login_wrong_password(client, admin_user):
    """Test login with wrong password."""
    response = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "wrong"
    })
    assert response.status_code == 401


def test_login_wrong_pin(client, admin_user):
    """Test login with wrong PIN."""
    response = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "pin": "0000"
    })
    assert response.status_code == 401


def test_login_nonexistent_user(client):
    """Test login with nonexistent user."""
    response = client.post("/api/v1/auth/login", json={
        "username": "nonexistent",
        "password": "whatever"
    })
    assert response.status_code == 401


def test_get_current_user(client, auth_headers):
    """Test getting current user info."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert "admin" in data["roles"]


def test_change_password(client, auth_headers, admin_user):
    """Test changing password."""
    response = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
        "old_password": "admin1234",
        "new_password": "newpassword123"
    })
    assert response.status_code == 200
    
    # Verify new password works
    response = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "newpassword123"
    })
    assert response.status_code == 200


def test_change_pin(client, auth_headers):
    """Test changing PIN."""
    response = client.post("/api/v1/auth/change-pin", headers=auth_headers, json={
        "old_pin": "1234",
        "new_pin": "5678"
    })
    assert response.status_code == 200
    
    # Verify new PIN works
    response = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "pin": "5678"
    })
    assert response.status_code == 200


def test_register_info(client):
    """Test register info endpoint."""
    response = client.get("/api/v1/auth/register-info")
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "pin_length" in data