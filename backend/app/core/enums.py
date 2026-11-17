from enum import Enum, StrEnum


class RiskType(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    MODERATE = "MODERATE"
    AGGRESSIVE = "AGGRESSIVE"


class AiUsageEndpoint(StrEnum):
    SELL_DIAGNOSIS = "SELL_DIAGNOSIS"
    DAILY_RECOMMENDATION = "DAILY_RECOMMENDATION"
