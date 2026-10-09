// Use exclusivamente banco/contas descartáveis com as fixtures descritas no módulo 30.
const assert = require('node:assert/strict');
const {chromium} = require('playwright-core');
const root = process.env.AGENDA_TEST_BASE_URL?.replace(/\/$/, '');
const adminSession = process.env.AGENDA_TEST_ADMIN_SESSION;
const ownerSession = process.env.AGENDA_TEST_OWNER_SESSION;
if (!root || !adminSession || !ownerSession) throw new Error('Defina base e sessões AGENDA_TEST_* descartáveis.');
const query = 'q=Execu%C3%A7%C3%A3o+browser&status=confirmada';
const management = root+'/agenda/solicitacoes/';

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    await context.addCookies([{name:'sessionid',value:adminSession,url:new URL(root).origin}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error=>errors.push(error.message));
    await page.goto(management+'?'+query);
    for (const label of ['Aguardando início','Em execução','Concluídos','Aguardando encerramento','Equipamentos históricos']) {
      assert.equal(await page.getByRole('heading',{name:new RegExp('^'+label)}).count(),1,`Grupo ausente: ${label}`);
    }
    const allBookings = [];
    let next = root+'/api/v1/agendamentos/';
    while (next) {
      const result = await (await context.request.get(next)).json();
      allBookings.push(...result.results);
      next = result.next;
    }
    const visits = allBookings.filter(row=>row.categoria==='visita');
    const current = visits.find(row=>row.observacoes==='Execução browser · em curso');
    const expired = visits.find(row=>row.observacoes==='Execução browser · encerramento');
    const future = visits.find(row=>row.observacoes==='Execução browser · futura');
    assert(current && expired && future,'Fixtures de visitas incompletas');
    assert.equal(current.estado_execucao,'em_execucao');
    assert.equal(expired.estado_execucao,'aguardando_encerramento');
    assert.equal(expired.realizada_em,null);
    const card = row=>page.locator(`[data-booking-key="visita-${row.id}"]`);
    assert.equal(await card(future).getByRole('button',{name:'Marcar como realizada'}).count(),0);
    assert.equal(await card(expired).locator('.execution-status').innerText(),'Aguardando encerramento');
    assert.equal(await page.locator('.execution-status').filter({hasText:'Concluído com atraso'}).count(),1);
    assert(await page.locator('.execution-alert').count()>0);
    for (const width of [1440,768,390,360]) {
      await page.setViewportSize({width,height:1000});
      await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth+1,{},{timeout:2000});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Overflow em ${width}`);
    }
    await page.setViewportSize({width:1440,height:1000});
    await page.getByRole('link',{name:'2',exact:true}).click();
    await page.waitForURL(url=>url.searchParams.get('page')==='2');
    await page.waitForFunction(()=>!document.getElementById('main').hasAttribute('aria-busy'));
    assert(await page.locator('.execution-column').filter({hasText:'Nenhum agendamento deste grupo nesta página.'}).count()>0);
    assert.equal(await page.locator('[data-booking-key]').count(),3);
    await page.goto(management+'?'+query);
    await page.getByRole('combobox',{name:'Execução',exact:true}).selectOption('em_execucao');
    await page.waitForURL(url=>url.searchParams.get('execucao')==='em_execucao');
    await page.waitForFunction(()=>!document.getElementById('main').hasAttribute('aria-busy'));
    const endpoint = await card(current).locator('.booking-execution-actions').getAttribute('action');
    const csrf = await card(current).locator('[name=csrfmiddlewaretoken]').first().inputValue();
    const detail = root+`/api/v1/agendamentos/visita/${current.id}/`;
    const history = async()=> (await (await context.request.get(detail+'historico/')).json()).results.filter(event=>event.acao==='realizar').length;
    const initialEvents = await history();
    const initialVersion = current.versao;
    const requests = [];
    const track = request=>{if(request.method()==='POST' && request.url().endsWith(endpoint)) requests.push(request);};
    page.on('request',track);
    await card(current).getByRole('button',{name:'Marcar como realizada'}).focus();
    await card(current).getByRole('button',{name:'Marcar como realizada'}).press('Enter');
    await page.waitForURL(url=>url.pathname.endsWith('/solicitacoes/') && url.searchParams.get('execucao')==='em_execucao');
    await page.getByText('Realização da visita registrada.',{exact:false}).waitFor();
    assert.equal(requests.length,1,'A realização deve enviar apenas um POST');
    const recorded = await (await context.request.get(detail)).json();
    assert.equal(recorded.versao,initialVersion+1);
    assert.equal(recorded.situacao,'confirmado');
    assert.equal(recorded.estado_execucao,'concluido');
    assert.equal(await history(),initialEvents+1);
    assert.equal(await card(current).count(),0);
    await page.goto(root+`/agenda/visita/${current.id}/`);
    assert.equal(await page.locator('.sheet-layout').count(),1);
    assert.equal(await page.locator('.sheet-detail-topbar .execution-status').innerText(),'Concluído');
    assert(await page.getByText(/^Realizada em/).count());
    assert.equal(await page.getByRole('button',{name:'Marcar como realizada'}).count(),0);
    const stale = await context.request.post(new URL(endpoint,root).href,{headers:{'X-CSRFToken':csrf},form:{versao:String(initialVersion)}});
    assert.equal(stale.status(),409);
    assert.equal(await history(),initialEvents+1);
    await page.goto(management+'?'+query+'&execucao=concluido');
    assert.equal(await card(current).count(),1);
    await page.getByRole('link',{name:'Limpar filtros'}).focus();
    await page.getByRole('link',{name:'Limpar filtros'}).press('Enter');
    await page.waitForURL(management);
    await page.waitForFunction(()=>!document.getElementById('main').hasAttribute('aria-busy'));
    assert.equal(await page.getByRole('combobox',{name:'Execução',exact:true}).inputValue(),'');
    assert.equal(await page.locator('.module-tabs a[aria-current=page]').innerText(),'Todas');

    const noJS = await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:900}});
    await noJS.addCookies([{name:'sessionid',value:adminSession,url:new URL(root).origin}]);
    const plain = await noJS.newPage();
    await plain.goto(management+'?'+query+'&execucao=aguardando_encerramento');
    const plainAction = plain.locator(`[data-booking-key="visita-${expired.id}"] .booking-execution-actions`);
    await plainAction.getByRole('button',{name:'Marcar como realizada'}).click();
    await plain.getByText('Realização da visita registrada.',{exact:false}).waitFor();
    assert.equal(new URL(plain.url()).searchParams.get('execucao'),'aguardando_encerramento');
    assert.equal(await plain.locator('[data-booking-key]').count(),0);
    await plain.getByRole('link',{name:'Limpar filtros'}).click();
    await plain.waitForURL(management);

    const owner = await browser.newContext({viewport:{width:390,height:900}});
    await owner.addCookies([{name:'sessionid',value:ownerSession,url:new URL(root).origin}]);
    const personal = await owner.newPage();
    await personal.goto(root+'/agenda/meus/');
    assert.equal(await personal.getByRole('button',{name:'Marcar como realizada'}).count(),0);
    assert.equal(await personal.getByRole('link',{name:'Gerenciamento de agendamentos'}).count(),0);
    assert.equal((await owner.request.get(management)).status(),403);
    const ownerCsrf = (await owner.cookies()).find(cookie=>cookie.name==='csrftoken').value;
    assert.equal((await owner.request.post(root+`/api/v1/agendamentos/visita/${future.id}/realizar/`,
      {headers:{'X-CSRFToken':ownerCsrf},data:{versao:future.versao}})).status(),403);

    // Uma falha de transporte não deve repetir a gravação.
    const failureContext = await browser.newContext();
    await failureContext.addCookies([{name:'sessionid',value:adminSession,url:new URL(root).origin}]);
    const failed = await failureContext.newPage();
    await failed.goto(root+`/agenda/visita/${future.id}/`);
    // Visita futura: o servidor recusa mesmo um POST manual.
    assert.equal((await context.request.post(root+`/api/v1/agendamentos/visita/${future.id}/realizar/`,
      {headers:{'X-CSRFToken':csrf},data:{versao:future.versao}})).status(),400);
    let attempts=0;
    await failed.route('**/agenda/visita/*/realizar/',route=>{attempts++; return route.abort();});
    await failed.evaluate(({endpoint,csrf,version})=>{
      const form=document.createElement('form'); form.method='post'; form.action=endpoint;
      for(const [name,value] of Object.entries({versao:version,csrfmiddlewaretoken:csrf})) {
        const input=document.createElement('input'); input.name=name; input.value=value; form.append(input);
      }
      document.body.append(form); form.submit();
    },{endpoint:root+`/agenda/visita/${future.id}/realizar/`,csrf,version:String(future.versao)});
    await failed.waitForTimeout(1000);
    assert.equal(attempts,1);
    assert.equal((await (await context.request.get(root+`/api/v1/agendamentos/visita/${future.id}/`)).json()).versao,future.versao);
    const expiredSession = await browser.newContext();
    await expiredSession.addCookies([{name:'sessionid',value:'expired-test-session',url:new URL(root).origin},
      {name:'csrftoken',value:csrf,url:new URL(root).origin}]);
    const denied = await expiredSession.request.post(new URL(endpoint,root).href,
      {form:{versao:String(initialVersion),csrfmiddlewaretoken:csrf},maxRedirects:0});
    assert.equal(denied.status(),302);
    assert.equal(await history(),initialEvents+1);
    if (process.env.AGENDA_TEST_AXE_PATH) {
      await page.goto(management+'?'+query);
      await page.addScriptTag({path:process.env.AGENDA_TEST_AXE_PATH});
      const violations=await page.evaluate(async()=> (await axe.run(document.querySelector('#main'),
        {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(row=>({id:row.id,targets:row.nodes.map(node=>node.target)})));
      assert.deepEqual(violations,[],'Violações de acessibilidade');
      console.log('Acessibilidade WCAG A/AA OK.');
    }
    assert.deepEqual(errors,[]);
    console.log('Grupos, contadores/paginação, filtros/limpeza, realização/versão/evento, API/detalhes, teclado/celular, sem JS, 403/409/sessão/rede OK.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error.message);process.exitCode=1;});
