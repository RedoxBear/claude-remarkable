# claude-remarkable

A Python library for the reMarkable 2 tablet. Push PDFs to your device, pull annotated documents back, and render handwritten annotations as overlays — all without cloud lock-in.

Works over **USB SSH**, **WiFi SSH**, or **reMarkable Connect** (cloud subscription).

---

## Table of Contents

1. [What it does](#what-it-does)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Step 1 — Connect your device](#step-1--connect-your-device)
   - [USB (Mac)](#usb-mac)
   - [USB (Linux)](#usb-linux)
   - [USB (Windows)](#usb-windows)
   - [WiFi](#wifi)
   - [Verify the connection](#verify-the-connection)
5. [Step 2 — SSH access](#step-2--ssh-access)
6. [Step 3 — Using the CLI](#step-3--using-the-cli)
   - [SSH commands](#ssh-commands)
   - [Connect commands](#connect-commands)
7. [Step 4 — Using the Python API](#step-4--using-the-python-api)
8. [reMarkable Connect (cloud)](#remarkable-connect-cloud)
9. [Troubleshooting](#troubleshooting)
10. [Project status](#project-status)

---

## What it does

| Feature | SSH | Connect |
|---------|-----|---------|
| List documents | ✅ | ✅ |
| Push PDF to device | ✅ | ✅ |
| Pull original PDF | ✅ | ✅ |
| Pull annotation strokes (.rm) | ✅ | ✅ |
| Render annotations onto PDF | ⏳ Phase 2 | ⏳ Phase 2 |
| Works without internet | ✅ | ❌ |
| Works without USB cable | ✅ (WiFi) | ✅ |

---

## Requirements

- Python 3.10 or later
- reMarkable 2 tablet (firmware 3.x or later)
- USB-C cable **or** WiFi network shared with your computer
- For reMarkable Connect: an active Connect subscription

---

## Installation

```bash
pip install claude-remarkable
```

To install from source:

```bash
git clone https://github.com/bdcl/claude-remarkable
cd claude-remarkable
pip install -e ".[dev]"
```

Verify the install:

```bash
rm-bridge --version
```

---

## Step 1 — Connect your device

The reMarkable 2 exposes a USB network interface when connected via USB-C. Your computer sees it as a wired network adapter with the device at IP `10.11.99.1`.

> **Note:** The device uses RNDIS (Remote NDIS) for USB networking. This works out of the box on Linux and Windows, but requires an extra step on Mac.

---

### USB (Mac)

macOS does not include an RNDIS driver. You have two options:

**Option A — HoRNDIS (recommended)**

HoRNDIS is an open-source RNDIS driver for macOS.

1. Download the latest release from [https://github.com/jwise/HoRNDIS/releases](https://github.com/jwise/HoRNDIS/releases)
2. Open the `.pkg` installer and follow the prompts
3. Go to **System Settings → Privacy & Security** and approve the kernel extension if prompted
4. Restart your Mac
5. Plug in the reMarkable 2 via USB-C
6. Open **System Settings → Network** — you should see a new "RNDIS" or "USB Ethernet" adapter appear

**Option B — SSH over WiFi instead**

If you prefer not to install a kernel extension, skip USB and use WiFi (see [WiFi](#wifi) below). WiFi SSH works identically to USB SSH.

---

### USB (Linux)

RNDIS is built into the Linux kernel. No extra setup required.

1. Plug in the reMarkable 2 via USB-C
2. A new network interface will appear (usually `usb0` or `enp0s20f0u1`)
3. It should auto-configure with DHCP, giving your machine an address in the `10.11.99.x` range

If the interface appears but has no IP address, assign one manually:

```bash
sudo ip addr add 10.11.99.2/29 dev usb0
sudo ip link set usb0 up
```

---

### USB (Windows)

Windows 10 and 11 include RNDIS support natively.

1. Plug in the reMarkable 2 via USB-C
2. Windows will install the driver automatically
3. Open **Device Manager** — look for "Remote NDIS Compatible Device" under Network Adapters
4. If it shows a yellow warning icon, right-click → Update driver → Search automatically

---

### WiFi

1. On the reMarkable 2: swipe down from the top → **Settings → WiFi**
2. Connect to the same network as your computer
3. Go to **Settings → Help → Copyrights** and scroll to the bottom — the device IP address is shown there
4. Note that IP address. You will use it in place of `10.11.99.1` in all commands below

---

### Verify the connection

Once connected (USB or WiFi), confirm the device is reachable:

```bash
ping -c 3 10.11.99.1
```

Expected output:

```
PING 10.11.99.1: 56 data bytes
64 bytes from 10.11.99.1: icmp_seq=0 ttl=64 time=1.2 ms
...
```

If ping fails, see [Troubleshooting](#troubleshooting).

---

## Step 2 — SSH access

The reMarkable 2 runs Linux and has SSH enabled by default. The default user is `root` with no password.

**Find your SSH password:**

Go to **Settings → Help → Copyrights** on the device. The SSH password is shown near the bottom of that screen.

> Some firmware versions show a password, others allow passwordless root login. Try connecting without a password first.

**Test the connection:**

```bash
ssh root@10.11.99.1
```

You should see a shell prompt like:

```
root@remarkable:~#
```

Type `exit` to leave. You are now ready to use `rm-bridge`.

---

## Step 3 — Using the CLI

### SSH commands

All SSH commands accept `--host` (default: `10.11.99.1`) and optionally `--key` (path to SSH private key) or `--password`.

**List documents on the device:**

```bash
rm-bridge ssh list
```

Output:

```
3f4a1b2c-...  'My Research Paper'  (12p, pdf)
8e9d0c1a-...  'Meeting Notes'      (3p, pdf)
```

**Push a PDF:**

```bash
rm-bridge ssh push my_paper.pdf
```

The document title defaults to the filename. Override it:

```bash
rm-bridge ssh push my_paper.pdf --title "Q1 Research"
```

> The device screen will go blank briefly while xochitl (the reMarkable UI) restarts. This is normal — it takes 5–10 seconds.

**Pull a document back (by UUID):**

```bash
rm-bridge ssh pull 3f4a1b2c-...
```

Saves as `3f4a1b2c-....pdf` in the current directory. Set a custom output path:

```bash
rm-bridge ssh pull 3f4a1b2c-... --out annotated_paper.pdf
```

**Show device info:**

```bash
rm-bridge ssh info
```

Output:

```json
{
  "serial": "RM110-...",
  "os_version": "3.x.x.x (kirkstone)",
  "host": "10.11.99.1",
  "xochitl_conf_preview": "..."
}
```

**Using WiFi instead of USB:**

Add `--host` with the device's WiFi IP:

```bash
rm-bridge ssh list --host 192.168.1.42
```

---

### Connect commands

reMarkable Connect gives cloud access to your documents without needing the device nearby.

**One-time setup — register this computer:**

1. Open [https://my.remarkable.com/device/desktop/connect](https://my.remarkable.com/device/desktop/connect) in your browser (log in if prompted)
2. You will see an 8-character one-time code (e.g., `ab12cd34`)
3. Run:

```bash
rm-bridge connect register ab12cd34
```

This saves a permanent device token to `~/.rm_bridge/tokens.json`. You only do this once.

**List documents:**

```bash
rm-bridge connect list
```

**Push a PDF to the cloud:**

```bash
rm-bridge connect push my_paper.pdf --title "My Paper"
```

The document will appear on your reMarkable 2 after its next sync.

**Pull a document:**

```bash
rm-bridge connect pull 3f4a1b2c-...
```

---

## Step 4 — Using the Python API

### SSH

```python
from rm_bridge import ReMarkable

# Connect over USB (default IP)
with ReMarkable.over_ssh(host="10.11.99.1") as rm:

    # List all documents
    docs = rm.list_documents()
    for doc in docs:
        print(f"{doc.uuid}  {doc.title}  ({doc.page_count} pages)")

    # Push a PDF
    doc = rm.push_pdf("paper.pdf", title="My Paper")
    print(f"Pushed: {doc.uuid}")

    # Pull a document back
    pdf_bytes = rm.pull_document(doc.uuid)
    with open("pulled.pdf", "wb") as f:
        f.write(pdf_bytes)

    # Pull raw annotation strokes (Phase 2: these will be rendered)
    annotations = rm.pull_annotations(doc.uuid)
    for page, rm_bytes in annotations.items():
        print(f"Page {page}: {len(rm_bytes)} bytes of stroke data")
```

### reMarkable Connect

```python
from rm_bridge import ReMarkable

# First-time only: register with a code from my.remarkable.com/device/desktop/connect
rm = ReMarkable.from_connect()
rm.register("ab12cd34")

# Subsequent sessions
with ReMarkable.from_connect() as rm:
    docs = rm.list_documents()
    doc = rm.push_pdf("paper.pdf", title="My Paper")
```

---

## reMarkable Connect

### Token storage

After `register()`, a permanent device token is saved to:

```
~/.rm_bridge/tokens.json
```

This file gives full access to your reMarkable account. Treat it like a password — do not commit it to version control.

### Token refresh

User tokens expire every 24 hours. The library refreshes them automatically on each `connect()` call using the stored device token.

### Custom token path

If you want to store tokens elsewhere (e.g., for multiple accounts):

```bash
rm-bridge connect register ab12cd34 --token-path ~/.rm_bridge/work_tokens.json
rm-bridge connect list --token-path ~/.rm_bridge/work_tokens.json
```

```python
from pathlib import Path
from rm_bridge import ReMarkable

with ReMarkable.from_connect(token_path=Path("~/.rm_bridge/work_tokens.json").expanduser()) as rm:
    docs = rm.list_documents()
```

---

## Troubleshooting

### Ping to 10.11.99.1 fails

- **Mac**: Confirm HoRNDIS is installed and approved in Privacy & Security. Try unplugging and replugging the cable.
- **Linux**: Run `ip link` and check if a `usb0` interface exists. If yes but no IP, assign one manually (see [USB Linux](#usb-linux)).
- **All**: Try a different USB-C cable. Some cables are charge-only and carry no data.
- **Alternative**: Switch to WiFi (see [WiFi](#wifi)).

### SSH connection refused

- The device may be asleep. Press the power button once to wake it.
- Confirm SSH is enabled: **Settings → Security → SSH**.

### SSH "Host key verification failed"

The device key changed (common after a firmware update). Remove the old key:

```bash
ssh-keygen -R 10.11.99.1
```

Then reconnect. Accept the new host key when prompted.

### "Permission denied" on SSH

- Try without a password first: `ssh root@10.11.99.1`
- If that fails, find the password at **Settings → Help → Copyrights** and pass it:

```bash
rm-bridge ssh list --password YOUR_PASSWORD
```

### Document appears on device but is blank / won't open

This usually means xochitl was interrupted mid-restart. On the device, go to the document and tap it — it may need a moment to load. If it stays blank, try:

```bash
ssh root@10.11.99.1 "systemctl restart xochitl"
```

### reMarkable Connect: "No device token found"

Run the one-time registration:

```bash
rm-bridge connect register <code>
```

Get the code from [https://my.remarkable.com/device/desktop/connect](https://my.remarkable.com/device/desktop/connect).

### reMarkable Connect: authentication errors after working previously

Your device token may have been invalidated (e.g., you removed this device from your account). Re-register:

```bash
rm-bridge connect register <new-code>
```

---

## Project status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | SSH transport + reMarkable Connect auth | ✅ Complete (`v0.1.1`) |
| 2 | Pull annotation strokes + render onto PDF | ⏳ Planned |
| 3 | MCP server (Claude integration) | ⏳ Planned |
| 4 | GitHub release + pip publish | ⏳ Planned |

Architecture decisions are logged in [docs/adr/](docs/adr/).

---

## License

MIT
