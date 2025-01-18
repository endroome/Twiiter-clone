import pytest
import pytest_asyncio
from app.app import app as fastapi_app
from app.database import get_async_session
from app.models import Base, Follower, Like, Media, Tweet, User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

DATABASE_TEST_URL = "postgresql+asyncpg://test:test@localhost:5432/test"

engine = create_async_engine(
    DATABASE_TEST_URL,
    echo=True
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession
)


@pytest_asyncio.fixture(scope="function")
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(setup_database):
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    fastapi_app.dependency_overrides[get_async_session] = override_get_db

    async with AsyncClient(base_url="http://0.0.0.0:8000 ") as client:
        yield client

    fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def create_test_user():
    async with TestingSessionLocal() as session:
        user = User(id=1, name="User1", api_key="test-api-key1")
        session.add(user)
        await session.commit()
        yield user


@pytest.mark.asyncio
async def test_create_post(client, create_test_user):
    headers = {"api-key": "test-api-key1"}

    payload = {"tweet_data": "Hello, world!", "tweet_media_ids": None}
    response = await client.post("/api/tweets", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json()["result"] is True
    assert "tweet_id" in response.json()


@pytest.mark.asyncio
async def test_create_media(client, create_test_user):
    headers = {"api-key": "test-api-key1"}
    files = {"file": ("image.png", b"image content", "image/png")}

    response = await client.post("/api/medias", files=files, headers=headers)

    assert response.status_code == 200
    assert response.json()["result"] is True
    assert "media_id" in response.json()


@pytest.mark.asyncio
async def test_get_media(client, create_test_user):
    async with TestingSessionLocal() as session:
        media = Media(id=1, data=b"image content", file_name="test.png")
        session.add(media)
        await session.commit()

    response = await client.get("/api/media/1")

    assert response.status_code == 200
    assert response.content == b"image content"
    assert response.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_delete_tweet(client, create_test_user):
    async with TestingSessionLocal() as session:
        tweet = Tweet(id=1, content_text="Hello, world!", owner_id=1)
        session.add(tweet)
        await session.commit()

    headers = {"api-key": "test-api-key1"}
    response = await client.delete("/api/tweets/1", headers=headers)

    assert response.status_code == 200
    assert response.json()["result"] is True


@pytest.mark.asyncio
async def test_like_tweet(client, create_test_user):
    async with TestingSessionLocal() as session:
        tweet = Tweet(id=1, content_text="Hello, world!", owner_id=1)
        session.add(tweet)
        await session.commit()

        headers = {"api-key": "test-api-key1"}
        response = await client.post("/api/tweets/1/likes", headers=headers)

        assert response.status_code == 200
        assert response.json()["result"] is True


async def test_create_follow(client, create_test_user):
    async with TestingSessionLocal() as session:
        user1_db = User(id=2, name="User2", api_key="test-api-key2")
        session.add(user1_db)
        await session.commit()
        await session.refresh(user1_db)

        response = await client.post(
            f"/api/users/{user1_db.id}/follow",
            headers={"api-key": user1_db.api_key}
        )

        assert response.status_code == 200
        assert response.json()["result"] is True


@pytest.mark.asyncio
async def test_read_tweets(client, create_test_user):
    headers = {"api-key": "test-api-key1"}

    response = await client.get("/api/tweets", headers=headers)
    assert response.status_code == 200
    assert response.json()["result"] is True
    assert "tweets" in response.json()


@pytest.mark.asyncio
async def test_read_user_by_id(client, create_test_user):
    headers = {"api-key": "test-api-key1"}

    response = await client.get("/api/users/1", headers=headers)
    assert response.status_code == 200
    assert response.json()["result"] is True
    assert "user" in response.json()


@pytest.mark.asyncio
async def test_delete_like(client, create_test_user):
    async with TestingSessionLocal() as session:
        tweet = Tweet(id=1, content_text="Hello, world!", owner_id=1)
        session.add(tweet)
        await session.commit()

        like_tweet = Like(user_id=1, tweet_id=1)
        session.add(like_tweet)
        await session.commit()

    headers = {"api-key": "test-api-key1"}
    response = await client.delete("/api/tweets/1/likes", headers=headers)

    assert response.status_code == 200
    assert response.json()["result"] is True

    async with TestingSessionLocal() as session:
        likes = await session.execute(
            select(Like).filter(Like.user_id == 1, Like.tweet_id == 1)
        )
        like = likes.scalar_one_or_none()
        assert like is None


@pytest.mark.asyncio
async def test_delete_follower(client, create_test_user):
    async with TestingSessionLocal() as session:
        user2 = User(id=2, name="User2", api_key="test-api-key2")
        session.add(user2)
        await session.commit()

        follow = Follower(follower_id=1, following_id=2)
        session.add(follow)
        await session.commit()

    headers = {"api-key": "test-api-key1"}
    response = await client.delete("/api/users/2/follow", headers=headers)

    assert response.status_code == 200
    assert response.json()["result"] is True

    async with TestingSessionLocal() as session:
        subscription = await session.execute(
            select(Follower).filter(
                Follower.follower_id == 1, Follower.following_id == 2
            )
        )
        subscription = subscription.scalars().first()
        assert subscription is None


@pytest.mark.asyncio
async def test_read_me(client, create_test_user):
    headers = {"api-key": "test-api-key1"}
    response = await client.get("/api/users/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["result"] is True
    assert "user" in response.json()
