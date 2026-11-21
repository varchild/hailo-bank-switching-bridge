# hailo_bridge v5.4.7
# v5.4.7: the unconditional "That bank is not loaded: <bank name>" rule is gone.
#  - BUG: whenever ANY bank existed, build_system told the model "if a question depends on an unloaded bank,
#    reply exactly 'That bank is not loaded: <bank name>'" on EVERY request, whether or not the question had
#    anything to do with a bank. A 1.5-4B model obeys that on unrelated questions ("woodchuck" -> "That bank is
#    not loaded: 7b70e4e1-..."), and a nameless /save names its bank after the chat UUID, so the UUID got echoed.
#  - FIX: the bank rules are now added only when they can matter: a bank was loaded this turn, or a bank that
#    matches the question (score > 0) did not fit and was NOT loaded. The "not loaded" line names those banks, and
#    says to ignore them if the answer does not need them. An unrelated question gets the base prompt + the
#    plain index and no instruction to say anything about banks. Token budget is still reserved for the
#    worst case (rules + names), so a bank that does load can never push the prompt over MAX_PROMPT_TOKENS.
# hailo_bridge v5.4.6
# v5.4.6: review of v5.4.4 (the "/save never drops facts" build): /save and /forget corner cases.
#  - BUG: a smaller re-save under the same name left the old <name>-2, <name>-3 ... parts behind. They kept
#    older text (including anything /forgotten) and stayed loaded as shared banks. They are now removed
#    (only files /save wrote as parts), and a part name never replaces a bank that is not a /save part.
#  - BUG: parts were sized in characters, but bank_file_max is a file-size limit and _load_one skips bigger
#    files, so non-ASCII text produced parts up to 4x too big that never loaded. Parts are sized in UTF-8 bytes.
#  - BUG: newlines in a message were flattened to spaces, so pasted configs / code lost their structure
#    despite "verbatim". Line breaks are kept (continuation lines are indented under the bullet).
#  - BUG: /forget lived only in the in-memory _floor. After a bridge restart the forgotten turns were
#    archived and recalled again, and /save wrote them to disk. The floor is now also derived from the
#    history Open WebUI resends (the last "/forget" in it), so it survives restarts and idle discards.
#  - a multi-part save is staged first and renamed afterwards: a failed write no longer leaves a half-written set.
# hailo_bridge v5.4.4
# v5.4.4: /save now really saves, plus a batch of smaller fixes found in review.
#  - /save (the bug behind "No session bank to save yet", which v5.4.3 did NOT fix): the verbatim
#    fallback read only archive.jsonl, and the archive holds only turns that have already been EVICTED
#    from the context window. In a chat where nothing has scrolled out yet (every short chat, and the
#    newest turns of every long one) the archive is empty, so /save still had nothing to write. Also,
#    the /save request is answered before the eviction/archiving code runs, so it never archives
#    anything itself. Open WebUI resends the whole history with every request, so /save now builds
#    the bank from the user turns in that request, merged with the archive. REST /save has no live
#    history and still uses the archive only (it says so when empty).
#  - /save no longer overwrites a hand-written bank: it only replaces files it wrote itself
#    (first line "session memory: ..."). A write failure (e.g. BANKS_DIR not writable under systemd
#    ProtectHome) is reported in the chat instead of surfacing as an HTTP 500. Writes are atomic.
#    A name that sanitises to nothing falls back to the chat id (the ledger path wrote ".txt").
#  - /save NEVER drops facts. It used to promote only the RAM ledger when one existed: capped at ~580
#    chars, FIFO-trimmed, and missing every turn not yet consolidated. Now every /save writes ALL of
#    the user's messages in the chat (verbatim, unclipped, no size cap) and, when the ledger has facts,
#    those too in a labelled section. A bank too big to be loaded (> bank_file_max) is split into
#    <name>, <name>-2, ... instead of being cut. The reply says how many messages/facts were written.
#  - consolidation: a reply of "FACTS:" with no lines (the answer the prompt asks for when a segment
#    holds nothing factual) was treated as a failure and the segment requeued, so every later request
#    re-ran the same NPU extraction in the background and held the gate. It is now consumed.
#  - an empty or all-unsafe x-openwebui-chat-id made CHATS_DIR itself the "chat directory" (state written
#    into it, /forget could rmdir it). It now maps to "unknown", for the REST endpoints too.
#  - GET /hailo/archive/<id>: "last n" indexed a single element (IndexError / 500 when fewer than n).
#  - the catch-all proxy dropped query strings; a system message with null content became "None".
#  - background tasks are now kept referenced (asyncio only holds weak references to tasks).
# hailo_bridge v5.4.3
# v5.4.3: /save now always has something to save; /forget no longer eats one extra turn.
#  - BUG (the "No session bank to save yet" loop): the session ledger (session.txt) is written ONLY
#    by the async consolidator, which only runs once >= CONSOLIDATE_MIN_TOKENS of evicted USER text
#    has queued up - and /save itself returns before any of that machinery runs. With USER-only
#    extraction (the default), that threshold is rarely reached: a 1300-token window holds mostly
#    assistant text, the user's short turns queue slowly, and the newest user turns (the ones just
#    written) never leave the window at all, so they can never be consolidated. Result: /save kept
#    reporting "No session bank to save yet" even though the archive held the facts.
#  - FIX: /save (chat command and REST) now falls back to writing the chat's archived USER turns
#    verbatim as the bank when no consolidated ledger exists yet. Deterministic, no NPU call,
#    user's own words only (v5.2.1 lesson). "No session bank" is now returned only when nothing at
#    all has been archived (a fresh chat, or immediately after /forget).
#  - FIX: /forget set _floor = len(turns) + 1, which permanently skipped the FIRST turn sent after
#    the /forget as well (off by one). Now len(turns): everything up to and including the /forget
#    command stays forgotten; the very next message is remembered.
# hailo_bridge v5.4.2
# v5.4.2: safe handling when the model's replies ARE stored (MEMORY_INCLUDE_ASSISTANT=1).
#  - The user's own statements are recalled first. A reply chunk is only added if it matches a distinctive
#    question word that no recalled user chunk already covers (so a wrong reply can't sit next to the
#    user's fact), and at most ARCHIVE_MAX_ASSISTANT_CHUNKS (default 2) per turn.
#  - The session ledger is controlled separately: LEDGER_INCLUDE_ASSISTANT=1 lets the extractor read replies
#    too (default off: the ledger is what /save promotes to an authoritative bank).
#  - "answer(s)" is no longer treated as a generic word.
# hailo_bridge v5.4.1
# v5.4.1 (from the first real run): recall no longer fires on boilerplate. Your 30-prompt test showed each
#  filler prompt ("In about 120 words, explain ...") recalling the earlier filler prompts, because generic
#  words matched. A chunk must now share at least one DISTINCTIVE question word - one that appears in no more
#  than max(3, ARCHIVE_DISTINCT_FRACTION of) this chat's indexed chunks (measured with the index itself,
#  per term). A question made only of common words recalls nothing and costs no window space.
# hailo_bridge v5.4
# v5.4: RAM-aware sizing + safeguards. Nothing about memory capacity is a fixed number any more.
#  - At service start a formula reads /proc/meminfo and sets the maximum RAM the bridge's memory may
#    use:  usable = min(MemAvailable, MemTotal - OS reserve);  budget = usable * BANK_RAM_FRACTION,
#    clamped, and never more than half of the tmpfs. A 4 GB Pi therefore gets a smaller budget than 8/16 GB.
#    Per-chat archive length, queue sizes, curated-bank file limits and the debug-log size are all
#    derived from that budget (ARCHIVE_MAX_TURNS still works as an explicit override).
#  - Safeguards while running (checked at most every GOVERNOR_INTERVAL_S): the budget can only ratchet
#    DOWN if the OS later has less free RAM (e.g. services that started after the bridge); the
#    least-recently-used chats are shed if the budget is exceeded or system RAM drops below a floor;
#    if it still can't fit, memory growth is paused (chat keeps working, nothing new is stored).
#  - SQLite index uses incremental auto-vacuum, so deleting chats really returns RAM; it is rebuilt
#    from the archives at every start.
#  - Only text that is actually used is stored: assistant replies are no longer archived unless
#    MEMORY_INCLUDE_ASSISTANT=1. Archive length tracking is O(new turns) instead of re-reading the file.
#  - GET /hailo/ram shows the plan and live usage.
# hailo_bridge v5.3.1
# v5.3.1: RAM-only guarantees (core design rule: conversation text never reaches the microSD unless
# the user explicitly runs /save).
#  - Per-chat memory (archive, ledger) and the retrieval index refuse to start on non-RAM storage
#    (checked against /proc/mounts: tmpfs/ramfs only). ALLOW_NON_RAM_STORAGE=1 overrides, e.g. for tests.
#  - BRIDGE_DEBUG output goes to a RAM file (DEBUG_LOG), NOT the journal. journald may be persistent,
#    which would put prompt text on the SD card.
#  - Log lines that carried conversation text (ledger-full, no-FACTS reply) now log lengths only.
#  - SQLite temp files are forced into memory (PRAGMA temp_store=MEMORY).
#  - The ONLY conversation-derived write to disk is /save (BANKS_DIR).
# v5.3: dynamic retrieval index (SQLite FTS5 + BM25, stdlib only).
#  - Chat memory: every evicted USER turn is split into sentence/line chunks and indexed once, at
#    eviction time. Recall is a ranked index lookup returning only the matching chunks (not whole
#    messages), packed into the recall token budget. No per-request file reads or re-scoring.
#  - Banks: files are re-indexed only when their mtime changes, and the directory is rescanned every
#    BANK_RESCAN_SECONDS instead of on every request. A relevant bank too big for the budget used
#    to be skipped; now its best-matching chunks are loaded as "EXCERPTS ONLY".
#  - The index is a derived cache: archive.jsonl / BANKS_DIR stay the source of truth, rebuilt on
#    demand. If FTS5 is unavailable (or BRIDGE_INDEX=0) the v5.2.x keyword scan is used instead.
#  - Eviction bookkeeping is O(new turns) per request (verified high-water mark), not O(history).
#  - New debug endpoints: GET /hailo/index, GET /hailo/search/<chat-id>?q=...
# --- earlier version notes ---
# v5.2 changes on top of v5.1:
#  - Evicted turns are archived verbatim per chat (CHATS_DIR/<chat-id>/archive.jsonl) and queued
#    for the fact ledger exactly once (hash-deduped by index+role+text). Fixes the v5.1 bug where
#    the whole evicted prefix was re-queued on every request, and makes /forget stick.
#  - RECALL: each turn the archive is keyword-scored against the current question and the best
#    1-2 earlier exchanges are injected verbatim ("EARLIER IN THIS CHAT") within a token budget.
#  - Window is fitted twice, so turns evicted by THIS request are already recallable this turn.
#  - base system content is capped; DEFAULT_BLUEPRINT is empty unless BRIDGE_BLUEPRINT is set.
#  - options.num_predict is capped so prompt + output stays inside the HEF window.
#  - chars/token 3 (code/paths/IPs tokenize worse than 4), smaller ledger, ledger sized to its cap.
#  - /forget cancels an in-flight consolidation; regex fallback only mines USER turns.
#  - BRIDGE_LEDGER=0 disables model consolidation entirely (archive+recall only, no NPU contention).
# v5.2.1 (from the first real test run):
#  - Recall and the ledger now use USER turns only (MEMORY_INCLUDE_ASSISTANT=1 restores v5.2
#    behavior). On a 1.5B the assistant's own hallucinations (e.g. "kestrel-3, port 617") matched the
#    keywords as well as the user's real statement and won on recency, so recall fed lies back in.
#  - Recall skips archived messages that are near-duplicates of the current question, and
#    de-prioritizes bare questions; keywords get a light plural stem (listens -> listen).
#  - BRIDGE_DEBUG=1 logs the exact system prompt, trimmed messages and options sent upstream.
# v5.2.2:
#  - BRIDGE_FORCE_OPTIONS='{"frequency_penalty":0,"presence_penalty":0}' overrides whatever sampling
#    options Open WebUI sends. A/B test showed penalties of 1.7 (sent by Open WebUI) corrupt the
#    exact-copy answers a small model needs (ports, versions, paths).

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [Bridge] - %(message)s")

UPSTREAM = os.environ.get("HAILO_UPSTREAM", "http://127.0.0.1:8000")
BRIDGE_HOST = os.environ.get("BRIDGE_HOST", "127.0.0.1")
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "5001"))

# HARD LIMIT: 2048-token context window, compiled into the HEF.
HEF_CONTEXT_TOKENS = int(os.environ.get("HEF_CONTEXT_TOKENS", "2048"))
MAX_PROMPT_TOKENS = int(os.environ.get("MAX_PROMPT_TOKENS", "1300"))
OUTPUT_MARGIN_TOKENS = int(os.environ.get("OUTPUT_MARGIN_TOKENS", "100"))
CHARS_PER_TOKEN = int(os.environ.get("CHARS_PER_TOKEN", "3"))

# Shared, user-curated banks: BANKS_DIR/*.txt (disk; survives reboots). READ-ONLY input, except that
# an explicit /save writes the session ledger there - the only conversation write that leaves RAM.
# Per-chat dynamic state:  CHATS_DIR/<chat-id>/{session.txt,archive.jsonl} (Pi RAM; volatile)
CHATS_DIR = Path(os.environ.get("CHATS_DIR", "/dev/shm/hailo-banks/chats"))
BANKS_DIR = Path(os.environ.get("BANKS_DIR", "/home/user/banks"))

BANK_BUDGET_FRACTION = float(os.environ.get("BANK_BUDGET_FRACTION", "0.6"))
# Never let banks + recall squeeze the recent-conversation window below this.
MIN_HISTORY_TOKENS = int(os.environ.get("MIN_HISTORY_TOKENS", "300"))
# base = all system messages Open WebUI sends (RAG/filter injections can be huge). Cap it.
BASE_MAX_FRACTION = float(os.environ.get("BASE_MAX_FRACTION", "0.4"))

# Fact ledger knobs
LEDGER_ENABLED = os.environ.get("BRIDGE_LEDGER", "1") not in ("0", "false", "False", "")
DYN_BANK_MAX_TOKENS = int(os.environ.get("DYN_BANK_MAX_TOKENS", "250"))
CONSOLIDATE_MIN_TOKENS = int(os.environ.get("CONSOLIDATE_MIN_TOKENS", "200"))
CONSOLIDATE_MAX_WORDS = int(os.environ.get("CONSOLIDATE_MAX_WORDS", "150"))
# Consolidation request budget: the extraction segment must fit the HEF window.
CONSOLIDATE_PROMPT_TOKENS = int(os.environ.get("CONSOLIDATE_PROMPT_TOKENS", "1500"))
CONSOLIDATE_NUM_PREDICT = int(os.environ.get("CONSOLIDATE_NUM_PREDICT", "400"))

# Verbatim archive + recall knobs
# ARCHIVE_MAX_TURNS: optional explicit override; by default derived from the RAM budget (_max_turns)
ARCHIVE_TURN_CHARS = int(os.environ.get("ARCHIVE_TURN_CHARS", "800"))     # stored chars per turn
ARCHIVE_RECALL_TOKENS = int(os.environ.get("ARCHIVE_RECALL_TOKENS", "300"))
ARCHIVE_MAX_EXCHANGES = int(os.environ.get("ARCHIVE_MAX_EXCHANGES", "3"))
ARCHIVE_MIN_SCORE = float(os.environ.get("ARCHIVE_MIN_SCORE", "2.0"))     # keyword-overlap threshold
MIN_EXCHANGE_CHARS = 160                                                   # don't inject slivers
# Default: only the USER's own words are recalled / extracted into the ledger.
MEMORY_INCLUDE_ASSISTANT = os.environ.get("MEMORY_INCLUDE_ASSISTANT", "0") in ("1", "true", "True")
LEDGER_INCLUDE_ASSISTANT = os.environ.get("LEDGER_INCLUDE_ASSISTANT", "0") in ("1", "true", "True")
ARCHIVE_MAX_ASSISTANT_CHUNKS = int(os.environ.get("ARCHIVE_MAX_ASSISTANT_CHUNKS", "2"))
BRIDGE_DEBUG = os.environ.get("BRIDGE_DEBUG", "0") in ("1", "true", "True")
try:
    FORCE_OPTIONS = json.loads(os.environ.get("BRIDGE_FORCE_OPTIONS", "") or "{}")
    if not isinstance(FORCE_OPTIONS, dict):
        raise ValueError("not a JSON object")
except ValueError as _exc:
    logging.error("BRIDGE_FORCE_OPTIONS ignored (%s)", _exc)
    FORCE_OPTIONS = {}

# ---- v5.3 dynamic index ----
INDEX_ENABLED = os.environ.get("BRIDGE_INDEX", "1") not in ("0", "false", "False", "")
INDEX_DB = Path(os.environ.get("INDEX_DB", str(CHATS_DIR.parent / "index.db")))
ARCHIVE_CANDIDATES = int(os.environ.get("ARCHIVE_CANDIDATES", "24"))     # ranked rows pulled per query
ARCHIVE_MAX_CHUNKS = int(os.environ.get("ARCHIVE_MAX_CHUNKS", "6"))      # chunks injected per turn
ARCHIVE_DISTINCT_FRACTION = float(os.environ.get("ARCHIVE_DISTINCT_FRACTION", "0.3"))   # "rare" = in <= this share of chunks
INDEX_CHUNK_CHARS = int(os.environ.get("INDEX_CHUNK_CHARS", "240"))      # chat chunk size cap
BANK_CHUNK_CHARS = int(os.environ.get("BANK_CHUNK_CHARS", "400"))        # bank chunk size cap
BANK_EXCERPT_TOKENS = int(os.environ.get("BANK_EXCERPT_TOKENS", "250"))  # budget per oversized bank
BANK_EXCERPT_MAX_CHUNKS = int(os.environ.get("BANK_EXCERPT_MAX_CHUNKS", "6"))
BANK_RESCAN_SECONDS = float(os.environ.get("BANK_RESCAN_SECONDS", "5"))  # 0 = rescan every request

# ---- RAM-only guard ----
ALLOW_NON_RAM_STORAGE = os.environ.get("ALLOW_NON_RAM_STORAGE", "0") in ("1", "true", "True")
DEBUG_LOG = Path(os.environ.get("DEBUG_LOG", str(CHATS_DIR.parent / "debug.log")))


def _on_ram(path: Path) -> bool:
    """True if path lives on tmpfs/ramfs (RAM): longest-prefix mount match in /proc/mounts.
    Works for paths that don't exist yet. Any doubt -> False."""
    try:
        real = os.path.realpath(str(path))
        best, fstype = "", ""
        with open("/proc/mounts", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mnt = parts[1].replace("\\040", " ")
                if (real == mnt or real.startswith(mnt.rstrip("/") + "/")) and len(mnt) > len(best):
                    best, fstype = mnt, parts[2]
        return fstype in ("tmpfs", "ramfs")
    except OSError:
        return False


MEMORY_ENABLED = ALLOW_NON_RAM_STORAGE or _on_ram(CHATS_DIR)
if not MEMORY_ENABLED:
    logging.error("CHATS_DIR %s is not on tmpfs/ramfs: per-chat memory is DISABLED so conversation "
                  "text can never reach the SD card. Use a /dev/shm path (or ALLOW_NON_RAM_STORAGE=1).",
                  CHATS_DIR)
if INDEX_ENABLED and not (ALLOW_NON_RAM_STORAGE or _on_ram(INDEX_DB)):
    logging.error("INDEX_DB %s is not on tmpfs/ramfs: the retrieval index is DISABLED (it holds chat "
                  "text). Use a /dev/shm path (or ALLOW_NON_RAM_STORAGE=1).", INDEX_DB)
    INDEX_ENABLED = False


# ---- v5.4 RAM plan: sized from the machine at service start ----
BANK_RAM_FRACTION = float(os.environ.get("BANK_RAM_FRACTION", "0.10"))   # share of usable RAM
OS_RESERVE_MIN_MB = int(os.environ.get("OS_RESERVE_MIN_MB", "768"))      # RAM the OS must keep, at least
OS_RESERVE_FRACTION = float(os.environ.get("OS_RESERVE_FRACTION", "0.20"))   # ... or this share of total
BANK_RAM_MIN_MB = int(os.environ.get("BANK_RAM_MIN_MB", "16"))
BANK_RAM_MAX_MB = int(os.environ.get("BANK_RAM_MAX_MB", "2048"))
BANK_RAM_BUDGET_MB = os.environ.get("BANK_RAM_BUDGET_MB", "")            # explicit override (still clamped)
LOW_MEM_FLOOR_MB = int(os.environ.get("LOW_MEM_FLOOR_MB", "256"))        # shed chats below this MemAvailable
GOVERNOR_INTERVAL_S = float(os.environ.get("GOVERNOR_INTERVAL_S", "5"))
PENDING_TURN_CHARS = 4000       # the extractor only ever reads about this much of one turn
_MIB = 1024 * 1024
# how the budget is divided (shares of the budget)
CHAT_SHARE, PENDING_SHARE, CURATED_SHARE, BANK_FILE_SHARE, DEBUG_SHARE = 0.05, 0.05, 0.25, 0.05, 0.001
RAM_PLAN: dict = {}


def _meminfo() -> dict:
    out = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                k, _, rest = line.partition(":")
                if k in ("MemTotal", "MemAvailable"):
                    out[k] = int(rest.split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        return {}
    return out


def _tmpfs_total(path: Path):
    p = path
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        st = os.statvfs(str(p))
        return st.f_blocks * st.f_frsize
    except OSError:
        return None


def _formula_budget(mi: dict):
    """The sizing formula. Returns (budget_bytes, details)."""
    total, avail = mi.get("MemTotal"), mi.get("MemAvailable")
    if not total or not avail:
        return BANK_RAM_MIN_MB * _MIB, {"total": 0, "avail": 0, "os_reserve": 0, "usable": 0,
                                        "note": "meminfo unreadable: using the minimum budget"}
    os_reserve = max(OS_RESERVE_MIN_MB * _MIB, int(OS_RESERVE_FRACTION * total))
    usable = max(0, min(avail, total - os_reserve))
    budget = int(usable * BANK_RAM_FRACTION)
    if BANK_RAM_BUDGET_MB.strip():
        budget = int(float(BANK_RAM_BUDGET_MB) * _MIB)
    ts = _tmpfs_total(CHATS_DIR.parent)
    if ts:
        budget = min(budget, ts // 2)      # never plan to fill more than half the tmpfs
    budget = max(BANK_RAM_MIN_MB * _MIB, min(budget, BANK_RAM_MAX_MB * _MIB))
    return budget, {"total": total, "avail": avail, "os_reserve": os_reserve, "usable": usable}


def _derive(budget: int) -> dict:
    per_turn = 3 * (ARCHIVE_TURN_CHARS + 48)     # archive line + index rows + FTS overhead, worst case
    chat_cap = int(budget * CHAT_SHARE)
    return {
        "chat_cap": chat_cap,
        "max_turns": max(100, min(5000, chat_cap // per_turn)),
        "pending_cap": int(budget * PENDING_SHARE),
        "bank_file_max": max(256 * 1024, min(16 * _MIB, int(budget * BANK_FILE_SHARE))),
        "curated_cap": int(budget * CURATED_SHARE),
        "debug_log_bytes": max(64 * 1024, min(4 * _MIB, int(budget * DEBUG_SHARE))),
    }


def _plan_ram(mi=None, ratchet: bool = False):
    """Run the formula. With ratchet=True the budget may only go DOWN (and only if it drops >5%)."""
    mi = _meminfo() if mi is None else mi
    budget, info = _formula_budget(mi)
    if ratchet and RAM_PLAN and budget >= 0.95 * RAM_PLAN["budget"]:
        return
    RAM_PLAN.update(info)
    RAM_PLAN["budget"] = budget
    RAM_PLAN.update(_derive(budget))
    logging.info("RAM plan%s: total=%.0f MiB available=%.0f MiB os_reserve=%.0f MiB usable=%.0f MiB "
                 "-> memory budget %.0f MiB | per-chat cap %.1f MiB (%d turns) | queue %.1f MiB | "
                 "bank file <= %.1f MiB | curated banks <= %.0f MiB",
                 " (lowered)" if ratchet else "", info["total"] / _MIB, info["avail"] / _MIB,
                 info["os_reserve"] / _MIB, info["usable"] / _MIB, budget / _MIB,
                 RAM_PLAN["chat_cap"] / _MIB, RAM_PLAN["max_turns"], RAM_PLAN["pending_cap"] / _MIB,
                 RAM_PLAN["bank_file_max"] / _MIB, RAM_PLAN["curated_cap"] / _MIB)


def _max_turns() -> int:
    v = os.environ.get("ARCHIVE_MAX_TURNS")
    return int(v) if v else RAM_PLAN["max_turns"]


_plan_ram()     # <- runs once when the service starts

_debug_logger = None


def _dbg(fmt: str, *args):
    """BRIDGE_DEBUG sink: a size-capped file in RAM. Never the journal (it can be persistent)."""
    global _debug_logger
    if not BRIDGE_DEBUG:
        return
    if _debug_logger is None:
        _debug_logger = logging.getLogger("bridge.debug")
        _debug_logger.propagate = False          # never reaches the root handler / journald
        _debug_logger.setLevel(logging.INFO)
        if ALLOW_NON_RAM_STORAGE or _on_ram(DEBUG_LOG):
            try:
                DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
                h = RotatingFileHandler(DEBUG_LOG, maxBytes=RAM_PLAN["debug_log_bytes"], backupCount=1, encoding="utf-8")
                h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
                _debug_logger.addHandler(h)
            except OSError as exc:
                logging.error("BRIDGE_DEBUG disabled: cannot open %s (%s)", DEBUG_LOG, type(exc).__name__)
        else:
            logging.error("BRIDGE_DEBUG ignored: %s is not on RAM", DEBUG_LOG)
    _debug_logger.info(fmt, *args)

# Session lifetime: state is DISCARDED after this much idle time (session-end proxy).
# 0 = keep in RAM until the Pi reboots. Saving is ALWAYS the user's explicit choice.
SESSION_TTL_MINUTES = int(os.environ.get("SESSION_TTL_MINUTES", "120"))
SWEEP_INTERVAL_SECONDS = 300

TIMEOUT = httpx.Timeout(300.0, connect=10.0)
gate = asyncio.Lock()

# Empty by default (v5.1 shipped a PostgreSQL example here that leaked into every chat).
DEFAULT_BLUEPRINT = os.environ.get("BRIDGE_BLUEPRINT", "")
BLUEPRINT_BY_CHAT = {}

app = FastAPI(title="Open WebUI <-> hailo-ollama dynamic bank-switching bridge")

WORD_RE = re.compile(r"[a-z0-9_]+")
THINK_RE = re.compile(r"<think\b.*?</think\s*>", re.S)
SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_-]")
SAVE_RE = re.compile(r"^/save(?:\s+(\S+))?\s*$")
FORGET_RE = re.compile(r"^/forget\s*$")
STOPWORDS = set("""
a an and are as at be but by for from has have how i in is it its of on or
that the this to was what when where which who will with you your
""".split())

RECALL_HEADER = "EARLIER IN THIS CHAT (verbatim, older than the visible messages):"
RECALL_HEADER_USER = "EARLIER USER MESSAGES IN THIS CHAT (verbatim, older than the visible messages):"
COMMAND_REPLY_PREFIXES = ("Session bank", "No session bank", "Session commands need", "Session memory")
SESSION_BANK_MARKER = "session memory:"    # first line of every bank that /save writes


def _safe_chat_id(raw) -> str:
    """Sanitised chat id. Never empty: "" would make CHATS_DIR / "" (the whole chats directory) the chat."""
    return SAFE_ID_RE.sub("", str(raw or ""))[:64] or "unknown"


class SaveError(Exception):
    """A /save that could not be completed; the message is shown to the user."""

    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


PART_RE = re.compile(r"\(part \d+ of \d+\)\s*$")    # first line of a bank that is one part of a multi-part /save


def _forget_floor(turns: list) -> int:
    """Index just after the LAST /forget the user sent, found in the history Open WebUI resends. Stateless, so
    it survives a bridge restart, an idle-TTL discard and a service reload: the in-memory _floor alone lost
    the /forget in all three, after which the forgotten turns were archived, recalled and /save'd again."""
    floor = 0
    for i, m in enumerate(turns):
        if m.get("role") == "user" and FORGET_RE.match(str(m.get("content") or "").strip()):
            floor = i + 1
    return floor


def est_tokens_text(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN + 4


def est_tokens(msg: dict) -> int:
    return est_tokens_text(str(msg.get("content") or ""))


def _stem(w: str) -> str:
    """Light plural stem so 'listens'/'listen', 'runs'/'run', 'ports'/'port' match."""
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def keywords(text: str) -> set:
    return {_stem(w) for w in WORD_RE.findall(text.lower()) if len(w) > 2 and w not in STOPWORDS}


def parse_bank_text(text: str, fallback_desc: str):
    """First line = description; optional '---'; rest = content."""
    lines = text.splitlines()
    if not lines:
        return fallback_desc, ""
    description = lines[0].strip() or fallback_desc
    rest = lines[1:]
    if rest and rest[0].strip() == "---":
        rest = rest[1:]
    return description, "\n".join(rest).strip()


class Bank:
    __slots__ = ("name", "description", "content", "desc_kw", "content_kw", "tokens", "dynamic",
                 "mtime", "excerpt")

    def __init__(self, name, description, content, dynamic=False, mtime=0.0, excerpt=False):
        self.name = name
        self.description = description
        self.content = content
        self.desc_kw = keywords(description)
        self.content_kw = keywords(content)
        self.tokens = est_tokens_text(content)
        self.dynamic = dynamic
        self.mtime = mtime
        self.excerpt = excerpt


_bank_cache: dict[str, tuple[float, Bank]] = {}
_bank_skipped: set = set()
_warned_curated: set = set()
_pending: dict[str, list] = {}     # chat_id -> evicted turns awaiting consolidation
_inflight: set[str] = set()        # chats with a consolidation task running
_last_seen: dict[str, float] = {}  # chat_id -> last request time (TTL sweep)
_seen: dict[str, set] = {}         # chat_id -> hashes of turns already archived
_floor: dict[str, int] = {}        # chat_id -> turn indices below this are never archived (/forget)
_gen: dict[str, int] = {}          # chat_id -> bumped on discard; cancels in-flight consolidation


def _load_one(path: Path, name: str, dynamic: bool, fallback_desc: str):
    try:
        st = path.stat()
        mtime = st.st_mtime
    except OSError:
        return None
    key = str(path)
    cached = _bank_cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    if not dynamic and st.st_size > RAM_PLAN["bank_file_max"]:
        if (key, mtime) not in _bank_skipped:
            _bank_skipped.add((key, mtime))
            logging.warning("bank file %s is %.1f MiB, over this machine's %.1f MiB per-file limit: skipped",
                            path.name, st.st_size / _MIB, RAM_PLAN["bank_file_max"] / _MIB)
        return None
    try:
        description, content = parse_bank_text(
            path.read_text(encoding="utf-8", errors="replace"), fallback_desc)
    except OSError:
        return None
    if dynamic and len(content) > DYN_BANK_MAX_TOKENS * CHARS_PER_TOKEN:
        content = content[:DYN_BANK_MAX_TOKENS * CHARS_PER_TOKEN]
    bank = Bank(name, description, content, dynamic=dynamic, mtime=mtime)
    _bank_cache[key] = (mtime, bank)
    return bank


def _shared_banks() -> list:
    """Shared banks. The directory is rescanned at most every BANK_RESCAN_SECONDS (not per request);
    per-file parsing is still mtime-cached, and the retrieval index is re-synced only on a rescan."""
    now = time.time()
    if _shared_cache["t"] > 0 and now - _shared_cache["t"] < BANK_RESCAN_SECONDS:
        return _shared_cache["banks"]
    banks = []
    if BANKS_DIR.is_dir():
        for f in sorted(BANKS_DIR.glob("*.txt")):
            b = _load_one(f, f.name[:-4], dynamic=False, fallback_desc="shared bank")
            if b:
                banks.append(b)
    # total curated-bank RAM cap (3x: text + keyword sets + index overhead); keep the smaller banks
    cost = lambda b: 3 * (len(b.content) + len(b.description))
    if sum(cost(b) for b in banks) > RAM_PLAN["curated_cap"]:
        kept, total, skipped = [], 0, []
        for b in sorted(banks, key=lambda b: len(b.content)):
            if total + cost(b) <= RAM_PLAN["curated_cap"]:
                kept.append(b)
                total += cost(b)
            else:
                skipped.append(b.name)
        banks = sorted(kept, key=lambda b: b.name)
        if frozenset(skipped) not in _warned_curated:
            _warned_curated.add(frozenset(skipped))
            logging.warning("curated banks exceed this machine's %.0f MiB bank limit; not loaded: %s",
                            RAM_PLAN["curated_cap"] / _MIB, ", ".join(skipped))
    _shared_cache["t"] = now
    _shared_cache["banks"] = banks
    _sync_bank_index(banks)
    return banks


def load_banks(chat_id: str) -> list:
    """Shared user-curated banks + this chat's dynamic session bank (RAM)."""
    banks = list(_shared_banks())
    if chat_id and chat_id != "unknown":
        p = CHATS_DIR / chat_id / "session.txt"
        if p.is_file():
            b = _load_one(p, "session", dynamic=True, fallback_desc="memory of this conversation")
            if b:
                banks.append(b)
    return banks


def score_banks(banks: list, turns: list) -> list:
    users = [m for m in turns if m.get("role") == "user"]
    assistants = [m for m in turns if m.get("role") == "assistant"]
    q_last = keywords(str(users[-1].get("content") or "")) if users else set()
    q_prev = keywords(str(users[-2].get("content") or "")) if len(users) > 1 else set()
    q_asst = keywords(str(assistants[-1].get("content") or "")) if assistants else set()

    scored = []
    for b in banks:
        s = 3 * len(q_last & b.desc_kw) + len(q_last & b.content_kw)
        s += 1.5 * len(q_prev & b.desc_kw) + 0.5 * len(q_prev & b.content_kw)
        s += 1.5 * len(q_asst & b.desc_kw) + 0.5 * len(q_asst & b.content_kw)
        if b.dynamic:
            s += 5  # this conversation's own memory is near-always relevant
        scored.append((s, b))
    scored.sort(key=lambda t: (-t[0], t[1].name))
    return scored


def build_system(base: str, blueprint: str, banks: list, selected: list, recall: str = "",
                 missed: list = ()) -> str:
    parts = [base, blueprint]
    if banks:
        idx = ["MEMORY BANK INDEX - %d banks exist:" % len(banks)]
        for i, b in enumerate(banks, 1):
            tag = "auto-summarized session memory" if b.dynamic else "user-provided"
            idx.append("%d. %s (%s): %s" % (i, b.name, tag, b.description))
        parts.append("\n".join(idx))
        if selected:
            loaded = ["LOADED BANK CONTENT:"]
            for b in selected:
                if b.dynamic:
                    tags = "[MODEL-SUMMARIZED]"
                elif b.excerpt:
                    tags = "[USER-PROVIDED] [EXCERPTS ONLY]"
                else:
                    tags = "[USER-PROVIDED]"
                loaded.append("### BANK: %s %s\n%s" % (b.name, tags, b.content))
            parts.append("\n".join(loaded))
        # v5.4.7: rules only when a bank is loaded or a matching bank could not be loaded. With neither, the
        # model gets the index alone and no instruction to say anything about banks.
        if selected or missed:
            rules = [
                "BANK RULES:",
                "- Only banks under LOADED BANK CONTENT are visible to you this turn.",
                "- [USER-PROVIDED] banks are authoritative; treat their contents as fact.",
                "- [MODEL-SUMMARIZED] banks are compressed memories; details may be lost.",
            ]
            if any(b.excerpt for b in selected):
                rules.append("- [EXCERPTS ONLY] banks show just the parts matching the question; "
                             "the rest of that bank exists but is not shown.")
            if missed:
                names = ", ".join("'%s'" % b.name for b in list(missed)[:3])
                rules.append("- This question matches bank(s) that did not fit this turn: %s. If you cannot "
                             "answer without them, reply exactly:" % names)
                rules.append("  'That bank is not loaded: <bank name>' and stop. Do not guess its contents. "
                             "If the answer does not need them, ignore them.")
            parts.append("\n".join(rules))
    if recall:
        parts.append(recall)
    return "\n\n".join(p for p in parts if p)


def _cap_base(base: str, chat_id: str) -> str:
    max_chars = int(MAX_PROMPT_TOKENS * BASE_MAX_FRACTION) * CHARS_PER_TOKEN
    if len(base) > max_chars:
        logging.warning("chat=%s system content %d chars exceeds cap %d; truncated "
                        "(RAG/filter injected into the system message?)",
                        chat_id, len(base), max_chars)
        return base[:max_chars]
    return base


def fit_window(system_message: dict, turns: list):
    """Newest-first fill of the prompt budget. Returns (kept, evicted, truncated).
    kept is always a suffix of turns; evicted is the prefix that did not fit."""
    budget = MAX_PROMPT_TOKENS - est_tokens(system_message)
    kept, truncated = [], False
    for m in reversed(turns):
        if not kept and est_tokens(m) > budget:
            m = dict(m)
            keep_chars = max(0, (budget - 8) * CHARS_PER_TOKEN)
            text = str(m.get("content") or "")
            m["content"] = text[-keep_chars:] if keep_chars > 0 else ""
            truncated = True
        cost = est_tokens(m)
        if kept and cost > budget:
            break
        kept.append(m)
        budget -= cost
    kept.reverse()
    evicted = turns[: len(turns) - len(kept)] if kept else list(turns)
    return kept, evicted, truncated


async def forward(method: str, path: str, content: bytes | None, headers: dict, locked: bool):
    client = httpx.AsyncClient(timeout=TIMEOUT)
    if locked:
        await gate.acquire()
    try:
        req = client.build_request(method, f"{UPSTREAM}/{path}", content=content, headers=headers)
        upstream = await client.send(req, stream=True)
    except Exception as exc:
        if locked:
            gate.release()
        await client.aclose()
        logging.error("Upstream error: %s", exc)
        return JSONResponse({"error": f"hailo-ollama unreachable: {exc}"}, status_code=502)

    async def body():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()
            if locked:
                gate.release()

    return StreamingResponse(
        body(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )


async def _upstream_chat(payload: dict):
    """Internal NPU call for consolidation. Serialized by the same gate as user requests."""
    async with gate:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(f"{UPSTREAM}/api/chat", json=payload,
                                  headers={"accept-encoding": "identity"})
    if r.status_code != 200:
        logging.error("consolidation upstream error %d: %s", r.status_code, r.text[:200])
        return None
    try:
        return r.json()
    except Exception:
        return None


# ---------- v5.2 verbatim archive + recall ----------

def _turn_hash(idx: int, role: str, text: str) -> str:
    return hashlib.blake2s(("%d|%s|%s" % (idx, role, text)).encode("utf-8", "replace"),
                           digest_size=8).hexdigest()


def _is_command_noise(role: str, text: str) -> bool:
    """/save, /forget and the bridge's own replies to them are not conversation."""
    if role == "user":
        return bool(SAVE_RE.match(text) or FORGET_RE.match(text))
    return text.startswith(COMMAND_REPLY_PREFIXES)


def _read_archive(chat_id: str) -> list:
    out = []
    try:
        with open(CHATS_DIR / chat_id / "archive.jsonl", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if (isinstance(e, dict) and e.get("r") in ("user", "assistant")
                        and isinstance(e.get("c"), str) and isinstance(e.get("i"), int)):
                    out.append(e)
    except OSError:
        pass
    return out


def _seen_set(chat_id: str) -> set:
    s = _seen.get(chat_id)
    if s is None:
        entries = _read_archive(chat_id)
        s = {_turn_hash(e["i"], e["r"], e["c"]) for e in entries}
        _seen[chat_id] = s
        _arch_n[chat_id] = len(entries)
    return s


def _archive_append(chat_id: str, fresh: list) -> list:
    """Append turns to archive.jsonl. Returns the entries trimmed off the front (oldest first).
    The per-chat limit comes from the RAM budget; length is tracked in memory (no re-read per turn),
    and trimming has ~10% hysteresis so the file is rewritten rarely."""
    d = CHATS_DIR / chat_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / "archive.jsonl"
    with open(p, "a", encoding="utf-8") as fh:
        for i, r, t in fresh:
            fh.write(json.dumps({"i": i, "r": r, "c": t[:ARCHIVE_TURN_CHARS]},
                                ensure_ascii=False) + "\n")
    _arch_n[chat_id] = _arch_n.get(chat_id, 0) + len(fresh)
    limit = _max_turns()
    dropped = []
    if _arch_n[chat_id] > limit + limit // 10:
        entries = _read_archive(chat_id)
        dropped = entries[:-limit]
        entries = entries[-limit:]
        tmp = d / "archive.jsonl.tmp"
        tmp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries),
                       encoding="utf-8")
        os.replace(tmp, p)
        _arch_n[chat_id] = len(entries)
    return dropped


def _trim_pending(chat_id: str):
    """Keep the ledger queue inside its share of the budget (the archive still has the turns)."""
    q = _pending.get(chat_id)
    while q and _pending_bytes() > RAM_PLAN["pending_cap"]:
        q.pop(0)


def _ingest_evicted(chat_id: str, evicted: list) -> int:
    """Archive newly evicted user turns (verbatim, once), index them, queue them for the ledger.
    `evicted` is a growing prefix of the history, so a verified high-water mark lets us look only
    at turns not seen before (O(new) per request). If the prefix changed (edit/regenerate), the
    mark fails verification and we rescan; the hash set still prevents double-archiving.
    Only text that is used is stored: assistant turns need MEMORY_INCLUDE_ASSISTANT=1.
    While the RAM governor has memory growth paused, nothing new is stored."""
    if not evicted or chat_id == "unknown" or _mem_paused:
        return 0
    floor = _floor.get(chat_id, 0)
    seen = _seen_set(chat_id)
    start = 0
    hw = _hw.get(chat_id)
    if hw and 0 < hw[0] <= len(evicted):
        m = evicted[hw[0] - 1]
        key = _turn_hash(hw[0] - 1, str(m.get("role")),
                         str(m.get("content") or "").strip()[:ARCHIVE_TURN_CHARS])
        if key == hw[1]:
            start = hw[0]
    fresh = []
    for i in range(start, len(evicted)):
        if i < floor:
            continue
        m = evicted[i]
        role = m.get("role")
        text = str(m.get("content") or "").strip()
        if role not in ("user", "assistant") or not text or _is_command_noise(role, text):
            continue
        if role == "assistant" and not MEMORY_INCLUDE_ASSISTANT:
            continue
        h = _turn_hash(i, role, text[:ARCHIVE_TURN_CHARS])
        if h in seen:
            continue
        seen.add(h)
        fresh.append((i, role, text))
    last = evicted[-1]
    _hw[chat_id] = (len(evicted), _turn_hash(len(evicted) - 1, str(last.get("role")),
                                             str(last.get("content") or "").strip()[:ARCHIVE_TURN_CHARS]))
    if not fresh:
        return 0
    _ensure_chat_index(chat_id)          # rebuild from the archive BEFORE appending, so no dupes
    dropped = _archive_append(chat_id, fresh)
    _index_add(chat_id, fresh)
    if dropped:
        _index_drop(chat_id, dropped)
    if LEDGER_ENABLED:
        _pending.setdefault(chat_id, []).extend(
            {"role": r, "content": t[:PENDING_TURN_CHARS]} for _, r, t in fresh
            if r == "user" or LEDGER_INCLUDE_ASSISTANT)
        _trim_pending(chat_id)
    return len(fresh)


def _build_exchanges(entries: list) -> list:
    ex, cur = [], None
    for e in entries:
        if e["r"] == "user":
            cur = {"u": e["c"], "a": ""}
            ex.append(cur)
        elif cur is None:
            cur = {"u": "", "a": e["c"]}
            ex.append(cur)
        else:
            cur["a"] = (cur["a"] + " " + e["c"]).strip()
    return ex


def _clip(text: str, max_chars: int) -> str:
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _fit_exchange(u: str, a: str, max_chars: int) -> str:
    u_cap = min(len(u), max_chars // 3)
    u_txt = u[:u_cap] + ("..." if len(u) > u_cap else "")
    a_cap = max(0, max_chars - len(u_txt) - 12)
    return "U: %s\nA: %s" % (u_txt, _clip(a, a_cap))


def recall_from_archive(chat_id: str, turns: list, max_tokens: int):
    """Keyword-score archived exchanges against the current question; return
    (recall_block, n_exchanges). Deterministic: no model call, nothing is paraphrased.
    Default is user-turns-only: the user's own statements are the ground truth, and a small
    model's replies are the main source of hallucinated 'facts'."""
    if max_tokens < 60:
        return "", 0
    exchanges = _build_exchanges(_read_archive(chat_id))
    if not exchanges:
        return "", 0

    users = [m for m in turns if m.get("role") == "user"]
    assistants = [m for m in turns if m.get("role") == "assistant"]
    q_last = keywords(str(users[-1].get("content") or "")) if users else set()
    q_prev = keywords(str(users[-2].get("content") or "")) if len(users) > 1 else set()
    q_asst = keywords(str(assistants[-1].get("content") or "")) if assistants else set()

    scored = []
    for n, e in enumerate(exchanges):
        if not e["u"]:
            continue  # orphaned assistant turn (archive was trimmed): nothing authoritative
        kw_u = keywords(e["u"])
        if q_last and len(q_last & kw_u) / len(q_last | kw_u) >= 0.7:
            continue  # the user is re-asking this; recalling the question itself adds nothing
        s = len(q_last & kw_u) + 0.5 * len(q_prev & kw_u) + 0.25 * len(q_asst & kw_u)
        if MEMORY_INCLUDE_ASSISTANT:
            s += 0.5 * len(q_last & keywords(e["a"]))
        elif e["u"].rstrip().endswith("?"):
            s *= 0.5  # a bare question carries no facts when assistant text isn't recalled
        if s >= ARCHIVE_MIN_SCORE:
            scored.append((s, n, e))
    if not scored:
        return "", 0
    scored.sort(key=lambda t: (-t[0], -t[1]))  # best score first; ties -> most recent
    top = scored[:ARCHIVE_MAX_EXCHANGES]

    header = RECALL_HEADER if MEMORY_INCLUDE_ASSISTANT else RECALL_HEADER_USER
    avail = max_tokens * CHARS_PER_TOKEN - len(header) - 4
    while top and avail // len(top) < MIN_EXCHANGE_CHARS:
        top.pop()  # drop the lowest-scoring until each has room
    if not top:
        return "", 0
    per = avail // len(top)
    top.sort(key=lambda t: t[1])  # chronological order reads naturally
    if MEMORY_INCLUDE_ASSISTANT:
        body = "\n".join(_fit_exchange(e["u"], e["a"], per) for _, _, e in top)
    else:
        body = "\n".join("- " + _clip(e["u"], per) for _, _, e in top)
    return header + "\n" + body, len(top)


# ---------- v5.3 dynamic index: SQLite FTS5 + BM25 ----------
# A derived cache. archive.jsonl (chats) and BANKS_DIR/*.txt (banks) remain the source of truth and
# the index is rebuilt from them whenever it is missing or out of sync. Every entry point returns
# None / does nothing on failure, and chat() then falls back to the v5.2 keyword scan.

_conn = None
_index_failed = False
_idx_ready: set = set()        # chats whose index rows are in sync with archive.jsonl
_bank_indexed: dict = {}       # bank name -> mtime currently indexed
_shared_cache = {"t": 0.0, "banks": []}
_hw: dict = {}                 # chat_id -> (evicted turns processed, hash of the last one)
_arch_n: dict = {}             # chat_id -> number of entries in archive.jsonl
_idx_rows: dict = {}           # chat_id -> number of indexed chunks (for term-rarity checks)
_mem_paused = False            # set by the RAM governor: store nothing new while True

_CHAT_DDL = ("CREATE VIRTUAL TABLE IF NOT EXISTS chat_fts USING fts5("
             "text, chat_id UNINDEXED, idx UNINDEXED, ord UNINDEXED, role UNINDEXED, "
             "tokenize='porter unicode61')")
_BANK_DDL = ("CREATE VIRTUAL TABLE IF NOT EXISTS bank_fts USING fts5("
             "text, bank UNINDEXED, ord UNINDEXED, tokenize='porter unicode61')")
_CHAT_INS = "INSERT INTO chat_fts(text, chat_id, idx, ord, role) VALUES (?,?,?,?,?)"


def _db():
    """Lazy connection. Returns None when the index is disabled or FTS5 is unavailable."""
    global _conn, _index_failed
    if not INDEX_ENABLED or _index_failed:
        return None
    if _conn is not None:
        return _conn
    try:
        INDEX_DB.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("", "-journal", "-wal", "-shm"):   # derived cache: always rebuilt from the archives
            try:
                os.unlink(str(INDEX_DB) + suffix)
            except OSError:
                pass
        c = sqlite3.connect(str(INDEX_DB), check_same_thread=False)
        c.execute("PRAGMA auto_vacuum=INCREMENTAL")   # deleted chats must give their RAM back
        c.execute("PRAGMA cache_size=-2048")          # 2 MiB page cache
        c.execute("PRAGMA journal_mode=MEMORY")
        c.execute("PRAGMA synchronous=OFF")
        c.execute("PRAGMA temp_store=MEMORY")   # sort/temp spill must not land on the SD card
        c.execute(_CHAT_DDL)
        c.execute(_BANK_DDL)
        with c:
            c.execute("DELETE FROM bank_fts")   # banks are re-indexed from disk after every start
            for (cid,) in c.execute("SELECT DISTINCT chat_id FROM chat_fts").fetchall():
                if not (CHATS_DIR / str(cid)).is_dir():   # orphans from a chat that was discarded
                    c.execute("DELETE FROM chat_fts WHERE chat_id = ?", (cid,))
        _conn = c
        logging.info("retrieval index ready: SQLite %s FTS5 at %s", sqlite3.sqlite_version, INDEX_DB)
    except Exception as exc:
        _index_failed = True
        logging.error("FTS5 index unavailable (%s); using the keyword scan instead", exc)
        return None
    return _conn


def _reclaim():
    """Give deleted rows' RAM back. FTS5 deletes are lazy (tombstones until segments are merged),
    so merge first ('optimize'), then let incremental auto-vacuum truncate the tmpfs file.
    Called only after something was deleted, never on the hot path."""
    if _conn is None:
        return
    try:
        with _conn:
            _conn.execute("INSERT INTO chat_fts(chat_fts) VALUES('optimize')")
            _conn.execute("INSERT INTO bank_fts(bank_fts) VALUES('optimize')")
        _conn.execute("PRAGMA incremental_vacuum").fetchall()   # the pragma frees one page per fetched row
    except Exception as exc:
        logging.error("index vacuum failed (%s)", type(exc).__name__)


def _chunk_text(text: str, max_chars: int) -> list:
    """Split into sentence/line-sized pieces (<= max_chars), dropping slivers with no content."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for sent in SENT_SPLIT_RE.split(line):
            piece = sent.strip()
            while len(piece) > max_chars:
                cut_at = piece.rfind(" ", 0, max_chars)
                if cut_at < max_chars // 2:
                    cut_at = max_chars
                out.append(piece[:cut_at].strip())
                piece = piece[cut_at:].strip()
            if len(piece) >= 6 and re.search(r"[A-Za-z0-9]{3}", piece):
                out.append(piece)
    return out


def _merge_chunks(pieces: list, max_chars: int) -> list:
    """Pack consecutive small pieces together (bank chunks keep a little surrounding context)."""
    out, cur = [], ""
    for piece in pieces:
        if cur and len(cur) + 1 + len(piece) <= max_chars:
            cur += "\n" + piece
        else:
            if cur:
                out.append(cur)
            cur = piece
    if cur:
        out.append(cur)
    return out


def _chunk_rows(chat_id: str, idx: int, role: str, text: str) -> list:
    return [(c, chat_id, idx, n, role)
            for n, c in enumerate(_chunk_text(text[:ARCHIVE_TURN_CHARS], INDEX_CHUNK_CHARS))]


def _ensure_chat_index(chat_id: str):
    """Make this chat's rows match archive.jsonl (once per chat per process)."""
    if chat_id in _idx_ready:
        return
    conn = _db()
    if conn is None:
        return
    try:
        rows = []
        for e in _read_archive(chat_id):
            if e["r"] == "user" or MEMORY_INCLUDE_ASSISTANT:
                rows += _chunk_rows(chat_id, e["i"], e["r"], e["c"])
        with conn:
            conn.execute("DELETE FROM chat_fts WHERE chat_id = ?", (chat_id,))
            conn.executemany(_CHAT_INS, rows)
        _idx_rows[chat_id] = len(rows)
        _idx_ready.add(chat_id)
    except Exception as exc:
        logging.error("chat=%s index rebuild failed: %s", chat_id, exc)


def _index_add(chat_id: str, fresh: list):
    conn = _db()
    if conn is None or chat_id not in _idx_ready:
        return
    rows = []
    for i, r, t in fresh:
        if r == "user" or MEMORY_INCLUDE_ASSISTANT:
            rows += _chunk_rows(chat_id, i, r, t)
    if not rows:
        return
    try:
        with conn:
            conn.executemany(_CHAT_INS, rows)
        _idx_rows[chat_id] = _idx_rows.get(chat_id, 0) + len(rows)
    except Exception as exc:
        logging.error("chat=%s index insert failed (%s); will rebuild", chat_id, type(exc).__name__)
        _idx_ready.discard(chat_id)


def _index_drop(chat_id: str, dropped: list):
    """Archive was trimmed; remove the same turns from the index."""
    conn = _db()
    if conn is None or chat_id not in _idx_ready:
        return
    try:
        with conn:
            conn.executemany("DELETE FROM chat_fts WHERE chat_id = ? AND idx = ? AND role = ?",
                             [(chat_id, e["i"], e["r"]) for e in dropped])
        _idx_rows[chat_id] = conn.execute("SELECT COUNT(*) FROM chat_fts WHERE chat_id = ?", (chat_id,)).fetchone()[0]
        _reclaim()
    except Exception as exc:
        logging.error("chat=%s index trim failed (%s); will rebuild", chat_id, exc)
        _idx_ready.discard(chat_id)


def _index_delete_chat(chat_id: str):
    _idx_ready.discard(chat_id)
    _idx_rows.pop(chat_id, None)
    if _conn is None:
        return
    try:
        with _conn:
            _conn.execute("DELETE FROM chat_fts WHERE chat_id = ?", (chat_id,))
        _reclaim()
    except Exception as exc:
        logging.error("chat=%s index delete failed: %s", chat_id, exc)


def _sync_bank_index(banks: list):
    """Index only banks whose mtime changed; drop banks that disappeared."""
    conn = _db()
    if conn is None:
        return
    try:
        current = {b.name: b for b in banks}
        changed = False
        with conn:
            for name in [n for n in _bank_indexed if n not in current]:
                conn.execute("DELETE FROM bank_fts WHERE bank = ?", (name,))
                _bank_indexed.pop(name, None)
                changed = True
            for name, b in current.items():
                if _bank_indexed.get(name) == b.mtime:
                    continue
                changed = True
                conn.execute("DELETE FROM bank_fts WHERE bank = ?", (name,))
                chunks = _merge_chunks(_chunk_text(b.content, BANK_CHUNK_CHARS), BANK_CHUNK_CHARS)
                conn.executemany("INSERT INTO bank_fts(text, bank, ord) VALUES (?,?,?)",
                                 [(c, name, n) for n, c in enumerate(chunks)])
                _bank_indexed[name] = b.mtime
        if changed:
            _reclaim()
    except Exception as exc:
        logging.error("bank index sync failed (%s); will retry", type(exc).__name__)
        _bank_indexed.clear()


def _query_terms(text: str, limit: int = 16) -> list:
    """Distinct content words, longest first (longer words tend to be the more specific ones)."""
    seen, out = set(), []
    for w in WORD_RE.findall(text.lower()):
        if len(w) > 2 and w not in STOPWORDS and w not in seen and re.search(r"[a-z0-9]", w):
            seen.add(w)
            out.append(w)
    out.sort(key=lambda w: -len(w))
    return out[:limit]


def _fts_query(terms: list) -> str:
    return " OR ".join('"%s"' % t for t in terms)   # terms are [a-z0-9_]+, so quoting is safe


# Instruction boilerplate that says nothing about the TOPIC of a question. Ignored when deciding what a
# question matches (a prompt like "In about 120 words, explain ..." must not recall other such prompts).
GENERIC_WORDS = set("""
about words word explain describe summarize summarise summary write tell give show please help using
use need want make does did can could would should also just short sentence reply respond why
any some there here then than them they their our out not but all one get got let say see way work works working
""".split())
GENERIC_WORDS |= {w[:-1] for w in GENERIC_WORDS if len(w) > 3 and w.endswith("s")} | {_stem(w) for w in GENERIC_WORDS}


# "in about 120 words", "under 5 sentences": a length request, not a topic
LENGTH_RE = re.compile(r"\b\d+\s*(?:words?|sentences?|lines?|bullets?|paragraphs?|characters?|chars?)\b", re.I)


def _question_terms(turns: list):
    """(terms for the index query, keyword set for the relevance gate, keyword set of the question).
    A very short question ("why?") borrows the previous user message's terms."""
    users = [m for m in turns if m.get("role") == "user"]
    last = LENGTH_RE.sub(" ", str(users[-1].get("content") or "")) if users else ""
    qkw_last = keywords(last)
    terms, qkw = _query_terms(last), set(qkw_last)
    if len(qkw_last - GENERIC_WORDS) < 3 and len(users) > 1:
        prev = LENGTH_RE.sub(" ", str(users[-2].get("content") or ""))
        terms = _query_terms(last + " " + prev)
        qkw |= keywords(prev)
    terms = [t for t in terms if t not in GENERIC_WORDS]
    return terms, {w for w in qkw if w not in GENERIC_WORDS}, qkw_last


def _match_count(qkw: set, ckw: set) -> int:
    """How many question keywords appear in the chunk (exact, or sharing a 5-letter prefix)."""
    n = 0
    for q in qkw:
        if q in ckw or (len(q) >= 5 and any(len(c) >= 5 and c[:5] == q[:5] for c in ckw)):
            n += 1
    return n


def _term_df(conn, chat_id: str, term: str) -> int:
    """In how many of this chat's chunks does the term occur? (An index lookup, so it uses the same
    tokenizer/stemmer as the index itself.)"""
    return conn.execute("SELECT COUNT(*) FROM chat_fts WHERE chat_fts MATCH ? AND chat_id = ?",
                        ('"%s"' % term, chat_id)).fetchone()[0]


def _distinctive_terms(conn, chat_id: str, terms: list) -> list:
    """Question words that are rare in this chat (<= max(3, ARCHIVE_DISTINCT_FRACTION of its chunks))."""
    limit = max(3, int(ARCHIVE_DISTINCT_FRACTION * _idx_rows.get(chat_id, 0)))
    return [t for t in terms if _term_df(conn, chat_id, t) <= limit]


def _chat_candidates(conn, chat_id: str, terms: list, limit: int) -> list:
    sql = ("SELECT text, idx, ord, role, bm25(chat_fts) FROM chat_fts "
           "WHERE chat_fts MATCH ? AND chat_id = ?"
           + ("" if MEMORY_INCLUDE_ASSISTANT else " AND role = 'user'")
           + " ORDER BY rank LIMIT ?")
    return conn.execute(sql, (_fts_query(terms), chat_id, limit)).fetchall()


def recall_from_index(chat_id: str, turns: list, max_tokens: int):
    """Ranked FTS5/BM25 lookup over this chat's archived turns. Returns (block, n_chunks), or None
    if the index is unavailable (caller falls back to the keyword scan)."""
    conn = _db()
    if conn is None:
        return None
    if max_tokens < 60:
        return "", 0
    try:
        _ensure_chat_index(chat_id)
        terms, qkw, qkw_last = _question_terms(turns)
        if not terms:
            return "", 0
        rows = _chat_candidates(conn, chat_id, terms, ARCHIVE_CANDIDATES)
        if not rows:
            return "", 0
        dkw = {_stem(t) for t in _distinctive_terms(conn, chat_id, terms)}
        if not dkw:
            return "", 0          # the question is all common words: nothing here is worth the window space
    except Exception as exc:
        logging.error("chat=%s index query failed (%s)", chat_id, type(exc).__name__)
        return None

    need = max(1, min(int(ARCHIVE_MIN_SCORE), len(qkw)))   # distinct question words a chunk must share
    header = RECALL_HEADER if MEMORY_INCLUDE_ASSISTANT else RECALL_HEADER_USER
    budget = max_tokens - est_tokens_text(header) - 2
    picked, seen_txt, covered = [], set(), set()
    n_asst = 0

    def consider(text, idx, ord_, role):
        nonlocal budget, n_asst
        t = text.strip()
        if not t or t in seen_txt:
            return
        ckw = keywords(t)
        if qkw_last and len(qkw_last & ckw) / len(qkw_last | ckw) >= 0.7:
            return                                        # the user is re-asking this
        if not MEMORY_INCLUDE_ASSISTANT and t.endswith("?"):
            return                                        # a bare question carries no facts
        if _match_count(qkw, ckw) < need:
            return
        if role == "user":
            if _match_count(dkw, ckw) < 1:
                return
        else:
            # The model's own words only ever ADD coverage: they must match a distinctive question word
            # that no recalled user chunk covers, so a wrong reply can't sit next to the user's fact.
            fresh = dkw - covered
            if not fresh or _match_count(fresh, ckw) < 1 or n_asst >= ARCHIVE_MAX_ASSISTANT_CHUNKS:
                return
        line = ("- " if role == "user" else "- [assistant] ") + t
        cost = est_tokens_text(line)
        if cost > budget:
            return
        picked.append((idx, ord_, line))
        seen_txt.add(t)
        budget -= cost
        covered.update(d for d in dkw if _match_count({d}, ckw))
        if role != "user":
            n_asst += 1

    for text, idx, ord_, role, _score in rows:           # user statements first, best BM25 first
        if role == "user" and len(picked) < ARCHIVE_MAX_CHUNKS:
            consider(text, idx, ord_, role)
    for text, idx, ord_, role, _score in rows:           # then replies that add something new
        if role != "user" and len(picked) < ARCHIVE_MAX_CHUNKS:
            consider(text, idx, ord_, role)
    if not picked:
        return "", 0
    picked.sort(key=lambda p: (p[0], p[1]))               # conversation order reads naturally
    return header + "\n" + "\n".join(p[2] for p in picked), len(picked)


def bank_excerpts(bank, terms: list, qkw: set, max_tokens: int):
    """For a relevant bank that is too big to load whole: its best-matching chunks as a Bank."""
    if max_tokens < 60 or not terms:
        return None
    conn = _db()
    if conn is None:
        return None
    try:
        rows = conn.execute(
            "SELECT text, ord FROM bank_fts WHERE bank_fts MATCH ? AND bank = ? "
            "ORDER BY rank LIMIT ?",
            (_fts_query(terms), bank.name, BANK_EXCERPT_MAX_CHUNKS * 3)).fetchall()
        n_chunks = conn.execute("SELECT COUNT(*) FROM bank_fts WHERE bank = ?", (bank.name,)).fetchone()[0]
        limit_df = max(3, int(ARCHIVE_DISTINCT_FRACTION * n_chunks))
        dkw = {_stem(t) for t in terms if conn.execute(
            "SELECT COUNT(*) FROM bank_fts WHERE bank_fts MATCH ? AND bank = ?",
            ('"%s"' % t, bank.name)).fetchone()[0] <= limit_df}
    except Exception as exc:
        logging.error("bank=%s excerpt query failed (%s)", bank.name, type(exc).__name__)
        return None
    need = max(1, min(int(ARCHIVE_MIN_SCORE), len(qkw)))
    picked, budget = [], max_tokens
    for text, ord_ in rows:
        ckw = keywords(text)
        if _match_count(qkw, ckw) < need or _match_count(dkw, ckw) < 1:
            continue
        cost = est_tokens_text(text) + 2
        if cost > budget:
            continue
        picked.append((ord_, text))
        budget -= cost
        if len(picked) >= BANK_EXCERPT_MAX_CHUNKS:
            break
    if not picked:
        return None
    picked.sort()
    return Bank(bank.name, bank.description, "\n...\n".join(t for _, t in picked),
                dynamic=False, mtime=bank.mtime, excerpt=True)


# ---------- v5.1 deterministic fact ledger ----------

SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
FACTISH_RE = re.compile(r"\d|[A-Z]{2,}|\b[a-z]+_[a-z]+\b|\"[^\"]+\"|[/\\][A-Za-z0-9_.-]+")


def _norm_fact(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _clean_fact(s: str) -> str:
    s = re.sub(r"^[\s>*#-]+", "", s.strip())      # markdown bullets/quotes
    s = re.sub(r"^\d+[.)]\s*", "", s)             # numbered list markers ("10.", "3. ")
    return s.strip()


def _is_junk_fact(s: str) -> bool:
    if not (8 <= len(s) <= 200):
        return True
    if not re.search(r"[A-Za-z]{3}", s):          # bare numbers, "10.", "03:41"
        return True
    if re.fullmatch(r"\([^)]*\)", s):             # "(passage 1 of 8)"
        return True
    return False


def parse_session_content(content: str):
    """Inverse of the bridge-written session bank body: (facts list, context or None)."""
    facts, ctx_lines, in_facts = [], [], False
    for raw in content.splitlines():
        line = raw.strip()
        u = line.upper()
        if u.startswith("FACTS:"):
            in_facts = True
            rest = line[6:].strip()
            if rest.startswith("- "):
                facts.append(rest[2:].strip())
            continue
        if u.startswith("CONTEXT:"):
            in_facts = False
            ctx_lines.append(line[8:].strip())
            continue
        if in_facts:
            if line.startswith("- ") and len(line) > 2:
                facts.append(line[2:].strip())
            elif line:
                facts.append(line)
        elif ctx_lines:
            ctx_lines.append(line)
    context = " ".join(x for x in ctx_lines if x) or None
    return facts, context


def parse_reply_facts(text: str):
    """Deterministically pull FACTS lines and CONTEXT out of a consolidation reply."""
    facts, context, in_facts = [], None, False
    for raw in text.splitlines():
        line = raw.strip()
        u = line.upper()
        if u.startswith("FACTS:"):
            in_facts = True
            rest = line[6:].strip()
            if rest.startswith("- "):
                facts.append(rest[2:].strip())
            continue
        if u.startswith("CONTEXT:"):
            in_facts = False
            context = line[8:].strip() or None
            continue
        if in_facts and line:
            if line.startswith("- "):
                facts.append(line[2:].strip())
            elif len(line) <= 200:
                facts.append(line)
    return [f for f in facts if f], context


def extract_facts_regex(msgs: list) -> list:
    """Deterministic fallback extractor for chunks the model failed to format.
    v5.2: only USER turns - assistant sentences may be hallucinated and must not become 'facts'."""
    facts = []
    for m in msgs:
        if m.get("role") != "user":
            continue
        for line in str(m.get("content") or "").splitlines():
            for sent in SENT_SPLIT_RE.split(line.strip()):
                s = sent.strip()
                if 3 <= len(s) <= 200 and FACTISH_RE.search(s):
                    facts.append(s)
    return facts[:24]


def _read_ledger(chat_id: str):
    f = CHATS_DIR / chat_id / "session.txt"
    if not f.is_file():
        return [], None
    try:
        _, content = parse_bank_text(f.read_text(encoding="utf-8", errors="replace"), "")
    except OSError:
        return [], None
    return parse_session_content(content)


_tasks: set = set()


def _spawn(coro):
    """asyncio keeps only a weak reference to a task: hold our own so a pending background task
    (consolidation, sweeper) cannot be garbage-collected mid-flight."""
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return t


async def _consolidate(chat_id: str, model: str):
    """Extract facts from evicted turns into an append-only, bridge-managed ledger.

    The model only EXTRACTS facts from one new segment; the bridge parses the reply, dedups,
    and carries every fact forward verbatim. Ledger cap: FIFO at DYN_BANK_MAX_TOKENS.
    v5.2: turns arrive here exactly once (see _ingest_evicted), the ledger is sized to fit its
    own cap including list markers and context, and a /forget during the NPU call cancels the write.
    """
    if chat_id in _inflight:
        return  # a consolidation task for this chat is already draining the queue
    _inflight.add(chat_id)
    gen = _gen.get(chat_id, 0)
    drained = []       # original, untruncated messages removed from the queue in this attempt
    committed = False  # becomes True only after the updated session ledger is atomically installed
    try:
        msgs = _pending.setdefault(chat_id, [])
        if not msgs:
            return

        system = (
            "You are a fact extractor on a small-context edge device. "
            "List the facts stated in the conversation segment below.\n"
            "Reply in exactly this format:\n"
            "FACTS:\n"
            "- one fact per line, copied EXACTLY as stated\n"
            "- include every identifier, name, number, version, path, port, setting, "
            "error, decision and fixed detail\n"
            "CONTEXT: one or two sentences on what the conversation is about\n"
            f"Keep the whole reply under {CONSOLIDATE_MAX_WORDS} words. "
            "Copy values exactly. Do not invent facts. "
            "If the segment states nothing factual, reply with FACTS: and no lines."
        )

        # --- drain the pending queue in window-sized chunks (oldest first) ---
        seg_budget = max(200, CONSOLIDATE_PROMPT_TOKENS - est_tokens_text(system) - 20)
        chunk, used = [], 0
        while msgs:
            m = msgs.pop(0)
            drained.append(m)  # retain the original even if the prompt copy is truncated below
            cost = est_tokens(m)
            if not chunk:
                if cost > seg_budget:  # single oversized turn: keep its head
                    m = dict(m)
                    m["content"] = str(m.get("content") or "")[:max(0, (seg_budget - 8) * CHARS_PER_TOKEN)]
                    cost = est_tokens(m)
                chunk.append(m)
                used += cost
            elif used + cost <= seg_budget:
                chunk.append(m)
                used += cost
            else:
                msgs.insert(0, m)  # stays queued for the next chunk
                drained.pop()      # it was not actually drained by this attempt
                break
        if not chunk:
            return

        seg = "\n".join("%s: %s" % (m.get("role"), str(m.get("content") or "")) for m in chunk)
        payload = {"model": model, "stream": False,
                   "options": {"num_predict": CONSOLIDATE_NUM_PREDICT},
                   "messages": [
                       {"role": "system", "content": system},
                       {"role": "user", "content": "CONVERSATION SEGMENT:\n" + seg}]}

        data = await _upstream_chat(payload)
        if _gen.get(chat_id, 0) != gen:
            logging.info("chat=%s session discarded during consolidation; result dropped", chat_id)
            return
        if not data:
            _pending[chat_id] = chunk + msgs
            return
        text = THINK_RE.sub("", str(data.get("message", {}).get("content") or "")).strip()
        new_facts, new_context = parse_reply_facts(text)
        if not new_facts:
            # never silently lose a chunk the model failed to format
            new_facts = extract_facts_regex(chunk)
            logging.warning("chat=%s consolidation reply had no FACTS lines (reply was %d chars); "
                            "regex fallback kept %d candidate facts", chat_id, len(text), len(new_facts))
        if not new_facts and not new_context:
            # The prompt asks the model to answer "FACTS:" with no lines when a segment holds nothing
            # factual, so this is a normal outcome. Requeueing it made EVERY later request re-run the
            # same extraction on the NPU (holding the gate) forever. The turns stay in the archive and
            # the index, so recall still finds them.
            logging.info("chat=%s segment of %d turns held no facts (reply %d chars); consumed",
                         chat_id, len(chunk), len(text))
            _inflight.discard(chat_id)
            if msgs:
                _spawn(_consolidate(chat_id, model))
            return

        facts, context = _read_ledger(chat_id)
        seen = {_norm_fact(f) for f in facts}
        added = 0
        for f in new_facts:
            f = _clean_fact(f)
            if _is_junk_fact(f):
                continue
            n = _norm_fact(f)
            if n and n not in seen:
                seen.add(n)
                facts.append(f[:200])
                added += 1
        if new_context:
            context = new_context[:120]

        # FIFO cap sized to the whole bank body: "- " + newline per fact, plus header/context
        cap_chars = DYN_BANK_MAX_TOKENS * CHARS_PER_TOKEN - 170
        while facts and sum(len(f) + 3 for f in facts) > cap_chars:
            dropped = facts.pop(0)
            logging.warning("chat=%s fact ledger full; dropped oldest fact (%d chars)",
                            chat_id, len(dropped))

        content = "FACTS:\n" + "".join("- %s\n" % f for f in facts)
        if context:
            content += "\nCONTEXT: %s\n" % context
        d = CHATS_DIR / chat_id
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "session.txt.tmp"
        tmp.write_text(
            "session memory: facts extracted by the model, kept verbatim by the bridge\n---\n"
            + content + "\n", encoding="utf-8")
        os.replace(tmp, d / "session.txt")
        committed = True
        logging.info("chat=%s consolidated: facts=%d (+%d new) | segment=%d est. tokens, "
                     "%d turns | %d turns still queued",
                     chat_id, len(facts), added, used, len(chunk), len(msgs))

        # chain: drain the rest of the queue without waiting for the next user turn
        _inflight.discard(chat_id)  # hand off before scheduling the next chunk
        if msgs:
            _spawn(_consolidate(chat_id, model))
    except Exception as exc:
        # A failed attempt must not discard turns already popped from the pending queue.
        # Do not resurrect them after /forget or session discard, and do not requeue after
        # the atomic ledger replace has succeeded.
        if drained and not committed and _gen.get(chat_id, 0) == gen:
            pending = _pending.setdefault(chat_id, [])
            pending[:0] = drained
            logging.warning("chat=%s consolidation failed; requeued %d drained turns", chat_id, len(drained))
        logging.error("chat=%s consolidation failed: %s", chat_id, exc)
    finally:
        _inflight.discard(chat_id)


# ---------- session lifecycle: user-controlled persistence ----------

def _discard_session(chat_id: str, reason: str):
    d = CHATS_DIR / chat_id
    if d.is_dir():
        for f in d.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            d.rmdir()
        except OSError:
            pass
    _bank_cache.pop(str(d / "session.txt"), None)
    _pending.pop(chat_id, None)
    _last_seen.pop(chat_id, None)
    _seen.pop(chat_id, None)
    _hw.pop(chat_id, None)
    _arch_n.pop(chat_id, None)
    _index_delete_chat(chat_id)
    _gen[chat_id] = _gen.get(chat_id, 0) + 1
    logging.info("chat=%s session state discarded (%s)", chat_id, reason)


def _bank_target(chat_id: str, name: str | None):
    """(bank_name, path) for a /save. Refuses to replace a file that /save did not write itself."""
    bank_name = SAFE_ID_RE.sub("", name or "")[:64] or chat_id[:64]
    target = BANKS_DIR / f"{bank_name}.txt"
    try:
        if target.is_file():
            first = target.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0]
            if not first.strip().lower().startswith(SESSION_BANK_MARKER):
                raise SaveError(f"a bank named '{bank_name}' already exists and was not created by /save, "
                                f"so I left it alone. Pick another name: /save <name>")
    except OSError as exc:
        raise SaveError(f"cannot inspect {target.name} ({exc.strerror or type(exc).__name__})", 500) from exc
    return bank_name, target


def _is_part_bank(path: Path) -> bool:
    """True for a file /save wrote as one part of a multi-part bank (its first line ends with '(part k of n)')."""
    try:
        first = path.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0]
    except OSError:
        return False
    return first.strip().lower().startswith(SESSION_BANK_MARKER) and bool(PART_RE.search(first))


def _write_banks(items: list):
    """Write one or more banks: stage EVERY file first (a full disk or a permission error then leaves nothing
    behind), then rename them into place. Failures become SaveError so the user sees them in the chat."""
    staged = []
    try:
        BANKS_DIR.mkdir(parents=True, exist_ok=True)
        for target, text in items:
            tmp = target.with_name(target.name + ".tmp")     # not *.txt, so never loaded half-written
            staged.append(tmp)
            tmp.write_text(text, encoding="utf-8")
        for (target, _text), tmp in zip(items, staged):
            os.replace(tmp, target)
    except OSError as exc:
        for tmp in staged:
            try:
                tmp.unlink()
            except OSError:
                pass
        raise SaveError(f"cannot write to {BANKS_DIR} ({exc.strerror or type(exc).__name__}). "
                        f"The bridge's service user needs write access there (check ProtectHome / "
                        f"ReadWritePaths in the systemd unit).", 500) from exc
    _shared_cache["t"] = 0.0   # a saved bank is visible (and indexed) on the very next request


def _drop_stale_parts(base: str, keep: int):
    """A smaller re-save leaves the higher <base>-N parts of the previous save behind, still holding older
    (possibly /forgotten) text and still loaded as shared banks. Remove only files /save wrote as parts."""
    k = keep + 1
    while k < 1000 and _is_part_bank(BANKS_DIR / f"{base}-{k}.txt"):
        try:
            (BANKS_DIR / f"{base}-{k}.txt").unlink()
        except OSError:
            break
        k += 1
    _shared_cache["t"] = 0.0


def _user_statements(chat_id: str, turns) -> list:
    """ALL of the user's own messages in this chat, oldest first, without commands. Nothing is clipped.
    Sources: the archive (turns already evicted from the window; stored clipped to ARCHIVE_TURN_CHARS)
    merged with the live history of the current request (`turns`: everything Open WebUI resent, full
    text). The live request wins on a clash and bounds the archive: archived turns beyond its length
    were deleted from the chat since. Indices are positions in `turns`, the numbering _ingest_evicted
    uses, so the /forget floor applies. Only exact duplicates are collapsed."""
    floor = _floor.get(chat_id, 0)
    limit = len(turns) if turns is not None else None
    by_idx = {e["i"]: e["c"] for e in _read_archive(chat_id)
              if e["r"] == "user" and e["i"] >= floor and (limit is None or e["i"] < limit)}
    for i, m in enumerate(turns or []):
        if i < floor or m.get("role") != "user":
            continue
        text = str(m.get("content") or "").strip()
        if text and not _is_command_noise("user", text):
            by_idx[i] = text
    out, seen = [], set()
    for i in sorted(by_idx):
        if by_idx[i] not in seen:
            seen.add(by_idx[i])
            out.append(by_idx[i])
    return out


def _split_parts(lines: list, limit: int) -> list:
    """Greedy split into parts of at most `limit` BYTES of UTF-8. bank_file_max is a file-size limit and
    _load_one skips bigger files, so counting characters made non-ASCII banks unloadable. Only a single line
    longer than `limit` is sliced (at limit // 4 characters: a character is at most 4 bytes)."""
    blen = lambda s: len(s.encode("utf-8"))
    step = max(1, limit // 4)
    pieces = []
    for ln in lines:
        pieces += [ln[i:i + step] for i in range(0, len(ln), step)] if blen(ln) > limit else [ln]
    parts, cur, used = [], [], 0
    for ln in pieces:
        n = blen(ln) + 1
        if cur and used + n > limit:
            parts.append(cur)
            cur, used = [], 0
        cur.append(ln)
        used += n
    if cur:
        parts.append(cur)
    return parts


def _save_bank(chat_id: str, name: str | None, turns=None):
    """/save: write EVERYTHING the user said in this chat (verbatim, unclipped) plus the ledger's facts
    (labelled as model-extracted) into BANKS_DIR. No size cap: a bank larger than a loadable file is
    split into <name>, <name>-2, ... Deterministic, no NPU call. `turns` is the live history of the
    current request; without it (REST) only the archive is available.
    Returns (bank_names, n_user_messages, n_ledger_facts), or None when there is nothing to save."""
    statements = _user_statements(chat_id, turns)
    facts, _ctx = _read_ledger(chat_id)
    if not statements and not facts:
        return None
    lines = []
    if statements:
        lines.append("USER MESSAGES (verbatim, oldest first):")
        lines += ["- " + t.replace("\r\n", "\n").replace("\n", "\n  ") for t in statements]
    if facts:
        lines.append("MODEL-EXTRACTED FACTS (written by the model, may contain errors):")
        lines += ["- " + f for f in facts]
    base = SAFE_ID_RE.sub("", name or "")[:60] or chat_id[:60]
    parts = _split_parts(lines, max(4096, RAM_PLAN["bank_file_max"] - 4096))
    names = [base if k == 1 else f"{base}-{k}" for k in range(1, len(parts) + 1)]
    targets = [_bank_target(chat_id, nm)[1] for nm in names]      # refuse BEFORE writing anything
    for k, target in enumerate(targets[1:], 2):      # a part may only replace an earlier part, never another bank
        if target.is_file() and not _is_part_bank(target):
            raise SaveError(f"a bank named '{names[k - 1]}' already exists and is not a part of a /save, "
                            f"so I left it alone. Pick another name: /save <name>")
    items = []
    for k, (target, part) in enumerate(zip(targets, parts), 1):
        more = f" (part {k} of {len(parts)})" if len(parts) > 1 else ""
        items.append((target, f"session memory: your messages from one chat, saved verbatim{more}\n---\n"
                      + "\n".join(part) + "\n"))
    _write_banks(items)
    _drop_stale_parts(base, len(parts))
    logging.info("chat=%s bank written to %s as %s (explicit /save, %d messages, %d ledger facts)",
                 chat_id, BANKS_DIR, names, len(statements), len(facts))
    return names, len(statements), len(facts)


def _save_summary(names: list, n_msgs: int, n_facts: int) -> str:
    what = f"{n_msgs} of your messages" + (f" + {n_facts} model-extracted facts (labelled; review them)" if n_facts else "")
    which = ", ".join(f"'{n}'" for n in names)
    return f"Session bank saved as {which}: {what}, nothing cut. It is now a shared bank for every chat."


def _command_response(payload: dict, text: str):
    """Bridge-generated reply to /save or /forget. No NPU call. Honors the stream flag."""
    model = payload.get("model", "bridge")
    done_obj = {"model": model, "message": {"role": "assistant", "content": text},
                "done": True, "done_reason": "stop"}
    if payload.get("stream", True):
        chunk = dict(done_obj, done=False)
        lines = json.dumps(chunk) + "\n" + json.dumps({"model": model, "done": True,
                                                      "done_reason": "stop"}) + "\n"

        def gen():
            yield lines.encode()

        return StreamingResponse(gen(), media_type="application/x-ndjson")
    return JSONResponse(done_obj)


# ---------- v5.4 RAM governor ----------

_gov_t = 0.0


def _pending_bytes() -> int:
    return sum(len(str(m.get("content") or "")) for q in _pending.values() for m in q)


def _ram_used() -> int:
    """Bytes the bridge's memory currently occupies in RAM: chat files + index + debug log +
    in-process queues, caches and hash sets."""
    total = 0
    if CHATS_DIR.is_dir():
        for d in os.scandir(CHATS_DIR):
            if d.is_dir(follow_symlinks=False):
                try:
                    for f in os.scandir(d.path):
                        if f.is_file(follow_symlinks=False):
                            total += f.stat().st_size
                except OSError:
                    pass
    for p in (INDEX_DB, DEBUG_LOG, Path(str(DEBUG_LOG) + ".1")):
        try:
            total += p.stat().st_size
        except OSError:
            pass
    total += _pending_bytes()
    total += 3 * sum(len(b.content) + len(b.description) for b in _shared_cache["banks"])
    total += 120 * sum(len(h) for h in _seen.values())
    return total


def _low_floor(total: int) -> int:
    return max(LOW_MEM_FLOOR_MB * _MIB, int(0.06 * total))


def _chats_lru(exclude):
    """Chats that hold state in RAM, least recently used first (never the one being served)."""
    names = set(_last_seen)
    if CHATS_DIR.is_dir():
        names |= {d.name for d in os.scandir(CHATS_DIR) if d.is_dir(follow_symlinks=False)}
    names.discard(exclude)
    names.discard("unknown")

    def age(n):
        t = _last_seen.get(n)
        if t is None:
            try:
                t = (CHATS_DIR / n).stat().st_mtime
            except OSError:
                t = 0.0
        return t
    return sorted((n for n in names if (CHATS_DIR / n).is_dir() or n in _pending), key=age)


def _governor(current):
    """Safeguards, run at most every GOVERNOR_INTERVAL_S from the request path:
    1) ratchet the budget down if the OS now has less free RAM than at start,
    2) shed least-recently-used chats if system RAM is below the floor,
    3) shed least-recently-used chats if the budget is exceeded,
    4) if it still can't fit, pause new storage (chat keeps working)."""
    global _gov_t, _mem_paused
    now = time.time()
    if now - _gov_t < GOVERNOR_INTERVAL_S:
        return
    _gov_t = now
    mi = _meminfo()
    if not mi:
        return
    _plan_ram(mi, ratchet=True)
    floor = _low_floor(mi["MemTotal"])
    avail = mi["MemAvailable"]
    victims = _chats_lru(current)
    while avail < floor and victims:
        _discard_session(victims.pop(0), "system RAM below floor")
        avail = _meminfo().get("MemAvailable", avail)
    used = _ram_used()
    while used > RAM_PLAN["budget"] and victims:
        _discard_session(victims.pop(0), "memory budget exceeded")
        used = _ram_used()
    paused = avail < floor or used > RAM_PLAN["budget"]
    if paused != _mem_paused:
        logging.warning("RAM governor: new memory storage %s (available %.0f MiB, floor %.0f MiB, "
                        "used %.1f of %.1f MiB)", "PAUSED" if paused else "resumed",
                        avail / _MIB, floor / _MIB, used / _MIB, RAM_PLAN["budget"] / _MIB)
    _mem_paused = paused


@app.on_event("startup")
async def _init_index():
    if BRIDGE_DEBUG:
        logging.warning("BRIDGE_DEBUG is on: prompt text goes to %s (RAM only), not the journal", DEBUG_LOG)
    if INDEX_ENABLED:
        _db()


@app.on_event("startup")
async def _start_sweeper():
    if SESSION_TTL_MINUTES > 0:
        _spawn(_sweep_loop())


async def _sweep_loop():
    while True:
        try:
            now = time.time()
            ttl = SESSION_TTL_MINUTES * 60
            victims = set()
            if CHATS_DIR.is_dir():
                for d in CHATS_DIR.iterdir():
                    if d.is_dir() and d.name not in _inflight:
                        last = _last_seen.get(d.name, d.stat().st_mtime)
                        if now - last > ttl:
                            victims.add(d.name)
            for cid, seen in _last_seen.items():
                if now - seen > ttl and cid not in _inflight:
                    victims.add(cid)
            for cid in victims:
                _discard_session(cid, f"idle > {SESSION_TTL_MINUTES} min")
        except Exception as exc:
            logging.error("sweep error: %s", exc)
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)


# ---------- REST management (before the catch-all so they win the route match) ----------

@app.get("/hailo/session/{chat_id}")
async def session_get(chat_id: str):
    cid = _safe_chat_id(chat_id)
    f = CHATS_DIR / cid / "session.txt"
    if not f.is_file():
        return JSONResponse({"error": "no session bank for this chat"}, status_code=404)
    return JSONResponse({"chat_id": cid, "bank": f.read_text(encoding="utf-8", errors="replace")})


@app.get("/hailo/archive/{chat_id}")
async def archive_get(chat_id: str, n: int = 10):
    """Debug view of the verbatim archive: turn count plus the last n archived turns."""
    cid = _safe_chat_id(chat_id)
    entries = _read_archive(cid)
    return JSONResponse({"chat_id": cid, "turns": len(entries),
                         "floor": _floor.get(cid, 0),
                         "pending_for_ledger": len(_pending.get(cid, [])),
                         "last": entries[-max(1, min(n, 50)):]})


@app.get("/hailo/ram")
async def ram_status():
    mi = _meminfo()
    mib = lambda b: round(b / _MIB, 1)
    return JSONResponse({
        "total_mib": mib(mi.get("MemTotal", 0)), "available_mib": mib(mi.get("MemAvailable", 0)),
        "os_reserve_mib": mib(RAM_PLAN.get("os_reserve", 0)), "usable_at_start_mib": mib(RAM_PLAN.get("usable", 0)),
        "budget_mib": mib(RAM_PLAN["budget"]), "used_mib": mib(_ram_used()), "paused": _mem_paused,
        "low_mem_floor_mib": mib(_low_floor(mi.get("MemTotal", 0))),
        "max_turns_per_chat": _max_turns(), "per_chat_cap_mib": mib(RAM_PLAN["chat_cap"]),
        "queue_cap_mib": mib(RAM_PLAN["pending_cap"]), "bank_file_max_mib": mib(RAM_PLAN["bank_file_max"]),
        "curated_banks_cap_mib": mib(RAM_PLAN["curated_cap"]), "debug_log_max_bytes": RAM_PLAN["debug_log_bytes"],
        "chats_in_ram": len(_chats_lru(None))})


@app.get("/hailo/index")
async def index_status():
    conn = _db()
    if conn is None:
        return JSONResponse({"enabled": INDEX_ENABLED, "ok": False,
                             "note": "FTS5 index disabled or unavailable; using the keyword scan"})
    size = INDEX_DB.stat().st_size if INDEX_DB.exists() else 0
    return JSONResponse({
        "enabled": True, "ok": True, "db": str(INDEX_DB), "size_bytes": size,
        "chat_chunks": conn.execute("SELECT COUNT(*) FROM chat_fts").fetchone()[0],
        "bank_chunks": conn.execute("SELECT COUNT(*) FROM bank_fts").fetchone()[0],
        "banks_indexed": sorted(_bank_indexed), "chats_in_sync": len(_idx_ready)})


@app.get("/hailo/search/{chat_id}")
async def search_get(chat_id: str, q: str, n: int = 8):
    """Try retrieval without chatting: ranked chunks plus exactly what recall would inject."""
    cid = _safe_chat_id(chat_id)
    conn = _db()
    if conn is None:
        return JSONResponse({"error": "index unavailable"}, status_code=503)
    _ensure_chat_index(cid)
    fake = [{"role": "user", "content": q}]
    terms, _, _ = _question_terms(fake)
    ranked = []
    if terms:
        for text, idx, ord_, role, score in _chat_candidates(conn, cid, terms, max(1, min(n, 50))):
            ranked.append({"text": text, "turn": idx, "role": role, "bm25": round(score, 4)})
    res = recall_from_index(cid, fake, ARCHIVE_RECALL_TOKENS)
    distinct = _distinctive_terms(conn, cid, terms) if terms else []
    return JSONResponse({"chat_id": cid, "query_terms": terms, "distinctive_terms": distinct, "ranked": ranked,
                         "would_inject": res[0] if res else "", "chunks": res[1] if res else 0})


@app.post("/hailo/session/{chat_id}/save")
async def session_save(chat_id: str, name: str | None = None):
    cid = _safe_chat_id(chat_id)
    try:
        saved = _save_bank(cid, name)       # REST cannot see the live history: archive + ledger only
    except SaveError as exc:
        return JSONResponse({"error": str(exc)}, status_code=exc.status)
    if saved is None:
        return JSONResponse({"error": "nothing archived for this chat yet (REST /save cannot see the live "
                                      "history; send /save from inside the chat instead)"}, status_code=404)
    names, n_msgs, n_facts = saved
    return JSONResponse({"saved": f"{names[0]}.txt", "files": [f"{n}.txt" for n in names],
                         "messages": n_msgs, "ledger_facts": n_facts})


@app.delete("/hailo/session/{chat_id}")
async def session_delete(chat_id: str):
    cid = _safe_chat_id(chat_id)
    _discard_session(cid, "user requested (REST)")
    return JSONResponse({"discarded": cid})


@app.post("/api/chat")
async def chat(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    # Per-chat dynamic memory REQUIRES ENABLE_FORWARD_USER_INFO_HEADERS=True.
    chat_id = _safe_chat_id(request.headers.get("x-openwebui-chat-id"))
    if not MEMORY_ENABLED:
        chat_id = "unknown"   # no per-chat memory unless storage is RAM (see _on_ram)
    _last_seen[chat_id] = time.time()
    _governor(chat_id)

    messages = payload.get("messages", [])
    system_msgs = [m for m in messages if m.get("role") == "system"]
    turns = [m for m in messages if m.get("role") != "system"]
    if chat_id != "unknown":
        # v5.4.6: recompute the /forget floor from the resent history, so it survives a restart.
        _floor[chat_id] = max(_floor.get(chat_id, 0), _forget_floor(turns))

    # --- user session commands: intercepted before anything else, no NPU call ---
    last_user = next((m for m in reversed(turns) if m.get("role") == "user"), None)
    cmd_text = str((last_user or {}).get("content") or "").strip()
    save_m = SAVE_RE.match(cmd_text)
    forget_m = FORGET_RE.match(cmd_text)
    if save_m or forget_m:
        if chat_id == "unknown":
            return _command_response(payload, "Session memory is off: CHATS_DIR is not on RAM (see the bridge log)."
                                     if not MEMORY_ENABLED else
                                     "Session commands need ENABLE_FORWARD_USER_INFO_HEADERS=True on Open WebUI.")
        if forget_m:
            _discard_session(chat_id, "user requested (/forget)")
            # Everything up to and including this command stays forgotten, even though Open WebUI
            # keeps resending it. The command itself is the last turn (index len(turns) - 1), so the
            # floor is len(turns): the very NEXT message is remembered again. (v5.4.6: the floor is
            # also recomputed from the resent history on every request, so a restart does not lose it.)
            _floor[chat_id] = len(turns)
            return _command_response(payload, "Session bank discarded.")
        # /save: everything you said in this chat (this request's history, merged with the archive)
        # plus the ledger's facts. Reply texts start with "Session bank" so they stay command-noise.
        try:
            saved = _save_bank(chat_id, save_m.group(1), turns)
        except SaveError as exc:
            return _command_response(payload, f"Session bank not saved: {exc}")
        if saved:
            return _command_response(payload, _save_summary(*saved))
        return _command_response(
            payload,
            "No session bank to save yet - you haven't written anything in this chat that can be "
            "saved (or the session was just forgotten).")

    base = "\n\n".join(str(m.get("content") or "") for m in system_msgs).strip() or (
        "You are an expert software engineering assistant."
    )
    base = _cap_base(base, chat_id)
    blueprint = BLUEPRINT_BY_CHAT.get(chat_id, DEFAULT_BLUEPRINT)

    banks = load_banks(chat_id)
    scored = score_banks(banks, turns)

    # Budget is reserved for the worst case (rules + the "not loaded" line), whatever ends up injected.
    core = build_system(base, blueprint, banks, [], missed=banks)
    remaining = MAX_PROMPT_TOKENS - est_tokens_text(core)
    if banks and remaining < 100:
        logging.error("chat=%s index+rules est. %d/%d tokens; shrink bank descriptions",
                      chat_id, est_tokens_text(core), MAX_PROMPT_TOKENS)

    # Banks may use up to BANK_BUDGET_FRACTION of what's left, but never eat the history floor.
    bank_budget = max(0, min(int(remaining * BANK_BUDGET_FRACTION),
                             remaining - MIN_HISTORY_TOKENS))
    banks_used = 0
    selected = []
    q_terms, q_kw, _ = _question_terms(turns)
    for score, b in scored:
        if score <= 0:
            break
        if b.tokens + 8 > bank_budget:
            if not b.dynamic:   # relevant but too big to load whole: load its best-matching chunks
                ex = bank_excerpts(b, q_terms, q_kw, min(bank_budget - 8, BANK_EXCERPT_TOKENS))
                if ex:
                    selected.append(ex)
                    bank_budget -= ex.tokens + 8
                    banks_used += ex.tokens + 8
            continue
        selected.append(b)
        bank_budget -= b.tokens + 8
        banks_used += b.tokens + 8

    # v5.4.7: banks that match the question but were not loaded (too big, no excerpt, no budget).
    loaded_names = {b.name for b in selected}
    missed = [b for score, b in scored if score > 0 and b.name not in loaded_names]

    # Pass 1: fit the window without recall, archive whatever it evicts (including turns that
    # fell out of the window on THIS request), then retrieve recall from the archive.
    sys_plain = {"role": "system", "content": build_system(base, blueprint, banks, selected, missed=missed)}
    kept, evicted, truncated = fit_window(sys_plain, turns)
    _ingest_evicted(chat_id, evicted)

    system_message = sys_plain
    n_recall = 0
    if chat_id != "unknown":
        recall_budget = min(ARCHIVE_RECALL_TOKENS, remaining - banks_used - MIN_HISTORY_TOKENS)
        res = recall_from_index(chat_id, turns, recall_budget)
        if res is None:   # index disabled/unavailable/failed: keyword scan over archive.jsonl
            res = recall_from_archive(chat_id, turns, recall_budget)
        recall, n_recall = res
        if recall:
            # Pass 2: the recall block takes window space; re-fit and archive any extra evictions.
            system_message = {"role": "system",
                              "content": build_system(base, blueprint, banks, selected, recall, missed)}
            kept, evicted, truncated = fit_window(system_message, turns)
            _ingest_evicted(chat_id, evicted)

    if truncated:
        logging.warning("chat=%s latest message tail-truncated to fit budget", chat_id)

    payload["messages"] = [system_message] + kept
    est_prompt = est_tokens(system_message) + sum(est_tokens(m) for m in kept)

    # Keep prompt + generation inside the HEF window (client value is only ever lowered).
    opts = payload.get("options")
    if not isinstance(opts, dict):
        opts = {}
    opts.update(FORCE_OPTIONS)  # operator overrides win over whatever the client sent
    req = opts.get("num_predict")
    if not isinstance(req, int) or req <= 0:
        req = 10 ** 6
    room = max(64, HEF_CONTEXT_TOKENS - est_prompt - OUTPUT_MARGIN_TOKENS)
    opts["num_predict"] = min(req, room)
    payload["options"] = opts

    if BRIDGE_DEBUG:
        for m in payload["messages"]:
            lim = 1500 if m.get("role") == "system" else 300
            _dbg("chat=%s %s: %r", chat_id, m.get("role"), str(m.get("content") or "")[:lim])
        _dbg("chat=%s options=%s", chat_id, json.dumps(opts))
    logging.info(
        "chat=%s banks=%d loaded=%s recall=%d idx=%s archived=%d est_prompt=%d/%d num_predict=%d turns=%d/%d",
        chat_id, len(banks), [b.name + ("*" if b.excerpt else "") for b in selected], n_recall,
        "fts5" if _conn is not None else "scan",
        len(_seen.get(chat_id, ())), est_prompt, MAX_PROMPT_TOKENS,
        opts["num_predict"], len(kept), len(turns),
    )

    resp = await forward(
        "POST", "api/chat",
        json.dumps(payload).encode(),
        {"content-type": "application/json", "accept-encoding": "identity"},
        locked=True,
    )

    # Deferred consolidation into the RAM session bank (queue is filled by _ingest_evicted).
    if LEDGER_ENABLED and chat_id != "unknown" and not _mem_paused:
        est_pending = sum(est_tokens(m) for m in _pending.get(chat_id, []))
        if est_pending >= CONSOLIDATE_MIN_TOKENS and chat_id not in _inflight:
            _spawn(_consolidate(chat_id, payload.get("model", "")))
    return resp


@app.api_route("/{path:path}", methods=["GET", "POST", "DELETE", "HEAD"])
async def passthrough(path: str, request: Request):
    body = await request.body()
    headers = {"accept-encoding": "identity"}
    if request.headers.get("content-type"):
        headers["content-type"] = request.headers["content-type"]
    target = path + ("?" + request.url.query if request.url.query else "")
    return await forward(request.method, target, body or None, headers, locked=(path == "api/generate"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=BRIDGE_HOST, port=BRIDGE_PORT)


