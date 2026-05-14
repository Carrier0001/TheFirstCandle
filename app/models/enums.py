from enum import Enum

class SubmissionStatus(str, Enum):
    PENDING_JURY = "PENDING_JURY"
    ASSIGNED_JURY = "ASSIGNED_JURY"
    JURY_COMPLETE = "JURY_COMPLETE"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class EntryStatus(str, Enum):
    APPROVED = "APPROVED"
    DISPUTED = "DISPUTED"
    REFUTED = "REFUTED"
    REPAIRED = "REPAIRED"
    MITIGATED = "MITIGATED"

class HarmType(str, Enum):
    NEGLIGENCE = "NEGLIGENCE"
    RECKLESSNESS = "RECKLESSNESS"
    DELIBERATE = "DELIBERATE"
    SYSTEMIC = "SYSTEMIC"
    COVER_UP = "COVER_UP"

class Confidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CERTAINTY = "CERTAINTY"

class JuryVote(str, Enum):
    APPROVE = "APPROVE"
    REFUTE = "REFUTE"
    ABSTAIN = "ABSTAIN"