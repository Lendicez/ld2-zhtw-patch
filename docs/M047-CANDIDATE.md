# m047 candidate integration

The disposable-copy candidate now defaults to pinned m045: 554 text locations and 71 existing font locations. m020, m037, m038, m041 and m042 remain selectable with unchanged recipes, source/output hashes and expected sizes. The ordinary non-trial generator still defaults to m020.

Only an identity-bound, newly created EXE test workspace is eligible. Production can_apply remains false. Restore identifies the stored profile from the protected recovery anchor, regardless of the profile selected in the new process. Preserve the workspace and recovery-store together on the same Windows account; users never edit JSON or copy hashes manually. No changes to the filesystem backend, permission model or restore trust design are introduced.

The m046 observation establishes only that m045's initial F1 prompt displayed correctly; the user reported that the File menu could be opened manually. The attached user image was not independently inspected. Character/facility scenes, save/load and normal exit are not accepted. Automatic input failure remains unexplained; manual success does not prove UIPI. Candidate GUI has not been visually tested.

Headless commands (the packaged tool is local-only):

```text
ld2-patch-generator.exe --help
ld2-patch-generator.exe --version
ld2-patch-generator.exe --trial preview --source "<absolute original EXE>"
ld2-patch-generator.exe --trial preview --source "<absolute original EXE>" --cancel
ld2-patch-generator.exe --trial install --source "<absolute original EXE>" --confirm
ld2-patch-generator.exe --trial inspect --workspace "<workspace returned by install>"
ld2-patch-generator.exe --trial restore --workspace "<workspace returned by install>" --confirm
```

Omitting arguments opens GUI; do not do that during headless checks. Restore is restricted to the protected newly created workspace, never a full game directory. Existing game/save data is not an installation target. The onefile is asInvoker and refuses administrator execution; no elevated helper, security exclusion, hook or dependency is added. m039 dynamic formatter and m040 layout are not enabled. No game EXE is bundled or executed. No new full-game copy is prepared.

See packaging/m047-verification.json for final measured results and limitations. No new translation, original-language excerpt or resource locator is introduced by this integration.
