#!/usr/bin/env node
// Claude Code는 세션당 statusLine을 하나만 허용해서, 프로젝트의 graft statusline이 사용자 전역
// statusLine(~/.claude/settings.json)을 가린다. 둘을 같은 stdin으로 함께 실행해 위아래로 이어 붙인다.
// 파일명에 'graft-statusline.cjs'가 들어가면 `graft init`이 자기 것으로 보고 되돌리므로 피한다.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

function userStatuslineCommand() {
  try {
    const configDir = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');
    const settings = JSON.parse(fs.readFileSync(path.join(configDir, 'settings.json'), 'utf8'));
    const command = settings.statusLine && settings.statusLine.command;
    // 전역 설정이 이 래퍼를 가리키면 무한 재귀가 되므로 건너뛴다.
    if (typeof command !== 'string' || command.includes(path.basename(__filename))) return null;
    return command;
  } catch { return null; }
}

function run(command, args, input, shell) {
  return new Promise((resolve) => {
    const child = spawn(command, args, { shell, stdio: ['pipe', 'pipe', 'ignore'] });
    let out = '';
    child.stdout.on('data', (d) => { out += d; });
    child.on('error', () => resolve(''));
    child.on('close', () => resolve(out.replace(/\n+$/, '')));
    child.stdin.on('error', () => { /* 입력을 읽지 않고 끝나는 명령 */ });
    child.stdin.end(input);
  });
}

const input = fs.readFileSync(0, 'utf8');
const userCommand = userStatuslineCommand();
Promise.all([
  userCommand ? run(userCommand, [], input, true) : '',
  run(process.execPath, [path.join(__dirname, 'graft-statusline.cjs')], input, false),
]).then((outputs) => process.stdout.write(outputs.filter(Boolean).join('\n')));
