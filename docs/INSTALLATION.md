# Windows installation

Download the Windows portable ZIP from [Releases](https://github.com/DeveloperPY-YUG/Multi-AI/releases) once a build is published. Extract the entire ZIP. Open `MULTI-AI/Multi-AI.exe`; keep `_internal` next to the EXE. Run `MULTI-AI/Install-MULTI-AI.cmd` to create a desktop shortcut. This is a portable application, not a system installer. An unsigned binary may trigger Windows reputation prompts.

For source installation use 64-bit Python 3.11 or newer, then run `py -m pip install -r requirements.txt` and `py main.py` in the repository directory. To build locally on Windows run `BUILD-WINDOWS.cmd`. See [configuration](CONFIGURATION.md).
