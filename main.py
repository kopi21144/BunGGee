# BunGGee — elastic hop bridge with retroactive airdrop cashback lanes.
# Codename: tungsten voucher / slack tide relay nine.

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

BGG_SCALE = 10**18
BGG_BPS = 10000
BGG_VERSION = (1, 10, 49)

ADDRESS_A = "0x439528554Efb34E42642d9c9C8A551911CEa186a"
ADDRESS_B = "0x0323f28815B40839EF4654de5F84aD6086d27e7F"
ADDRESS_C = "0x6F19b7A644dd20dBCE7Ec44a6a3b02150178505E"
CURATOR_SEAT = "0x1A4B6715Db15AD98688b7554e18486F161f88032"
RELAY_DESK = "0xd2de8493e4bF7330fcE63BEf37cd8903e43F4E7a"
CASHBACK_VAULT = "0xFAE00c7a0119EaFb71F1E5aE4A3329300577B5b3"

DOMAIN_ROOT = "0x62bdb18af0493fdd940a87b712a10954ffb66f230ca59d84145357c09d1db955"
BRIDGE_SALT = "0x65c24678736fb27978f9a9f0e32396d86190f866b2d2349b03658afaccf7b8d8"
AIRDROP_MERKLE = "0x83690265f13a8a269f35662961f5fc051fa90c9c82f659ed149e33b1f8fb4eb5"
SETTLEMENT_DIGEST = "0xa93fb1cee27cc2c55dd5f8f5845a57bcc9f78eaeadd1ec87028eea7b501157ea"
ROUTE_LUT = "0x2a399f6028102785ed59787e6ad0f1f192f44e898bbfc91a1d273288b6afa415"
GUARD_NONCE = "0x574b702def746970168729ce0703ff7abd371b3e8ab4929ea4070b1a1aa4588a"

MIN_BRIDGE_WEI = 3000000000000000
MAX_SINGLE_WEI = 712000000000000000000
CASHBACK_FLOOR_BPS = 40
CASHBACK_CEIL_BPS = 820
AIRDROP_CLIP_BPS = 132
FEE_CLIP_BPS = 91
EPOCH_SECONDS = 108000
MAX_PENDING_INTENTS = 97
REPLAY_WINDOW_BLOCKS = 754
MAX_ROUTE_HOPS = 4
BGG_TIER_COUNT = 8
MAX_CASHBACK_CLAIMS = 50

class BGG_IntentPhase(IntEnum):
    DRAFT = 0
    QUOTED = 1
    LOCKED = 2
    RELAYED = 3
    SETTLED = 4
    REFUNDED = 5
    VOID = 6

class BGG_CashbackTier(IntEnum):
    TIER_1 = 0
    TIER_2 = 1
    TIER_3 = 2
    TIER_4 = 3
    TIER_5 = 4
    TIER_6 = 5
    TIER_7 = 6
    TIER_8 = 7

class BGG_ChainFamily(IntEnum):
    EVM_L1 = 0
    EVM_L2 = 1
    ROLLUP = 2
    SIDECHAIN = 3
    HUB = 4

class BGG_SettlementKind(IntEnum):
    STANDARD = 0
    EXPRESS = 1
    BATCH = 2
    AIRDROP_TOPUP = 3

class BGG_ZeroAddress(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "address required"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_ZeroWei(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "amount must be positive"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_NotCurator(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "caller is not curator"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_IntentFrozen(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "intent lane paused"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_CapExceeded(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "bridge cap exceeded"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_Replay(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "nonce already consumed"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_InvalidRoute(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "route profile unknown"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_PendingOverflow(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "pending queue full"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_CashbackFloor(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "cashback below floor"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_AirdropClip(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "airdrop clip exceeded"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_MerkleReject(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "merkle proof invalid"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_EpochClosed(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "epoch not accepting claims"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_SelfBridge(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "source and dest must differ"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))

class BGG_HopLimit(Exception):
    def __init__(self, detail: str = "") -> None:
        base = "hop count exceeds max"
        super().__init__(f"BGG: {base}" + (f" ({detail})" if detail else ""))
