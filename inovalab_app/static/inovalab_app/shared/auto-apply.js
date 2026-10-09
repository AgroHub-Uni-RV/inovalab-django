(() => {
  const main = document.getElementById('main');
  const status = document.getElementById('async-update-status');
  if (!main || !status) return;
  const pagePath = location.pathname;
  let pending;
  let debounce;
  let statusTimer;

  const announce = (message = '', retry = null) => {
    clearTimeout(statusTimer);
    status.replaceChildren(document.createTextNode(message));
    status.hidden = !message;
    if (retry) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = 'Tentar novamente';
      button.addEventListener('click', retry);
      status.append(button);
    }
  };

  const cancelRequest = () => {
    if (!pending) return;
    pending.controller.abort();
    pending.restore();
    pending = null;
    main.removeAttribute('aria-busy');
    announce();
  };

  const updateMaterial = field => {
    const usesLabMaterial = field.value === 'nao';
    ['id_material_gasto', 'id_material_gasto_gramas'].forEach(id => {
      const input = field.form?.querySelector(`#${id}`);
      if (!input) return;
      input.closest('.form-field').hidden = !usesLabMaterial;
      input.disabled = !usesLabMaterial;
      input.required = usesLabMaterial;
    });
  };

  const saveFocus = () => {
    const active = document.activeElement;
    if (!active?.closest('[data-page-content]')) return null;
    return {active, start: active.selectionStart, end: active.selectionEnd};
  };

  const restoreFocus = saved => {
    if (!saved) return;
    let field = saved.active.isConnected ? saved.active : document.getElementById(saved.active.id);
    if (!field && saved.active.href) {
      field = [...main.querySelectorAll('a')].find(link => link.href === saved.active.href);
    }
    (field || main).focus({preventScroll: true});
    if (field?.setSelectionRange && typeof saved.start === 'number') {
      field.setSelectionRange(saved.start, saved.end);
    }
  };

  const load = async ({url, method = 'GET', data, form, render, retry, onError}) => {
    const controller = new AbortController();
    // Somente os campos dependentes e Salvar aguardam a troca de categoria.
    // Campos comuns continuam editáveis; o DOM deles não é substituído.
    const disabled = new Map();
    if (method === 'POST') {
      form.querySelectorAll('[data-refresh-field] input, [data-refresh-field] select, [data-refresh-field] textarea, button[type=submit], input[type=submit]').forEach(input => {
        disabled.set(input, input.disabled);
        input.disabled = true;
      });
      form.setAttribute('aria-busy', 'true');
    }
    const request = {controller, form, restore: () => {
      disabled.forEach((wasDisabled, input) => { input.disabled = wasDisabled; });
      form?.removeAttribute('aria-busy');
    }};
    pending = request;
    main.setAttribute('aria-busy', 'true');
    announce('Atualizando…');
    try {
      const response = await fetch(url, {
        method, body: data, signal: controller.signal, credentials: 'same-origin', cache: 'no-store',
        headers: {'Accept': 'text/html', 'X-Requested-With': 'XMLHttpRequest'},
      });
      if (new URL(response.url).pathname !== new URL(url).pathname) {
        throw new Error('Sua sessão pode ter expirado. Entre novamente para continuar.');
      }
      if (!response.ok) {
        const error = new Error(response.status === 403 ? 'Acesso negado. Confira sua sessão e permissões.' :
          'Não foi possível atualizar o conteúdo. Tente novamente.');
        error.status = response.status;
        throw error;
      }
      const html = await response.text();
      if (pending !== request) return;
      const page = new DOMParser().parseFromString(html, 'text/html');
      page.querySelectorAll('script').forEach(script => script.remove());
      const focus = saveFocus();
      const scroll = {x: scrollX, y: scrollY};
      render(page);
      document.title = page.title;
      restoreFocus(focus);
      window.scrollTo(scroll.x, scroll.y);
      announce('Conteúdo atualizado.');
      statusTimer = setTimeout(() => announce(), 1500);
    } catch (error) {
      if (pending !== request || error.name === 'AbortError') return;
      if (onError?.(error) === true) return;
      announce(error.message === 'Failed to fetch' ? 'Não foi possível conectar. Tente novamente.' : error.message, retry);
    } finally {
      if (pending === request) {
        request.restore();
        pending = null;
        main.removeAttribute('aria-busy');
      }
    }
  };

  const filterPage = (url, {restoreForm = false, historyMode = 'push', recoverPage = false} = {}) => {
    clearTimeout(debounce);
    cancelRequest();
    const form = main.querySelector('form[data-auto-apply]');
    if (!form || new URL(url).origin !== location.origin) return;
    load({url, form, onError: error => {
      const firstPage = new URL(url);
      if (recoverPage && error.status === 404 && firstPage.searchParams.has('page')) {
        firstPage.searchParams.delete('page');
        filterPage(firstPage, {historyMode});
        return true;
      }
    }, retry: () => restoreForm ? filterPage(url, {restoreForm, historyMode}) :
      applyFilters(main.querySelector('form[data-auto-apply]')), render: page => {
      const incoming = page.querySelector('[data-page-content]');
      const nextForm = incoming?.querySelector('form[data-auto-apply]');
      if (!nextForm) throw new Error('Não foi possível atualizar os filtros. Tente novamente.');
      // Preserva o campo, a digitação e o cursor nas consultas automáticas.
      // Abas, paginação e Voltar/Avançar recuperam os valores da URL.
      if (!restoreForm) nextForm.replaceWith(form);
      main.querySelector('[data-page-content]').replaceWith(incoming);
      if (historyMode === 'push' && location.href !== String(url)) {
        history.pushState({inovalabFilters: true}, '', url);
      }
    }});
  };

  const applyFilters = form => {
    if (!form.checkValidity()) return;
    const url = new URL(form.action);
    url.search = new URLSearchParams(new FormData(form)).toString();
    filterPage(url);
  };

  document.addEventListener('inovalab:refresh-filters', () => {
    const form = main.querySelector('form[data-auto-apply]');
    if (!form) return;
    const url = new URL(location.href);
    let changed = false;
    for (const [name, value] of new FormData(form)) {
      changed ||= (url.searchParams.get(name) || '') !== value;
      url.searchParams.set(name, value);
    }
    // Preserva os filtros ainda em digitação e a página atual quando válida.
    // Busca nova ou última página esvaziada retorna à primeira página.
    if (changed) url.searchParams.delete('page');
    filterPage(url, {recoverPage:true});
  });

  const refreshCategory = (form, field, value = field.value) => {
    clearTimeout(debounce);
    cancelRequest();
    field.value = value;
    const data = new FormData(form);
    data.set('atualizar', '1');
    load({url: form.action, method: 'POST', data, form,
      retry: () => refreshCategory(form, field, value),
      onError: () => { field.value = form.dataset.bookingCategory; },
      render: page => {
        const nextForm = page.querySelector('form[data-booking-category]');
        if (!nextForm || nextForm.dataset.bookingCategory !== value) {
          throw new Error('Não foi possível atualizar as opções. A categoria anterior foi mantida.');
        }
        const grid = form.querySelector('.form-grid');
        const newFields = [...nextForm.querySelectorAll('[data-refresh-field]')];
        const currentFields = [...grid.querySelectorAll('[data-booking-field]')];
        currentFields.filter(node => node.hasAttribute('data-refresh-field')).forEach(node => {
          const replacement = newFields.find(next => next.dataset.bookingField === node.dataset.bookingField);
          if (replacement) node.replaceWith(replacement);
          else node.remove();
        });
        newFields.filter(node => !grid.contains(node)).forEach(node => {
          // Mantém a ordem dos campos fornecida pelo formulário Django.
          const following = [...node.parentElement.children].slice([...node.parentElement.children].indexOf(node)+1);
          const next = following.map(sibling => currentFields.find(current =>
            current.dataset.bookingField === sibling.dataset.bookingField && grid.contains(current))).find(Boolean);
          grid.insertBefore(node, next || null);
        });
        ['hora_inicio', 'hora_termino'].forEach(name => {
          const input = form.elements.namedItem(name);
          const next = nextForm.elements.namedItem(name);
          if (!input || !next) return;
          input.step = next.step;
          // Os horários das categorias usam minutos; mantenha a digitação existente.
          const normalized = input.value.replace(/^(\d{2}:\d{2}):00(?:\.0+)?$/, '$1');
          if (normalized !== input.value) input.value = normalized;
          const container = input.closest('[data-booking-field]');
          const help = container.querySelector('.field-help');
          const nextHelp = next.closest('[data-booking-field]').querySelector('.field-help');
          if (help && nextHelp) help.replaceWith(nextHelp.cloneNode(true));
          else if (help) help.remove();
          else if (nextHelp) container.append(nextHelp.cloneNode(true));
        });
        form.dataset.bookingCategory = value;
        form.querySelectorAll('[data-material-proprio]').forEach(updateMaterial);
      },
    });
  };

  document.addEventListener('submit', event => {
    const form = event.target;
    if (form.matches('form[data-auto-apply]') && form.method.toLowerCase() === 'get') {
      event.preventDefault();
      clearTimeout(debounce);
      applyFilters(form);
    } else if (pending?.form === form && form.querySelector('[data-auto-refresh]')) {
      // Nunca transforma uma atualização de opções em gravação do agendamento.
      event.preventDefault();
    }
  });

  const scheduleFilters = event => {
    const form = event.target.form;
    if (!form?.matches('form[data-auto-apply]') || form.method.toLowerCase() !== 'get') return;
    clearTimeout(debounce);
    cancelRequest();
    announce();
    if (!event.isComposing) debounce = setTimeout(() => applyFilters(form), 600);
  };
  document.addEventListener('input', scheduleFilters);
  document.addEventListener('compositionend', scheduleFilters);
  document.addEventListener('change', event => {
    const field = event.target;
    if (field.matches('[data-material-proprio]')) updateMaterial(field);
    const form = field.form;
    if (!form) return;
    if (field.matches('[data-auto-refresh]') && form.method.toLowerCase() === 'post') {
      refreshCategory(form, field);
    } else if (form.matches('form[data-auto-apply]') && form.method.toLowerCase() === 'get' &&
        (field.tagName === 'SELECT' || (field.tagName === 'INPUT' && field.type !== 'text'))) {
      clearTimeout(debounce);
      applyFilters(form);
    }
  });

  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('.module-tabs a, .pagination a, a[data-clear-filters]');
    if (!link || link.target || link.hasAttribute('download') || !main.contains(link) ||
        !main.querySelector('form[data-auto-apply]')) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin || url.pathname !== pagePath) return;
    event.preventDefault();
    if (link.matches('[data-clear-filters]')) {
      // Use the clean destination, including blank month when the agenda defaults it.
      // Never merge pending input, selected tabs or pagination into a reset.
      filterPage(url, {restoreForm: true});
      return;
    }
    const tab = link.closest('.module-tabs');
    let filterChanged = false;
    const current = new URL(location.href);
    for (const [name, value] of new FormData(main.querySelector('form[data-auto-apply]'))) {
      if (tab && (name === 'status' || name === 'tab')) continue;
      filterChanged ||= (current.searchParams.get(name) || '') !== value;
      url.searchParams.set(name, value);
    }
    // Uma aba não descarta texto digitado antes dos 600 ms de espera.
    // Uma consulta nova começa na primeira página, mesmo ao clicar na paginação.
    if (tab || filterChanged) url.searchParams.delete('page');
    filterPage(url, {restoreForm: true});
  });
  window.addEventListener('popstate', () => {
    if (location.pathname === pagePath && main.querySelector('form[data-auto-apply]')) {
      filterPage(location.href, {restoreForm: true, historyMode: 'none'});
    }
  });
  document.querySelectorAll('[data-material-proprio]').forEach(updateMaterial);
})();
