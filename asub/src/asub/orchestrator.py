from __future__ import annotations

import errno
import logging
import math
import shutil
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any

from . import media
from .discovery import discover_inputs
from .exceptions import AsubError, UnsupportedLanguageError, WorkerError
from .languages import aligner_name, normalize_language, parse_targets, source_language_from_probe
from .logging_config import configure_logging
from .models import CaptionSegment, JobMetadata, ProcessingOptions, WordTimestamp
from .paths import safe_stem, unique_dir
from .subtitles import validate_segments, write_subtitles
from .workers.ipc import PersistentWorkerClient, WorkerClient

ASR_MODEL = "Qwen/Qwen3-ASR-1.7B"
MT_MODEL = "tencent/Hunyuan-MT-Chimera-7B"
ALIGN_MODEL = "Qwen/Qwen3-ForcedAligner-0.6B"


def _replace_file(source: Path, target: Path) -> None:
    try:
        source.replace(target)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
    temporary = target.with_name(f".{target.name}.asub-tmp")
    temporary.unlink(missing_ok=True)
    shutil.copy2(source, temporary)
    temporary.replace(target)
    source.unlink()


class Pipeline:
    def __init__(
        self,
        options: ProcessingOptions,
        *,
        asr_client: WorkerClient | None = None,
        mt_client: WorkerClient | None = None,
        align_client: WorkerClient | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.options = options
        self.asr_client = asr_client or PersistentWorkerClient("qwen_asr", "asub.workers.qwen_asr_worker")
        self.mt_client = mt_client or WorkerClient("mt", "asub.workers.mt_worker")
        self.align_client = align_client or WorkerClient("align", "asub.workers.align_worker")
        self.log = logger or configure_logging(verbose=False)

    def process_inputs(self, inputs: list[str | Path]) -> list[JobMetadata]:
        videos = discover_inputs(inputs)
        if not videos:
            raise AsubError("No supported video inputs found.")
        max_workers = max(1, min(int(self.options.jobs), len(videos)))
        if max_workers == 1:
            return [self.process_video(video) for video in videos]

        jobs: list[JobMetadata | None] = [None] * len(videos)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._process_video_isolated, video): idx
                for idx, video in enumerate(videos)
            }
            for future, idx in futures.items():
                jobs[idx] = future.result()
        return [job for job in jobs if job is not None]

    def _process_video_isolated(self, video: Path) -> JobMetadata:
        pipeline = Pipeline(
            self.options,
            asr_client=self.asr_client,
            mt_client=self.mt_client,
            align_client=self.align_client,
            logger=self.log,
        )
        return pipeline.process_video(video)

    def process_video(self, video: Path) -> JobMetadata:
        job = self._prepare_job(video)
        self.log = configure_logging(job.log_path)
        if job.status.get("job") == "failed":
            job.errors = []
            job.status["job"] = "running"
        job.models = {"asr": self.options.asr_model, "translation": self.options.translation_model, "alignment": self.options.alignment_model}
        job.options = self.options.model_dump()
        job.target_languages = parse_targets(self.options.target_languages) if self.options.target_languages else []
        job.source_language = normalize_language(self.options.source_language, allow_auto=True)
        job.save()

        try:
            if self.options.in_place and not self.options.mux:
                raise AsubError("In-place output requires muxing to be enabled.")
            self._probe(job)
            self._extract_audio(job)
            self._transcribe(job)
            if self.options.align or job.target_languages:
                self._release_asr_worker()
            if self.options.align:
                self._align(job)
            self._translate(job)
            self._write_subtitles(job)
            if self.options.mux:
                self._mux(job)
            if self.options.burn:
                self._burn(job)
            if self.options.in_place:
                self._install_in_place(job)
            job.status["job"] = "completed"
            if self.options.cleanup:
                self._cleanup(job)
        except Exception as exc:
            job.status["job"] = "failed"
            job.errors.append(str(exc))
            job.save()
            raise
        if not (self.options.cleanup and self.options.in_place):
            job.save()
        return job

    def _prepare_job(self, video: Path) -> JobMetadata:
        base = self.options.output_dir.resolve(strict=False)
        stem = safe_stem(video)
        out_dir = base / stem
        if out_dir.exists() and not self.options.resume:
            out_dir = unique_dir(base, stem)
        work = out_dir / "work"
        subtitles = out_dir / "subtitles"
        rendered = out_dir / "video"
        logs = out_dir / "logs"
        for directory in [work, subtitles, rendered, logs]:
            directory.mkdir(parents=True, exist_ok=True)
        metadata_path = out_dir / "metadata.json"
        if metadata_path.exists() and self.options.resume:
            return JobMetadata.load(metadata_path)
        return JobMetadata(
            input_path=video.resolve(strict=False),
            output_dir=out_dir,
            work_dir=work,
            subtitle_dir=subtitles,
            video_dir=rendered,
            log_path=logs / "asub.log",
            metadata_path=metadata_path,
        )

    def _stage_done(self, job: JobMetadata, name: str) -> bool:
        return self.options.resume and self.options.skip_existing and job.status.get(name) == "completed"

    def _probe(self, job: JobMetadata) -> None:
        if self._stage_done(job, "probe") and job.ffprobe:
            if job.source_language == "auto":
                hinted = source_language_from_probe(job.ffprobe)
                if hinted:
                    job.source_language = hinted
                    if f"Using audio stream language tag as source language: {hinted}" not in job.warnings:
                        job.warnings.append(f"Using audio stream language tag as source language: {hinted}")
                    job.save()
            return
        job.ffprobe = media.ffprobe_json(job.input_path, log=self.log)
        if job.source_language == "auto":
            hinted = source_language_from_probe(job.ffprobe)
            if hinted:
                job.source_language = hinted
                job.warnings.append(f"Using audio stream language tag as source language: {hinted}")
        job.status["probe"] = "completed"
        job.save()

    def _extract_audio(self, job: JobMetadata) -> None:
        audio = job.work_dir / "audio.wav"
        if self._stage_done(job, "audio") and audio.exists():
            job.extracted_audio = audio
            return
        job.extracted_audio = media.extract_audio(job.input_path, audio, sample_rate=self.options.audio_sample_rate, overwrite=self.options.overwrite, log=self.log)
        job.status["audio"] = "completed"
        job.save()

    def _transcribe(self, job: JobMetadata) -> None:
        if self._stage_done(job, "asr") and job.segments:
            return
        duration = media.media_duration_seconds(job.ffprobe) or 0
        use_chunks = self.options.chunk_mode == "always" or (self.options.chunk_mode == "auto" and duration > 3600)
        if use_chunks and job.extracted_audio:
            segments, detected = self._transcribe_chunked(job, duration)
        else:
            response = self.asr_client.call(
                {
                    "audio": str(job.extracted_audio),
                    "source_language": job.source_language,
                    "device": self.options.device,
                    "dtype": self.options.dtype,
                    "chunk_mode": self.options.chunk_mode,
                    "model": self.options.asr_model,
                    "alignment_model": self.options.alignment_model,
                    "return_time_stamps": True,
                    "duration": duration,
                    "asr_max_new_tokens": self.options.asr_max_new_tokens,
                    "asr_max_batch_size": self.options.asr_max_batch_size,
                    "asr_max_model_len": self.options.asr_max_model_len,
                    "asr_gpu_memory_utilization": self.options.asr_gpu_memory_utilization,
                }
            )
            segments = [CaptionSegment.model_validate(seg) for seg in response.get("segments", [])]
            detected = response.get("detected_language")
            job.warnings.extend(response.get("warnings", []))
        job.segments = self._reindex(segments)
        job.detected_language = detected or (None if job.source_language == "auto" else job.source_language)
        job.status["asr"] = "completed"
        job.save()

    def _transcribe_chunked(self, job: JobMetadata, duration: float) -> tuple[list[CaptionSegment], str | None]:
        assert job.extracted_audio is not None
        chunk_len = 55 * 60
        overlap = 8.0
        starts = []
        cursor = 0.0
        while cursor < duration:
            starts.append(cursor)
            cursor += chunk_len - overlap
        all_segments: list[CaptionSegment] = []
        detected: str | None = None
        chunk_paths: list[Path] = []
        chunk_lengths: list[float] = []
        chunk_starts: list[float] = []
        for idx, start in enumerate(starts):
            length = min(chunk_len, duration - start)
            chunk_path = job.work_dir / "chunks" / f"audio_{idx:03}.wav"
            media.extract_audio_chunk(job.extracted_audio, chunk_path, start=start, duration=length, log=self.log)
            chunk_paths.append(chunk_path)
            chunk_lengths.append(length)
            chunk_starts.append(start)

        response = self.asr_client.call(
            {
                "audio": [str(path) for path in chunk_paths],
                "source_language": job.source_language,
                "device": self.options.device,
                "dtype": self.options.dtype,
                "model": self.options.asr_model,
                "alignment_model": self.options.alignment_model,
                "return_time_stamps": True,
                "durations": chunk_lengths,
                "asr_max_new_tokens": self.options.asr_max_new_tokens,
                "asr_max_batch_size": self.options.asr_max_batch_size,
                "asr_max_model_len": self.options.asr_max_model_len,
                "asr_gpu_memory_utilization": self.options.asr_gpu_memory_utilization,
            }
        )
        results = response.get("results")
        if not isinstance(results, list):
            results = [response]
        for start, item in zip(chunk_starts, results):
            detected = detected or item.get("detected_language")
            job.warnings.extend(item.get("warnings", []))
            for raw in item.get("segments", []):
                seg = CaptionSegment.model_validate(raw)
                seg.start += start
                seg.end += start
                if seg.asr_start is not None:
                    seg.asr_start += start
                if seg.asr_end is not None:
                    seg.asr_end += start
                for word in seg.words:
                    word.start += start
                    word.end += start
                all_segments.append(seg)
        return self._dedupe_segments(sorted(all_segments, key=lambda s: (s.start, s.end))), detected

    def _dedupe_segments(self, segments: list[CaptionSegment]) -> list[CaptionSegment]:
        output: list[CaptionSegment] = []
        for segment in segments:
            if output and abs(output[-1].start - segment.start) < 2.0 and output[-1].text.strip().casefold() == segment.text.strip().casefold():
                continue
            if output and segment.start < output[-1].end and segment.text.strip().casefold() in output[-1].text.strip().casefold():
                continue
            output.append(segment)
        return output

    def _release_asr_worker(self) -> None:
        close = getattr(self.asr_client, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _segments_have_alignment(segments: list[CaptionSegment]) -> bool:
        return bool(segments) and all(
            segment.aligned_start is not None
            and segment.aligned_end is not None
            and bool(segment.words)
            for segment in segments
        )

    def _align(self, job: JobMetadata) -> None:
        if self._stage_done(job, "align"):
            return
        if self._segments_have_alignment(job.segments):
            job.status["align"] = "completed"
            job.save()
            return
        source = job.detected_language or job.source_language or "auto"
        language = aligner_name(source)
        if not language:
            job.warnings.append(f"Forced alignment is unsupported for source language {source}; keeping ASR timings.")
            job.status["align"] = "skipped"
            job.save()
            return
        try:
            response = self.align_client.call(
                {
                    "audio": str(job.extracted_audio),
                    "segments": [s.model_dump() for s in job.segments],
                    "language": language,
                    "device": self.options.device,
                    "dtype": self.options.dtype,
                    "model": self.options.alignment_model,
                }
            )
            job.segments = [CaptionSegment.model_validate(seg) for seg in response.get("segments", [])]
            job.status["align"] = "completed"
        except WorkerError as exc:
            job.warnings.append(f"Forced alignment failed; keeping ASR timings. {exc}")
            job.status["align"] = "failed_continued"
        job.save()

    def _translate(self, job: JobMetadata) -> None:
        if self._stage_done(job, "translation") and all(target in job.translations for target in job.target_languages):
            return
        source = normalize_language(job.detected_language or job.source_language or "auto", allow_auto=True)
        if source == "auto":
            source = "en"
            job.warnings.append("Source language was not detected; defaulting translation source label to English.")
        for target in job.target_languages:
            if target == source:
                job.translations[target] = deepcopy(job.segments)
                continue
            response = self.mt_client.call(
                {
                    "segments": [s.model_dump() for s in job.segments],
                    "source_language": source,
                    "target_language": target,
                    "device": self.options.device,
                    "dtype": self.options.dtype,
                    "model": self.options.translation_model,
                }
            )
            job.translations[target] = [CaptionSegment.model_validate(seg) for seg in response.get("segments", [])]
        job.status["translation"] = "completed"
        job.save()

    def _write_subtitles(self, job: JobMetadata) -> None:
        expected_languages = [normalize_language(job.detected_language or job.source_language or "en", allow_auto=True)]
        expected_languages.extend(job.translations.keys())
        if self._stage_done(job, "subtitles") and all(
            any(key.startswith(f"{lang}.") for key in job.generated_files) for lang in expected_languages
        ):
            return
        basename = safe_stem(job.input_path)
        source_code = normalize_language(job.detected_language or job.source_language or "en", allow_auto=True)
        if source_code == "auto":
            source_code = "source"
        for fmt, path in write_subtitles(job.segments, job.subtitle_dir, basename, source_code, self.options).items():
            job.generated_files[f"{source_code}.{fmt}"] = str(path)
        for lang, segments in job.translations.items():
            for fmt, path in write_subtitles(segments, job.subtitle_dir, basename, lang, self.options).items():
                job.generated_files[f"{lang}.{fmt}"] = str(path)
        job.status["subtitles"] = "completed"
        job.save()

    def _mux(self, job: JobMetadata) -> None:
        if self._stage_done(job, "mux"):
            return
        subtitle_tracks = []
        for key, value in job.generated_files.items():
            if key.endswith(".srt"):
                subtitle_tracks.append((Path(value), key.rsplit(".", 1)[0]))
        if not subtitle_tracks:
            raise AsubError("Mux requested but no SRT subtitle tracks were generated.")
        output = job.video_dir / f"{safe_stem(job.input_path)}.subtitled.mp4"
        media.mux_subtitles(job.input_path, subtitle_tracks, output, overwrite=self.options.overwrite, log=self.log)
        job.generated_files["mux.mp4"] = str(output)
        job.status["mux"] = "completed"
        job.save()

    def _install_in_place(self, job: JobMetadata) -> None:
        muxed = job.generated_files.get("mux.mp4")
        if not muxed:
            raise AsubError("In-place output requested but no muxed MP4 was generated.")
        source = Path(muxed)
        target = job.input_path.with_suffix(".mp4")
        target.parent.mkdir(parents=True, exist_ok=True)
        _replace_file(source, target)
        if job.input_path.suffix.lower() != ".mp4" and job.input_path.exists():
            job.input_path.unlink()
        job.generated_files["mux.mp4"] = str(target)
        job.generated_files["in_place.mp4"] = str(target)
        job.status["in_place"] = "completed"
        job.save()

    def _cleanup(self, job: JobMetadata) -> None:
        job.status["cleanup"] = "completed"
        for handler in list(self.log.handlers):
            handler.close()
            self.log.removeHandler(handler)
        if self.options.in_place:
            job.save()
            shutil.rmtree(job.output_dir, ignore_errors=True)
            return
        shutil.rmtree(job.work_dir, ignore_errors=True)
        shutil.rmtree(job.log_path.parent, ignore_errors=True)
        job.save()

    def _burn(self, job: JobMetadata) -> None:
        if self._stage_done(job, "burn"):
            return
        ass_files = [(key.rsplit(".", 1)[0], Path(value)) for key, value in job.generated_files.items() if key.endswith(".ass")]
        if not ass_files:
            raise AsubError("Burn requested but no ASS subtitle files were generated.")
        for lang, ass in ass_files:
            output = job.video_dir / f"{safe_stem(job.input_path)}.{lang}.burned.mp4"
            media.burn_subtitles(job.input_path, ass, output, encoder=self.options.encoder, preset=self.options.preset, cq=self.options.cq, overwrite=self.options.overwrite, log=self.log)
            job.generated_files[f"burn.{lang}"] = str(output)
        job.status["burn"] = "completed"
        job.save()

    @staticmethod
    def _reindex(segments: list[CaptionSegment]) -> list[CaptionSegment]:
        normalized = []
        for idx, segment in enumerate(sorted(segments, key=lambda s: (s.start, s.end)), start=1):
            segment.index = idx
            if segment.asr_start is None:
                segment.asr_start = segment.start
            if segment.asr_end is None:
                segment.asr_end = segment.end
            normalized.append(segment)
        validate_segments(normalized)
        return normalized


def translate_existing(job_path: Path, targets: list[str], options: ProcessingOptions) -> JobMetadata:
    metadata = job_path / "metadata.json" if job_path.is_dir() else job_path
    job = JobMetadata.load(metadata)
    options.target_languages = targets
    job.target_languages = targets
    pipeline = Pipeline(options)
    pipeline._translate(job)
    pipeline._write_subtitles(job)
    return job
