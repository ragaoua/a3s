# Run an LLM locally through ollama

```bash
cd ollama
podman-compose up -d
```

Alternatively, run ollama on the host machine directly:

```bash
cd ollama
OLLAMA_MODELS=./ollama_data/models/ ollama serve
ollama pull qwen2.5:1.5b
```

Access OpenAI-compatible endpoint at `http://localhost:11434/v1`.

# Run a mock LLM server with mockllm

```sh
cd mockllm
uvx mockllm start --port 8001
```

Access OpenAI-compatible endpoint at `http://localhost:8001/v1`.

**Note**: API key and model name are ignored.
