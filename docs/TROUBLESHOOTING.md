# Troubleshooting

| Symptom | Action |
| --- | --- |
| No models | Use **Test & refresh**, or add the exact model ID in Model Manager. |
| Authentication fails | Check the key, account access, and selected model. |
| Ollama or LM Studio unavailable | Start the local server and check the default port. |
| Custom provider fails | Confirm HTTPS and compatible `/chat/completions` streaming. |
| Key cannot save | Check Windows Credential Manager. |
| EXE does not start | Extract the full portable ZIP, including `_internal`, and retry. |

Open an issue with steps and non-secret logs if the problem persists.
