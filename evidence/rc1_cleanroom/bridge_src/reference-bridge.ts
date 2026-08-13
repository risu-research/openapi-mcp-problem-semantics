import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { McpServer, type CallToolResult } from "@modelcontextprotocol/server";
import { serveStdio } from "@modelcontextprotocol/server/stdio";
import { z } from "zod";

const PROBLEM_JSON = "application/problem+json";
const SOURCE_HTTP_META = "org.risu.reference.source_http";
const OPENAPI_PATH = fileURLToPath(new URL("../../openapi.json", import.meta.url));
const FIXTURE_BASE_URL = process.env.E7_FIXTURE_BASE_URL ?? "http://127.0.0.1:8765";

interface OpenApiOperation {
  operationId?: string;
  summary?: string;
  description?: string;
}

interface OpenApiDocument {
  paths?: Record<string, Record<string, OpenApiOperation>>;
}

function mediaTypeBase(value: string | null): string {
  return (value ?? "").split(";", 1)[0].trim().toLowerCase();
}

function compactJson(value: unknown): string {
  return JSON.stringify(value);
}

function problemDataUri(text: string): string {
  const encoded = encodeURIComponent(text).replace(/[!'()*]/g, character =>
    `%${character.charCodeAt(0).toString(16).toUpperCase()}`,
  );
  return `data:${PROBLEM_JSON},${encoded}`;
}

function sourceMeta(response: Response): Record<string, unknown> {
  const source: Record<string, unknown> = {
    observed_http_status: response.status,
    content_type: response.headers.get("content-type") ?? "",
  };
  const language = response.headers.get("content-language");
  if (language !== null) {
    source.content_language = language;
  }
  return { [SOURCE_HTTP_META]: source };
}

async function mapHttpResponse(toolName: string, response: Response): Promise<CallToolResult> {
  const text = await response.text();
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    body = undefined;
  }

  const audit = {
    event: "e7_upstream_response",
    tool_name: toolName,
    observed_http_status: response.status,
    content_type: response.headers.get("content-type") ?? "",
    ...(response.headers.get("content-language") === null
      ? {}
      : { content_language: response.headers.get("content-language") }),
    body,
  };
  process.stderr.write(`${compactJson(audit)}\n`);

  const meta = sourceMeta(response);
  if (mediaTypeBase(response.headers.get("content-type")) === PROBLEM_JSON && body !== undefined) {
    const problemText = compactJson(body);
    return {
      content: [
        {
          type: "resource",
          resource: {
            uri: problemDataUri(problemText),
            mimeType: PROBLEM_JSON,
            text: problemText,
          },
        },
      ],
      isError: response.status < 200 || response.status >= 300,
      _meta: meta,
    };
  }

  if (response.ok && body !== undefined) {
    return {
      content: [{ type: "text", text: compactJson(body) }],
      structuredContent: body as Record<string, unknown>,
      isError: false,
      _meta: meta,
    };
  }

  return {
    content: [{ type: "text", text: `Upstream HTTP ${response.status}` }],
    isError: !response.ok,
    _meta: meta,
  };
}

function buildServer(): McpServer {
  const openapi = JSON.parse(readFileSync(OPENAPI_PATH, "utf8")) as OpenApiDocument;
  const server = new McpServer(
    { name: "risu-e7-reference-bridge", version: "1.0.0" },
    { capabilities: { tools: {} } },
  );

  for (const [path, pathItem] of Object.entries(openapi.paths ?? {})) {
    const operation = pathItem.get;
    if (operation?.operationId === undefined) {
      continue;
    }
    const operationId = operation.operationId;
    const description = operation.description ?? operation.summary ?? `GET ${path}`;

    if (path === "/S00-asymmetry") {
      server.registerTool(
        operationId,
        {
          description,
          inputSchema: z.object({ outcome: z.enum(["success", "problem"]) }),
        },
        async ({ outcome }) => {
          const target = new URL(path, FIXTURE_BASE_URL);
          target.searchParams.set("outcome", outcome);
          return mapHttpResponse(operationId, await fetch(target));
        },
      );
      continue;
    }

    server.registerTool(
      operationId,
      { description, inputSchema: z.object({}) },
      async () => mapHttpResponse(operationId, await fetch(new URL(path, FIXTURE_BASE_URL))),
    );
  }

  return server;
}

serveStdio(buildServer, {
  legacy: "reject",
  onerror: error => process.stderr.write(`${compactJson({ event: "e7_server_error", message: error.message })}\n`),
});
