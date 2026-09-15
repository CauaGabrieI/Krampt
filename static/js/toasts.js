function setupToast(toast) {
  const fechar = () => {
    if (toast.classList.contains('is-leaving')) return;
    toast.classList.add('is-leaving');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  };

  toast.querySelector('[data-toast-close]')?.addEventListener('click', fechar);
  const persistente = toast.classList.contains('global-toast--error');
  if (!persistente) window.setTimeout(fechar, 6000);
}

window.KramptToast = function (message, type = 'info', action = null) {
  let region = document.querySelector('.toast-region');
  if (!region) {
    region = document.createElement('div');
    region.className = 'toast-region';
    region.setAttribute('aria-label', 'Avisos');
    region.setAttribute('aria-live', 'polite');
    document.body.append(region);
  }
  const toast = document.createElement('div');
  toast.className = `global-toast global-toast--${type}`;
  toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
  toast.setAttribute('data-toast', '');
  toast.innerHTML = `
    <span class="material-symbols-outlined global-toast-icon" aria-hidden="true">${type === 'error' ? 'error' : 'check_circle'}</span>
    <span class="global-toast-text"></span>
    <button class="global-toast-close" type="button" aria-label="Fechar aviso" data-toast-close>
      <span class="material-symbols-outlined" aria-hidden="true">close</span>
    </button>
  `;
  toast.querySelector('.global-toast-text').textContent = message;
  if (action?.label && typeof action.onClick === 'function') {
    const button = document.createElement('button');
    button.className = 'global-toast-action';
    button.type = 'button';
    button.textContent = action.label;
    button.addEventListener('click', action.onClick, { once: true });
    toast.querySelector('.global-toast-text').insertAdjacentElement('afterend', button);
  }
  region.append(toast);
  setupToast(toast);
};

document.querySelectorAll('[data-toast]').forEach(setupToast);
