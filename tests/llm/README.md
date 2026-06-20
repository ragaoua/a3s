# Run an LLM locally through ollama

```bash
cd ollama
podman-compose up -d
```

Access OpenAI-compatible endpoint at `http://localhost:11434/v1`.

# Run a mock LLM server with mockllm

```sh
cd mockllm
uvx mockllm start --port 8001
```

Access OpenAI-compatible endpoint at `http://localhost:8001/v1`.

**Note**: API key and model name are ignored.
