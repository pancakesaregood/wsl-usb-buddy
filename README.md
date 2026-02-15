🧩 WSL USB Buddy

Stateless USB-to-WSL Attachment Tool for Security Keys (usbipd-win v4+)

Source: 

main

📌 Purpose

WSL USB Buddy is a public-safe GUI utility that allows administrators to:

Attach USB security devices (ex: YubiKeys) to WSL

Detach them back to Windows

Enable / disable USB sharing using usbipd

Launch WSL as root for privileged configuration tasks

This tool was created to support secure workflows such as:

✔️ Hardware-gated sudo
✔️ FIDO-backed authentication
✔️ YubiKey-protected Ansible execution
✔️ Secure network automation environments inside WSL
✔️ Zero-trust change-control pipelines

🔐 Security Design

This application is intentionally designed to be:

Feature	Status
Writes config to disk	❌ No
Stores device BUSIDs	❌ No
Saves device names	❌ No
Saves profiles	❌ No
Persistent state	❌ No
Telemetry	❌ No
Logging beyond session	❌ No

All operational state exists in-memory only for the current session.

This allows:

Safe public distribution

Compliance with locked-down enterprise environments

Use on regulated infrastructure (ex: healthcare networks)

No forensic residue of hardware device use

🧰 Requirements
Dependency	Version
Windows	10 / 11
Python	3.x
usbipd-win	v4+
WSL	Installed
Tkinter	Included w/ Python

Install usbipd:

winget install usbipd

🚀 Running the Application

Run from an elevated shell:

python main.py


⚠️ Administrator privileges are recommended
Bind / attach operations may fail without elevation.

🖥️ Interface Overview
Device Controls
Button	Function
🔄 Refresh	Updates USB device list
🔓 Enable Sharing	Runs usbipd bind
🔒 Disable Sharing	Runs usbipd unbind
✅ Attach to WSL	Runs bind + attach
🧹 Detach from WSL	Runs usbipd detach
🐧 Open WSL as root

Launches:

wsl.exe -u root


Used for:

PAM configuration

FIDO2 sudo setup

libfido2 / yubico-pam installation

Hardware-gated privilege workflows

🔎 Device Filtering

By default, the UI shows only:

Yubico VID:PID

Devices containing keywords:

yubikey

security key

fido

yubico

Vendor filter:

ALLOW_VIDPID_PREFIXES = ["1050:"]


Enable Show ALL Devices for troubleshooting.
