# MULTI-AI

<div align="center">
<img src="assets/icon.png" width="112" alt="MULTI-AI icon" />

**Cloud and local AI models in one Windows desktop app**  
💜 **MADE BY YUG**

[![MIT](https://img.shields.io/badge/license-MIT-7656e8)](LICENSE) [![Windows](https://img.shields.io/badge/platform-Windows%2010%2F11-3178c6)](docs/INSTALLATION.md) [![Tests](https://github.com/DeveloperPY-YUG/Multi-AI/actions/workflows/tests.yml/badge.svg)](https://github.com/DeveloperPY-YUG/Multi-AI/actions/workflows/tests.yml) [![Build](https://github.com/DeveloperPY-YUG/Multi-AI/actions/workflows/build-windows.yml/badge.svg)](https://github.com/DeveloperPY-YUG/Multi-AI/actions/workflows/build-windows.yml)
</div>

## Project guides

[Installation](docs/INSTALLATION.md) · [Configuration](docs/CONFIGURATION.md) · [Providers](docs/PROVIDERS.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [FAQ](docs/FAQ.md) · [Releases](https://github.com/DeveloperPY-YUG/Multi-AI/releases) · [Contributing](CONTRIBUTING.md)

## First public release — v1.0.0

**MADE BY YUG** · Windows 10/11 desktop AI application.

Chat with Groq, Gemini, Anthropic, Qwen, LM Studio, Ollama and additional compatible AI providers from one interface. **Providers can be added, removed, and re-added from inside the app—no editing Python, HTML or project files required after this upgrade.** Conversation history is never written to disk.

## Download the Windows desktop EXE

When a Windows build is published, download it from [Releases](https://github.com/DeveloperPY-YUG/Multi-AI/releases). You can also run the GitHub Actions workflow **Build Windows Release** (`Actions -> Run workflow`)
or build on Windows with `BUILD-WINDOWS.cmd`. The resulting
`release/MULTI-AI-v1.0.0-Windows.zip` includes `Multi-AI.exe` (no separate Python
installation), bundled UI, and `Install-MULTI-AI.cmd` for a desktop shortcut.
Extract the entire ZIP and open the EXE. The console stays hidden.

> A release asset exists only after its build and publication succeed. The source ZIP is not the Windows compiled binary. PyInstaller must run on
> Windows (or the provided Windows GitHub Actions runner) to create `Multi-AI.exe`.
> The application may require user-supplied API keys or locally running model servers.

**Upgrade:** Existing preferences and Windows Credential Manager entries from
older releases using the prior app name are migrated automatically when accessible.
The 1.0.0 label marks the public release; feature behavior is retained from the
provided project sources. Review `LICENSE` before publishing.

## Run from source on Windows

1. Unzip your source ZIP into a folder (for example, Desktop/MULTI-AI). The source ZIP contains the complete program, not a patch.
2. Open a PowerShell or Command Prompt in the extracted `MULTI-AI` folder containing `main.py`.
3. Install dependencies and launch:

```powershell
python -m pip install -r requirements.txt
python main.py
```

Requires 64-bit Python 3.11 or newer. Existing MULTI-AI settings saved in the Windows application configuration folder will be loaded when available; old chat messages do not persist. If you have a very old `xAI` connection, xAI is no longer preinstalled, but can be re-added with one click from the provider presets. Existing xAI credentials can be managed after re-adding xAI.

## Use Groq (not Grok)

1. Open **API Connections**. A **Groq** card is included by default.
2. Create an API key at **https://console.groq.com/keys**. Keep the key private.
3. In the Groq card choose **Add API key**, paste the key into the native dialog, and click **Save**.
4. Choose **Test & refresh**. Available Groq model IDs will appear in **Model Manager** and the chat model selector.
5. Select a model and chat. If discovery is unavailable, save the provider's exact chat model ID in **Model Manager → Add custom model**.

Groq's OpenAI-compatible base URL is `https://api.groq.com/openai/v1`, preconfigured in this release.

## Add and remove any supported connection from the app

Go to **API Connections → + Add AI provider**. Choose:

- **Groq**, **Google Gemini (Google AI Studio)**, **Anthropic**, **Qwen**, or **xAI** presets.
- **LM Studio** or **Ollama** local presets.
- **Custom cloud API (OpenAI-compatible)** to add other services, giving it a name and HTTPS API base URL.
- **Custom local API (OpenAI-compatible)** to connect an unauthenticated server on localhost or another loopback IP.

Click **Add provider**. A new connection card appears immediately. Add its API key (cloud), then **Test & refresh** and choose a model. Custom cloud services must expose compatible `/chat/completions` streaming; `/models` discovery is optional because exact model IDs can also be entered manually. Services using other proprietary protocols require a specific connector; a custom URL alone does not make every API format compatible.

To delete a connection, click **Remove provider** on its card and confirm. The app removes that provider's saved model entries, the currently configured endpoint and its saved API key from Windows Credential Manager. You can re-add a preset at any time without reinstalling anything. A model currently selected in chat is replaced by another available configured model when its provider is removed.

**Qwen:** set your account/region's HTTPS OpenAI-compatible base URL in its card before adding the API key. The endpoint is editable on Qwen, local and custom provider cards. Official native Gemini/Claude endpoints and Groq endpoint are fixed to avoid accidentally sending credentials elsewhere.

## Connections included in a fresh installation

| Connection | Protocol | Default API base URL |
| --- | --- | --- |
| Groq | OpenAI-compatible chat/SSE | `https://api.groq.com/openai/v1` |
| Google Gemini | Native Gemini API | `https://generativelanguage.googleapis.com/v1beta` |
| Anthropic Claude | Native Claude Messages API | `https://api.anthropic.com/v1` |
| Qwen | OpenAI-compatible chat/SSE | Enter endpoint for your region |
| LM Studio | Local OpenAI-compatible | `http://127.0.0.1:1234/v1` |
| Ollama | Native local API | `http://127.0.0.1:11434` |

You can add xAI and multiple custom connections from the UI. The preconfigured Claude Opus 4.6 manual model ID is `claude-opus-4-6`; it requires Anthropic API account access. A web subscription does not necessarily include API credits.

## Model Manager and chat

Choose **Model Manager** to refresh model lists or save any custom API model ID under the corresponding provider. Saved entries survive restarts; discovered entries appear when the service supports listing. Choose a model from the upper-right selector. Chat supports streamed Markdown, syntax highlighted code, copy, edit, retry/regenerate, stop, and multiple **temporary** conversations. Select another model while in a conversation to keep the temporary context.

Keyboard shortcuts: `Ctrl+N` new chat, `Ctrl+K` model selector, `Ctrl+B` sidebar, `Ctrl+,` settings, `Enter` send, `Shift+Enter` newline, `Esc` stop generation.

## Security, data, privacy

- Chats exist only in memory and are cleared when the program closes. No SQLite chat database, stored chat files or browser localStorage.
- Provider profiles, editable endpoints and saved model identifiers persist in Windows app preferences as `settings.json`; **API keys never go into that file**.
- API keys are stored in **Windows Credential Manager**, handled only by the Python backend. Remote requests use HTTPS. Custom local endpoints are restricted to loopback hosts. Requests do not follow redirects.
- Whenever a cloud provider is used, conversation context is sent to that provider according to its policies. This includes any prior context from a different model in the same chat.
- Qt WebEngine uses an off-the-record profile and bundled offline frontend resources; AI Markdown is sanitized.
- If you previously used an endpoint for Qwen or another editable cloud profile, changing its URL does not automatically revoke credentials for earlier endpoints. Remove the earlier key before changing the endpoint if necessary; old Windows Credential Manager entries can also be managed in Windows.
- Don't share API keys, and don't paste them into chat messages or project files.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| No Groq card | Run this v1.0.0 folder and check **API Connections**. If a provider was removed, re-add **Groq** from the presets. |
| Missing models | Click **Test & refresh** or enter an exact model ID in **Model Manager**. |
| Authentication failed | Ensure your API key has access to the selected service/model. |
| Can't add a cloud custom endpoint | Enter its HTTPS base URL, usually ending in `/v1`. It must support OpenAI-compatible chat. |
| Can't connect to local | Start LM Studio or Ollama and check the server host and port. |
| Can't save API key | Check Windows Credential Manager availability. |
| Custom model errors | Some providers use different token limits, sampling parameters or incompatible chat formats. Use a supported model and try provider-default temperature. |

## Run tests

```powershell
python -m unittest discover -v
```

Offline unit tests use mocked cloud APIs; desktop integration tests exercise a real PySide6 WebEngine window and simulated local endpoints. No credentials are needed for tests. Real API service access and Windows Snap integration require verification on the target Windows machine.

## Project files

- `main.py` — native desktop window and private WebEngine.
- `backend/config.py` — validated dynamic provider registry and persistent non-secret settings.
- `backend/bridge.py` — native key dialogs, provider add/remove, model controls.
- `backend/providers.py` / `ai_manager.py` — provider protocols, model discovery, background HTTP streaming.
- `backend/key_manager.py` — Windows Credential Manager.
- `frontend/` — locally bundled HTML/CSS/JS interface.
- `assets/` — application icon.
- `tests/` — offline unit and desktop tests.


## v1.0.0 — Hover-to-remove models

Open the model selector (**Ctrl+K**) or **Model Manager**. Move your mouse over
any model and click the **trash icon**. It is removed from MULTI-AI in one click,
with **no confirmation dialog and no need to select the model first**.
An **Undo** button is shown for 8 seconds after removal. You can also expand
**Removed models** in the selector or Model Manager and click **Restore** later.

Removing a model hides it from the app; it **does not delete the model from the
AI provider**. The hidden state is saved across restarts. Manual model IDs and
custom display names are retained so they can be restored. If the removed model
was active, MULTI-AI automatically selects another available model.
Keyboard users can Tab to the remove button; on touch screens, the icon is
always visible.
