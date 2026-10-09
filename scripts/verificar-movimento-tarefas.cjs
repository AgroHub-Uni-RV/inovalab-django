// Execute somente contra servidor e sessão de testes isolados.
const assert = require('node:assert/strict');
const {chromium} = require('playwright-core');
const root = process.env.TASK_TEST_BASE_URL?.replace(/\/$/, '');
const session = process.env.TASK_TEST_SESSION;
if (!root || !session) throw new Error('Defina TASK_TEST_BASE_URL e TASK_TEST_SESSION de testes.');

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport:{width:1366,height:1000}});
    await context.addCookies([{name:'sessionid',value:session,url:new URL(root).origin}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(root+'/tarefas/');
    assert(await page.locator('form[data-task-move]').count() > 0, 'O quadro deve oferecer Mover para…');
    const card = page.locator('[data-task-id]').first();
    const csrf = await card.locator('[name=csrfmiddlewaretoken]').inputValue();
    // Banco dedicado: restaura o cenário para tornar a verificação repetível.
    let listURL = root+'/api/v1/tarefas/';
    const fixtureTasks = [];
    while (listURL) {
      const list = await (await context.request.get(listURL)).json();
      fixtureTasks.push(...list.results);
      listURL = list.next;
    }
    for (const task of fixtureTasks.filter(task=>task.status!=='demanda')) {
      const reset = await context.request.post(root+`/api/v1/tarefas/${task.id}/transicoes/`,
        {headers:{'X-CSRFToken':csrf},data:{status:'demanda',versao:task.versao}});
      assert.equal(reset.status(),200);
    }
    await page.reload();
    const id = await card.getAttribute('data-task-id');
    const endpoint = await card.locator('form').getAttribute('data-api-url');
    const apiUrl = new URL(endpoint, root).href;
    const detailUrl = apiUrl.replace(/transicoes\/$/, '');
    const getTask = async () => (await context.request.get(detailUrl)).json();
    const moveAPI = async status => {
      const task = await getTask();
      const result = await context.request.post(apiUrl, {headers:{'X-CSRFToken':csrf},data:{status,versao:task.versao}});
      assert.equal(result.status(),200);
    };
    await moveAPI('demanda');
    await page.reload();
    const selector = `[data-task-id="${id}"]`;
    const waitBoard = async status => {
      await page.waitForFunction(({selector,status}) => {
        const card = document.querySelector(selector);
        return card?.dataset.taskStatus === status && !document.getElementById('main').hasAttribute('aria-busy');
      }, {selector,status});
    };
    let navigations = 0;
    page.on('request',request => {if(request.isNavigationRequest()) navigations++;});
    const before = await getTask();
    const controlSizes = await page.locator(selector+' form').evaluate(form=>{
      const select=form.querySelector('select').getBoundingClientRect();
      const button=form.querySelector('button').getBoundingClientRect();
      return {selectWidth:select.width,selectHeight:select.height,buttonHeight:button.height};
    });
    assert(controlSizes.selectWidth>=100,'O seletor deve comportar Mover para… nas quatro colunas');
    assert.equal(controlSizes.selectHeight,controlSizes.buttonHeight,'Seletor e botão devem ter a mesma altura');
    await page.locator(selector+' [data-task-drag]').dragTo(page.locator('[data-task-column="criacao"] .column-cards'));
    await waitBoard('criacao');
    const after = await getTask();
    assert.equal(after.versao,before.versao+1);
    assert(after.inicio);
    assert.equal(after.conclusao,null);
    assert.equal(after.descricao,before.descricao);
    assert.deepEqual(after.responsaveis,before.responsaveis);
    assert.equal(after.prazo,before.prazo);
    assert.equal(navigations,0,'Movimento não deve navegar para outra página');

    // Mover por teclado e em viewport móvel, inclusive numa única coluna filtrada.
    await page.setViewportSize({width:390,height:900});
    await page.locator(selector+' select').selectOption('concluido');
    await page.locator(selector+' button[type=submit]').focus();
    await page.locator(selector+' button[type=submit]').press('Enter');
    await waitBoard('concluido');
    assert((await getTask()).conclusao);
    for (const width of [1366,768,390,360]) {
      await page.setViewportSize({width,height:1000});
      await page.waitForTimeout(200);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Overflow em ${width}`);
    }
    await page.goto(root+'/tarefas/?status=concluido');
    await page.locator(selector+' select').selectOption('demanda');
    await page.locator(selector+' button[type=submit]').click();
    await page.waitForFunction(selector=>!document.querySelector(selector) && !document.getElementById('main').hasAttribute('aria-busy'),selector);
    assert.equal(new URL(page.url()).searchParams.get('status'),'concluido');
    assert.equal((await getTask()).status,'demanda');

    // Alteração concorrente real: 409 não sobrescreve dados nem repete POST.
    await page.goto(root+'/tarefas/');
    await moveAPI('avaliacao');
    const concurrent = await getTask();
    await page.locator(selector+' select').selectOption('criacao');
    await page.locator(selector+' button[type=submit]').click();
    await page.locator('#task-board-feedback').filter({hasText:'alterada'}).waitFor();
    await waitBoard('avaliacao');
    assert.equal((await getTask()).versao,concurrent.versao);

    // Gravação em andamento não aceita um segundo envio, mesmo após eventos repetidos.
    let releaseMove;
    let enteredMove;
    const moveEntered = new Promise(resolve=>{enteredMove=resolve;});
    const moveRelease = new Promise(resolve=>{releaseMove=resolve;});
    let writes = 0;
    await page.route(apiUrl,async route=>{
      writes++;
      const response = await route.fetch();
      enteredMove();
      await moveRelease;
      await route.fulfill({response});
    });
    await page.locator(selector+' select').selectOption('concluido');
    await page.locator(selector+' button[type=submit]').click();
    await moveEntered;
    await page.locator(selector+' form').evaluate(form=>form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
    assert.equal(writes,1);
    releaseMove();
    await waitBoard('concluido');
    await page.unroute(apiUrl);
    assert.equal((await getTask()).versao,concurrent.versao+1);
    const stable = await getTask();
    const messageRects = await page.evaluate(()=>['task-board-feedback','async-update-status'].map(id=>{
      const r=document.getElementById(id).getBoundingClientRect();return {top:r.top,bottom:r.bottom};
    }));
    assert(messageRects[0].bottom<=messageRects[1].top,'Mensagens de movimento e atualização não devem sobrepor');

    // Falha de transporte: conservar o estado confirmado, sem repetir gravação.
    await page.route(apiUrl,route=>route.abort());
    await page.locator(selector+' select').selectOption('criacao');
    await page.locator(selector+' button[type=submit]').click();
    await page.locator('#task-board-feedback').filter({hasText:'confirmar'}).waitFor();
    await page.waitForFunction(()=>!document.getElementById('main').hasAttribute('aria-busy'));
    assert.equal((await getTask()).versao,stable.versao);
    await page.unroute(apiUrl);

    // Uma busca iniciada antes da gravação não pode devolver o status antigo depois dela.
    let releaseSearch;
    let enteredSearch;
    const searchEntered = new Promise(resolve=>{enteredSearch=resolve;});
    const searchRelease = new Promise(resolve=>{releaseSearch=resolve;});
    let delayFirstSearch = true;
    await page.route('**/tarefas/?**',async route=>{
      if (!delayFirstSearch || new URL(route.request().url()).searchParams.get('q')!=='Tarefa filtro') return route.continue();
      delayFirstSearch = false;
      const response = await route.fetch();
      enteredSearch();
      await searchRelease;
      await route.fulfill({response}).catch(()=>{});
    });
    await page.locator('#task-q').fill('Tarefa filtro');
    await searchEntered;
    await page.locator(selector+' select').selectOption('avaliacao');
    await page.locator(selector+' button[type=submit]').click();
    await waitBoard('avaliacao');
    releaseSearch();
    await page.unroute('**/tarefas/?**');
    assert.equal(await page.locator('#task-q').inputValue(),'Tarefa filtro');
    assert.equal((await getTask()).status,'avaliacao');
    const afterSearch = await getTask();

    // Conexão sem resposta deve liberar os controles e reconsultar o quadro.
    await page.clock.install();
    await page.route(apiUrl, async route => {await new Promise(resolve=>setTimeout(resolve,18000)); await route.abort().catch(()=>{});});
    await page.locator(selector+' select').selectOption('criacao');
    await page.locator(selector+' button[type=submit]').click();
    await page.waitForFunction(selector=>document.querySelector(selector)?.getAttribute('aria-busy')==='true',selector);
    await page.clock.fastForward(16000);
    await page.waitForFunction(()=>document.getElementById('task-board-feedback')?.textContent.includes('confirmar'),null,{timeout:1000});
    await page.clock.resume();
    await page.unroute(apiUrl);
    await page.waitForFunction(()=>!document.getElementById('main').hasAttribute('aria-busy'));
    assert.equal((await getTask()).versao,afterSearch.versao);

    // A página atual é mantida enquanto ainda existir após o movimento.
    await page.goto(root+'/tarefas/?status=demanda&page=2');
    const pageTwoCard = page.locator('[data-task-id]').first();
    await pageTwoCard.locator('select').selectOption('criacao');
    await pageTwoCard.locator('button[type=submit]').click();
    await page.waitForFunction(()=>!document.getElementById('main').hasAttribute('aria-busy') &&
      document.getElementById('task-board-feedback')?.textContent.includes('atualizado'));
    assert.equal(new URL(page.url()).searchParams.get('page'),'2','Movimento deve conservar a página se ainda existir');
    await page.locator('[data-task-id]').first().locator('select').selectOption('criacao');
    await page.locator('[data-task-id]').first().locator('button[type=submit]').click();
    await page.waitForURL(url=>!url.searchParams.has('page'));
    assert.equal(new URL(page.url()).searchParams.get('status'),'demanda');
    assert.deepEqual(errors,[]);
    if (process.env.TASK_TEST_AXE_PATH) {
      await page.addScriptTag({path:process.env.TASK_TEST_AXE_PATH});
      const axe = await page.evaluate(()=>window.axe.run({runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));
      assert.deepEqual(axe.violations.map(item=>({id:item.id,impact:item.impact,nodes:item.nodes.map(node=>node.target)})),[]);
      console.log('Acessibilidade automatizada WCAG A/AA OK.');
    }
    console.log('Drag, teclado/celular, filtros, datas automáticas, versão, conflito e falha de rede OK.');

    // Alternativa tradicional, sem JavaScript: mesma autorização e CSRF.
    const traditional = await browser.newContext({javaScriptEnabled:false});
    await traditional.addCookies([{name:'sessionid',value:session,url:new URL(root).origin}]);
    const noJS = await traditional.newPage();
    await noJS.goto(root+'/tarefas/');
    await noJS.locator(selector+' select').selectOption('criacao');
    await noJS.locator(selector+' button[type=submit]').click();
    await noJS.waitForURL(root+`/tarefas/${id}/`);
    assert.equal((await getTask()).status,'criacao');
    console.log('Alternativa sem JavaScript OK.');

    if (process.env.TASK_TEST_OWNER_SESSION) {
      await moveAPI('demanda');
      const ownerContext = await browser.newContext({viewport:{width:390,height:900},isMobile:true,hasTouch:true});
      await ownerContext.addCookies([{name:'sessionid',value:process.env.TASK_TEST_OWNER_SESSION,url:new URL(root).origin}]);
      const ownerPage = await ownerContext.newPage();
      await ownerPage.goto(root+'/tarefas/');
      const ownerCard = ownerPage.locator(selector);
      assert.deepEqual(await ownerCard.locator('select option').evaluateAll(options=>options.map(option=>option.value)),['','criacao']);
      await ownerCard.locator('select').selectOption('criacao');
      await ownerCard.locator('button[type=submit]').click();
      await ownerPage.waitForFunction(selector=>document.querySelector(selector)?.dataset.taskStatus==='criacao',selector);
      assert.deepEqual(await ownerCard.locator('select option').evaluateAll(options=>options.map(option=>option.value)),['','avaliacao']);
      const ownerCSRF = await ownerCard.locator('[name=csrfmiddlewaretoken]').inputValue();
      await ownerCard.locator('select').selectOption('avaliacao');
      await ownerCard.locator('button[type=submit]').click();
      await ownerPage.waitForFunction(selector=>document.querySelector(selector)?.dataset.taskStatus==='avaliacao',selector);
      assert.equal(await ownerCard.locator('form[data-task-move]').count(),0);
      const evaluation = await getTask();
      const forbidden = await ownerContext.request.post(apiUrl,{headers:{'X-CSRFToken':ownerCSRF},data:{status:'concluido',versao:evaluation.versao}});
      assert.equal(forbidden.status(),403);
      assert.equal((await getTask()).versao,evaluation.versao);
      console.log('Responsável no celular: somente Demanda → Criação → Avaliação; aprovação bloqueada também na API.');
    }
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
