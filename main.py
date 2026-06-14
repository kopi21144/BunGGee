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
    )
    return table

def _seed_route_profiles() -> Dict[str, Tuple[int, List[BGG_RouteHop]]]:
    profiles: Dict[str, Tuple[int, List[BGG_RouteHop]]] = {}
    hops_0: List[BGG_RouteHop] = []
    hops_0.append(BGG_RouteHop(chain_id=242249, relay="0x54Ad53a75282527698Bf3bA97704E774B8Da6549", fee_bps=18, min_confirmations=18))
    hops_0.append(BGG_RouteHop(chain_id=938202, relay="0xDd03B7B1fb433ae1df0d81f966a5e9909dfCdc34", fee_bps=22, min_confirmations=10))
    hops_0.append(BGG_RouteHop(chain_id=965541, relay="0xBEdCD7b8A87F623Cb191036D799d102Dc2a211d7", fee_bps=59, min_confirmations=17))
    hops_0.append(BGG_RouteHop(chain_id=282992, relay="0x9CE26b90364EEF80aC480D9F2Cc7EF6ed976D7bD", fee_bps=34, min_confirmations=4))
    profiles["lane_886594"] = (116, hops_0)
    hops_1: List[BGG_RouteHop] = []
    hops_1.append(BGG_RouteHop(chain_id=786782, relay="0x75C1e6BaaBa012c6324b63b72543D877215f3e8a", fee_bps=27, min_confirmations=21))
    hops_1.append(BGG_RouteHop(chain_id=813483, relay="0x39E3E83530d70a0589D58e1f9e3A13eA2713a3c2", fee_bps=12, min_confirmations=7))
    hops_1.append(BGG_RouteHop(chain_id=191766, relay="0x5eE27371eFC8063b66AD99dEdAE19681eEba52eb", fee_bps=104, min_confirmations=10))
    hops_1.append(BGG_RouteHop(chain_id=769105, relay="0x7D98ab61728c0bd1A26765B9aad119FEdb09868e", fee_bps=24, min_confirmations=3))
    profiles["lane_c7dc46"] = (352, hops_1)
    hops_2: List[BGG_RouteHop] = []
    hops_2.append(BGG_RouteHop(chain_id=330256, relay="0xd9e13ce73B2c5e762bA893C785e4C8590A9A6C45", fee_bps=18, min_confirmations=13))
    hops_2.append(BGG_RouteHop(chain_id=527398, relay="0x8CCC65F2BfaA2a01406FB2519c64b51f49a0a3ec", fee_bps=96, min_confirmations=12))
    profiles["lane_870276"] = (542, hops_2)
    hops_3: List[BGG_RouteHop] = []
    hops_3.append(BGG_RouteHop(chain_id=692851, relay="0x2D1a0F4f36f23076b46f9D7E502531FA9828E3F7", fee_bps=79, min_confirmations=22))
    hops_3.append(BGG_RouteHop(chain_id=511396, relay="0x65323721d50B703c31FBB1b79b2E9d1fB0B0dc3D", fee_bps=122, min_confirmations=3))
    hops_3.append(BGG_RouteHop(chain_id=704884, relay="0x6EA024e63169b50D32C94Fa778d3E2759e6A3743", fee_bps=44, min_confirmations=7))
    hops_3.append(BGG_RouteHop(chain_id=606061, relay="0x23d8F682f0B0885ad118bb914513c0D9b6c7Aa4A", fee_bps=53, min_confirmations=13))
    profiles["lane_769b22"] = (171, hops_3)
    hops_4: List[BGG_RouteHop] = []
    hops_4.append(BGG_RouteHop(chain_id=546416, relay="0x05d1bF65CA33843F330B40CD07DA8260f58cD4bF", fee_bps=90, min_confirmations=13))
    hops_4.append(BGG_RouteHop(chain_id=384769, relay="0x641B432D34264Da5221755b69C50D10F24a5c2Dc", fee_bps=82, min_confirmations=11))
    hops_4.append(BGG_RouteHop(chain_id=234552, relay="0xb400B0Fc4651F0C1A45b4305c8bcD330d3ace075", fee_bps=90, min_confirmations=6))
    profiles["lane_6997a7"] = (260, hops_4)
    hops_5: List[BGG_RouteHop] = []
    hops_5.append(BGG_RouteHop(chain_id=352404, relay="0xe40Ea9543474c17E0CEaC1fAB9A77c4575332657", fee_bps=72, min_confirmations=13))
    hops_5.append(BGG_RouteHop(chain_id=901088, relay="0x27Ae7F2f070CbeB1c385A08e4D1f9390C6d1cE14", fee_bps=67, min_confirmations=4))
    profiles["lane_aceb12"] = (606, hops_5)
    hops_6: List[BGG_RouteHop] = []
    hops_6.append(BGG_RouteHop(chain_id=690885, relay="0xF2FBdB3dDd7C7219188a6A4270E2c4E186Ce4c51", fee_bps=51, min_confirmations=17))
    hops_6.append(BGG_RouteHop(chain_id=984533, relay="0xD178eAF78a03891e0804a7e4326e36D9c2fBd571", fee_bps=87, min_confirmations=22))
    hops_6.append(BGG_RouteHop(chain_id=751211, relay="0x2C7b1EE7A7aA7C50Ca0DD790Ab58BA7f50495F15", fee_bps=42, min_confirmations=12))
    profiles["lane_b9193f"] = (753, hops_6)
    hops_7: List[BGG_RouteHop] = []
    hops_7.append(BGG_RouteHop(chain_id=247106, relay="0x048682314DDE4a6170afa8ec2adCA3Ef45E00be1", fee_bps=20, min_confirmations=12))
    hops_7.append(BGG_RouteHop(chain_id=621654, relay="0xAFa47397A87571eebB437A51e568f9570A987Ce6", fee_bps=33, min_confirmations=16))
    hops_7.append(BGG_RouteHop(chain_id=612438, relay="0x964d2b5B69DaAffC4dAa1eAAd78E80d4D9Ef4696", fee_bps=96, min_confirmations=10))
    hops_7.append(BGG_RouteHop(chain_id=886515, relay="0x91b4a9b821ba09B35b4e6A10F4737d16DBC114f2", fee_bps=104, min_confirmations=5))
    profiles["lane_85c56b"] = (67, hops_7)
    hops_8: List[BGG_RouteHop] = []
    hops_8.append(BGG_RouteHop(chain_id=442586, relay="0x922362348eb41D4Fdc2401a31E38380cbECf029c", fee_bps=104, min_confirmations=15))
    hops_8.append(BGG_RouteHop(chain_id=299221, relay="0x6f3551a2FCCB805B65283475112FC0A8B6899d54", fee_bps=30, min_confirmations=10))
    profiles["lane_de52cd"] = (380, hops_8)
    hops_9: List[BGG_RouteHop] = []
    hops_9.append(BGG_RouteHop(chain_id=999697, relay="0xbFfFC2B003Ff8bbF4737377A1a0C8761ecc10A26", fee_bps=34, min_confirmations=11))
    hops_9.append(BGG_RouteHop(chain_id=408314, relay="0xeA982D16529Fe610541415D5B6f16eBe7F80766a", fee_bps=17, min_confirmations=11))
    hops_9.append(BGG_RouteHop(chain_id=412756, relay="0x84d74221aa22Da63BAA1d172992711c061873f41", fee_bps=122, min_confirmations=15))
    hops_9.append(BGG_RouteHop(chain_id=407256, relay="0x286C48a0529c640619E5AAE366E2d0786276e885", fee_bps=47, min_confirmations=15))
    profiles["lane_ef5ca5"] = (151, hops_9)
    hops_10: List[BGG_RouteHop] = []
    hops_10.append(BGG_RouteHop(chain_id=697647, relay="0x47A123A8FA720e8e4596B9ec1aB8f08efe999628", fee_bps=99, min_confirmations=5))
    hops_10.append(BGG_RouteHop(chain_id=690463, relay="0x1352943BE98EE3404A003368a56cEDB0fc753Ee2", fee_bps=12, min_confirmations=6))
    hops_10.append(BGG_RouteHop(chain_id=124157, relay="0xB6ad1FB3650D62b7719c38e3AC73f0D2ce9761Ff", fee_bps=66, min_confirmations=7))
    profiles["lane_ff8490"] = (415, hops_10)
    hops_11: List[BGG_RouteHop] = []
    hops_11.append(BGG_RouteHop(chain_id=700464, relay="0x0b32AB9d45E4fcFBB084dC74320d564423c0f9B7", fee_bps=86, min_confirmations=15))
    hops_11.append(BGG_RouteHop(chain_id=491848, relay="0x8b2cFE6f5e6714680D21A9f189b88B5A1f848361", fee_bps=102, min_confirmations=16))
    hops_11.append(BGG_RouteHop(chain_id=223871, relay="0x54D1f4608c6BfD9952D2BAe2Cca4661C8BaBCA4d", fee_bps=112, min_confirmations=11))
    profiles["lane_c6701b"] = (723, hops_11)
    hops_12: List[BGG_RouteHop] = []
    hops_12.append(BGG_RouteHop(chain_id=204284, relay="0x2710f69363Fc3E8C339be9Ce7f3d7BF29ef648EC", fee_bps=94, min_confirmations=5))
    hops_12.append(BGG_RouteHop(chain_id=179035, relay="0x7d5F1a68Ac954B88F0CBa5d0CAc53f56510628c7", fee_bps=75, min_confirmations=9))
    profiles["lane_1253cc"] = (334, hops_12)
    hops_13: List[BGG_RouteHop] = []
    hops_13.append(BGG_RouteHop(chain_id=931702, relay="0xDa94833cBA06341B2C38ad13C8A6094cEC10B1c4", fee_bps=96, min_confirmations=22))
    hops_13.append(BGG_RouteHop(chain_id=425440, relay="0xF7871beD8A01d47929FABaF83Fa401505cD7878C", fee_bps=112, min_confirmations=3))
    hops_13.append(BGG_RouteHop(chain_id=552210, relay="0xFCA15AE9c49818FEeF5308DBB64C13bF96D62f0e", fee_bps=65, min_confirmations=5))
    hops_13.append(BGG_RouteHop(chain_id=334910, relay="0x8dd57D4C5206E60E81cbc766745519eB0dCbCD87", fee_bps=109, min_confirmations=14))
    profiles["lane_7b05ce"] = (652, hops_13)
    hops_14: List[BGG_RouteHop] = []
    hops_14.append(BGG_RouteHop(chain_id=222230, relay="0xe2Dc172A4F47323332ac4E55486131Bb21f58c7a", fee_bps=74, min_confirmations=19))
    hops_14.append(BGG_RouteHop(chain_id=342404, relay="0x7B78e41279cd280390Ac93B752e3be3031b7c93A", fee_bps=122, min_confirmations=12))
    hops_14.append(BGG_RouteHop(chain_id=256057, relay="0x053b2dbB06924B7c50E635C4743e24e9f956BA0F", fee_bps=108, min_confirmations=7))
    hops_14.append(BGG_RouteHop(chain_id=252415, relay="0x91fbc40826E5EE8F4B84861213bA9C5869A68ecf", fee_bps=57, min_confirmations=4))
    profiles["lane_70d228"] = (211, hops_14)
    hops_15: List[BGG_RouteHop] = []
    hops_15.append(BGG_RouteHop(chain_id=222847, relay="0xDfAEc7FC17c213eC2764582574ADA0e098D76D0e", fee_bps=87, min_confirmations=17))
    hops_15.append(BGG_RouteHop(chain_id=907847, relay="0x557Af179b6988d4c9D7f65E57833BAba9B9C2Ab4", fee_bps=65, min_confirmations=11))
    profiles["lane_7f835a"] = (679, hops_15)
    hops_16: List[BGG_RouteHop] = []
    hops_16.append(BGG_RouteHop(chain_id=811915, relay="0xa9f4b7eB377792CC2767AF7Fd60E181199777aC4", fee_bps=75, min_confirmations=16))
    hops_16.append(BGG_RouteHop(chain_id=737397, relay="0x7f2dbBa759c510426b6F678E3458651Cce11B7c1", fee_bps=10, min_confirmations=3))
    hops_16.append(BGG_RouteHop(chain_id=289199, relay="0x5377C42af80eE2148AEba683EABdBA4753a4e45d", fee_bps=59, min_confirmations=4))
    hops_16.append(BGG_RouteHop(chain_id=280245, relay="0x000D27ceC3a861E17a380973763D437E313a7AfC", fee_bps=53, min_confirmations=17))
    profiles["lane_cf1cfc"] = (347, hops_16)
    hops_17: List[BGG_RouteHop] = []
    hops_17.append(BGG_RouteHop(chain_id=129059, relay="0x07825976a0a042AEED074153adD3DD0651CA58E5", fee_bps=125, min_confirmations=6))
    hops_17.append(BGG_RouteHop(chain_id=949207, relay="0x4c6572028dc958847B9d4dAf564E76eabB61e699", fee_bps=92, min_confirmations=12))
    hops_17.append(BGG_RouteHop(chain_id=467537, relay="0xE1E3127BfE5ce093259755DD1FE93bB511e86793", fee_bps=14, min_confirmations=7))
    hops_17.append(BGG_RouteHop(chain_id=758616, relay="0x8b5e77259303438fc4b786f9237bac8ad212e36C", fee_bps=19, min_confirmations=5))
    profiles["lane_ed7ecc"] = (358, hops_17)
    return profiles

BGG_REPLAY_GUARDS: Tuple[str, ...] = (
    "0xd9146a188e30347de4f00735857170a2e2ffcd15c2a618132fe9e64c2ff3b1bc",
    "0xea3a9383a037c9a110a30e2b288f6f6946da2d5af17b9a9a7bd2d7e892d8ae05",
    "0x3af23b931cd13b0b4605e0b85bd95705e3d7cdd7c76b6a0752236bef0d4da9d3",
    "0x12ca67de8ee5be54d4697c8d11ecf7fb5f32ef0e5e0ed31180eccb813e2cfd7b",
    "0xb9d5ed69ca3dc253c6acf04dd612baabdfcdd21b929ae896bea1ffef9b8070a4",
    "0x1c9474377f3927c10f527c423ca6cd1cc2693533cd8a0db3fcac4a8ed213fb45",
    "0x3c395862cd18d1235a50e5e05700e872bb3bfb5d936cf9b100fc37a365d9dade",
    "0x6e383fb7a011981ae95be3e359909a47e143d59dbfa9e9ccf3282c1b037485aa",
    "0x3b0b2a759fda4c6c4e69ad4911ec52ca209c22798a9139e97fec77a4870489f8",
    "0x583fa10c183cff622322999909e7f53527a1130aa1a2e81278544d93f0a46d80",
    "0x556937ce51ed8e0b68dd3ca1f3bad92ce2a9c0038c8161120533a07fd9f80c52",
    "0x57eb7f667c44bed3546c22a2c256e27208894593f5fd8dbeb417c946ff26a1bd",
    "0xc40897e1167cc32e7934250906cac5136e40f4ec2a2bd1b9eafe52d04f894066",
    "0x1443883d1d51f1cb06e30a4f2449556b38248ce1d5137993e141913ed6347703",
    "0x42caf745197c95649a2b7f977e2a1c9dc37deddf7eb763dae50dcb50e562a904",
    "0x9f48ad8c5190f2f2e9cae644db583fb62191b77fb55d0186e101c80d38c0bbb1",
    "0x5291421d032e21549be89be38645f49a1ae36a2e645a29af27e62630c1f3fb1c",
    "0xd260cd2c0952e1823c117dfde858e207716a23cbc81a6e20e253f8ffe1856497",
    "0x58c330e547de65f69fbf24464ff396fafbad8b16ca9767e7a50233c4bd31ede9",
    "0x4f12f808c4f9c44d2efaecd6b76e3ddbd1f99b4f44cd0b1d13b238a0256e032a",
    "0xf488d3f27fa2ce4d23f33b1a2694f455933eec1659cfa41ab93879338adf91d1",
    "0x4b271b711680da7444b2550ecfc14090407a41e6f4df9e52cf2b354d8f482825",
    "0xf4af59e15c4002c5455cd23a2ae93b8c3dc0e1115d68ae7767ea9dfd80e432ca",
)

BGG_BATCH_SLOTS: Dict[int, Tuple[int, int, str]] = {
    0: (239, 749, "batch_c304"),
    1: (123, 522, "batch_0245"),
    2: (215, 1078, "batch_1d1e"),
    3: (414, 1205, "batch_5356"),
    4: (220, 809, "batch_8747"),
    5: (450, 1126, "batch_b18e"),
    6: (501, 855, "batch_c8d0"),
    7: (366, 969, "batch_8ec7"),
    8: (104, 942, "batch_df2c"),
    9: (484, 1184, "batch_89be"),
    10: (224, 642, "batch_695e"),
    11: (228, 1184, "batch_a041"),
    12: (335, 798, "batch_b20e"),
    13: (462, 1318, "batch_63c9"),
    14: (140, 572, "batch_668d"),
    15: (226, 1179, "batch_cba2"),
