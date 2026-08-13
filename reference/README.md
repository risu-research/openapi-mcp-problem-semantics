# Constructive reference

The reference bridge is a **non-normative existence proof**, not a mandated mapping.

For an in-scope `application/problem+json` response, the reference model:

1. preserves the Problem Details JSON data model in an explicitly typed embedded resource with `mimeType = application/problem+json`;
2. preserves observed source HTTP facts separately in namespaced result `_meta`;
3. marks the tool result as an error without mining human prose into additional machine semantics; and
4. leaves non-problem JSON outside the RFC 9457 path.

The reference E7 experiment carried this representation through an actual official MCP 2026-07-28 TypeScript v2 client/server stdio boundary and passed all 11 in-scope frozen cases.

Do not infer from this result that EmbeddedResource is the only conforming target carrier. The profile is representation-neutral by design.
