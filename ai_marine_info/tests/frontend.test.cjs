// 서버·브라우저를 실행하지 않고 Node의 내장 VM과 작은 DOM 대역으로 검증합니다.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor(tag='div') {this.tagName=tag;this.children=[];this.textContent='';this.value='';this.hidden=false;this.disabled=false;this.attributes={};}
  append(...items) {this.children.push(...items);}
  replaceChildren(...items) {this.children=[...items];}
  setAttribute(name,value) {this.attributes[name]=value;}
  addEventListener() {}
  get options(){return this.children.flatMap(el=>el.tagName==='optgroup'?el.children:[el]);}
  set innerHTML(_) {throw new Error('사용자 문자열을 HTML로 렌더링했습니다.');}
}
function environment() {
  const elements=new Map();
  for(const name of ['account-links','province','city','station','region-notice','page-error','global-notice','latest-section','marine-result','area-title','data-date','station-notice','high-time','low-time','high-height','low-height','water-temperature','observation-time','wave-max','tide-note','observation-note','forecast-note','tide-rows','observation-values','forecast-rows'])elements.set(name,new Element());
  const store=new Map(), calls=[];
  const context=vm.createContext({
    document:{body:{dataset:{page:'home'}},getElementById:id=>elements.get(id)||null,createElement:tag=>new Element(tag)},
    sessionStorage:{getItem:key=>store.get(key)||null,setItem:(key,value)=>store.set(key,value),removeItem:key=>store.delete(key)},
    location:{pathname:'/',hash:'',origin:'http://localhost',assign(){}},
    URL,URLSearchParams,Headers,FormData,AbortController,Intl,Date,setTimeout,clearTimeout,
    fetch:async(url,options)=>{calls.push({url,options});return {ok:true,status:200,json:async()=>({ok:true})};},
  });
  const source=fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8').replace(/guarded\(init\);\s*$/,'');
  vm.runInContext(source,context);
  const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/regions.json'),'utf8'));
  context.testCatalog=catalog;vm.runInContext('catalog=testCatalog',context);
  return {context,elements,calls,store};
}
test('Bearer 토큰은 헤더에만 전달한다',async()=>{
  const env=environment();env.store.set('ai-marine.access','private-token');
  await vm.runInContext("api('/posts')",env.context);
  assert.equal(env.calls[0].url,'/posts');
  assert.equal(env.calls[0].options.headers.get('Authorization'),'Bearer private-token');
  assert.equal(env.calls[0].options.credentials,'omit');
});
test('관측소가 없는 지역은 다른 지역을 자동 선택하지 않는다',()=>{
  const env=environment();env.elements.get('city').value='p01-c01';env.elements.get('province').value='p01';
  vm.runInContext('updateStations()',env.context);
  assert.equal(env.elements.get('station').options[0].value,'');
  assert.match(env.elements.get('station').options[0].textContent,/관측소 없음/);
});
test('다른 지역 관측소는 명시적으로 안내한다',()=>{
  const env=environment();env.elements.get('city').value='p01-c01';env.elements.get('province').value='p01';
  vm.runInContext("updateStations('DT_0012')",env.context);
  assert.match(env.elements.get('region-notice').textContent,/다른 지역/);
});
test('지역 변경 시 이전 결과와 요청 버전을 초기화한다',()=>{
  const env=environment();env.elements.get('high-time').textContent='12:30';
  vm.runInContext('resetMarine()',env.context);
  assert.equal(env.elements.get('high-time').textContent,'—');
  assert.equal(vm.runInContext('selectionRevision',env.context),1);
  assert.equal(env.elements.get('marine-result').attributes['aria-busy'],'false');
});
test('게시글의 HTML 태그를 버튼 텍스트로 렌더링한다',()=>{
  const env=environment();
  const item=vm.runInContext("postItem({id:'1',title:'<img src=x onerror=alert(1)>',author_name:'<script>evil</script>',created_at:'2026-10-30T00:00:00Z'},()=>{})",env.context);
  assert.equal(item.children[0].children[0].textContent,'<img src=x onerror=alert(1)>');
  assert.equal(item.children[0].children[0].tagName,'button');
});
test('인증 장애 중에도 공개 해양 조회는 익명으로 요청한다',async()=>{
  const env=environment();env.store.set('ai-marine.access','private-token');
  vm.runInContext('authUnavailable=true',env.context);
  await vm.runInContext("api('/api/dashboard?city_id=p01-c05')",env.context);
  assert.equal(env.calls[0].options.headers.get('Authorization'),null);
});
