import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .teams import TeamDirectory


INTENT_MAP = {
    "trivia_history": ("football_rag", "trivia"),
    "match_result": ("football_rag", "match_report"),
    "fixture_schedule": ("football_rag", "fixtures"),
    "standings_stats": ("football_rag", "standings"),
    "weekly_summary": ("football_rag", "weekly_report"),
    "general_football": ("general_ai", None),
    "prediction": ("local_ai", None),
    "out_of_scope": ("decline", None),
    "player_info": ("football_rag", "player"),
}

# CONTRACT v1.5: the 04 classifier does not know player_info, so these rules are its main entry.
PLAYER_WORDS = ("นักเตะ", "ผู้เล่น", "สควอด", "ผู้รักษาประตู", "กองหน้า", "กองกลาง", "กองหลัง",
                "โค้ช", "ผู้จัดการทีม", "กุนซือ", "ตำแหน่งอะไร", "เล่นตำแหน่ง", "อายุเท่า", "สัญชาติ",
                "squad", "players", "who plays for", "head coach", "manager of", "coach of",
                "how old is", "nationality")
# Goal and table questions stay with the scorer/standings rules or fall through to the LLM.
NOT_PLAYER_WORDS = ("ยิง", "ทำประตู", "กี่ประตู", "กี่ลูก", "ตาราง", "goals", "scored", "assist",
                    "table")

MATCHWEEK_PATTERN = re.compile(r"(?:นัดที่\s*|แมตช์วีค\s*|สัปดาห์ที่\s*|matchweek\s*)(\d+)")
OTHER_COMPETITIONS = ("ลาลีกา", "แชมเปียนส์ลีก", "แชมเปี้ยนส์ลีก", "ยูฟ่า",
                      "บุนเดสลีกา", "กัลโช่", "ฟุตบอลโลก", "la liga",
                      "champions league", "serie a", "bundesliga", "ligue 1", "world cup")
# Whole-season outlook questions (CONTRACT v1.7): answered from 07 /football/simulation.
SEASON_PREDICTION = re.compile(
    r"จะ\s*(?:ได้|เป็น|คว้า)?\s*แชมป์|จะ\s*ตกชั้น|จะ\s*(?:ติด|จบ)\s*(?:ท็อป|อันดับ)|เสี่ยง\s*ตกชั้น"
    r"|มีโอกาส\s*(?:ได้\s*)?(?:แชมป์|ติดท็อป|ท็อป|ตกชั้น|จบอันดับ)"
    r"|\bwho will (?:win the (?:premier league|league|title)|be relegated|finish)\b"
    r"|\bchances? of (?:winning the (?:league|title)|(?:a )?top[- ]?(?:4|four)|relegation|being relegated)\b")
SEASON_WORDS = ("แชมป์", "ท็อปโฟร์", "ท็อป 4", "ท็อป4", "top 4", "top four", "ตกชั้น", "relegat",
                "อันดับ", "title", "finish")


def normalize_thai(text: str) -> str:
    """Users often type two sara e (เเ) where they mean sara ae (แ)."""
    return text.replace("เเ", "แ")


def season_prediction(query: str) -> bool:
    return bool(SEASON_PREDICTION.search(query.lower()))


def prediction_kind(query: str, team_ids: list[int]) -> str:
    """match = two teams · season = title / top 4 / relegation outlook · otherwise ask."""
    if len(team_ids) >= 2:
        return "match"
    text = query.lower()
    if season_prediction(text) or _has(text, SEASON_WORDS):
        return "season"
    return "needs_team"


@dataclass
class Decision:
    route: str
    intent: str | None
    layer: str
    confidence: float
    reasoning: str
    filters: dict = field(default_factory=dict)
    rewritten_query: str | None = None
    team_ids: list[int] = field(default_factory=list)


def classify_intent(label: str, score: float) -> Decision | None:
    if label not in INTENT_MAP or score < 0.75:
        return None
    route, category = INTENT_MAP[label]
    filters = {"category": [category]} if category else {}
    return Decision(route, label, "classifier", score, f"classifier: {label}", filters)


def from_intent(label: str, confidence: float, layer: str = "llm") -> Decision | None:
    confidence = min(1.0, max(0.0, confidence))
    if label == "clarify":
        return Decision("clarify", None, layer, confidence, "คำถามกำกวม")
    if label not in INTENT_MAP:
        return None
    decision = classify_intent(label, max(0.75, confidence))
    decision.confidence = confidence
    decision.layer = layer
    decision.reasoning = f"{layer}: {label}"
    return decision


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _has_historical_marker(text: str) -> bool:
    if _has(text, ("ตลอดกาล", "ประวัติศาสตร์", "ย้อนหลัง", "ฤดูกาลที่แล้ว",
                   "ซีซั่นที่แล้ว", "ปีที่แล้ว", "ฤดูกาลก่อน", "ซีซั่นก่อน")):
        return True
    return bool(re.search(r"\b(?:all[- ]time|ever|in history|last season|previous season)\b", text))


def _previous_season(text: str) -> bool:
    return _has(text, ("ฤดูกาลที่แล้ว", "ซีซั่นที่แล้ว", "ปีที่แล้ว", "ฤดูกาลก่อน", "ซีซั่นก่อน")) or bool(
        re.search(r"\b(?:last season|previous season)\b", text)
    )


def _top_scorer_question(text: str) -> bool:
    return _has(text, ("ดาวซัลโว", "top scorer", "leading scorer", "golden boot")) or (
        _has(text, ("ยิง", "ทำประตู", "goals", "scored"))
        and _has(text, ("เยอะสุด", "เยอะที่สุด", "มากที่สุด", "สูงสุด", "most goals", "top scorer", "leading scorer"))
    )


def historical_scorer_season(query: str, current_season: str | None) -> tuple[str, bool] | None:
    """Read explicit season years; a bare year means its starting season."""
    text = query.lower()
    if not _top_scorer_question(text) or _has(text, ("ตลอดกาล", "ประวัติศาสตร์")) or re.search(
        r"\b(?:all[- ]time|ever|in history)\b", text
    ):
        return None
    full = re.search(r"(?<!\d)((?:19|20)\d{2})\s*[/\-]\s*((?:19|20)\d{2}|\d{2})(?!\d)", text)
    short = re.search(r"(?<!\d)(\d{2})\s*[/\-]\s*(\d{2})(?!\d)", text) if not full else None
    if full or short:
        match = full or short
        start = int(match.group(1)) if full else 2000 + int(match.group(1))
        end = int(match.group(2))
        if end != start + 1 and end != (start + 1) % 100:
            return None
        assumed = False
    else:
        years = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text)
        if len(years) == 1:
            start = int(years[0])
            assumed = True
        elif not years and _previous_season(text) and str(current_season or "").isdigit():
            start = int(current_season) - 1
            assumed = False
        else:
            return None
    if str(start) == str(current_season):
        return None
    return str(start), assumed


def league_wide_scorer_query(query: str, teams: TeamDirectory) -> bool:
    """Limit the verified winner shortcut to league player rankings."""
    text = query.lower()
    if teams.find(query) or MATCHWEEK_PATTERN.search(text) or _has(text, OTHER_COMPETITIONS):
        return False
    if _has(text, ("ทีมไหน", "สโมสรไหน", "which team", "which club", "team with most",
                   "เสียประตู", "conceded", "goals against", "ผู้รักษาประตู", "goalkeeper",
                   "เกมไหน", "นัดไหน", "ในเกม", "ในแมตช์", "which match", "which game",
                   "per match", "against",
                   "รอง", "runner-up", "second place", "อันดับสอง", "อันดับ 2",
                   "ตั้งแต่", "since", "จนถึง", "ถึง", "เดือน", "มกราคม", "กุมภาพันธ์",
                   "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
                   "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม")):
        return False
    if re.search(r"\bsecond\b", text) or re.search(r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
                 r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
                 r"dec(?:ember)?)\b", text):
        return False
    return _has(text, ("ใคร", "ดาวซัลโว", "top scorer", "leading scorer", "golden boot")) or bool(
        re.search(r"\bwho\b", text)
    )


def _current_top_scorer(text: str, current_season: str | None = None) -> bool:
    if not _top_scorer_question(text) or _has_historical_marker(text):
        return False
    if historical_scorer_season(text, current_season):
        return False
    years = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text)
    if not years:
        return True
    if not str(current_season or "").isdigit():
        return False
    if all(year == str(current_season) for year in years):
        return True
    next_year = str(int(current_season) + 1)
    return years == [str(current_season), next_year] and bool(re.search(
        rf"(?<!\d){re.escape(str(current_season))}\s*[/\-]\s*{re.escape(next_year)}(?!\d)", text
    ))


def _intent(query: str, current_season: str | None = None) -> str | None:
    text = query.lower()
    if _has(text, OTHER_COMPETITIONS) and _top_scorer_question(text):
        return "out_of_scope"
    if _has(text, ("พนัน", "เดิมพัน", "ราคาบอล", "ทีเด็ด", "แทงบอล", "odds", "betting", "bet ")):
        return "out_of_scope"
    if _has(text, ("อากาศ", "ร้านอาหาร", "bitcoin", "โค้ด python", "เขียนเว็บ", "หุ้น")):
        return "out_of_scope"
    if _has(text, ("ทำนาย", "คาดการณ์", "พยากรณ์ผล", "predict", "who will win", "โอกาสชนะ", "จะชนะ")) or (
            season_prediction(text)):
        return "prediction"
    if _has(text, ("ใบเหลือง", "ใบแดง", "ลูกโทษ")) and _has(
            text, ("เมื่อวาน", "เมื่อคืน", "นัดล่าสุด", "นัดก่อน", "นัดที่", "แมตช์", "เกมล่าสุด", "ผลแข่ง")):
        return "match_result"
    if _has(text, ("กฎ", "ล้ำหน้า", "var ", "ใบเหลือง", "ใบแดง", "แฮนด์บอล", "ลูกโทษ", "แผนการเล่น", "free kick", "ผู้รักษาประตูใช้มือ")):
        return "general_football"
    if _has(text, ("สรุป", "ไฮไลต์", "weekly summary")) and _has(text, ("สัปดาห์", "นัด", "week", "พรีเมียร์ลีก")):
        return "weekly_summary"
    if _has(text, ("แชมป์", "บัลลงดอร์", "ประวัติ", "trivia", "history")):
        return "trivia_history"
    if _has(text, ("โปรแกรม", "เตะกับใครต่อ", "แข่งกับใครต่อ", "นัดหน้า", "เมื่อไร", "วันไหน", "fixture", "schedule")):
        return "fixture_schedule"
    if _top_scorer_question(text):
        return "standings_stats" if _current_top_scorer(text, current_season) else "trivia_history"
    if re.search(r"\bscorers?\b", text):
        return "trivia_history" if _has_historical_marker(text) else "standings_stats"
    if _has(text, ("ตารางคะแนน", "จ่าฝูง", "อันดับ", "กี่แต้ม", "standings", "points")):
        return "standings_stats"
    if (_has(text, PLAYER_WORDS) or re.search(r"\bposition\b.*\bplay", text)) and not _has(
            text, NOT_PLAYER_WORDS):
        return "player_info"
    if _has(text, ("เมื่อวาน", "นัดล่าสุด", "นัดก่อน", "ชนะไหม", "ผลนัด", "ผลแข่ง", "จบเท่าไร", "สกอร์", "result")) or re.search(r"\bscore\b", text):
        return "match_result"
    if _has(text, ("ใครได้", "เคยได้", "ประวัติ", "กี่ครั้ง", "บัลลงดอร์", "ใครยิง", "trivia", "history")):
        return "trivia_history"
    return None


def _rewrite(query: str, intent: str, names: list[str], filters: dict) -> str:
    if not re.search(r"[ก-๙]", query):
        return query
    def keep_question(*parts: str) -> str:
        return " ".join(part for part in (*parts, query.strip()) if part)

    teams = " ".join(names)
    season = filters.get("season", "")
    matchweek = f"matchweek {filters['matchweek']}" if "matchweek" in filters else ""
    dates = " ".join(str(filters[key]) for key in ("date_from", "date_to") if key in filters)
    if intent == "match_result":
        event = "previous match result" if "ก่อนหน้า" in query else "latest match result"
        return keep_question(teams, event, season, matchweek, dates)
    if intent == "fixture_schedule":
        return keep_question(teams, "next Premier League fixture date opponent", season, matchweek, dates)
    if intent == "standings_stats":
        topic = "top scorer" if _top_scorer_question(query.lower()) else "standings points ranking"
        return keep_question(teams, "Premier League", topic, season, matchweek)
    if intent == "weekly_summary":
        return keep_question(teams, "Premier League weekly report summary", season, matchweek, dates)
    if intent == "player_info":
        return keep_question(teams, "Premier League squad players position nationality coach", season)
    if "บัลลงดอร์" in query:
        years = " ".join(re.findall(r"(?:19|20)\d{2}", query))
        return keep_question("Ballon d'Or winner", years)
    if "แชมป์" in query:
        return keep_question(teams, "Premier League title championship history count")
    years = " ".join(re.findall(r"(?:19|20)\d{2}", query))
    return keep_question(teams, "football trivia history", years)


def enrich(decision: Decision, query: str, context: dict, history: list[dict], teams: TeamDirectory,
           favorite_team_id: int | None = None) -> Decision:
    found = teams.find(query)
    if not found and re.search(r"(แล้ว|นัดนั้น|เขา|ทีมไหน)", query):
        for item in reversed(history[-10:]):
            if item.get("role") == "user":
                found = teams.find(item.get("content", ""))
                if found:
                    break
    if not found and favorite_team_id and re.search(r"(ทีมโปรด|ทีมฉัน|ทีมของฉัน)", query):
        found = [team for team in teams.teams if team.team_id == favorite_team_id]
    decision.team_ids = [team.team_id for team in found]
    if decision.route == "football_rag":
        if decision.intent == "trivia_history":
            decision.rewritten_query = _rewrite(query, decision.intent,
                                                [team.short_name for team in found], decision.filters)
            return decision
        if decision.team_ids:
            decision.filters["team_ids"] = decision.team_ids
        if context.get("season"):
            decision.filters["season"] = str(context["season"])
        text = query.lower()
        now = datetime.fromisoformat(context["now"]) if context.get("now") else datetime.now().astimezone()
        if "เมื่อวาน" in text or "yesterday" in text:
            day = (now - timedelta(days=1)).date().isoformat()
            decision.filters.update(date_from=day, date_to=day)
        elif "วันนี้" in text or "today" in text:
            day = now.date().isoformat()
            decision.filters.update(date_from=day, date_to=day)
        elif "สัปดาห์นี้" in text or "this week" in text:
            monday = (now - timedelta(days=now.weekday())).date()
            decision.filters.update(date_from=monday.isoformat(), date_to=(monday + timedelta(days=6)).isoformat())
        match = MATCHWEEK_PATTERN.search(text)
        if match:
            decision.filters["matchweek"] = int(match.group(1))
        elif decision.intent in ("weekly_summary", "standings_stats") and context.get("current_matchweek") and "สัปดาห์นี้" not in text:
            decision.filters["matchweek"] = int(context["current_matchweek"])
        decision.rewritten_query = _rewrite(query, decision.intent,
                                            [team.short_name for team in found], decision.filters)
    return decision


def decide(query: str, context: dict, history: list[dict], teams: TeamDirectory,
           favorite_team_id: int | None = None) -> Decision | None:
    text = query.lower().strip()
    if not text:
        return Decision("clarify", None, "guard", 1.0, "ไม่มีคำถาม")
    matchweek = MATCHWEEK_PATTERN.search(text)
    if matchweek and not 1 <= int(matchweek.group(1)) <= 38:
        return Decision("clarify", None, "guard", 1.0, "เลขนัดต้องอยู่ระหว่าง 1 ถึง 38")
    found = teams.find(query)
    if not found and ("ยูไนเต็ด" in text or re.search(r"(?<![A-Za-z])united(?![A-Za-z])", text)):
        return Decision("clarify", None, "guard", 1.0, "ชื่อ United กำกวม")
    if not found and _has(text, ("นัดนั้น", "ทีมไหนชนะ", "เขายิง")) and not history:
        return Decision("clarify", None, "guard", 1.0, "ขาดทีมที่อ้างถึง")
    if len(found) > 2:
        return Decision("clarify", None, "guard", 1.0, "พบหลายทีมในคำถาม")
    intent = _intent(query, context.get("season"))
    if intent is None and history and re.search(r"(แล้ว|นัดก่อน|นัดนั้น)", text):
        for item in reversed(history[-10:]):
            if item.get("role") == "user":
                intent = _intent(item.get("content", ""), context.get("season"))
                if intent is not None:
                    break
    if intent is None:
        return None
    route, category = INTENT_MAP[intent]
    decision = Decision(route, intent, "guard" if route == "decline" else "rules", 1.0 if route == "decline" else 0.9,
                        f"ตรวจพบ intent {intent}", {"category": [category]} if category else {})
    return enrich(decision, query, context, history, teams, favorite_team_id)
