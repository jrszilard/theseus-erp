import pytest
from httpx import AsyncClient


class TestEntityCRUD:
    @pytest.mark.asyncio
    async def test_create_entity(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/entities/test/Widget",
            json={"name": "Red Widget", "color": "red", "weight": 1.5})
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Red Widget"
        assert data["color"] == "red"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_get_entity(self, client: AsyncClient) -> None:
        create_resp = await client.post("/api/v1/entities/test/Widget",
            json={"name": "Blue Widget", "color": "blue"})
        entity_id = create_resp.json()["id"]
        get_resp = await client.get(f"/api/v1/entities/test/Widget/{entity_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Blue Widget"

    @pytest.mark.asyncio
    async def test_list_entities(self, client: AsyncClient) -> None:
        await client.post("/api/v1/entities/test/Widget", json={"name": "Widget A", "color": "red"})
        await client.post("/api/v1/entities/test/Widget", json={"name": "Widget B", "color": "green"})
        response = await client.get("/api/v1/entities/test/Widget")
        assert response.status_code == 200
        assert len(response.json()) >= 2

    @pytest.mark.asyncio
    async def test_update_entity(self, client: AsyncClient) -> None:
        create_resp = await client.post("/api/v1/entities/test/Widget",
            json={"name": "Old Name", "color": "red"})
        entity_id = create_resp.json()["id"]
        update_resp = await client.patch(f"/api/v1/entities/test/Widget/{entity_id}",
            json={"name": "New Name"})
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_nonexistent_entity_returns_404(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/entities/test/Widget/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_nonexistent_blueprint_returns_404(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/entities/fake/Nothing")
        assert response.status_code == 404
