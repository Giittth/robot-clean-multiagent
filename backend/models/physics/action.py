from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class Velocity(BaseModel):
    linear: float = 0.0
    angular: float = 0.0
    class Config:
        arbitrary_types_allowed = True
        extra = "ignore"


class ControlCommand(BaseModel):
    """全局控制指令（启停、复位、召回、暂停）"""
    type: str                          # "reset", "pause", "resume", "shutdown", "return_to_charge"
    params: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True
        extra = "ignore"