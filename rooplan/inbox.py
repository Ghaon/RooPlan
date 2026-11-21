import json
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QImageReader

from .agent import Agent, QwenClient
from .store import cutoff, interval, stamp, uid
from .settings import AISettings


class Inbox(QObject):
    changed = Signal()
    busyChanged = Signal()
    finished = Signal(str)
    notice = Signal(str)
    ready = Signal(str)
    keyRequired = Signal()
    settingsChanged = Signal()
    stage = Signal(str)

    def __init__(self, store, folder, calendar, factory=None):
        super().__init__()
        self.store, self.folder, self.calendar = store, folder, calendar
        self.calendar.changed.connect(self.changed)
        self.factory = factory
        self.settings = AISettings(folder)
        self.client = QwenClient(base=self.settings.base, model=self.settings.model,
                                 key=self.settings.key, provider=self.settings.provider)
        self.status = ""
        self.stage.connect(self.set_stage)
        self.waiting = None
        self.queue = {}
        self.active_job = ""
        self.finished.connect(self.on_finished)

    @Property(bool, notify=busyChanged)
    def busy(self):
        return bool(self.active_job)

    @Property(str, notify=changed)
    def waitingDraftId(self):
        return self.waiting[0] if self.waiting else ""

    @Property(str, notify=busyChanged)
    def progress(self):
        return self.status

    @Slot(str)
    def set_stage(self, text):
        self.status = text
        self.busyChanged.emit()

    @Property("QVariantMap", notify=settingsChanged)
    def apiSettings(self):
        result = self.settings.public()
        result["hasKey"] = bool(self.client.key)
        return result

    @Slot(str, str, str, str, result=bool)
    def saveAPI(self, provider, base, model, key):
        if self.busy:
            self.notice.emit("请等待当前解析完成后再修改 API 设置。")
            return False
        try:
            self.settings.save(provider, base, model, key)
        except ValueError as exc:
            self.notice.emit(str(exc))
            return False
        self.client = QwenClient(base=self.settings.base, model=self.settings.model,
                                 key=self.settings.key, provider=self.settings.provider)
        self.settingsChanged.emit()
        pending, self.waiting = self.waiting, None
        if pending:
            self.run(*pending)
        self.notice.emit("API 设置已保存。")
        return True

    @Slot(result=bool)
    def clearAPIKey(self):
        if self.busy:
            return False
        try:
            self.settings.save(self.settings.provider, self.settings.base, self.settings.model, "", clear=True)
        except ValueError as exc:
            self.notice.emit(str(exc))
            return False
        self.client.key = ""
        self.settingsChanged.emit()
        return True

    @Slot()
    def cancelKeyRequest(self):
        if self.waiting:
            self.waiting = None
            self.queue.clear()
            self.changed.emit()
            self.notice.emit("通知已保存在草稿中，设置 API 后可重新解析。")

    def draft_status(self, draft):
        key = draft["id"]
        if key == self.active_job:
            return "解析中"
        if self.waiting and key == self.waiting[0]:
            return "待设置 API"
        if key in self.queue:
            return "排队中"
        if draft.get("failed"):
            return "解析失败"
        if draft.get("already_recorded"):
            return "已在日历"
        if draft["choices"] or any(row["after"] and not row["after"]["start"] for row in draft["rows"]):
            return "待补充"
        if draft["rows"]:
            return "待确认"
        return "待补充" if draft["note"] else "待解析"

    @Property("QVariantList", notify=changed)
    def pending(self):
        return [dict(d, status=self.draft_status(d)) for d in self.store.pending()]

    @Property(int, notify=changed)
    def pendingCount(self):
        return self.store.pending_count()

    @Slot(str, result="QVariantMap")
    def draft(self, key):
        d = self.store.review(key)
        d["status"] = self.draft_status(d)
        d["preview"] = QUrl.fromLocalFile(d["attachment"]).toString() if d["attachment"] else ""
        return d

    @staticmethod
    def screenshot(url):
        src = Path(QUrl(url).toLocalFile())
        reader = QImageReader(str(src))
        fmt = bytes(reader.format()).lower()
        if fmt not in (b"png", b"jpeg", b"jpg") or not reader.canRead() or src.stat().st_size > 10*1024**2:
            raise ValueError("请选择 10 MB 以内的 PNG 或 JPEG 截图。")
        return src, ".png" if fmt == b"png" else ".jpg"

    @Slot(str, result=bool)
    def isScreenshot(self, url):
        try:
            self.screenshot(url)
            return True
        except (ValueError, OSError) as exc:
            self.notice.emit(str(exc) if isinstance(exc, ValueError) else "无法读取截图，请重新选择。")
            return False

    @Slot(str, str, result=str)
    def saveNotice(self, text, url):
        path = None
        if url:
            try:
                path, filename = self.copy_screenshot(url)
                text = (text.strip()+"\n" if text.strip() else "")+"截图："+filename
            except (ValueError, OSError) as exc:
                self.notice.emit(str(exc) if isinstance(exc,ValueError) else "无法读取截图，请重新拖入。")
                return ""
        if not text.strip():
            self.notice.emit("请粘贴通知或拖入截图。")
            return ""
        try:
            key = self.store.new_draft(text.strip(), str(path) if path else None)
        except Exception:
            if path:
                path.unlink(missing_ok=True)
            raise
        self.changed.emit()
        return key

    def copy_screenshot(self, url):
        src, extension = self.screenshot(url)
        target = self.folder / "screenshots"
        target.mkdir(exist_ok=True)
        path = target / (uid() + extension)
        try:
            shutil.copyfile(src, path)
        except OSError:
            path.unlink(missing_ok=True)
            raise
        return path, src.name

    @Slot(str, str, str, result=bool)
    def replaceScreenshot(self, key, url, supplement):
        if self.locked(key):
            return False
        draft = self.store.review(key)
        if (draft["state"] != "open" or not draft["attachment"] or draft["rows"]
                or draft["choices"] or draft["confirmed"] or draft.get("already_recorded")):
            return False
        path = None
        try:
            path, _ = self.copy_screenshot(url)
            self.store.set_context(key, attachment=str(path), supplement=supplement)
        except (ValueError, OSError) as exc:
            if path:
                path.unlink(missing_ok=True)
            self.notice.emit(str(exc) if isinstance(exc, ValueError) else "截图未能保存，请重试。")
            return False
        self.changed.emit()
        self.notice.emit("截图已更换，可以重新解析。")
        return True

    @Slot(str, str, result=str)
    def submit(self, text, url):
        key = self.saveNotice(text, url)
        if key:
            self.run(key, "", "")
        return key

    @Slot(str, str, str, result=bool)
    def run(self, key, choice, supplement):
        if key == self.active_job or key in self.queue or (self.waiting and key == self.waiting[0]):
            return False
        d = self.store.review(key)
        if d["state"] != "open":
            return False
        if d["confirmed"]:
            self.notice.emit("这份通知已部分确认，请编辑或手动补充剩余事项。")
            return False
        if choice and choice not in {e["id"] for e in d["choices"]}:
            self.notice.emit("请选择列表中的候选活动。")
            return False
        self.store.set_context(key, supplement=supplement)
        if self.active_job or self.waiting:
            self.queue[key] = (key, choice, supplement)
            self.changed.emit()
            return True
        if self.factory is None and not self.client.key:
            self.waiting = (key, choice, supplement)
            self.changed.emit()
            self.keyRequired.emit()
            return True
        self.active_job = key
        self.status = "正在读取通知…"
        self.busyChanged.emit()
        self.changed.emit()

        def work():
            try:
                agent = self.factory(self.store) if self.factory else Agent(self.store, self.client)
                arguments = dict(selected=choice or None, image=d["attachment"], supplement=supplement)
                if not self.factory:
                    arguments["progress"] = self.stage.emit
                agent.run(key, **arguments)
            except ValueError as exc:
                self.store.annotate(key, str(exc), d["choices"], failed=True)
            except Exception:
                self.store.annotate(key, "解析未完成。请检查配置后重试，或手动补充草稿。", d["choices"], failed=True)
            finally:
                self.finished.emit(key)
        threading.Thread(target=work, daemon=True, name="RooPlan-Qwen").start()
        return True

    @Slot(str)
    def provideKey(self, value):
        if value.strip():
            self.saveAPI(self.settings.provider, self.settings.base, self.settings.model, value)
        else:
            self.cancelKeyRequest()

    @Slot(str)
    def on_finished(self, key):
        self.active_job = ""
        self.status = ""
        self.settingsChanged.emit()
        self.busyChanged.emit()
        self.changed.emit()
        draft = self.store.draft(key)
        status = self.draft_status(draft)
        if status == "解析失败":
            self.notice.emit("通知解析失败，原文已保存在草稿中，可重新解析或手动补充。")
        elif status == "已在日历":
            self.notice.emit("日历中已有这份安排。")
        elif status == "待补充":
            self.notice.emit("这份通知需要补充信息，请打开草稿核对。")
        else:
            self.notice.emit("通知已处理，可在草稿中核对。")
        self.ready.emit(key)
        if self.queue and (self.factory or self.client.key) and not self.active_job and not self.waiting:
            following = self.queue.pop(next(iter(self.queue)))
            self.run(*following)
        elif self.queue and not self.client.key:
            self.queue.clear()
            self.changed.emit()

    def locked(self, key):
        return key == self.active_job or key in self.queue or (self.waiting and key == self.waiting[0])

    @Slot(str, str, result="QVariantList")
    def alternatives(self, key, ident):
        draft = self.draft(key)
        row = next((row for row in draft["rows"] if row["id"] == ident), None)
        item = row["after"] if row else next((item for item in draft["relatedReview"] if item["id"] == ident), None)
        if not item or item["kind"] != "prep" or not item["start"] or not item["end"]:
            return []
        events = self.store.all()
        for selected in draft["rows"]:
            if selected["selected"]:
                if selected["after"] and selected["after"]["start"]:
                    events[selected["id"]] = selected["after"]
                elif selected["after"] is None:
                    events.pop(selected["id"], None)
        parent = events.get(item["parent"])
        try:
            start, end = interval(item)
            duration = int((end-start).total_seconds()/60)
            now = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=1)
            limit = stamp(max(now, start)+timedelta(days=7))
            latest = min(stamp(cutoff(parent)), limit) if parent else limit
            choices = self.store.find_free_slots(stamp(now), latest, duration, exclude_ids=[ident], events=events)
        except (ValueError, TypeError) as exc:
            self.notice.emit(str(exc))
            return []
        return [part for part in choices if part["start"] != item["start"]][:3]

    @Slot(str, str, str, result=bool)
    def edit(self, key, ident, fields):
        if self.locked(key):
            return False
        try:
            self.store.edit(key, ident, fields=json.loads(fields), allow_related=True)
            self.changed.emit()
            return True
        except (ValueError, TypeError) as exc:
            self.notice.emit(str(exc))
            return False

    @Slot(str, str, bool)
    def select(self, key, ident, yes):
        if self.locked(key):
            return
        self.store.edit(key,ident,selected=yes)
        self.changed.emit()

    @Slot(str, str, str, result=bool)
    def approveConflicts(self, key, ident, tokens):
        if self.locked(key):
            return False
        try:
            self.store.approve_conflicts(key, ident, json.loads(tokens))
            self.changed.emit()
            return True
        except (TypeError, ValueError) as exc:
            self.notice.emit(str(exc))
            return False

    @Slot(str, str, result=bool)
    def add(self, key, fields):
        if self.locked(key):
            return False
        try:
            self.store.append_item(key, json.loads(fields))
        except (ValueError, TypeError) as exc:
            self.notice.emit(str(exc))
            return False
        self.changed.emit()
        return True

    @Slot(str, result=bool)
    @Slot(str, str, bool, result=bool)
    def confirm(self, key, supplement=None, retain_note=False):
        if self.locked(key):
            return False
        try:
            count, remaining = self.store.confirm(key, keep_remaining=True, supplement=supplement,
                                                  retain_note=retain_note)
            if count:
                self.calendar.changed.emit()
                if remaining is None:
                    message = "已确认并更新提醒。"
                elif remaining:
                    message = f"已确认 {count} 项，剩余 {remaining} 项保存在草稿中。"
                else:
                    message = f"已确认 {count} 项，待补充说明保存在草稿中。"
                self.notice.emit(message)
            return True
        except (TypeError, ValueError) as exc:
            self.notice.emit(str(exc))
            return False

    @Slot(str)
    def discard(self, key):
        if self.locked(key):
            return
        self.store.discard(key)
        self.changed.emit()

