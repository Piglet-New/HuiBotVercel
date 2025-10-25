from dataclasses import dataclass
from typing import Optional

@dataclass
class Group:
    id: int
    code: str
    name: str
    owner_tg_id: int
    cycle_total: int
    cycle_index: int
    stake_amount: float

@dataclass
class User:
    id: int
    tg_id: int
    tg_username: Optional[str]
    display_name: Optional[str]
