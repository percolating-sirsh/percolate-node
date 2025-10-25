"""Audio transcription using faster-whisper for local processing.

Based on carrier audio patterns with local-first approach.
Falls back to OpenAI Whisper API if configured.
"""

import json
from pathlib import Path
from typing import Callable
from uuid import UUID

from faster_whisper import WhisperModel
from loguru import logger

from percolate_reading.models.parse import (
    ParseContent,
    ParseQuality,
    ParseResult,
    ParseStorage,
    StorageStrategy,
)
from percolate_reading.providers.base import ParseProvider
from percolate_reading.settings import settings
from percolate_reading.storage.manager import StorageManager


class AudioProvider(ParseProvider):
    """Audio transcription provider using faster-whisper.

    Features:
    - Local Whisper model (no API calls)
    - Automatic language detection
    - Timestamp segments
    - Speaker diarization (future)

    Performance:
    - ~1x realtime on CPU
    - ~10x realtime on GPU
    """

    def __init__(self, storage_manager: StorageManager):
        """Initialize Audio provider.

        Args:
            storage_manager: Storage manager for artifacts
        """
        super().__init__(storage_manager)
        self._model: WhisperModel | None = None

    @property
    def supported_types(self) -> list[str]:
        """Supported MIME types."""
        return [
            "audio/mpeg",  # .mp3
            "audio/wav",  # .wav
            "audio/x-wav",  # .wav (alternative)
            "audio/x-m4a",  # .m4a
            "audio/ogg",  # .ogg
            "audio/flac",  # .flac
        ]

    @property
    def provider_name(self) -> str:
        """Provider name."""
        return "whisper_local"

    def _get_model(self) -> WhisperModel:
        """Get or create Whisper model instance.

        Returns:
            WhisperModel instance
        """
        if self._model is None:
            logger.info("Loading Whisper model (base)...")
            self._model = WhisperModel(
                "base",
                device=settings.device,
                compute_type="int8" if settings.device == "cpu" else "float16",
                download_root=settings.model_cache_dir,
            )
            logger.info("Whisper model loaded")
        return self._model

    async def _parse(
        self,
        file_path: Path,
        job_id: UUID,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> ParseResult:
        """Transcribe audio using faster-whisper.

        Args:
            file_path: Path to audio file
            job_id: Job ID for artifact storage
            progress_callback: Optional progress callback

        Returns:
            ParseResult with transcription and metadata

        Raises:
            Exception: On transcription failure
        """
        if progress_callback:
            progress_callback(0.1, "Loading Whisper model")

        model = self._get_model()

        if progress_callback:
            progress_callback(0.2, "Transcribing audio")

        # Transcribe
        try:
            segments, info = model.transcribe(
                str(file_path),
                beam_size=5,
                vad_filter=True,  # Voice activity detection
                word_timestamps=False,  # Faster without word-level timestamps
            )

            # Collect segments
            transcript_lines: list[str] = []
            segment_data: list[dict] = []

            for segment in segments:
                # Format timestamp
                start_time = self._format_timestamp(segment.start)
                end_time = self._format_timestamp(segment.end)

                # Add to transcript
                transcript_lines.append(
                    f"[{start_time} → {end_time}] {segment.text.strip()}"
                )

                # Store segment metadata
                segment_data.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                })

            full_transcript = "\n\n".join(transcript_lines)

            logger.info(
                f"Transcribed audio: {info.language} "
                f"({len(segment_data)} segments, "
                f"{info.duration:.1f}s duration)"
            )

        except Exception as e:
            raise Exception(f"Transcription failed: {e}")

        if progress_callback:
            progress_callback(0.8, "Building parse result")

        # Create storage info
        storage = ParseStorage(
            strategy=self._current_job.storage_strategy if self._current_job else StorageStrategy.DATED,
            base_path=str(self.get_job_path(job_id)),
            artifacts={
                "transcript": "transcript.txt",
                "segments": "segments.json",
                "metadata": "metadata.json",
            },
        )

        # Create content stats
        content = ParseContent(
            text_length=len(full_transcript),
            num_tables=0,
            num_images=0,
            num_pages=1,
            languages=[info.language],
        )

        # Quality assessment based on language probability
        quality = ParseQuality(
            overall_score=min(info.language_probability, 1.0),
            flags=[],
        )

        # Create result
        result = ParseResult(
            file_name=file_path.name,
            file_type="audio/mpeg",  # Generic
            file_size_bytes=file_path.stat().st_size,
            parse_duration_ms=0,  # Will be set by base provider
            storage=storage,
            content=content,
            quality=quality,
            warnings=[],
        )

        # Store transcription data
        result._transcript = full_transcript  # type: ignore
        result._segments = segment_data  # type: ignore
        result._audio_info = {
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
        }  # type: ignore

        if progress_callback:
            progress_callback(0.9, "Writing artifacts")

        # Store artifacts
        await self._store_artifacts(result, job_id, progress_callback)

        if progress_callback:
            progress_callback(1.0, "Transcription complete")

        return result

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as MM:SS timestamp.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted timestamp
        """
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    async def _store_artifacts(
        self,
        result: ParseResult,
        job_id: UUID,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> None:
        """Store transcription artifacts.

        Args:
            result: ParseResult with transcription
            job_id: Job ID for storage path
            progress_callback: Optional progress callback
        """
        # Get data from private attributes
        transcript = getattr(result, "_transcript", "")
        segments = getattr(result, "_segments", [])
        audio_info = getattr(result, "_audio_info", {})

        # Write transcript (uses job context automatically)
        transcript_path = self.write_artifact(job_id, "transcript.txt", transcript)
        logger.debug(f"Wrote transcript.txt: {transcript_path}")

        # Write segments
        segments_path = self.write_artifact(
            job_id, "segments.json", json.dumps(segments, indent=2)
        )
        logger.debug(f"Wrote segments.json: {segments_path}")

        # Write metadata
        metadata = {
            "file_name": result.file_name,
            "file_size_bytes": result.file_size_bytes,
            "audio_info": audio_info,
            "segment_count": len(segments),
        }
        metadata_path = self.write_artifact(
            job_id, "metadata.json", json.dumps(metadata, indent=2)
        )
        logger.debug(f"Wrote metadata.json: {metadata_path}")
