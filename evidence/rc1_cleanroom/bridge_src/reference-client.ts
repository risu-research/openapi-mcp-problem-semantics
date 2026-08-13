import { spawn } from "node:child_process";
import { once } from "node:events";
import { createWriteStream, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const SPEC_VERSION = "2026-07-28";
const BRIDGE_ROOT = dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT = resolve(BRIDGE_ROOT, "..");
const HANDOFF_ROOT = resolve(PACKAGE_ROOT, "..");
const EVIDENCE_ROOT = resolve(HANDOFF_ROOT, "evidence-e7-reference");
const FIXTURE_PORT = Number.parseInt(process.env.E7_FIXTURE_PORT ?? "18765", 10);
const FIXTURE_BASE_URL = `http://127.0.0.1:${FIXTURE_PORT}`;
const NODE_BINARY = process.execPath;
const PYTHON_BINARY = process.env.E7_PYTHON ?? "python3";

interface SourceResponse {
  http_status: number;
  content_type: string;
  content_language?: string;
  body: unknown;
}

interface CorpusCase extends Partial<SourceResponse> {
  id: string;
  pair?: SourceResponse[];
}

interface Corpus {
  cases: CorpusCase[];
}

const TOOL_BY_CASE: Record<string, string[]> = {
  "P01-explicit-type": ["fixture_P01_explicit_type"],
  "P02-default-about-blank": ["fixture_P02_default_about_blank"],
  "P03-same-status-different-type": [
    "fixture_P03_same_status_different_type_1",
    "fixture_P03_same_status_different_type_2",
  ],
  "P04-instance": ["fixture_P04_instance"],
  "P05-media-type-gate": ["fixture_P05_media_type_gate"],
  "P06-scalar-extension": ["fixture_P06_scalar_extension"],
  "P07-nested-validation-extension": ["fixture_P07_nested_validation_extension"],
  "P08-unknown-future-extension": ["fixture_P08_unknown_future_extension"],
  "P09-localized-human-text": [
    "fixture_P09_localized_human_text_1",
    "fixture_P09_localized_human_text_2",
  ],
  "P10-no-prose-mining": ["fixture_P10_no_prose_mining"],
  "P11-origin-status-survives-intermediary": ["fixture_P11_origin_status_survives_intermediary"],
  "P12-no-retryability-invention": ["fixture_P12_no_retryability_invention"],
};

function sourceResponses(testCase: CorpusCase): SourceResponse[] {
  if (testCase.pair !== undefined) {
    return testCase.pair;
  }
  return [
    {
      http_status: testCase.http_status as number,
      content_type: testCase.content_type as string,
      ...(testCase.content_language === undefined ? {} : { content_language: testCase.content_language }),
      body: testCase.body,
    },
  ];
}

async function waitForFixture(fixture: ReturnType<typeof spawn>): Promise<void> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (fixture.exitCode !== null) {
      throw new Error(`fixture server exited before becoming ready (exit ${fixture.exitCode})`);
    }
    try {
      const response = await fetch(`${FIXTURE_BASE_URL}/openapi.json`);
      if (response.ok) {
        return;
      }
    } catch {
      // The fixture is still starting.
    }
    await new Promise(resolveWait => setTimeout(resolveWait, 25));
  }
  throw new Error("fixture server did not become ready");
}

async function main(): Promise<void> {
  const wireIn = resolve(EVIDENCE_ROOT, "e7-client-to-server-wire.jsonl");
  const wireOut = resolve(EVIDENCE_ROOT, "e7-server-to-client-wire.jsonl");
  const bridgeStderr = resolve(EVIDENCE_ROOT, "e7-bridge-stderr.jsonl");
  writeFileSync(wireIn, "");
  writeFileSync(wireOut, "");
  writeFileSync(bridgeStderr, "");

  const fixture = spawn(PYTHON_BINARY, [resolve(HANDOFF_ROOT, "fixture_server.py"), "--port", String(FIXTURE_PORT)], {
    stdio: ["ignore", "ignore", "pipe"],
  });
  const fixtureStderr = createWriteStream(resolve(EVIDENCE_ROOT, "e7-fixture-stderr.log"), { flags: "w" });
  fixture.stderr.pipe(fixtureStderr);

  let client: Client | undefined;
  try {
    await waitForFixture(fixture);
    const transport = new StdioClientTransport({
      command: NODE_BINARY,
      args: [resolve(BRIDGE_ROOT, "wire-tee.js"), NODE_BINARY, resolve(BRIDGE_ROOT, "reference-bridge.js")],
      cwd: PACKAGE_ROOT,
      stderr: "pipe",
      env: {
        ...process.env,
        E7_FIXTURE_BASE_URL: FIXTURE_BASE_URL,
        E7_WIRE_IN_LOG: wireIn,
        E7_WIRE_OUT_LOG: wireOut,
      } as Record<string, string>,
    });
    const bridgeStderrStream = createWriteStream(bridgeStderr, { flags: "a" });
    transport.stderr?.pipe(bridgeStderrStream);

    client = new Client(
      { name: "risu-e7-reference-client", version: "1.0.0" },
      { versionNegotiation: { mode: { pin: SPEC_VERSION } } },
    );
    await client.connect(transport);
    const toolsList = await client.listTools();
    const corpus = JSON.parse(readFileSync(resolve(HANDOFF_ROOT, "cases.json"), "utf8")) as Corpus;

    const cases = [];
    for (const testCase of corpus.cases) {
      const tools = TOOL_BY_CASE[testCase.id];
      if (tools === undefined) {
        throw new Error(`no tool mapping for ${testCase.id}`);
      }
      const sources = sourceResponses(testCase);
      const calls = [];
      for (let index = 0; index < tools.length; index += 1) {
        const raw = await client.callTool({ name: tools[index], arguments: {} });
        calls.push({ source: sources[index], tool_name: tools[index], arguments: {}, raw_call_tool_result: raw });
      }
      cases.push({ id: testCase.id, calls });
    }

    const sameToolName = "fixture_S00_asymmetry";
    const success = await client.callTool({ name: sameToolName, arguments: { outcome: "success" } });
    const problem = await client.callTool({ name: sameToolName, arguments: { outcome: "problem" } });
    const output = {
      generated_at_utc: new Date().toISOString(),
      official_sdk: {
        client_package: "@modelcontextprotocol/client@2.0.0",
        server_package: "@modelcontextprotocol/server@2.0.0",
      },
      protocol: {
        pinned_spec_version: SPEC_VERSION,
        era: client.getProtocolEra(),
        negotiated_protocol_version: client.getNegotiatedProtocolVersion(),
        discover_result: client.getDiscoverResult(),
      },
      tools_list: toolsList,
      cases,
      same_operation_control: {
        tool_name: sameToolName,
        success: { arguments: { outcome: "success" }, raw_call_tool_result: success },
        problem: { arguments: { outcome: "problem" }, raw_call_tool_result: problem },
      },
    };
    writeFileSync(resolve(EVIDENCE_ROOT, "e7-official-client-raw.json"), `${JSON.stringify(output, null, 2)}\n`);
    await client.close();
    client = undefined;
    bridgeStderrStream.end();
  } finally {
    if (client !== undefined) {
      await client.close().catch(() => undefined);
    }
    if (fixture.exitCode === null) {
      fixture.kill("SIGTERM");
      await once(fixture, "exit").catch(() => undefined);
    }
    fixtureStderr.end();
  }
}

main().catch(error => {
  process.stderr.write(`${error instanceof Error ? error.stack ?? error.message : String(error)}\n`);
  process.exitCode = 1;
});
