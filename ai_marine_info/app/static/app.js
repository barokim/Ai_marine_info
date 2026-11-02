/* 모든 사용자·API 문자열은 textContent로 렌더링합니다. 토큰은 URL·로그에 쓰지 않습니다. */
'use strict';
const $ = id => document.getElementById(id);
const page = document.body.dataset.page;
const TOKEN = 'ai-marine.access';
const SELECTED = 'ai-marine.region';
let user = null, catalog = null, selectionRevision = 0, authUnavailable = false;
const privatePages = new Set(['board', 'records', 'history', 'photo']);
const dateText = value => value ? new Date(value).toLocaleString('ko-KR', {timeZone:'Asia/Seoul'}) : '—';
const timeText = value => value ? new Date(value).toLocaleTimeString('ko-KR', {timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',hour12:false}) : '—';
const today = () => new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const valueText = (value, unit='') => value === null || value === undefined ? '—' : `${value}${unit}`;
function node(tag, text, className) { const el=document.createElement(tag); if(text!==undefined) el.textContent=text; if(className) el.className=className; return el; }
function text(id, value) { if($(id)) $(id).textContent=value; }
function error(message) { const target=$('page-error'); target.textContent=message; target.hidden=false; }
function clearError() { $('page-error').hidden=true; }
function toast(message) { const target=$('global-notice'); target.textContent=message; target.hidden=false; clearTimeout(toast.timer); toast.timer=setTimeout(()=>target.hidden=true,5000); }
function sessionToken() { return sessionStorage.getItem(TOKEN); }
function clearSession() { sessionStorage.removeItem(TOKEN); user=null; renderAccount(); if($('latest-section')) $('latest-section').hidden=true; }
function requireLogin(destination=location.pathname+location.hash) {
  sessionStorage.setItem('ai-marine.return', destination);
  location.assign('/login?reason=required');
}
async function api(path, options={}) {
  const headers=new Headers(options.headers || {});
  const publicQuery=path.startsWith('/api/dashboard') || path.startsWith('/api/species');
  const token=authUnavailable && publicQuery ? null : sessionToken(); if(token) headers.set('Authorization', `Bearer ${token}`);
  let body=options.body;
  if(body!==undefined && !(body instanceof FormData)) {headers.set('Content-Type','application/json');body=JSON.stringify(body);}
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(), path==='/api/analyze'?90000:65000);
  let response, data;
  try {
    response=await fetch(path,{method:options.method||'GET',headers,body,signal:controller.signal,cache:'no-store',credentials:'omit'});
    data=response.status===204 ? null : options.blob && response.ok ? await response.blob() : await response.json();
  }
  catch(e) { throw new Error(e.name==='AbortError'?'응답 시간이 초과되었습니다. 잠시 후 다시 시도하세요.':'서버에 연결할 수 없습니다. 연결 상태를 확인해 주세요.'); }
  finally { clearTimeout(timer); }
  if(!response.ok) {
    if(response.status===401 && token) clearSession();
    const err=new Error(typeof data?.detail==='string'?data.detail:'입력 내용을 확인해 주세요.'); err.status=response.status; throw err;
  }
  return data;
}
async function guarded(task) {
  clearError();
  try { return await task(); }
  catch(e) { if(e.status===401 && privatePages.has(page)) requireLogin(); else error(e.message); }
}
function submit(form, task) {
  form.addEventListener('submit', async event=>{
    event.preventDefault(); if(!form.reportValidity()) return;
    const button=form.querySelector('[type="submit"]'); button.disabled=true;
    try { await guarded(task); } finally {button.disabled=false;}
  });
}
function action(textValue, callback, className='secondary') {const button=node('button',textValue,className);button.type='button';button.addEventListener('click',()=>guarded(callback));return button;}
function empty(target, label='아직 표시할 자료가 없습니다.') {target.replaceChildren(node('p',label,'empty'));}
function renderAccount() {
  const target=$('account-links'); target.replaceChildren();
  if(user) {
    target.append(node('span',`${user.name}님`));
    target.append(action('로그아웃',async()=>{
      let message='로그아웃했습니다.';
      try { await api('/auth/logout',{method:'POST'}); } catch(e) { message='브라우저 로그인 정보를 지웠습니다. 서버 로그아웃 처리는 확인하지 못했습니다.'; }
      clearSession(); sessionStorage.setItem('ai-marine.notice',message); location.assign('/');
    }));
  } else {
    for(const [label,path] of [['로그인','/login'],['회원가입','/signup']]) {const link=node('a',label);link.href=path;target.append(link);}
  }
}
async function currentUser() {
  if(!sessionToken()) return;
  try {user=await api('/me');}
  catch(e) {if(e.status!==401) {if(privatePages.has(page))throw e;authUnavailable=true;toast('회원 확인이 지연되어 공개 정보만 표시합니다.');}}
  renderAccount();
}
function authPage() {
  const form=$('auth-form'); if(!form) return;
  if(page==='login' && new URLSearchParams(location.search).get('reason')==='required') text('auth-hint','이 서비스는 로그인이 필요합니다. 로그인 후 이용해 주세요.');
  // 이전 방식의 URL 토큰이 들어오면 사용하지 않고 즉시 주소에서 제거합니다.
  if(location.hash || location.search.includes('token')) {history.replaceState(null,'',location.pathname);toast('메일의 인증 코드를 직접 입력해 주세요.');}
  submit(form, async()=>{
    if($('password-confirm') && $('password').value!==$('password-confirm').value) throw new Error('비밀번호 확인이 일치하지 않습니다.');
    const body={email:$('email').value.trim()};
    if($('password')) body.password=$('password').value;
    if($('name')) body.name=$('name').value.trim();
    if($('otp')) body.token=$('otp').value.trim();
    const routes={login:'login',signup:'signup',forgot:'forgot-password',reset:'reset-password',confirm:'confirm-email'};
    const result=await api(`/auth/${routes[page]}`,{method:'POST',body});
    if($('password')) $('password').value=''; if($('password-confirm')) $('password-confirm').value=''; if($('otp')) $('otp').value='';
    if(page==='login') {
      sessionStorage.setItem(TOKEN,result.access_token);
      const destination=sessionStorage.getItem('ai-marine.return') || '/';sessionStorage.removeItem('ai-marine.return');
      // 외부 URL로 이동시키는 open redirect를 허용하지 않습니다.
      const allowed=new Set(['/','/board','/records','/history','/photo','/tides','/ocean','/species']);
      const url=new URL(destination,location.origin);
      location.assign(url.origin===location.origin && allowed.has(url.pathname)?url.pathname+url.hash:'/');
    } else {text('auth-result',result.message);$('auth-result').hidden=false;if(page==='reset') clearSession();}
  });
}
function option(value,label) {const el=node('option',label);el.value=value;return el;}
function resetMarine() {
  selectionRevision++;
  $('marine-result')?.setAttribute('aria-busy','false');
  for(const id of ['high-time','low-time','water-temperature','wave-max']) text(id,'—');
  text('high-height','조위 — cm');text('low-height','조위 — cm');text('observation-time','수신 시각 —');text('data-date','');
  text('tide-note','지역·날짜를 선택하고 조회해 주세요.');text('observation-note','조회 대기 중');text('forecast-note','');
  for(const id of ['tide-rows','observation-values','forecast-rows']) $(id)?.replaceChildren();
  if($('station-notice')) $('station-notice').hidden=true;
  text('area-title','바다 정보');
}
function saveSelection() {sessionStorage.setItem(SELECTED,JSON.stringify({province:$('province').value,city:$('city').value,station:$('station')?.value||''}));}
function updateStations(preferred='') {
  const select=$('station'); if(!select) return;
  select.replaceChildren();
  const own=catalog.stations.filter(s=>s.city_id===$('city').value);
  const label=s=>`${s.name} · ${[s.tides?'물때':'',s.observations?'실측':''].filter(Boolean).join('·')}`;
  if(own.length) {const group=node('optgroup');group.label='선택 지역의 지점';for(const s of own)group.append(option(s.id,label(s)));select.append(group);}
  else select.append(option('','등록된 지역 관측소 없음 · 모델 예보만 조회'));
  const others=node('optgroup');others.label='다른 지역 지점 · 위치를 확인하고 직접 선택';
  const sorted=catalog.stations.filter(s=>s.city_id!==$('city').value).sort((a,b)=>Number(b.province_id===$('province').value)-Number(a.province_id===$('province').value));
  for(const s of sorted) {const c=catalog.cities.find(c=>c.id===s.city_id);const p=catalog.provinces.find(p=>p.id===s.province_id);others.append(option(s.id,`${p.name} ${c.name} / ${label(s)}`));}
  select.append(others);select.disabled=false;
  if(preferred && catalog.stations.some(s=>s.id===preferred)) select.value=preferred;
  stationNotice();
}
function stationNotice() {
  const station=catalog.stations.find(s=>s.id===$('station')?.value);
  text('region-notice',!$('station')?'관찰한 지역과 날짜를 선택하세요.':!station?'지역 실측 자료는 미제공으로 표시합니다. 필요하면 다른 지역 지점을 직접 선택하세요.':station.city_id!==$('city').value?'다른 지역의 관측소를 선택했습니다. 결과에 실제 관측 지역을 표시합니다.':'물때와 실측 제공 여부는 지점·날짜·API 상태에 따라 달라집니다.');
}
function updateCities(preferred='') {
  const target=$('city');target.replaceChildren();
  for(const c of catalog.cities.filter(c=>c.province_id===$('province').value))target.append(option(c.id,c.name));
  target.disabled=false;if(preferred && [...target.options].some(o=>o.value===preferred))target.value=preferred;
  updateStations();
}
async function setupRegions() {
  catalog=await api('/api/regions');$('province').replaceChildren();
  for(const p of catalog.provinces)$('province').append(option(p.id,p.name));
  let saved={};try {saved=JSON.parse(sessionStorage.getItem(SELECTED)||'{}');}catch{}
  $('province').value=catalog.provinces.some(p=>p.id===saved.province)?saved.province:'p02';
  updateCities(saved.city);updateStations(saved.station);$('target-date').value=today();
  $('province').addEventListener('change',()=>{resetMarine();updateCities();saveSelection();});
  $('city').addEventListener('change',()=>{resetMarine();updateStations();saveSelection();});
  $('station')?.addEventListener('change',()=>{resetMarine();stationNotice();saveSelection();});
  $('target-date').addEventListener('change',resetMarine);
  if(page!=='records') {submit($('region-form'),loadMarine);await loadMarine();}
  else $('region-form').addEventListener('submit',event=>event.preventDefault());
}
function tableRow(values) {const row=node('tr');for(const v of values)row.append(node('td',v));return row;}
async function loadMarine() {
  resetMarine();const revision=selectionRevision;saveSelection();$('marine-result').setAttribute('aria-busy','true');
  const query=new URLSearchParams({city_id:$('city').value,target_date:$('target-date').value});if($('station').value)query.set('station_id',$('station').value);
  let data;
  try {data=await api('/api/dashboard?'+query);}
  catch(e) {if(e.status===401)data=await api('/api/dashboard?'+query);else throw e;}
  finally {if(revision===selectionRevision)$('marine-result').setAttribute('aria-busy','false');}
  if(revision!==selectionRevision)return;
  text('area-title',data.selection.requested_area);text('data-date',`${data.target_date} · 한국 시간`);
  const station=data.station;
  text('station-notice',station?`물때·실측 지점: ${data.selection.station_area} ${station.name}${data.selection.is_other_area?' — 선택한 시·군·구와 다른 지역의 자료입니다.':''}`:'등록된 지역 관측소가 없어 물때·실측 자료를 표시하지 않습니다.');$('station-notice').hidden=false;
  for(const [kind,prefix] of [['high','high'],['low','low']]) {const event=data.tides.events.find(e=>e.kind===kind);text(prefix+'-time',timeText(event?.time));text(prefix+'-height',`조위 ${valueText(event?.height_cm,' cm')}`);}
  text('water-temperature',valueText(data.observations.water_temperature_c,' °C'));text('observation-time',dateText(data.observations.observed_at));
  const waves=data.marine.points.map(p=>p.wave_height_m).filter(v=>typeof v==='number');text('wave-max',waves.length?Math.max(...waves)+' m':'—');
  text('tide-note',data.tides.note);text('observation-note',data.observations.note);
  for(const event of data.tides.events)$('tide-rows').append(tableRow([event.kind==='high'?'만조':'간조',timeText(event.time),`${event.height_cm} cm`]));
  if(!data.tides.events.length)$('tide-rows').append(tableRow(['자료 없음','—','—']));
  for(const [key,label,unit] of [['water_temperature_c','수온',' °C'],['tide_height_cm','조위',' cm'],['wind_speed_ms','풍속',' m/s'],['air_temperature_c','기온',' °C'],['salinity_psu','염분',' psu'],['air_pressure_hpa','기압',' hPa'],['wind_direction_deg','풍향',' °'],['max_gust_speed_ms','최대 순간 풍속',' m/s']]) {const group=node('div');group.append(node('dt',label),node('dd',valueText(data.observations[key],unit)));$('observation-values').append(group);}
  if($('forecast-rows')) {text('forecast-note',`${data.marine.note} ${data.coordinate_note} (${data.city.latitude}, ${data.city.longitude})`);for(const p of data.marine.points)$('forecast-rows').append(tableRow([timeText(p.time),valueText(p.wave_height_m),valueText(p.sea_surface_temperature_c)]));}
}
function postItem(post,open) {const item=node('article',undefined,'post-item');const copy=node('div');copy.append(action(post.title,()=>open(post.id),'title-button'),node('p',`${post.author_name} · ${dateText(post.created_at)}`));item.append(copy,node('span','읽기 ↗'));return item;}
async function latestPosts() {
  if(!user)return;
  const result=await api('/posts?limit=3');$('latest-section').hidden=false;const target=$('latest-posts');target.replaceChildren();
  for(const post of result.items)target.append(postItem(post,id=>{sessionStorage.setItem('ai-marine.post',id);location.assign('/board');}));
  if(!result.items.length)empty(target,'첫 바다 이야기를 남겨보세요.');
}
function board() {
  let offset=0, editing=null, selected=null;
  async function list() {
    const result=await api(`/posts?offset=${offset}&limit=10`);const target=$('post-list');target.replaceChildren();
    if(!result.items.length)empty(target,'등록된 게시글이 없습니다.');
    for(const post of result.items)target.append(postItem(post,open));
    text('post-page',`${Math.floor(offset/10)+1} 페이지 · 총 ${result.total??result.items.length}건`);$('post-prev').disabled=offset===0;$('post-next').disabled=offset+10>=(result.total??offset+result.items.length);
  }
  async function open(id) {selected=await api('/posts/'+id);text('post-title',selected.title);text('post-content',selected.content);text('post-meta',`${selected.author_name} · ${dateText(selected.created_at)} · 수정 ${dateText(selected.updated_at)}`);$('post-detail').hidden=false;$('post-actions').hidden=selected.author_id!==user.id;$('post-detail').scrollIntoView({block:'start'});}
  function reset() {editing=null;$('post-form').reset();text('write-heading','새 글 작성');}
  submit($('post-form'),async()=>{const result=await api(editing?'/posts/'+editing:'/posts',{method:editing?'PUT':'POST',body:{title:$('post-input-title').value,content:$('post-input-content').value}});reset();offset=0;await list();await open(result.id);toast('게시글을 저장했습니다.');});
  $('post-edit').addEventListener('click',()=>{if(!selected)return;editing=selected.id;$('post-input-title').value=selected.title;$('post-input-content').value=selected.content;text('write-heading','게시글 수정');$('write').scrollIntoView();$('post-input-title').focus();});
  $('post-delete').addEventListener('click',()=>guarded(async()=>{if(!selected || !confirm('이 게시글을 삭제할까요?'))return;await api('/posts/'+selected.id,{method:'DELETE'});selected=null;$('post-detail').hidden=true;reset();offset=0;await list();toast('게시글을 삭제했습니다.');}));
  $('post-cancel').addEventListener('click',reset);
  $('post-prev').addEventListener('click',()=>guarded(async()=>{offset=Math.max(0,offset-10);await list();}));$('post-next').addEventListener('click',()=>guarded(async()=>{offset+=10;await list();}));
  return list().then(async()=>{const id=sessionStorage.getItem('ai-marine.post');sessionStorage.removeItem('ai-marine.post');if(id && /^[0-9a-f-]{36}$/i.test(id))await open(id);});
}
function speciesPage() {
  let currentPage=1, lastQuery=null;
  async function search() {
    if(!lastQuery)return;
    const query=new URLSearchParams({...lastQuery,page:currentPage});const result=await api('/api/species?'+query);const target=$('species-list');target.replaceChildren();$('species-detail').hidden=true;
    text('species-note',`${result.source_name || '해양생물 DB'} · ${result.total_count==null?'현재 페이지 '+result.items.length+'건':'전체 '+result.total_count+'건'} ${result.note||''}`);
    for(const item of result.items) {const card=node('article',undefined,'panel species-card');card.append(node('h3',item.korean_name||item.name||item.scientific_name||'이름 미제공'),node('p',item.scientific_name||'학명 미제공','muted'));if(item.description)card.append(node('p',item.description));if(result.provider==='worms')card.append(action('분류·분포 상세',async()=>{const data=await api('/api/species/'+item.id);const detail=$('species-detail');detail.replaceChildren(node('h2',data.species.scientific_name),node('p',`분류 상태: ${data.species.taxonomic_status||'미제공'} / 인정 학명: ${data.species.accepted_name||'미제공'}`),node('p',Object.entries(data.species.taxonomy).map(([k,v])=>`${k}: ${v}`).join(' · ')),node('p',data.vernaculars.map(n=>`${n.name} (${n.language})`).join(', ')||'일반명 미제공'),node('p',data.distributions.join(', ')||'분포 미제공'),node('p',data.note));const link=node('a','WoRMS 원문 보기 ↗');link.href=`https://www.marinespecies.org/aphia.php?p=taxdetails&id=${item.id}`;link.target='_blank';link.rel='noopener noreferrer';detail.append(link);detail.hidden=false;detail.scrollIntoView();}));target.append(card);}
    if(!result.items.length)empty(target,'검색 결과가 없습니다. 다른 이름으로 검색해 보세요.');
    text('species-page',`${currentPage} 페이지`);$('species-prev').disabled=currentPage===1;$('species-next').disabled=result.provider!=='mbris'||!result.has_more;
  }
  submit($('species-form'),async()=>{lastQuery={q:$('species-query').value.trim(),provider:$('provider').value};currentPage=1;await search();});
  $('species-prev').addEventListener('click',()=>guarded(async()=>{currentPage=Math.max(1,currentPage-1);await search();}));$('species-next').addEventListener('click',()=>guarded(async()=>{currentPage++;await search();}));
}
function photoPage() {
  let previewURL=null;
  $('photo').addEventListener('change',()=>{if(previewURL)URL.revokeObjectURL(previewURL);const file=$('photo').files[0];$('photo-preview').hidden=!file;if(file){previewURL=URL.createObjectURL(file);$('photo-preview').src=previewURL;}});
  submit($('photo-form'),async()=>{const file=$('photo').files[0];if(!file || file.size>10*1024*1024)throw new Error('10 MiB 이하의 사진을 선택하세요.');const body=new FormData();body.append('file',file);body.append('consent',String($('consent').checked));text('photo-status','사진을 분석하고 있습니다. 잠시 기다려 주세요.');let result;try{result=await api('/api/analyze',{method:'POST',body});}finally{text('photo-status','');}const target=$('photo-result');target.replaceChildren(node('h2','분석 결과'),node('p',result.identification.explanation));for(const candidate of result.identification.candidates){const card=node('article',undefined,'panel');card.append(node('h3',candidate.common_name_ko+' · '+candidate.scientific_name),node('p',`외형 일치 수준: ${{low:'낮음',medium:'중간',high:'높음'}[candidate.visual_match]} (정확도 확률이 아닙니다)`),node('p',candidate.visible_features.join(' · ')),node('p',candidate.distinguishing_limits.join(' · ')));target.append(card);}target.append(node('p',result.database_note),node('p','학명 대조: '+(result.database_matches.map(s=>s.scientific_name).join(', ')||'일치 자료 없음')),node('p',result.specimen_edibility,'notice'));});
}
function recordsPage() {
  let editing=null, offset=0;
  function reset(){editing=null;$('record-form').reset();text('record-heading','새 관찰 기록');}
  async function list(){const rows=await api(`/api/records?offset=${offset}&limit=10`);const target=$('record-list');target.replaceChildren();for(const row of rows){const city=catalog.cities.find(c=>c.id===row.city);const card=node('article',undefined,'record-card');card.append(node('h3',(row.favorite?'★ ':'')+row.title),node('p',`${city?.name||row.city} · ${row.observed_on}`,'muted'),node('p',row.note,'prewrap'));const buttons=node('div',undefined,'actions');buttons.append(action('수정',()=>{editing=row.id;$('record-title').value=row.title;$('record-note').value=row.note;$('record-favorite').checked=row.favorite;$('province').value=row.province;updateCities(row.city);$('target-date').value=row.observed_on;text('record-heading','관찰 기록 수정');$('record-title').focus();}),action('삭제',async()=>{if(!confirm('이 관찰 기록을 삭제할까요?'))return;await api('/api/records/'+row.id,{method:'DELETE'});if(editing===row.id)reset();offset=0;await list();},'danger'));card.append(buttons);target.append(card);}if(!rows.length)empty(target,'아직 관찰 기록이 없습니다.');$('record-prev').disabled=offset===0;$('record-next').disabled=rows.length<10;text('record-page',`${offset/10+1} 페이지`);}
  submit($('record-form'),async()=>{if(!$('region-form').reportValidity())return;const body={title:$('record-title').value,note:$('record-note').value,favorite:$('record-favorite').checked,province:$('province').value,city:$('city').value,observed_on:$('target-date').value};await api(editing?'/api/records/'+editing:'/api/records',{method:editing?'PUT':'POST',body});reset();offset=0;await list();toast('관찰 기록을 저장했습니다.');});$('record-cancel').addEventListener('click',reset);
  $('record-prev').addEventListener('click',()=>guarded(async()=>{offset=Math.max(0,offset-10);await list();}));$('record-next').addEventListener('click',()=>guarded(async()=>{offset+=10;await list();}));return list();
}
function historyPage(){let offset=0,imageURL=null;async function open(id){const data=await api('/api/history/'+id);text('history-title',data.title);text('history-date',`저장 시각: ${dateText(data.created_at)} · 현재 자료가 아닙니다.`);text('history-json',JSON.stringify(data.result,null,2));$('history-image').hidden=true;if(imageURL)URL.revokeObjectURL(imageURL);if(data.has_image){const blob=await api('/api/history/'+id+'/image',{blob:true});imageURL=URL.createObjectURL(blob);$('history-image').src=imageURL;$('history-image').hidden=false;}$('history-detail').hidden=false;$('history-detail').scrollIntoView();}async function list(){const rows=await api(`/api/history?offset=${offset}&limit=10`);const target=$('history-list');target.replaceChildren();for(const row of rows){const item=node('article',undefined,'post-item');const info=node('div');info.append(action(row.title,()=>open(row.id),'title-button'),node('p',dateText(row.created_at)));item.append(info,action('삭제',async()=>{if(!confirm('이 조회 이력과 연결된 사진을 삭제할까요?'))return;await api('/api/history/'+row.id,{method:'DELETE'});$('history-detail').hidden=true;offset=0;await list();},'secondary'));target.append(item);}if(!rows.length)empty(target,'저장된 조회 이력이 없습니다.');$('history-prev').disabled=offset===0;$('history-next').disabled=rows.length<10;text('history-page',`${offset/10+1} 페이지`);}$('history-prev').addEventListener('click',()=>guarded(async()=>{offset=Math.max(0,offset-10);await list();}));$('history-next').addEventListener('click',()=>guarded(async()=>{offset+=10;await list();}));return list();}
async function init(){
  $('menu-toggle').addEventListener('click',()=>{const open=$('main-nav').classList.toggle('open');$('menu-toggle').setAttribute('aria-expanded',String(open));});
  document.querySelectorAll('[data-member]').forEach(link=>link.addEventListener('click',event=>{if(!user){event.preventDefault();requireLogin(link.getAttribute('href'));}}));
  authPage();const notice=sessionStorage.getItem('ai-marine.notice');if(notice){toast(notice);sessionStorage.removeItem('ai-marine.notice');}
  await currentUser();
  if(privatePages.has(page)){if(!user){requireLogin();return;}$('member-content').hidden=false;}
  if($('province'))await setupRegions();
  if(page==='home')await latestPosts();if(page==='board')await board();if(page==='species')speciesPage();if(page==='photo')photoPage();if(page==='records')await recordsPage();if(page==='history')await historyPage();
}
guarded(init);
