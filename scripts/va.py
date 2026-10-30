#!/usr/bin/env python3
"""VA pipeline: deterministic orchestration so small models only do small, schema-checked tasks.

Stages per run:  summarize (index files) -> review (file x checklist) -> triage (one candidate) -> report
Everything except the three LLM task types is done here, deterministically.

Python >= 3.11, standard library only.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("va.py needs Python 3.11+ (tomllib)")

VA_ROOT = Path(__file__).resolve().parent.parent
AGENTS = VA_ROOT / ".agents"

TAGS = [
    "http-input", "db", "shell", "filesystem", "template", "deserialize", "xml", "outbound-http",
    "auth", "session", "crypto", "config", "secrets", "ci", "container", "iac", "llm",
    "memory-unsafe", "regex",
]
KINDS = {"entry", "lib", "config", "test", "ci", "iac", "docs", "build", "other"}
SEVERITIES = ["critical", "high", "medium", "low", "info"]
CONFIDENCE = {"high", "medium", "low"}
ATTACKERS = {"unauthenticated", "user", "admin", "local", "ci-committer", "unknown"}
STATUSES = {"confirmed", "likely", "needs_info", "false_positive"}
STAGES = ["summarize", "review", "triage"]

DEFAULTS = {
    "model": "claude-haiku-5-5",
    "escalate_model": "",
    "escalate_when": ["critical", "high"],
    "retro_model": "claude-haiku-5-5",
    "runner": "claude",
    "runner_cmd": "",
    "jobs": 4,
    "max_file_bytes": 200_000,
    "chunk_lines": 400,
    "chunk_overlap": 30,
    "summary_lines": 600,
    "full_every": 4,
    "review_budget": 300,
    "rotate_per_run": 20,
    "semgrep_config": "p/default",
    "exclude": [],
}

DEFAULT_EXCLUDE = [
    "node_modules/**", "**/node_modules/**", "vendor/**", "**/vendor/**", "third_party/**",
    "dist/**", "build/**", "out/**", "target/**", ".venv/**", "venv/**", "__pycache__/**",
    "*.min.js", "*.min.css", "*.map", "*.lock", "package-lock.json", "pnpm-lock.yaml",
    "yarn.lock", "go.sum", "*.snap", "*.svg", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico",
    "*.pdf", "*.woff", "*.woff2", "*.ttf", "*.zip", "*.gz", "*.jar", "*.so", "*.dll", "*.exe",
]

LANG_BY_EXT = {
    ".py": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".go": "go", ".java": "java", ".kt": "kotlin",
    ".rb": "ruby", ".php": "php", ".cs": "csharp", ".rs": "rust", ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".hpp": "cpp", ".swift": "swift", ".scala": "scala",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".ps1": "powershell",
    ".yml": "yaml", ".yaml": "yaml", ".tf": "terraform", ".hcl": "terraform",
    ".html": "html", ".htm": "html", ".vue": "vue", ".svelte": "svelte", ".erb": "erb",
    ".ejs": "ejs", ".hbs": "handlebars", ".jinja": "jinja", ".j2": "jinja", ".twig": "twig",
    ".sql": "sql", ".json": "json", ".toml": "toml", ".ini": "ini", ".xml": "xml",
    ".gradle": "gradle", ".properties": "properties", ".conf": "conf",
}
LANG_BY_NAME = {"Dockerfile": "dockerfile", "Makefile": "make", "Jenkinsfile": "groovy", "Procfile": "procfile"}
# Path hints used as a floor for risk, so a poisoned or wrong summary cannot hide an entry point.
ENTRY_HINT = re.compile(r"(route|controller|handler|api|view|endpoint|middleware|auth|login|session|webhook|upload|admin)", re.I)


# ----------------------------------------------------------------------------- utils

def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def rjson(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def wjson(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def git(src: Path, *args: str, check=True) -> str:
    r = subprocess.run(["git", "-C", str(src), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def target_id(repo: str) -> str:
    return repo.strip("/").replace("/", "__")


def va_version() -> str:
    return (AGENTS / "VERSION").read_text().strip()


def operator_dir(root: Path | None) -> Path:
    return (root or VA_ROOT) / "operator"


def load_config(root: Path | None, repo: str | None = None) -> dict:
    cfg = dict(DEFAULTS)
    path = operator_dir(root) / "va.toml"
    data = tomllib.loads(path.read_text()) if path.exists() else {}
    cfg.update(data.get("defaults", {}))
    cfg["targets"] = data.get("targets", [])
    if repo:
        for t in cfg["targets"]:
            if t.get("repo") == repo:
                cfg.update({k: v for k, v in t.items() if k != "repo"})
    return cfg


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    meta: dict = {}
    for line in text[4:end].splitlines():
        line = line.split(" #", 1)[0].rstrip()
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            meta[k.strip()] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        else:
            meta[k.strip()] = v.strip("'\"")
    return meta, text[end + 4:].lstrip("\n")


def load_checklists() -> list[dict]:
    out = []
    for p in sorted((AGENTS / "checklists").glob("*.md")):
        if p.name == "README.md":
            continue
        meta, body = parse_frontmatter(p.read_text(encoding="utf-8"))
        meta["body"] = body.strip()
        meta["file"] = p.name
        out.append(meta)
    return out


def model_notes(model: str, stage: str, root: Path | None) -> str:
    """Lines tagged '- [stage]' from the model profile and operator overrides."""
    notes = []
    for p in (AGENTS / "model-profiles" / f"{model}.md", operator_dir(root) / "overrides.md"):
        if p.exists():
            text = re.sub(r"<!--.*?-->", "", p.read_text(encoding="utf-8"), flags=re.S)
            for line in text.splitlines():
                m = re.match(rf"\s*-\s*\[(?:{stage}|all)\]\s*(.+)", line)
                if m:
                    notes.append("- " + m.group(1).strip())
    return ("\n## Extra rules for this run\n" + "\n".join(notes)) if notes else ""


def lang_of(path: str) -> str | None:
    name = os.path.basename(path)
    if name in LANG_BY_NAME or name.startswith("Dockerfile"):
        return LANG_BY_NAME.get(name, "dockerfile")
    if name.startswith(".env"):
        return "dotenv"
    return LANG_BY_EXT.get(os.path.splitext(name)[1].lower())


def excluded(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(os.path.basename(path), pat) for pat in patterns)


def is_text(p: Path) -> bool:
    try:
        with p.open("rb") as f:
            return b"\0" not in f.read(8192)
    except OSError:
        return False


def numbered(lines: list[str], start: int) -> str:
    return "\n".join(f"{i:>5} | {l}" for i, l in enumerate(lines, start))


def fill(template: str, **kw) -> str:
    for k, v in kw.items():
        template = template.replace("{{" + k + "}}", str(v))
    return template


def fingerprint(category: str, path: str, line_text: str) -> str:
    norm = re.sub(r"\s+", "", line_text)
    return hashlib.sha256(f"{category}:{path}:{norm}".encode()).hexdigest()[:16]


def extract_json(text: str):
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    raise ValueError("no JSON object in model output")


# ----------------------------------------------------------------------------- run layout

class Run:
    def __init__(self, path: Path):
        self.path = path
        self.meta = rjson(path / "meta.json", {})
        self.queue = rjson(path / "queue.json", {"tasks": {}})

    @property
    def target_dir(self) -> Path:
        return self.path.parent.parent

    @property
    def src(self) -> Path:
        return Path(self.meta["src"])

    @property
    def root(self) -> Path:
        return Path(self.meta["root"])

    def save(self):
        wjson(self.path / "meta.json", self.meta)
        wjson(self.path / "queue.json", self.queue)

    def result(self, tid: str):
        return rjson(self.path / "results" / f"{tid}.json")

    def failed(self, tid: str):
        return rjson(self.path / "failures" / f"{tid}.json")

    def pending(self, stage: str) -> list[dict]:
        return [t for t in self.queue["tasks"].get(stage, [])
                if not (self.path / "results" / f"{t['id']}.json").exists()
                and not (self.path / "failures" / f"{t['id']}.json").exists()]

    def current_stage(self) -> str | None:
        for s in STAGES:
            if s not in self.queue["tasks"] or self.pending(s):
                return s
        return None


def load_index(target_dir: Path) -> dict[str, dict]:
    p = target_dir / "index" / "files.jsonl"
    if not p.exists():
        return {}
    return {r["path"]: r for r in (json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip())}


def save_index(target_dir: Path, index: dict[str, dict]) -> None:
    p = target_dir / "index" / "files.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(index[k], ensure_ascii=False, sort_keys=True) + "\n" for k in sorted(index)),
                 encoding="utf-8")


# ----------------------------------------------------------------------------- tools

def run_tools(src: Path, raw: Path, cfg: dict) -> tuple[dict, list[dict]]:
    """Run deterministic scanners if installed. Returns (status, candidates)."""
    raw.mkdir(parents=True, exist_ok=True)
    status, cands = {}, []

    def avail(b):
        return shutil.which(b) is not None

    # semgrep
    if avail("semgrep"):
        out = raw / "semgrep.json"
        r = subprocess.run(["semgrep", "scan", "--config", cfg["semgrep_config"], "--json", "--quiet",
                            "--metrics=off", "--output", str(out), str(src)], capture_output=True, text=True)
        data = rjson(out, None)
        if data is None:
            status["semgrep"] = f"failed: {r.stderr.strip()[:200]}"
        else:
            status["semgrep"] = "ok"
            for f in data.get("results", []):
                rule = f.get("check_id", "")
                sev = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}.get(f.get("extra", {}).get("severity"), "medium")
                cands.append({
                    "source": "semgrep", "category": map_rule_category(rule),
                    "title": rule.split(".")[-1][:80], "path": os.path.relpath(f["path"], src),
                    "line": f.get("start", {}).get("line", 0), "severity": sev, "confidence": "medium",
                    "attacker": "unknown", "evidence": f.get("extra", {}).get("message", "")[:300], "fix": "",
                })
    else:
        status["semgrep"] = "missing"

    # gitleaks (values are redacted by the tool)
    if avail("gitleaks"):
        out = raw / "gitleaks.json"
        subprocess.run(["gitleaks", "detect", "--source", str(src), "--no-git", "--redact", "--exit-code", "0",
                        "--report-format", "json", "--report-path", str(out)], capture_output=True, text=True)
        data = rjson(out, None)
        status["gitleaks"] = "ok" if data is not None else "failed"
        for f in data or []:
            cands.append({
                "source": "gitleaks", "category": "hardcoded-secret", "title": f"Possible secret: {f.get('RuleID', '')}"[:80],
                "path": f.get("File", ""), "line": f.get("StartLine", 0), "severity": "high", "confidence": "medium",
                "attacker": "unknown", "evidence": f"gitleaks rule {f.get('RuleID')} (value redacted)", "fix": "Remove and rotate the secret.",
            })
    else:
        status["gitleaks"] = "missing"

    # osv-scanner: deterministic, not LLM-triaged (reachability is reported as unknown)
    if avail("osv-scanner"):
        out = raw / "osv.json"
        # --no-ignore: the clone usually sits in a directory the operator repository ignores (work/),
        # and without it osv-scanner skips every lockfile and finds no package sources.
        for args in (["scan", "source", "-r", "--no-ignore"], ["-r", "--no-ignore"]):
            r = subprocess.run(["osv-scanner", *args, "--format", "json", str(src)], capture_output=True, text=True)
            if r.stdout.strip().startswith("{"):
                out.write_text(r.stdout)
                break
        data = rjson(out, None)
        status["osv-scanner"] = "ok" if data is not None else "failed"
        for res in (data or {}).get("results", []):
            path = os.path.relpath(res.get("source", {}).get("path", ""), src)
            for pkg in res.get("packages", []):
                name = pkg.get("package", {}).get("name", "")
                ver = pkg.get("package", {}).get("version", "")
                for v in pkg.get("vulnerabilities", []):
                    sev = str(v.get("database_specific", {}).get("severity", "")).lower()
                    sev = {"moderate": "medium"}.get(sev, sev)
                    cands.append({
                        "source": "osv-scanner", "category": "dep-vuln", "title": f"{name}@{ver}: {v.get('id')}"[:80],
                        "path": path, "line": 0, "severity": sev if sev in SEVERITIES else "medium",
                        "confidence": "high", "attacker": "unknown", "status": "needs_info",
                        "evidence": (v.get("summary") or "")[:300] + " (reachability: unknown)",
                        "fix": "Upgrade to a fixed version.", "skip_triage": True,
                    })
    else:
        status["osv-scanner"] = "missing"
    return status, cands


def map_rule_category(rule: str) -> str:
    r = rule.lower()
    for key, cat in [("sql", "sqli"), ("xss", "xss"), ("ssti", "ssti"), ("template", "ssti"), ("command", "command-injection"),
                     ("exec", "command-injection"), ("ssrf", "ssrf"), ("path", "path-traversal"), ("travers", "path-traversal"),
                     ("deserial", "insecure-deserialization"), ("pickle", "insecure-deserialization"), ("xxe", "xxe"),
                     ("redirect", "open-redirect"), ("csrf", "csrf"), ("cors", "cors"), ("jwt", "authn"), ("secret", "hardcoded-secret"),
                     ("crypto", "weak-crypto"), ("random", "weak-random"), ("github-actions", "ci-injection"), ("docker", "container"),
                     ("terraform", "iac"), ("regex", "redos")]:
        if key in r:
            return cat
    return "other"


# ----------------------------------------------------------------------------- plan

def cmd_plan(a) -> None:
    root = Path(a.root).resolve() if a.root else None
    cfg = load_config(root, a.target)
    src = Path(a.src).resolve()
    tid = target_id(a.target)
    tdir = operator_dir(root) / "targets" / tid
    state = rjson(tdir / "state.json", {"run_count": 0, "suppressed": {}})
    head = git(src, "rev-parse", "HEAD").strip()

    mode = a.mode
    if mode == "auto":
        prev_minor = ".".join(str(state.get("va_version", "")).split(".")[:2])
        cur_minor = ".".join(va_version().split(".")[:2])
        mode = "full" if (not state.get("last_commit") or state["run_count"] % int(cfg["full_every"]) == 0
                          or prev_minor != cur_minor) else "diff"

    run_id = dt.date.today().strftime("%Y%m%d") + "-" + head[:7]
    rdir = tdir / "runs" / run_id
    n = 2
    while rdir.exists():
        rdir = tdir / "runs" / f"{run_id}-{n}"
        n += 1
    rdir.mkdir(parents=True)

    # inventory
    patterns = DEFAULT_EXCLUDE + list(cfg.get("exclude", []))
    files, skipped = {}, {"excluded": 0, "binary": 0, "too_large": 0, "unknown_type": 0}
    for line in git(src, "ls-files", "-s", "-z").split("\0"):
        if not line.strip():
            continue
        meta, path = line.split("\t", 1)
        fmode, blob = meta.split()[:2]
        if fmode == "160000":
            continue
        p = src / path
        if excluded(path, patterns):
            skipped["excluded"] += 1
            continue
        lang = lang_of(path)
        if lang is None:
            skipped["unknown_type"] += 1
            continue
        if not p.is_file() or p.stat().st_size > int(cfg["max_file_bytes"]):
            skipped["too_large"] += 1
            continue
        if not is_text(p):
            skipped["binary"] += 1
            continue
        files[path] = {"blob": blob, "lang": lang}

    index = load_index(tdir)
    changed = sorted(p for p, f in files.items() if index.get(p, {}).get("blob") != f["blob"])
    deleted = sorted(set(index) - set(files))

    tasks = [{"id": f"s-{hashlib.sha1(p.encode()).hexdigest()[:10]}", "path": p} for p in changed]

    tool_status, tool_cands = ({}, []) if a.no_tools else run_tools(src, Path(a.work).resolve() / "raw" / tid, cfg)

    run = Run(rdir)
    run.meta = {
        "target": tid, "repo": a.target, "commit": head, "va_version": va_version(),
        "model": a.model or cfg["model"], "escalate_model": cfg.get("escalate_model", ""),
        "mode": mode, "started_at": now(), "src": str(src), "root": str(root or VA_ROOT),
        "prev_run": state.get("last_run"), "prev_commit": state.get("last_commit"),
        "tools": tool_status, "inventory": {"files": len(files), "changed": len(changed), "deleted": len(deleted), "skipped": skipped},
    }
    run.queue = {"files": files, "changed": changed, "deleted": deleted, "tool_candidates": tool_cands,
                 "tasks": {"summarize": tasks}}
    run.save()
    print(rdir)


# ----------------------------------------------------------------------------- stage advance

def advance(run: Run) -> None:
    """Create the next stage's tasks once the current stage is done."""
    cfg = load_config(run.root, run.meta["repo"])
    tasks = run.queue["tasks"]
    if "review" not in tasks and not run.pending("summarize"):
        index = merged_index(run)
        prev_index = load_index(run.target_dir)
        mode = run.meta["mode"]
        changed = set(run.queue["changed"])

        def eff_risk(path):
            r = index[path]
            risk = int(r.get("risk", 0))
            if ENTRY_HINT.search(path):
                risk = max(risk, 2)
            if r.get("injection_suspect"):
                risk = 3
            if r.get("kind") in {"entry", "ci", "iac"}:
                risk = max(risk, 2)
            return risk

        cands = [p for p in index if eff_risk(p) >= 1]
        if mode == "diff":
            sel = [p for p in cands if p in changed]
            # rotating sweep of high-risk unchanged files, least recently reviewed first
            rest = sorted((p for p in cands if p not in changed and eff_risk(p) >= 2),
                          key=lambda p: (prev_index.get(p, {}).get("reviewed_at") or "", -eff_risk(p)))
            sel += rest[: int(cfg["rotate_per_run"])]
        else:
            sel = cands
        sel = sorted(set(sel), key=lambda p: (-eff_risk(p), p))[: int(cfg["review_budget"])]
        run.queue["not_reviewed"] = sorted(set(cands) - set(sel))

        checklists = load_checklists()
        rtasks = []
        for path in sel:
            rec = index[path]
            tags = set(rec.get("tags", []))
            if rec.get("kind") == "entry" or ENTRY_HINT.search(path):
                tags.add("http-input")
            chosen = [c["id"] for c in checklists
                      if ("always" in c.get("tags", []) or tags & set(c.get("tags", [])))
                      and ("any" in c.get("langs", ["any"]) or rec["lang"] in c.get("langs", []))]
            nlines = rec.get("lines") or 1
            step = int(cfg["chunk_lines"])
            for start in range(1, nlines + 1, step):
                end = min(nlines, start + step - 1 + int(cfg["chunk_overlap"]))
                rtasks.append({"id": f"r-{hashlib.sha1(f'{path}:{start}'.encode()).hexdigest()[:10]}",
                               "path": path, "start": start, "end": end, "checklists": chosen})
        tasks["review"] = rtasks
        run.save()

    if "review" in tasks and "triage" not in tasks and not run.pending("review"):
        state = rjson(run.target_dir / "state.json", {"suppressed": {}})
        suppressed = state.get("suppressed", {})
        cands, seen = [], set()
        allc = list(run.queue.get("tool_candidates", []))
        for t in tasks["review"]:
            for c in (run.result(t["id"]) or {}).get("candidates", []):
                allc.append({**c, "path": t["path"], "source": "llm"})
        for c in allc:
            line_text = line_at(run.src / c["path"], c.get("line", 0)) or c.get("title", "")
            fp = fingerprint(c["category"], c["path"], line_text)
            if fp in seen:
                continue
            seen.add(fp)
            c["fingerprint"] = fp
            if fp in suppressed:
                c["suppressed"] = suppressed[fp]
            cands.append(c)
        wjson(run.path / "candidates.json", cands)
        # Same fingerprint = same code line: reuse the previous verdict instead of paying for triage again.
        prev_run = run.meta.get("prev_run")
        prev = {f["fingerprint"]: f for f in rjson(run.target_dir / "runs" / prev_run / "findings.json", [])
                if not f.get("carried_over") and f.get("triage_model")} if prev_run else {}
        for c in cands:
            pf = prev.get(c["fingerprint"])
            if pf and not c.get("skip_triage") and not (run.path / "results" / f"t-{c['fingerprint']}.json").exists():
                c["reused_triage"] = True
                wjson(run.path / "results" / f"t-{c['fingerprint']}.json",
                      {k: pf.get(k, "") for k in ("status", "severity", "attacker", "fp_reason", "rationale")}
                      | {"_meta": {"model": pf.get("triage_model"), "reused_from": prev_run}})
        wjson(run.path / "candidates.json", cands)
        esc_model, esc_when = cfg.get("escalate_model"), set(cfg.get("escalate_when", []))
        tasks["triage"] = [{"id": f"t-{c['fingerprint']}", "fingerprint": c["fingerprint"],
                            "model": esc_model if esc_model and c.get("severity") in esc_when else None}
                           for c in cands if not c.get("skip_triage") and not c.get("suppressed") and not c.get("reused_triage")]
        run.save()


def line_at(p: Path, n: int) -> str:
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[n - 1] if 0 < n <= len(lines) else ""
    except OSError:
        return ""


def merged_index(run: Run) -> dict[str, dict]:
    """Previous index for unchanged files + this run's summaries (cached once summarize is complete)."""
    if getattr(run, "_mi", None) is not None:
        return run._mi
    prev = load_index(run.target_dir)
    files = run.queue["files"]
    out = {}
    by_path = {t["path"]: t["id"] for t in run.queue["tasks"].get("summarize", [])}
    for path, f in files.items():
        if path in by_path:
            res = run.result(by_path[path]) or {"purpose": "(summary failed)", "kind": "other", "tags": [], "risk": 2}
            lines = len((run.src / path).read_text(encoding="utf-8", errors="replace").splitlines())
            out[path] = {"path": path, "blob": f["blob"], "lang": f["lang"], "lines": lines,
                         **{k: res.get(k) for k in ("purpose", "kind", "tags", "entry_points", "sinks", "risk", "injection_suspect")},
                         "model": run.meta["model"], "va_version": run.meta["va_version"], "updated": run.path.name,
                         "reviewed_at": prev.get(path, {}).get("reviewed_at")}
        else:
            out[path] = prev[path]
    if not run.pending("summarize"):
        run._mi = out
    return out


# ----------------------------------------------------------------------------- prompts & validation

def build_prompt(run: Run, stage: str, task: dict) -> str:
    cfg = load_config(run.root, run.meta["repo"])
    tpl = (AGENTS / "prompts" / "tasks" / {"summarize": "summarize-file.md", "review": "review-file.md",
                                           "triage": "triage-candidate.md"}[stage]).read_text(encoding="utf-8")
    model = task.get("model") or run.meta["model"]
    notes = model_notes(model, stage, run.root)
    if stage == "summarize":
        path = task["path"]
        lines = (run.src / path).read_text(encoding="utf-8", errors="replace").splitlines()
        n = int(cfg["summary_lines"])
        note = f"(showing first {n} of {len(lines)} lines)" if len(lines) > n else ""
        return fill(tpl, TAGS=", ".join(TAGS), PATH=path, LANG=run.queue["files"][path]["lang"],
                    CHUNK_NOTE=note, CONTENT="\n".join(lines[:n])) + notes
    if stage == "review":
        index = merged_index(run)
        rec = index[task["path"]]
        lines = (run.src / task["path"]).read_text(encoding="utf-8", errors="replace").splitlines()
        chunk = lines[task["start"] - 1: task["end"]]
        cls = {c["id"]: c for c in load_checklists()}
        chosen = [cls[i] for i in task["checklists"] if i in cls]
        cats = sorted({cat for c in chosen for cat in c.get("categories", [])})
        d = os.path.dirname(task["path"])
        neigh = [f"{p}: {r.get('purpose', '')}" for p, r in index.items() if os.path.dirname(p) == d and p != task["path"]][:8]
        note = f"(lines {task['start']}-{task['end']} of {len(lines)})" if len(lines) > len(chunk) else ""
        return fill(tpl, PATH=task["path"], LANG=rec["lang"],
                    SUMMARY=json.dumps({k: rec.get(k) for k in ("purpose", "kind", "entry_points", "sinks")}, ensure_ascii=False),
                    NEIGHBORS="; ".join(neigh) or "(none)",
                    CHECKLIST="\n\n".join(f"### {c['id']}\n{c['body']}" for c in chosen),
                    CATEGORIES=", ".join(cats), CHUNK_NOTE=note, CONTENT=numbered(chunk, task["start"]),
                    MODEL_NOTES=notes)
    # triage
    cands = {c["fingerprint"]: c for c in rjson(run.path / "candidates.json", [])}
    c = cands[task["fingerprint"]]
    lines = (run.src / c["path"]).read_text(encoding="utf-8", errors="replace").splitlines() if (run.src / c["path"]).is_file() else []
    ln = int(c.get("line") or 1)
    s, e = max(1, ln - 60), min(len(lines), ln + 40)
    rec = merged_index(run).get(c["path"], {})
    shown = {k: c.get(k) for k in ("category", "title", "line", "severity", "confidence", "attacker", "evidence", "source")}
    return fill(tpl, CANDIDATE=json.dumps(shown, ensure_ascii=False, indent=1), PATH=c["path"],
                SUMMARY=rec.get("purpose", "(none)"), CONTENT=numbered(lines[s - 1:e], s), MODEL_NOTES=notes)


def validate(stage: str, obj: dict, task: dict, run: Run) -> dict:
    if stage == "summarize":
        if not isinstance(obj.get("purpose"), str):
            raise ValueError("missing 'purpose' string")
        risk = obj.get("risk", 1)
        return {
            "purpose": obj["purpose"][:200],
            "kind": obj.get("kind") if obj.get("kind") in KINDS else "other",
            "tags": [t for t in obj.get("tags", []) if t in TAGS],
            "entry_points": [str(x)[:120] for x in obj.get("entry_points", []) or []][:10],
            "sinks": [str(x)[:120] for x in obj.get("sinks", []) or []][:10],
            "risk": max(0, min(3, int(risk))) if str(risk).lstrip("-").isdigit() else 1,
            "injection_suspect": bool(obj.get("injection_suspect", False)),
        }
    if stage == "review":
        if not isinstance(obj.get("candidates"), list):
            raise ValueError("missing 'candidates' list")
        cls = {c["id"]: c for c in load_checklists()}
        allowed = {cat for i in task["checklists"] if i in cls for cat in cls[i].get("categories", [])}
        out, dropped = [], []
        for c in obj["candidates"]:
            if not isinstance(c, dict):
                continue
            line = c.get("line")
            if c.get("category") not in allowed or not isinstance(line, int) or not task["start"] <= line <= task["end"]:
                dropped.append({"category": c.get("category"), "line": line, "title": c.get("title")})
                continue
            out.append({
                "category": c["category"], "title": str(c.get("title", ""))[:80], "line": line,
                "severity": c.get("severity") if c.get("severity") in SEVERITIES else "medium",
                "confidence": c.get("confidence") if c.get("confidence") in CONFIDENCE else "low",
                "attacker": c.get("attacker") if c.get("attacker") in ATTACKERS else "unknown",
                "evidence": str(c.get("evidence", ""))[:500], "fix": str(c.get("fix", ""))[:300],
            })
        return {"candidates": out, "dropped": dropped}
    if obj.get("status") not in STATUSES:
        raise ValueError(f"'status' must be one of {sorted(STATUSES)}")
    return {
        "status": obj["status"],
        "severity": obj.get("severity") if obj.get("severity") in SEVERITIES else "low",
        "attacker": obj.get("attacker") if obj.get("attacker") in ATTACKERS else "unknown",
        "fp_reason": str(obj.get("fp_reason") or ("unspecified" if obj["status"] == "false_positive" else ""))[:300],
        "rationale": str(obj.get("rationale", ""))[:600],
    }


# ----------------------------------------------------------------------------- runners

def call_model(prompt: str, model: str, cfg: dict, runner: str) -> tuple[str, dict]:
    if runner == "anthropic":
        body = json.dumps({"model": model, "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
        text = "".join(b.get("text", "") for b in data.get("content", []))
        return text, {"usage": data.get("usage", {})}
    if runner == "claude":
        cmd = cfg.get("runner_cmd") or "claude -p --model {model} --output-format json --max-turns 1"
    elif runner.startswith("cmd:"):
        cmd = runner[4:]
    else:
        raise ValueError(f"unknown runner {runner}")
    # Run in an empty directory so no repo CLAUDE.md/AGENTS.md (or target content) is auto-loaded.
    with tempfile.TemporaryDirectory() as empty:
        r = subprocess.run(shlex.split(cmd.replace("{model}", model)), input=prompt, capture_output=True,
                           text=True, cwd=empty, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"runner exit {r.returncode}: {r.stderr.strip()[:300]}")
    out = r.stdout
    try:
        env = json.loads(out)
        if isinstance(env, dict) and "result" in env:
            return str(env["result"]), {"cost_usd": env.get("total_cost_usd"), "usage": env.get("usage")}
    except json.JSONDecodeError:
        pass
    return out, {}


def do_task(run: Run, stage: str, task: dict, runner: str) -> str:
    cfg = load_config(run.root, run.meta["repo"])
    model = task.get("model") or run.meta["model"]
    prompt = build_prompt(run, stage, task)
    err = ""
    for attempt in (1, 2):
        p = prompt if not err else prompt + f"\n\nYour previous answer was invalid: {err}\nReturn ONLY the JSON object."
        try:
            text, usage = call_model(p, model, cfg, runner)
            res = validate(stage, extract_json(text), task, run)
            res["_meta"] = {"model": model, "attempts": attempt, **usage}
            wjson(run.path / "results" / f"{task['id']}.json", res)
            return "ok"
        except Exception as e:  # noqa: BLE001 - record and retry once
            err = str(e)[:300]
    wjson(run.path / "failures" / f"{task['id']}.json", {"error": err, "stage": stage, "task": task, "model": model})
    return "failed"


def cmd_exec(a) -> None:
    run = Run(Path(a.run).resolve())
    cfg = load_config(run.root, run.meta["repo"])
    runner = a.runner or cfg["runner"]
    jobs = a.jobs or int(cfg["jobs"])
    while True:
        advance(run)
        stage = run.current_stage()
        if stage is None:
            break
        todo = run.pending(stage)
        print(f"[{stage}] {len(todo)} tasks", file=sys.stderr)
        with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
            res = list(ex.map(lambda t: do_task(run, stage, t, runner), todo))
        print(f"[{stage}] ok={res.count('ok')} failed={res.count('failed')}", file=sys.stderr)
    print("done", file=sys.stderr)


def cmd_next(a) -> None:
    run = Run(Path(a.run).resolve())
    advance(run)
    stage = run.current_stage()
    if stage is None:
        print(json.dumps({"done": True}))
        return
    task = run.pending(stage)[0]
    print(json.dumps({"done": False, "stage": stage, "task_id": task["id"], "remaining": len(run.pending(stage)),
                      "prompt": build_prompt(run, stage, task)}, ensure_ascii=False))


def cmd_submit(a) -> None:
    run = Run(Path(a.run).resolve())
    stage = run.current_stage()
    task = next((t for t in run.queue["tasks"].get(stage, []) if t["id"] == a.task), None)
    if task is None:
        sys.exit(f"task {a.task} is not pending in stage {stage}")
    text = sys.stdin.read() if a.output == "-" else Path(a.output).read_text()
    res = validate(stage, extract_json(text), task, run)
    res["_meta"] = {"model": a.model or run.meta["model"], "attempts": 1, "runner": "manual"}
    wjson(run.path / "results" / f"{task['id']}.json", res)
    print("ok")


# ----------------------------------------------------------------------------- report

SEV_ORDER = {s: i for i, s in enumerate(SEVERITIES)}


def cmd_report(a) -> None:
    run = Run(Path(a.run).resolve())
    advance(run)
    if run.current_stage() is not None:
        sys.exit(f"stage '{run.current_stage()}' still has pending tasks; run exec first")
    tdir = run.target_dir
    state = rjson(tdir / "state.json", {"run_count": 0, "suppressed": {}})
    prev_run = run.meta.get("prev_run")
    prev = {f["fingerprint"]: f for f in rjson(tdir / "runs" / prev_run / "findings.json", [])} if prev_run else {}

    reviewed = {t["path"] for t in run.queue["tasks"].get("review", []) if run.result(t["id"])}
    findings = []
    for c in rjson(run.path / "candidates.json", []):
        if c.get("suppressed"):
            continue
        tri = run.result(f"t-{c['fingerprint']}") or {}
        f = {
            "fingerprint": c["fingerprint"], "category": c["category"], "title": c.get("title", ""),
            "severity": tri.get("severity", c.get("severity")), "status": tri.get("status", c.get("status", "needs_info")),
            "confidence": c.get("confidence"), "location": {"path": c["path"], "line": c.get("line", 0)},
            "attacker": tri.get("attacker", c.get("attacker", "unknown")), "summary": c.get("title", ""),
            "evidence": c.get("evidence", ""), "rationale": tri.get("rationale", ""), "fix": c.get("fix", ""),
            "source": c.get("source"), "fp_reason": tri.get("fp_reason", ""),
            "first_seen": prev.get(c["fingerprint"], {}).get("first_seen", run.path.name),
            "triage_model": (tri.get("_meta") or {}).get("model"),
        }
        findings.append(f)
    # carry over open findings in files that were not re-reviewed this run (diff mode)
    cur = {f["fingerprint"] for f in findings}
    deleted = set(run.queue.get("deleted", []))
    resolved = []
    for fp, f in prev.items():
        if fp in cur or f["status"] == "false_positive" or fp in state.get("suppressed", {}):
            continue
        path = f["location"]["path"]
        if path in deleted or path in reviewed or f.get("source") in {"semgrep", "gitleaks", "osv-scanner"}:
            resolved.append(f)
        else:
            findings.append({**f, "carried_over": True})
    findings.sort(key=lambda f: (f["status"] == "false_positive", SEV_ORDER.get(f["severity"], 9), f["location"]["path"]))
    wjson(run.path / "findings.json", findings)

    # index + state
    index = merged_index(run)
    for p in reviewed:
        if p in index:
            index[p]["reviewed_at"] = run.path.name
    save_index(tdir, index)
    state.update({"last_commit": run.meta["commit"], "last_run": run.path.name, "run_count": state.get("run_count", 0) + 1,
                  "va_version": run.meta["va_version"]})
    state.setdefault("suppressed", {})
    wjson(tdir / "state.json", state)

    run.meta["finished_at"] = now()
    run.meta["usage"] = usage_totals(run)
    run.save()
    (run.path / "changes.md").write_text(render_changes(run, index), encoding="utf-8")
    (run.path / "report.md").write_text(render_report(run, findings, prev, resolved), encoding="utf-8")
    print(run.path / "report.md")


def usage_totals(run: Run) -> dict:
    tot = {"tasks": 0, "failed": 0, "cost_usd": 0.0}
    for p in (run.path / "results").glob("*.json"):
        meta = rjson(p, {}).get("_meta") or {}
        if meta.get("reused_from"):
            tot["reused"] = tot.get("reused", 0) + 1
            continue
        tot["tasks"] += 1
        tot["cost_usd"] += float((rjson(p, {}).get("_meta") or {}).get("cost_usd") or 0)
    tot["failed"] = len(list((run.path / "failures").glob("*.json")))
    tot["cost_usd"] = round(tot["cost_usd"], 4)
    return tot


def render_changes(run: Run, index: dict) -> str:
    out = [f"# Changes: {run.meta['target']} {str(run.meta.get('prev_commit') or '(first run)')[:7]} → {run.meta['commit'][:7]}", ""]
    if run.meta.get("prev_commit"):
        stat = git(run.src, "diff", "--shortstat", run.meta["prev_commit"], run.meta["commit"], check=False).strip()
        out += [stat or "(diff unavailable: history too shallow?)", ""]
    changed = run.queue.get("changed", [])
    out += [f"## Changed or new files ({len(changed)})", ""]
    for p in changed[:300]:
        r = index.get(p, {})
        out.append(f"- `{p}` [{r.get('kind', '?')}, risk {r.get('risk', '?')}] {r.get('purpose', '')}")
    if len(changed) > 300:
        out.append(f"- … and {len(changed) - 300} more")
    if run.queue.get("deleted"):
        out += ["", f"## Deleted files ({len(run.queue['deleted'])})", ""] + [f"- `{p}`" for p in run.queue["deleted"][:100]]
    return "\n".join(out) + "\n"


def render_report(run: Run, findings: list, prev: dict, resolved: list) -> str:
    m = run.meta
    live = [f for f in findings if f["status"] != "false_positive"]
    new = [f for f in live if f["fingerprint"] not in prev]
    cont = [f for f in live if f["fingerprint"] in prev]
    fps = [f for f in findings if f["status"] == "false_positive"]

    def counts(fs):
        return ", ".join(f"{s} {sum(1 for f in fs if f['severity'] == s)}" for s in SEVERITIES if any(f['severity'] == s for f in fs)) or "0"

    def row(f):
        loc = f"{f['location']['path']}:{f['location']['line']}"
        co = " (not re-checked)" if f.get("carried_over") else ""
        return f"| {f['severity']} | {f['status']} | {f['category']} | `{loc}` | {f['title']}{co} | `{f['fingerprint']}` |"

    hdr = "| severity | status | category | location | title | id |\n|---|---|---|---|---|---|"
    out = [f"# Security report: {m['repo']}", "",
           f"- commit `{m['commit'][:12]}` / mode **{m['mode']}** / VA {m['va_version']} / model `{m['model']}`"
           + (f" (escalation `{m['escalate_model']}`)" if m.get("escalate_model") else ""),
           f"- LLM tasks {m['usage']['tasks']} run, {m['usage'].get('reused', 0)} reused, {m['usage']['failed']} failed / cost ≈ ${m['usage']['cost_usd']}", "",
           "## Summary", "", f"- New: {counts(new)}", f"- Continuing: {counts(cont)}", f"- Resolved: {len(resolved)}",
           f"- Rejected as false positive: {len(fps)}", ""]
    for title, fs in (("New findings", new), ("Continuing findings", cont)):
        out += [f"## {title}", ""]
        out += ([hdr] + [row(f) for f in fs]) if fs else ["None."]
        out.append("")
        for f in fs:
            if f["severity"] in ("critical", "high", "medium") and not f.get("carried_over"):
                out += [f"### {f['title']} (`{f['fingerprint']}`)", "",
                        f"- **Where**: `{f['location']['path']}:{f['location']['line']}`  **Attacker**: {f['attacker']}",
                        f"- **Evidence**: {f['evidence']}", f"- **Triage**: {f['rationale']}", f"- **Fix**: {f['fix']}", ""]
    out += ["## Resolved since last run", ""]
    out += [f"- `{f['fingerprint']}` {f['title']} (`{f['location']['path']}`)" for f in resolved] or ["None."]
    sus = sorted(p for p, r in load_index(run.target_dir).items() if r.get("injection_suspect"))
    if sus:
        out += ["", "## Files that address AI reviewers (possible prompt injection)", "",
                "These files contain text aimed at automated reviewers. They were reviewed with maximum priority; "
                "check them manually too.", ""] + [f"- `{p}`" for p in sus]
    out += ["", "## Not covered", ""]
    inv = m["inventory"]
    low = sum(1 for r in load_index(run.target_dir).values() if int(r.get("risk") or 0) == 0
              and not ENTRY_HINT.search(r["path"]) and r.get("kind") not in {"entry", "ci", "iac"})
    out.append(f"- Indexed as no security relevance (risk 0, not reviewed by design): {low} files")
    out.append(f"- Skipped files: {json.dumps(inv['skipped'])}")
    nr = run.queue.get("not_reviewed", [])
    out.append(f"- Indexed but not reviewed this run: {len(nr)} files" + (" (diff mode: unchanged files outside the rotation)" if m["mode"] == "diff" else " (review budget reached)" if nr else ""))
    for name, st in m.get("tools", {}).items():
        if st != "ok":
            out.append(f"- Tool `{name}`: {st}")
    fails = list((run.path / "failures").glob("*.json"))
    if fails:
        out.append(f"- Failed LLM tasks: {len(fails)}")
        for p in fails[:20]:
            d = rjson(p, {})
            out.append(f"  - {d.get('stage')} `{d.get('task', {}).get('path') or d.get('task', {}).get('fingerprint')}`: {d.get('error', '')[:120]}")
    out += ["", "## How to triage this report", "",
            "Add a fingerprint to `suppressed` in `state.json` with `false_positive`, `accepted_risk`, `wont_fix` or `fixed` to stop re-reporting it. "
            "For false positives, add a one-line reason to `learnings.md` so the retrospective can learn from it.", ""]
    return "\n".join(out)


# ----------------------------------------------------------------------------- stats / validate / targets

def cmd_stats(a) -> None:
    root = Path(a.root).resolve() if a.root else None
    tdirs = [operator_dir(root) / "targets" / target_id(a.target)] if a.target else sorted((operator_dir(root) / "targets").glob("*"))
    per_model: dict = {}
    per_cat: dict = {}
    for tdir in tdirs:
        for rdir in sorted((tdir / "runs").glob("*")):
            for f in rjson(rdir / "findings.json", []):
                if f.get("carried_over"):
                    continue
                key = f.get("triage_model") or "none"
                pm = per_model.setdefault(key, {"total": 0, "false_positive": 0, "confirmed": 0})
                pm["total"] += 1
                pm[f["status"]] = pm.get(f["status"], 0) + 1
                pc = per_cat.setdefault(f"{f.get('source')}:{f['category']}", {"total": 0, "false_positive": 0, "fp_reasons": []})
                pc["total"] += 1
                if f["status"] == "false_positive":
                    pc["false_positive"] += 1
                    pc["fp_reasons"].append(f.get("fp_reason", ""))
            for p in (rdir / "results").glob("r-*.json"):
                d = rjson(p, {})
                key = (d.get("_meta") or {}).get("model", "none")
                pm = per_model.setdefault(key, {"total": 0, "false_positive": 0, "confirmed": 0})
                pm["review_dropped"] = pm.get("review_dropped", 0) + len(d.get("dropped", []))
    for pc in per_cat.values():
        pc["fp_reasons"] = pc["fp_reasons"][-10:]
    print(json.dumps({"targets": [t.name for t in tdirs], "by_triage_model": per_model, "by_source_category": per_cat},
                     ensure_ascii=False, indent=2))


def cmd_validate(a) -> None:
    errs = []
    cats_all = set()
    ids = set()
    for c in load_checklists():
        for k in ("id", "tags", "langs", "categories"):
            if k not in c:
                errs.append(f"{c['file']}: missing '{k}'")
        if c.get("id") in ids:
            errs.append(f"{c['file']}: duplicate id {c.get('id')}")
        ids.add(c.get("id"))
        bad = [t for t in c.get("tags", []) if t not in TAGS and t != "always"]
        if bad:
            errs.append(f"{c['file']}: unknown tags {bad} (add to TAGS in scripts/va.py and checklists/README.md)")
        cats_all |= set(c.get("categories", []))
        if len([l for l in c.get("body", "").splitlines() if l.lstrip().startswith("- ")]) > 10:
            errs.append(f"{c['file']}: more than 10 items; split it")
    need = {"summarize-file.md": ["TAGS", "PATH", "CONTENT"],
            "review-file.md": ["PATH", "CHECKLIST", "CATEGORIES", "CONTENT", "MODEL_NOTES"],
            "triage-candidate.md": ["CANDIDATE", "CONTENT", "MODEL_NOTES"]}
    for name, keys in need.items():
        txt = (AGENTS / "prompts" / "tasks" / name).read_text(encoding="utf-8")
        for k in keys:
            if "{{" + k + "}}" not in txt:
                errs.append(f"prompts/tasks/{name}: missing placeholder {{{{{k}}}}}")
    if not re.fullmatch(r"\d+\.\d+\.\d+", va_version()):
        errs.append(".agents/VERSION is not SemVer")
    for e in errs:
        print("ERROR", e)
    print(f"{len(ids)} checklists, {len(cats_all)} categories, {len(errs)} errors")
    sys.exit(1 if errs else 0)


def cmd_targets(a) -> None:
    cfg = load_config(Path(a.root).resolve() if a.root else None)
    print(json.dumps([{"repo": t["repo"], "id": target_id(t["repo"]), "ref": t.get("ref", "")}
                      for t in cfg["targets"] if t.get("enabled", True)]))


def cmd_detect(a) -> None:
    """Decide per target whether a scheduled run should audit it: remote HEAD vs state.json last_commit."""
    root = Path(a.root).resolve() if a.root else None
    cfg = load_config(root)
    minor = ".".join(va_version().split(".")[:2])
    out = []
    for t in cfg["targets"]:
        if not t.get("enabled", True):
            continue
        repo, tid, ref = t["repo"], target_id(t["repo"]), t.get("ref", "")
        tdir = operator_dir(root) / "targets" / tid
        state = rjson(tdir / "state.json", {})
        last = state.get("last_commit", "")
        meta = rjson(tdir / "runs" / state.get("last_run", "") / "meta.json", {}) if state.get("last_run") else {}
        url = t.get("url") or f"https://github.com/{repo}"
        r = subprocess.run(["git", "ls-remote", url, ref or "HEAD"], capture_output=True, text=True)
        head = r.stdout.split()[0] if r.returncode == 0 and r.stdout.strip() else ""
        if r.returncode != 0:
            action, reason = "skip", "unreachable"
        elif not head:
            action, reason = "skip", "empty"
        elif not last:
            action, reason = "audit", "first"
        elif head != last:
            action, reason = "audit", "changed"
        elif ".".join(str(state.get("va_version", "")).split(".")[:2]) != minor:
            action, reason = "audit", "va-upgraded"   # plan picks full mode for a MINOR change
        elif meta.get("usage", {}).get("failed") and meta.get("prev_commit") != head:
            action, reason = "audit", "retry"         # once per commit: the last run had failed tasks
        else:
            action, reason = "skip", "same"
        out.append({"repo": repo, "id": tid, "url": url, "ref": ref, "head": head, "last_commit": last,
                    "action": action, "reason": reason})
    if a.changed:
        print("\n".join(x["repo"] for x in out if x["action"] == "audit"))
    else:
        print(json.dumps(out, indent=1))


def cmd_config(a) -> None:
    cfg = load_config(Path(a.root).resolve() if a.root else None, a.target)
    v = cfg.get(a.key, "")
    print(json.dumps(v) if isinstance(v, (list, dict)) else v)


def main() -> None:
    ap = argparse.ArgumentParser(prog="va.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help="repository root containing operator/ (default: this repo)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="inventory the target and create a run")
    p.add_argument("--target", required=True, help="owner/repo")
    p.add_argument("--src", required=True, help="checked-out target")
    p.add_argument("--mode", default="auto", choices=["auto", "full", "diff"])
    p.add_argument("--model")
    p.add_argument("--work", default="work")
    p.add_argument("--no-tools", action="store_true")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("exec", help="run all LLM tasks with a runner")
    p.add_argument("--run", required=True)
    p.add_argument("--runner", help="claude | anthropic | cmd:'<command reading prompt on stdin>'")
    p.add_argument("--jobs", type=int)
    p.set_defaults(fn=cmd_exec)

    p = sub.add_parser("next", help="print the next task prompt (interactive use)")
    p.add_argument("--run", required=True)
    p.set_defaults(fn=cmd_next)

    p = sub.add_parser("submit", help="submit a task result (interactive use)")
    p.add_argument("--run", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--output", default="-")
    p.add_argument("--model")
    p.set_defaults(fn=cmd_submit)

    p = sub.add_parser("report", help="build findings, report.md, changes.md, update index and state")
    p.add_argument("--run", required=True)
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("stats", help="aggregate outcomes per model and per check (for the retrospective)")
    p.add_argument("--target")
    p.set_defaults(fn=cmd_stats)

    sub.add_parser("validate", help="check checklists and prompt templates").set_defaults(fn=cmd_validate)
    sub.add_parser("targets", help="list enabled targets as JSON (CI matrix)").set_defaults(fn=cmd_targets)

    p = sub.add_parser("detect", help="per target, audit or skip: remote HEAD vs last audited commit")
    p.add_argument("--changed", action="store_true", help="print only the repos to audit, one per line")
    p.set_defaults(fn=cmd_detect)

    p = sub.add_parser("config", help="print one config value (for CI)")
    p.add_argument("key")
    p.add_argument("--target")
    p.set_defaults(fn=cmd_config)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
