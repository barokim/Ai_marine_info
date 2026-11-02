/* 화면 코드는 FastAPI를 fetch로 호출합니다. 학습의 중심은 Python 파일 3개입니다. */
const $ = (id) => document.getElementById(id);
let editingId = null;
let records = [];
let previewUrl = null;
let historyOffset = 0;
let imageConfigured = false;
let selectedPhoto = null;
const regionNames = {incheon: "인천 연안", busan: "부산 연안", jeju: "제주 연안"};
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const clock = (value) => new Intl.DateTimeFormat("ko-KR", {timeZone:"Asia/Seoul", hour:"2-digit", minute:"2-digit", hour12:false}).format(new Date(value));
const number = (value, digits=1) => Number.isFinite(value) ? value.toFixed(digits) : "정보 없음";

async function api(path, options = {}, inspect = true) {
  const response = await fetch(path, options);
  const data = response.status === 204 ? null : await response.json();
  if(inspect){
    $("last-request").textContent = `${options.method || "GET"} ${path} → ${response.status}`;
    $("api-json").textContent = JSON.stringify(data, null, 2) ?? "204 No Content";
  }
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(Array.isArray(detail) ? detail.map((e) => `${e.loc?.join(".")}: ${e.msg}`).join(" / ") : detail || "요청에 실패했습니다.");
  }
  return data;
}

function drawChart(points) {
  const valid = points.filter((p) => p.wave_height_m !== null);
  if (!valid.length) {
    $("wave-chart").textContent = "조회일의 파고 예보값이 없습니다.";
    return;
  }
  const width=600, height=175, left=35, right=12, top=10, bottom=27;
  const ceiling = Math.max(1, Math.ceil(Math.max(...valid.map((p) => p.wave_height_m)) * 2) / 2);
  const x = (i) => left + i / Math.max(1, points.length - 1) * (width-left-right);
  const y = (v) => top + (1-v/ceiling)*(height-top-bottom);
  // 누락값은 0으로 바꾸지 않고 선을 끊어서 표시합니다.
  const segments=[];
  let current=[];
  points.forEach((p,i) => {
    if (p.wave_height_m === null) {if(current.length) segments.push(current); current=[];}
    else current.push([x(i),y(p.wave_height_m)]);
  });
  if(current.length) segments.push(current);
  const grids = [0,.5,1].map((part) => {
    const py=y(ceiling*part);
    return `<line x1="${left}" x2="${width-right}" y1="${py}" y2="${py}" stroke="#edf2f1"/><text x="0" y="${py+4}">${(ceiling*part).toFixed(1)}</text>`;
  }).join("");
  const lines=segments.map((segment)=>{
    const path=segment.map((p,i)=>`${i?"L":"M"}${p[0]},${p[1]}`).join(" ");
    const area=`${path} L${segment.at(-1)[0]},${height-bottom} L${segment[0][0]},${height-bottom} Z`;
    return `<path d="${area}" fill="url(#sea-fill)"/><path d="${path}" fill="none" stroke="#188f8a" stroke-width="2.5"/>`;
  }).join("");
  const labels=[...new Set([0, Math.floor(points.length/3), Math.floor(points.length*2/3), points.length-1])].map((i)=>`<text x="${x(i)}" y="${height-4}" text-anchor="middle">${escapeHtml(clock(points[i].time))}</text>`).join("");
  $("wave-chart").innerHTML=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="한국 시간 기준 시간별 파고, 단위 미터"><defs><linearGradient id="sea-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b6e1d5" stop-opacity=".7"/><stop offset="1" stop-color="#ecf6f1" stop-opacity=".2"/></linearGradient></defs>${grids}${lines}${labels}</svg>`;
}

async function loadDashboard() {
  const params = new URLSearchParams({region:$("region").value, target_date:$("target-date").value});
  $("error").hidden=true;
  $("query-button").disabled=true;
  $("query-button").textContent="조회하는 중…";
  $("dashboard-content").setAttribute("aria-busy","true");
  try {
    const data = await api(`/api/dashboard?${params}`);
    $("dashboard-content").hidden=false;
    $("region-heading").textContent=`${data.region.name}의 바다`;
    $("query-date").textContent=`${data.target_date} · 한국 시간 기준`;
    const high = data.tides.events.find((e)=>e.kind==="high");
    const low = data.tides.events.find((e)=>e.kind==="low");
    $("high-time").textContent=high ? clock(high.time) : "정보 없음";
    $("low-time").textContent=low ? clock(low.time) : "정보 없음";
    $("high-height").textContent=high ? `조위 ${high.height_cm} cm · 공식 예보` : data.tides.note;
    $("low-height").textContent=low ? `조위 ${low.height_cm} cm · 공식 예보` : data.tides.note;
    const waves=data.marine.points.map((p)=>p.wave_height_m).filter((v)=>v!==null);
    const temps=data.marine.points.map((p)=>p.sea_surface_temperature_c).filter((v)=>v!==null);
    $("wave-max").textContent=number(waves.length ? Math.max(...waves) : null);
    $("temperature-avg").textContent=number(temps.length ? temps.reduce((a,b)=>a+b,0)/temps.length : null);
    document.querySelectorAll(".marine-badge").forEach((badge)=>setBadge(badge,data.marine.status,"모델 예보"));
    document.querySelectorAll(".tide-badge").forEach((badge)=>setBadge(badge,data.tides.status,"공식 예보"));
    $("data-notice").innerHTML=`<span class="notice-icon">i</span><p><strong>실제 API 조회 · SQLite 이력 #${data.history_id}</strong> 물때는 공식 예보, 관측소 현황은 실측, 파고 차트는 모델 예보입니다. 각 데이터의 시각과 출처를 확인하세요.</p>`;
    $("marine-source").textContent=`${data.marine.source_name} · 조회 ${clock(data.marine.fetched_at)} KST · ${data.marine.note}`;
    setBadge($("tide-status"),data.tides.status,"공식 예보");
    $("tide-source").textContent=`${data.tides.source_name} · ${data.tides.station_name} (${data.tides.station_code}) · ${data.tides.note}`;
    $("tide-list").innerHTML=data.tides.events.length ? data.tides.events.map((e)=>`<div class="tide-row"><span class="tide-kind"><span class="tide-arrow ${e.kind==="low"?"low":""}">${e.kind==="high"?"↗":"↘"}</span>${e.kind==="high"?"만조":"간조"}</span><strong class="tide-time">${escapeHtml(clock(e.time))}</strong><span class="tide-height">${e.height_cm} cm</span></div>`).join("") : `<p class="provider-note">${escapeHtml(data.tides.note)}</p>`;
    const obs=data.observations;
    setBadge($("observation-status"),obs.status,obs.stale?"지연된 관측":"실측");
    $("observation-values").innerHTML=[['실측 수온',obs.water_temperature_c,'°C'],['실측 조위',obs.tide_height_cm,'cm'],['풍속',obs.wind_speed_ms,'m/s'],['기온',obs.air_temperature_c,'°C'],['염분',obs.salinity_psu,'psu'],['기압',obs.air_pressure_hpa,'hPa'],['풍향',obs.wind_direction_deg,'°'],['최대순간풍속',obs.max_gust_speed_ms,'m/s']].map(([label,value,unit])=>`<div><span>${label}</span><strong>${number(value)} <small>${Number.isFinite(value)?unit:''}</small></strong></div>`).join('');
    $("observation-source").textContent=`${obs.source_name} · ${obs.station_name} (${obs.station_code}) · ${obs.observed_at?new Date(obs.observed_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})+' KST · ':''}${obs.note}`;
    drawChart(data.marine.points);
    await loadHistory();
  } catch(error) {
    $("dashboard-content").hidden=true;
    $("observation-values").textContent="조회 실패";
    $("observation-source").textContent="이전 관측값을 숨겼습니다. 다시 조회해 주세요.";
    $("error").textContent=error.message;
    $("error").hidden=false;
    $("data-notice").innerHTML='<span class="notice-icon">i</span><p>조회에 실패해 이전 결과를 숨겼습니다. 예시로 자동 대체하지 않습니다. 입력값을 확인한 뒤 다시 조회해 주세요.</p>';
  } finally {
    $("query-button").disabled=false;
    $("query-button").innerHTML='바다 정보 조회 <span>↗</span>';
    $("dashboard-content").setAttribute("aria-busy","false");
  }
}

// MBRIS의 종 ID는 AphiaID가 아닙니다. 국명 결과와 상세 표시를 별도로 관리합니다.
let mbrisResults = [];
let speciesPage = 1;

async function loadSpecies(resetPage = true) {
  if (resetPage) speciesPage = 1;
  $("species-button").disabled=true;
  $("species-detail").hidden=true;
  const query = $("species-query").value.trim();
  const provider = $("species-provider").value;
  const useMbris = provider === 'mbris' || (provider === 'auto' && /[가-힣]/.test(query));
  $("species-pages").hidden = true;
  mbrisResults = [];
  $("species-list").textContent=useMbris ? "MBRIS에서 국명을 검색하는 중…" : "WoRMS DB를 검색하는 중…";
  try {
    // 화면과 API 문서가 같은 통합 검색 경로를 사용하도록 맞춥니다.
    const data = await api(`/api/species?q=${encodeURIComponent(query)}&provider=${provider}&page=${speciesPage}`);
    if (useMbris) {
      mbrisResults = data.items;
      $("species-list").innerHTML=data.items.length ? data.items.map((s,index)=>`<div class="species-row"><span class="species-icon">◒</span><div><strong>${escapeHtml(s.korean_name||'국명 미등록')}</strong><em>${escapeHtml(s.scientific_name||'학명 미등록')}</em><span class="species-note">MBRIS · 국내 종 정보</span></div><button type="button" class="detail-button" data-mbris-index="${index}">상세</button></div>`).join('') : '<p class="provider-note">MBRIS에서 해당 국명을 찾지 못했습니다. 다른 국명이나 학명으로 검색해 보세요.</p>';
      $("species-source").textContent=`${data.source_name} · 포함 검색어 ${data.query} · 이력 #${data.history_id}. ${data.note}`;
      $("species-pages").hidden = false;
      $("species-page").textContent = `${data.page_no}페이지 · ${data.total_count === null ? '전체 건수 미제공' : '총 '+data.total_count+'건'}`;
      $("species-prev").disabled = data.page_no <= 1;
      $("species-next").disabled = !data.has_more;
      await loadHistory();
      return;
    }
    $("species-list").innerHTML=data.items.length ? data.items.map((s)=>`<div class="species-row"><span class="species-icon">◒</span><div><strong>${escapeHtml(s.name)}</strong><em>${escapeHtml(s.scientific_name)}</em><span class="species-note">${escapeHtml(s.group)} · ${escapeHtml(s.taxonomic_status)} · ${escapeHtml(s.rank)}</span></div><button type="button" class="detail-button" data-species-id="${s.id}">상세</button></div>`).join("") : '<p class="provider-note">검색 결과가 없습니다. 다른 국명 또는 학명으로 검색해보세요.</p>';
    $("species-source").textContent=`${data.source_name} · 검색어 ${data.resolved_query} · 이력 #${data.history_id}. ${data.note}`;
    await loadHistory();
  } catch(error) {$("species-list").textContent=error.message;$("species-source").textContent=useMbris ? 'MBRIS 국명 검색에 실패했습니다. 키 설정과 API 상태를 확인하세요.' : 'WoRMS 검색에 실패했습니다.';await loadHistory();}
  finally {$("species-button").disabled=false;}
}

async function loadRecords() {
  records=await api("/api/records",{},false);
  $("record-count").textContent=records.length;
  $("record-list").innerHTML=records.length ? records.map((r)=>`<article class="record-card"><div class="record-head"><h3>${escapeHtml(r.title)}</h3><button type="button" data-action="favorite" data-id="${r.id}" class="${r.favorite?"is-favorite":""}" aria-label="${r.favorite?"즐겨찾기 해제":"즐겨찾기"}" aria-pressed="${r.favorite}">${r.favorite?"★":"☆"}</button></div><div class="record-meta">${escapeHtml(regionNames[r.region])} · ${escapeHtml(r.observed_on)}</div><p>${escapeHtml(r.note || "메모 없음")}</p><div class="record-actions"><button type="button" data-action="edit" data-id="${r.id}">수정하기</button><button type="button" class="delete" data-action="delete" data-id="${r.id}">삭제하기</button></div></article>`).join("") : '<div class="empty-state"><span class="empty-icon">▤</span><strong>아직 기록하지 않은 바다가 있어요.</strong><p>오늘의 작은 발견을 남겨보세요.<br>왼쪽 폼에서 첫 관찰 기록을 만들 수 있습니다.</p></div>';
}

function resetEdit() {
  editingId=null;$("record-form").reset();$("record-form-title").textContent="새로운 관찰 남기기";
  $("save-record").textContent="기록 저장하기 ＋";$("cancel-edit").hidden=true;
  document.querySelector(".form-hint").textContent="상단에서 선택한 지역과 날짜로 저장합니다.";
}

$("filters").addEventListener("submit", (event)=>{event.preventDefault();loadDashboard();});
$("species-search").addEventListener("submit", (event)=>{event.preventDefault();loadSpecies();});
$("species-provider").addEventListener("change", ()=>{
  speciesPage=1;$("species-list").textContent='검색 출처를 변경했습니다. 검색 버튼을 눌러 주세요.';
  $("species-source").textContent='';$("species-detail").hidden=true;$("species-pages").hidden=true;mbrisResults=[];
});
$("species-query").addEventListener("input", ()=>{speciesPage=1;$("species-pages").hidden=true;});
$("species-prev").addEventListener("click", ()=>{speciesPage=Math.max(1,speciesPage-1);loadSpecies(false);});
$("species-next").addEventListener("click", ()=>{speciesPage+=1;loadSpecies(false);});
$("cancel-edit").addEventListener("click", resetEdit);
$("record-form").addEventListener("submit", async(event)=>{
  event.preventDefault();$("save-record").disabled=true;
  const editing=editingId!==null;
  const payload={title:$("record-title").value,note:$("record-note").value || null};
  if(!editing){payload.region=$("region").value;payload.observed_on=$("target-date").value;}
  try {
    await api(editing?`/api/records/${editingId}`:"/api/records",{method:editing?"PATCH":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    resetEdit();await loadRecords();$("record-status").textContent=editing?"기록을 수정했습니다.":"관찰 기록을 저장했습니다.";
  } catch(error){$("record-status").textContent=error.message;}
  finally{$("save-record").disabled=false;}
});
$("record-list").addEventListener("click", async(event)=>{
  const button=event.target.closest("button[data-action]");if(!button)return;
  const id=Number(button.dataset.id),record=records.find((r)=>r.id===id);if(!record)return;
  if(button.dataset.action==="edit"){
    editingId=id;$("record-title").value=record.title;$("record-note").value=record.note||"";
    $("record-form-title").textContent="관찰 기록 수정하기";$("save-record").textContent="수정 내용 저장";$("cancel-edit").hidden=false;
    document.querySelector(".form-hint").textContent=`${regionNames[record.region]} · ${record.observed_on} 유지, 제목·메모만 수정합니다.`;
    $("record-title").focus();return;
  }
  button.disabled=true;
  try{
    if(button.dataset.action==="delete"){
      await api(`/api/records/${id}`,{method:"DELETE"});if(editingId===id)resetEdit();
    }else{
      await api(`/api/records/${id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({favorite:!record.favorite})});
    }
    await loadRecords();$("record-status").textContent="기록을 변경했습니다.";
  }catch(error){$("record-status").textContent=error.message;button.disabled=false;}
});
$("photo").addEventListener("change",()=>{
  const file=$("photo").files[0];if(!file)return;
  selectedPhoto=null;
  if(file.size>10*1024*1024 || !["image/jpeg","image/png","image/webp"].includes(file.type)){
    $("photo-status").textContent="10 MiB 이하의 JPEG, PNG, WEBP를 선택해 주세요.";return;
  }
  if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=URL.createObjectURL(file);
  $("photo-preview").onerror=()=>{selectedPhoto=null;$("photo-preview").hidden=true;$("shell-art").hidden=false;$("photo-status").textContent="이미지를 읽을 수 없습니다.";};
  $("photo-preview").src=previewUrl;$("photo-preview").hidden=false;$("shell-art").hidden=true;
  selectedPhoto=file;
  $("photo-status").textContent=imageConfigured?"동의 후 분석 버튼을 누르면 전송·분석·저장됩니다.":"미리보기 완료 · 분석 API 키를 서버에 설정해 주세요.";
});
document.querySelectorAll("nav a").forEach((link)=>link.addEventListener("click",()=>{
  document.querySelectorAll("nav a").forEach((item)=>item.classList.remove("active"));link.classList.add("active");
}));

const dateParts=new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Seoul",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
const part=(type)=>dateParts.find((p)=>p.type===type).value;
$("target-date").value=`${part("year")}-${part("month")}-${part("day")}`;
(async()=>{
  await loadStatus();
  try{await loadRecords();}catch(error){$("record-list").textContent=error.message;}
  await loadDashboard();
})();

function setBadge(element,status,successLabel){
  element.textContent=status==='ok'?successLabel:({not_configured:'키 설정 필요',error:'연결 오류',no_data:'자료 없음'}[status]||status);
  element.className=`badge ${status==='ok'?'live':'neutral'}`;
  // 기존 선택자를 다음 조회에도 유지합니다.
  if(element.closest('.metric'))element.classList.add(element.closest('.metric').querySelector('#high-time,#low-time')?'tide-badge':'marine-badge');
}

async function loadStatus(){
  try{
    const data=await api('/api/status',{},false);
    imageConfigured=data.image_analysis_configured;
    $('connection-status').textContent=`물때 ${data.khoa_tides_configured?'키 설정됨':'키 필요'} · 실측 ${data.khoa_observations_configured?'키 설정됨':'키 필요'} · 국명 검색 ${data.mbris_configured?'키 설정됨':'MBRIS 키 필요'} · 사진 분석 ${imageConfigured?'키 설정됨':'키 필요'} · WoRMS 공개 DB · SQLite 영구 저장`;
    $('photo-status').textContent=imageConfigured?'사진을 선택하고 전송·저장에 동의한 뒤 분석하세요.':'사진 분석 키가 필요합니다. .env.example과 README의 설정 방법을 확인하세요.';
  }catch(error){$('connection-status').textContent=error.message;}
}

async function loadHistory(){
  try{
    const items=await api(`/api/history?limit=10&offset=${historyOffset}`,{},false);
    const names={dashboard:'바다 조회',species_search:'생물 검색',species_detail:'도감 상세',image_analysis:'사진 분석'};
    $('history-list').innerHTML=items.length?items.map(h=>`<button type="button" class="history-row" data-history-id="${h.id}"><span class="badge neutral">${names[h.kind]}</span><strong>${escapeHtml(h.title)}</strong><small>${escapeHtml(new Date(h.created_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}))} · ${h.status==='ok'?'저장됨':h.status==='partial'?'일부 항목 미수신':'조회 오류'}</small><span>열기 →</span></button>`).join(''):'<p class="provider-note">저장된 조회 이력이 없습니다.</p>';
    $('history-page').textContent=`${historyOffset+1}~${historyOffset+items.length}번째`;
    $('history-prev').disabled=historyOffset===0;$('history-next').disabled=items.length<10;
  }catch(error){$('history-list').textContent=error.message;}
}

$('refresh-history').addEventListener('click',()=>{historyOffset=0;loadHistory();});
$('history-prev').addEventListener('click',()=>{historyOffset=Math.max(0,historyOffset-10);loadHistory();});
$('history-next').addEventListener('click',()=>{historyOffset+=10;loadHistory();});
$('history-list').addEventListener('click',async(event)=>{
  const button=event.target.closest('[data-history-id]');if(!button)return;
  try{
    const data=await api(`/api/history/${button.dataset.historyId}`);
    $('history-detail').hidden=false;$('history-title').textContent=data.title;
    $('history-meta').textContent=`조회 당시 저장된 응답 · ${new Date(data.created_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})} KST · 현재 데이터가 아닙니다.`;
    $('history-json').textContent=JSON.stringify(data.result,null,2);
    $('history-image').hidden=!data.has_image;
    if(data.has_image)$('history-image').src=`/api/history/${data.id}/image`;
  }catch(error){$('history-list').textContent=error.message;}
});

$('species-list').addEventListener('click',async(event)=>{
  const mbrisButton=event.target.closest('[data-mbris-index]');
  if(mbrisButton){
    const species=mbrisResults[Number(mbrisButton.dataset.mbrisIndex)];
    if(!species)return;
    $('species-detail').hidden=false;
    $('species-detail').innerHTML=`<h3>${escapeHtml(species.korean_name||'국명 미등록')}</h3><p>${escapeHtml(species.scientific_name||'학명 미등록')}</p><p>MBRIS 종 식별자: ${escapeHtml(species.mbris_id||'미제공')}</p><p>${escapeHtml(species.description||'이 종의 개요는 API에서 제공되지 않았습니다.')}</p><p>국립해양생물자원관의 조회 결과입니다. 개체의 식용 안전성을 판정하지 않습니다.</p><a href="https://www.data.go.kr/data/15094770/openapi.do" target="_blank" rel="noopener">MBRIS 데이터 출처 보기 ↗</a>`;
    return;
  }
  const button=event.target.closest('[data-species-id]');if(!button)return;
  button.disabled=true;$('species-detail').hidden=false;$('species-detail').textContent='도감 상세를 조회하는 중…';
  try{
    const data=await api(`/api/species/${button.dataset.speciesId}`),s=data.species;
    $('species-detail').innerHTML=`<h3>${escapeHtml(s.scientific_name)}</h3><p>${escapeHtml(s.authority||'')} · ${escapeHtml(s.rank||'')} · ${escapeHtml(s.taxonomic_status||'')}</p><dl>${Object.entries(s.taxonomy).map(([k,v])=>`<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd>`).join('')}</dl><p>인정 학명: ${escapeHtml(s.accepted_name||'미등록')}</p><p>일반명: ${escapeHtml(data.vernaculars.map(v=>`${v.name} (${v.language})`).join(', ')||'자료 없음')}</p><p>분포: ${escapeHtml(data.distributions.join(', ')||'이 API 응답에 등록된 자료 없음')}</p><p>${escapeHtml(data.note)}</p><p>${escapeHtml(s.food_information)}</p><a href="${escapeHtml(s.source_url)}" target="_blank" rel="noopener">WoRMS 원문 보기 ↗</a>`;
    await loadHistory();
  }catch(error){$('species-detail').textContent=error.message;}
  finally{button.disabled=false;}
});

$('analyze-button').addEventListener('click',async()=>{
  if(!selectedPhoto){$('photo-status').textContent='먼저 올바른 이미지 파일을 선택해 주세요.';return;}
  if(!$('photo-consent').checked){$('photo-status').textContent='외부 AI 전송 및 SQLite 저장 동의를 확인해 주세요.';return;}
  if(!imageConfigured){$('photo-status').textContent='서버에 OPENAI_API_KEY와 OPENAI_MODEL 설정 후 다시 실행하세요.';return;}
  const form=new FormData();form.append('file',selectedPhoto);form.append('consent','true');
  $('analyze-button').disabled=true;$('photo-status').textContent='사진을 분석하는 중입니다. 최대 1분 정도 걸릴 수 있습니다.';
  $('analysis-result').hidden=true;
  try{
    const data=await api('/api/analyze',{method:'POST',body:form}),result=data.identification;
    $('analysis-result').hidden=false;
    $('analysis-result').innerHTML=`<div class="eyebrow">VISION ANALYSIS · 저장 이력 #${data.history_id}</div><h2>사진 분석 결과</h2><p>${escapeHtml(result.explanation)}</p><p>식별 상태: ${escapeHtml({candidates_found:'종 후보 있음',uncertain:'식별 보류',no_marine_life:'해양생물 없음'}[result.status])} · 사진 품질: ${escapeHtml(result.image_quality)}</p>${result.candidates.map(c=>`<article class="candidate"><h3>${escapeHtml(c.common_name_ko)} <small>${escapeHtml(c.scientific_name)}</small></h3><p>주관적 외형 일치: ${escapeHtml(c.visual_match)} (정확도 확률 아님)</p><p>특징: ${escapeHtml(c.visible_features.join(', '))}</p><p>구분의 한계: ${escapeHtml(c.distinguishing_limits.join(', '))}</p></article>`).join('')}<p>DB 대조: ${escapeHtml(data.database_matches.map(m=>m.scientific_name).join(', ')||'일치 자료 없음')}</p><p>${escapeHtml(data.database_note)}</p><p>${escapeHtml(result.suggested_photos.join(' / '))}</p><strong>${escapeHtml(data.specimen_edibility)}</strong>`;
    $('photo-status').textContent=`분석 결과와 메타데이터를 제거한 사진을 SQLite에 저장했습니다. 이력 #${data.history_id}`;
    await loadHistory();
  }catch(error){$('photo-status').textContent=error.message;}
  finally{$('analyze-button').disabled=false;}
});
