const $ = id => document.getElementById(id);
async function api(path, method='GET') {
  const r = await fetch('/api/'+path,{method,headers:{'X-CloudTransfer':'1'}});
  const data = await r.json(); if(!r.ok) throw new Error(data.error || 'Falha na operação'); return data;
}
function show(id, items, format) {
  const list=$(id); list.replaceChildren();
  if(!items.length){const li=document.createElement('li');li.textContent='Nenhum arquivo encontrado.';list.append(li);}
  for(const item of items){const li=document.createElement('li');li.textContent=format(item);if(item.status)li.className=item.status;list.append(li);}
}
async function load(path, prefix){const items=await api(path);$(prefix+'Count').textContent=items.length;show(prefix+'List',items,f=>f.name);}
async function run(fn){const buttons=document.querySelectorAll('button');buttons.forEach(b=>b.disabled=true);$('notice').textContent='Processando...';try{await fn();$('notice').textContent='Operação concluída.';}catch(e){$('notice').textContent=e.message;}finally{buttons.forEach(b=>b.disabled=false);}}
$('source').onclick=()=>run(()=>load('origem','source'));
$('target').onclick=()=>run(()=>load('destino','target'));
$('migrate').onclick=()=>run(async()=>{const data=await api('migrar','POST');show('results',data.results,f=>`${f.name} — ${f.status}: ${f.message}`);$('successCount').textContent=data.results.filter(f=>f.status==='sucesso').length;await load('destino','target');});
