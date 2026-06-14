from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .exceptions import AsubError
from .languages import parse_targets
from .models import ProcessingOptions
from .orchestrator import Pipeline, translate_existing
from .workers.ipc import WorkerClient

app = typer.Typer(help="Local video captioning and subtitle translation.")
console = Console()


def _formats(value: str) -> list[str]:
    return [part.strip().lower().lstrip(".") for part in value.split(",") if part.strip()]


def _options(
    output: Path,
    targets: str,
    source: str,
    formats: str,
    align: bool,
    mux: bool,
    burn: bool,
    in_place: bool,
    cleanup: bool,
    overwrite: bool,
    resume: bool,
    skip_existing: bool,
    chunk_mode: str,
    device: str,
    dtype: str,
    quantization: str,
    speaker_labels: str,
    encoder: str,
    preset: str,
    cq: int,
    audio_sample_rate: int,
    asr_model: str,
    asr_max_new_tokens: int,
    asr_max_batch_size: int,
    asr_max_model_len: int,
    asr_gpu_memory_utilization: float,
    jobs: int,
) -> ProcessingOptions:
    return ProcessingOptions(
        output_dir=output,
        asr_model=asr_model,
        source_language=source,
        target_languages=parse_targets(targets) if targets else [],
        formats=_formats(formats),
        align=align,
        mux=mux,
        burn=burn,
        in_place=in_place,
        cleanup=cleanup,
        overwrite=overwrite,
        resume=resume,
        skip_existing=skip_existing,
        chunk_mode=chunk_mode,  # type: ignore[arg-type]
        device=device,
        dtype=dtype,  # type: ignore[arg-type]
        quantization=quantization,
        speaker_labels=speaker_labels,  # type: ignore[arg-type]
        encoder=encoder,
        preset=preset,
        cq=cq,
        audio_sample_rate=audio_sample_rate,
        asr_max_new_tokens=asr_max_new_tokens,
        asr_max_batch_size=asr_max_batch_size,
        asr_max_model_len=asr_max_model_len,
        asr_gpu_memory_utilization=asr_gpu_memory_utilization,
        jobs=jobs,
    )


def _run_pipeline(inputs: list[str], options: ProcessingOptions) -> None:
    try:
        jobs = Pipeline(options).process_inputs(inputs)
    except AsubError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    for job in jobs:
        console.print(f"[green]Completed[/green] {job.input_path} -> {job.output_dir}")


@app.command()
def process(
    inputs: list[str] = typer.Argument(..., help="Video files, folders, or glob patterns."),
    targets: str = typer.Option("", "--targets", help="Comma-separated target languages, e.g. en,es,fr."),
    source: str = typer.Option("auto", "--source", help="Source language code/name, or auto."),
    output: Path = typer.Option(Path("asub-output"), "--output", "-o"),
    formats: str = typer.Option("srt,vtt", "--formats"),
    align: bool = typer.Option(False, "--align/--no-align"),
    mux: bool = typer.Option(True, "--mux/--no-mux"),
    burn: bool = typer.Option(False, "--burn/--no-burn"),
    in_place: bool = typer.Option(False, "--in-place/--no-in-place", help="Replace the source video with the muxed MP4 output. MKV inputs are converted to a same-stem .mp4 and the original is removed after success."),
    cleanup: bool = typer.Option(False, "--cleanup/--no-cleanup", help="Remove transient work files after successful processing."),
    overwrite: bool = typer.Option(False, "--overwrite/--no-overwrite"),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
    skip_existing: bool = typer.Option(True, "--skip-existing/--no-skip-existing"),
    chunk_mode: str = typer.Option("auto", "--chunk-mode"),
    device: str = typer.Option("auto", "--device"),
    dtype: str = typer.Option("bf16", "--dtype"),
    quantization: str = typer.Option("none", "--quantization"),
    speaker_labels: str = typer.Option("visible", "--speaker-labels"),
    encoder: str = typer.Option("hevc_nvenc", "--encoder"),
    preset: str = typer.Option("p5", "--preset"),
    cq: int = typer.Option(22, "--cq"),
    audio_sample_rate: int = typer.Option(24000, "--audio-sample-rate"),
    asr_model: str = typer.Option("Qwen/Qwen3-ASR-1.7B", "--asr-model", help="Qwen ASR model id."),
    asr_max_new_tokens: int = typer.Option(4096, "--asr-max-new-tokens"),
    asr_max_batch_size: int = typer.Option(128, "--asr-max-batch-size"),
    asr_max_model_len: int = typer.Option(16384, "--asr-max-model-len"),
    asr_gpu_memory_utilization: float = typer.Option(0.65, "--asr-gpu-memory-utilization"),
    jobs: int = typer.Option(2, "--jobs", min=1, help="Number of input videos to process concurrently."),
) -> None:
    options = _options(output, targets, source, formats, align, mux, burn, in_place, cleanup, overwrite, resume, skip_existing, chunk_mode, device, dtype, quantization, speaker_labels, encoder, preset, cq, audio_sample_rate, asr_model, asr_max_new_tokens, asr_max_batch_size, asr_max_model_len, asr_gpu_memory_utilization, jobs)
    _run_pipeline(inputs, options)


@app.command()
def transcribe(
    inputs: list[str] = typer.Argument(...),
    output: Path = typer.Option(Path("asub-output"), "--output", "-o"),
    source: str = typer.Option("auto", "--source"),
    formats: str = typer.Option("srt,vtt", "--formats"),
    overwrite: bool = False,
    asr_model: str = typer.Option("Qwen/Qwen3-ASR-1.7B", "--asr-model"),
    asr_max_new_tokens: int = typer.Option(4096, "--asr-max-new-tokens"),
    asr_max_batch_size: int = typer.Option(128, "--asr-max-batch-size"),
    asr_max_model_len: int = typer.Option(16384, "--asr-max-model-len"),
    asr_gpu_memory_utilization: float = typer.Option(0.65, "--asr-gpu-memory-utilization"),
    jobs: int = typer.Option(2, "--jobs", min=1),
) -> None:
    options = _options(output, "", source, formats, False, False, False, False, False, overwrite, True, True, "auto", "auto", "bf16", "none", "visible", "hevc_nvenc", "p5", 22, 24000, asr_model, asr_max_new_tokens, asr_max_batch_size, asr_max_model_len, asr_gpu_memory_utilization, jobs)
    _run_pipeline(inputs, options)


@app.command()
def translate(job_or_metadata: Path, targets: str = typer.Option(..., "--targets"), formats: str = typer.Option("srt,vtt", "--formats"), overwrite: bool = False) -> None:
    options = ProcessingOptions(formats=_formats(formats), overwrite=overwrite, target_languages=parse_targets(targets))
    try:
        job = translate_existing(job_or_metadata, parse_targets(targets), options)
    except AsubError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print(f"[green]Translated[/green] {job_or_metadata} -> {job.subtitle_dir}")


@app.command()
def mux(job_or_metadata: Path, overwrite: bool = False) -> None:
    from .models import JobMetadata

    path = job_or_metadata / "metadata.json" if job_or_metadata.is_dir() else job_or_metadata
    job = JobMetadata.load(path)
    options = ProcessingOptions(overwrite=overwrite, mux=True, resume=False, skip_existing=False)
    pipeline = Pipeline(options)
    try:
        pipeline._mux(job)
    except AsubError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print(f"[green]Muxed[/green] {job.generated_files.get('mux.mp4')}")


@app.command()
def burn(job_or_metadata: Path, overwrite: bool = False, encoder: str = "hevc_nvenc", preset: str = "p5", cq: int = 22) -> None:
    from .models import JobMetadata

    path = job_or_metadata / "metadata.json" if job_or_metadata.is_dir() else job_or_metadata
    job = JobMetadata.load(path)
    options = ProcessingOptions(overwrite=overwrite, burn=True, encoder=encoder, preset=preset, cq=cq, formats=["ass"])
    pipeline = Pipeline(options)
    try:
        pipeline._burn(job)
    except AsubError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print("[green]Burned subtitles[/green]")


@app.command()
def gui() -> None:
    from .gui import main

    main()


@app.command()
def doctor() -> None:
    """Check local tools, worker interpreters, CUDA, and key imports."""
    import shutil
    import subprocess
    import sys

    console.print(f"Core Python: {sys.executable}")
    for tool in ["ffmpeg", "ffprobe"]:
        path = shutil.which(tool)
        console.print(f"{tool}: {path or '[red]missing[/red]'}")

    checks = [
        ("qwen_asr", "asub.workers.qwen_asr_worker", "from asub.workers.cuda import configure_cuda_environment; configure_cuda_environment('auto'); import torch, qwen_asr; from qwen_asr import Qwen3ASRModel; print(torch.__version__)"),
        ("mt", "asub.workers.mt_worker", "from asub.workers.cuda import configure_cuda_environment; configure_cuda_environment('auto'); import torch, transformers; print(torch.__version__, transformers.__version__)"),
        ("align", "asub.workers.align_worker", "from asub.workers.cuda import configure_cuda_environment; configure_cuda_environment('auto'); import torch, qwen_asr; from qwen_asr import Qwen3ForcedAligner; print(torch.__version__)"),
    ]
    failed = False
    for kind, module, probe in checks:
        command = WorkerClient(kind, module).command()
        python = command[0]
        console.print(f"{kind} worker Python: {python}")
        result = subprocess.run([python, "-c", probe], text=True, capture_output=True, check=False)
        if result.returncode == 0:
            console.print(f"  [green]OK[/green] {result.stdout.strip()}")
        else:
            failed = True
            console.print(f"  [red]FAIL[/red] {result.stderr.strip() or result.stdout.strip()}")

    cuda = subprocess.run(
        [WorkerClient("qwen_asr", "asub.workers.qwen_asr_worker").command()[0], "-c", "from asub.workers.cuda import configure_cuda_environment; configure_cuda_environment('auto'); import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"],
        text=True,
        capture_output=True,
        check=False,
    )
    if cuda.returncode == 0:
        console.print("CUDA:")
        for line in cuda.stdout.splitlines():
            console.print(f"  {line}")
    else:
        failed = True
        console.print(f"[red]CUDA check failed:[/red] {cuda.stderr.strip() or cuda.stdout.strip()}")
    if failed:
        raise typer.Exit(1)
