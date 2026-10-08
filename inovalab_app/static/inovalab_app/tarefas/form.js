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
