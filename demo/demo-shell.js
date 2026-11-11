'use strict';
document.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('reset-interview-demo').addEventListener('click',async()=>{
    if(!confirm('Reset your demo edits to the original 29-company snapshot?'))return;
    try{await window.ATLAS_DEMO.reset();location.reload();}catch(error){alert('Reset failed: '+error.message);}
  });
  const collect=document.getElementById('collectButton');
  if(collect){collect.disabled=true;collect.textContent='Scheduled intake runs in owner’s workspace';collect.title='This public demo shows a saved snapshot. It does not start the owner’s daily automation.';}
  const filter=document.getElementById('feedWindow');
  if(filter){filter.value='all';filter.dispatchEvent(new Event('change'));}
});
