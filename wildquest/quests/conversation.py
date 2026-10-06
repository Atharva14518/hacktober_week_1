"""Maps interpreted speech onto allowed state-machine actions."""

from __future__ import annotations

from dataclasses import dataclass

from wildquest.quests.engine import EngineSnapshot, QuestEngine, QuestState
from wildquest.safety.incidents import IncidentHandler
from wildquest.story.intent import Intent, IntentParser


@dataclass(frozen=True)
class ConversationResult:
    intent: Intent
    snapshot: EngineSnapshot
    spoken_reply: str


class QuestConversation:
    def __init__(
        self,
        engine: QuestEngine,
        parser: IntentParser,
        incident_handler: IncidentHandler | None = None,
    ) -> None:
        self.engine = engine
        self.parser = parser
        self.incident_handler = incident_handler or IncidentHandler()

    def handle(self, speech: str) -> ConversationResult:
        incident = self.incident_handler.handle(speech)
        if incident is not None:
            before = self.engine.snapshot()
            if before.state in {
                QuestState.OFFERED,
                QuestState.ACTIVE,
                QuestState.VERIFYING,
            }:
                snapshot = self.engine.end(f"safety incident: {incident.incident.value}")
            else:
                snapshot = before
            return ConversationResult(Intent.STOP, snapshot, incident.spoken_instruction)
        intent = self.parser.parse(speech).intent
        before = self.engine.snapshot()
        if intent is Intent.DONE and before.state is QuestState.ACTIVE:
            snapshot = self.engine.request_verification()
            reply = "I heard that you are done. I will verify it now."
        elif intent is Intent.SKIP and before.state in {
            QuestState.OFFERED,
            QuestState.ACTIVE,
            QuestState.VERIFYING,
        }:
            snapshot = self.engine.skip()
            reply = "Quest skipped. Your safety comes first."
        elif intent in {Intent.TIRED, Intent.STOP} and before.state in {
            QuestState.OFFERED,
            QuestState.ACTIVE,
            QuestState.VERIFYING,
        }:
            snapshot = self.engine.end("user was tired or asked to stop")
            reply = "The quest ends here. Rest somewhere safe on the marked trail."
        elif intent is Intent.HINT and before.quest is not None:
            snapshot = before
            reply = before.quest.hint
        elif intent is Intent.REPEAT and before.quest is not None:
            snapshot = before
            reply = before.quest.prompt_seed
        else:
            snapshot = before
            reply = "I did not understand. Say done, skip, hint, repeat, tired, or stop."
        return ConversationResult(intent, snapshot, reply)
