# Reproducible offline m020 build (m028)

This stacked change depends on PR #2 at
`7c443a04ed26831eed950dfeb835ac56fe6b6f8e`. It turns the existing reviewed
resource rebuild into a bounded offline command. It does not install, launch,
inject into or discover the game. Production `can_apply` remains false.

## Build contract

Inputs are immutable original EXE bytes, the version allowlist, the exact UTF-8
catalog and `patches/m020-recipe.json`. The recipe pins the catalog file hash,
version ID, transformation, text/font location counts and catalog filename. The
version record pins original/output hashes, sizes and file/product versions.
The engine parses VS_FIXEDFILEINFO from the EXE itself; a matching filename or
external version claim is insufficient.

Only the known original hash is accepted. The current recipe must reproduce the
historical m020 output exactly. Editing the catalog, recipes or expected hashes
is not an automatic approval of a new release: those are trusted reviewed inputs,
not signed security attestations. Unapproved output is rejected; expected values
are not relaxed to make a changed build pass.

Run from the repository with the existing Python; all three paths must be
absolute, the output parent must already exist, and both outputs must be new:

```text
python -B tools/build_patch.py --input "<absolute original EXE>" --out "<absolute new build EXE>" --metadata-out "<absolute new metadata JSON>"
```

Output and metadata must be distinct siblings outside the original input
directory. Existing outputs, in-place writes, path traversal and symlink/reparse
paths are refused. Input bytes/identity are checked again before artifact writes
and input bytes again afterward. Writes use exclusive creation and readback;
they never replace an existing game or output. A failed artifact write can leave
a partial build file and reports failure. This is not an installer transaction,
an adversarial filesystem sandbox or a guarantee against concurrent OS changes.

`PatchBuild.output` is the verified transient result; metadata contains hashes,
versions, counts and structural evidence only. A future installer can consume
the verified bytes through its reviewed transaction interface. There is no
connection to a production write adapter here. Full original/modified EXEs are
private local build artifacts and must never enter Git, uploads or releases.

## Resource and PE checks

The parser bounds PE32/x86 headers, section counts, file/RVA ranges, alignments,
raw and virtual section overlap, resource-directory depth/counts, metadata and
payload overlap, duplicate IDs and resource sizes. Virtual-only section bytes
are not treated as bytes present in the file. It intentionally supports the
reviewed layout with a final `.rsrc` section, not every valid PE variant.

Catalog validation rejects unknown fields, Boolean/negative/out-of-range
locators, duplicate physical text/font targets, invalid IDs, unsafe text and
contract changes. The recipe hash also binds the complete catalog. Builder
patches are restricted to resource data-entry relocation, with append and total
size budgets; arbitrary code/data patching is not permitted.

After rebuilding, the engine verifies the complete original prefix is identical
except for changed resource data-entry RVA/size pairs and these six fields:
SizeOfInitializedData, SizeOfImage, CheckSum, resource directory size, `.rsrc`
virtual size and raw size. Every other original byte stays identical. Resource
identity sets stay fixed; only allowed menu/dialog/string payloads change. New
bytes contain appended approved resource payloads and zero padding only. The
checksum is verified. Non-resource sections are compared byte-for-byte.

## Actual local evidence

The explicitly authorized local integration used the original 1.0.3.16 file
(product version 1.0.3.0), solely as read-only input. Two distinct EXE builds and
their metadata were byte-identical. The original file hash before and after was
unchanged. `patches/m020-build-verification.json` contains reproducible evidence
without source paths, raw bytes, disassembly or game assets.

| Item | Verified value |
| --- | --- |
| Original bytes | 7,090,176 |
| Original SHA-256 | `6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2` |
| Output bytes | 7,102,464 |
| Output SHA-256 | `a15bf7313636a7c19a065b388345f93b46bbce8eb6bf3c9b910a7dc192c3da81` |
| Carried translated text locations | 239 |
| Carried dialog font settings | 15 |
| Changed resource payloads | 27 of 316 resource entries |
| Unchanged non-resource sections | `.text`, `.rdata`, `.data` |

These are locations/resource counts, not whole-game translation coverage. No new
translation batch was added. Dynamic CP932 text, external archives/data, story
and item descriptions, DBCS drawing/measurement paths, runtime date text and
remaining UI still need separate work. Image text remains excluded. This build
does not establish Unicode engine support, Win11 gameplay stability, visual
layout correctness or save/load compatibility.

## Tests and skipped integration

`python -B tools/check.py` without licensed input: **117 tests, 114 passed,
3 skipped** (two licensed-input integrations and real Windows symlink creation).

With explicitly authorized local `--game-exe`: **117 tests, 116 passed,
1 skipped** (real Windows symlink creation). Windows native encoding tests pass.
No executable was run. Cloud environments without licensed input must keep the
two integration tests explicitly skipped; no Actions or cloud executor was used.

New negative tests cover truncated headers, raw/virtual section and resource
overlap, cycles/duplicate resource IDs, resource budgets, virtual-only RVAs,
malformed dialog/string lengths, unauthorized code changes, catalog injection,
wrong hashes/versions, output conflicts and in-place write refusal. Synthetic PE
fixtures are generated from invented source code and contain no game bytes.

## Shortest packaging step, still separate from installation

The smallest next packaging experiment is an **unelevated offline build tool**
containing this engine plus the reviewed recipe/catalog/version JSON, initially
as one folder and then as one executable. The current project Python environment
has neither PyInstaller nor Nuitka; no dependency was installed. Choosing
PyInstaller would require a separately approved project-local package install,
pinned compatible dependencies, a bundled-resource path adjustment and a bundle
content audit excluding all game/build/test assets. Existing MSVC alone does not
freeze this Python engine; a native port is a larger alternative.

Official PyInstaller documentation describes collecting Python and dependencies,
recommends validating one-folder mode before one-file mode, and explains that
one-file execution extracts support files into a temporary directory. It also
warns against running a Windows one-file bundle with administrator privileges.
Therefore this experiment must remain an unelevated builder; it is not approval
to package a privileged installer. A real installer still needs AppID evidence,
Windows filesystem/process adapters, secure privilege separation, recovery and
final GUI/save/load/restore acceptance. Signing or packaging cannot be promised
to remove security warnings; a block must be respected.

Sources: [PyInstaller operating model](https://pyinstaller.org/en/stable/operating-mode.html),
[official installation guide](https://pyinstaller.org/en/stable/installation.html).

## Versioned m037 profile

Add --profile m037 to the existing offline build command to select patches/m037.
It requires a schema-2 catalog/recipe/version set with matching source, catalog
and expected output hashes. Cross-schema mixtures, changed translations rebound
only to a recipe, unsupported sources and wrong output sizes are rejected.
No flag bypasses output verification. Omitting --profile still selects m020.

The original m020 files and exact output remain regression-locked. Production
installation remains disabled, and the m036 packaged candidate still contains
m020. New m037 outputs are private local build artifacts, never install/run them
as part of the build. See M037-COMBAT-UI.md for commands and validation details.
