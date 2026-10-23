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

`Pf.txt` includes the pf-esp-3 update: shared team resolution for ESP and aim
assist, Phantoms/Ghosts and blue/orange folder aliases, and safer rendering.
Leave **Treat Everyone As Enemy** off to use team filtering. Unresolved teams
are excluded from targeting instead of automatically treated as enemies.
Logic checks passed; behavior inside a live Phantom Forces match has not been
verified in this environment.
