import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from starlette import status

from .database import engine, get_async_session
from .models import Base, Follower, Like, Media, Tweet, User
from .schemas import TweetCreate

app = FastAPI()

api_key_header = APIKeyHeader(name="api-key", auto_error=False)


async def get_current_user(
        api_key: str = Depends(api_key_header),  # noqa: B008
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        result = await session.execute(
            select(User).filter(User.api_key == api_key)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API Key",
            )
        return user
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()


@app.post("/api/tweets")
async def create_tweet(
        tweet: TweetCreate,
        current_user: User = Depends(get_current_user),  # noqa: B008
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        db_tweet = Tweet(
            content_text=tweet.tweet_data,
            owner_id=current_user.id
        )
        session.add(db_tweet)
        await session.commit()
        await session.refresh(db_tweet)

        if tweet.tweet_media_ids is not None:
            for media_id in tweet.tweet_media_ids:
                media = await session.execute(
                    select(Media).filter(Media.id == media_id)
                )
                result_media = media.scalar_one_or_none()
                if result_media:
                    result_media.tweet_id = db_tweet.id
                    await session.commit()
                else:
                    await session.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Media not found"
                    )

        return {"result": True, "tweet_id": db_tweet.id}
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }


@app.post("/api/medias")
async def create_media(
        file: UploadFile = File(...),  # noqa: B008
        current_user: User = Depends(get_current_user),  # noqa: B008
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        if file.content_type not in ["image/jpeg", "image/png", "image/jpg"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only JPEG and PNG are allowed."
            )

        unique_filename = f"{uuid.uuid4()}{Path(file.filename).suffix}"

        media = Media(data=file.file.read(), file_name=unique_filename)
        session.add(media)
        await session.commit()
        await session.refresh(media)

        return {
            "result": True,
            "media_id": media.id,
        }
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }


@app.get("/api/media/{id}")
async def get_media_by_id(
        id: int,
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        media = await session.execute(
            select(Media).filter(Media.id == id)
        )
        result = media.scalar_one_or_none()
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media not found"
            )

        return Response(content=result.data, media_type="image/png")
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }


@app.delete("/api/tweets/{id}")
async def delete_by_id(
        id: int,
        current_user: User = Depends(get_current_user),  # noqa: B008
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        tweet = await session.execute(
            select(Tweet).filter(Tweet.id == id)
        )
        result = tweet.scalar_one_or_none()
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tweet not found"
            )

        if result.owner_id == current_user.id:
            await session.delete(result)
            await session.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to delete this tweet"
            )

        return {
            "result": True
        }
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }


@app.post("/api/tweets/{id}/likes")
async def likes_tweets(
        id: int,
        current_user: User = Depends(get_current_user),  # noqa: B008
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        tweet = await session.execute(
            select(Tweet).filter(Tweet.id == id)
        )
        result = tweet.scalar_one_or_none()
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tweet not found"
            )
        like_tweet = Like(user_id=current_user.id, tweet_id=id)
        session.add(like_tweet)
        await session.commit()

        return {
            "result": True
        }
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }


@app.delete("/api/tweets/{id}/likes")
async def delete_likes_by_id(
        id: int,
        current_user: User = Depends(get_current_user),  # noqa: B008
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        like_tweet = await session.execute(
            select(Like).filter(
                Like.user_id == current_user.id,
                Like.tweet_id == id
            )
        )
        like_tweet = like_tweet.scalars().first()

        if not like_tweet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Like not found"
            )

        await session.delete(like_tweet)
        await session.commit()

        return {
            "result": True
        }
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }


@app.post("/api/users/{id}/follow")
async def follow_user_by_id(
        id: int,
        current_user: User = Depends(get_current_user),  # noqa: B008
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        user = await session.execute(select(User).filter(User.id == id))
        result = user.scalar_one_or_none()
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        subscription = Follower(
            follower_id=current_user.id,
            following_id=id
        )
        session.add(subscription)
        await session.commit()

        return {
            "result": True
        }
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }


@app.delete("/api/users/{id}/follow")
async def delete_follow_by_id(
        id: int,
        current_user: User = Depends(get_current_user),  # noqa: B008
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        subscription = await session.execute(
            select(Follower).filter(
                Follower.follower_id == current_user.id,
                Follower.following_id == id
            )
        )
        subscription = subscription.scalars().first()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Follower not found"
            )

        await session.delete(subscription)
        await session.commit()

        return {
            "result": True
        }
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }


@app.get("/api/tweets")
async def read_tweets(
        current_user: User = Depends(get_current_user),  # noqa: B008
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        tweets = await session.execute(
            select(Tweet).options(selectinload(Tweet.owner))
        )
        tweet_list = []

        for tweet in tweets.scalars().all():
            print(tweet.id)
            media_files = await session.execute(
                select(Media).filter(Media.tweet_id == tweet.id)
            )
            attachments = [
                f"/api/media/{media.id}"
                for media in media_files.scalars().all()
            ]

            likes = await session.execute(
                select(Like).filter(Like.tweet_id == tweet.id).
                options(selectinload(Like.user))
            )
            like_list = [
                {"user_id": like.user_id,
                 "name": like.user.name}
                for like in likes.scalars().all()
            ]
            tweet_list.append(
                {
                    "id": tweet.id,
                    "content": tweet.content_text,
                    "attachments": attachments,
                    "author": {
                        "id": tweet.owner.id,
                        "name": tweet.owner.name
                    },
                    "likes": like_list
                }
            )

        return {
            "result": True,
            "tweets": tweet_list
        }
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }


@app.get("/api/users/me")
async def read_user(
        current_user: User = Depends(get_current_user),  # noqa: B008
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        user_query = await session.execute(
            select(User).filter(User.id == current_user.id)
        )
        user = user_query.scalar_one_or_none()

        follower_ids_query = await session.execute(
            select(Follower.follower_id).filter(
                Follower.following_id == current_user.id
            )
        )
        following_ids_query = await session.execute(
            select(Follower.following_id).filter(
                Follower.follower_id == current_user.id
            )
        )

        follower_ids = follower_ids_query.scalars().all()
        following_ids = following_ids_query.scalars().all()

        followers_query = await session.execute(
            select(User).filter(User.id.in_(follower_ids))
        )
        followings_query = await session.execute(
            select(User).filter(User.id.in_(following_ids))
        )

        followers_list = [
            {"id": f.id, "name": f.name}
            for f in followers_query.scalars().all()
        ]

        following_list = [
            {"id": f.id, "name": f.name}
            for f in followings_query.scalars().all()
        ]

        user_dict = {
            "id": user.id,
            "name": user.name,
            "followers": followers_list,
            "following": following_list
        }

        return {
            "result": True,
            "user": user_dict
        }
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }


@app.get("/api/users/{id}")
async def read_user_by_id(
        id: int,
        current_user: User = Depends(get_current_user),  # noqa: B008
        session: AsyncSession = Depends(get_async_session)  # noqa: B008
):
    try:
        user_query = await session.execute(
            select(User).filter(User.id == id)
        )
        user = user_query.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        follower_ids_query = await session.execute(
            select(Follower.follower_id).filter(
                Follower.following_id == id
            )
        )
        following_ids_query = await session.execute(
            select(Follower.following_id).filter(
                Follower.follower_id == id
            )
        )

        follower_ids = follower_ids_query.scalars().all()
        following_ids = following_ids_query.scalars().all()

        followers_query = await session.execute(
            select(User).filter(User.id.in_(follower_ids))
        )
        followings_query = await session.execute(
            select(User).filter(User.id.in_(following_ids))
        )

        followers_list = [
            {"id": f.id, "name": f.name}
            for f in followers_query.scalars().all()
        ]

        following_list = [
            {"id": f.id, "name": f.name}
            for f in followings_query.scalars().all()
        ]

        user_dict = {
            "id": user.id,
            "name": user.name,
            "followers": followers_list,
            "following": following_list
        }

        return {
            "result": True,
            "user": user_dict
        }
    except Exception as e:  # noqa: PIE786
        return {
            "result": False,
            "error_type": "server_error",
            "error_message": str(e)
        }
