import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from rooplan.agent import Agent
from rooplan.calendar import week_records
from rooplan.store import Store

NOW = datetime(2026, 11, 18, 13, 0)  # Wednesday
A = "周五下午 3 点在物理楼 302 开组会，每人汇报 10 分钟，周四晚上 8 点前交 PPT。"
B = "组会提前到周四上午 10 点，地点不变，PPT 改为会前提交。请重新安排一小时准备时间。"
THU = "2026-11-19T"
FRI = "2026-11-20T"


def call(name, **args):
    return dict(content=None,tool_calls=[dict(id="call_"+name,type="function",
                    function=dict(name=name,arguments=json.dumps(args,ensure_ascii=False)))])


class ScenarioModel:
    """Scripted model; tool outputs, IDs and slots come from the real database."""
    def __init__(self, reschedule=False):
        self.reschedule = reschedule
        self.names = []
        self.meeting = self.deadline = self.prep = None

    def complete(self, messages):
        previous = self.names[-1] if self.names else None
        result = json.loads(messages[-1]["content"]) if previous else None
        if not previous and self.reschedule:
            response = call("search_events",keyword="组会",kind="event")
        elif previous=="search_events":
            self.meeting = result[0]["id"]
            response = call("get_related_items",event_id=self.meeting)
        elif previous=="get_related_items":
            self.deadline = next(e["id"] for e in result if e["kind"]=="deadline")
            self.prep = next(e["id"] for e in result if e["kind"]=="prep")
            response = call("find_free_slots",earliest=THU+"08:00",deadline=THU+"10:00",
                            duration=60,exclude_ids=[self.prep])
        elif not previous:
            response = call("find_free_slots",earliest=THU+"16:00",deadline=THU+"20:00",duration=60)
        elif previous=="find_free_slots":
            slot = result[0]
            if self.reschedule:
                rows = [dict(id=self.meeting,fields=dict(start=THU+"10:00")),
                        dict(id=self.deadline,fields=dict(start=THU+"10:00",before_meeting=True,notes="会前提交"),
                             evidence="PPT 改为会前提交"),
                        dict(id=self.prep,fields=slot,suggested=True,evidence="重新安排一小时准备时间")]
            else:
                rows = [dict(ref="m",fields=dict(title="组会",start=FRI+"15:00",location="物理楼 302",
                                         notes="每人汇报 10 分钟")),
                        dict(ref="d",fields=dict(title="交 PPT",kind="deadline",start=THU+"20:00",parent="m")),
                        dict(ref="p",fields=dict(title="制作 PPT",kind="prep",parent="d",**slot),suggested=True)]
            response = call("propose_changes",changes=rows)
        else:
            raise AssertionError(result)
        self.names.append(response["tool_calls"][0]["function"]["name"])
        return response


class Scenarios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name)/"data.db")

    def first(self):
        key = self.store.new_draft(A)
        draft = Agent(self.store,ScenarioModel()).run(key,NOW)
        self.assertEqual(len(draft["rows"]),3)
        self.assertTrue(draft["rows"][2]["suggested"])
        self.assertFalse(self.store.all())
        self.store.confirm(key)
        self.store.confirm(key)
        return key

    def test_a_b_and_undo(self):
        self.first()
        old = self.store.all()
        idx = {e["kind"]:e for e in old.values()}
        self.assertEqual(idx["event"]["start"],FRI+"15:00")
        self.assertIsNone(idx["event"]["end"])
        self.assertIn("10 分钟",idx["event"]["notes"])
        self.assertEqual(idx["prep"]["start"],THU+"16:00")
        with self.store.session() as db:
            reminders = [tuple(r) for r in db.execute("SELECT * FROM reminders ORDER BY id")]
        model = ScenarioModel(True)
        b = self.store.new_draft(B)
        d = Agent(self.store,model).run(b,NOW)
        self.assertEqual(model.names, ["search_events","get_related_items","find_free_slots","propose_changes"])
        self.assertEqual(d["rows"][0]["before"]["location"],"物理楼 302")
        self.store.confirm(b)
        self.store.confirm(b)
        actual = self.store.all()
        self.assertEqual(set(actual),set(old))
        self.assertEqual(actual[idx["event"]["id"]]["location"],"物理楼 302")
        self.assertEqual(actual[idx["event"]["id"]]["start"],THU+"10:00")
        self.assertLessEqual(actual[idx["prep"]["id"]]["end"],THU+"10:00")
        with self.store.session() as db:
            self.assertEqual(db.execute("SELECT at FROM reminders WHERE id=?",
                (idx["event"]["id"],)).fetchone()[0],THU+"09:50")
        self.store.undo(b)
        self.assertEqual(old,self.store.all())
        with self.store.session() as db:
            self.assertEqual(reminders,[tuple(r) for r in db.execute("SELECT * FROM reminders ORDER BY id")])

    def test_repeating_creation_rolls_back_when_a_later_occurrence_conflicts(self):
        self.store.apply_manual([dict(fields=dict(title="实验", start="2026-11-27T10:30"))])
        baseline = self.store.all()
        fields = dict(title="组会", start="2026-11-20T10:00", end="2026-11-20T11:00")
        with self.assertRaisesRegex(ValueError, "时间冲突.*2026-11-27"):
            self.store.create_series(fields, 1, "2026-12-04")
        self.assertEqual(self.store.all(), baseline)
        self.assertFalse(self.store.pending())
        self.store.create_series(fields, 2, "2026-12-04")
        self.assertEqual([e["start"] for e in self.store.search_events("组会")],
                         ["2026-11-20T10:00", "2026-12-04T10:00"])
        self.store.undo()
        self.assertEqual(self.store.all(), baseline)

    def test_event_colors_survive_draft_confirmation_updates_recurrence_and_undo(self):
        self.store.apply_manual([dict(fields=dict(title="旧日程", start=THU+"09:00"))])
        legacy, = self.store.search_events("旧日程")
        self.assertNotIn("color", legacy)
        key = self.store.new_draft("实验通知")
        draft = self.store.propose_changes(key, [dict(fields=dict(title="核对数据", start=FRI+"16:00"))])
        ident = draft["rows"][0]["id"]
        with self.assertRaisesRegex(ValueError, "颜色"):
            self.store.edit(key, ident, {"color": "#abcdef"})
        self.store.edit(key, ident, {"color": "lilac"})
        self.store.confirm(key)
        self.store.apply_manual([dict(id=ident, fields=dict(done=True, start=FRI+"18:00"))])
        self.assertEqual(self.store.all()[ident]["color"], "lilac")
        self.store.apply_manual([dict(id=ident, fields=dict(color="blue"))])
        self.assertEqual(self.store.all()[ident]["color"], "blue")
        self.store.undo()
        self.assertEqual(self.store.all()[ident]["color"], "lilac")

        fields = dict(title="每周复盘", start=FRI+"20:00", color="rose")
        self.store.create_series(fields, 1, "2026-11-27")
        first, second = self.store.search_events("每周复盘")
        self.assertEqual((first["color"], second["color"]), ("rose", "rose"))
        self.store.apply_manual([dict(id=second["id"], fields=dict(color="auto"))])
        self.assertEqual([entry["color"] for entry in self.store.search_events("每周复盘")], ["rose", "auto"])

    def test_date_only_deadline_accepts_late_prep_and_optional_same_day_alert(self):
        self.store.apply_manual([
            dict(ref="due", fields=dict(title="交报告", kind="deadline", start="2026-11-20",
                                         reminder_time="09:00")),
            dict(fields=dict(title="核对报告", kind="prep", start="2026-11-20T22:00",
                             end="2026-11-21T00:00", parent="due", reminder=-1)),
            dict(fields=dict(title="缴费", kind="deadline", start="2026-11-20")),
        ])
        due, = self.store.search_events("交报告", "2026-11-20", "2026-11-20")
        self.assertFalse(self.store.search_events("交报告", "2026-11-21"))
        self.assertFalse(self.store.due_reminders(datetime(2026, 11, 20, 8, 59)))
        self.assertEqual(self.store.due_reminders(datetime(2026, 11, 20, 9)), [due])
        self.assertFalse(self.store.due_reminders(datetime(2026, 11, 21)))
        self.store.apply_manual([dict(id=due["id"], fields=dict(reminder_time="21:00"))])
        self.assertFalse(self.store.pending_reminders())
        self.store.undo()
        self.assertEqual(self.store.pending_reminders(), [due])

    def test_undoing_title_edit_preserves_subsequent_reminder_actions(self):
        self.store.apply_manual([dict(fields=dict(title="周会", start=FRI+"15:00"))])
        ident, = self.store.all()
        now = datetime.fromisoformat(FRI+"14:50")
        for action in ("delivered", "snoozed", "dismissed"):
            with self.subTest(action=action):
                self.store.apply_manual([dict(id=ident, fields=dict(title="课题组周会"))])
                if action == "delivered":
                    self.assertEqual(len(self.store.due_reminders(now)), 1)
                elif action == "snoozed":
                    self.store.handle_reminder(ident, FRI+"15:00:00")
                else:
                    self.store.handle_reminder(ident)
                self.store.undo()
                self.assertEqual(self.store.all()[ident]["title"], "周会")
                self.assertFalse(self.store.due_reminders(now))
                self.assertEqual(len(self.store.pending_reminders()), int(action == "delivered"))
                if action == "snoozed":
                    self.assertEqual(len(self.store.due_reminders(datetime.fromisoformat(FRI+"15:00"))), 1)

    def test_reminder_migration_preserves_older_undo_receipts(self):
        self.store.apply_manual([dict(fields=dict(title="组会", start=FRI+"15:00"))])
        entry, = self.store.all().values()
        self.store.apply_manual([dict(id=entry["id"], fields=dict(start=FRI+"16:00"))])
        with self.store.session(True) as db:
            db.execute("ALTER TABLE reminders DROP COLUMN snoozed_until")
            db.execute("UPDATE reminders SET fired=1")
            batch = db.execute("SELECT id,receipt FROM drafts ORDER BY applied_order DESC LIMIT 1").fetchone()
            receipt = json.loads(batch["receipt"])
            receipt[0]["old_reminder"].pop("snoozed_until")
            receipt[0]["old_reminder"]["fired"] = 1
            db.execute("UPDATE drafts SET receipt=? WHERE id=?", (json.dumps(receipt), batch["id"]))
        migrated = Store(self.store.path)
        self.assertFalse(migrated.pending_reminders())
        migrated.undo()
        self.assertEqual(migrated.all()[entry["id"]], entry)
        self.assertFalse(migrated.pending_reminders())
        self.assertFalse(migrated.due_reminders(datetime.fromisoformat(FRI+"17:00")))

    def test_notice_moves_only_the_meeting_preserves_duration_and_can_be_undone(self):
        self.first()
        meeting = next(item for item in self.store.all().values() if item["kind"] == "event")
        self.store.apply_manual([dict(id=meeting["id"], fields=dict(end=FRI+"16:30"))])
        originals = self.store.all()
        saturday = "2026-11-21T"

        class ChangeModel:
            def complete(self, messages):
                if messages[-1]["role"] == "user":
                    return call("search_events", keyword="组会", kind="event")
                original, = json.loads(messages[-1]["content"])
                return call("propose_changes", changes=[dict(id=original["id"],
                            fields=dict(start=saturday+"15:00"))])

        notice = "本周组会改到周六，地点不变，PPT 仍按原时间交。"
        key = self.store.new_draft(notice)
        draft = Agent(self.store, ChangeModel()).run(key, NOW)
        change, = draft["rows"]
        self.assertEqual(change["id"], meeting["id"])
        self.assertEqual(change["before"], originals[meeting["id"]])
        self.assertEqual(change["after"]["start"], saturday+"15:00")
        self.assertEqual(change["after"]["end"], saturday+"16:30")
        self.assertEqual(change["after"]["location"], meeting["location"])
        links = self.store.review(key)["relatedReview"]
        self.assertEqual({link["kind"] for link in links}, {"deadline", "prep"})
        self.assertTrue(all(not link["changed"] and not link["problem"] for link in links))
        self.store.confirm(key)
        self.assertEqual(self.store.all(), dict(originals, **{meeting["id"]: change["after"]}))
        again = self.store.new_draft(notice)
        duplicate = Agent(self.store, ChangeModel()).run(again, NOW)
        self.assertTrue(duplicate["already_recorded"])
        self.assertEqual(duplicate["rows"], [])
        self.store.undo(key)
        self.assertEqual(self.store.all(), originals)

    def test_duplicate_notice_flags_existing_items_and_rechecks_at_confirmation(self):
        fields = dict(title="提交 PPT", kind="deadline", start=FRI+"18:00")
        first, second = (self.store.new_draft(text) for text in ("交 PPT 通知", "转发交 PPT 通知"))
        original, = self.store.propose_changes(first, [dict(fields=fields)])["rows"]
        pending, = self.store.propose_changes(second, [dict(fields=dict(fields, title="提交 ＰＰＴ"))])["rows"]
        self.assertTrue(pending["selected"])
        self.store.confirm(first)
        self.assertEqual(self.store.review(second)["duplicates"][pending["id"]]["item"]["id"], original["id"])
        with self.assertRaisesRegex(ValueError, "重复项"):
            self.store.confirm(second)
        duplicate = self.store.propose_changes(second, [dict(fields=dict(fields, title="提交 ＰＰＴ"))], searched={})
        self.assertTrue(duplicate["already_recorded"])
        self.assertFalse(duplicate["rows"][0]["selected"])
        self.assertEqual(set(self.store.all()), {original["id"]})
        independent = dict(title="发材料给同学", start=FRI+"19:00")
        row, other = self.store.propose_changes(second, [dict(fields=fields), dict(fields=independent)])["rows"]
        self.assertFalse(row["selected"])
        self.assertTrue(other["selected"])
        self.assertEqual(self.store.confirm(second, keep_remaining=True), (1, 1))
        self.assertEqual(set(self.store.all()), {original["id"], other["id"]})
        self.store.edit(second, row["id"], selected=True)
        self.assertTrue(self.store.review(second)["duplicates"][row["id"]]["approved"])
        self.assertEqual(self.store.confirm(second, keep_remaining=True), (1, None))
        self.assertIn(row["id"], self.store.all())

    def test_agent_ignores_unsupported_linked_move_and_uses_calendar_dates_in_review(self):
        self.store.apply_manual([
            dict(ref="meeting", fields=dict(title="组会", start="2026-11-21T09:30", end="2026-11-21T10:30")),
            dict(fields=dict(title="提交材料", kind="deadline", start=FRI+"18:00", parent="meeting")),
        ])
        originals = self.store.all()
        meeting = next(item for item in originals.values() if item["kind"] == "event")
        deadline = next(item for item in originals.values() if item["kind"] == "deadline")
        notice = "原定周六的组会推迟到周日同一时间，地点改为305，材料提交要求不变。"

        class ChangeModel:
            def complete(self, messages):
                if messages[-1]["role"] == "user":
                    return call("search_events", keyword="组会", kind="event")
                return call("propose_changes", changes=[
                    dict(id=meeting["id"], fields=dict(start="2026-11-22T09:30", location="305")),
                    dict(id=deadline["id"], fields=dict(start="2026-11-21T18:00"),
                         evidence="材料提交要求不变"),
                ], note="材料提交改到周六 18:00，请确认。")

        key = self.store.new_draft(notice)
        draft = Agent(self.store, ChangeModel()).run(key, NOW)
        row, = draft["rows"]
        self.assertEqual(row["id"], meeting["id"])
        self.assertEqual(row["after"]["end"], "2026-11-22T10:30")
        self.assertFalse(draft["note"])
        linked, = self.store.review(key)["relatedReview"]
        self.assertEqual(linked["start"], FRI+"18:00")
        self.assertFalse(linked["changed"])
        self.assertEqual(self.store.all(), originals)
        self.store.confirm(key)
        self.assertEqual(self.store.all()[deadline["id"]], deadline)

    def test_selected_candidate_can_be_updated_without_another_search(self):
        self.store.apply_manual([
            dict(fields=dict(title="组会", start=FRI+"16:00", location="302")),
            dict(fields=dict(title="组会", start=FRI+"17:00", location="303")),
        ])
        chosen = next(item for item in self.store.all().values() if item["location"] == "303")

        class SelectedModel:
            calls = 0

            def complete(model, messages):
                model.calls += 1
                self.assertIn(chosen["id"], messages[-1]["content"][0]["text"])
                return call("propose_changes", changes=[dict(id=chosen["id"], fields=dict(location="401"))])

        model = SelectedModel()
        key = self.store.new_draft("组会改在401开。")
        row, = Agent(self.store, model).run(key, NOW, selected=chosen["id"])["rows"]
        self.assertEqual(model.calls, 1)
        self.assertEqual(row["before"], chosen)
        self.assertEqual(row["after"]["location"], "401")

    def test_conflict_after_review_rolls_back(self):
        key = self.store.new_draft(A)
        d = Agent(self.store,ScenarioModel()).run(key,NOW)
        other = self.store.new_draft("手动录入")
        self.store.propose_changes(other,[dict(fields=dict(title="临时工作",start=THU+"16:30"))])
        self.store.confirm(other)
        with self.assertRaisesRegex(ValueError,"时间冲突"):
            self.store.confirm(key)
        self.assertEqual(len(self.store.all()),1)
        self.store.edit(key,d["rows"][2]["id"],selected=False)
        self.store.confirm(key)
        self.assertEqual(len(self.store.all()),3)

    def test_rejects_unknown_reference_in_new_proposal(self):
        key = self.store.new_draft("交 PPT 通知")
        with self.assertRaisesRegex(ValueError, "关联项不存在"):
            self.store.propose_changes(key, [
                dict(ref="meeting", fields=dict(title="组会", start=FRI+"15:00")),
                dict(fields=dict(title="交 PPT", start=THU+"18:00", kind="deadline", parent="wrong-ref")),
            ])
        self.assertEqual(self.store.draft(key)["rows"], [])

    def test_deletion_requires_new_confirmation_if_related_items_changed(self):
        self.store.apply_manual([dict(fields=dict(title="组会", start=FRI+"15:00"))])
        prior = self.store.all()
        meeting, = prior
        self.store.apply_manual([dict(fields=dict(title="交材料", kind="deadline", parent=meeting,
                                                  start=THU+"18:00"))])
        current = self.store.all()
        with self.assertRaisesRegex(ValueError, "已变动"):
            self.store.delete_event(meeting, prior, delete_related=True)
        self.assertEqual(self.store.all(), current)

    def test_overlap_approval_is_rechecked_and_undo_restores_preexisting_overlap(self):
        self.store.apply_manual([dict(fields=dict(title="参观", start=FRI+"09:00", end=FRI+"11:00"))])
        visit, = self.store.all().values()
        key = self.store.new_draft("组会通知")
        meeting, = self.store.propose_changes(key, [
            dict(fields=dict(title="组会", start=FRI+"09:30", end=FRI+"10:30"))
        ])["rows"]
        ident = meeting["id"]
        conflict, = self.store.review(key)["conflicts"][ident]
        self.assertEqual((conflict["start"], conflict["end"]), (FRI+"09:30", FRI+"10:30"))
        self.store.approve_conflicts(key, ident, [conflict["token"]])
        self.store.apply_manual([dict(id=visit["id"], fields=dict(end=FRI+"10:00"))])
        self.assertFalse(self.store.review(key)["conflicts"][ident][0]["approved"])
        with self.assertRaisesRegex(ValueError, "时间冲突"):
            self.store.confirm(key)
        with self.assertRaisesRegex(ValueError, "时段有变化"):
            self.store.approve_conflicts(key, ident, [conflict["token"]])
        current, = self.store.review(key)["conflicts"][ident]
        self.store.approve_conflicts(key, ident, [current["token"]])
        self.store.confirm(key)
        self.store.apply_manual([dict(id=ident, fields=dict(location="302"))])
        self.store.undo()
        self.store.apply_manual([dict(id=ident, fields=dict(start=FRI+"11:00", end=FRI+"12:00"))])
        self.store.undo()
        self.assertEqual(self.store.all()[ident], meeting["after"])

    def test_partial_confirm_can_keep_a_note_and_undo_each_batch(self):
        key = self.store.new_draft("组会和另行通知的值班")
        first, = self.store.propose_changes(key, [dict(fields=dict(title="组会", start=FRI+"09:30"))],
                                            "值班时间待定")["rows"]
        self.assertEqual(self.store.confirm(key, keep_remaining=True, retain_note=True), (1, 0))
        reopened = Store(self.store.path)
        draft = reopened.review(key)
        self.assertEqual(draft["state"], "open")
        self.assertEqual(draft["note"], "值班时间待定")
        self.assertEqual([row["id"] for row in draft["confirmed"]], [first["id"]])
        self.assertEqual(draft["rows"], [])
        second = reopened.append_item(key, dict(title="值班", start=FRI+"14:30"))
        self.assertEqual(reopened.confirm(key, keep_remaining=True), (1, None))
        self.assertEqual(reopened.confirm(key, keep_remaining=True), (0, None))
        self.assertEqual(set(reopened.all()), {first["id"], second["id"]})
        reopened.undo()
        draft = reopened.review(key)
        self.assertEqual([row["id"] for row in draft["confirmed"]], [first["id"]])
        self.assertEqual([row["id"] for row in draft["rows"]], [second["id"]])
        reopened.undo()
        self.assertFalse(reopened.all())
        self.assertEqual({row["id"] for row in reopened.review(key)["rows"]}, {first["id"], second["id"]})

    def test_ambiguous_selection(self):
        self.first()
        other=self.store.new_draft("通知")
        self.store.propose_changes(other,[dict(fields=dict(title="组会二",start=FRI+"17:00"))])
        self.store.confirm(other)
        key=self.store.new_draft(B)
        d=Agent(self.store,ScenarioModel(True)).run(key,NOW)
        self.assertEqual(len(d["choices"]),2)
        with self.assertRaises(ValueError): self.store.confirm(key)
        chosen=next(e["id"] for e in d["choices"] if e["title"]=="组会")
        Agent(self.store,ScenarioModel(True)).run(key,NOW,selected=chosen)
        self.store.confirm(key)
        self.assertEqual(self.store.all()[chosen]["start"],THU+"10:00")

    def test_weekend_restart(self):
        k=self.store.new_draft("周末")
        self.store.propose_changes(k,[dict(fields=dict(title="周六活动",start="2026-11-21T11:00")),
            dict(fields=dict(title="周日提交",kind="deadline",start="2026-11-22T18:00"))])
        self.store.confirm(k)
        saved=Store(self.store.path).all()
        week=["2026-11-"+str(i) for i in range(16,23)]
        self.assertEqual([e["day"] for e in week_records(saved.values(),week)],[5,6])

    def test_manual_change_rejects_stale_records_and_undo_orders_legacy_batches(self):
        for number in range(3):
            self.store.apply_manual([dict(fields=dict(title=f"旧日程 {number}", start=FRI+f"{number+10}:00"))])
        with self.store.session(True) as db:
            db.execute("UPDATE drafts SET applied_order=NULL")
        original = next(iter(self.store.all().values()))
        ident = original["id"]
        self.store.apply_manual([dict(id=ident, fields=dict(start=FRI+"16:00"))])
        with self.assertRaisesRegex(ValueError, "编辑期间发生变化"):
            self.store.apply_manual([dict(id=ident, fields=dict(start=FRI+"17:00"))],
                                    originals={ident: original})
        self.assertEqual(self.store.all()[ident]["start"], FRI+"16:00")
        self.store.undo()
        self.assertEqual(self.store.all()[ident], original)
        self.assertEqual(len(self.store.all()), 3)

