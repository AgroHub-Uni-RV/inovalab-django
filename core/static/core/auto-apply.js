(() => {
  const focusKey = `inovalab.filter-focus:${location.pathname}`;
  try {
    const saved = JSON.parse(sessionStorage.getItem(focusKey));
    sessionStorage.removeItem(focusKey);
    if (saved) {
      const field = document.getElementById(saved.id);
      if (field?.closest('form[data-auto-apply]')) {
        field.focus();
        if (typeof saved.start === 'number' && field.type === 'text') {
          field.setSelectionRange(saved.start, saved.end);
        }
      }
    }
  } catch { /* A consulta funciona mesmo sem armazenamento disponível. */ }
  document.querySelectorAll('form[data-auto-apply]').forEach(form => {
    // Somente consultas GET podem aplicar o formulário inteiro automaticamente.
    if (form.method.toLowerCase() !== 'get') return;
    let timer;
    let submitting = false;
    const apply = () => {
      clearTimeout(timer);
      if (submitting || !form.checkValidity()) return;
      const field = document.activeElement;
      if (field?.form === form && field.id) {
        try {
          sessionStorage.setItem(focusKey, JSON.stringify({
            id: field.id, start: field.selectionStart, end: field.selectionEnd,
          }));
        } catch { /* O armazenamento de foco é opcional. */ }
      }
      form.requestSubmit();
    };
    form.addEventListener('submit', () => {
      clearTimeout(timer);
      submitting = true;
    });
    form.addEventListener('input', event => {
      clearTimeout(timer);
      if (event.isComposing || !event.target.matches('input:not([type=hidden]), textarea')) return;
      timer = setTimeout(apply, 600);
    });
    form.addEventListener('change', event => {
      if (event.target.matches('select, input:not([type=hidden])')) apply();
    });
  });

  // Atualiza apenas as opções dependentes; nunca aciona o botão de salvar.
  document.querySelectorAll('[data-auto-refresh]').forEach(field => {
    const button = field.form?.querySelector('button[name="atualizar"][value="1"]');
    if (button) field.addEventListener('change', () => field.form.requestSubmit(button));
  });
})();
