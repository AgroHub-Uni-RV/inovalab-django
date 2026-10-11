(() => {
  let saving = false;
  const initialize = () => document.querySelectorAll('[data-status-autosave]').forEach(form => {
    form.classList.add('task-status-autosave');
    form.elements.status.disabled = form.querySelector('.task-status-save').disabled;
  });
  const announce = (message, scope = document) => {
    const feedback = scope.querySelector('[data-status-feedback]');
    if (feedback) { feedback.textContent = message; feedback.hidden = !message; }
  };
  const refresh = async (form, message) => {
    const target = new URL(form.dataset.detailUrl, location.href);
    const response = await fetch(target, {credentials:'same-origin', cache:'no-store', signal:AbortSignal.timeout(15000)});
    if (!response.ok || response.redirected || response.url !== target.href) throw new Error('Não foi possível atualizar a tarefa.');
    const page = new DOMParser().parseFromString(await response.text(), 'text/html');
    const next = page.querySelector('.detail-sheet');
    if (!next?.querySelector('[data-status-autosave]')) throw new Error('Confira sua sessão e atualize a página.');
    const focused = document.activeElement === form.elements.status;
    form.closest('.detail-sheet').replaceWith(next);
    initialize();
    window.initializeTaskTimer?.();
    announce(message, next);
    if (focused) next.querySelector('[name=status]').focus({preventScroll:true});
  };
  document.addEventListener('change', async event => {
    const field = event.target;
    const form = field.form;
    if (!form?.matches('[data-status-autosave]') || field.name !== 'status' || saving || form.dataset.uncertain) return;
    const status = field.value;
    const version = Number(form.elements.versao.value);
    const endpoint = new URL(form.dataset.apiUrl, location.href);
    if (endpoint.origin !== location.origin) return;
    saving = true;
    field.disabled = true;
    form.setAttribute('aria-busy', 'true');
    announce('Salvando status…');
    let message;
    try {
      const response = await fetch(endpoint, {
        method:'POST', credentials:'same-origin', cache:'no-store', signal:AbortSignal.timeout(15000),
        headers:{'Content-Type':'application/json', 'Accept':'application/json',
          'X-CSRFToken':form.elements.csrfmiddlewaretoken.value},
        body:JSON.stringify({status, versao:version}),
      });
      if (response.redirected || !response.headers.get('Content-Type')?.includes('application/json')) throw new Error('Confira sua sessão.');
      const data = await response.json();
      if (!response.ok) {
        message = response.status === 409 ? 'A tarefa mudou em outra tela. Os dados atuais foram carregados; confira antes de alterar novamente.' :
          'O status não foi salvo. Confira as permissões e os dados atuais da tarefa.';
      } else {
        if (data.id !== Number(form.dataset.taskId) || data.status !== status || !Number.isInteger(data.versao) || data.versao < version) throw new Error('Resposta inválida.');
        message = 'Status salvo automaticamente.';
      }
    } catch {
      message = 'A resposta não foi confirmada. Consulte os dados atualizados antes de alterar novamente.';
    }
    try {
      await refresh(form, message);
    } catch {
      form.dataset.uncertain = 'true';
      announce('Não foi possível consultar o estado atual. Atualize a página antes de alterar o status novamente.');
      const feedback = document.querySelector('[data-status-feedback]');
      const link = document.createElement('a');
      link.href = form.dataset.detailUrl;
      link.textContent = 'Atualizar tarefa';
      feedback?.append(' ', link);
    } finally {
      saving = false;
      form.removeAttribute('aria-busy');
    }
  });
  document.addEventListener('submit', event => {
    if (event.target.matches('[data-status-autosave]')) event.preventDefault();
  });
  initialize();
})();
