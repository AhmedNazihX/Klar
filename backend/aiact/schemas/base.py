"""The shared base for every contract model."""

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """An immutable model that rejects unknown fields, so the contract can't drift silently."""

    model_config = ConfigDict(frozen=True, extra="forbid")
