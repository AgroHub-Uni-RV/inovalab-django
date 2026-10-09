// Run against an isolated, seeded development server with an administrative test session.
// Requires playwright-core (NODE_PATH may point to an existing installation).
const assert = require('node:assert/strict');
const {chromium} = require('playwright-core');

const base = process.env.FILTER_TEST_BASE_URL;
const session = process.env.FILTER_TEST_SESSION;
if (!base || !session) throw new Error('Defina FILTER_TEST_BASE_URL e FILTER_TEST_SESSION para o banco de testes isolado.');
const root = base.replace(/\/$/, '');
const cases = [
  {path:'/agenda/', query:'?q=inexistente&mes=2026-01&categoria=visita&situacao=pendente&page=1', clean:'?mes='},
  {path:'/agenda/solicitacoes/', query:'?q=inexistente&mes=2026-01&status=pendente&page=1'},
  {path:'/agenda/meus/', query:'?q=inexistente&mes=2026-01&categoria=visita&situacao=pendente&page=1', traditional:true},
  {path:'/tarefas/', query:'?q=inexistente&servico=1&status=concluido&page=1'},
  {path:'/materiais/', query:'?q=inexistente&categoria=Categoria+teste&status=indisponivel&page=1'},
  {path:'/banners/', query:'?q=inexistente&status=inativo&page=1'},
  {path:'/usuarios/', query:'?q=inexistente&tab=inativos&page=1'},
];

async function assertClean(page, item) {
  await page.waitForURL(root + item.path + (item.clean || ''));
  await page.waitForFunction(()=>!document.getElementById('main')?.hasAttribute('aria-busy'));
  const controls = await page.locator('form.filter-bar, form.user-search').evaluate(form=>
    Object.fromEntries([...new FormData(form)].filter(([name])=>name!=='csrfmiddlewaretoken')));
  for (const [name, value] of Object.entries(controls)) {
    assert.equal(value, name==='tab' ? 'todos' : '', `Filtro ${name} não foi limpo em ${item.path}`);
  }
  const tab = page.locator('.module-tabs a[aria-current=page]');
  if (await tab.count()) assert.match(await tab.first().innerText(),/^Tod/);
  const currentPage = page.locator('.pagination a[aria-current=page]');
  if (await currentPage.count()) assert.equal(await currentPage.innerText(),'1');
}

(async()=>{
  const browser = await chromium.launch({headless:true, executablePath:process.env.FILTER_TEST_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    for (const javaScriptEnabled of [true,false]) {
      const context = await browser.newContext({javaScriptEnabled,viewport:{width:1366,height:1000}});
      await context.addCookies([{name:'sessionid',value:session,url:new URL(root).origin}]);
      const page = await context.newPage();
      const errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      for (const item of cases) {
        await page.goto(root + item.path + item.query);
        const clear=page.getByRole('link',{name:'Limpar filtros',exact:true});
        assert.equal(await clear.count(),1);
        let navigations=0;
        const onRequest=request=>{if(request.isNavigationRequest()) navigations++;};
        page.on('request',onRequest);
        await clear.focus();
        await clear.press('Enter');
        await assertClean(page,item);
        page.off('request',onRequest);
        if (javaScriptEnabled&&!item.traditional) assert.equal(navigations,0,`${item.path}: limpeza deve usar atualização automática`);
        for (const width of [1366,768,390,360]) {
          await page.setViewportSize({width,height:1000});
          await page.waitForTimeout(150);
          const rect=await page.getByRole('link',{name:'Limpar filtros',exact:true}).evaluate(link=>{
            const r=link.getBoundingClientRect();return {left:r.left,right:r.right,height:r.height,width:r.width};});
          assert(rect.left>=0 && rect.right<=width+1 && rect.height>=44,`${item.path} ${width}: botão cortado ou pequeno`);
          assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${item.path} ${width}: overflow`);
        }
      }
      console.log(`Sete telas: limpeza por teclado, abas, campos, layout 1366/768/390/360 e ${javaScriptEnabled?'JavaScript':'sem JavaScript'} OK.`);
      if (javaScriptEnabled) {
        const taskCase=cases.find(item=>item.path==='/tarefas/');
        // The isolated fixture must contain enough matching tasks for a second page.
        await page.goto(root+'/tarefas/?status=demanda&page=2');
        assert.equal(await page.locator('.pagination a[aria-current=page]').innerText(),'2');
        await page.getByRole('link',{name:'Limpar filtros',exact:true}).click();
        await assertClean(page,taskCase);
        await page.goBack();
        await page.locator('.pagination a[aria-current=page]').filter({hasText:'2'}).waitFor();
        assert.equal(await page.locator('[name=status]').inputValue(),'demanda');
        await page.goForward();
        await assertClean(page,taskCase);
        // Clear before debounce fires: pending text must not reappear after reset.
        await page.locator('[name=q]').fill('Busca que ainda não foi enviada');
        await page.getByRole('link',{name:'Limpar filtros',exact:true}).click();
        await assertClean(page,taskCase);
        await page.waitForTimeout(800);
        await assertClean(page,taskCase);
        // A late response to the previous search must not overwrite the clean state.
        let entered, release;
        const started=new Promise(resolve=>{entered=resolve;});
        const delayed=new Promise(resolve=>{release=resolve;});
        await page.route('**/tarefas/?**',async route=>{
          if(new URL(route.request().url()).searchParams.get('q')!=='Busca atrasada') return route.continue();
          const response=await route.fetch();
          entered();await delayed;
          try {await route.fulfill({response});} catch { /* Aborted by reset. */ }
        });
        await page.locator('[name=q]').fill('Busca atrasada');
        await started;
        await page.getByRole('link',{name:'Limpar filtros',exact:true}).click();
        await assertClean(page,taskCase);
        release();
        await page.waitForTimeout(300);
        await assertClean(page,taskCase);
        await page.unroute('**/tarefas/?**');
        // Failure keeps the active filter and URL; retry must use the clean destination.
        await page.goto(root+'/tarefas/?q=Tarefa&status=demanda');
        await page.route('**/tarefas/',route=>route.fulfill({status:500,body:'Falha controlada'}));
        await page.getByRole('link',{name:'Limpar filtros',exact:true}).click();
        await page.locator('#async-update-status button').waitFor();
        assert.equal(await page.locator('[name=q]').inputValue(),'Tarefa');
        assert.match(page.url(),/q=Tarefa/);
        await page.unroute('**/tarefas/');
        await page.locator('#async-update-status button').click();
        await assertClean(page,taskCase);
        console.log('Paginação, Voltar/Avançar, debounce, resposta atrasada e nova tentativa após erro OK.');
      }
      assert.deepEqual(errors,[]);
      await context.close();
    }
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
