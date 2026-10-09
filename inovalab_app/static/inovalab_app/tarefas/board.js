(() => {
  const main = document.getElementById('main');
  if (!main?.querySelector('.task-board')) return;
  document.documentElement.classList.add('task-moves-enabled');
  const feedback = document.createElement('div');
  feedback.id = 'task-board-feedback';
  feedback.className = 'task-board-feedback';
  feedback.setAttribute('role', 'status');
  feedback.setAttribute('aria-live', 'polite');
  feedback.hidden = true;
  const notices = document.createElement('div');
  notices.className = 'task-board-notices';
  notices.append(feedback);
  const filterFeedback = document.getElementById('async-update-status');
  if (filterFeedback) notices.append(filterFeedback);
  main.after(notices);
  const pending = new Set();
  let dragged = null;
  const announce = message => {
    feedback.textContent = message;
    feedback.hidden = !message;
  };
  const destinations = card => [...card.querySelectorAll('select[name=status] option')]
    .map(option => option.value).filter(Boolean);
  const clearDrag = () => {
    document.querySelectorAll('.task-drop-allowed, .task-drop-active, .task-dragging').forEach(node =>
      node.classList.remove('task-drop-allowed', 'task-drop-active', 'task-dragging'));
    dragged = null;
  };
  const save = async (card, status) => {
    const id = card.dataset.taskId;
    if (pending.has(id) || !destinations(card).includes(status)) return;
    const form = card.querySelector('[data-task-move]');
    const version = Number(form.elements.versao.value);
    const token = form.elements.csrfmiddlewaretoken.value;
    pending.add(id);
    card.setAttribute('aria-busy', 'true');
    form.querySelectorAll('select, button').forEach(field => {field.disabled = true;});
    announce(`Salvando status da tarefa #${id}…`);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(form.dataset.apiUrl, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', signal:controller.signal,
        headers: {'Content-Type':'application/json', 'Accept':'application/json', 'X-CSRFToken':token},
        body: JSON.stringify({status, versao:version}),
      });
      if (response.redirected || !response.headers.get('Content-Type')?.includes('application/json')) {
        throw new Error('Sua sessão pode ter expirado. Atualize a página e entre novamente.');
      }
      const data = await response.json();
      if (!response.ok) {
        throw new Error(response.status === 409 ? 'A tarefa foi alterada por outra pessoa. Confira o quadro atualizado antes de tentar novamente.' :
          response.status === 403 || response.status === 404 ? 'Você não tem mais permissão para mover esta tarefa. Confira o quadro atualizado.' :
          'Não foi possível alterar o status. Confira o quadro atualizado antes de tentar novamente.');
      }
      if (data.id !== Number(id) || data.status !== status || !Number.isInteger(data.versao)) {
        throw new Error('Não foi possível confirmar a alteração. Confira o quadro atualizado.');
      }
      announce(`Status da tarefa #${id} atualizado.`);
    } catch (error) {
      announce(error.name === 'AbortError' ? 'A conexão demorou demais. Não foi possível confirmar a alteração. Confira o quadro atualizado antes de tentar novamente.' :
        error instanceof TypeError ? 'Não foi possível confirmar a alteração por falha de conexão. Confira o quadro atualizado antes de tentar novamente.' : error.message);
    } finally {
      clearTimeout(timeout);
      pending.delete(id);
      card.removeAttribute('aria-busy');
      form.querySelectorAll('select, button').forEach(field => {field.disabled = false;});
      form.elements.status.value = '';
      // Reconsulta o estado persistido mesmo se a conexão cair após a gravação.
      // Nunca repete automaticamente o POST nem move o cartão de modo otimista.
      const refresh = new CustomEvent('inovalab:refresh-filters', {cancelable:true});
      if (document.dispatchEvent(refresh)) {
        // Um script compartilhado antigo/em cache pode ignorar o evento.
        // Nesse caso, recarrega por GET, sem repetir a alteração de status.
        const url = new URL(location.href);
        const filters = main.querySelector('form[data-auto-apply]');
        if (filters) {
          for (const [name, value] of new FormData(filters)) url.searchParams.set(name, value);
        }
        url.searchParams.delete('page');
        location.replace(url);
      }
    }
  };
  document.addEventListener('submit', event => {
    if (!event.target.matches('[data-task-move]')) return;
    event.preventDefault();
    const form = event.target;
    if (form.checkValidity()) save(form.closest('[data-task-id]'), form.elements.status.value);
  });
  document.addEventListener('dragstart', event => {
    const handle = event.target.closest('[data-task-drag]');
    if (!handle) return;
    const card = handle.closest('[data-task-id]');
    if (pending.has(card.dataset.taskId)) {event.preventDefault(); return;}
    dragged = card;
    card.classList.add('task-dragging');
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', card.dataset.taskId);
    event.dataTransfer.setDragImage(card, 20, 20);
    const allowed = destinations(card);
    main.querySelectorAll('[data-task-column]').forEach(column => {
      if (allowed.includes(column.dataset.taskColumn)) column.classList.add('task-drop-allowed');
    });
    announce('Solte em uma coluna destacada para alterar o status.');
  });
  document.addEventListener('dragover', event => {
    const column = event.target.closest('[data-task-column]');
    if (!dragged || !column?.classList.contains('task-drop-allowed')) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    main.querySelectorAll('.task-drop-active').forEach(node => node.classList.remove('task-drop-active'));
    column.classList.add('task-drop-active');
  });
  document.addEventListener('dragleave', event => {
    const column = event.target.closest('[data-task-column]');
    if (column && !column.contains(event.relatedTarget)) column.classList.remove('task-drop-active');
  });
  document.addEventListener('drop', event => {
    const column = event.target.closest('[data-task-column]');
    if (!dragged || !column?.classList.contains('task-drop-allowed')) return;
    event.preventDefault();
    const card = dragged;
    const status = column.dataset.taskColumn;
    clearDrag();
    save(card, status);
  });
  document.addEventListener('dragend', clearDrag);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && dragged) {clearDrag(); announce('Movimento cancelado.');}
  });
})();
