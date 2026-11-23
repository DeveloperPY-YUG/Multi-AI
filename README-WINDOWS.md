# MULTI-AI v1.0.0 - Windows portable release

**MADE BY YUG** | Windows 10/11 x64

1. Extract the entire release ZIP into a permanent folder.
2. Double-click `Multi-AI.exe` to start MULTI-AI without a console window.
3. Double-click `Install-MULTI-AI.cmd` to create a desktop shortcut.
4. Keep the extracted folder in place; moving it will break the shortcut.

Python is not required for this packaged build. API providers may require your own
API keys and/or third-party accounts. Local LM Studio and Ollama require separately
installed local model servers. Keys are stored in Windows Credential Manager.

This is a portable EXE directory, not a Windows installer. The executable is
not code-signed. Windows SmartScreen may warn about newly built unsigned apps;
only run it when the release comes from a source you trust.

## Build from source

On Windows 10/11 x64 with Python 3.11+ installed, double-click `BUILD-WINDOWS.cmd`.
The build generates `release/MULTI-AI-v1.0.0-Windows.zip` containing `Multi-AI.exe`.
For builds without a local Windows machine, push the project to GitHub and run
**Actions -> Build Windows Release -> Run workflow**, then download the artifact.
