import fs from 'node:fs';
const record=(entry)=>{const p=process.env.RUNWARE_MOCK_LOG;if(p)fs.appendFileSync(p,JSON.stringify(entry)+'\n');};
export function isRunwareError(){return false}
export async function createClient(options){
  record({kind:'createClient',hasKey:!!options.apiKey,userAgentPrefix:options.userAgentPrefix});
  return {
    connect:async()=>{record({kind:'connect'})},
    disconnect:async()=>{record({kind:'disconnect'})},
    run:async(params,opts)=>{
      record({kind:'run',params,options:opts});
      return [{mockTaskId:'CONTROLLED-NO-EXTERNAL-API',received:params,summary:'CONTROLLED ' + String(params.positivePrompt??'NO_PROMPT')+' width='+String(params.width??'NONE')}];
    }
  };
}
