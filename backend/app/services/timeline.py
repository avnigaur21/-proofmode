from typing import Any

from app.schemas.runs import ProofRun, TimelineEvent, TimelineLayer


class TimelineRecorder:
    def record(
        self,
        run: ProofRun,
        event_type: str,
        message: str,
        *,
        layer: TimelineLayer,
        status: str | None = None,
        evidence: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        run.timeline.append(
            TimelineEvent(
                type=event_type,
                layer=layer,
                status=status,
                message=message,
                evidence=evidence or {},
                metadata=metadata or {},
            )
        )
