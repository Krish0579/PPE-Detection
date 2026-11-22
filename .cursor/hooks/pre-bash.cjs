#!/usr/bin/env node
/**
 * Project Cursor hook: beforeShellExecution / pre-bash.
 * Always prints JSON on stdout so Cursor can enable the hook.
 */

const DANGEROUS = ['rm -rf /', 'format c:', 'del /s /q c:\\', ':(){:|:&};:'];

function readStdin() {
  return new Promise((resolve) => {
    if (process.stdin.isTTY) {
      resolve('');
      return;
    }
    let data = '';
    const timer = setTimeout(() => {
      process.stdin.pause();
      resolve(data);
    }, 500);
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => {
      data += chunk;
    });
    process.stdin.on('end', () => {
      clearTimeout(timer);
      resolve(data);
    });
    process.stdin.on('error', () => {
      clearTimeout(timer);
      resolve(data);
    });
    process.stdin.resume();
  });
}

function emit(payload) {
  process.stdout.write(JSON.stringify(payload) + '\n');
}

function commandFrom(input) {
  const toolInput = input.toolInput || input.tool_input || {};
  return String(
    input.command ||
      toolInput.command ||
      input.prompt ||
      process.env.PROMPT ||
      '',
  );
}

async function main() {
  let input = {};
  const raw = (await readStdin()).trim();
  if (raw) {
    try {
      input = JSON.parse(raw);
    } catch {
      input = {};
    }
  }

  const cmd = commandFrom(input).toLowerCase();
  for (const pattern of DANGEROUS) {
    if (cmd.includes(pattern)) {
      emit({
        permission: 'deny',
        continue: false,
        decision: 'block',
        user_message: `Dangerous command blocked: ${pattern}`,
        agent_message: `A project hook blocked this command because it matched ${pattern}.`,
      });
      process.exit(2);
    }
  }

  emit({ permission: 'allow', continue: true });
}

main().catch(() => {
  emit({ permission: 'allow', continue: true });
});
