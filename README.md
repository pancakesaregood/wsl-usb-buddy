# 🧩 WSL USB Buddy (Public-Safe / Stateless)

A dead-simple GUI launcher to manage **usbipd v4** device sharing and attach a **YubiKey / FIDO security key** from Windows into **WSL** — designed for enterprise environments where:

* Users are **not Linux-savvy**
* Security teams require **sudo lockdown inside WSL**
* Hardware-backed auth (FIDO2/PIV) is required for automation (e.g., Ansible)
* You want to **share this tool publicly** without leaking endpoint identifiers

---

## ✨ Features

From a friendly GUI:

* 🔄 Lists acceptable USB security devices (e.g., YubiKey)
* 🔓 **Enable Sharing** → `usbipd bind --busid X-Y`
* ✅ **Attach to WSL** → `bind` + `usbipd attach --wsl --busid X-Y`
* 🧹 **Detach from WSL** → `usbipd detach --busid X-Y`
* 🔒 **Disable Sharing** → `usbipd unbind --busid X-Y`
* 🐧 **Open WSL as root** → launches `wsl.exe -u root`

No command line required for end users.

---

## 🛡️ Public-Safe / Stateless Design

This build is intentionally **stateless** so it can be shared publicly:

* ❌ No config files
* ❌ No saved BUSIDs
* ❌ No saved device names
* ❌ No saved profiles
* ❌ No persistent logs
* ❌ No endpoint-identifying artifacts written to disk

All device data exists **in memory only** for the current session.

This prevents accidental disclosure of:

* USB topology fingerprints
* Security token serials (if exposed by OS descriptors)
* User-specific endpoint identifiers

---

## 🧱 Architecture

```
Windows Host
 ├─ usbipd-win (v4+)
 ├─ Python + Tkinter GUI
 └─ WSL USB Buddy
        │
        ├─ bind / unbind (sharing)
        └─ attach / detach (WSL)
                 │
                 ▼
              WSL Distro
              ├─ lsusb
              ├─ pcscd / scdaemon
              └─ libfido2-tools (optional)
```

---

## 📋 Requirements

### Windows Host

* Windows 10 / 11
* WSL already installed and running
* **usbipd-win v4+**
* Python 3.x (with `py.exe` launcher recommended)

### WSL (Debian / Ubuntu)

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

## 🚀 Install (Windows)

Open **PowerShell as Administrator**

### Step 1 – Install prerequisites

```
.\1_windows_prereqs.ps1
```

### Step 2 – Deploy launcher

Place:

```
yub_usb_buddy_public_safe_stateless_rootbutton.py
```

in the same folder as:

```
2_windows_deploy.ps1
```

Then run:

```
.\2_windows_deploy.ps1
```

This deploys to:

```
C:\yub\
 ├─ yub_usb_buddy_public_safe_stateless_rootbutton.py
 └─ run_wsl_usb_buddy_as_admin.bat
```

Launch:

```
C:\yub\run_wsl_usb_buddy_as_admin.bat
```

---

## 🐧 Install (WSL)

Inside your WSL distro:

### Step 1 – Install tools

```
chmod +x 1_wsl_prereqs.sh
sudo ./1_wsl_prereqs.sh
```

### Step 2 – Verify key visibility

(After attaching from GUI)

```
chmod +x 2_wsl_verify_key.sh
./2_wsl_verify_key.sh
```

Expected:

```
lsusb | grep -i yubico
```

---

## 🧑‍💻 Usage

1. Run:

```
C:\yub\run_wsl_usb_buddy_as_admin.bat
```

2. Plug in your security key

3. Click:

* **Enable Sharing**
* **Attach to WSL**

4. (Optional) Click:

* **Open WSL as root**

5. Verify inside WSL:

```
lsusb
```

---

## 🔐 Security Model

* No secrets are handled by this tool
* No FIDO private material is accessible to Windows or WSL userspace
* Hardware-backed authentication remains inside the token
* Sharing is mediated via `usbipd` kernel-level redirection

Enables:

* FIDO2 / PIV usage inside WSL
* Automation workflows (e.g., Ansible)
* Reduced requirement for sudo inside Linux
* Centralized policy enforcement on Windows host

---

## 🧰 Repository Layout

```
.
├─ yub_usb_buddy_public_safe_stateless_rootbutton.py
├─ 1_windows_prereqs.ps1
├─ 2_windows_deploy.ps1
├─ 1_wsl_prereqs.sh
├─ 2_wsl_verify_key.sh
├─ LICENSE
└─ README.md
```

---

## 🧯 Troubleshooting

### Attach fails

Ensure launcher was run **as Administrator**

Try:

* Enable Sharing → Attach to WSL again

---

### `lsusb` shows nothing

Check from Windows:

```
usbipd list
```

Device must show:

```
Attached
```

---

### Python launcher not found

Install Python from:

* python.org
* Microsoft Store

Re-run deploy script.

---

## 📜 License

This project is licensed under the terms of the:

**GNU General Public License v3.0**

See:

```
LICENSE
```

---

## 🤝 Contributing

Pull requests welcome for:

* Multi-distro attach support
* Auto-attach on insert
* Enterprise packaging (MSIX / Intune)
* Opt-in logging (non-default)

---

Happy automating 🔐
