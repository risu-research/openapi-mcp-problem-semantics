import { createWriteStream } from "node:fs";
import { spawn } from "node:child_process";

const [command, ...args] = process.argv.slice(2);
if (command === undefined) {
  throw new Error("usage: wire-tee <command> [args ...]");
}

const inboundPath = process.env.E7_WIRE_IN_LOG;
const outboundPath = process.env.E7_WIRE_OUT_LOG;
if (inboundPath === undefined || outboundPath === undefined) {
  throw new Error("E7_WIRE_IN_LOG and E7_WIRE_OUT_LOG are required");
}

const inboundLog = createWriteStream(inboundPath, { flags: "a" });
const outboundLog = createWriteStream(outboundPath, { flags: "a" });
const child = spawn(command, args, { env: process.env, stdio: ["pipe", "pipe", "pipe"] });

process.stdin.on("data", chunk => {
  inboundLog.write(chunk);
  child.stdin.write(chunk);
});
process.stdin.on("end", () => child.stdin.end());
child.stdout.on("data", chunk => {
  outboundLog.write(chunk);
  process.stdout.write(chunk);
});
child.stderr.on("data", chunk => process.stderr.write(chunk));

child.on("error", error => {
  process.stderr.write(`${JSON.stringify({ event: "e7_wire_tee_error", message: error.message })}\n`);
  process.exitCode = 1;
});
child.on("exit", (code, signal) => {
  inboundLog.end();
  outboundLog.end();
  if (signal !== null) {
    process.kill(process.pid, signal);
  } else {
    process.exitCode = code ?? 1;
  }
});
