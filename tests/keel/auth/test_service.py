import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from theseus.keel.auth.models import CrewRole
from theseus.keel.auth.service import AuthService


@pytest.fixture
def auth_service(db_session: AsyncSession) -> AuthService:
    return AuthService(session=db_session)


class TestAuthService:
    @pytest.mark.asyncio
    async def test_create_crew_member(self, auth_service: AuthService) -> None:
        member = await auth_service.create_crew_member(username="captain", password="secure-password-123",
            display_name="Captain Hook", role=CrewRole.HELMSMAN)
        assert member.username == "captain"
        assert member.display_name == "Captain Hook"
        assert member.role == CrewRole.HELMSMAN
        assert member.password_hash != "secure-password-123"

    @pytest.mark.asyncio
    async def test_authenticate_valid_credentials(self, auth_service: AuthService) -> None:
        await auth_service.create_crew_member(username="bosun_maria", password="maria-pass-456",
            display_name="Maria", role=CrewRole.BOSUN)
        member = await auth_service.authenticate("bosun_maria", "maria-pass-456")
        assert member is not None
        assert member.username == "bosun_maria"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_password(self, auth_service: AuthService) -> None:
        await auth_service.create_crew_member(username="deckhand_tom", password="correct-password",
            display_name="Tom", role=CrewRole.DECKHAND)
        member = await auth_service.authenticate("deckhand_tom", "wrong-password")
        assert member is None

    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_user(self, auth_service: AuthService) -> None:
        member = await auth_service.authenticate("nobody", "password")
        assert member is None

    @pytest.mark.asyncio
    async def test_create_access_token(self, auth_service: AuthService) -> None:
        member = await auth_service.create_crew_member(username="helmsman", password="helm-pass",
            display_name="Helmsman", role=CrewRole.HELMSMAN)
        token = auth_service.create_access_token(member)
        assert isinstance(token, str) and len(token) > 0

    @pytest.mark.asyncio
    async def test_verify_access_token(self, auth_service: AuthService) -> None:
        member = await auth_service.create_crew_member(username="verified_user", password="pass",
            display_name="Verified", role=CrewRole.BOSUN)
        token = auth_service.create_access_token(member)
        payload = auth_service.verify_access_token(token)
        assert payload is not None
        assert payload["sub"] == str(member.id)
        assert payload["role"] == CrewRole.BOSUN.value

    @pytest.mark.asyncio
    async def test_assign_plank_scope(self, auth_service: AuthService) -> None:
        member = await auth_service.create_crew_member(username="scoped_user", password="pass",
            display_name="Scoped", role=CrewRole.BOSUN, plank_scopes=["inventory", "manufacturing"])
        assert member.plank_scopes == ["inventory", "manufacturing"]

    @pytest.mark.asyncio
    async def test_duplicate_username_raises(self, auth_service: AuthService) -> None:
        await auth_service.create_crew_member(username="unique_user", password="pass",
            display_name="First", role=CrewRole.DECKHAND)
        with pytest.raises(ValueError, match="already exists"):
            await auth_service.create_crew_member(username="unique_user", password="pass2",
                display_name="Second", role=CrewRole.DECKHAND)
