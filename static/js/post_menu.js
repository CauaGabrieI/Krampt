(function () {
  function toast(message, type = 'success') {
    if (window.KramptToast) {
      window.KramptToast(message, type);
      return;
    }
    const status = document.createElement('div');
    status.className = 'sr-only';
    status.setAttribute('role', type === 'error' ? 'alert' : 'status');
    status.textContent = message;
    document.body.append(status);
    window.setTimeout(() => status.remove(), 2500);
  }

  function closeMenu(menu) {
    if (!menu) return;
    const panel = menu.querySelector('.post-menu-panel');
    const trigger = menu.querySelector('.post-menu-trigger');
    panel.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
  }

  function closeAllMenus(except) {
    document.querySelectorAll('[data-post-menu]').forEach((menu) => {
      if (menu !== except) closeMenu(menu);
    });
  }

  async function copyText(text, fallbackMessage) {
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (error) {
        // Alguns navegadores bloqueiam clipboard em contextos não seguros.
      }
    }
    window.prompt(fallbackMessage, text);
    return false;
  }

  document.addEventListener('click', async (event) => {
    const trigger = event.target.closest('.post-menu-trigger');
    if (trigger) {
      event.preventDefault();
      const menu = trigger.closest('[data-post-menu]');
      const panel = menu.querySelector('.post-menu-panel');
      const opening = panel.hidden;
      closeAllMenus(menu);
      panel.hidden = !opening;
      trigger.setAttribute('aria-expanded', String(opening));
      if (opening) panel.querySelector('[role="menuitem"]')?.focus();
      return;
    }

    const dialogButton = event.target.closest('[data-open-dialog]');
    if (dialogButton) {
      event.preventDefault();
      closeAllMenus();
      document.getElementById(dialogButton.dataset.openDialog)?.showModal();
      return;
    }

    const closeDialog = event.target.closest('[data-close-dialog]');
    if (closeDialog) {
      event.preventDefault();
      closeDialog.closest('dialog')?.close();
      return;
    }

    const copyLink = event.target.closest('[data-copy-post-link]');
    if (copyLink) {
      event.preventDefault();
      closeAllMenus();
      const post = copyLink.closest('.post');
      const url = post?.dataset.postUrl;
      if (!url) return;
      await copyText(url, 'Copie o link do post:');
      toast('Link copiado.');
      return;
    }

    const copyEmbed = event.target.closest('[data-copy-embed-code]');
    if (copyEmbed) {
      event.preventDefault();
      const dialog = copyEmbed.closest('dialog');
      const code = dialog?.querySelector('[data-embed-code]')?.value;
      if (!code) return;
      await copyText(code, 'Copie o código de incorporação:');
      toast('Código copiado.');
      return;
    }

    if (!event.target.closest('[data-post-menu]')) closeAllMenus();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeAllMenus();
  });
})();
