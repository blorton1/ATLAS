document.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('cloud-sign-out')?.addEventListener('click',async()=>{await window.ATLAS_CLOUD.signOut();location.replace('/');});
  const button=document.getElementById('collectButton');
  if(button){button.disabled=true;button.textContent='Cloud intake · 7 AM Eastern';button.title='The scheduled worker adds new prospects automatically. Review the run log for completion or errors.';}
  const filter=document.getElementById('feedWindow');if(filter){filter.value='all';filter.dispatchEvent(new Event('change'));}
});
