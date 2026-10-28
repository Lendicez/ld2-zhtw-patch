# m047 acceptance boundary

This milestone only validates the packaged candidate CLI in a fresh bounded EXE workspace. Preview/cancel must not write; unknown source/version and out-of-bound paths must be refused. Install must produce the exact pinned m045 hash, retaining the original backup and metadata. A new process must identify m045 from the protected anchor and restore the original identity/metadata even if another profile is selected. Repeated restore must be read-only and idempotent.

The GUI/controller and profile choices are checked headlessly, not visually. No GUI or game launch is part of this milestone. m046's full copy may still be running and must remain untouched. That prior minimal acceptance covers the F1 prompt (direct observation) and File menu (user report), not all 554 positions, gameplay, save compatibility or normal exit. Production installation remains disabled. Two-step rename is not an atomic transaction or proof of power-loss safety.

After this milestone, any further game or candidate-GUI acceptance requires a separately arranged observation window. Keep prior profiles and protected recovery evidence. Do not publish the executable, game inputs/outputs, recovery credentials or screenshots.
