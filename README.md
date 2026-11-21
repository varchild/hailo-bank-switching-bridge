# hailo-bank-switching-bridge

A FastAPI/Uvicorn proxy and memory/bank manager sitting between **Open WebUI** and **`hailo-ollama`** for small-context edge hardware (such as a Raspberry Pi 5 + Hailo AI HAT+ 2).

It manages curated knowledge banks, RAM-only per-chat recall and fact consolidation, strict prompt budgeting inside a 2048-token HEF context window, and explicit `/save` and `/forget` session controls—without writing conversation logs to persistent disk unless you explicitly save a bank.

## Architecture

```text
┌──────────────┐   HTTP (/api/chat, /hailo/*)   ┌──────────────────────────────────┐
│  Open WebUI  │ ──────────────────────────────► │  hailo_bridge.py (FastAPI/Uvicorn)│
│  (Frontend)  │ ◄────────────────────────────── │  0.0.0.0:5001                    │
└──────────────┘                                 └───────┬──────────┬────────┬──────┘
                                                         │          │        │
              ┌──────────────────────────────────────────┘          │        └──────────────────────┐
              ▼                                                     ▼                               ▼
   [Curated Memory Banks]                              [RAM-Only Session State]        [hailo-ollama Upstream]
   • BANKS_DIR/*.txt (disk)                            • CHATS_DIR (tmpfs/ramfs)     • 127.0.0.1:8000
   • Keyword + FTS5/BM25 scoring                       • archive.jsonl + session.txt   • Serialized via asyncio.Lock
   • Full load or [EXCERPTS ONLY]                      • SQLite FTS5 index + LRU RAM   • HEF context & num_predict
   • Explicit /save [name] -> BANKS_DIR                   governor + /forget floor        clamping
```

## Key Features

* **Curated Bank Routing & Excerpts:** Scans `*.txt` files in `BANKS_DIR`, scores them against recent user and assistant turns, loads matching banks into the system prompt, or extracts top SQLite FTS5/BM25 chunks (`[EXCERPTS ONLY]`) when a relevant bank exceeds the token budget.
* **Targeted Bank Rules:** Injects bank-handling rules and `"That bank is not loaded: <bank name>"` instructions only when a bank is loaded or a matching bank could not be loaded—preventing small `1B–4B` models from echoing bank names or chat UUIDs on unrelated prompts.
* **RAM-Only Privacy & Safeguards:** Refuses to store per-chat memory or FTS5 index state on non-RAM filesystems (`tmpfs`/`ramfs` check against `/proc/mounts` unless `ALLOW_NON_RAM_STORAGE=1` is set), and routes `BRIDGE_DEBUG` logs to a capped RAM file rather than `journald`.
* **Automatic RAM Sizing & Governor:** Computes memory budgets from `/proc/meminfo` at startup, ratchets down if available RAM drops, evicts least-recently-used chats under memory pressure, and pauses new storage rather than triggering an OOM kill.
* **Two-Pass Context Fitting & Recall:** Fits recent turns inside `MAX_PROMPT_TOKENS` (`1300` by default within `HEF_CONTEXT_TOKENS=2048`), archives evicted turns verbatim (`MEMORY_INCLUDE_ASSISTANT=0` by default to avoid reinforcing model hallucinations), recalls chunks matching distinctive question terms, and runs background fact extraction into `session.txt` once queued tokens reach `CONSOLIDATE_MIN_TOKENS`.
* **In-Chat & REST Controls:** Supports `/save [bank_name]` (writing verbatim user messages plus any consolidated ledger facts to `BANKS_DIR`, splitting across UTF-8 byte-sized `<name>-2.txt` parts if needed), `/forget` (discarding session state and advancing the forget floor across restarts), and `/hailo/*` inspection and management endpoints.

## Quick Start

See **[INSTALL.md](INSTALL.md)** for full `systemd` setup, directory permissions, and Open WebUI configuration.

```bash
python3 -m venv /opt/hailo-bridge/venv
/opt/hailo-bridge/venv/bin/pip install fastapi uvicorn httpx

HAILO_UPSTREAM=http://127.0.0.1:8000 \
BANKS_DIR=/var/lib/hailo-bridge/banks \
CHATS_DIR=/run/hailo-bridge/chats \
/opt/hailo-bridge/venv/bin/uvicorn hailo_bridge:app --host 0.0.0.0 --port 5001
```

## Bank File Format

Place plain-text `.txt` files in `BANKS_DIR` (e.g., `/var/lib/hailo-bridge/banks/network.txt`). The first line serves as the bank description used for indexing and scoring, followed by an optional `---` separator and the bank content:

```text
Local LAN hosts, ports, and internal services
---
- hal-9001.lan runs hailo-ollama on port 8000 and hailo-bridge on port 5001.
- search.lan runs SearXNG at 192.168.1.10.
```

## In-Chat Commands

When Open WebUI forwards chat IDs (`ENABLE_FORWARD_USER_INFO_HEADERS=True`), you can control session memory directly from chat:

* `/save` or `/save <name>` — Saves all of your messages from the current chat verbatim (plus any model-extracted ledger facts, clearly labeled) into `BANKS_DIR` as a shared bank available to all chats. Never overwrites a hand-written bank that was not created by `/save`.
* `/forget` — Immediately discards the current chat's RAM archive, FTS5 index rows, and session ledger, and sets a stateless forget floor so earlier turns are not re-archived or saved even across service restarts.

## HTTP Endpoints

* `POST /api/chat` — Main chat proxy with bank selection, two-pass windowing, recall, `/save` & `/forget` commands, and async consolidation.
* `GET /hailo/session/{chat_id}` — Read the current RAM `session.txt` ledger for a chat.
* `GET /hailo/archive/{chat_id}?n=10` — Inspect archived turn count, forget floor, pending consolidation count, and recent archived entries.
* `GET /hailo/ram` — View `/proc/meminfo` sizing plan, live RAM usage, governor state, and active chats in RAM.
* `GET /hailo/index` — Inspect SQLite FTS5 status, chunk counts, and indexed banks/chats.
* `GET /hailo/search/{chat_id}?q=...&n=8` — Preview candidate chunks and exact recall output for a query without invoking the NPU.
* `POST /hailo/session/{chat_id}/save?name=...` — Save archived chat state to `BANKS_DIR` via REST.
* `DELETE /hailo/session/{chat_id}` — Discard a chat session via REST.
* `* /{path:path}` — Pass-through proxy to `HAILO_UPSTREAM` (preserving query strings; serializing `api/generate`).

## Contributing & Feedback

Feedback, bug reports, and PRs are welcome—especially around:

* Edge cases in two-pass prompt fitting, FTS5 query/stemming behavior, and streaming responses from `hailo-ollama`.
* Multi-turn tool/function behavior or Open WebUI prompt injections on small `1B–4B` quantized models.
* RAM governor tuning across different Raspberry Pi and edge SBC memory footprints.
