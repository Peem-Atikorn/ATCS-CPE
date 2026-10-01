"""Decide when a follow-up question needs an LLM rewrite and check that rewrite.

A rewrite is only used for routing and retrieval. It may not bring in a team or a
number that the user's question and the chat history do not already contain.
"""

import os
import re

from .decisions import _intent
from .teams import TeamDirectory


TEAM_FREE_INTENTS = {"standings_stats", "weekly_summary", "trivia_history", "general_football"}
SHORT_QUERY_CHARS = 15
FOLLOWUP_TH = re.compile(r"^แล้ว|เขา|นัดนั้น|ทีมนี้|ทีมนั้น|คนนั้น|นัดก่อน|นัดต่อไป|อีกทีม|ล่ะ\s*\??$")
FOLLOWUP_EN = re.compile(r"\b(?:he|she|they|it|that|those|what about|how about|and)\b", re.IGNORECASE)
QUESTION_TH = re.compile(r"ไหม|มั้ย|อะไร|ใคร|เท่าไหร่|ยังไง|อย่างไร|กี่|ที่ไหน|ไหน|เมื่อไหร่|บ้าง|ล่ะ|หรือเปล่า")
QUESTION_EN = re.compile(r"^(?:who|what|when|where|which|why|how|is|are|was|were|did|does|do|can|will)\b",
                         re.IGNORECASE)
CITATION = re.compile(r"\[\d+\]")
NUMBER = re.compile(r"\d+")
# Time scopes change which season or day the answer is about, so a rewrite may not add one.
TIME_MARKERS_TH = ("ฤดูกาลที่แล้ว", "ซีซั่นที่แล้ว", "ปีที่แล้ว", "ฤดูกาลก่อน", "ซีซั่นก่อน", "ตลอดกาล",
                   "ประวัติศาสตร์", "ย้อนหลัง", "เมื่อวาน", "วันนี้", "พรุ่งนี้", "สัปดาห์นี้",
                   "สัปดาห์ที่แล้ว", "นัดล่าสุด", "นัดก่อน", "นัดต่อไป")
TIME_MARKERS_EN = re.compile(r"\b(?:last season|previous season|all[- ]time|ever|in history|yesterday|today|"
                             r"tomorrow|this week|last week)\b", re.IGNORECASE)
DISABLED_VALUES = ("false", "0", "no", "off")


def condense_enabled() -> bool:
    return os.getenv("ROUTER_CONDENSE_ENABLED", "true").strip().lower() not in DISABLED_VALUES


def needs_condense(query: str, history: list[dict], teams: TeamDirectory, season: str | None = None) -> bool:
    if not any(item.get("role") == "user" and str(item.get("content", "")).strip() for item in history):
        return False
    text = query.strip()
    if FOLLOWUP_TH.search(text) or FOLLOWUP_EN.search(text) or len(text) < SHORT_QUERY_CHARS:
        return True
    return not teams.find(text) and _intent(text, season) not in TEAM_FREE_INTENTS


def _is_question(text: str) -> bool:
    stripped = text.strip()
    return stripped.endswith("?") or bool(QUESTION_TH.search(stripped) or QUESTION_EN.search(stripped))


def _time_markers(text: str) -> set[str]:
    return ({marker for marker in TIME_MARKERS_TH if marker in text}
            | {match.lower() for match in TIME_MARKERS_EN.findall(text)})


def invented_entities(original: str, rewritten: str, history: list[dict], teams: TeamDirectory) -> list[str]:
    """Teams, numbers and time scopes in the rewrite that appear in neither the question nor the history."""
    source = "\n".join([original, *(str(item.get("content", "")) for item in history)])
    known = {team.team_id for team in teams.find(source)}
    names = [team.short_name for team in teams.find(rewritten) if team.team_id not in known]
    numbers = sorted(set(NUMBER.findall(rewritten)) - set(NUMBER.findall(source)))
    times = sorted(_time_markers(rewritten) - _time_markers(source))
    return names + numbers + times


def validate(original: str, rewritten: str, history: list[dict], teams: TeamDirectory) -> str | None:
    candidate = rewritten.strip()
    if not candidate or len(candidate) > 3 * len(original.strip()) + 120:
        return None
    if CITATION.search(candidate):
        return None
    if _is_question(original) and not _is_question(candidate):
        return None
    if invented_entities(original, candidate, history, teams):
        return None
    asked = {team.team_id for team in teams.find(original)}
    if not asked <= {team.team_id for team in teams.find(candidate)}:
        return None
    return candidate
