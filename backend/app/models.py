from sqlalchemy import Column, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):  # type: ignore
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    api_key = Column(String, unique=True, index=True)
    tweets = relationship("Tweet", back_populates="owner")
    like = relationship("Like", back_populates="user")


class Tweet(Base):  # type: ignore
    __tablename__ = "tweets"

    id = Column(Integer, primary_key=True)
    content_text = Column(String)
    owner_id = Column(Integer, ForeignKey('users.id'))
    owner = relationship("User", back_populates="tweets")
    media = relationship("Media", back_populates="tweets")
    like = relationship(
        "Like", back_populates="tweets",
        cascade="all, delete-orphan"
    )


class Follower(Base):  # type: ignore
    __tablename__ = "followers"

    id = Column(Integer, primary_key=True)
    follower_id = Column(Integer, ForeignKey('users.id'))
    following_id = Column(Integer, ForeignKey('users.id'))


class Like(Base):  # type: ignore
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    tweet_id = Column(Integer, ForeignKey('tweets.id', ondelete="CASCADE"))
    user = relationship("User", back_populates="like")
    tweets = relationship("Tweet", back_populates="like")


class Media(Base):  # type: ignore
    __tablename__ = "medias"

    id = Column(Integer, primary_key=True)
    data = Column(LargeBinary, nullable=False)
    file_name = Column(String, nullable=False)
    tweet_id = Column(Integer, ForeignKey('tweets.id'), nullable=True)
    tweets = relationship("Tweet", back_populates="media")
