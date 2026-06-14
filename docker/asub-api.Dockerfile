FROM nvidia/cuda:12.9.1-cudnn-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_XET=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        python3.12 \
        python3.12-dev \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY asub ./asub

RUN python3.12 -m venv /opt/asub-service \
    && /opt/asub-service/bin/python -m pip install --upgrade pip \
    && /opt/asub-service/bin/pip install -e '.[test]' \
    && /opt/asub-service/bin/pip install \
        'torch' \
        'qwen-asr[vllm]' \
        'transformers>=4.56.0' \
        'accelerate' \
        'vllm>=0.10.0'

ENV PATH="/opt/asub-service/bin:${PATH}"
EXPOSE 8765

CMD ["uvicorn", "asub_service.api:app", "--host", "0.0.0.0", "--port", "8765"]
