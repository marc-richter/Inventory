from typing import Optional
from pydantic import BaseModel


class MergePersonsRequest(BaseModel):
    source_id: int
    target_id: int


class MergeUsersRequest(BaseModel):
    source_id: int
    target_id: int