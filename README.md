# WSL USB Buddy (Public-Safe / Stateless)

Small Tkinter desktop app for managing USB passthrough from Windows to WSL with `usbipd-win` (v4+).

This build is intentionally **stateless** and **public-safe**:
- No config file
- No saved profiles
- No persistent storage of BUSIDs, device names, window size, or history
- Session-only in-memory state

## Features

- Modernized desktop UI (cards, status chip, cleaner action layout)
- List USB devices from `usbipd list`
- Filter to "acceptable devices" by VID:PID prefix and keyword
- Optional toggle to show all devices for troubleshooting
- Optional toggle to auto-attach known devices during refresh
- Responsive device list:
  - Columns auto-scale with window width
  - Visible row count auto-fits the number of shown devices (within min/max limits)
- Enable sharing (`usbipd bind`)
- Disable sharing (`usbipd unbind`)
- Attach to WSL (`usbipd bind` + `usbipd attach --wsl`)
- Detach from WSL (`usbipd detach`)
- Open a new WSL terminal as root (`wsl.exe -u root`)
- System tray token monitor with color status:
  - Red: no security key detected on host
  - Blue: security key detected on host (not attached to WSL)
  - Green: security key attached to WSL
  - Minimizing the app hides it to the tray (no taskbar icon while hidden)
- Session log in the UI

## Requirements

- Windows with WSL installed
- `usbipd-win` v4 or newer available in `PATH`
- Python 3.x
- Tkinter (included with standard Windows Python installs)
- Optional (for tray icon): `pystray`, `Pillow`
- Recommended: run the app as **Administrator** for bind/attach/detach/unbind operations

## File

- Main app: `main.py`

## Run

From PowerShell in this folder:

```powershell
python .\main.py
```

If you want tray status icons, install:

```powershell
python -m pip install pystray Pillow
```

## Typical workflow

1. Click **Refresh**.
2. Select a USB device from the list.
3. Click **Enable Sharing** if needed.
4. Click **Attach to WSL**.
5. Use **Detach from WSL** when done.
6. Optionally disable sharing with **Disable Sharing**.

## Device filter behavior

By default, only devices matching one of these checks are shown:
- VID:PID starts with `1050:` (Yubico)
- Device name contains one of:
  - `yubico`
  - `yubikey`
  - `security key`
  - `fido`

Use **Show ALL devices (troubleshooting)** to bypass filtering.

## Notes

- Operations run in background threads to keep the UI responsive.
- Command failures are shown in popup dialogs and written to the log panel.
- Auto-attach targets known security token devices not currently attached to WSL.
- Auto-attach retries are throttled after failures to avoid repeated spam.
- Manual **Detach**/**Disable Sharing** for a BUSID temporarily blocks auto-attach for that BUSID until you manually attach it again or re-enable auto-attach.
- If tray dependencies are missing, tray features are disabled gracefully.
- This project does not write operational state to disk by design.

## Troubleshooting

- If operations fail with access errors, restart the app as Administrator.
- If `usbipd` is not found, ensure `usbipd-win` is installed and in `PATH`.
- If no device appears, enable **Show ALL devices** to verify detection.
