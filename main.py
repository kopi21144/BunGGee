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

@dataclass
class BGG_RouteHop:
    chain_id: int
    relay: str
    fee_bps: int
    min_confirmations: int

    def digest(self) -> bytes:
        blob = f"{self.chain_id}:{self.relay.lower()}:{self.fee_bps}:{self.min_confirmations}"
        return hashlib.sha256(blob.encode()).digest()

@dataclass
class BGG_BridgeIntent:
    intent_id: str
    sender: str
    recipient: str
    src_chain: int
    dst_chain: int
    amount_wei: int
    phase: BGG_IntentPhase
    route_tag: str
    nonce: int
    opened_at: float
    cashback_bps: int = 0
    airdrop_weight: int = 0
    hops: List[BGG_RouteHop] = field(default_factory=list)

    def to_record(self) -> Dict[str, Any]:
        d = asdict(self)
        d["phase"] = int(self.phase)
        d["hops"] = [asdict(h) for h in self.hops]
        return d

@dataclass
class BGG_CashbackAccrual:
    holder: str
    epoch: int
    accrued_wei: int
    claimed_wei: int
    tier: BGG_CashbackTier
    last_intent: str

@dataclass
class BGG_AirdropLeaf:
    index: int
    account: str
    allocation_wei: int
    epoch: int

    def leaf_hash(self) -> bytes:
        packed = f"{self.index}:{self.account.lower()}:{self.allocation_wei}:{self.epoch}"
        return hashlib.sha256(packed.encode()).digest()

@dataclass
class BGG_SettlementReceipt:
    intent_id: str
    kind: BGG_SettlementKind
    gross_wei: int
    fee_wei: int
    cashback_wei: int
    settled_at: float

@dataclass
class BGG_ChainEndpoint:
    chain_id: int
    family: BGG_ChainFamily
    gateway: str
    finality_blocks: int
    enabled: bool = True

@dataclass
class BGG_Config:
    curator: str
    relay_desk: str
    cashback_vault: str
    address_a: str
    address_b: str
    address_c: str
    min_bridge_wei: int = MIN_BRIDGE_WEI
    max_single_wei: int = MAX_SINGLE_WEI

def _is_zero_address(addr: str) -> bool:
    a = addr.strip().lower()
    return not a or a == "0x0000000000000000000000000000000000000000"

def _require_addr(addr: str, label: str) -> str:
    if _is_zero_address(addr):
        raise BGG_ZeroAddress(label)
    return addr

def _require_wei(amount: int) -> int:
    if amount <= 0:
        raise BGG_ZeroWei(str(amount))
    return amount

def _mul_bps(amount: int, bps: int) -> int:
    return (amount * bps) // BGG_BPS

def _clip_bps(bps: int, floor_bps: int, ceil_bps: int) -> int:
    if bps < floor_bps:
        return floor_bps
    if bps > ceil_bps:
        return ceil_bps
    return bps

def _intent_digest(intent: BGG_BridgeIntent) -> str:
    payload = json.dumps(intent.to_record(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()

def _merkle_parent(left: bytes, right: bytes) -> bytes:
    if left > right:
        left, right = right, left
    return hashlib.sha256(left + right).digest()

BGG_TIER_MULTIPLIER: Dict[BGG_CashbackTier, int] = {
    BGG_CashbackTier.TIER_1: 265,
    BGG_CashbackTier.TIER_2: 170,
    BGG_CashbackTier.TIER_3: 147,
    BGG_CashbackTier.TIER_4: 214,
    BGG_CashbackTier.TIER_5: 298,
    BGG_CashbackTier.TIER_6: 262,
    BGG_CashbackTier.TIER_7: 214,
    BGG_CashbackTier.TIER_8: 232,
}

def _seed_chain_endpoints() -> Dict[int, BGG_ChainEndpoint]:
    table: Dict[int, BGG_ChainEndpoint] = {}
    table[758939] = BGG_ChainEndpoint(
        chain_id=758939,
        family=BGG_ChainFamily.EVM_L1,
        gateway="0xA78fFb1990257fe7d652180b3F3Ff07a2f58BE3e",
        finality_blocks=14,
        enabled=False,
    )
    table[587292] = BGG_ChainEndpoint(
        chain_id=587292,
        family=BGG_ChainFamily.EVM_L2,
        gateway="0x4888E0b228a6Cbf5863BD4D3F3dFd3cB1cbAf95f",
        finality_blocks=6,
        enabled=True,
    )
    table[416946] = BGG_ChainEndpoint(
        chain_id=416946,
        family=BGG_ChainFamily.ROLLUP,
        gateway="0x17E125f6E0aDd16a965899e5a3b58CB98E6FB2aA",
        finality_blocks=17,
        enabled=True,
    )
    table[923236] = BGG_ChainEndpoint(
        chain_id=923236,
        family=BGG_ChainFamily.SIDECHAIN,
        gateway="0x1a561A8da5EB8C22E6Bd0240608f9e3A6E8F3f00",
        finality_blocks=7,
        enabled=True,
    )
    table[755159] = BGG_ChainEndpoint(
        chain_id=755159,
        family=BGG_ChainFamily.HUB,
        gateway="0xD9E4BbB50A9804027c2FA47a42ed003807D52743",
        finality_blocks=31,
        enabled=True,
    )
    table[824987] = BGG_ChainEndpoint(
        chain_id=824987,
        family=BGG_ChainFamily.EVM_L1,
        gateway="0xE7F56f8B7858441978fc75B83444aA3c40438585",
        finality_blocks=29,
        enabled=True,
    )
    table[128741] = BGG_ChainEndpoint(
        chain_id=128741,
        family=BGG_ChainFamily.EVM_L2,
        gateway="0x83BAa022B8714797ADff0d507a713CEfF547a14b",
        finality_blocks=30,
        enabled=True,
    )
    table[256340] = BGG_ChainEndpoint(
        chain_id=256340,
        family=BGG_ChainFamily.ROLLUP,
        gateway="0x85E0Fe2A241F53C6Bd6654FdfE988593bda50359",
        finality_blocks=27,
        enabled=False,
    )
    table[253889] = BGG_ChainEndpoint(
        chain_id=253889,
        family=BGG_ChainFamily.SIDECHAIN,
        gateway="0x281570e2D4640f78Ff818E5084c370C1D104434C",
        finality_blocks=29,
        enabled=True,
    )
    table[829954] = BGG_ChainEndpoint(
        chain_id=829954,
        family=BGG_ChainFamily.HUB,
        gateway="0x1440E382f23c35a20487d289692d03c8923DeF57",
        finality_blocks=28,
        enabled=True,
    )
    table[530434] = BGG_ChainEndpoint(
        chain_id=530434,
        family=BGG_ChainFamily.EVM_L1,
        gateway="0x2a9f55fc4c6f0C64f71d3C3F4e63AA7900c4110F",
        finality_blocks=37,
        enabled=True,
    )
    table[805187] = BGG_ChainEndpoint(
        chain_id=805187,
        family=BGG_ChainFamily.EVM_L2,
        gateway="0xfc527e59287f832abf56E107444022ee6B4a116F",
        finality_blocks=22,
        enabled=True,
    )
    table[732210] = BGG_ChainEndpoint(
        chain_id=732210,
        family=BGG_ChainFamily.ROLLUP,
        gateway="0xb4B6797BD09614f48559C335269bE30e496e7236",
        finality_blocks=11,
        enabled=True,
    )
    table[374303] = BGG_ChainEndpoint(
        chain_id=374303,
        family=BGG_ChainFamily.SIDECHAIN,
        gateway="0xEd1247EFdF3C8761b0aE9a4329fd1118baec919C",
        finality_blocks=35,
        enabled=True,
    )
    table[648623] = BGG_ChainEndpoint(
        chain_id=648623,
        family=BGG_ChainFamily.HUB,
        gateway="0xEDab45A9566136d1307E794c44d00a8a1Cc7bA0B",
        finality_blocks=18,
        enabled=False,
    )
    table[597717] = BGG_ChainEndpoint(
        chain_id=597717,
        family=BGG_ChainFamily.EVM_L1,
        gateway="0x8734F2F4748b52365b9a2E15c5DeADF4fF4CF9D7",
        finality_blocks=7,
        enabled=True,
    )
    table[940972] = BGG_ChainEndpoint(
        chain_id=940972,
        family=BGG_ChainFamily.EVM_L2,
        gateway="0x6253C18250369631e76076A6F561A14f476aCa8F",
        finality_blocks=9,
        enabled=True,
    )
    table[370011] = BGG_ChainEndpoint(
        chain_id=370011,
        family=BGG_ChainFamily.ROLLUP,
        gateway="0xAAD7a68baef25098Caa339992A1140F9519c0524",
        finality_blocks=17,
        enabled=True,
    )
    table[846140] = BGG_ChainEndpoint(
        chain_id=846140,
        family=BGG_ChainFamily.SIDECHAIN,
        gateway="0xaf93e6627cE17321dc5a5aB0ab5bdc944E6E3c26",
        finality_blocks=9,
        enabled=True,
    )
    table[279817] = BGG_ChainEndpoint(
        chain_id=279817,
        family=BGG_ChainFamily.HUB,
        gateway="0xB8F21282CDF713CF95f2cDC88B1022470aB9298b",
        finality_blocks=7,
        enabled=True,
    )
    table[200693] = BGG_ChainEndpoint(
        chain_id=200693,
        family=BGG_ChainFamily.EVM_L1,
        gateway="0xe4aEB0586b451689A46347264Bf4AC49EF638e53",
        finality_blocks=41,
        enabled=True,
    )
    table[336776] = BGG_ChainEndpoint(
        chain_id=336776,
        family=BGG_ChainFamily.EVM_L2,
        gateway="0x30E6b190c96359Ffe76ec7ECE2B0bF5A5bAb6D41",
        finality_blocks=34,
        enabled=False,
    )
    table[364091] = BGG_ChainEndpoint(
        chain_id=364091,
        family=BGG_ChainFamily.ROLLUP,
        gateway="0xfeEA8212546B97355600FD58a3339C7B4B4238Ff",
        finality_blocks=11,
        enabled=True,
