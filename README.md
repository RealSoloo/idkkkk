# Solos Key Manager

A dark purple desktop dashboard for managing your Cloudflare worker keys.

## Run

Use Python 3.10 or newer with Tk support (included with standard Windows Python).
From this directory:

```sh
python -m pip install -r requirements.txt
python run.py
```

`run.py` loads the original `App` and `Api` files, so their uploaded names can stay unchanged.
On Linux, Tk and a graphical desktop/display are required.

Enter your actual Cloudflare worker URL and admin token, then select Connect.
The default workers.dev address is a placeholder. Credentials are not included.
Remember connection stores the token locally in `~/.solos_key_manager.json`;
leave it unchecked on shared machines.

Click a key or Copy to copy its full value, including when the table shortens
long keys. Search, status filters, duration presets, permanent keys, reset,
revoke, and F5 refresh remain available.

If your local files are named `app.py` and `api.py`, keep those names and launch
with `python app.py`. Keep `code_workspace.py` and `lua_preview.py` beside them. For editor updates,
replace `code_workspace.py`, `lua_preview.py`, and `requirements.txt`, then run
`python -m pip install -r requirements.txt` before restarting.

## Local code workspace

Select **Code Workspace** in the top bar. It works offline, without connecting
an API. Use **Open files** for existing `.txt`, `.lua`, `.luau`, Python, or other
UTF-8/UTF-16 text files, or **New** to paste code into a blank tab. **Open folder**
shows a local folder; double-click a file to edit it or a folder to browse it.

Each file opens in a separate tab with line numbers, undo/redo, horizontal
scrolling, syntax colors, current-line shading, and automatic indentation.
The explorer, scrollbars, search controls, and Problems panel use the app's
dark purple palette. Choose a language in the toolbar; `.txt` and new files
default to Luau for the hub scripts (select Plain text for notes).

After a short typing pause, local parsers check Luau, Python, and JSON syntax.
Errors underline the affected code and mark its line number red. Select an
entry in **Problems** to jump to it. Luau checks support Roblox type annotations
and `continue`. JavaScript has highlighting only. These checks do not execute
code, validate Roblox APIs, or detect runtime/logic errors. Install the updated
`requirements.txt` to enable highlighting and Luau parsing; missing packages
are reported prominently as **CHECKER / HIGHLIGHTING UNAVAILABLE** rather than
zero errors. **Check code** requests an immediate check. **Check setup** tests
Luau coloring and error detection, then copies a report with the editor revision,
loaded file path, Python interpreter, and dependency versions. Document contents
are excluded from that report. This helps identify stale copies or dependencies
installed for a different Python interpreter.

**Save**, **Save as**, and **Save all**
write to your computer. Files are not uploaded, synced to GitHub, or executed.
Use **+ Workspace** to create a named group such as LT2 or Phantom Forces.
Select a group in the sidebar, then **+ Add** to keep local files in its Files
list. Closing an editor tab keeps the file in that list; double-click to reopen
it. Removing a file from the list does not delete it from disk. **Rename** changes
the group's name. Each group remembers its own open tabs, selected tab, languages,
cursor positions, folder, and drafts. The Text size menu changes the editor font.

Workspace data and draft copies are stored locally in
`~/.solos_code_workspace.json`. Edits are backed up after a short pause and on
normal app exit. Switching groups also saves their state. **Save** still writes
to the original script file; workspace draft storage is separate. On restart,
clean files are read from disk and drafts recover the previous text. Saving a
recovered draft still detects external changes before replacing the original.
Keep this local session file if you move the app to another computer; file paths
may need to be reopened on that computer. Abrupt shutdown can lose edits made
since the last successful workspace save.

Shortcuts: Ctrl+N new, Ctrl+O open, Ctrl+S save, Ctrl+Shift+S save as,
Ctrl+W close tab, Ctrl+F find, Ctrl+Z undo, Ctrl+Shift+Z redo. Find next wraps
around and matches literal text without case sensitivity.

A `*` marks edits not yet saved to the original file. Closing a changed tab
prompts to save, discard, or cancel. Exiting keeps tabs and drafts for the next
launch without those prompts. A workspace-save failure blocks normal exit so
you can save your files. Files changed by another program prompt before replacement.
Saves preserve UTF encoding/BOM and the detected newline style; edited files
with mixed newline styles are normalized to that style. Save failures leave
the tab open. The app also remembers whether you last used Key Manager or Code Workspace.

Run the editor checks with `python -m unittest discover -s tests -p test_code_workspace.py`.
GUI checks require a display (for example Xvfb on headless Linux).

## Visual Lua preview

Click **Preview** in the editor toolbar to open a pane beside the code. Drag the
vertical divider to resize it; **Hide preview** gives the space back to the
editor. The choice is remembered between launches. Use **Example** in the preview
to create a new, unsaved sample UI without replacing your current script.

The preview refreshes after a short pause while editing Luau. It reads
`Instance.new`, the hub's `new(class, props, parent)`, `Label` and `Row` helpers,
and direct property assignments. Frames, labels, buttons, text boxes, scale/offset
sizes and positions, anchor points, colors, visibility, corners, strokes, padding,
and simple horizontal/vertical list layouts are approximated on a 720×480 canvas.
Roblox image assets use placeholders. Click a previewed element to locate the
line that created it.

For Solos Hub game modules, `Hub.GamePanel`, `Panel.Sub`, `Section`, `Collapse`,
`Button`, `Toggle`, `Slider`, `Dropdown`, `Input`, `Keybind`, and `InfoRow` produce
an approximate control layout. Select a page in the preview dropdown; LT2's Wood,
Logs, Plot, Shop, Tools, Vehicle, World, and Protection pages are supported.

This is a static preview, not a Roblox runtime. It never executes Lua, callbacks,
network requests, or game actions. Function-built/conditional/loop-created UI,
complex expressions, constraints, clipping, rich-text formatting, and animations
are not reproduced exactly. Runtime values use defaults; the pane reports partial
or unsupported content. Use Roblox Studio for a full runtime preview.

## App icon

Click **App icon** in the top bar and choose a PNG/GIF image or, on Windows,
an ICO file. The app keeps a local copy beside its settings and reapplies it
on launch. PNG/GIF images also appear in the header. PNG is the simplest choice
for an existing script logo. Icon selection does not upload the image.

This changes the running app's window icon. Windows taskbar display also depends
on Windows and any pinned shortcut; a Python script's Explorer file icon or a
separate shortcut/executable icon is not changed by this setting.

## Solos Hub scripts

The main hub is `Soloshub.txt`. Its game-module links load the files in this
repository's `main` branch: `Arsenal.txt`, `Bab.txt`, `Doomspire.txt`, `Lt2.txt`,
`Mm2.txt`, and `Pf.txt`. `INFO.txt` is the supplied reference document.
The icon sprite sheet still loads from its original SolosHub repository.

Update these same files in place for later releases. Reload the hub after
updating a module. Updating a file does not change an already running session.

`Pf.txt` includes the pf-esp-10 update.

### Automatic teammate calibration

Team detection is built into Phantom Forces and runs automatically; there is
no toggle or configuration step. When the crosshair briefly passes over a
teammate and the game displays **Friendly** for about 0.2 seconds, it calibrates
the team groups. The module uses that native HUD indicator and the existing crosshair
body picker to calibrate the teammate group automatically; no F6 press is needed.
**Enemy** text never calibrates a group. Conflicting or hidden indicators, this
hub's own labels, and text away from the crosshair are excluded. Changing the
body under the crosshair restarts the short confirmation period.

The automatic status line explains whether it is waiting for the Friendly
indicator, a character body, or confirmation. This requires readable native
Friendly text near the crosshair in PlayerGui; text drawn outside that GUI is
not available to this reader. Regression checks pass; live HUD recognition
still needs user verification. F6 remains a manual fallback already verified by
the user. Mouse movement remains the default working aim method.

### Phantom Forces automatic teams and names

Reload the updated hub, select Phantom Forces, and open the game's leaderboard
for a moment. The new reader uses the Phantoms/Ghosts columns to build a team
roster from exact usernames or unique display names. It excludes this hub's UI
and expires a hidden scoreboard snapshot after 20 seconds to avoid indefinitely
using stale teams. Available native team colors remain a fallback.

In **ESP → Team Detection**, the roster and model-owner status lines explain
which data was found. **Refresh leaderboard teams** forces an immediate retry
while the leaderboard is open. Keep **Team Check** enabled to show confirmed
enemies only. Then enable Aim Assist with **Mouse movement** and hold right
mouse near a visible enemy in the FOV circle.

The scoreboard provides player-to-team information, not character ownership.
Where the game's shared runtime exposes its `ReplicationInterface`, the module
uses its existing entry/third-person character references to map actual Player
objects to randomized Models. Only verified Model references are accepted.
This supports real display names and propagates consistent known teams across
a randomized team folder. Conflicting folder evidence stays unresolved. No
name is guessed from model IDs, scoreboard order, or player counts.

This bridge is conditional on the runtime exposing a supported replication
interface. If unavailable, the status line says so; a leaderboard roster alone
cannot map arbitrary bodies to usernames. Native character ownership and
manual team calibration remain fallbacks. Copy the diagnostic report if the
owner count is zero or the interface is unavailable; live runtime confirmation
is still required.

### Optional manual calibration

For randomized folders without a model-owner link, center a known teammate and
press F6, or a known enemy and press F7. Calibration uses normal raycasts plus
body-box intersection and a small 16-pixel margin. It infers the complementary
team only when exactly two groups exist. Recalibrate after changing team/server.

Mouse movement is the default tracking method after the user verified it works
in a live match. Camera tracking selected targets but did not move the user's
view, so it remains an optional alternative. Mouse movement reports missing or
failing APIs.
Sticky targets are rechecked for team and range. ESP uses verified player names
when available; otherwise labels are Enemy, Teammate, or Unknown player rather
than randomized model IDs. Real usernames cannot be recovered from model IDs
alone. Randomized body-part names use geometric head/torso fallbacks.

Regression checks cover leaderboard parsing and expiry, verified ownership lookup,
randomized 6/7-player groups, calibration, team filtering,
activation modes, camera writes, mouse API failures, labels, and render cleanup
using mocked game objects. The user confirmed live F6 team calibration and
mouse aiming work; automatic username/model lookup remains unverified. Troubleshooting identifies this revision as `pf-esp-10`.

## LT2 additions

`Lt2.txt` now includes more features adapted from the supplied Dynxe source,
using the existing LT2 pages and hub controls:

- **Tools:** lasso selection, pyramid sorting, wood/length group matching,
  Select All My Planks, and Select All My Loose Items.
- **Plot:** owned-plank wood/length filters, click-to-fill, and fill-all blueprints.
- **Shop:** selected/all-missing blueprint purchases and the Rukiryaxe quest.

See [LT2_FEATURES.md](LT2_FEATURES.md) for controls, source scope, validation and
live-game limitations. Stop and unload cancel the new operations. No new GUI
framework or remote script loader is introduced.

### Own-character body part editor

Reload Solos Hub and open **Player → Body Part Editor**. Enable **Body Editing**,
select a body part, and expand Size, Position, or Rotation. Width/height/depth
range from 25–300% of the original size; offsets range from -5 to +5 studs per
axis (10 slider units = 1 stud); rotation ranges from -180° to +180°. An outline
marks the selected part. Settings are kept separately for each edited part.

Movement uses the original Motor6D joint offset, so limbs stay attached; moving
an upper limb can also move parts joined beneath it. The HumanoidRootPart and
accessory/tool handles are excluded. **Reset Selected** restores one part;
**Reset All**, disabling editing, respawning, and unloading restore tracked edits.
Editing starts disabled and is never automatically applied to a new character.
Use **Refresh Body Parts** if the list was populated before spawning completed.

These are local character edits, not a guarantee of replication to other players.
Games can override changes, and resizing can affect movement/collisions. Parts
without a Motor6D support resizing but report that joint movement is unavailable.
Five mock regression tests cover R6/R15, ownership checks, relative edits, and
cleanup (`PYTHONPATH=... python tests/test_body_editor.py`, with `lupa` installed).
Full hub Luau parsing passes; live Roblox behavior still needs verification.

### Game loading recovery

The reported HTTP 404 was caused by the repository being private; making it
public restored game loading. The shared downloader retains its request / HttpGet
fallback. The temporary **Copy Module Error** card and visible URL report have
been removed. Failures show a short notification; technical details stay in the
console. Removing these links does not make a public repository's source private.

### Standalone hub for private repositories or blocked downloads

Use **SoloshubStandalone.txt** when Roblox receives 404 for module URLs. Download
it while signed into GitHub, then run its contents in place of Soloshub.txt.
It includes all six game scripts and selects them locally; game-module loading
makes no network requests. Key validation and other existing online features
still use their usual services. Never put a GitHub token into the client script.

`Soloshub.txt` remains the modular version. If its downloads fail, it also checks
the executor workspace for `SolosHub/mod_<id>.lua` (for example `mod_lt2.lua`).
A private repository can return 404 to anonymous clients despite being accessible
to the repository owner. No repository visibility changes are made here.

After editing the hub or any game module, run `python scripts/build_standalone.py`
to regenerate the standalone file, then download the new version. It does not
fetch future module updates automatically. The loader tests verify that all six
bundled sources match their originals and load without requesting the network.

### Build a Boat: local build library and placement preview

Open **Build A Boat → Build Library**. The existing hub layout and farming tools
are unchanged. Files live in the executor's **SolosHub/Babft Builds** folder.
Capture a source team's plot (your own or a build its creator has shared), enter
a name under **Save as**, and load it from **Saved builds** on a later session.
Existing filenames are never overwritten. Shared files must use this library's
versioned JSON format; arbitrary scripts and other hubs' save formats are not run.

**Show Preview** draws translucent, anchored, non-colliding parts on your own
team's plot. X/Y/Z sliders or **Exact offset** move it; **Rotation** rotates the
whole build around the source plot's origin. Both preview and building use the
same plot-relative transforms, including the plot's rotation. Red geometry means
at least one corner is outside the plot or below the surface, and prevents building.
The preview clears on respawn, team/plot change or unload. Limits: 3,000 parts,
8 MB per file, and ±100 studs of horizontal offset / 0–100 studs of added height.

The initial auto-builder supports **standard, unscaled, unpainted block geometry**.
It is **not live verified**. Because no known working building source was supplied,
it learns a restricted native placement call instead of sending guessed requests:

1. Click **Learn Building Tool** and place one plain, anchored block with the
   game's normal building tool. It must report **Learned <block type>**. Repeat
   for each required type; learning is session-local.
2. Capture/load a build, show its preview, and adjust its placement.
3. **Check Build** verifies learned shapes, inventory counts and plot bounds.
4. **Build At Preview** sends one placement at a time using the observed format,
   then verifies the new block's position, orientation, size and appearance.
   A rejection or mismatch stops the job without retries. **Stop Building** stops
   subsequent placements; already placed blocks remain, and an in-flight remote
   call cannot be recalled. Placement controls are frozen while a job runs.

Learning requires executor `hookmetamethod` and `getnamecallmethod` support, a
`BuildingTool` RemoteFunction, readable unambiguous inventory values, and the
recognized seven-argument native format. A different live format is rejected,
not silently treated as compatible. Saving needs the normal executor file APIs.
Capture recognizes block Models with a direct `PPart` on a team's named zone.
Unrecognized structures and mesh geometry are rejected rather than approximated.
Scaled/painted geometry may be previewed but cannot be built unless it matches a
learned native block. Wiring, engines, constraints and tool settings are not saved.
This is a first standard-block builder, not a complete arbitrary-boat copier.

`tests/test_bab_builds.py` runs the actual library in mocked Roblox/file/tool
services. It checks rotated-plot preview/build parity, corner bounds, JSON and
path validation, native-call learning, inventory/shape checks, mismatch stopping,
control locking, and cleanup. These checks do not verify the live game's API.
