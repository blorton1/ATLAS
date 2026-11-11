/* Private ATLAS transport. Public demo pages do not load this script. */
(function(global){
  'use strict';
  const SESSION_KEY='atlas_owner_session_v1';
  const ENGINE_KEY='atlas_interview_demo_v1';
  const clone=x=>JSON.parse(JSON.stringify(x));
  function createCloudApi({config,fetch:remote,storage,createApi,now=()=>Date.now()}){
    const base=new URL(config.url);if(base.protocol!=='https:'||!base.hostname.endsWith('.supabase.co'))throw Error('Invalid Supabase project URL.');
    const endpoint=path=>new URL(path,base).href;
    function session(){try{return JSON.parse(storage.getItem(SESSION_KEY)||'null');}catch{throw Error('Sign-in storage is unavailable.');}}
    function saveSession(s){if(!s?.access_token||!s?.refresh_token||!s?.user?.id)throw Error('Incomplete sign-in response.');const value={...s,expires_at:s.expires_at||Math.floor(now()/1000)+(s.expires_in||3600)};storage.setItem(SESSION_KEY,JSON.stringify(value));return value;}
    async function json(path,options={},token){
      const response=await remote(endpoint(path),{...options,headers:{apikey:config.key,'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{}),...options.headers}});
      let data;try{data=await response.json();}catch{data={};}
      if(!response.ok){const error=Error(data.msg||data.error_description||data.message||data.error||'Cloud request failed.');error.status=response.status;error.code=data.code;throw error;}return data;
    }
    async function activeSession(){
      let s=session();if(!s?.access_token||!s?.refresh_token||!s?.user?.id){const e=Error('Sign in to open your saved pipeline.');e.status=401;throw e;}
      if(!s.expires_at||s.expires_at*1000<=now()+60000){
        try{s=saveSession(await json('/auth/v1/token?grant_type=refresh_token',{method:'POST',body:JSON.stringify({refresh_token:s.refresh_token})}));}
        catch(error){if(error.status===400||error.status===401){storage.removeItem(SESSION_KEY);error.status=401;}throw error;}
      }return s;
    }
    async function request(path,method='GET',body){
      try{
        const s=await activeSession();
        const row=await json('/rest/v1/rpc/atlas_open_workspace',{method:'POST',body:'{}'},s.access_token);
        if(!row?.state||!Number.isInteger(row.version)){const e=Error('Your private workspace has not been provisioned. Contact the ATLAS owner.');e.status=403;throw e;}
        const memory=new Map();
        const local={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)};
        const engine=createApi(clone(row.state),local);
        const result=engine.request(path,method,body);
        if(result.status>=400||method==='GET')return result;
        const raw=memory.get(ENGINE_KEY);if(!raw)throw Error('Changes were not saved: mutation did not produce a workspace.');
        await json('/rest/v1/rpc/atlas_save_workspace',{method:'POST',body:JSON.stringify({expected_version:row.version,new_state:JSON.parse(raw)})},s.access_token);
        return result;
      }catch(error){return {status:error.code==='40001'?409:(error.status||503),body:{error:error.code==='40001'?'Pipeline changed on another device. Refresh before saving.':error.message}};}
    }
    async function sendLink(email,redirect){if(email!=='brendan.lorton123@gmail.com')throw Error('Use the enrolled ATLAS owner email.');return json('/auth/v1/otp?redirect_to='+encodeURIComponent(redirect),{method:'POST',body:JSON.stringify({email,create_user:true})});}
    async function verifyCode(email,token){return saveSession(await json('/auth/v1/verify',{method:'POST',body:JSON.stringify({email,token,type:'email'})}));}
    async function verifyLink(value){
      let link;try{link=new URL(value);}catch{throw Error('Paste the complete Supabase confirmation link from your email.');}
      if(link.protocol!=='https:'||link.hostname!==base.hostname||link.pathname!=='/auth/v1/verify')throw Error('Use the confirmation link for this ATLAS Supabase project.');
      const token=link.searchParams.get('token_hash')||link.searchParams.get('token'),type=link.searchParams.get('type')||'email';
      if(!token||!['email','signup','magiclink','invite'].includes(type))throw Error('This confirmation link is incomplete or unsupported.');
      return saveSession(await json('/auth/v1/verify',{method:'POST',body:JSON.stringify({token_hash:token,type})}));
    }
    async function acceptLink(hash){const p=new URLSearchParams(hash.replace(/^#/,''));if(!p.get('access_token'))return false;const user=await json('/auth/v1/user',{},p.get('access_token'));saveSession({access_token:p.get('access_token'),refresh_token:p.get('refresh_token'),expires_in:Number(p.get('expires_in'))||3600,user});return true;}
    async function signOut(){const s=session();storage.removeItem(SESSION_KEY);if(s?.access_token)try{await json('/auth/v1/logout',{method:'POST'},s.access_token);}catch{} }
    return {request,sendLink,verifyCode,verifyLink,acceptLink,signOut,session,saveSession};
  }
  if(typeof module!=='undefined'&&module.exports){module.exports={createCloudApi,SESSION_KEY};return;}
  const config=global.ATLAS_CLOUD_CONFIG;if(!config){global.ATLAS_CLOUD_ERROR='Cloud configuration is unavailable.';return;}
  const originalFetch=global.fetch.bind(global);
  const api=createCloudApi({config,fetch:originalFetch,storage:global.localStorage,createApi:global.ATLAS_CREATE_API});
  global.ATLAS_CLOUD=api;
  global.fetch=async function(input,options={}){
    const u=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href);
    if(u.origin!==location.origin||!u.pathname.startsWith('/api/'))return originalFetch(input,options);
    try{
      const method=(options.method||(typeof input!=='string'&&input.method)||'GET').toUpperCase();let body=options.body;
      if(body===undefined&&typeof input!=='string'&&!(input instanceof URL)&&method!=='GET')body=await input.clone().text();
      const result=await api.request(u.pathname+u.search,method,body?JSON.parse(body):undefined);
      if(result.status===401&&location.pathname!=='/pipeline-login.html')location.replace('/pipeline-login.html');
      return new Response(JSON.stringify(result.body),{status:result.status,headers:{'Content-Type':'application/json'}});
    }catch(e){return new Response(JSON.stringify({error:e.message}),{status:503,headers:{'Content-Type':'application/json'}});}
  };
})(globalThis);
