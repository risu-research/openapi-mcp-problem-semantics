# RISU Probe P4-U: real external MCP released-version drift

Compares real installed releases of **mcp-server-time** from the external modelcontextprotocol/servers project: **2026.10.19** and **2026.11.4**, on genuine MCP stdio JSON-RPC. We do not invent an updated MCP schema for the comparison.

Exact PyPI wheel SHA-256 values and publisher release Git commits are in release_pins.json. Each installed wheel starts its own isolated Python environment; the protocol version is negotiated through initialize (2025-11-25), and we capture tools/list and safe read-only tools/call for both releases. The P4-T comparator reads the actual captured tools/list responses.

We compare outputSchema field changes, and separately report inputSchema.required drift, added/removed tools, and actual structuredContent keys. In particular, the newly advertised convert_time output field later_occurrence is optional and is **not** automatically a new mandatory output duty. No operator policy was supplied, so no change in operator policy is claimed.

The server has no external service dependency for the chosen calls. Dependencies are installed online in CI from PyPI but the MCP calls happen through local stdio. The top-level wheel bytes are hashed; dependencies are recorded, not all byte-hash-pinned.

The output can validate exposed schema changes, not an external supplier contract breach, production data loss, or a real-world user's use of upgraded versions. Results are only confirmed after CI captures the actual server wire and verifies SHA-linked P4-T snapshots.

Artifacts: results/<version>/mcp_stdio_wire.jsonl, tools_list.json, tool_calls.json, installed_dependencies.txt, capture_manifest.json; results/*.snapshot.json, *.diff.json, p4u_real_release_report.json.
