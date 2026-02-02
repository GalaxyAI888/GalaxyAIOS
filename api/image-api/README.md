# Image API

A text-to-image and image-to-image server compatible with the OpenAI API, powered by backend support for Stable Diffusion 3.5, Flux, Z-Image, Qwen-Image, and more.

## Features

- **OpenAI Compatible API**: Drop-in replacement for OpenAI's image generation API
- **Multiple Model Support**: SD3.5 Medium/Large, Flux, Z-Image, Qwen-Image
- **Task Queue**: ComfyUI-style queue system for managing generation requests
- **Auto Download**: Automatic model downloading from HuggingFace or ModelScope
- **VRAM Optimization**: Automatic quantization based on available GPU memory
- **Model Management**: APIs for downloading, listing, and managing models

## Quick Start

### Prerequisites

- Python 3.10+
- CUDA compatible GPU (recommended 12GB+ VRAM)
- uv (recommended) or pip

### Installation with uv

```bash
# Create virtual environment with uv
uv venv --python 3.10

# Activate virtual environment
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies with Chinese mirror
uv pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# Or install with pip
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Running the Server

```bash
# Basic usage
image-api start --model-scope-model-id AI-ModelScope/stable-diffusion-3.5-medium --model-dir /opt/data/models --output-dir /opt/data/output --logs-dir /opt/data/logs --host 0.0.0.0 --port 8882

# With HuggingFace model
image-api start --huggingface-repo-id stabilityai/stable-diffusion-3.5-medium --model-dir /opt/data/models --host 0.0.0.0 --port 8882

# Debug mode
image-api start -d --model-scope-model-id AI-ModelScope/stable-diffusion-3.5-medium --model-dir /opt/data/models --port 8882
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --debug` | Enable debug mode | `False` |
| `--host` | Host to bind the server to | `0.0.0.0` |
| `--port` | Port to bind the server to | `80` |
| `--device` | Binding device (e.g., cuda:0) | `cuda:0` |
| `--huggingface-repo-id` | HuggingFace repo id for the model | - |
| `--model-scope-model-id` | ModelScope model id for the model | - |
| `--model-dir` | Directory to store model files | OS specific |
| `--output-dir` | Directory to store output images | `./output` |
| `--logs-dir` | Directory to store log files | `./logs` |

## API Endpoints

### OpenAI Compatible

#### Text to Image

```bash
POST /v1/images/generations
```

Request body:
```json
{
    "model": "stable-diffusion-3.5-medium",
    "prompt": "A beautiful sunset over mountains",
    "n": 1,
    "size": "1024x1024",
    "response_format": "url"
}
```

#### Image to Image

```bash
POST /v1/images/edits
```

#### Image Variations

```bash
POST /v1/images/variations
```

### Model Management

#### List Models

```bash
GET /v1/models
```

Returns all supported models with their status (downloaded, enabled, etc.)

#### Download Model

```bash
POST /v1/models/{model_id}/download
```

Triggers model download. Can also be done automatically on first use.

### Queue Management

#### Get Queue Status

```bash
GET /v1/queue
```

#### Get Task Status

```bash
GET /v1/queue/{task_id}
```

#### Cancel Task

```bash
DELETE /v1/queue/{task_id}
```

### Health Check

```bash
GET /health
```

## Supported Models

| Model | Size | VRAM | Quantization | Status |
|-------|------|------|--------------|--------|
| stable-diffusion-3.5-medium | 4.8GB | 8G (INT4) / 12G (INT8) / 24G (FP16) | Auto | ✅ |
| stable-diffusion-3.5-large | 16GB | 12G (INT4) / 16G (INT8) / 24G (FP16) | Auto | ✅ |
| stable-diffusion-3.5-large-turbo | 16GB | 12G (INT4) / 16G (INT8) / 24G (FP16) | Auto | ✅ |
| flux-dev | 23GB | 24G+ | FP16 | 🚧 |
| flux-schnell | 23GB | 24G+ | FP16 | 🚧 |

### VRAM Quantization Strategy

| VRAM | Quantization | Description |
|------|--------------|-------------|
| < 10GB | INT4 (NF4) | 4-bit quantization for low VRAM GPUs |
| 10-20GB | INT8 | 8-bit quantization for medium VRAM GPUs |
| > 20GB | FP16 | Full precision for high VRAM GPUs |

## Docker

### Build Image

```bash
docker build -t image-api:latest .
```

### Run Container

```bash
docker run -d \
    --gpus all \
    -p 8882:8882 \
    -v /opt/data/models:/opt/data/models \
    -v /opt/data/output:/opt/data/output \
    -v /opt/data/logs:/opt/data/logs \
    image-api:latest \
    start --model-scope-model-id AI-ModelScope/stable-diffusion-3.5-medium \
    --model-dir /opt/data/models \
    --output-dir /opt/data/output \
    --logs-dir /opt/data/logs \
    --host 0.0.0.0 --port 8882
```

## Development

### Run Tests

```bash
pytest tests/ -v
```

### Code Style

```bash
# Format code
black image_api/

# Lint code
flake8 image_api/
```

## License

MIT License
