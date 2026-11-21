# Installation Guide

This guide covers deploying `hailo_bridge.py` as a hardened `systemd` service alongside `hailo-ollama` and connecting it to Open WebUI.

## 1. Prerequisites

* A Linux host (such as a Raspberry Pi 5 with a Hailo AI HAT+ 2) running `hailo-ollama` (default `http://127.0.0.1:8000`) with compiled `.hef` models loaded.
* Python `3.10+` with `venv` and `pip` installed (`sudo apt install python3-venv python3-pip`).
* SQLite compiled with FTS5 enabled (standard in modern Python builds; if unavailable, the bridge automatically falls back to a keyword scan).
* An Open WebUI instance with `ENABLE_FORWARD_USER_INFO_HEADERS=True` configured so `x-openwebui-chat-id` headers are forwarded for per-chat recall, `/forget`, and `/save`.

## 2. Create Service User & Directories

The provided `hailo-bridge.service` runs under a dedicated unprivileged `hailo-bridge` system user with `ProtectSystem=strict` and `ProtectHome=true`. Create the user, application directory, and persistent bank directory:

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin hailo-bridge

sudo mkdir -p /opt/hailo-bridge /var/lib/hailo-bridge/banks
sudo chown -R hailo-bridge:hailo-bridge /opt/hailo-bridge /var/lib/hailo-bridge
```

> **Note:** `/run/hailo-bridge` (used for `CHATS_DIR=/run/hailo-bridge/chats`, the SQLite FTS5 index, and `debug.log`) is created automatically on `tmpfs` by `RuntimeDirectory=hailo-bridge` in the `systemd` unit.

## 3. Clone Repository & Install Python Dependencies

Clone the repository into `/opt/hailo-bridge` and set up a virtual environment:

```bash
sudo -u hailo-bridge git clone https://github.com/varchild/hailo-bank-switching-bridge.git /opt/hailo-bridge

sudo -u hailo-bridge python3 -m venv /opt/hailo-bridge/venv
sudo -u hailo-bridge /opt/hailo-bridge/venv/bin/pip install --upgrade pip
sudo -u hailo-bridge /opt/hailo-bridge/venv/bin/pip install fastapi uvicorn httpx
```

## 4. Install & Start the `systemd` Service

Copy `hailo-bridge.service` to `/etc/systemd/system/`, reload `systemd`, and enable the service:

```bash
sudo cp /opt/hailo-bridge/hailo-bridge.service /etc/systemd/system/hailo-bridge.service
sudo systemctl daemon-reload
sudo systemctl enable --now hailo-bridge.service
```

Verify that the bridge is running and initialized cleanly:

```bash
sudo systemctl status hailo-bridge.service
journalctl -u hailo-bridge.service -n 50 --no-pager
curl -s http://127.0.0.1:5001/hailo/ram | python3 -m json.tool
```

## 5. Add Curated Memory Banks (Optional)

Place `.txt` knowledge banks in `/var/lib/hailo-bridge/banks/` and ensure they are readable (and writable for `/save`) by the `hailo-bridge` user:

```bash
sudo tee /var/lib/hailo-bridge/banks/example.txt > /dev/null <<'EOF'
Example hardware and network reference
---
- Inference host runs hailo-ollama on port 8000.
- Bridge listens on port 5001.
EOF

sudo chown -R hailo-bridge:hailo-bridge /var/lib/hailo-bridge/banks
```

Banks are rescanned automatically every `BANK_RESCAN_SECONDS` (default `5` seconds).

## 6. Connect Open WebUI

1. In Open WebUI, navigate to **Admin Panel → Settings → Connections**.
2. Add or edit an **Ollama** connection and set its URL to `http://<bridge-host>:5001` (e.g., `http://127.0.0.1:5001` or `http://hal-9001.lan:5001`).
3. Ensure `ENABLE_FORWARD_USER_INFO_HEADERS=True` is set in your Open WebUI environment (such as your Docker Compose `environment:` block) and restart Open WebUI if changed.
4. Start a chat and verify that `/hailo/index` and `/hailo/ram` reflect active session tracking.

## 7. Configuration Reference

All settings are configured via environment variables in `/etc/systemd/system/hailo-bridge.service`:

| Variable | Unit Value | Code Default | Description |
| :--- | :--- | :--- | :--- |
| `HAILO_UPSTREAM` | `http://127.0.0.1:8000` | `http://127.0.0.1:8000` | Upstream `hailo-ollama` endpoint. |
| `BANKS_DIR` | `/var/lib/hailo-bridge/banks` | `/home/kosh/banks` | Directory for shared and `/save`-written `.txt` banks. |
| `CHATS_DIR` | `/run/hailo-bridge/chats` | `/dev/shm/hailo-banks/chats` | RAM-backed (`tmpfs`/`ramfs`) directory for per-chat archives and ledgers. |
| `HEF_CONTEXT_TOKENS` | *(default)* | `2048` | Compiled context window ceiling of the HEF model. |
| `MAX_PROMPT_TOKENS` | `1300` | `1300` | Maximum tokens allocated to system prompt, banks, recall, and chat turns. |
| `DYN_BANK_MAX_TOKENS` | `500` | `250` | Maximum token size of the consolidated `session.txt` ledger per chat. |
| `CONSOLIDATE_PROMPT_TOKENS` | `1500` | `1500` | Prompt token budget for background fact-extraction calls. |
| `CONSOLIDATE_MIN_TOKENS` | `500` | `200` | Queued evicted tokens required before triggering background consolidation. |
| `CONSOLIDATE_MAX_WORDS` | `200` | `150` | Word limit requested from the model during fact extraction. |
| `SESSION_TTL_MINUTES` | `120` | `120` | Idle minutes before RAM session state is discarded (`0` = keep until reboot). |
| `BRIDGE_DEBUG` | `1` | `0` | Writes truncated prompt/option traces to `DEBUG_LOG` in RAM (`/run/hailo-bridge/debug.log`). |
| `BRIDGE_LEDGER` | *(default)* | `1` | Set to `0` to disable background NPU fact consolidation (archive + recall only). |
| `BRIDGE_INDEX` | *(default)* | `1` | Set to `0` to disable SQLite FTS5 indexing and use the keyword scan fallback. |
| `BRIDGE_FORCE_OPTIONS` | *(default)* | `{}` | JSON object of Ollama options enforced on every request (e.g. `'{"frequency_penalty":0}'`). |
| `MEMORY_INCLUDE_ASSISTANT` | *(default)* | `0` | Set to `1` to archive and recall assistant replies in addition to user turns. |
| `ALLOW_NON_RAM_STORAGE` | *(default)* | `0` | Set to `1` only for testing when `CHATS_DIR` is not on `tmpfs`/`ramfs`. |

After editing `/etc/systemd/system/hailo-bridge.service`, apply changes with:

```bash
sudo systemctl daemon-reload
sudo systemctl restart hailo-bridge.service
```
