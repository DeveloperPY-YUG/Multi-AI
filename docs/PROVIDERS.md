# Providers

| Provider | Protocol | Default endpoint |
| --- | --- | --- |
| Groq | OpenAI-compatible | `https://api.groq.com/openai/v1` |
| Google Gemini | Native Gemini | `https://generativelanguage.googleapis.com/v1beta` |
| Anthropic Claude | Native Messages | `https://api.anthropic.com/v1` |
| Qwen | OpenAI-compatible | Set your regional HTTPS endpoint |
| LM Studio | Local OpenAI-compatible | `http://127.0.0.1:1234/v1` |
| Ollama | Native local | `http://127.0.0.1:11434` |

xAI and custom providers can be added in the app. For Ollama, install it, run `ollama pull <model-name>`, start the service, and select **Test & refresh** in MULTI-AI. For LM Studio, load a model and start its local API server. Cloud providers require your own credentials and may charge fees. A web subscription does not necessarily grant API access.
