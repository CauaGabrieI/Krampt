(function () {
  const accountMenus = [...document.querySelectorAll('[data-account-menu]')];
  if (!accountMenus.length) return;

  function setAccountMenuOpen(menu, open) {
    const trigger = menu.querySelector('.account-menu-trigger');
    const panel = menu.querySelector('.account-menu-panel');
    panel.hidden = !open;
    trigger.setAttribute('aria-expanded', String(open));
    trigger.setAttribute('aria-label', open ? 'Fechar opções da conta' : 'Abrir opções da conta');
  }

  accountMenus.forEach((menu) => {
    const trigger = menu.querySelector('.account-menu-trigger');
    trigger.addEventListener('click', () => {
      const shouldOpen = menu.querySelector('.account-menu-panel').hidden;
      accountMenus.forEach((otherMenu) => setAccountMenuOpen(otherMenu, false));
      setAccountMenuOpen(menu, shouldOpen);
    });

    menu.addEventListener('focusout', (event) => {
      if (!menu.contains(event.relatedTarget)) setAccountMenuOpen(menu, false);
    });
  });

  document.addEventListener('click', (event) => {
    accountMenus.forEach((menu) => {
      if (!menu.contains(event.target)) setAccountMenuOpen(menu, false);
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const openMenu = accountMenus.find((menu) => !menu.querySelector('.account-menu-panel').hidden);
    if (openMenu) {
      setAccountMenuOpen(openMenu, false);
      openMenu.querySelector('.account-menu-trigger').focus();
    }
  });
})();