/* Interview-only API: data stays in this browser; no owner database writes. */
(function (global) {
  'use strict';
  const KEY = 'atlas_interview_demo_v1';
  const copy = x => JSON.parse(JSON.stringify(x));
  const own = (o,k) => Object.prototype.hasOwnProperty.call(o,k);
  const fail = (message,status=400,current) => { const e=new Error(message);e.status=status;e.current=current;throw e; };
  const object = (o,allowed) => {
    if (!o || typeof o!=='object' || Array.isArray(o) || Object.keys(o).some(k=>!allowed.includes(k))) fail('Unsupported fields or invalid object.');
  };
  const text = (v,label,required=false,max=20000) => {
    if (typeof v!=='string' || v.length>max || (required&&!v.trim())) fail(label+' must be '+(required?'nonempty ':'')+'text.');
    return v.trim();
  };
  const https = (v,label,required=false) => {
    v=text(v||'',label,required,2048);if(!v)return '';
    let u;try {u=new URL(v);}catch{fail(label+' must be an HTTPS URL.');}
    if(u.protocol!=='https:'||!u.hostname||u.username||u.password||(u.port&&u.port!=='443')||/\s/.test(v))fail(label+' must be an HTTPS URL without credentials.');
    return v;
  };
  const date = (v,label,required=false,nonfuture=true) => {
    if(!v&&!required)return '';
    if(typeof v!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(v)||!Number.isFinite(Date.parse(v))||new Date(v).toISOString().slice(0,10)!==v||(nonfuture&&v>new Date().toISOString().slice(0,10)))fail(label+' must be a valid '+(nonfuture?'nonfuture ':'')+'YYYY-MM-DD date.');
    return v;
  };
  const amount = v => typeof v==='number'&&Number.isFinite(v)&&v>=0;
  const qualified = r => r&&r.status==='Qualified target'&&r.usVerified===true&&r.sectorVerified===true&&r.usSource&&r.sectorSource&&r.checkedOn&&r.reviewer?.trim()&&r.rationale?.trim();
  const stages=['Unknown','Seed','Series A','Series B','Series C','Series D','Series E+','Public','Acquired'];
  const planText=['qualification','stageSource','stageRationale','stage','owner','nextAction','nextActionDate','notes','planUpdatedAt','relationship','objectives'];
  const listFields={contacts:['id','name','role','email','influence'],opportunities:['id','name','stage','amount','product','nextStep'],activities:['id','date','type','summary']};
  function validatePlan(p) {
    object(p,[...planText,...Object.keys(listFields),'shortlisted']);
    for(const k of planText)if(p[k]!=null)text(p[k],k);
    const enums={qualification:['Needs review','Qualified target','Outside target'],stage:['Identified','Qualified','Outreach','Discovery','Pilot','Opportunity','Customer','Growth discovery','Expansion opportunity','Disqualified'],relationship:['Prospect','Customer','Partner']};
    for(const [k,values] of Object.entries(enums))if(p[k]&&!values.includes(p[k]))fail('Unsupported '+k);
    if(own(p,'shortlisted')&&typeof p.shortlisted!=='boolean')fail('shortlisted must be boolean.');
    if(p.stageSource)https(p.stageSource,'stageSource');
    date(p.nextActionDate,'nextActionDate',false,false);
    if(p.planUpdatedAt&&!Number.isFinite(Date.parse(p.planUpdatedAt)))fail('Invalid plan update timestamp.');
    for(const [key,fields] of Object.entries(listFields)) {
      const rows=p[key]||[];if(!Array.isArray(rows)||rows.length>250)fail('Invalid '+key+' list.');
      const ids=new Set();
      for(const row of rows) {
        object(row,fields);text(row.id,'id',true);if(ids.has(row.id))fail('Duplicate list entry ID.');ids.add(row.id);
        for(const [k,v] of Object.entries(row)) {
          if(k==='amount'&&key==='opportunities'){if(v!=null&&v!==''&&!amount(v))fail('Invalid opportunity amount.');}
          else if(v!=null)text(v,key+'.'+k);
        }
        if(key==='opportunities'&&row.stage&&!['Discovery','Evaluation','Pilot','Proposal','Negotiation','Won','Lost'].includes(row.stage))fail('Unsupported opportunity stage.');
        if(key==='activities')date(row.date,'Activity date',false,false);
      }
    }
  }
  function validateReview(r) {
    object(r,['status','usVerified','sectorVerified','latestStage','latestStageVerified','stageSource','usSource','sectorSource','checkedOn','rationale','reviewer']);
    r={status:'Needs review',latestStage:'Unknown',usVerified:false,sectorVerified:false,latestStageVerified:false,...r};
    if(!['Needs review','Qualified target','Outside target'].includes(r.status)||!stages.includes(r.latestStage))fail('Invalid qualification status or stage.');
    for(const k of ['usVerified','sectorVerified','latestStageVerified'])if(typeof r[k]!=='boolean')fail(k+' must be boolean.');
    for(const k of ['stageSource','usSource','sectorSource'])r[k]=https(r[k]||'',k);
    r.checkedOn=date(r.checkedOn,'Review date');
    for(const k of ['rationale','reviewer'])r[k]=text(r[k]||'',k);
    if(r.status==='Qualified target'&&!qualified(r))fail('Qualification requires US and business-fit checks, source URLs, review date, reviewer and sales rationale.');
    return r;
  }
  function createDemoApi(seed,storage) {
    const baseline=copy(seed);
    baseline.accountPlans ||= {};baseline.researchReviews ||= {};baseline.feed ||= {events:[],runs:[]};
    function read(){let raw;try{raw=storage.getItem(KEY);}catch{fail('Browser storage is unavailable. Enable site storage to use this demo.',503);}if(!raw)return copy(baseline);try{const s=JSON.parse(raw);if(!Array.isArray(s.accounts)||!s.accountPlans||!s.researchReviews||!s.feed)throw Error();return s;}catch{fail('Saved demo data could not be read. Reset the demo to restore its example data.',503);}}
    function save(s){try{storage.setItem(KEY,JSON.stringify(s));}catch{fail('Changes were not saved. Browser storage is full or blocked.',507);}}
    function version(actual,wanted){if(!Number.isInteger(wanted)||wanted<0)fail('Version must be a nonnegative integer.');if((actual?.version||0)!==wanted)fail('Record changed in another tab. Refresh before saving.',409,actual||{version:0});}
    const now=()=>new Date().toISOString();
    const uid=()=>global.crypto?.randomUUID?.()||('demo-'+Date.now()+'-'+Math.random().toString(36).slice(2));
    function request(path,method='GET',body) {
      try {
        const u=new URL(path,'https://demo.local'),p=u.pathname,s=read();let result;
        if(method==='GET') {
          if(p==='/api/bootstrap')result={asOf:s.asOf,mode:s.mode,accounts:s.accounts,accountPlans:s.accountPlans,researchReviews:s.researchReviews};
          else if(p==='/api/research')result={accounts:s.accounts,reviews:s.researchReviews,plans:s.accountPlans,feed:s.feed};
          else if(p==='/api/account-plans')result=s.accountPlans;
          else if(p==='/api/accounts')result=s.accounts.filter(a=>!u.searchParams.get('motion')||a.motion===u.searchParams.get('motion'));
          else if(p.startsWith('/api/accounts/'))result=s.accounts.find(a=>a.id===decodeURIComponent(p.split('/').pop()))||fail('Account not found.',404);
          else if(p==='/api/health')result={status:'ok',data_mode:s.mode,demo:true};
          else fail('Unknown demo endpoint.',404);
          return {status:200,body:copy(result)};
        }
        if(p==='/api/research/collect')fail('Live prospect collection runs in the owner’s scheduled environment. This interview demo includes a dated snapshot; it does not run new web searches.',501);
        if(method==='PUT'&&(p.startsWith('/api/account-plans/')||p.startsWith('/api/research/reviews/'))) {
          const id=decodeURIComponent(p.split('/').pop());if(!s.accounts.some(a=>a.id===id))fail('Account not found.',404);
          const review=p.includes('/reviews/'),key=review?'review':'plan',store=review?s.researchReviews:s.accountPlans;
          object(body,['version',key]);version(store[id],body.version);
          let value=copy(body[key]);
          if(review)value=validateReview(value);
          else {
            validatePlan(value);
            if(value.qualification==='Qualified target'&&!qualified(s.researchReviews[id]?.review))fail('Complete a qualified sales assessment before marking a qualified target.');
            for(const k of ['qualification','stageSource','stageRationale'])if(!own(value,k)&&own(store[id]?.plan||{},k))value[k]=store[id].plan[k];
          }
          result={version:body.version+1,[key]:value,updatedAt:now()};store[id]=result;
        } else if(method==='POST'&&p.startsWith('/api/research/promote/')) {
          const id=decodeURIComponent(p.split('/').pop());if(!s.accounts.some(a=>a.id===id))fail('Account not found.',404);
          object(body,['reviewVersion','planVersion']);version(s.researchReviews[id],body.reviewVersion);version(s.accountPlans[id],body.planVersion);
          const review=s.researchReviews[id]?.review;if(!qualified(review))fail('Save a fully evidenced Qualified target review before promotion.');
          const plan=copy(s.accountPlans[id]?.plan||{relationship:'Prospect',stage:'Qualified'}),activityId='research-promotion-'+body.reviewVersion;
          plan.activities ||= [];if(!plan.activities.some(a=>a.id===activityId))plan.activities.push({id:activityId,date:now().slice(0,10),type:'Research qualification',summary:'Demo qualification by '+review.reviewer+'. '+review.rationale});
          Object.assign(plan,{shortlisted:true,qualification:'Qualified target',stageSource:review.stageSource,stageRationale:review.rationale});validatePlan(plan);
          result={version:body.planVersion+1,plan,updatedAt:now()};s.accountPlans[id]=result;
        } else if(method==='POST'&&p==='/api/research/candidates') {
          object(body,['name','sector','hq','website','workflow','businessNeed','openaiFit','buyerRole','nextStep','priority']);
          const candidate={};for(const k of ['name','sector','hq','workflow'])candidate[k]=text(body[k]||'',k,['name','sector','hq'].includes(k),1000);
          for(const k of ['businessNeed','openaiFit','buyerRole','nextStep'])candidate[k]=text(body[k]||'',k,false,4000);
          candidate.priority=body.priority||'Unassessed';if(!['High','Medium','Low','Unassessed'].includes(candidate.priority))fail('Invalid priority.');
          candidate.website=https(body.website,'website',true);const domain=new URL(candidate.website).hostname.toLowerCase().replace(/^www\./,''),norm=x=>x.toLowerCase().replace(/[^a-z0-9]/g,'');
          if(!norm(candidate.name))fail('Company name must include letters or numbers.');
          if(s.accounts.some(a=>norm(a.name)===norm(candidate.name)||(a.website&&new URL(a.website).hostname.toLowerCase().replace(/^www\./,'')===domain)))fail('Company name or website already exists.');
          candidate.accountId='demo-'+uid();candidate.createdAt=now();
          s.accounts.push({id:candidate.accountId,...candidate,motion:'Acquire',fundingAmount:null,fundingDate:null,contractObligations:null,ttmRevenue:null,contractedACV:null,scenarioAnnualValue:null,scores:{fit:0,urgency:0,capacity:0,access:0,feasibility:0},gate:'Security review',evidenceStrength:0,stage:'Identified',owner:'Unassigned',products:[],workflows:null,buyer:candidate.buyerRole||'To validate',useCases:[{title:candidate.workflow||'Needs discovery',description:'User-entered workflow hypothesis',product:'To validate',buyer:'To validate',kpi:'To validate'}],signals:[],lastReviewed:null,notes:'',accountThesis:candidate.openaiFit||'Potential OpenAI client — sales fit to assess',dataMode:'PUBLIC'});
          result=candidate;
        } else if(method==='POST'&&p==='/api/research/import') {
          object(body,['runDate','events','sources']);date(body.runDate,'runDate',true);
          if(!Array.isArray(body.events)||body.events.length>500||!Array.isArray(body.sources)||body.sources.length>100)fail('Batch exceeds limits or lacks events/sources arrays.');
          const events=body.events.map(raw=>{
            object(raw,['accountId','type','title','date','publishedAt','source','sourceUrl','verification','amount','amountBasis','workflow']);const e=copy(raw);
            if(!s.accounts.some(a=>a.id===e.accountId))fail('Event must identify an existing company.');
            if(!['funding','contract','hiring','expansion','ai_adoption','partnership','product_launch'].includes(e.type))fail('Invalid event type.');
            e.title=text(e.title,'title',true,2000);e.source=text(e.source,'source',true,2000);e.date=date(e.date,'date',true);e.publishedAt=date(e.publishedAt,'publishedAt')||null;e.sourceUrl=https(e.sourceUrl,'sourceUrl',true);
            e.verification ||= 'Pending';if(!['Pending','Primary verified'].includes(e.verification))fail('Invalid evidence status.');
            e.amountBasis=text(e.amountBasis||'','amountBasis');e.workflow=text(e.workflow||'','workflow');e.amount ??= null;if(e.amount!==null&&(!amount(e.amount)||!e.amountBasis))fail('Amounts require a nonnegative value and basis.');
            e.id=uid();e.collectedAt=now();return e;
          });
          const sources=body.sources.map(raw=>{object(raw,['name','url','status','detail']);const x={...raw,name:text(raw.name,'Source name',true,1000),url:https(raw.url,'Source URL',true),detail:text(raw.detail||'','Source detail')};if(!['ok','failed','paywalled'].includes(x.status))fail('Invalid source status.');return x;});
          const key=e=>JSON.stringify([e.accountId,e.type,e.date,e.title.toLowerCase().replace(/\s+/g,' ').trim()]);const keys=new Set(s.feed.events.map(key));let inserted=0;
          for(const e of events)if(!keys.has(key(e))){keys.add(key(e));s.feed.events.push(e);inserted++;const a=s.accounts.find(a=>a.id===e.accountId);a.signals.unshift({id:e.id,type:e.type,date:e.date,title:e.title,amount:e.amount,source:e.source,sourceUrl:e.sourceUrl,publishedAt:e.publishedAt,ingestedAt:e.collectedAt,evidenceType:e.verification,amountBasis:e.amountBasis});}
          const runId=uid(),status=sources.length&&sources.every(x=>x.status==='ok')?'success':'partial';s.feed.runs.unshift({id:runId,kind:'demo_import',runDate:body.runDate,status,sources,collectedAt:now(),inserted,duplicates:events.length-inserted});s.feed.events.sort((a,b)=>b.date.localeCompare(a.date));if(status==='success')s.feed.lastSuccessfulRun=body.runDate;
          result={inserted,duplicates:events.length-inserted,runId};
        } else fail('Unsupported demo operation.',404);
        save(s);return {status:200,body:copy(result)};
      }catch(e){return {status:e.status||400,body:{error:e.message,...(e.current?{current:e.current}:{})}};}
    }
    return {request,reset(){try{storage.removeItem(KEY);}catch{throw Error('Unable to reset browser storage.');}},key:KEY};
  }
  if(typeof module!=='undefined'&&module.exports){module.exports={createDemoApi,KEY};return;}
  const originalFetch=global.fetch.bind(global),script=document.currentScript?.src||location.href;
  const ready=originalFetch(new URL('demo-seed.json',script)).then(r=>{if(!r.ok)throw Error('Demo snapshot unavailable.');return r.json();}).then(seed=>createDemoApi(seed,global.localStorage));
  global.ATLAS_DEMO={ready,reset:async()=>{const api=await ready;api.reset();}};
  global.fetch=async function(input,options={}) {
    const u=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href);
    if(u.origin!==location.origin||!u.pathname.startsWith('/api/'))return originalFetch(input,options);
    try {const api=await ready,method=(options.method||input.method||'GET').toUpperCase();let body=options.body;if(body===undefined&&typeof input!=='string'&&!(input instanceof URL)&&method!=='GET')body=await input.clone().text();const result=api.request(u.pathname+u.search,method,body?JSON.parse(body):undefined);return new Response(JSON.stringify(result.body),{status:result.status,headers:{'Content-Type':'application/json'}});}catch(e){return new Response(JSON.stringify({error:e.message}),{status:503,headers:{'Content-Type':'application/json'}});}
  };
})(globalThis);
