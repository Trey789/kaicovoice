import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
const path = new URL('../assets/attribution.js', import.meta.url);
const script = existsSync(path) ? readFileSync(path, 'utf8') : '';
function visit({url='https://www.kaicovoice.com/industries/hvac', referrer='', storage=new Map(), blocked=false, now=1000000}={}) {
  let clock=now; const location = new URL(url), listeners = {};
  const link = {href:'https://cal.com/kaicovoice/demo'};
  const context = vm.createContext({ URL, URLSearchParams, Date: {now:()=>clock}, window:{location},
    sessionStorage: {getItem:k=>{if(blocked)throw Error();return storage.get(k)||null;},setItem:(k,v)=>{if(blocked)throw Error();storage.set(k,v);}},
    document:{referrer,querySelector:()=>({href:'https://www.kaicovoice.com'+location.pathname}),querySelectorAll:()=>[link],addEventListener:(n,f)=>listeners[n]=f},
  });
  vm.runInContext(script,context);
  listeners.DOMContentLoaded?.();
  return {read:()=>JSON.parse(JSON.stringify(context.window.kaicoAttribution?.() ?? null)),advance:n=>clock+=n,click:()=>listeners.click?.({target:{closest:()=>link}}),value:JSON.parse(JSON.stringify(context.window.kaicoAttribution?.() ?? null)),storage,link};
}
test('first touch survives internal and Spanish navigation without private query fields',()=>{
  const first=visit({url:'https://www.kaicovoice.com/industries/hvac?utm_source=newsletter&utm_medium=email&utm_campaign=heat&utm_term=repair&utm_content=button&email=private@example.test&invite=secret'});
  const next=visit({url:'https://www.kaicovoice.com/es/start?need=phone',referrer:'https://www.kaicovoice.com/industries/hvac',storage:first.storage});
  assert.deepEqual(next.value,{source:'newsletter',medium:'email',campaign:'heat',keyword:'repair',content:'button',click_id:'',landing_page:'/industries/hvac'});
  assert.doesNotMatch([...first.storage.values()].join(''),/private|secret|invite|email=/);
});
test('Google referral remains a referral, not an AI or organic claim',()=>{
  const result=visit({referrer:'https://www.google.com/search?q=private-query'});
  assert.equal(result.value?.source,'www.google.com');
  assert.equal(result.value?.medium,'referral');
  assert.doesNotMatch(JSON.stringify(result.value),/private-query|organic|ai_overview/);
});
test('blocked storage and no referrer retain a useful unknown source',()=>{
  const result=visit({blocked:true});
  assert.equal(result.value?.source,'unknown');
  assert.equal(result.value?.landing_page,'/industries/hvac');
});
test('expired or corrupt storage does not attribute a new visit to an old campaign',()=>{
  const first=visit({url:'https://www.kaicovoice.com/industries/hvac?utm_source=old'});
  assert.equal(visit({storage:first.storage,now:3000000}).value?.source,'unknown');
  const broken=first.storage;for(const key of broken.keys())broken.set(key,'{broken');
  assert.equal(visit({storage:broken}).value?.source,'unknown');
});
test('Cal.com retains supported campaign fields and uses entry page when content is absent',()=>{
  const result=visit({url:'https://www.kaicovoice.com/industries/hvac?utm_source=google&utm_medium=cpc&utm_campaign=hvac&utm_term=answering'});
  const query=new URL(result.link.href).searchParams;
  assert.equal(query.get('utm_source'),'google');assert.equal(query.get('utm_campaign'),'hvac');
  assert.equal(query.get('utm_term'),'answering');assert.equal(query.get('utm_content'),'/industries/hvac');
});
test('untrusted campaign fields are bounded',()=>{
  const result=visit({url:'https://www.kaicovoice.com/?utm_campaign='+ 'x'.repeat(1000)});
  assert.equal(result.value?.campaign.length,200);
});

for (const lang of ['', 'es/']) for (const [tradeKey, tradeLabel] of [['hvac','HVAC'],['plumbing','Plumbing'],['electrical','Electrical']]) {
  test(`${lang || 'en/'} ${tradeLabel} enquiry preselects phone and trade without touching consent`,()=>{
    const html=readFileSync(new URL('../src/pages/'+lang+'start.html',import.meta.url),'utf8');
    const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
    const phone={checked:false},trade={value:''},sms={checked:false};
    const context=vm.createContext({URLSearchParams,window:{location:{search:'?need=phone&trade='+tradeKey}},
      document:{getElementById:id=>id==='lf-trade'?trade:null,querySelector:s=>s.includes('Phone answering')?phone:s.includes('sms')?sms:null,querySelectorAll:()=>[]}});
    vm.runInContext(code,context);
    assert.equal(phone.checked,true);assert.equal(trade.value,tradeLabel);assert.equal(sms.checked,false);
  });
}

for (const lang of ['', '.es']) for (const demo of [false,true]) {
  test(`${lang || 'English'} ${demo?'callback':'enquiry'} sends acquisition fields with existing consent contract`,async()=>{
    const html=readFileSync(new URL('../src/partials/footer'+lang+'.html',import.meta.url),'utf8');
    const code=demo?html.match(/  var cm = document.getElementById\('callMe'\);[\s\S]*?^  }/m)[0]:html.match(/\(function \(\) {\n  var form = document.getElementById\('leadForm'\);[\s\S]*?\n}\)\(\);/)[0];
    let submit,posted;
    const blank=()=>({value:'',checked:false,hidden:true,classList:{toggle(){}},focus(){},getAttribute(){return null;}});
    const fields=new Map(),element=s=>{if(!fields.has(s))fields.set(s,blank());return fields.get(s);};
    const form={querySelector:element,querySelectorAll:()=>[],addEventListener:(event,fn)=>submit=fn};
    for(const [s,v] of Object.entries(demo?{'#cm-name':'Fixture','#cm-phone':'9185550123','#cm-trade':'HVAC'}:{'[name="name"]':'Fixture','[name="business"]':'Fictional HVAC','[name="trade"]':'HVAC','[name="phone"]':'9185550123'}))element(s).value=v;
    element('#cm-consent').checked=true;
    const attribution={source:'newsletter',medium:'email',landing_page:'/industries/hvac'};
    const context=vm.createContext({Date,Math,JSON,sessionStorage:{getItem(){},setItem(){},removeItem(){}},
      document:{getElementById:id=>(id===(demo?'callMe':'leadForm'))?form:blank()},window:{location:{pathname:'/start'},kaicoAttribution:()=>attribution,addEventListener(){}},
      fetch:(url,options)=>{posted={url,...JSON.parse(options.body)};return Promise.resolve({ok:true,json:()=>Promise.resolve({ok:true})});}});
    vm.runInContext(code,context);submit({preventDefault(){}});await new Promise(r=>setImmediate(r));
    assert.deepEqual(posted.attribution,attribution);
    assert.equal(posted.source,demo?'web_demo':'web_form');
    if(demo){assert.equal(posted.consent,true);assert.equal(posted.consent_version,'2026-09-10');}
    else {assert.equal(posted.sms_consent,false);assert.equal(posted.sms_consent_lang,lang?'es':'en');}
  });
}


test('an open document expires before form reads and Cal navigation',()=>{
  const page=visit({url:'https://www.kaicovoice.com/industries/hvac?utm_source=old'});
  page.advance(1800001);assert.equal(page.read().source,'unknown');
  page.click();assert.equal(new URL(page.link.href).searchParams.get('utm_source'),'unknown');
});
test('a tagged calendar booking keeps both creative and original entry page',()=>{
  const page=visit({url:'https://www.kaicovoice.com/industries/hvac?utm_content=creative-42'});
  const content=new URL(page.link.href).searchParams.get('utm_content');
  assert.match(content,/creative-42/);assert.match(content,/industries\/hvac/);
});
test('owned app referrals are internal and external hostname fallback is bounded',()=>{
  assert.equal(visit({referrer:'https://app.kaicovoice.com/dashboard'}).value.source,'unknown');
  const host=['a'.repeat(60),'b'.repeat(60),'c'.repeat(60),'d'.repeat(30),'test'].join('.');
  assert.ok(visit({referrer:'https://'+host+'/'}).value.source.length<=200);
});
test('stored landing-page queries are stripped before forwarding',()=>{
  const page=visit();for(const [key,value] of page.storage){const data=JSON.parse(value);data.touch.landing_page='/start?invite=private#secret';page.storage.set(key,JSON.stringify(data));}
  const next=visit({storage:page.storage});assert.equal(next.value.landing_page,'/start');
  assert.doesNotMatch(next.link.href,/private|secret/);
});

for (const unsafe of ['__proto__','constructor','unlisted']) test(`unknown trade ${unsafe} cannot prefill a request`,()=>{
  const html=readFileSync(new URL('../src/pages/start.html',import.meta.url),'utf8');
  const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
  const phone={checked:false},trade={value:''},language={search:''};
  vm.runInNewContext(code,{URLSearchParams,window:{location:{search:'?need=phone&trade='+unsafe}},document:{getElementById:()=>trade,querySelector:()=>phone,querySelectorAll:()=>[language]}});
  assert.equal(trade.value,'');assert.equal(language.search,'?need=phone');
});
