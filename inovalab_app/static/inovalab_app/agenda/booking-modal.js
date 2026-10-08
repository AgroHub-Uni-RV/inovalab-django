(() => {
  const dialog = document.getElementById('booking-modal');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const body = dialog.querySelector('.booking-modal-body');
  const status = dialog.querySelector('.booking-modal-status');
  const closeButton = dialog.querySelector('[data-booking-close]');
  const paths = new Set([dialog.dataset.createUrl, dialog.dataset.visitUrl]);
  const drafts = new Map();
  let trigger;
  let controller;
  let saving = false;
  let standalone = false;

  const creationURL = value => {
    const url = new URL(value, location.href);
    return url.origin === location.origin && paths.has(url.pathname) ? url : null;
  };
  const announce = (message = '') => {
    status.textContent = message;
    status.hidden = !message;
  };
  const materialFields = form => {
    const choice = form.querySelector('[data-material-proprio]');
    if (!choice) return;
    ['material_gasto', 'material_gasto_gramas'].forEach(name => {
      const field = form.elements.namedItem(name);
      if (!field) return;
      const enabled = choice.value === 'nao';
      field.closest('.form-field').hidden = !enabled;
      field.disabled = !enabled;
      field.required = enabled;
    });
  };
  const saveDraft = () => {
    const form = body.querySelector('form');
    if (form) drafts.set(form.elements.categoria.value, new FormData(form));
  };
  const render = (content, restoreDraft = false) => {
    body.replaceChildren(content);
    const form = body.querySelector('form');
    const draft = form && drafts.get(form.elements.categoria.value);
    if (restoreDraft && draft) {
      [...form.elements].forEach(field => {
        if (!field.name || ['csrfmiddlewaretoken', 'versao'].includes(field.name)) return;
        const values = draft.getAll(field.name);
        if (['radio', 'checkbox'].includes(field.type)) field.checked = values.includes(field.value);
        else if (values.length) field.value = values[0];
      });
    }
    if (form) materialFields(form);
    const focus = body.querySelector('.errorlist, h1');
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
      // Ao concluir antes da resposta, preserve uma nova digitação nos filtros.
      if (!dialog.open && active?.closest('form')) return;
      const restoreTrigger = !dialog.open && active === trigger;
      next.querySelectorAll('script').forEach(script => script.remove());
      document.querySelector('[data-page-content]').replaceWith(next);
      if (restoreTrigger) [...document.querySelectorAll('a[href]')].find(link => link.href === trigger.href)?.focus();
    } catch {
      if (dialog.open) announce('Agendamento salvo. Atualize a página para atualizar a lista.');
    }
  };
  const success = result => {
    const content = document.createElement('section');
    content.className = 'module-page booking-modal-success';
    const title = document.createElement('h1');
    title.textContent = 'Agendamento registrado';
    const message = document.createElement('p');
    message.textContent = result.message;
    const actions = document.createElement('div');
    actions.className = 'sheet-actions';
    const details = document.createElement('a');
    const url = new URL(result.detail_url, location.href);
    if (url.origin !== location.origin) throw new Error('Destino de agendamento inválido.');
    details.href = url.href;
    details.className = 'secondary-button';
    details.textContent = 'Ver detalhes';
    const done = document.createElement('button');
    done.type = 'button';
    done.className = 'primary-button';
    done.dataset.bookingClose = '';
    done.textContent = 'Concluir';
    actions.append(details, done);
    content.append(title, message, actions);
    render(content);
    announce();
    document.dispatchEvent(new CustomEvent('booking:created'));
    refreshSource();
  };
  const load = async (url, form = null) => {
    if (saving || form?.dataset.bookingUncertain === 'true') return;
    const target = creationURL(url);
    if (!target) return;
    controller?.abort();
    const request = new AbortController();
    const timeout = setTimeout(() => request.abort(new DOMException('Tempo de resposta excedido.', 'TimeoutError')), 20000);
    controller = request;
    const data = form ? new FormData(form) : undefined;
    saveDraft();
    saving = Boolean(form);
    closeButton.disabled = saving;
    dialog.setAttribute('aria-busy', 'true');
    const buttons = form ? [...form.querySelectorAll('button[type=submit]')] : [];
    buttons.forEach(button => { button.disabled = true; });
    announce(form ? 'Salvando agendamento…' : 'Carregando…');
    try {
      const response = await fetch(target, {
        method: form ? 'POST' : 'GET', body: data, signal: request.signal,
        credentials: 'same-origin', cache: 'no-store',
        headers: {'Accept': 'text/html, application/json', 'X-Booking-Modal': '1'},
      });
      if (controller !== request || !dialog.open) return;
      if (new URL(response.url).pathname === '/entrar/') {
        location.assign(response.url);
        return;
      }
      if (!creationURL(response.url)) throw new Error('Não foi possível carregar o agendamento.');
      if (response.status === 201 && response.headers.get('Content-Type')?.includes('application/json')) {
        const result = await response.json();
        if (result.created !== true) throw new Error('Não foi possível confirmar o agendamento.');
        if (result.next_url) {
          const next = new URL(result.next_url, location.href);
          if (next.origin !== location.origin) throw new Error('Destino de confirmação inválido.');
          location.assign(next.href);
          return;
        }
        success(result);
        return;
      }
      if ([401, 403].includes(response.status)) {
        announce('Confira sua sessão e permissões para criar agendamentos.');
        return;
      }
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const content = page.querySelector('[data-booking-modal-content]');
      if (!content || (!response.ok && ![400, 409].includes(response.status))) {
        throw new Error('Não foi possível carregar o agendamento.');
      }
      content.querySelectorAll('script').forEach(script => script.remove());
      render(content, !form);
      announce(response.status === 409 ? 'Confira o conflito informado no formulário.' : '');
    } catch (error) {
      if (controller !== request || error.name === 'AbortError') return;
      if (form) {
        // Sem confirmação da resposta, não reenviar um POST que pode ter sido salvo.
        form.dataset.bookingUncertain = 'true';
        buttons.length = 0;
        announce('Não foi possível confirmar a resposta. Consulte Meus agendamentos antes de reenviar.');
        const link = document.createElement('a');
        link.href = dialog.dataset.mineUrl;
        link.textContent = 'Meus agendamentos';
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
    document.body.classList.add('booking-modal-open');
    load(url);
  };
  const close = () => { if (!saving) dialog.close(); };
  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (dialog.open && event.target.closest('[data-booking-close]')) { close(); return; }
    const link = event.target.closest('a[href]');
    if (!link || link.target || link.hasAttribute('download') || !creationURL(link.href)) return;
    event.preventDefault();
    if (dialog.open) load(link.href);
    else open(link.href, link);
  });
  dialog.addEventListener('submit', event => {
    const form = event.target;
    if (!form.matches('form.sheet-form')) return;
    event.preventDefault();
    if (form.reportValidity()) load(form.action, form);
  });
  dialog.addEventListener('change', event => {
    if (event.target.matches('[data-material-proprio]')) materialFields(event.target.form);
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
    document.body.classList.remove('booking-modal-open');
    body.replaceChildren();
    drafts.clear();
    announce();
    if (standalone) location.assign(dialog.dataset.mineUrl);
    else if (trigger?.isConnected) trigger.focus();
    else if (trigger) [...document.querySelectorAll('a[href]')].find(link => link.href === trigger.href)?.focus();
  });
  const initial = document.querySelector('[data-booking-create-page]');
  if (initial) {
    standalone = true;
    initial.querySelectorAll('.sheet-topbar a:not([data-booking-step])').forEach(link => link.remove());
    // Ao mover a ficha, preserve o mesmo contêiner de estilos dos fragmentos.
    const content = document.createElement('div');
    content.className = 'module-page detail-page';
    content.append(initial);
    dialog.showModal();
    document.body.classList.add('booking-modal-open');
    render(content);
  }
})();
