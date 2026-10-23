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

`Pf.txt` includes the pf-esp-4 update. ESP and aim assist share team detection.
If Roblox does not expose your faction, open **ESP → Team Detection → Your
team** and select **Phantoms** or **Ghosts**. Update that selection after
switching teams. Auto uses available player or local-character folder data.
Unknown-team models remain visible in gray ESP but are excluded from aim
assist until their relationship can be resolved. Leave **Treat Everyone As
Enemy** off to keep team filtering.

The update handles nested faction folders and servers where only opponents
have a replicated faction folder. Team logic and rendering regression checks
passed with mocked game objects. Live Phantom Forces behavior still requires
in-game verification. The troubleshooting row identifies this as `pf-esp-4`.
