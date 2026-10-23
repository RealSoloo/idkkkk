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
