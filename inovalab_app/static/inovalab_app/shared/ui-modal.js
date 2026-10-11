(() => {
  const dialog = document.getElementById('ui-modal');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const body = dialog.querySelector('.ui-modal-body');
  const feedback = dialog.querySelector('.ui-modal-status');
  const closeButton = dialog.querySelector('button[data-ui-close]');
  const title = dialog.querySelector('#ui-modal-title');
  const roots = ['equipmentRoot', 'materialRoot', 'bannerRoot'].map(key => dialog.dataset[key]).filter(Boolean).map(root => new URL(root, location.href).pathname);
  let trigger, controller, saving = false, standalone = false, returnURL;
  const previews = new Set();
  const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const formPaths = roots.map(root => new RegExp(`^${escape(root)}(?:novo|\\d+/editar)/$`));
  const taskRoot = new URL(dialog.dataset.taskRoot, location.href).pathname;
  const agendaRoot = new URL(dialog.dataset.agendaRoot, location.href).pathname;
  const confirmationPaths = roots.map(root => new RegExp(`^${escape(root)}(?:\\d+/excluir|restaurar-padrao)/$`));
  confirmationPaths.push(new RegExp(`^${escape(taskRoot)}\\d+/excluir/$`),
    new RegExp(`^${escape(agendaRoot)}(?:meus/)?(?:servico|equipamento|visita)/\\d+/cancelar/$`));
  const actionPaths = [new RegExp(`^${escape(agendaRoot)}(?:servico|equipamento|visita)/\\d+/avaliar/$`),
    new RegExp(`^${escape(agendaRoot)}visita/\\d+/realizar/$`)];
  const mode = value => {
    const url = new URL(value, location.href);
    if (url.origin !== location.origin) return null;
    if (formPaths.some(pattern => pattern.test(url.pathname))) return 'form';
    if (confirmationPaths.some(pattern => pattern.test(url.pathname))) return 'confirmation';
    if (actionPaths.some(pattern => pattern.test(url.pathname))) return 'action';
    return null;
  };
  const announce = message => { feedback.textContent = message; feedback.hidden = !message; };
  const discardPreviews = () => { previews.forEach(url => URL.revokeObjectURL(url)); previews.clear(); };
  const imagePreview = editor => {
    const input = editor.querySelector('input[type=file]');
    const image = editor.querySelector('[data-image-preview]');
    const caption = editor.querySelector('[data-image-caption]');
    if (!input || !image) return;
    const original = image.dataset.original ?? image.getAttribute('src') ?? '';
    image.dataset.original = original;
    if (image.dataset.blob) { URL.revokeObjectURL(image.dataset.blob); previews.delete(image.dataset.blob); delete image.dataset.blob; }
    const cleared = editor.querySelector('input[type=checkbox][name$="-clear"]')?.checked;
    const file = input.files[0];
    if (file && !cleared) {
      const url = URL.createObjectURL(file);
      previews.add(url);
      image.dataset.blob = url;
      image.src = url;
      image.hidden = false;
      caption.textContent = `Prévia: ${file.name}`;
    } else {
      image.hidden = cleared || !original;
      if (original) image.src = original;
      caption.textContent = cleared ? 'A foto será removida ao salvar.' : original ? 'Imagem atual' : 'Nenhuma imagem selecionada';
    }
  };
  const publication = form => {
    const section = form.querySelector('[data-banner-period]');
    if (!section) return;
    const scheduled = form.elements.status.value === 'agendado';
    const values = [form.elements.inicio_exibicao, form.elements.fim_exibicao];
    section.hidden = !scheduled && values.every(input => !input.value) && !section.querySelector('.errorlist');
    values.forEach(input => { input.required = scheduled; });
    section.querySelector('[data-clear-period]').hidden = false;
  };
  const render = (content, target, previousForm = null) => {
    discardPreviews();
    content.querySelectorAll('script').forEach(script => script.remove());
    const form = content.querySelector('form');
    if (form) {
      form.action = target;
      if (previousForm) for (const input of previousForm.querySelectorAll('input[type=file]')) {
        const next = [...form.querySelectorAll('input[type=file]')].find(next => next.name === input.name);
        if (next && input.files.length) next.files = input.files;
      }
    }
    content.querySelector('.sheet-topbar')?.remove();
    body.replaceChildren(content);
    dialog.classList.toggle('ui-modal-confirmation', content.hasAttribute('data-ui-confirmation'));
    const heading = content.querySelector('h1');
    title.textContent = heading?.textContent || 'Formulário';
    heading?.remove();
    body.querySelectorAll('[data-image-editor]').forEach(imagePreview);
    body.querySelectorAll('[data-banner-editor]').forEach(publication);
    const focus = body.querySelector('.form-error-summary, .errorlist') || title;
    if (focus) { focus.tabIndex = -1; focus.focus({preventScroll:true}); }
    body.scrollTop = 0;
  };
  const focusOrigin = () => {
    const replacement = trigger?.isConnected ? trigger : [...document.querySelectorAll('a[href]')].find(link => link.href === trigger?.href);
    const target = replacement || document.querySelector('.page-heading h1, main h1');
    if (target) { if (!replacement) target.tabIndex = -1; target.focus({preventScroll:true}); }
  };
  const refreshSource = async destination => {
    if (standalone) { returnURL = destination; location.assign(destination); return; }
    const source = new URL(location.href);
    const filters = document.querySelector('main form[data-auto-apply]');
    if (filters) for (const [key, value] of new FormData(filters)) {
      if (source.searchParams.get(key) !== value) source.searchParams.delete('page');
      source.searchParams.set(key, value);
    }
    let response = await fetch(source, {credentials:'same-origin', cache:'no-store', signal:AbortSignal.timeout(15000)});
    if (response.status === 404 && source.searchParams.has('page')) {
      source.searchParams.delete('page');
      response = await fetch(source, {credentials:'same-origin', cache:'no-store', signal:AbortSignal.timeout(15000)});
    }
    if (response.status === 404) { location.assign(destination); return; }
    if (!response.ok || response.redirected || response.url !== source.href) throw new Error('Atualize a página para consultar os dados salvos.');
    const page = new DOMParser().parseFromString(await response.text(), 'text/html');
    const next = page.querySelector('[data-page-content]') || page.querySelector('#main-content');
    const current = document.querySelector('[data-page-content]') || document.querySelector('#main-content');
    if (!next || !current) throw new Error('Atualize a página para consultar os dados salvos.');
    next.querySelectorAll('script').forEach(script => script.remove());
    current.replaceChildren(...next.childNodes);
    history.replaceState(null, '', source);
    document.dispatchEvent(new CustomEvent('inovalab:content-updated'));
  };
  const load = async (value, form = null, submitter = null) => {
    if (saving || form?.dataset.uncertain || !mode(value) || (!form && mode(value) === 'action')) return;
    const target = new URL(value, location.href);
    controller?.abort();
    const request = new AbortController();
    controller = request;
    const timeout = setTimeout(() => request.abort(), 20000);
    const data = form ? new FormData(form) : undefined;
    if (data && submitter?.name) data.append(submitter.name, submitter.value);
    saving = Boolean(form);
    closeButton.disabled = saving;
    dialog.setAttribute('aria-busy', 'true');
    const buttons = form ? [...form.querySelectorAll('button[type=submit]')] : [];
    buttons.forEach(button => { button.disabled = true; });
    announce(form ? 'Salvando…' : 'Carregando…');
    let committed = false;
    try {
      const response = await fetch(target, {method:form ? 'POST' : 'GET', body:data,
        credentials:'same-origin', cache:'no-store', signal:request.signal,
        headers:{'X-UI-Modal':'1', 'Accept':'text/html, application/json'}});
      if (controller !== request || !dialog.open) return;
      if (response.redirected || response.url !== target.href) throw new Error('Confira sua sessão e atualize a página.');
      if (response.ok && response.headers.get('Content-Type')?.includes('application/json')) {
        const result = await response.json();
        const destination = new URL(result.redirect_url, location.href);
        const successRoots = [...roots, dialog.dataset.taskRoot, dialog.dataset.agendaRoot].map(root => new URL(root, location.href).pathname);
        if (result.saved !== true || destination.origin !== location.origin || !successRoots.some(root => destination.pathname.startsWith(root))) throw new Error('Resposta inválida.');
        committed = true;
        await refreshSource(destination.href);
        dialog.close();
        return;
      }
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const content = page.querySelector('[data-ui-modal-page]');
      if (!content || (!response.ok && ![400,409].includes(response.status))) throw new Error('Não foi possível concluir. Confira a sessão e a permissão.');
      render(content, target.href, form);
      announce(response.status === 409 ? 'Este registro mudou em outra tela. Recarregue os dados antes de salvar novamente.' : '');
      if (response.status === 409 && mode(target.href) !== 'action') {
        const reload = document.createElement('button');
        reload.type = 'button'; reload.textContent = 'Recarregar formulário';
        reload.addEventListener('click', () => load(target.href));
        feedback.append(' ', reload);
      } else if (response.status === 409) {
        const link = document.createElement('a'); link.href = location.href;
        link.textContent = 'Atualizar página'; feedback.append(' ', link);
      }
    } catch {
      if (controller !== request) return;
      if (form) {
        form.dataset.uncertain = 'true';
        announce(committed ? 'Alteração salva. Atualize a página para consultar os dados.' : 'A resposta não foi confirmada. Consulte a lista antes de enviar novamente.');
      } else {
        announce('Não foi possível carregar. Você pode abrir o formulário completo.');
        const link = document.createElement('a'); link.href = target.href; link.textContent = 'Abrir página completa'; feedback.append(' ', link);
      }
    } finally {
      clearTimeout(timeout);
      if (controller === request) {
        saving = false; controller = null; closeButton.disabled = false; dialog.removeAttribute('aria-busy');
        if (!form?.dataset.uncertain) buttons.forEach(button => { button.disabled = false; });
      }
    }
  };
  const open = (url, source) => {
    document.dispatchEvent(new CustomEvent('inovalab:pause-filters'));
    trigger = source;
    if (!dialog.open) dialog.showModal();
    document.body.classList.add('ui-modal-open');
    load(url);
  };
  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const close = event.target.closest('[data-ui-close]');
    if (dialog.open && close) { event.preventDefault(); if (!saving) dialog.close(); return; }
    const link = event.target.closest('a[href]');
    if (link && !link.target && !link.hasAttribute('download') && ['form','confirmation'].includes(mode(link.href))) { event.preventDefault(); open(link.href, link); }
    const clear = event.target.closest('[data-clear-period]');
    if (clear) { const form = clear.form || clear.closest('form'); form.elements.inicio_exibicao.value = ''; form.elements.fim_exibicao.value = ''; publication(form); }
  });
  dialog.addEventListener('submit', event => {
    event.preventDefault();
    if (event.target.reportValidity()) load(event.target.action, event.target, event.submitter);
  });
  document.addEventListener('submit', event => {
    const source = event.target, button = event.submitter;
    if (event.defaultPrevented || dialog.contains(source) || !button?.dataset.confirmMessage || mode(source.action) !== 'action') return;
    event.preventDefault();
    if (dialog.open || !source.reportValidity()) return;
    document.dispatchEvent(new CustomEvent('inovalab:pause-filters'));
    trigger = button;
    const content = document.createElement('section');
    content.className = 'detail-sheet'; content.setAttribute('data-ui-confirmation', '');
    const section = document.createElement('div'); section.className = 'sheet-content';
    const heading = document.createElement('h1'); heading.textContent = button.dataset.confirmTitle || 'Confirmar ação';
    const text = document.createElement('p'); text.textContent = button.dataset.confirmMessage;
    const form = source.cloneNode(true); form.className = 'sheet-form';
    form.querySelectorAll('button, a').forEach(control => control.remove());
    form.querySelectorAll('[id]').forEach(control => control.removeAttribute('id'));
    if (button.name) { const choice = document.createElement('input'); choice.type = 'hidden'; choice.name = button.name; choice.value = button.value; form.append(choice); }
    const actions = document.createElement('div'); actions.className = 'sheet-actions';
    const confirm = document.createElement('button'); confirm.type = 'submit'; confirm.textContent = button.dataset.confirmTitle || 'Confirmar';
    const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'secondary-button'; cancel.setAttribute('data-ui-close',''); cancel.textContent = 'Voltar';
    actions.append(confirm, cancel); form.append(actions); section.append(heading, text, form); content.append(section);
    dialog.showModal(); document.body.classList.add('ui-modal-open'); render(content, source.action);
  });
  dialog.addEventListener('change', event => {
    const editor = event.target.closest('[data-image-editor]');
    if (editor) imagePreview(editor);
    const banner = event.target.closest('[data-banner-editor]');
    if (banner) publication(banner);
  });
  dialog.addEventListener('cancel', event => { if (saving) event.preventDefault(); });
  dialog.addEventListener('close', () => {
    controller?.abort(); controller = null; saving = false; closeButton.disabled = false;
    dialog.removeAttribute('aria-busy'); discardPreviews(); body.replaceChildren(); announce('');
    document.body.classList.remove('ui-modal-open');
    if (standalone) location.assign(returnURL); else focusOrigin();
  });
  const initial = document.querySelector('main [data-ui-modal-page]');
  if (initial && mode(location.href)) {
    standalone = true;
    returnURL = initial.dataset.uiReturnUrl;
    dialog.showModal(); document.body.classList.add('ui-modal-open');
    render(initial, location.href);
  }
})();
