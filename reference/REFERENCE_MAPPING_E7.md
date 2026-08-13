# Reference-preserving bridge mapping (non-normative)

## Purpose

Provide a constructive existence proof that the current MCP tool-result data model has enough carrier capacity to preserve the RFC 9457 semantics exercised by the frozen 12-case profile.

This is **not** a proposed mandatory mapping. A different mapping is conformant if the frozen carrier-neutral oracle can deterministically recover the source semantic without prose mining and no forbidden semantic is introduced.

## Mapping

For an upstream response identified by its source contract/media type as `application/problem+json`:

1. Parse the JSON object without interpreting extension-member names.
2. Return a tool-execution result with `isError: true` for the tested non-2xx responses.
3. Embed the unmodified JSON data model as an MCP embedded text resource with declared `mimeType: application/problem+json`.
4. Preserve HTTP observations separately in namespaced result `_meta`, including `observed_http_status`, original `content_type`, and `content_language` when present.
5. Do not infer retryability, retry delays, safety, idempotence, custom problem types, or semantics from `title`/`detail` prose.

For successful JSON, use `structuredContent` (with a serialized TextContent compatibility copy). For non-problem errors, do not infer RFC 9457 from JSON field shape.

## Why body status and observed status are separate

RFC 9457's `status` member records the origin status and is advisory; an intermediary can change the observed HTTP status. The mapping therefore leaves the body untouched and records the observed transport status separately.

## Why an embedded resource

MCP tool results can contain embedded resources with a MIME type. Using an explicitly typed `application/problem+json` resource avoids depending on any disputed convention about error-specific `outputSchema` / `structuredContent` behavior. It is only one possible carrier.

## Resource URI

The executable model uses a self-contained `data:` URI so the bridge does not invent an external resource identity or dereferenceability claim.
