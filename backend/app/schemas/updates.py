from pydantic import BaseModel


class UpdateInstallRequest(BaseModel):
    ref: str