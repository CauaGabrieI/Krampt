document.querySelectorAll('[data-toast]').forEach((toast) => {
  const fechar = () => {
    if (toast.classList.contains('is-leaving')) return;
    toast.classList.add('is-leaving');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  };

  toast.querySelector('[data-toast-close]')?.addEventListener('click', fechar);
  const persistente = toast.classList.contains('global-toast--error');
  if (!persistente) window.setTimeout(fechar, 6000);
});
