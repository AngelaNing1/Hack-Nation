"""mcPHASES ingestion adapter: high-frequency streams to participant-days.

mcPHASES is longitudinal and credentialed-access. Its data are never committed
to this repository; the adapter operates on paths supplied at runtime.

The output unit is :class:`~schemas.temporal.ParticipantDay`, one row per
participant per day, with each feature carried as the
(value, is_observed, time_since_last_observed) triple the temporal model
expects. Days with no readings are still emitted so that the model can see the
gap rather than infer a dense series that never existed.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ingestion.base import BaseIngestionAdapter, file_checksum
from ingestion.mcphases.alignment import build_participant_days, date_range
from ingestion.mcphases.daily_aggregation import aggregate_day
from ingestion.mcphases.validation import (
    assert_use_permitted,
    validate_participant_days,
    validate_stream_columns,
)
from schemas.dataset import ProcessingManifest
from schemas.event import HormonalHealthEvent
from schemas.temporal import ParticipantDay

#: Stream column -> canonical variable code.
STREAM_COLUMN_MAP: dict[str, str] = {
    "glucose_mgdl": "cgm_mean_glucose",
    "heart_rate_bpm": "resting_heart_rate",
    "hrv_rmssd_ms": "hrv_rmssd",
    "skin_temp_c": "skin_temperature",
    "steps": "activity_steps",
    "sleep_hours": "sleep_duration_hours",
}

#: Expected readings per day per stream, used only for ``missing_fraction``.
EXPECTED_PER_DAY: dict[str, int] = {
    "cgm_mean_glucose": 288,  # 5-minute CGM sampling
    "resting_heart_rate": 288,
    "hrv_rmssd": 24,
    "skin_temperature": 288,
    "activity_steps": 24,
    "sleep_duration_hours": 1,
}


class McPhasesAdapter(BaseIngestionAdapter):
    """Builds participant-day tables from mcPHASES wearable and CGM streams."""

    dataset_id = "mcphases"
    adapter_version = "0.1.0"

    def __init__(
        self,
        *,
        dataset_version: str = "unversioned",
        use: str = "temporal_state_model",
    ) -> None:
        super().__init__(dataset_version=dataset_version)
        assert_use_permitted(use, self.dataset_id)
        self.use = use
        self.participant_days: list[ParticipantDay] = []

    # -- Lifecycle ----------------------------------------------------------

    def load_raw(self, source: Any) -> pd.DataFrame:
        """Load a long-format stream table with participant_id/timestamp columns."""
        if isinstance(source, pd.DataFrame):
            frame = source.copy()
        else:
            path = Path(source)
            self.file_checksums[path.name] = file_checksum(path)
            frame = pd.read_csv(path)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        self.n_source_records = len(frame)
        return frame

    def validate_raw(self, raw: pd.DataFrame) -> list[str]:
        errors = validate_stream_columns(list(raw.columns))
        if not any(c in raw.columns for c in STREAM_COLUMN_MAP):
            errors.append("Stream table contains no recognised measurement column.")
        self.validation_errors = errors
        return errors

    def transform(self, raw: pd.DataFrame) -> list[HormonalHealthEvent]:
        """Build participant-days; mcPHASES emits days, not point events.

        The event list is intentionally empty: mcPHASES is consumed by the
        temporal model as participant-days. Emitting one event per raw sample
        would flood the ledger with millions of device readings that no
        clinician will ever review.
        """
        self.participant_days = self.build_days(raw)
        self.n_events_emitted = 0
        return []

    def build_manifest(self) -> ProcessingManifest:
        return self.make_manifest()

    # -- Participant-day construction ---------------------------------------

    def build_days(
        self,
        raw: pd.DataFrame,
        *,
        menses_onsets: dict[str, list[date]] | None = None,
        cycle_lengths: dict[str, int] | None = None,
    ) -> list[ParticipantDay]:
        """Aggregate a stream table into participant-days.

        Args:
            raw: Long-format stream table.
            menses_onsets: Participant id -> recorded menses onset dates.
            cycle_lengths: Participant id -> typical cycle length in days.

        Returns:
            All participant-days across all participants, grouped by participant.
        """
        stream_columns = [c for c in STREAM_COLUMN_MAP if c in raw.columns]
        all_days: list[ParticipantDay] = []

        for participant, group in raw.groupby("participant_id"):
            scoped_id = f"{self.dataset_id}:{participant}"
            per_date: dict[date, dict[str, float | None]] = defaultdict(dict)
            days_present = sorted({ts.date() for ts in group["timestamp"]})

            for day in days_present:
                same_day = group[group["timestamp"].dt.date == day]
                stamps = [
                    ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
                    for ts in same_day["timestamp"]
                ]
                for column in stream_columns:
                    code = STREAM_COLUMN_MAP[column]
                    aggregate = aggregate_day(
                        code,
                        stamps,
                        list(same_day[column]),
                        expected_per_day=EXPECTED_PER_DAY.get(code),
                    )
                    if not aggregate.is_observed:
                        # No readings: leave every derived feature unset so the
                        # day is recorded as unobserved rather than zero-filled.
                        continue
                    per_date[day].update(aggregate.as_feature_dict())

            if not days_present:
                continue
            covered = date_range(days_present[0], days_present[-1])
            all_days.extend(
                build_participant_days(
                    scoped_id,
                    covered,
                    dict(per_date),
                    menses_onsets=(menses_onsets or {}).get(str(participant), ()),
                    cycle_length=(cycle_lengths or {}).get(str(participant)),
                    source_dataset=self.dataset_id,
                )
            )

        # Validate per participant: the series invariants (strictly increasing
        # dates, single participant) only hold within one participant's series.
        by_participant: dict[str, list[ParticipantDay]] = defaultdict(list)
        for day in all_days:
            by_participant[day.participant_id].append(day)
        for series in by_participant.values():
            self.warnings.extend(validate_participant_days(series))
        return all_days

    def run(
        self,
        source: Any,
        *,
        strict: bool = True,
        menses_onsets: dict[str, list[date]] | None = None,
        cycle_lengths: dict[str, int] | None = None,
    ) -> list[ParticipantDay]:
        """Load, validate and build participant-days in one call."""
        raw = self.load_raw(source)
        errors = self.validate_raw(raw)
        if errors and strict:
            raise ValueError("mcPHASES validation failed:\n" + "\n".join(errors))
        self.warnings.extend(errors)
        self.participant_days = self.build_days(
            raw, menses_onsets=menses_onsets, cycle_lengths=cycle_lengths
        )
        return self.participant_days

    def variable_mapping(self) -> dict[str, str]:
        return dict(STREAM_COLUMN_MAP)

    def excluded_source_columns(self) -> dict[str, str]:
        return {
            "device_id": "Device hardware identifier; not a person-level observation.",
            "timestamp": "Used for alignment, not emitted as a variable.",
            "participant_id": "Identifier, scoped by dataset rather than emitted.",
        }


#: Filenames accepted as the stream table inside an mcPHASES root directory.
STREAM_FILE_CANDIDATES: tuple[str, ...] = ("streams.csv", "mcphases_streams.csv", "raw_streams.csv")


class McPhasesDataNotFoundError(FileNotFoundError):
    """Raised when the mcPHASES dataset is absent, with actionable guidance.

    mcPHASES is credentialed-access and is never committed. Callers get the
    expected path and the environment variable to set rather than a bare
    traceback, because "file not found" three frames deep in pandas tells a user
    nothing about what they were supposed to have downloaded.
    """


def _stream_files(root: Path) -> list[Path]:
    """Find the stream table(s) under an mcPHASES root."""
    if root.is_file():
        return [root]
    found = [root / name for name in STREAM_FILE_CANDIDATES if (root / name).exists()]
    if found:
        return found
    return sorted(root.glob("*.csv"))


def load_participant_days(
    root: str | Path,
    *,
    strict: bool = True,
    use: str = "temporal_state_model",
    dataset_version: str = "unversioned",
    menses_onsets: dict[str, list[date]] | None = None,
    cycle_lengths: dict[str, int] | None = None,
) -> list[ParticipantDay]:
    """Load an mcPHASES root directory into participant-days.

    This is the module-level entry point the training and preparation scripts
    use. It wraps :class:`McPhasesAdapter` so that callers who only want the
    participant-day list do not have to know the adapter's lifecycle.

    Args:
        root: Directory holding the mcPHASES stream tables, or a single CSV.
        strict: Raise on validation errors instead of recording them as warnings.
        use: Declared use, checked against the dataset registry. Fails closed.
        dataset_version: Version string recorded in the processing manifest.
        menses_onsets: Participant id -> recorded menses onset dates.
        cycle_lengths: Participant id -> typical cycle length in days.

    Returns:
        Every participant-day across every stream table found under ``root``.

    Raises:
        McPhasesDataNotFoundError: If ``root`` does not exist or holds no CSV.
    """
    path = Path(root).expanduser()
    if not path.exists():
        raise McPhasesDataNotFoundError(
            f"mcPHASES dataset not found at: {path}\n"
            "mcPHASES requires credentialed PhysioNet access and is never committed to "
            "this repository.\n"
            "Obtain it under its own access terms, store it outside the repository tree, "
            "then either set PRISM_DATA_ROOT (and export it — nothing auto-loads .env), "
            "pass --data-root, or set `data.root` in configs/data/mcphases.yaml."
        )

    files = _stream_files(path)
    if not files:
        raise McPhasesDataNotFoundError(
            f"mcPHASES root '{path}' exists but contains no stream table.\n"
            f"Expected one of {', '.join(STREAM_FILE_CANDIDATES)} or any *.csv file."
        )

    days: list[ParticipantDay] = []
    for file in files:
        adapter = McPhasesAdapter(dataset_version=dataset_version, use=use)
        days.extend(
            adapter.run(
                file,
                strict=strict,
                menses_onsets=menses_onsets,
                cycle_lengths=cycle_lengths,
            )
        )
    return days


def to_frame(days: list[ParticipantDay]) -> pd.DataFrame:
    """Flatten participant-days into a wide DataFrame for inspection."""
    rows: list[dict[str, Any]] = []
    for day in days:
        row: dict[str, Any] = {
            "participant_id": day.participant_id,
            "study_day": day.study_day,
            "calendar_date": day.calendar_date,
            "cycle_day": day.cycle_day,
            "cycle_phase": day.cycle_phase,
        }
        for name, value in day.values.items():
            row[name] = value
            row[f"{name}__is_observed"] = day.is_observed.get(name, False)
            row[f"{name}__time_since_last_observed"] = day.time_since_last_observed.get(name)
        rows.append(row)
    return pd.DataFrame(rows)


def _as_datetime(value: Any) -> datetime:
    return value if isinstance(value, datetime) else pd.Timestamp(value).to_pydatetime()
