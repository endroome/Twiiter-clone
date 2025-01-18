from typing import List, Optional

from pydantic import BaseModel


class TweetCreate(BaseModel):
    tweet_data: str
    tweet_media_ids: Optional[List[int]] = None
