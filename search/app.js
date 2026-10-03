const $ = id => document.getElementById(id);
const input = $('query'), list = $('results'), preview = $('preview');
const initialPreview = preview.innerHTML;
const suggestions = ['Artificial intelligence', 'Quantum mechanics', 'Roman Empire', 'James Webb Space Telescope', 'Octopus'];
let results = [], selected = -1, queryVersion = 0, articleVersion = 0, timer, controller, articleController, composing = false;
const cache = new Map();
function marked(text) {
  const fragment = document.createDocumentFragment();
  text.split('\u0001').forEach((part, i) => {
    if (!i) return fragment.append(document.createTextNode(part));
    const [match, ...rest] = part.split('\u0002');
    const mark = document.createElement('mark'); mark.textContent = match;
    fragment.append(mark, document.createTextNode(rest.join('')));
  });
  return fragment;
}
function idle() {
  results = suggestions.map(title => ({title, suggestion:true, snippet:'Explore this topic'}));
  $('result-label').textContent = 'START EXPLORING';
  $('empty').hidden = true; $('timing').textContent = 'Ready when you are';
  preview.innerHTML = initialPreview; render();
}
function render() {
  list.replaceChildren(); selected = -1; input.removeAttribute('aria-activedescendant');
  results.forEach((r, i) => {
    const row = document.createElement('div'); row.className = 'result'; row.id = 'result-' + i;
    row.setAttribute('role','option'); row.setAttribute('aria-selected','false');
    const icon = document.createElement('span'); icon.className = 'result-icon'; icon.textContent = r.suggestion ? '↗' : '▤';
    const copy = document.createElement('div'); copy.className = 'result-copy';
    const title = document.createElement('div'); title.className = 'result-title'; title.textContent = r.title;
    const snippet = document.createElement('div'); snippet.className = 'snippet'; snippet.append(marked(r.snippet));
    copy.append(title, snippet); row.append(icon,copy); row.onclick = () => { select(i); if(r.suggestion) activate(); else if(matchMedia('(max-width:700px)').matches) activate(); }; list.append(row);
  });
  if(results.length) select(0);
}
async function select(i) {
  selected = i;
  [...list.children].forEach((row, n) => row.setAttribute('aria-selected', String(n===i)));
  input.setAttribute('aria-activedescendant','result-'+i);
  list.children[i]?.scrollIntoView({block:'nearest'});
  const r = results[i]; if(!r || r.suggestion) return;
  const version = ++articleVersion; articleController?.abort();
  articleController = new AbortController();
  preview.replaceChildren(); const loading = document.createElement('p'); loading.textContent = 'Loading article…'; preview.append(loading);
  try {
    let article = cache.get(r.id);
    if(!article) {
      const response = await fetch('/api/article/'+r.id, {signal:articleController.signal});
      if(!response.ok) throw new Error('Could not load this article. Select it to retry.');
      article = await response.json(); if(cache.size >= 40) cache.delete(cache.keys().next().value); cache.set(r.id,article);
    }
    if(version !== articleVersion) return;
    preview.replaceChildren(); preview.scrollTop = 0;
    const tag = document.createElement('div'); tag.className = 'article-eyebrow'; tag.textContent = 'WIKIPEDIA / ARTICLE';
    const h = document.createElement('h2'); h.textContent = article.title;
    const source = document.createElement('a'); source.className = 'source'; source.textContent = 'Open original ↗'; source.href = article.url; source.target = '_blank'; source.rel = 'noopener noreferrer';
    preview.append(tag,h,source);
    article.text.split(/\n\s*\n/).forEach(t => {const p=document.createElement('p');p.textContent=t;preview.append(p);});
  } catch(e) {if(e.name!=='AbortError' && version===articleVersion) preview.textContent=e.message;}
}
function activate() {
  const r=results[selected]; if(!r) return;
  if(r.suggestion) {input.value=r.title; schedule(0);return;}
  document.querySelector('.palette').classList.add('reading'); preview.tabIndex=-1;preview.focus();
}
function schedule(delay=80) {
  clearTimeout(timer);controller?.abort();articleController?.abort(); ++articleVersion;
  const version=++queryVersion; selected=-1; results=[]; list.replaceChildren();input.removeAttribute('aria-activedescendant');
  document.querySelector('.palette').classList.remove('reading');
  if(composing) return;
  const q=input.value.trim();
  if(!q){idle();return;}
  $('empty').hidden=true;$('result-label').textContent='SEARCHING';$('timing').textContent='Searching…';preview.innerHTML=initialPreview;
  timer=setTimeout(()=>run(q,version),delay);
}
async function run(q,version) {
  controller=new AbortController();const start=performance.now();
  try {
    const response=await fetch('/api/search?q='+encodeURIComponent(q), {signal:controller.signal});
    const data=await response.json();if(version!==queryVersion)return;
    if(!response.ok)throw new Error(data.error || 'Search is unavailable. Try again.');
    const elapsed=Math.round(performance.now()-start);
    results=data.results;render();$('result-label').textContent=results.length===30?'TOP 30 RESULTS':results.length+' RESULTS';
    $('timing').textContent=elapsed+' ms round trip · '+data.server_ms+' ms search';
    $('empty').hidden=!!results.length;$('empty').textContent='No matches. Try fewer words or a different spelling.';
  } catch(e) {
    if(e.name==='AbortError'||version!==queryVersion)return;
    results=[];render();$('empty').hidden=false;$('empty').textContent=e.message;$('timing').textContent='Connection interrupted';$('result-label').textContent='SEARCH UNAVAILABLE';
  }
}
input.addEventListener('input',()=>schedule());
input.addEventListener('compositionstart',()=>{composing=true;clearTimeout(timer);controller?.abort();++queryVersion;});
input.addEventListener('compositionend',()=>{composing=false;schedule();});
input.addEventListener('keydown',e=>{
  if(e.isComposing)return;
  if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();if(results.length)select((selected+(e.key==='ArrowDown'?1:-1)+results.length)%results.length);}
  if(e.key==='Enter'){e.preventDefault();activate();}
});
document.addEventListener('keydown',e=>{
  if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();input.focus();input.select();}
  if(e.key==='Escape'){
    if(document.querySelector('.palette').classList.contains('reading')){document.querySelector('.palette').classList.remove('reading');input.focus();}
    else {input.value='';schedule(0);input.focus();}
  }
});
fetch('/api/stats').then(r=>{if(!r.ok)throw Error();return r.json();}).then(s=>{
  $('corpus').textContent=s.articles.toLocaleString()+' articles';
  $('library-size').textContent=s.articles.toLocaleString()+' articles · '+Math.round(s.text_bytes/1e6)+' MB of searchable text';
}).catch(()=>{$('corpus').textContent='Library unavailable';$('library-size').textContent='Refresh to reconnect';});
idle();
