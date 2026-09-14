document.querySelectorAll('.post-share').forEach((button) => {
  const label = button.querySelector('.post-share-label');
  const status = button.parentElement.querySelector('.post-share-status');
  let resetTimer;

  button.addEventListener('click', async () => {
    const url = new URL(button.dataset.shareUrl, window.location.origin).href;

    if (navigator.share) {
      try {
        await navigator.share({ title: 'Post no Krampt', url });
        return;
      } catch (error) {
        if (error.name === 'AbortError') return;
      }
    }

    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(url);
        if (status) status.textContent = 'Link copiado';
        label.textContent = 'Copiado!';
        clearTimeout(resetTimer);
        resetTimer = setTimeout(() => {
          if (status) status.textContent = '';
          label.textContent = 'Compartilhar';
        }, 2500);
        return;
      } catch (error) {
        // O navegador pode bloquear a área de transferência fora de HTTPS.
      }
    }

    window.prompt('Copie o link do post:', url);
  });
});