#!/usr/bin/env node
/**
 * Project Cursor hook: preToolUse for file edits.
 * Always prints JSON on stdout so Cursor can enable the hook.
 */

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

async function main() {
  await readStdin();
  process.stdout.write(
    JSON.stringify({ permission: 'allow', continue: true }) + '\n',
  );
}

main().catch(() => {
  process.stdout.write(
    JSON.stringify({ permission: 'allow', continue: true }) + '\n',
  );
});
