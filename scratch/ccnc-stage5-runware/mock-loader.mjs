// Test-only dependency substitution. The third-party @runware/mcp server's files are untouched.
export async function resolve(specifier, context, nextResolve){
  if(specifier==='@runware/sdk'){
    return {url:new URL('./mock-sdk.mjs',import.meta.url).href,shortCircuit:true};
  }
  return nextResolve(specifier,context);
}
