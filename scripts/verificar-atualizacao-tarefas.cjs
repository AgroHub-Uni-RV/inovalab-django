// Regressão: quadro deve atualizar mesmo com o script compartilhado antigo/bloqueado.
// Somente servidor e sessão administrativos de um banco de testes dedicado.
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {chromium} = require('playwright-core');
const root = process.env.TASK_TEST_BASE_URL?.replace(/\/$/,'');
const session = process.env.TASK_TEST_SESSION;
if (!root || !session) throw new Error('Defina TASK_TEST_BASE_URL e TASK_TEST_SESSION de testes.');
const legacyFilters = execFileSync('git',['show','bb5e9c9:inovalab_app/static/inovalab_app/shared/auto-apply.js'],{encoding:'utf8'});

(async()=>{
  const browser = await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    for (const mode of ['legacy','blocked']) {
      const context = await browser.newContext({viewport:{width:1366,height:1000}});
      await context.addCookies([{name:'sessionid',value:session,url:new URL(root).origin}]);
      const page = await context.newPage();
      await page.route('**/shared/auto-apply.js*',route=>mode==='legacy' ?
        route.fulfill({status:200,contentType:'application/javascript',body:legacyFilters}) : route.abort());
      await page.goto(root+'/tarefas/?q=Tarefa+filtro&status=demanda');
      const card = page.locator('[data-task-id]').first();
      const id = await card.getAttribute('data-task-id');
      const apiURL = new URL(await card.locator('form').getAttribute('data-api-url'),root).href;
      const detailURL = apiURL.replace(/transicoes\/$/,'');
      const before = await (await context.request.get(detailURL)).json();
      let posts = 0;
      page.on('request',request=>{if(request.url()===apiURL && request.method()==='POST') posts++;});
      // A coluna filtrada não mostra o destino; selecionar Todas mantém a busca.
      await page.locator('.module-tabs a').first().click();
      await page.waitForFunction(()=>document.querySelectorAll('[data-task-column]').length===4);
      const saved = page.waitForResponse(response=>response.url()===apiURL && response.request().method()==='POST');
      await page.locator(`[data-task-id="${id}"] [data-task-drag]`).dragTo(page.locator('[data-task-column="criacao"] .column-cards'));
      const afterWrite = await saved;
      assert.equal(afterWrite.status(),200);
      const after = await (await context.request.get(detailURL)).json();
      assert.equal(after.status,'criacao');
      await page.waitForFunction(id=>document.querySelector(`[data-task-id="${id}"]`)?.dataset.taskStatus==='criacao',id,{timeout:2500});
      assert.equal(new URL(page.url()).searchParams.get('q'),'Tarefa filtro');
      assert.equal(after.versao,before.versao+1);
      assert.equal(posts,1,'Atualizar quadro não pode reenviar a gravação');
      assert.equal(await page.locator('#task-q').inputValue(),'Tarefa filtro');
      console.log(`Arraste com script ${mode}: estado persistido e quadro atualizado automaticamente, filtros e versão preservados.`);
      await context.close();
    }
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
