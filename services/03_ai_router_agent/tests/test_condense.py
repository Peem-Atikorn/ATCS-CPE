import unittest
from pathlib import Path
from unittest.mock import patch

from app.condense import condense_enabled, invented_entities, needs_condense, validate
from app.teams import TeamDirectory


TEAMS = TeamDirectory.from_file(Path(__file__).parents[1] / "data" / "team_aliases.json")
LIVERPOOL_TURN = [{"role": "user", "content": "ลิเวอร์พูลชนะไหมเมื่อวาน"},
                  {"role": "assistant", "content": "ลิเวอร์พูลชนะ 2-1 [1]"}]


class FlagTests(unittest.TestCase):
    def test_flag_defaults_on(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(condense_enabled())

    def test_flag_values(self):
        for value, expected in (("true", True), ("1", True), ("yes", True), ("false", False),
                                ("0", False), ("no", False), ("OFF", False), (" False ", False)):
            with patch.dict("os.environ", {"ROUTER_CONDENSE_ENABLED": value}):
                self.assertEqual(condense_enabled(), expected, value)


class GateTests(unittest.TestCase):
    def gate(self, query, history=LIVERPOOL_TURN):
        return needs_condense(query, history, TEAMS, "2026")

    def test_no_history_never_condenses(self):
        for query in ("แล้วใครยิง", "who scored?", "มีนักเตะคนไหนบ้าง"):
            self.assertFalse(self.gate(query, []), query)

    def test_assistant_only_history_never_condenses(self):
        self.assertFalse(self.gate("แล้วใครยิง", [{"role": "assistant", "content": "สวัสดีครับ"}]))

    def test_follow_up_markers_condense(self):
        for query in ("แล้วใครยิง", "เขายิงกี่ลูก", "นัดก่อนหน้านั้นล่ะ", "แล้วเชลซีล่ะ",
                      "ทีมนี้นัดต่อไปเตะกับใคร", "what about the next match?",
                      "and who scored for them"):
            self.assertTrue(self.gate(query), query)

    def test_short_question_condenses(self):
        self.assertTrue(self.gate("ใครเป็นโค้ช"))
        self.assertTrue(self.gate("ใครทำประตู"))

    def test_team_bound_intent_without_team_condenses(self):
        self.assertTrue(self.gate("มีนักเตะคนไหนบ้าง"))

    def test_standalone_questions_skip(self):
        for query in ("อาร์เซนอลอยู่อันดับเท่าไหร่", "ตารางคะแนนพรีเมียร์ลีก",
                      "ใครได้บัลลงดอร์ปี 2008", "กฎล้ำหน้าคืออะไร",
                      "Who won Arsenal vs Chelsea yesterday?"):
            self.assertFalse(self.gate(query), query)


class ValidateTests(unittest.TestCase):
    def check(self, rewritten, original="แล้วใครยิง", history=LIVERPOOL_TURN):
        return validate(original, rewritten, history, TEAMS)

    def test_accepts_rewrite_using_history_team(self):
        self.assertEqual(self.check("  ใครยิงประตูให้ลิเวอร์พูลในนัดเมื่อวาน "),
                         "ใครยิงประตูให้ลิเวอร์พูลในนัดเมื่อวาน")

    def test_accepts_team_alias_from_history(self):
        self.assertEqual(self.check("ใครยิงประตูให้หงส์แดงเมื่อวาน"), "ใครยิงประตูให้หงส์แดงเมื่อวาน")

    def test_accepts_number_from_history(self):
        self.assertIsNotNone(self.check("ใครยิงประตูให้ลิเวอร์พูลในนัดที่ชนะ 2-1"))

    def test_rejects_new_team(self):
        self.assertIsNone(self.check("ใครยิงประตูให้ลิเวอร์พูลและเชลซีเมื่อวาน"))

    def test_rejects_new_number(self):
        self.assertIsNone(self.check("ใครยิงประตูให้ลิเวอร์พูลนัดที่ 7"))

    def test_rejects_answer_with_citation(self):
        self.assertIsNone(self.check("ซาลาห์ยิงให้ลิเวอร์พูล [1]"))

    def test_rejects_statement_when_user_asked(self):
        self.assertIsNone(self.check("ลิเวอร์พูลชนะเมื่อวาน"))

    def test_rejects_empty_and_too_long(self):
        self.assertIsNone(self.check("   "))
        self.assertIsNone(self.check("ใครยิงประตูให้ลิเวอร์พูล " * 20))

    def test_english_rewrite(self):
        history = [{"role": "user", "content": "Who won Arsenal vs Chelsea yesterday?"},
                   {"role": "assistant", "content": "Arsenal won 1-0 [1]"}]
        self.assertEqual(validate("who scored?", "Who scored in Arsenal vs Chelsea yesterday?", history, TEAMS),
                         "Who scored in Arsenal vs Chelsea yesterday?")

    def test_invented_entities_lists_new_teams_and_numbers(self):
        self.assertEqual(invented_entities("แล้วใครยิง", "เชลซีกับลิเวอร์พูลนัดที่ 7 ใครยิง",
                                           LIVERPOOL_TURN, TEAMS), ["Chelsea", "7"])
        self.assertEqual(invented_entities("แล้วใครยิง", "ใครยิงให้ลิเวอร์พูล", LIVERPOOL_TURN, TEAMS), [])
