export function publicHttps(value) {
  const u=new URL(value);
  if(u.protocol!=='https:'||u.username||u.password||u.port||!u.hostname.includes('.')||/^[\d.]+$/.test(u.hostname)||u.hostname.includes(':')||/(^|\.)(localhost|local|internal|test|invalid)$/.test(u.hostname))throw Error('Public HTTPS source required');
  return u.href;
}
export function extract(response) {
  if(response.status!=='completed')throw Error('Research response incomplete');
  const text=(response.output||[]).filter(x=>x.type==='message').flatMap(x=>x.content||[]).filter(x=>x.type==='output_text').map(x=>x.text).join('\n');
  const citations=new Set();
  for(const item of response.output||[])for(const c of item.content||[])for(const a of c.annotations||[])if(a.type==='url_citation'&&a.url)citations.add(publicHttps(a.url));
  const value=JSON.parse(text.replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,''));
  if(!Array.isArray(value.prospects)||value.prospects.length>5)throw Error('Research must return at most five prospects');
  return {prospects:value.prospects,citations};
}
export function validate(p,citations,runDate) {
  for(const k of ['name','sector','hq','website','workflow','businessNeed','openaiFit','buyerRole','nextStep','sourceUrl','sourceDate','title','locationEvidence'])if(typeof p[k]!=='string'||!p[k].trim()||p[k].length>4000)throw Error('Missing or invalid '+k);
  p.website=publicHttps(p.website);p.sourceUrl=publicHttps(p.sourceUrl);
  const domain=x=>new URL(x).hostname.toLowerCase().replace(/^www\./,'');
  if(domain(p.website)!==domain(p.sourceUrl))throw Error('Company primary source must match official company domain');
  if(!citations.has(p.sourceUrl))throw Error('Primary source was not cited by web search');
  const day=Date.parse(p.sourceDate),last=Date.parse(runDate+'T23:59:59Z');
  if(!/^\d{4}-\d{2}-\d{2}$/.test(p.sourceDate)||!Number.isFinite(day)||new Date(day).toISOString().slice(0,10)!==p.sourceDate||day>last||day<last-4*86400000)throw Error('Source outside recent research window');
  if(!['funding','contract','hiring','expansion','ai_adoption','partnership','product_launch'].includes(p.type))throw Error('Unsupported signal type');
  p.priority=['High','Medium','Low'].includes(p.priority)?p.priority:'Unassessed';
  return p;
}
