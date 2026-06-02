def test_health_publico(client):
    assert client.get("/health").status_code == 200


def test_ui_serve(client):
    assert client.get("/ui/").status_code == 200
