(() => {
  const selector = document.querySelector('form.sheet-form [name="agendamento_servico"]');
  const output = document.querySelector('#task-service-deadline');
  const data = document.querySelector('#task-service-deadlines');
  if (!selector || !output || !data) return;
  const deadlines = JSON.parse(data.textContent);
  const update = () => {
    output.textContent = deadlines[selector.value] || 'Selecione um agendamento de serviço.';
  };
  selector.addEventListener('change', update);
  update();
})();

(() => {
  const rows = document.querySelector('#task-material-rows');
  const template = document.querySelector('#task-material-template');
  const add = document.querySelector('#task-add-material');
  const total = document.querySelector('[name="materiais-TOTAL_FORMS"]');
  if (!rows || !template || !add || !total) return;
  const prepare = row => {
    const label = row.querySelector('.task-material-delete');
    const deletion = label.querySelector('input');
    label.hidden = true;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'secondary-button';
    remove.textContent = 'Remover material';
    remove.addEventListener('click', () => {
      deletion.checked = true;
      row.hidden = true;
      add.focus();
    });
    row.append(remove);
  };
  rows.querySelectorAll('.task-material-row').forEach(prepare);
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
    row.querySelector('select').focus();
  });
})();
