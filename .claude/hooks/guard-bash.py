#!/usr/bin/env python3
"""Bash 명령 안전 가드 (PreToolUse 훅).

stdin의 hook payload에서 Bash 명령을 꺼내 되돌릴 수 없는 명령을 차단한다.
헤드리스 실행(--dangerously-skip-permissions)에서는 이것이 유일한 방어선이다.

차단: stdout에 deny JSON, stderr에 사유, exit 2.
통과: exit 0, 출력 없음 (정상 권한 흐름).

설계 원칙
- 따옴표를 존중한다. `grep 'rm -rf /'` 는 차단하지 않는다.
- 플래그 표기 우회를 막는다. `-rf`, `-fr`, `-r -f`, `--recursive --force` 전부 같게 본다.
- 경로는 해석해서 허용 루트(프로젝트/스크래치패드/임시 디렉토리) 안인지 본다.
- 판정할 수 없으면 통과시킨다. 가드가 죽어서 모든 작업을 막는 쪽이 더 나쁘다.

한계
  이 가드는 사고와 명백한 파괴 명령을 막는다. 작정한 우회는 막지 못한다.
  난독화 경로(base64 디코드, 변수 조립, printf 이스케이프 등)는 원칙적으로
  정적 판정이 불가능하다. 마지막 방어선으로 취급하지 말 것.
"""

import json
import os
import re
import shlex
import sys

# 파괴적 명령이 허용되는 루트. 이 밖은 차단한다.
STATIC_ROOTS = ("/tmp", "/private/tmp", "/var/folders", "/var/tmp")

# 제어 연산자. 세그먼트 경계로 쓴다. 리다이렉션(< >)은 세그먼트에 남긴다.
CONTROL_OPS = {";", "&", "&&", "||", "|", "|&", ";;", "(", ")", "{", "}", "\n"}

SHELLS = {"sh", "bash", "zsh", "ksh", "dash", "fish",
          "python", "python3", "node", "perl", "ruby"}

FETCHERS = {"curl", "wget"}

RAW_DENY = (
    (re.compile(r":\s*\(\s*\)\s*\{[^}]*\|[^}]*&[^}]*\}\s*;\s*:"), "fork bomb"),
    (re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", re.I), "SQL DROP"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.I), "SQL TRUNCATE"),
    (re.compile(r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", re.I | re.S), "WHERE 없는 SQL DELETE"),
)

SUBST = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")

# 구분자를 따옴표로 감싼 heredoc의 본문은 셸이 확장하지 않는 순수 데이터다.
# 스캔하면 마크다운 코드 스팬의 백틱을 명령 치환으로 오인한다. 미리 잘라낸다.
# 구분자에 따옴표가 없는 heredoc은 실제로 확장되므로 남겨 둔다.
LITERAL_HEREDOC = re.compile(
    r"<<-?[ \t]*(['\"])([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n.*?^[ \t]*\2[ \t]*$",
    re.S | re.M,
)
# `$(echo rm -rf /)` 는 치환 내용이 아니라 치환 결과가 실행된다.
ECHO_WRAPPER = re.compile(r"^\s*(?:echo|printf)\s+(?:-\S+\s+)*")


def resolve(target, cwd):
    """경로 토큰을 절대 경로로 정규화한다. 존재 여부는 보지 않는다."""
    t = target
    for var in ("${HOME}", "$HOME"):
        if t.startswith(var):
            t = os.path.expanduser("~") + t[len(var):]
    t = os.path.expanduser(t)
    if not os.path.isabs(t):
        t = os.path.join(cwd, t)
    return os.path.normpath(t)


def inside(path, roots):
    """path가 어느 루트 안에 엄격히 포함되는가. 루트 자신은 False."""
    return any(path.startswith(r.rstrip("/") + os.sep) for r in roots)


def unsafe_target(target, ctx):
    """이 경로에 파괴적 연산을 해도 되는지. 안 되면 사유 문자열."""
    if target in (".", "..", "./", "../", "*", "./*", ".*", "/", "~", "~/"):
        return f"작업 트리 전체를 가리키는 대상 '{target}'"
    path = resolve(target, ctx["cwd"])
    if not inside(path, ctx["roots"]):
        return f"허용 루트 밖의 경로 '{target}' (해석: {path})"
    return None


def split_flags(tokens):
    """토큰을 (플래그 문자 집합, 롱플래그 집합, 나머지 인자)로 나눈다."""
    short, long_, rest, only_args = set(), set(), [], False
    for t in tokens:
        if only_args or not t.startswith("-") or t == "-":
            rest.append(t)
        elif t == "--":
            only_args = True
        elif t.startswith("--"):
            long_.add(t[2:].split("=")[0])
        else:
            short.update(t[1:])
    return short, long_, rest


def base(cmd):
    return os.path.basename(cmd)


# --- 개별 규칙: 세그먼트(토큰 리스트)를 받아 차단 사유 또는 None ---

def rule_sudo(tok, ctx):
    if base(tok[0]) in ("sudo", "doas", "su"):
        return f"권한 상승 명령 '{tok[0]}'. 에이전트는 sudo를 쓰지 않는다."
    return None


def rule_rm(tok, ctx):
    cmd = base(tok[0])
    args = tok[1:]
    if cmd == "xargs":
        if not args or base(args[0]) != "rm":
            return None
        short, long_, _ = split_flags(args[1:])
        if short & set("rR") or "recursive" in long_:
            return "xargs로 넘어오는 rm 대상은 검증할 수 없다"
        return None
    if cmd != "rm":
        return None
    short, long_, rest = split_flags(args)
    if not (short & set("rR") or "recursive" in long_):
        return None
    if not rest:
        return "대상 없는 재귀 rm"
    for t in rest:
        why = unsafe_target(t, ctx)
        if why:
            return f"재귀 rm — {why}"
    return None


def rule_find_delete(tok, ctx):
    if base(tok[0]) != "find":
        return None
    joined = " ".join(tok)
    if "-delete" not in tok and not re.search(r"-exec(dir)?\s+rm\b", joined):
        return None
    starts = []
    for t in tok[1:]:
        if t.startswith("-"):
            break
        starts.append(t)
    for t in starts or ["."]:
        why = unsafe_target(t, ctx)
        if why:
            return f"find 삭제 — {why}"
    return None


def rule_git(tok, ctx):
    if base(tok[0]) != "git" or len(tok) < 2:
        return None
    sub = next((t for t in tok[1:] if not t.startswith("-")), None)
    short, long_, _ = split_flags(tok[2:])
    if sub == "push":
        if "force" in long_ or "f" in short:
            if "force-with-lease" in long_:
                return None
            return "git push --force. --force-with-lease를 쓰거나 사람이 직접 하라."
    if sub == "reset" and "hard" in long_:
        return "git reset --hard는 커밋되지 않은 작업을 말없이 버린다. git stash를 쓰라."
    if sub == "clean" and ("force" in long_ or "f" in short):
        return "git clean --force는 추적되지 않는 파일을 지운다. git stash -u를 쓰라."
    return None


def rule_chmod_chown(tok, ctx):
    cmd = base(tok[0])
    if cmd not in ("chmod", "chown", "chgrp"):
        return None
    short, long_, rest = split_flags(tok[1:])
    if not (short & set("R") or "recursive" in long_):
        return None
    for t in rest[1:] if len(rest) > 1 else []:
        why = unsafe_target(t, ctx)
        if why:
            return f"재귀 {cmd} — {why}"
    return None


def rule_device_write(tok, ctx):
    cmd = base(tok[0])
    if cmd.startswith("mkfs"):
        return f"파일시스템 생성 명령 '{cmd}'"
    if cmd == "dd":
        for t in tok[1:]:
            if t.startswith("of=") and re.match(r"/dev/(sd|disk|rdisk|nvme|hd|mem)", t[3:]):
                return f"dd로 raw 디바이스에 쓰기 ({t})"
    for i, t in enumerate(tok):
        if t in (">", ">>") and i + 1 < len(tok):
            if re.match(r"/dev/(sd|disk|rdisk|nvme|hd|mem)", tok[i + 1]):
                return f"raw 디바이스로 리다이렉션 ({tok[i + 1]})"
    return None


RULES = (rule_sudo, rule_rm, rule_find_delete, rule_git,
         rule_chmod_chown, rule_device_write)


def tokenize(command):
    """제어 연산자로 쪼갠 세그먼트 리스트. 파싱 실패 시 None."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    segments, cur = [], []
    for t in tokens:
        if t in CONTROL_OPS:
            if cur:
                segments.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        segments.append(cur)
    return segments


def scan(command, ctx, depth=0):
    """차단 사유 또는 None. 명령 치환 내부까지 재귀한다."""
    command = LITERAL_HEREDOC.sub(" ", command)
    for pattern, label in RAW_DENY:
        if pattern.search(command):
            return label

    if depth < 3:
        for m in SUBST.finditer(command):
            inner = m.group(1) or m.group(2) or ""
            stripped = ECHO_WRAPPER.sub("", inner, count=1)
            for candidate in dict.fromkeys((inner, stripped)):
                if not candidate.strip():
                    continue
                why = scan(candidate, ctx, depth + 1)
                if why:
                    return f"명령 치환 내부 — {why}"

    segments = tokenize(command)
    if segments is None:
        return None

    cmds = [base(s[0]) for s in segments if s]
    if any(c in FETCHERS for c in cmds) and any(c in SHELLS for c in cmds):
        return "네트워크에서 받은 내용을 셸로 파이프 (curl | sh)"

    for seg in segments:
        if not seg:
            continue
        payload = None
        cmd = base(seg[0])
        if cmd == "eval":
            payload = " ".join(seg[1:])
        elif cmd in SHELLS and "-c" in seg:
            i = seg.index("-c")
            if i + 1 < len(seg):
                payload = seg[i + 1]
        if payload and payload.strip() and depth < 3:
            why = scan(payload, ctx, depth + 1)
            if why:
                return f"eval/-c 페이로드 — {why}"
        for rule in RULES:
            why = rule(seg, ctx)
            if why:
                return why
    return None


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except (ValueError, OSError):
        sys.exit(0)

    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command.strip():
        sys.exit(0)

    cwd = payload.get("cwd") or os.getcwd()
    roots = [cwd, *STATIC_ROOTS]
    scratchpad = payload.get("scratchpad_dir")
    if scratchpad:
        roots.append(scratchpad)
    ctx = {"cwd": cwd, "roots": [os.path.normpath(r) for r in roots]}

    why = scan(command, ctx)
    if not why:
        sys.exit(0)

    reason = f"안전 가드 차단: {why}"
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    print(reason, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
