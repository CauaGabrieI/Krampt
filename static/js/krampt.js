(function () {
  document.addEventListener('submit', function (event) {
    const confirmForm = event.target.closest('form[data-confirm-message]');
    if (confirmForm && !window.confirm(confirmForm.dataset.confirmMessage)) {
      event.preventDefault();
      return;
    }

    const form = event.target.closest('form[data-submit-once]');
    if (!form || form.dataset.submitting === 'true') {
      if (form) event.preventDefault();
      return;
    }
    form.dataset.submitting = 'true';
    const botao = form.querySelector('button[type="submit"]');
    if (botao) {
      botao.disabled = true;
      botao.dataset.originalText = botao.textContent;
      botao.textContent = 'Enviando...';
    }
  });

  document.addEventListener('submit', async function (event) {
    const form = event.target.closest('form[data-async-action]');
    if (!form) return;
    event.preventDefault();
    form.setAttribute('aria-busy', 'true');

    try {
      const resposta = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      if (!resposta.ok) throw new Error('A ação não pôde ser concluída.');
      const dados = await resposta.json();
      const tipo = form.dataset.actionType;

      if (tipo === 'like' || tipo === 'repost' || tipo === 'comment-like' || tipo === 'save') {
        const botao = form.querySelector('button');
        if (botao && tipo === 'save') {
          botao.classList.toggle('is-saved', dados.saved);
          botao.setAttribute('aria-pressed', String(dados.saved));
          botao.setAttribute('aria-label', dados.saved ? 'Remover dos salvos' : 'Salvar post');
          const icone = botao.querySelector('.save-icon');
          if (icone) icone.src = dados.saved ? '/static/imgs/marca-paginas%20preenchido.png' : '/static/imgs/marca-paginas.png';
        } else if (botao && typeof dados.total === 'number') {
          botao.classList.toggle('is-liked', tipo !== 'repost' && dados.liked);
          botao.classList.toggle('is-reposted', tipo === 'repost' && dados.reposted);
          botao.setAttribute('aria-pressed', String(tipo === 'repost' ? dados.reposted : dados.liked));

          if (tipo === 'like') {
            botao.setAttribute('aria-label', dados.liked ? 'Descurtir' : 'Curtir');
            const icone = botao.querySelector('.like-icon');
            if (icone) {
              icone.src = dados.liked ? icone.dataset.likedSrc : icone.dataset.unlikedSrc;
            }
          }

          const contador = botao.querySelector('span:last-child');
          if (contador) contador.textContent = dados.total;
        }
      }
      if (tipo === 'comment') {
        form.reset();
        form.querySelector('textarea')?.focus();
      }
      if (tipo === 'mute-user') {
        const username = form.dataset.username || '';
        const csrf = form.querySelector('[name="csrfmiddlewaretoken"]')?.value;

        const atualizarEstado = (muted) => {
          form.action = muted ? form.dataset.unmuteUrl : form.dataset.muteUrl;
          const botao = form.querySelector('button');
          if (!botao) return;
          const icone = document.createElement('span');
          icone.className = 'material-symbols-outlined';
          icone.setAttribute('aria-hidden', 'true');
          icone.textContent = muted ? 'volume_up' : 'volume_off';
          botao.replaceChildren(
            icone,
            document.createTextNode(` ${muted ? 'Dessilenciar' : 'Silenciar'} @${username}`)
          );
        };

        const muted = dados.muted === true && dados.unmuted !== true;
        atualizarEstado(muted);

        const menu = form.closest('[data-post-menu]');
        const painel = menu?.querySelector('.post-menu-panel');
        const gatilho = menu?.querySelector('.post-menu-trigger');
        if (painel) painel.hidden = true;
        if (gatilho) gatilho.setAttribute('aria-expanded', 'false');

        if (window.KramptToast) {
          const undoUrl = dados.undo_url;
          window.KramptToast(
            dados.message || (muted ? `@${username} foi silenciado.` : `@${username} foi dessilenciado.`),
            'success',
            undoUrl ? {
              label: dados.undo_label || 'Desfazer',
              onClick: async () => {
                const payload = new FormData();
                if (csrf) payload.append('csrfmiddlewaretoken', csrf);
                const undoResponse = await fetch(undoUrl, {
                  method: 'POST',
                  body: payload,
                  credentials: 'same-origin',
                  headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });
                if (!undoResponse.ok) throw new Error('Não foi possível desfazer.');
                const undoData = await undoResponse.json();
                atualizarEstado(false);
                window.KramptToast(
                  undoData.message || dados.undo_message || 'Ação desfeita.',
                  'success'
                );
              }
            } : null
          );
        }
      }
      if (tipo === 'hide-post') {
        form.closest('dialog')?.close();
        form.closest('.post')?.remove();
        if (window.KramptToast) {
          const csrf = form.querySelector('[name="csrfmiddlewaretoken"]')?.value;
          const undoUrl = dados.undo_url;
          window.KramptToast(dados.message || 'Post ocultado.', 'success', undoUrl ? {
            label: dados.undo_label || 'Desfazer',
            onClick: async () => {
              const payload = new FormData();
              if (csrf) payload.append('csrfmiddlewaretoken', csrf);
              const undoResponse = await fetch(undoUrl, {
                method: 'POST',
                body: payload,
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
              });
              if (!undoResponse.ok) throw new Error('Não foi possível desfazer.');
              const undoData = await undoResponse.json();
              window.KramptToast(undoData.message || dados.undo_message || 'Ação desfeita.', 'success');
            }
          } : null);
        }
      }
      if (tipo === 'delete-comment') form.closest('.comment-item, .comment-reply')?.remove();
      if (tipo === 'delete-post' || form.querySelector('.delete-post-action')) {
        form.closest('.post')?.remove();
        form.closest('dialog')?.close();
        if (window.KramptToast) window.KramptToast('Post excluído.', 'success');
      }
    } catch (erro) {
      const aviso = document.createElement('div');
      aviso.className = 'async-action-error';
      aviso.setAttribute('role', 'alert');
      aviso.textContent = erro.message;
      form.insertAdjacentElement('afterend', aviso);
    } finally {
      form.removeAttribute('aria-busy');
    }
  });

  (function () {
    const emojis = [
      '😀', '😃', '😄', '😁', '😆', '😅', '😂', '🤣', '😊', '😇', '🙂', '🙃', '😉', '😌', '😍', '🥰', '😘',
      '😎', '🤩', '🥳', '😏', '😢', '😭', '😤', '😡', '🤔', '🤗', '🤭', '🤫', '😴', '🤯', '😱', '🥺',
      '👍', '👎', '👏', '🙌', '🙏', '💪', '🤝', '❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '💔', '🔥',
      '✨', '⭐', '💯', '🎉', '🎊', '✅', '❌', '💡', '🚀', '👀', '💬', '🎶', '🍕', '☕', '⚽', '🐶'
    ];
    let picker;
    let campoAtivo;

    function fechar() {
      picker?.remove();
      picker = null;
      campoAtivo = null;
    }

    function abrir(botao) {
      fechar();
      campoAtivo = document.getElementById(botao.dataset.emojiTarget);
      if (!campoAtivo) return;
      picker = document.createElement('div');
      picker.className = 'emoji-picker';
      picker.setAttribute('role', 'dialog');
      picker.setAttribute('aria-label', 'Escolha um emoji');
      const titulo = document.createElement('strong');
      titulo.textContent = 'Emojis';
      const grade = document.createElement('div');
      grade.className = 'emoji-picker-grid';
      picker.append(titulo, grade);
      emojis.forEach((emoji) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'emoji-picker-item';
        item.textContent = emoji;
        item.setAttribute('aria-label', `Inserir ${emoji}`);
        item.addEventListener('click', () => {
          const inicio = campoAtivo.selectionStart ?? campoAtivo.value.length;
          const fim = campoAtivo.selectionEnd ?? inicio;
          campoAtivo.value = `${campoAtivo.value.slice(0, inicio)}${emoji}${campoAtivo.value.slice(fim)}`;
          campoAtivo.focus();
          campoAtivo.selectionStart = campoAtivo.selectionEnd = inicio + emoji.length;
          fechar();
        });
        grade.append(item);
      });
      document.body.append(picker);
      const rect = botao.getBoundingClientRect();
      const esquerda = Math.min(rect.left, window.innerWidth - picker.offsetWidth - 12);
      picker.style.left = `${Math.max(12, esquerda)}px`;
      picker.style.top = `${Math.max(12, rect.top - picker.offsetHeight - 8)}px`;
    }

    document.addEventListener('click', (event) => {
      const botao = event.target.closest('[data-emoji-target]');
      if (botao) {
        event.preventDefault();
        abrir(botao);
      } else if (picker && !picker.contains(event.target)) {
        fechar();
      }
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') fechar();
    });
  })();

  (function () {
    document.addEventListener('change', function (event) {
      const input = event.target.closest('.comment-image-input');
      if (!input) return;
      const preview = document.querySelector(`[data-media-preview-for="${input.id}"]`);
      if (!preview) return;
      if (preview.__mediaUrl) URL.revokeObjectURL(preview.__mediaUrl);
      preview.__mediaUrl = null;
      preview.replaceChildren();
      const arquivo = input.files?.[0];
      if (!arquivo) return;
      if (arquivo.size > 10 * 1024 * 1024) {
        window.alert('A imagem ou GIF ultrapassa o limite máximo de 10 MB.');
        input.value = '';
        return;
      }
      const imagem = document.createElement('img');
      const url = URL.createObjectURL(arquivo);
      preview.__mediaUrl = url;
      imagem.src = url;
      imagem.alt = `Prévia de ${arquivo.name}`;
      const remover = document.createElement('button');
      remover.type = 'button';
      remover.className = 'comment-media-remove';
      remover.setAttribute('aria-label', `Remover ${arquivo.name}`);
      const iconeRemover = document.createElement('img');
      iconeRemover.src = '/static/imgs/circulo-xmark.png';
      iconeRemover.alt = '';
      iconeRemover.setAttribute('aria-hidden', 'true');
      remover.append(iconeRemover);
      remover.addEventListener('click', () => {
        input.value = '';
        if (preview.__mediaUrl) URL.revokeObjectURL(preview.__mediaUrl);
        preview.__mediaUrl = null;
        preview.replaceChildren();
      });
      preview.append(imagem, remover);
    });
  })();

  (function () {
    function atualizarViewport() {
      const altura = window.visualViewport ? window.visualViewport.height : window.innerHeight;
      document.documentElement.style.setProperty('--viewport-height', `${altura}px`);
    }
    atualizarViewport();
    window.addEventListener('resize', atualizarViewport, { passive: true });
    window.addEventListener('orientationchange', atualizarViewport, { passive: true });
    if (window.visualViewport) window.visualViewport.addEventListener('resize', atualizarViewport, { passive: true });
  })();

  window.addEventListener('pageshow', function (event) {
    if (event.persisted) window.location.reload();
  });
})();
