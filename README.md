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

## Solos Hub scripts

The main hub is `Soloshub.txt`. Its game-module links load the files in this
repository's `main` branch: `Arsenal.txt`, `Bab.txt`, `Doomspire.txt`, `Lt2.txt`,
`Mm2.txt`, and `Pf.txt`. `INFO.txt` is the supplied reference document.
The icon sprite sheet still loads from its original SolosHub repository.

Update these same files in place for later releases. Reload the hub after
updating a module. Updating a file does not change an already running session.

`Pf.txt` includes the pf-esp-7 update.

### Phantom Forces automatic teams and names

Reload the updated hub, select Phantom Forces, and open the game's leaderboard
for a moment. The new reader uses the Phantoms/Ghosts columns to build a team
roster from exact usernames or unique display names. It excludes this hub's UI
and expires a hidden scoreboard snapshot after 20 seconds to avoid indefinitely
using stale teams. Available native team colors remain a fallback.

In **ESP → Team Detection**, the roster and model-owner status lines explain
which data was found. **Refresh leaderboard teams** forces an immediate retry
while the leaderboard is open. Keep **Team Check** enabled to show confirmed
enemies only. Then enable Aim Assist with **Camera tracking** and hold right
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

Camera tracking runs after the normal camera update and does not require a
mouse movement API. Optional Mouse movement reports missing or failing APIs.
Sticky targets are rechecked for team and range. ESP uses verified player names
when available; otherwise labels are Enemy, Teammate, or Unknown player rather
than randomized model IDs. Real usernames cannot be recovered from model IDs
alone. Randomized body-part names use geometric head/torso fallbacks.

Regression checks cover leaderboard parsing and expiry, verified ownership lookup,
randomized 6/7-player groups, calibration, team filtering,
activation modes, camera writes, mouse API failures, labels, and render cleanup
using mocked game objects. Live Phantom Forces behavior still requires in-game
verification. Troubleshooting identifies this revision as `pf-esp-7`.
