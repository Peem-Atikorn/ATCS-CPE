import json
import unittest
from pathlib import Path

from app.decisions import (classify_intent, decide, from_intent, historical_scorer_season,
                           prediction_kind)
from app.teams import TeamDirectory


CASES = Path(__file__).with_name("routing_cases.jsonl")
TEAMS = TeamDirectory.from_file(Path(__file__).parents[1] / "data" / "team_aliases.json")
CONTEXT = {"season": "2026", "current_matchweek": 5, "now": "2026-09-26T10:00:00+07:00"}


class DecisionTests(unittest.TestCase):
    def test_season_questions_are_prediction_intent(self):
        for query in ("ใครจะได้แชมป์พรีเมียร์ลีกปีนี้", "อาร์เซนอลมีโอกาสติดท็อป 4 กี่เปอร์เซ็นต์",
                      "ใครเสี่ยงตกชั้นมากที่สุด", "ทีมไหนจะตกชั้น", "Who will be relegated this season?",
                      "What are Arsenal's chances of winning the title?"):
            with self.subTest(query=query):
                self.assertEqual(decide(query, CONTEXT, [], TEAMS).intent, "prediction")

    def test_history_questions_stay_trivia(self):
        for query in ("อาร์เซนอลได้แชมป์พรีเมียร์ลีกกี่ครั้ง", "ลิเวอร์พูลได้แชมป์ครั้งล่าสุดเมื่อไร",
                      "เชลซีเคยได้แชมป์พรีเมียร์ลีกกี่ครั้ง"):
            with self.subTest(query=query):
                self.assertEqual(decide(query, CONTEXT, [], TEAMS).intent, "trivia_history")

    def test_prediction_kind(self):
        cases = (
            ("ลิเวอร์พูลกับซิตี้ใครจะชนะ", [64, 65], "match"),
            ("ใครจะได้แชมป์ปีนี้", [], "season"),
            ("อาร์เซนอลมีโอกาสติดท็อป 4 กี่ %", [57], "season"),
            ("ใครเสี่ยงตกชั้น", [], "season"),
            ("อาร์เซนอลมีโอกาสชนะไหม", [57], "needs_team"),
            ("ทำนายผลหน่อย", [], "needs_team"),
        )
        for query, team_ids, expected in cases:
            with self.subTest(query=query):
                self.assertEqual(prediction_kind(query, team_ids), expected)

    def test_historical_scorer_year_forms(self):
        cases = (
            ("ลีคปี 2025 ใครยิงเยอะสุด", ("2025", True)),
            ("พรีเมียร์ลีกฤดูกาล 2025/26 ดาวซัลโว", ("2025", False)),
            ("2025-2026 Premier League top scorer", ("2025", False)),
            ("พรีเมียร์ลีก 25/26 ใครทำประตูมากที่สุด", ("2025", False)),
            ("ใครยิงเยอะสุดตอนนี้", None),
            ("ใครยิงประตูมากที่สุดตลอดกาลปี 2025", None),
            ("Who was the top scorer last season", ("2025", False)),
            ("ใครเป็นดาวซัลโวซีซั่นที่แล้ว", ("2025", False)),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                self.assertEqual(historical_scorer_season(query, "2026"), expected)

    def test_explicit_current_season_scorer_uses_live_standings(self):
        result = decide("พรีเมียร์ลีกฤดูกาล 2026/27 ดาวซัลโว", CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "standings_stats")
        self.assertEqual(result.filters["season"], "2026")
        self.assertIn("top scorer", result.rewritten_query)

    def test_scorer_review_edge_cases(self):
        cases = (
            ("ดาวซัลโว Everton ตอนนี้", "standings_stats"),
            ("ดาวซัลโวฤดูกาล 2026", "standings_stats"),
            ("ดาวซัลโวฤดูกาล 2026/2027", "standings_stats"),
            ("ดาวซัลโวซีซั่น 2025/26", "trivia_history"),
            ("ผู้รักษาประตูคนไหนเซฟมากที่สุด", "player_info"),
            ("ทีมไหนเสียประตูมากที่สุด", None),
            ("Who was the top scorer last season", "trivia_history"),
            ("ใครเป็นดาวซัลโวซีซั่นที่แล้ว", "trivia_history"),
            ("ดาวซัลโวปีที่แล้ว", "trivia_history"),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                decision = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(decision.intent if decision else None, expected)

    def test_routing_cases(self):
        cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(cases), 44)
        self.assertEqual({route: sum(case["route"] == route for case in cases)
                          for route in {case["route"] for case in cases}},
                         {"football_rag": 9, "general_ai": 8, "local_ai": 11,
                          "clarify": 8, "decline": 8})
        for case in cases:
            with self.subTest(query=case["query"]):
                result = decide(case["query"], CONTEXT, [], TEAMS)
                self.assertIsNotNone(result)
                self.assertEqual(result.route, case["route"])
                if "intent" in case:
                    self.assertEqual(result.intent, case["intent"])

    def test_classifier_threshold_and_mapping(self):
        self.assertEqual(classify_intent("match_result", 0.75).route, "football_rag")
        self.assertIsNone(classify_intent("fixture_schedule", 0.74))
        self.assertEqual(classify_intent("prediction", 0.9).route, "local_ai")
        self.assertIsNone(classify_intent("unknown", 0.99))

    def test_yesterday_date_filter(self):
        result = decide("เมื่อวานปืนใหญ่ชนะไหม", CONTEXT, [], TEAMS)
        self.assertEqual(result.filters["category"], ["match_report"])
        self.assertEqual(result.filters["team_ids"], [57])
        self.assertEqual(result.filters["date_from"], "2026-09-25")
        self.assertEqual(result.filters["date_to"], "2026-09-25")
        self.assertNotIn("matchweek", result.filters)
        self.assertIn("Arsenal", result.rewritten_query)
        self.assertIn("เมื่อวานปืนใหญ่ชนะไหม", result.rewritten_query)

    def test_rewrite_keeps_person_and_question_condition(self):
        query = "ใครยิงประตูชัยให้ลิเวอร์พูลในนัดชิงปี 2005"
        result = decide(query, CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "trivia_history")
        self.assertIn(query, result.rewritten_query)

    def test_followup_reuses_recent_team(self):
        history = [{"role": "user", "content": "อาร์เซนอลนัดล่าสุดชนะไหม"},
                   {"role": "assistant", "content": "อาร์เซนอลชนะ"}]
        result = decide("แล้วนัดก่อนหน้าล่ะ", CONTEXT, history, TEAMS)
        self.assertEqual(result.route, "football_rag")
        self.assertEqual(result.filters["team_ids"], [57])
        self.assertIn("Arsenal", result.rewritten_query)

    def test_vague_followup_uses_latest_classifiable_user_intent(self):
        history = [{"role": "user", "content": "ทำนายผล แมนซิตี้ กับ ลิเวอร์พูล"},
                   {"role": "assistant", "content": "ยังไม่พร้อม"},
                   {"role": "user", "content": "อาร์เซนอลอยู่อันดับเท่าไร"}]
        result = decide("แล้วล่ะ", CONTEXT, history, TEAMS)
        self.assertEqual(result.intent, "standings_stats")
        self.assertEqual(result.route, "football_rag")

    def test_match_discipline_questions_remain_factual(self):
        for query in ("เมื่อวานลิเวอร์พูลได้ลูกโทษไหม", "ใครโดนใบแดงนัดล่าสุด"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(result.intent, "match_result")
                self.assertEqual(result.filters["category"], ["match_report"])

    def test_discipline_rule_question_stays_general(self):
        result = decide("กฎใบแดงคืออะไร", CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "general_football")

    def test_title_history_when_is_trivia(self):
        result = decide("ลิเวอร์พูลได้แชมป์ครั้งล่าสุดเมื่อไร", CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "trivia_history")
        self.assertEqual(result.filters["category"], ["trivia"])
        self.assertNotIn("season", result.filters)

    def test_team_trivia_does_not_filter_unlabeled_trivia_documents(self):
        result = decide("อาร์เซนอลได้แชมป์พรีเมียร์ลีกกี่ครั้ง", CONTEXT, [], TEAMS)
        self.assertEqual(result.team_ids, [57])
        self.assertEqual(result.filters, {"category": ["trivia"]})

    def test_full_manchester_club_names_are_recognized(self):
        for name, team_id in (("Manchester United", 66), ("Manchester City", 65)):
            with self.subTest(name=name):
                result = decide(f"{name} นัดล่าสุดชนะไหม", CONTEXT, [], TEAMS)
                self.assertEqual(result.team_ids, [team_id])
                self.assertEqual(result.intent, "match_result")

    def test_other_city_club_is_not_man_city(self):
        result = decide("เลสเตอร์ ซิตี้ ได้แชมป์ปีไหน", CONTEXT, [], TEAMS)
        self.assertNotIn(65, result.team_ids if result else [])

    def test_out_of_range_matchweek_is_clarified(self):
        for query in ("นัดที่ 45 ผลแข่งปืนใหญ่", "matchweek 0 Arsenal result"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(result.route, "clarify")

    def test_english_top_scorer_uses_standings(self):
        result = decide("who is the top scorer", CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "standings_stats")
        self.assertEqual(result.filters["category"], ["standings"])

    def test_weekly_summary_uses_spaced_matchweek(self):
        result = decide("สรุปพรีเมียร์ลีกนัดที่ 3", CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "weekly_summary")
        self.assertEqual(result.filters["matchweek"], 3)

    def test_current_scorer_filters_current_matchweek(self):
        result = decide("ใครนำดาวซัลโวตอนนี้", CONTEXT, [], TEAMS)
        self.assertEqual(result.filters["matchweek"], 5)

    def test_current_top_scorer_phrases_use_standings(self):
        for query in (
            "ใครยิงเยอะสุดในลีกตอนนี้",
            "ครยิงเยอะสุดในลีกตอนนี้",
            "ใครทำประตูมากที่สุดในพรีเมียร์ลีกฤดูกาลนี้",
            "ใครทำประตูเยอะที่สุด",
            "ใครยิงเยอะที่สุดตอนนี้",
            "นักเตะคนไหนยิงประตูมากที่สุดฤดูกาลนี้",
            "Who has the most goals this season",
        ):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(result.intent, "standings_stats")
                self.assertEqual(result.filters["category"], ["standings"])
                self.assertEqual(result.filters["matchweek"], 5)
                if query != "Who has the most goals this season":
                    self.assertIn("top scorer", result.rewritten_query)

    def test_historical_scorer_does_not_use_current_standings(self):
        for query in ("ใครยิงมากที่สุดในลีกปี 2020", "ใครยิงประตูมากที่สุดตลอดกาลของพรีเมียร์ลีก"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(result.intent, "trivia_history")

    def test_ambiguous_united(self):
        self.assertEqual(decide("ยูไนเต็ดนัดล่าสุดชนะไหม", CONTEXT, [], TEAMS).route, "clarify")

    def test_alias_does_not_match_inside_english_word(self):
        self.assertEqual(TEAMS.find("Arsenalization"), [])

    def test_prediction_teams_follow_question_order(self):
        result = decide("ทำนายผล แมนซิตี้ กับ ลิเวอร์พูล", CONTEXT, [], TEAMS)
        self.assertEqual(result.team_ids, [65, 64])

    def test_liverpool_duck_alias_resolves_offline(self):
        self.assertEqual(TEAMS.find("เป็ดแดงเตะวันไหน")[0].team_id, 64)
        self.assertIn("Liverpool", TEAMS.replace_aliases("เป็ดแดงเตะวันไหน"))

    def test_live_team_refresh_keeps_offline_aliases(self):
        live = TeamDirectory.from_payload({"teams": [{"team_id": 57, "name": "Arsenal FC",
            "short_name": "Arsenal", "aliases": ["ใหม่"]}]})
        merged = TEAMS.merged(live)
        self.assertEqual(merged.find("ปืนใหญ่")[0].team_id, 57)
        self.assertEqual(merged.find("ใหม่")[0].team_id, 57)


if __name__ == "__main__":
    unittest.main()


class PlayerInfoTests(unittest.TestCase):
    """CONTRACT v1.5: the classifier (04) does not know player_info, so rules must catch it."""

    PLAYER_QUERIES = [
        ("อาร์เซนอลมีนักเตะใครบ้าง", [57]),
        ("ขอดูสควอดของเชลซีหน่อย", [61]),
        ("โค้ชของลิเวอร์พูลคือใคร", [64]),
        ("ผู้จัดการทีมแมนซิตี้คนปัจจุบันคือใคร", [65]),
        ("ซาก้าเล่นตำแหน่งอะไร", []),
        ("ฮาลันด์อายุเท่าไหร่", []),
        ("นักเตะสัญชาติไทยในพรีเมียร์ลีกมีใครบ้าง", []),
        ("ผู้รักษาประตูของนิวคาสเซิลมีใครบ้าง", [67]),
        ("Which players are in the Chelsea squad", [61]),
        ("What position does Salah play", []),
        ("Who is the manager of Arsenal", [57]),
        ("How old is Erling Haaland", []),
    ]

    def test_player_questions_route_to_player_documents(self):
        for query, team_ids in self.PLAYER_QUERIES:
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertIsNotNone(result)
                self.assertEqual(result.intent, "player_info")
                self.assertEqual(result.route, "football_rag")
                self.assertEqual(result.layer, "rules")
                self.assertEqual(result.filters["category"], ["player"])
                self.assertEqual(result.filters.get("team_ids", []), team_ids)
                self.assertNotIn("matchweek", result.filters)

    def test_player_rewrite_is_english_and_keeps_the_question(self):
        query = "อาร์เซนอลมีนักเตะใครบ้าง"
        result = decide(query, CONTEXT, [], TEAMS)
        self.assertIn("Arsenal", result.rewritten_query)
        self.assertIn("squad", result.rewritten_query)
        self.assertIn(query, result.rewritten_query)

    def test_neighbouring_questions_keep_their_intent(self):
        cases = [
            ("ใครนำดาวซัลโวตอนนี้", "standings_stats"),
            ("ดาวซัลโวของอาร์เซนอลคือใคร", "standings_stats"),
            ("อาร์เซนอลอยู่ตำแหน่งไหนในตารางคะแนน", "standings_stats"),
            ("ผู้รักษาประตูใช้มือได้ตอนไหน", "general_football"),
            ("ผู้เล่นคนไหนโดนใบแดงเมื่อวาน", "match_result"),
            ("โค้ชคนไหนพาทีมได้แชมป์พรีเมียร์ลีกมากที่สุด", "trivia_history"),
            ("นักเตะคนไหนยิงประตูมากที่สุดฤดูกาลนี้", "standings_stats"),
            # This question still falls through to the classifier/LLM.
            ("What position is Arsenal in the table", None),
        ]
        for query, intent in cases:
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(result.intent if result else None, intent)

    def test_classifier_and_llm_labels_map_to_player_documents(self):
        self.assertEqual(classify_intent("player_info", 0.8).filters, {"category": ["player"]})
        self.assertEqual(from_intent("player_info", 0.6).route, "football_rag")
