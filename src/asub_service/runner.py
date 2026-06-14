from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from asub.models import ProcessingOptions
from asub.orchestrator import Pipeline

from .config import ServiceConfig
from .jobs import JobRequest
from .sidecars import missing_languages


class AsubPipelineRunner:
    async def run(self, request: JobRequest, config: ServiceConfig) -> list[Path]:
        return await asyncio.to_thread(self.run_sync, request, config)

    def run_sync(self, request: JobRequest, config: ServiceConfig) -> list[Path]:
        media_path = request.media_path.resolve(strict=False)
        targets = missing_languages(
            media_path,
            request.target_languages,
            existing_languages=request.existing_languages,
            formats=config.subtitle_formats,
        )
        if not targets:
            return []

        options = ProcessingOptions(
            output_dir=config.work_dir / media_path.stem,
            asr_model=config.asr_model,
            translation_model=config.translation_model,
            alignment_model=config.alignment_model,
            target_languages=targets,
            formats=config.subtitle_formats,
            align=True,
            mux=False,
            burn=False,
            in_place=False,
            cleanup=True,
            overwrite=True,
            device=config.device,
            dtype=config.dtype,  # type: ignore[arg-type]
            asr_gpu_memory_utilization=config.gpu_memory_utilization,
            jobs=max(1, config.max_concurrent_asr),
        )
        job = Pipeline(options).process_video(media_path)
        outputs: list[Path] = []
        for language in targets:
            for fmt in config.subtitle_formats:
                key = f"{language}.{fmt}"
                generated = job.generated_files.get(key)
                if not generated:
                    continue
                target = media_path.with_name(f"{media_path.stem}.{language}.{fmt}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(generated, target)
                outputs.append(target)
        return outputs

    async def unload(self) -> None:
        # asub workers are process-scoped and are closed by Pipeline stage transitions.
        # This hook exists so future persistent model servers can release memory when
        # the service queue drains without changing the queue contract.
        return None
