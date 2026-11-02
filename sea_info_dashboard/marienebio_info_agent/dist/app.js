'use strict';

// The contour drawing is an illustration, not oceanographic data.
const contours = document.getElementById('contours');
for (let ring = 0; ring < 28; ring++) {
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  const points = [];
  for (let step = 0; step <= 180; step++) {
    const t = (step / 180) * Math.PI * 2;
    const r = 38 + ring * 9 + Math.sin(t * 3 + ring * .07) * 14 + Math.cos(t * 5) * 5;
    const x = 300 + Math.cos(t) * r * .8 + Math.sin(t * 2) * 12;
    const y = 285 + Math.sin(t) * r * 1.15;
    points.push(`${step ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`);
  }
  path.setAttribute('d', points.join(' ') + 'Z');
  contours.append(path);
}

const filters = [...document.querySelectorAll('[data-filter]')];
filters.forEach(button => button.addEventListener('click', () => {
  filters.forEach(filter => {
    const selected = filter === button;
    filter.classList.toggle('active', selected);
    filter.setAttribute('aria-pressed', String(selected));
  });
  document.querySelectorAll('.project-card').forEach(card => {
    card.hidden = button.dataset.filter !== 'all' && card.dataset.category !== button.dataset.filter;
  });
}));

const projectContent = {
  sea: `<p class="eyebrow">PROJECT 01 / OCEAN DATA</p><h2 id="detail-title">Sea-Info 해양 대시보드</h2><p class="detail-lead">해양 예보와 생물 분류 정보를 조회하고, 관찰 기록과 조회 이력을 SQLite에 남기는 FastAPI 기반 학습 프로젝트입니다.</p><div class="tech-list"><span>Python</span><span>FastAPI</span><span>SQLite</span><span>Open-Meteo</span><span>WoRMS</span></div><h3>만들고 있는 흐름</h3><ul><li>Open-Meteo Marine API로 파고·해수면 온도 예보 조회</li><li>WoRMS에서 해양생물 학명과 분류 정보 검색</li><li>관찰 기록과 조회 당시의 응답·상태를 SQLite에 저장</li><li>공공 API와 이미지 분석을 연결하고 결과의 출처·한계를 표시</li></ul><h3>확인된 것과 남은 것</h3><p>저장소 README에는 실제 WoRMS 검색·상세 조회와 Open-Meteo 호출 확인이 기록되어 있습니다. 국립해양조사원 API와 OpenAI 사진 분석은 사용자 키가 없어 모의 응답으로 흐름을 검증한 상태입니다.</p><div class="detail-callout">다음 실험 제안 — 인증키 설정 후 실제 응답을 확인하고, 저장된 예보의 조회 시각과 현재 예보를 구분해 보기. 데이터 수신 실패를 정상 값으로 바꾸지 않는 원칙을 이어갑니다.</div><div class="detail-actions"><a class="button primary" href="https://github.com/barokim/sea-info_dashboard" target="_blank" rel="noopener noreferrer">GitHub에서 코드 보기 ↗</a><a class="text-link" href="https://github.com/barokim/sea-info_dashboard/blob/main/README.md" target="_blank" rel="noopener noreferrer">실행 방법과 검증 기록 ↗</a></div><p class="detail-source">2026.10.26 저장소 README 확인 기준 · 이 페이지는 대시보드 자체나 실시간 해양 데이터를 제공하지 않습니다.</p>`,
  guest: `<p class="eyebrow">PROJECT 02 / WEB BACKEND</p><h2 id="detail-title">작은 방명록</h2><p class="detail-lead">닉네임을 입력하고 짧은 인사를 남기는 FastAPI·SQLite 웹 애플리케이션. 화면에서 보낸 요청이 저장되고 다시 읽히는 과정을 익히는 프로젝트입니다.</p><div class="tech-list"><span>FastAPI</span><span>SQLite</span><span>Pydantic</span><span>Cookie</span></div><h3>코드에서 확인한 동작</h3><ul><li>작성자 이름, 메시지, 작성 시각을 entries 테이블에 저장</li><li>guestbook_name 쿠키에 닉네임을 기억해 다음 방문에 재사용</li><li>쿠키에 HttpOnly·SameSite 설정 적용, HTTPS 요청에서는 Secure 설정</li><li>입력값 검증, 페이지 나누기, 저장 후 리다이렉트 처리</li></ul><div class="detail-callout">이름을 기억하는 기능은 회원가입이나 본인 인증과 다릅니다. 현재 확인한 코드는 별도의 로그인 인증이나 서버 측 세션 저장 기능을 포함하지 않습니다.</div><h3>다음 질문</h3><p>“이 이름을 입력한 사람이 지난번과 같은 사람인가?”를 확인하려면 무엇이 더 필요할까요? 닉네임 쿠키와 인증된 사용자 식별의 차이에서 다음 학습을 시작합니다.</p><div class="detail-actions"><a class="button primary" href="https://github.com/barokim/guestbook" target="_blank" rel="noopener noreferrer">GitHub에서 코드 보기 ↗</a><a class="text-link" href="https://github.com/barokim/guestbook/blob/main/main.py" target="_blank" rel="noopener noreferrer">main.py 읽기 ↗</a></div><p class="detail-source">2026.10.26 main.py 확인 기준 · 외부 서비스의 현재 배포 상태는 이 페이지에서 확인하지 않았습니다.</p>`
};

const noteContent = {
  cookie: `<p class="eyebrow">NOTE 01 / WEB FUNDAMENTALS</p><h2 id="detail-title">닉네임 기억과<br>사용자 인증의 차이</h2><p class="detail-lead">방명록은 guestbook_name 쿠키를 읽어 이름을 화면에 다시 보여줍니다. 이 이름은 편리한 입력값이지만, 사용자의 신원을 입증하지는 않습니다.</p><h3>방명록에서 확인할 것</h3><ol><li><b>기억:</b> 쿠키에 저장한 닉네임을 다음 요청에서 읽습니다.</li><li><b>검증:</b> 길이와 제어문자를 검사합니다. 입력 형식 검증은 본인 인증과 다릅니다.</li><li><b>인증:</b> 로그인이나 검증된 계정 연결을 통해 “누구인가”를 확인하는 단계가 추가로 필요합니다.</li></ol><h3>세션을 공부할 때 던질 질문</h3><p>서버는 어떤 상태를 유지할까요? 브라우저에는 무엇을 보낼까요? 만료·로그아웃 때 기존 상태를 어떻게 무효화할까요? 세션 저장 방식은 여러 가지이므로, “쿠키는 클라이언트, 세션은 무조건 서버”라는 구분만으로 끝내지 않습니다.</p><div class="detail-callout">다음 실험 제안 — 임시 사용자 ID와 서버 세션 저장소를 연결해 보고, 이름 변경·쿠키 삭제·로그아웃의 결과를 각각 관찰하기. 실제 방명록에 이미 구현된 기능은 아닙니다.</div><div class="detail-actions"><a class="text-link" href="https://github.com/barokim/guestbook/blob/main/main.py" target="_blank" rel="noopener noreferrer">출발점이 된 코드 ↗</a></div>`,
  api: `<p class="eyebrow">NOTE 02 / DATA & VERIFICATION</p><h2 id="detail-title">진짜 데이터와 예시 데이터,<br>경계를 분명하게</h2><p class="detail-lead">화면에 값이 보인다는 사실만으로 실제 API 연결을 확인했다고 말할 수는 없습니다. Sea-Info의 검증 기록은 이 차이를 구분합니다.</p><h3>현재 기록된 검증 범위</h3><ul><li><b>실제 호출 확인:</b> WoRMS 생물 검색·상세, Open-Meteo Marine 예보</li><li><b>모의 응답 검증:</b> 국립해양조사원 물때·관측, OpenAI 사진 분석 흐름</li><li><b>남은 확인:</b> 사용자 인증키를 넣은 실제 요청·응답, 사진 식별의 실제 품질</li></ul><h3>오류도 데이터의 일부</h3><p>인증키가 없거나 요청이 실패했을 때 정상 수치처럼 보이는 예시 값으로 바꾸지 않습니다. 조회 당시의 상태와 시각을 함께 저장해, 나중에 다시 열어도 그 결과의 의미를 알 수 있게 합니다.</p><div class="detail-callout">회고 질문 — 이번 주에 직접 확인한 것은 무엇이고, 테스트용 응답으로만 확인한 것은 무엇인가요? 두 문장으로 나누어 적어보세요.</div><div class="detail-actions"><a class="text-link" href="https://github.com/barokim/sea-info_dashboard/blob/main/README.md" target="_blank" rel="noopener noreferrer">검증 및 현재 한계 읽기 ↗</a></div>`,
  db: `<p class="eyebrow">NOTE 03 / NEXT EXPERIMENT</p><h2 id="detail-title">저장한 기록은<br>다시 시작해도 남아 있을까?</h2><p class="detail-lead">SQLite 파일에 기록이 저장되는 것과, 배포 환경에서 그 파일이 계속 보관되는 것은 서로 다른 확인이 필요합니다.</p><h3>직접 확인할 순서</h3><ol><li>고유한 문구를 포함한 테스트 기록을 하나 작성합니다.</li><li>앱을 종료하고 같은 DB 경로로 다시 실행합니다.</li><li>기존 기록이 남아 있는지 화면과 DB 양쪽에서 확인합니다.</li><li>배포 환경에서는 재시작·재배포 이후에도 같은 저장소가 유지되는지 확인합니다.</li></ol><h3>방명록 코드가 남긴 힌트</h3><p>get_database_path()는 실행 위치가 바뀌어도 DB 경로를 일정하게 해줍니다. 하지만 코드 주석에서도, 경로 고정만으로 임시 디스크가 영구 저장소로 바뀌지는 않는다고 구분합니다.</p><div class="detail-callout">다음 실험 제안 — 재시작 전후의 DB 경로·기록 수·확인 시각을 함께 적어보기. “저장 성공”을 눈으로 본 결과와 운영 환경의 보관 조건을 따로 확인합니다.</div><div class="detail-actions"><a class="text-link" href="https://github.com/barokim/guestbook/blob/main/main.py" target="_blank" rel="noopener noreferrer">DB 경로와 저장 로직 읽기 ↗</a></div>`
};

const detailDialog = document.getElementById('detail-dialog');
const reflectionDialog = document.getElementById('reflection-dialog');
function openDialog(dialog) {
  dialog.showModal();
  document.body.classList.add('modal-open');
}
document.querySelectorAll('[data-project]').forEach(button => button.addEventListener('click', () => {
  document.getElementById('detail-content').innerHTML = projectContent[button.dataset.project];
  detailDialog.setAttribute('aria-labelledby', 'detail-title');
  openDialog(detailDialog);
}));
document.querySelectorAll('[data-note]').forEach(button => button.addEventListener('click', () => {
  document.getElementById('detail-content').innerHTML = noteContent[button.dataset.note];
  detailDialog.setAttribute('aria-labelledby', 'detail-title');
  openDialog(detailDialog);
}));
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => document.body.classList.remove('modal-open'));
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
});

const STORAGE_KEY = 'baro-logbook-reflection-v1';
const fieldDefinitions = {
  KPT: [
    ['keep', 'Keep', '계속 가져가고 싶은 것', '이번 주에 도움이 된 습관이나 접근은 무엇인가요? 다음에도 이어갈 이유를 적어보세요.'],
    ['problem', 'Problem', '막혔던 순간과 그 이유', '어디서 예상과 달랐나요? 직접 확인한 사실과 아직 확인하지 못한 것을 나눠 적어보세요.'],
    ['try', 'Try', '다음 주, 작게 시도할 것', '언제, 무엇을, 어떻게 확인할지. 실행할 수 있는 작은 실험 하나를 정해보세요.']
  ],
  '4L': [
    ['liked', 'Liked', '좋았던 경험', '배우거나 만드는 과정에서 가장 즐거웠던 순간은 언제였나요?'],
    ['learned', 'Learned', '새롭게 배운 점', '이전에는 몰랐지만 이제 설명할 수 있는 것을 적어보세요.'],
    ['lacked', 'Lacked', '부족했던 점', '시간, 이해, 도구 중 무엇이 부족했나요? 구체적인 상황을 적어보세요.'],
    ['longed', 'Longed for', '다음에 바라는 것', '다음 주에는 어떤 경험을 더 해보고 싶나요? 작은 행동으로 바꿔보세요.']
  ]
};
const dateParts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).filter(p => p.type !== 'literal').map(p => [p.type,p.value]));
let draft = {date:`${dateParts.year}-${dateParts.month}-${dateParts.day}`,title:'',format:'KPT',values:{},updatedAt:null};
let storageAvailable = true;
try {
  const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
  if (stored && typeof stored === 'object') {
    if (typeof stored.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(stored.date)) draft.date = stored.date;
    if (typeof stored.title === 'string') draft.title = stored.title.slice(0,120);
    if (stored.format === '4L') draft.format = '4L';
    for (const [key] of Object.values(fieldDefinitions).flat()) {
      if (typeof stored.values?.[key] === 'string') draft.values[key] = stored.values[key].slice(0,4000);
    }
    if (typeof stored.updatedAt === 'string' && !Number.isNaN(Date.parse(stored.updatedAt))) draft.updatedAt = stored.updatedAt;
  }
} catch { storageAvailable = false; }
const dateInput = document.getElementById('log-date');
const titleInput = document.getElementById('log-title');
const formatInput = document.getElementById('log-format');
const saveStatus = document.getElementById('save-status');
dateInput.value = draft.date;
titleInput.value = draft.title;
formatInput.value = draft.format;

function updateDraftStatus() {
  const hasContent = draft.title.trim() || Object.values(draft.values).some(value => value.trim());
  document.getElementById('draft-status').textContent = hasContent && draft.updatedAt ? `${draft.date.replaceAll('-','.')} 회고 초안이 이 브라우저에 저장되어 있어요.` : 'KPT 또는 4L로 가볍게 시작하세요.';
}
function saveDraft() {
  draft.title = titleInput.value;
  draft.date = dateInput.value;
  draft.format = formatInput.value;
  draft.updatedAt = new Date().toISOString();
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
    storageAvailable = true;
    saveStatus.textContent = '이 브라우저에 자동 저장했어요.';
  } catch {
    storageAvailable = false;
    saveStatus.textContent = '자동 저장을 사용할 수 없어요. 파일로 내려받으세요.';
  }
  updateDraftStatus();
}
function renderFields() {
  const container = document.getElementById('reflection-fields');
  container.replaceChildren();
  fieldDefinitions[draft.format].forEach(([key, title, subtitle, placeholder]) => {
    const label = document.createElement('label');
    label.className = 'reflection-field';
    const top = document.createElement('span');
    top.className = 'field-top';
    const name = document.createElement('span');
    name.className = 'field-label';
    name.textContent = title;
    const small = document.createElement('small');
    small.textContent = subtitle;
    name.append(small);
    const count = document.createElement('span');
    count.className = 'field-count';
    const textarea = document.createElement('textarea');
    textarea.id = `log-${key}`;
    textarea.setAttribute('aria-label', `${title} — ${subtitle}`);
    textarea.maxLength = 4000;
    textarea.placeholder = placeholder;
    textarea.value = draft.values[key] || '';
    count.textContent = `${textarea.value.length} / 4000`;
    textarea.addEventListener('input', () => {
      draft.values[key] = textarea.value;
      count.textContent = `${textarea.value.length} / 4000`;
      saveDraft();
    });
    top.append(name,count);
    label.append(top,textarea);
    container.append(label);
  });
}
dateInput.addEventListener('input', saveDraft);
titleInput.addEventListener('input', saveDraft);
formatInput.addEventListener('change', () => {
  draft.format = formatInput.value;
  renderFields();
  saveDraft();
});
renderFields();
updateDraftStatus();
if (!storageAvailable) saveStatus.textContent = '이 브라우저에서는 파일로 기록을 보관하세요.';
document.getElementById('open-reflection').addEventListener('click', () => openDialog(reflectionDialog));

let toastTimeout;
function toast(message) {
  const element = document.getElementById('toast');
  element.textContent = message;
  element.classList.add('visible');
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => element.classList.remove('visible'),3500);
}
document.getElementById('reflection-form').addEventListener('submit', event => {
  event.preventDefault();
  if (!draft.title.trim() && !fieldDefinitions[draft.format].some(([key]) => (draft.values[key] || '').trim())) {
    toast('이번 주의 경험을 한 줄 먼저 적어주세요.');
    document.getElementById(`log-${fieldDefinitions[draft.format][0][0]}`).focus();
    return;
  }
  saveDraft();
  const lines = [`# ${draft.title.trim() || '주간 회고'}`, '', `- 작성자: 김바로`, `- 기록 날짜: ${draft.date}`, `- 회고 방식: ${draft.format}`, ''];
  for (const [key,title,subtitle] of fieldDefinitions[draft.format]) lines.push(`## ${title} — ${subtitle}`, '', (draft.values[key] || '').trim() || '(아직 작성하지 않음)', '');
  const blob = new Blob([lines.join('\n')],{type:'text/markdown;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `baro-${draft.format.toLowerCase()}-${draft.date}.md`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url),10000);
  toast('회고 파일 다운로드를 시작했어요.');
});
