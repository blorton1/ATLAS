'use strict';
const assert=require('node:assert/strict');
const {createCloudApi,SESSION_KEY}=require('./cloud-api.js');
const {createDemoApi}=require('../demo/demo-api.js');
const seed={asOf:'2026-11-11',mode:'PUBLIC MARKET INTELLIGENCE',accounts:[{id:'a',name:'Example',signals:[]}],accountPlans:{},researchReviews:{},feed:{events:[],runs:[]}};
const makeStorage=()=>{const m=new Map();return {getItem:k=>m.get(k)||null,setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)}};
const storage=makeStorage();
storage.setItem(SESSION_KEY,JSON.stringify({access_token:'test-access',refresh_token:'test-refresh',expires_at:9999999999,user:{id:'owner'}}));
let version=1,state=structuredClone(seed),posts=0,conflict=false,offline=false;
const remote=async(url,options)=>{
  if(offline)throw Error('Network unavailable');
  if(url.includes('/rest/v1/rpc/atlas_open_workspace'))return new Response(JSON.stringify({version,state}));
  if(url.includes('/rest/v1/rpc/atlas_save_workspace')){
    posts++;const payload=JSON.parse(options.body);
    if(conflict||payload.expected_version!==version)return new Response(JSON.stringify({code:'40001',message:'conflict'}),{status:400});
    state=payload.new_state;version++;return new Response(JSON.stringify({version}));
  }throw Error('Unexpected endpoint '+url);
};
const config={url:'https://iikworeqzzinccrhshed.supabase.co',key:'test-publishable'};
const api=createCloudApi({config,fetch:remote,storage,createApi:createDemoApi});
(async()=>{
  const initial=await api.request('/api/bootstrap');assert.equal(initial.status,200);assert.equal(posts,0);
  let result=await api.request('/api/account-plans/a','PUT',{version:0,plan:{owner:'Brendan',salesMotion:'Federal',missionOwner:'Discovery required'}});
  assert.equal(result.status,200);assert.equal(state.accountPlans.a.plan.owner,'Brendan');assert.equal(posts,1);
  const api2=createCloudApi({config,fetch:remote,storage,createApi:createDemoApi});
  assert.equal((await api2.request('/api/bootstrap')).body.accountPlans.a.plan.salesMotion,'Federal');
  result=await api2.request('/api/account-plans/a','PUT',{version:0,plan:{owner:'Stale'}});assert.equal(result.status,409);assert.equal(posts,1);
  conflict=true;result=await api.request('/api/account-plans/a','PUT',{version:1,plan:{owner:'Not saved'}});assert.equal(result.status,409);assert.equal(state.accountPlans.a.plan.owner,'Brendan');
  conflict=false;offline=true;result=await api.request('/api/account-plans/a','PUT',{version:1,plan:{owner:'Not saved'}});assert.equal(result.status,503);assert.equal(state.accountPlans.a.plan.owner,'Brendan');
  offline=false;storage.removeItem(SESSION_KEY);result=await api.request('/api/bootstrap');assert.equal(result.status,401);
  assert.equal(storage.getItem('atlas_interview_demo_v1'),null,'Private workspace must not persist in public demo storage');
  const authStorage=makeStorage();let otpBody,verifyBody,refreshes=0;
  const authRemote=async(url,options)=>{
    if(url.includes('/auth/v1/otp')){otpBody=JSON.parse(options.body);return new Response('{}');}
    if(url.includes('/auth/v1/verify')){verifyBody=JSON.parse(options.body);return new Response(JSON.stringify({access_token:'new-test-access',refresh_token:'new-test-refresh',expires_in:3600,user:{id:'owner'}}));}
    if(url.includes('/auth/v1/token')){refreshes++;return new Response(JSON.stringify({access_token:'refreshed-test-access',refresh_token:'refreshed-test-refresh',expires_in:3600,user:{id:'owner'}}));}
    return remote(url,options);
  };
  const authApi=createCloudApi({config,fetch:authRemote,storage:authStorage,createApi:createDemoApi});
  await authApi.sendLink('brendan.lorton123@gmail.com','https://demo.example/pipeline-login.html');assert.equal(otpBody.create_user,true);
  await assert.rejects(()=>authApi.sendLink('other@example.invalid','https://demo.example/'),/enrolled/);
  await assert.rejects(()=>authApi.verifyLink('https://other.example/auth/v1/verify?token=secret&type=email'),/this ATLAS/);
  await authApi.verifyLink(config.url+'/auth/v1/verify?token=test-token-hash&type=magiclink');assert.equal(verifyBody.token_hash,'test-token-hash');
  const stale=JSON.parse(authStorage.getItem(SESSION_KEY));stale.expires_at=1;authStorage.setItem(SESSION_KEY,JSON.stringify(stale));
  assert.equal((await authApi.request('/api/bootstrap')).status,200);assert.equal(refreshes,1);
  console.log('PASS: remote saves, cross-device reads, stale record/workspace conflicts, network failure, missing session, demo isolation.');
})().catch(error=>{console.error(error);process.exitCode=1;});
