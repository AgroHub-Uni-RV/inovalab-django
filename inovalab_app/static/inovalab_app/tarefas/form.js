(() => {
  const initializeDeadline = root => {
    const selector = root.querySelector('form.task-form [name="agendamento_servico"]');
    const output = root.querySelector('#task-service-deadline');
    const data = root.querySelector('#task-service-deadlines');
    if (!selector || !output || !data) return;
    let deadlines = {};
    try { deadlines = JSON.parse(data.textContent); } catch { return; }
    const update = () => {
      output.textContent = deadlines[selector.value] || 'Selecione um agendamento de serviço.';
    };
    selector.addEventListener('change', update);
    update();
  };

  const initializeChoiceGroups = root => {
    root.querySelectorAll('[data-task-choice-group]').forEach(group => {
      const search = group.querySelector('[data-task-choice-search]');
      const choices = [...group.querySelectorAll('.task-choice-option')];
      const count = group.querySelector('[data-task-choice-count]');
      const empty = group.querySelector('[data-task-choice-empty]');
      const updateCount = () => {
        const selected = choices.filter(choice => choice.querySelector('input')?.checked).length;
        count.textContent = selected ? `${selected} selecionado${selected === 1 ? '' : 's'}` : 'Nenhum selecionado';
      };
      const filter = () => {
        const query = search.value.trim().toLocaleLowerCase('pt-BR');
        let visible = 0;
        choices.forEach(choice => {
          const matches = choice.textContent.toLocaleLowerCase('pt-BR').includes(query);
          choice.hidden = !matches;
          if (matches) visible += 1;
        });
        empty.hidden = visible !== 0;
      };
      group.addEventListener('change', updateCount);
      search?.addEventListener('input', filter);
      updateCount();
    });
  };

  const initializeMaterials = root => {
    const rows = root.querySelector('#task-material-rows');
    const template = root.querySelector('#task-material-template');
    const add = root.querySelector('#task-add-material');
    const total = root.querySelector('[name="materiais-TOTAL_FORMS"]');
    if (!rows || !template || !add || !total) return;

    const renumber = () => {
      [...rows.querySelectorAll('.task-material-row:not([hidden])')].forEach((row, index) => {
        const title = row.querySelector('[data-task-material-title]');
        if (title) title.textContent = `Material ${index + 1}`;
      });
    };
    const prepare = row => {
      if (row.dataset.taskMaterialReady === 'true') return;
      row.dataset.taskMaterialReady = 'true';
      const label = row.querySelector('.task-material-delete');
      const deletion = label?.querySelector('input');
      if (!label || !deletion) return;
      label.hidden = true;
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'task-material-remove';
      remove.textContent = 'Remover';
      remove.setAttribute('aria-label', 'Remover material');
      remove.addEventListener('click', () => {
        deletion.checked = true;
        row.hidden = true;
        renumber();
        add.focus();
      });
      row.querySelector('.task-material-row-heading')?.append(remove);
    };
    rows.querySelectorAll('.task-material-row').forEach(prepare);
    renumber();
    add.addEventListener('click', event => {
      event.preventDefault();
      const index = Number(total.value);
      if (!Number.isInteger(index) || index < 0 || index >= 1000) return;
      const container = document.createElement('template');
      container.innerHTML = template.innerHTML.replace(/__prefix__/g, String(index));
      const row = container.content.firstElementChild;
      rows.append(row);
      prepare(row);
      total.value = String(index + 1);
      renumber();
      row.querySelector('select')?.focus();
    });
  };

  window.initializeTaskForm = root => {
    if (!root || root.dataset.taskFormReady === 'true') return;
    root.dataset.taskFormReady = 'true';
    initializeDeadline(root);
    initializeChoiceGroups(root);
    initializeMaterials(root);
  };

  document.querySelectorAll('.task-form-sheet').forEach(window.initializeTaskForm);
})();
