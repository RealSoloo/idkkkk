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

`Pf.txt` includes the pf-esp-5 update.

### Phantom Forces setup

1. Reload the updated main hub, select Phantom Forces, and deploy into a match.
2. In ESP, leave **Team Check** enabled. If team-group names are randomized,
   point directly at a known teammate and press **F6**, or at a known enemy and
   press **F7**. A successful calibration notification confirms the selection.
   The two existing team groups can then be classified without guessing their
   randomized names. Recalibrate after changing team or server. The calibration
   keys are configurable in Team Detection.
3. Enable ESP. With Team Check on, only confirmed enemies are shown.
4. Enable Aim Assist, select **Camera tracking**, and hold right mouse while a
   visible enemy is inside the FOV circle. Activation can also be set to Hold Key
   or Always On. Aim status reports missing targets and runtime errors.

Auto team detection recognizes known faction colors even when `Player.Team`
is nil. The Your team dropdown can specify a faction, but faction names alone
cannot identify randomized folders; use the calibration keys in that case.
Calibration requires a direct raycast hit on a visible player. If no player is
hit, it reports that and leaves existing calibration unchanged. It infers the
complementary team only when exactly two groups exist.

Camera tracking runs after the normal camera update and does not require a
mouse movement API. Optional Mouse movement reports missing or failing APIs.
Sticky targets are rechecked for team and range. ESP uses verified player names
when available; otherwise labels are Enemy, Teammate, or Unknown player rather
than randomized model IDs. Real usernames cannot be recovered from model IDs
alone. Randomized body-part names use geometric head/torso fallbacks.

Regression checks cover randomized 6/7-player groups, calibration, team filtering,
activation modes, camera writes, mouse API failures, labels, and render cleanup
using mocked game objects. Live Phantom Forces behavior still requires in-game
verification. Troubleshooting identifies this revision as `pf-esp-5`.
