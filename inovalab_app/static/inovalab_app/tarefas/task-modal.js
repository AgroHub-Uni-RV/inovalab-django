(() => {
  const dialog = document.getElementById('task-modal');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const body = dialog.querySelector('.task-modal-body');
  const status = dialog.querySelector('.task-modal-status');
  const closeButton = dialog.querySelector('[data-task-close]');
  let trigger;
  let controller;
  let saving = false;
  let standalone = false;
  let standaloneReturn = dialog.dataset.boardUrl;
  const createPath = new URL(dialog.dataset.createUrl, location.href).pathname;
  const loginURL = new URL(dialog.dataset.loginUrl, location.href);
  const taskRoot = createPath.slice(0, -'nova/'.length);
  const escapedRoot = taskRoot.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const updatePath = new RegExp(`^${escapedRoot}\\d+/editar/$`);
  const detailPath = new RegExp(`^${escapedRoot}\\d+/$`);

  const taskURL = value => {
    const url = new URL(value, location.href);
    const allowed = url.pathname === createPath || updatePath.test(url.pathname);
    return url.origin === location.origin && allowed ? url : null;
  };
  const isLoginURL = value => {
    const url = new URL(value, location.href);
    return url.origin === loginURL.origin && url.pathname === loginURL.pathname &&
      [...loginURL.searchParams].every(([key, expected]) => url.searchParams.getAll(key).includes(expected));
  };
  const announce = (message = '') => {
    status.textContent = message;
    status.hidden = !message;
  };
  const render = content => {
    body.replaceChildren(content);
    body.querySelectorAll('.task-form-sheet').forEach(window.initializeTaskForm || (() => {}));
    const focus = body.querySelector('.form-error-summary, .errorlist, h1');
    if (focus) {
      focus.tabIndex = -1;
      focus.focus({preventScroll: true});
    }
    dialog.scrollTop = 0;
  };
  const refreshSource = async () => {
    if (standalone || !document.querySelector('[data-page-content]')) return;
    const url = location.href;
    try {
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok || response.url !== url) return;
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const next = page.querySelector('[data-page-content]');
      if (!next || location.href !== url) return;
      const active = document.activeElement;
      if (!dialog.open && active?.closest('form')) return;
      const restoreTrigger = !dialog.open && active === trigger;
      next.querySelectorAll('script').forEach(script => script.remove());
      document.querySelector('[data-page-content]').replaceWith(next);
      if (restoreTrigger) [...document.querySelectorAll('a[data-task-modal-trigger][href]')]
        .find(link => link.href === trigger.href)?.focus();
    } catch {
      if (dialog.open) announce('Tarefa salva. Atualize a página para atualizar os dados exibidos.');
    }
  };
  const showSuccess = result => {
    const content = document.createElement('section');
    content.className = 'module-page task-modal-success';
    const eyebrow = document.createElement('p');
    eyebrow.className = 'form-eyebrow';
    eyebrow.textContent = 'Tudo certo';
    const title = document.createElement('h1');
    title.textContent = 'Tarefa salva';
    const message = document.createElement('p');
    message.textContent = result.message;
    const actions = document.createElement('div');
    actions.className = 'sheet-actions';
    const details = document.createElement('a');
    const url = new URL(result.detail_url, location.href);
    if (url.origin !== location.origin || !detailPath.test(url.pathname)) {
      throw new Error('Destino de tarefa inválido.');
    }
    details.href = url.href;
    details.className = 'secondary-button';
    details.textContent = 'Ver tarefa';
    const done = document.createElement('button');
    done.type = 'button';
    done.className = 'primary-button';
    done.dataset.taskClose = '';
    done.textContent = 'Concluir';
    actions.append(details, done);
    content.append(eyebrow, title, message, actions);
    render(content);
    announce();
    document.dispatchEvent(new CustomEvent('task:saved', {detail: result}));
    refreshSource();
  };
  const load = async (url, form = null) => {
    if (saving || form?.dataset.taskUncertain === 'true') return;
    const target = taskURL(url);
    if (!target) return;
    controller?.abort();
    const request = new AbortController();
    const timeout = setTimeout(() => request.abort(new DOMException('Tempo de resposta excedido.', 'TimeoutError')), 20000);
    controller = request;
    saving = Boolean(form);
    closeButton.disabled = saving;
    dialog.setAttribute('aria-busy', 'true');
    const buttons = form ? [...form.querySelectorAll('button[type=submit]')] : [];
    buttons.forEach(button => { button.disabled = true; });
    announce(form ? 'Salvando tarefa…' : 'Carregando…');
    try {
      const response = await fetch(target, {
        method: form ? 'POST' : 'GET',
        body: form ? new FormData(form) : undefined,
        signal: request.signal,
        credentials: 'same-origin',
        cache: 'no-store',
        headers: {'Accept': 'text/html, application/json', 'X-Task-Modal': '1'},
      });
      if (controller !== request || !dialog.open) return;
      if (isLoginURL(response.url)) {
        location.assign(response.url);
        return;
      }
      if (!taskURL(response.url)) throw new Error('Não foi possível carregar a tarefa.');
      if ([200, 201].includes(response.status) && response.headers.get('Content-Type')?.includes('application/json')) {
        const result = await response.json();
        if (result.saved !== true) throw new Error('Não foi possível salvar a tarefa.');
        showSuccess(result);
        return;
      }
      if ([401, 403].includes(response.status)) {
        announce('Confira sua sessão e sua permissão para gerenciar tarefas.');
        return;
      }
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const content = page.querySelector('[data-task-modal-content]');
      if (!content || (!response.ok && response.status !== 409)) {
        throw new Error('Não foi possível carregar a tarefa.');
      }
      content.querySelectorAll('script:not([type="application/json"])').forEach(script => script.remove());
      render(content);
      announce(response.status === 409 ? 'A tarefa foi alterada em outra tela. Confira os dados antes de tentar novamente.' : '');
    } catch (error) {
      if (controller !== request || error.name === 'AbortError') return;
      if (form) {
        form.dataset.taskUncertain = 'true';
        announce('Não foi possível confirmar a resposta. Consulte o quadro antes de reenviar.');
        const link = document.createElement('a');
        link.href = dialog.dataset.boardUrl;
        link.textContent = 'Abrir quadro de tarefas';
        status.append(' ', link);
      } else {
        announce('Não foi possível carregar. Tente novamente.');
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.textContent = 'Tentar novamente';
        retry.addEventListener('click', () => load(target));
        status.append(' ', retry);
      }
    } finally {
      clearTimeout(timeout);
      if (controller === request) {
        saving = false;
        controller = null;
        closeButton.disabled = false;
        dialog.removeAttribute('aria-busy');
        buttons.forEach(button => { button.disabled = false; });
      }
    }
  };
  const open = (url, source) => {
    trigger = source;
    if (!dialog.open) dialog.showModal();
    document.body.classList.add('task-modal-open');
    load(url);
  };
  const close = () => { if (!saving) dialog.close(); };

  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (dialog.open && event.target.closest('[data-task-close]')) {
      event.preventDefault();
      close();
      return;
    }
    const link = event.target.closest('a[data-task-modal-trigger][href]');
    if (!link || link.target || link.hasAttribute('download') || !taskURL(link.href)) return;
    event.preventDefault();
    open(link.href, link);
  });
  dialog.addEventListener('submit', event => {
    const form = event.target;
    if (!form.matches('form.task-form')) return;
    event.preventDefault();
    if (form.reportValidity()) load(form.action, form);
  });
  document.addEventListener('keydown', event => {
    if (!dialog.open) return;
    if (event.key === 'Escape') event.stopPropagation();
    if (event.key === 'Tab') {
      event.stopPropagation();
      const controls = [...dialog.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea, [tabindex]')]
        .filter(control => !control.disabled && control.tabIndex >= 0 && control.getClientRects().length);
      const first = controls[0], last = controls[controls.length - 1];
      const active = document.activeElement;
      if (!controls.includes(active) || (event.shiftKey ? active === first : active === last)) {
        event.preventDefault();
        (event.shiftKey ? last : first)?.focus();
      }
    }
  }, true);
  dialog.addEventListener('cancel', event => { if (saving) event.preventDefault(); });
  dialog.addEventListener('click', event => {
    const rect = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right ||
        event.clientY < rect.top || event.clientY > rect.bottom)) close();
  });
  dialog.addEventListener('close', () => {
    controller?.abort();
    controller = null;
    document.body.classList.remove('task-modal-open');
    body.replaceChildren();
    announce();
    if (standalone) location.assign(standaloneReturn);
    else if (trigger?.isConnected) trigger.focus();
    else if (trigger) [...document.querySelectorAll('a[data-task-modal-trigger][href]')]
      .find(link => link.href === trigger.href)?.focus();
  });

  const initial = document.querySelector('[data-task-write-page]');
  if (initial) {
    standalone = true;
    standaloneReturn = initial.dataset.taskReturnUrl || dialog.dataset.boardUrl;
    initial.querySelector('.sheet-topbar a')?.remove();
    initial.querySelector('.task-form-actions a[href]')?.setAttribute('data-task-close', '');
    const content = document.createElement('div');
    content.className = 'module-page detail-page';
    content.append(initial);
    dialog.showModal();
    document.body.classList.add('task-modal-open');
    render(content);
  }
})();
