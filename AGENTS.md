# Development rules

Work on source and synthetic tests only. No game assets, binaries, private saves, dumps, credentials or full disassembly.
No game/harness execution, GUI automation, security changes, installs, network publication or Actions activation without the applicable authorization.
Do not treat this repository as permission to retry historically blocked binaries.
Run `python -B tools/check.py`; absent licensed input and Windows APIs must be explicitly skipped, never reported as passing integration.
Keep source and expected-output version hashes; no guessed Steam AppID. Installer is planned, not implemented.
Do not spawn agents. Keep changes bounded; preserve formatting contracts, resource IDs, saves and original gameplay.
