# 🧩 WSL USB Buddy  
### Hardware Security Key Passthrough Manager for WSL (YubiKey / FIDO2)

---

## 📌 What is this?

**WSL USB Buddy** is a simple, user-friendly desktop application that allows Windows users to safely attach a hardware security key (such as a **YubiKey**) to **WSL (Windows Subsystem for Linux)** without using the command line.

It is designed for enterprise environments where:

- Hardware-backed authentication is required (FIDO2 / PIV)
- WSL must run with restricted or locked-down `sudo`
- Users are not Linux-savvy
- Automation platforms (ex: **Ansible**) require hardware-based authentication
- Security teams require:
  - auditability
  - least-privilege workflows
  - no persistent credential storage

---

## 🎯 Use Case

Attach a hardware security key from Windows into WSL so that Linux-based tools can authenticate using:

- SSH with FIDO2
- Smartcard / PIV
- GPG
- PAM integrations
- TACACS workflows
- Automation platforms (ex: Ansible)

Without exposing:

- private keys
- device configuration
- endpoint identity
- persistent device metadata

---

## 🖥️ Installer Application

The included **GUI Installer**:

✔ Displays an agreement screen describing all system changes  
✔ Allows the user to opt-in to installation steps  
✔ Shows installation progress with live logging  
✔ Deploys WSL USB Buddy to:

```
C:\yub\
```

✔ Optionally installs:

- `usbipd-win`
- WSL verification tools (`usbutils`, etc.)
- System tray support (`pystray`, `pillow`)

---

## 🟢🔵🔴 System Tray Status Indicator

Once installed, the launcher provides a tray icon indicating hardware key state:

| Color | Meaning |
|------|--------|
🔴 Red | No acceptable security device shared or attached |
🔵 Blue | Device is shared (bound) but not attached to WSL |
🟢 Green | Device is attached to WSL |

---

## 🧰 Application Features

From the GUI:

- 🔄 List supported USB security devices
- 🔓 Enable Sharing (usbipd bind)
- 🔒 Disable Sharing (usbipd unbind)
- ✅ Attach to WSL
- 🧹 Detach from WSL
- 🐧 Launch WSL as root (for secure automation workflows)
- 📍 Filter for acceptable hardware security devices only

No command-line interaction required.

---

## 🔐 Public-Safe / Stateless Design

This project is intentionally built to be safe for:

- internal deployment
- public GitHub release
- cross-organization sharing

It does **not** store:

❌ BUSIDs  
❌ device names  
❌ hardware identifiers  
❌ window state  
❌ user configuration  
❌ profiles  
❌ logs  

All device state exists **in memory only** for the duration of the session.

No personal or endpoint data is written to disk.

---

## 📋 Requirements

### Windows Host

- Windows 10 / 11
- WSL installed and running
- Python 3.x
- Administrator privileges (for USB passthrough)

---

### WSL Distribution

Debian / Ubuntu recommended

Required:
```
usbutils
```

Optional:
```
pcscd
scdaemon
libfido2-tools
```

---

## 🚀 Installation

### Step 1 – Run Installer (as Administrator)

Double-click:

```
run_installer_as_admin_tray.bat
```

Follow the on-screen prompts and accept the installation agreement.

---

### Step 2 – Launch Buddy

After installation:

```
C:\yub\run_wsl_usb_buddy_as_admin.bat
```

---

## 🧪 Verify Key Inside WSL

After attaching your device:

Inside WSL:

```bash
lsusb | grep -i yubico
```

---

## 🧹 Uninstall

### Windows

Run:

```powershell
.\3_windows_uninstall.ps1
```

Removes:

```
C:\yub\
Desktop shortcut (if present)
```

---

### WSL

Inside WSL:

```bash
sudo ./3_wsl_uninstall.sh
```

Removes:

- usbutils
- pcscd
- libfido2-tools
- optional dependencies

---

## ⚠️ Security Notes

- Private keys remain inside the hardware device
- No credentials are exported into Windows or WSL userspace
- USB passthrough is mediated via `usbipd`
- Device sharing must be enabled by an Administrator

---

## 📜 License

This project is licensed under:

```
GNU General Public License v3.0
```

See:

```
LICENSE
```
