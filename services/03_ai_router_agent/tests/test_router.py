import asyncio
import unittest
from unittest.mock import patch

from app.router import Router, UpstreamError
from app.teams import TeamDirectory
from pathlib import Path


class FakeClients:
    def __init__(self):
        self.calls = []
        self.chunks = []
        self.classifier = {"data": {"label": "general_football", "score": 0.9}}
        self.standalone = None

    async def historical_scorer(self, season, request_id):
        self.calls.append(("historical_scorer", season, request_id))
        if season != "2025":
            raise UpstreamError("football-data", 404)
        return {"season": "2025", "season_label": "2025/26",
                "player": "Erling Haaland", "goals": 27,
                "source_url": "https://www.premierleague.com/en/news/4668605"}

    async def search(self, payload, request_id):
        self.calls.append(("search", payload, request_id))
        return {"chunks": self.chunks}

    async def general(self, payload, request_id):
        self.calls.append(("general", payload, request_id))
        return {"content": "กฎฟุตบอล", "token_usage": {"input": 2, "output": 3}}

    async def classify(self, payload, request_id):
        self.calls.append(("classify", payload, request_id))
        return self.classifier

    async def predict_match(self, home_team_id, away_team_id, request_id):
        self.calls.append(("predict_match", {"home_team_id": home_team_id,
                                             "away_team_id": away_team_id}, request_id))
        return {"content": "Liverpool ชนะ 46% · เสมอ 27% · Man City ชนะ 27% · สกอร์ที่น่าจะเป็นที่สุด 1–1",
                "data": {"as_of": "2026-09-30T22:50:00+07:00"}}

    async def season_simulation(self, request_id):
        self.calls.append(("season_simulation", None, request_id))
        return {"season": "2026", "as_of": "2026-09-30T22:50:00+07:00", "stale": False, "n_sims": 10000,
                "teams": [{"team_id": 65, "short_name": "Man City", "points": 15, "expected_points": 80.0,
                           "p_title": 0.38, "p_top4": 0.9, "p_relegation": 0.0},
                          {"team_id": 57, "short_name": "Arsenal", "points": 12, "expected_points": 74.0,
                           "p_title": 0.31, "p_top4": 0.82, "p_relegation": 0.0}]}

    async def generate(self, payload, request_id):
        self.calls.append(("generate", payload, request_id))
        answer = payload["draft"] if payload.get("mode") == "passthrough" else "ตอบแล้ว"
        return {"answer": answer, "sources": [c["source"] for c in payload.get("contexts", [])],
                "token_usage": {"input": 5, "output": 7}}

    async def llm_decide(self, query, request_id):
        self.calls.append(("llm", query, request_id))
        return {"intent": "general_football", "confidence": 0.8}

    async def condense(self, query, history, request_id):
        self.calls.append(("condense", query, request_id))
        if self.standalone is None:
            raise UpstreamError("llm")
        return {"standalone_query": self.standalone, "changed": True,
                "token_usage": {"input": 3, "output": 2}}


class RouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clients = FakeClients()
        teams = TeamDirectory.from_file(Path(__file__).parents[1] / "data" / "team_aliases.json")
        self.router = Router(self.clients, teams)
        self.request = {"request_id": "req-1", "session_id": "session-1",
                        "user": {"id": "user-1", "favorite_team_id": None, "language": "th"},
                        "query": "", "history": [],
                        "context": {"season": "2026", "current_matchweek": 5,
                                    "now": "2026-09-26T10:00:00+07:00"}}

    async def run_query(self, query):
        return await self.router.route({**self.request, "query": query})

    async def test_bare_historical_year_uses_verified_scorer_and_names_season(self):
        result = await self.run_query("ลีคปี 2025 ใครยิงเยอะสุด")
        self.assertIn("ถ้าหมายถึงพรีเมียร์ลีกฤดูกาล 2025/26", result["answer"])
        self.assertIn("Erling Haaland", result["answer"])
        self.assertEqual(result["trace"]["intent"], "trivia_history")
        self.assertEqual(result["sources"][0]["url"],
                         "https://www.premierleague.com/en/news/4668605")
        self.assertEqual(self.clients.calls[0][0], "historical_scorer")

    async def test_unverified_historical_year_does_not_guess(self):
        result = await self.run_query("พรีเมียร์ลีกปี 2020 ใครยิงเยอะสุด")
        self.assertIn("ยังไม่มีข้อมูล", result["answer"])
        self.assertEqual(result["sources"], [])
        self.assertEqual([call[0] for call in self.clients.calls], ["historical_scorer"])

    async def test_last_season_uses_previous_verified_season(self):
        result = await self.run_query("Who was the top scorer last season")
        self.assertIn("2025/26", result["answer"])
        self.assertEqual(result["sources"][0]["doc_id"], "official-scorer-2025")

    async def test_team_match_and_player_questions_skip_league_winner_shortcut(self):
        queries = (
            "Arsenal top scorer 2023/24",
            "อาร์เซนอลใครยิงเยอะสุดฤดูกาล 2024/25",
            "ทีมไหนยิงประตูมากที่สุดฤดูกาล 2024/25",
            "ทีมไหนเสียประตูมากที่สุดฤดูกาล 2024/25",
            "ผู้รักษาประตูคนไหนเซฟมากที่สุด 2024/25",
            "ใครยิงเยอะสุดนัดที่ 3 ฤดูกาล 2024/25",
            "Salah ยิงมากที่สุดในเกมไหน 2024/25",
            "Everton top scorer 2024/25",
            "ดาวซัลโวลาลีกาฤดูกาล 2023/24",
            "ดาวซัลโวแชมเปียนส์ลีก 2023/24",
            "ใครได้รองดาวซัลโว 2023/24",
            "Who was second top scorer in 2023/24",
            "ใครยิงเยอะสุดตั้งแต่ปี 2020",
            "ใครยิงเยอะสุดถึง 2020",
            "ใครยิงเยอะสุดในเดือนสิงหาคม 2025",
        )
        for query in queries:
            with self.subTest(query=query):
                self.clients.calls.clear()
                result = await self.run_query(query)
                self.assertNotIn("historical_scorer", [call[0] for call in self.clients.calls])
                self.assertNotIn("official-scorer-", str(result["sources"]))

    async def test_rag_calls_search_and_grounded_generation(self):
        source = {"ref": 1, "doc_id": "match-1", "title": "Arsenal result", "category": "match_report",
                  "origin": "football-data.org", "season": "2026", "matchweek": 5,
                  "team_ids": [57], "fetched_at": "2026-09-26T09:00:00+07:00", "url": None}
        self.clients.chunks = [{"text": "Arsenal won 1-0", "source": source}]
        result = await self.run_query("เมื่อวานปืนใหญ่ชนะไหม")
        self.assertEqual(result["route"], "football_rag")
        self.assertEqual(result["engines_used"], ["retrieval", "generation"])
        self.assertEqual(self.clients.calls[0][0], "search")
        self.assertEqual(self.clients.calls[0][1]["filters"]["team_ids"], [57])
        self.assertIn("เมื่อวานปืนใหญ่ชนะไหม", self.clients.calls[0][1]["query"])
        self.assertEqual(self.clients.calls[1][1]["mode"], "grounded")
        self.assertEqual(self.clients.calls[1][1]["contexts"][0]["source"]["doc_id"], "match-1")
        self.assertEqual(result["sources"][0]["doc_id"], "match-1")
        self.assertTrue(all(call[2] == "req-1" for call in self.clients.calls))

    async def test_empty_match_data_never_calls_general(self):
        result = await self.run_query("เมื่อวานปืนใหญ่ชนะไหม")
        self.assertEqual(result["route"], "football_rag")
        self.assertEqual(result["trace"]["fallback"], "retrieval_empty")
        self.assertEqual([x[0] for x in self.clients.calls], ["search", "search"])

    async def test_empty_match_data_reports_ingest_time_when_supplied(self):
        request = {**self.request, "query": "เมื่อวานปืนใหญ่ชนะไหม",
                   "context": {**self.request["context"], "last_ingest_at": "2026-09-26T09:00:00+07:00"}}
        result = await self.router.route(request)
        self.assertIn("2026-09-26T09:00:00+07:00", result["answer"])

    async def test_scorer_uses_standings_without_general_fallback(self):
        result = await self.run_query("ใครนำดาวซัลโวตอนนี้")
        self.assertEqual(result["route"], "football_rag")
        self.assertEqual(self.clients.calls[0][1]["filters"]["category"], ["standings"])
        self.assertEqual(self.clients.calls[0][1]["filters"]["matchweek"], 5)
        self.assertNotIn("matchweek", self.clients.calls[1][1]["filters"])
        self.assertIn("ดาวซัลโว", self.clients.calls[0][1]["query"])
        self.assertNotIn("general", [call[0] for call in self.clients.calls])

    async def test_explicit_old_standings_week_does_not_fall_back_to_current_table(self):
        result = await self.run_query("ตารางคะแนนหลังแมตช์วีค 4")
        self.assertEqual(result["route"], "football_rag")
        searches = [call for call in self.clients.calls if call[0] == "search"]
        self.assertEqual(len(searches), 1)
        self.assertEqual(searches[0][1]["filters"]["matchweek"], 4)
        self.assertEqual(result["trace"]["fallback"], "retrieval_empty")

    async def test_english_explicit_old_standings_week_does_not_fall_back(self):
        result = await self.run_query("Standings after Matchweek 4")
        self.assertEqual(result["route"], "football_rag")
        searches = [call for call in self.clients.calls if call[0] == "search"]
        self.assertEqual(len(searches), 1)
        self.assertEqual(searches[0][1]["filters"]["matchweek"], 4)
        self.assertEqual(result["trace"]["fallback"], "retrieval_empty")

    async def test_empty_trivia_falls_back_to_general(self):
        result = await self.run_query("ใครได้บัลลงดอร์ปี 2008")
        self.assertEqual(result["route"], "general_ai")
        self.assertIn("ไม่ได้อ้างอิงคลังข้อมูล", result["answer"])
        self.assertEqual([x[0] for x in self.clients.calls], ["search", "general", "generate"])

    async def test_team_trivia_reaches_unlabeled_trivia_chunk(self):
        async def search(payload, request_id):
            self.clients.calls.append(("search", payload, request_id))
            if "team_ids" in payload["filters"]:
                return {"chunks": []}
            return {"chunks": [{"text": "Arsenal won three titles", "source": {
                "doc_id": "trivia-0001", "title": "Arsenal titles", "category": "trivia",
                "origin": "trivia", "ref": 1}}]}
        self.clients.search = search
        result = await self.run_query("อาร์เซนอลได้แชมป์พรีเมียร์ลีกกี่ครั้ง")
        self.assertEqual(result["route"], "football_rag")
        self.assertEqual([x[0] for x in self.clients.calls], ["search", "generate"])
        self.assertEqual(result["sources"][0]["doc_id"], "trivia-0001")

    async def test_ambiguous_team_does_not_call_upstream(self):
        result = await self.run_query("ยูไนเต็ดนัดล่าสุดชนะไหม")
        self.assertEqual(result["route"], "clarify")
        self.assertEqual(self.clients.calls, [])

    async def test_unknown_uses_classifier(self):
        result = await self.run_query("ฟุตบอลเล่นกี่คน")
        self.assertEqual(result["trace"]["decided_at_layer"], "classifier")
        self.assertEqual([x[0] for x in self.clients.calls], ["classify", "general", "generate"])

    async def test_low_classifier_uses_llm(self):
        self.clients.classifier = {"data": {"label": "general_football", "score": 0.4}}
        result = await self.run_query("ฟุตบอลเล่นกี่คน")
        self.assertEqual(result["trace"]["decided_at_layer"], "llm")

    async def test_llm_rewrite_keeps_original_question_in_search(self):
        self.clients.classifier = {"data": {"label": "general_football", "score": 0.4}}
        async def llm_decide(query, request_id):
            return {"intent": "trivia_history", "confidence": 0.8,
                    "rewritten_query": "Premier League history"}
        self.clients.llm_decide = llm_decide
        query = "นักเตะชื่อ กิตติ เคยยิงให้ลิเวอร์พูลกี่ประตู"
        await self.run_query(query)
        self.assertIn(query, self.clients.calls[1][1]["query"])

    async def test_double_sara_e_spelling_matches_team_nicknames(self):
        result = await self.run_query("ระหว่าง เป็ดเเดง กับ เรือใบสีฟ้า ใครน่าจะชนะ")
        self.assertEqual(result["route"], "local_ai")
        call = next(call[1] for call in self.clients.calls if call[0] == "predict_match")
        self.assertEqual((call["home_team_id"], call["away_team_id"]), (64, 65))

    async def test_who_will_win_between_two_teams_is_prediction(self):
        result = await self.run_query("ระหว่าง เป็ดแดง กับ เรือใบสีฟ้า ใครจะชนะ")
        self.assertEqual(result["route"], "local_ai")
        called = [call[0] for call in self.clients.calls]
        self.assertEqual(called[0], "predict_match")
        self.assertNotIn("llm", called)
        self.assertIn("ไม่ใช่คำแนะนำการพนัน", result["answer"])

    async def test_season_questions_use_the_simulation(self):
        for query in ("คุณคิดว่าใครจะได้เเชมป์ปีนี้", "เดาสิว่าใครจะแชมป์ปีนี้",
                      "Who will win the Premier League this season?"):
            with self.subTest(query=query):
                self.clients.calls.clear()
                result = await self.run_query(query)
                self.assertEqual(result["route"], "local_ai")
                self.assertEqual(self.clients.calls[0][0], "season_simulation")
                self.assertIn("1. Man City 38%", result["answer"])
                self.assertIn("จำลอง 10,000 ครั้ง", result["answer"])

    async def test_two_teams_title_question_uses_the_simulation(self):
        result = await self.run_query("อาร์เซนอลกับแมนซิตี้ ใครจะได้แชมป์")
        self.assertEqual(self.clients.calls[0][0], "season_simulation")
        self.assertIn("Arsenal: แต้มตอนนี้ 12", result["answer"])
        self.assertIn("Man City: แต้มตอนนี้ 15", result["answer"])

    async def test_single_team_season_question_shows_that_team(self):
        result = await self.run_query("อาร์เซนอลมีโอกาสติดท็อป 4 กี่เปอร์เซ็นต์")
        self.assertIn("Arsenal: แต้มตอนนี้ 12", result["answer"])

    async def test_prediction_without_enough_detail_asks(self):
        result = await self.run_query("ทำนายผลหน่อย")
        self.assertEqual(result["route"], "clarify")
        self.assertEqual(result["trace"]["fallback"], "prediction_needs_team")
        self.assertEqual(self.clients.calls, [])

    async def test_prediction_service_down_never_uses_general_ai(self):
        async def down(*args):
            raise UpstreamError("football-data", 503)
        self.clients.season_simulation = down
        result = await self.run_query("ใครจะได้แชมป์ปีนี้")
        self.assertEqual(result["answer"], "ตอนนี้ระบบทำนายผลไม่พร้อมใช้งาน")
        self.assertEqual(result["trace"]["fallback"], "simulation_down")
        self.assertNotIn("general", [call[0] for call in self.clients.calls])

    async def test_prediction_team_not_found(self):
        async def missing(*args):
            raise UpstreamError("football-data", 404)
        self.clients.predict_match = missing
        result = await self.run_query("ทำนายผล แมนซิตี้ กับ ลิเวอร์พูล")
        self.assertEqual(result["answer"], "ไม่พบข้อมูลของทีมนี้ในฤดูกาลปัจจุบัน")
        self.assertEqual(result["trace"]["fallback"], "prediction_team_not_found")

    async def test_retrieval_down_never_invents_match_result(self):
        async def unavailable(payload, request_id):
            raise UpstreamError("retrieval", 503)
        self.clients.search = unavailable
        result = await self.run_query("เมื่อวานปืนใหญ่ชนะไหม")
        self.assertEqual(result["trace"]["fallback"], "retrieval_down")
        self.assertEqual(result["engines_used"], [])
        self.assertNotIn("general", [call[0] for call in self.clients.calls])

    async def test_generation_down_does_not_expose_unchecked_draft(self):
        async def unavailable(payload, request_id):
            raise UpstreamError("generation", 503)
        self.clients.generate = unavailable
        result = await self.run_query("อธิบายกฎล้ำหน้า")
        self.assertEqual(result["trace"]["fallback"], "generation_down")
        self.assertEqual(result["answer"], "ตอนนี้ระบบไม่ว่าง ลองใหม่อีกครั้งในอีกสักครู่")

    async def test_timeout_returns_contract_fallback(self):
        async def slow_search(payload, request_id):
            await asyncio.sleep(0.1)
        self.clients.search = slow_search
        short_timeout = asyncio.timeout(0.001)
        with patch("app.router.asyncio.timeout", return_value=short_timeout):
            result = await self.run_query("เมื่อวานปืนใหญ่ชนะไหม")
        self.assertEqual(result["trace"]["fallback"], "router_timeout")

    async def test_empty_player_data_never_calls_general(self):
        result = await self.run_query("อาร์เซนอลมีนักเตะใครบ้าง")
        self.assertEqual(result["route"], "football_rag")
        self.assertEqual(result["trace"]["intent"], "player_info")
        self.assertEqual(result["trace"]["fallback"], "retrieval_empty")
        self.assertEqual(self.clients.calls[0][1]["filters"]["category"], ["player"])
        self.assertEqual(self.clients.calls[0][1]["filters"]["team_ids"], [57])
        self.assertNotIn("general", [call[0] for call in self.clients.calls])


if __name__ == "__main__":
    unittest.main()


class CondenseRouterTests(unittest.IsolatedAsyncioTestCase):
    HISTORY = [{"role": "user", "content": "ลิเวอร์พูลชนะไหมเมื่อวาน"},
               {"role": "assistant", "content": "ลิเวอร์พูลชนะ 2-1 [1]"}]
    STANDALONE = "ใครยิงประตูให้ลิเวอร์พูลในนัดเมื่อวาน"

    def setUp(self):
        patcher = patch.dict("os.environ", {"ROUTER_CONDENSE_ENABLED": "true"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.clients = FakeClients()
        self.clients.chunks = [{"text": "Liverpool won 2-1", "source": {
            "ref": 1, "doc_id": "match-64", "title": "Liverpool result", "category": "match_report",
            "origin": "football-data.org", "season": "2026", "matchweek": 5, "team_ids": [64],
            "fetched_at": "2026-09-26T09:00:00+07:00", "url": None}}]
        teams = TeamDirectory.from_file(Path(__file__).parents[1] / "data" / "team_aliases.json")
        self.router = Router(self.clients, teams)

    async def ask(self, query, history=None):
        return await self.router.route({
            "request_id": "req-1", "session_id": "session-1",
            "user": {"id": "user-1", "favorite_team_id": None, "language": "th"},
            "query": query, "history": self.HISTORY if history is None else history,
            "context": {"season": "2026", "current_matchweek": 5, "now": "2026-09-26T10:00:00+07:00"}})

    def names(self):
        return [call[0] for call in self.clients.calls]

    async def test_applied_condense_routes_and_searches_with_standalone_query(self):
        self.clients.standalone = self.STANDALONE
        result = await self.ask("แล้วใครยิง")
        self.assertEqual(self.names(), ["condense", "search", "generate"])
        search = self.clients.calls[1][1]
        self.assertEqual(search["filters"]["team_ids"], [64])
        self.assertIn(self.STANDALONE, search["query"])
        self.assertEqual(search["query_original"], "แล้วใครยิง")
        self.assertEqual(self.clients.calls[2][1]["query"], "แล้วใครยิง")
        self.assertEqual(result["trace"]["condense"], "applied")
        self.assertEqual(result["trace"]["standalone_query"], self.STANDALONE)
        self.assertEqual(result["trace"]["intent"], "match_result")
        self.assertIn("router.condense", [step["name"] for step in result["trace"]["steps"]])
        self.assertEqual(result["token_usage"], {"input": 8, "output": 9})

    async def test_condense_down_keeps_current_behaviour(self):
        result = await self.ask("แล้วใครยิง")
        self.assertEqual(result["trace"]["condense"], "unavailable")
        self.assertIsNone(result["trace"]["standalone_query"])
        self.assertIsNone(result["trace"]["fallback"])
        self.assertEqual(result["trace"]["intent"], "trivia_history")
        self.assertEqual(self.clients.calls[1][1]["query_original"], "แล้วใครยิง")

    async def test_rejected_rewrite_uses_original_query(self):
        self.clients.standalone = "ใครยิงประตูให้ลิเวอร์พูลและเชลซีเมื่อวาน"
        result = await self.ask("แล้วใครยิง")
        self.assertEqual(result["trace"]["condense"], "rejected")
        self.assertIsNone(result["trace"]["standalone_query"])
        self.assertEqual(result["trace"]["intent"], "trivia_history")

    async def test_unchanged_rewrite_is_recorded(self):
        self.clients.standalone = "แล้วใครยิง"
        result = await self.ask("แล้วใครยิง")
        self.assertEqual(result["trace"]["condense"], "unchanged")
        self.assertIsNone(result["trace"]["standalone_query"])

    async def test_slow_condense_times_out(self):
        async def slow(query, history, request_id):
            await asyncio.sleep(1)
        self.clients.condense = slow
        with patch("app.router.CONDENSE_TIMEOUT", 0.01):
            result = await self.ask("แล้วใครยิง")
        self.assertEqual(result["trace"]["condense"], "unavailable")
        self.assertEqual(result["route"], "football_rag")

    async def test_disabled_flag_skips_condense(self):
        self.clients.standalone = self.STANDALONE
        with patch.dict("os.environ", {"ROUTER_CONDENSE_ENABLED": "false"}):
            result = await self.ask("แล้วใครยิง")
        self.assertNotIn("condense", self.names())
        self.assertIsNone(result["trace"]["condense"])

    async def test_standalone_question_skips_condense(self):
        result = await self.ask("อาร์เซนอลอยู่อันดับเท่าไหร่")
        self.assertNotIn("condense", self.names())
        self.assertIsNone(result["trace"]["condense"])
        self.assertIsNone(result["trace"]["standalone_query"])

    async def test_no_history_skips_condense(self):
        await self.ask("แล้วใครยิง", history=[])
        self.assertNotIn("condense", self.names())

    async def test_unmatched_standalone_falls_back_to_original_rules(self):
        self.clients.standalone = "ลิเวอร์พูลนัดต่อไปเจอใคร"
        result = await self.ask("แล้วนัดต่อไปเจอใคร")
        self.assertEqual(result["route"], "football_rag")
        self.assertEqual(result["trace"]["filters"]["team_ids"], [64])
        self.assertNotIn("classify", self.names())
        self.assertEqual(result["trace"]["condense"], "applied")
        self.assertIsNone(result["trace"]["standalone_query"])

    async def test_retrieval_fallback_is_not_overwritten(self):
        self.clients.chunks = []
        self.clients.standalone = self.STANDALONE
        result = await self.ask("แล้วใครยิง")
        self.assertEqual(result["trace"]["condense"], "applied")
        self.assertEqual(result["trace"]["fallback"], "retrieval_empty")

    async def test_guarded_questions_are_not_rewritten(self):
        history = [{"role": "user", "content": "อาร์เซนอลอยู่อันดับเท่าไหร่"},
                   {"role": "assistant", "content": "อาร์เซนอลอยู่อันดับ 2 [1]"}]
        self.clients.standalone = "อาร์เซนอลอยู่อันดับเท่าไหร่"
        for query, route in (("แล้วราคาบอลล่ะ", "decline"), ("แล้วพรุ่งนี้อากาศเป็นไง", "decline"),
                             ("แล้วยูไนเต็ดล่ะ", "clarify")):
            with self.subTest(query=query):
                self.clients.calls = []
                result = await self.ask(query, history=history)
                self.assertEqual(result["route"], route)
                self.assertEqual(self.names(), [])
                self.assertIsNone(result["trace"]["condense"])
