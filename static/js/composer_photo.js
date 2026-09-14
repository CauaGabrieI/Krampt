(function () {
  const input = document.getElementById('composer-imagem');
  const status = document.getElementById('composer-photo-name');
  const previews = document.getElementById('composer-previews');
  if (!input || !status || !previews) return;
  let arquivos = [];
  let urls = [];

  function limparUrls() {
    urls.forEach(url => URL.revokeObjectURL(url));
    urls = [];
  }

  function atualizar() {
    const transferencia = new DataTransfer();
    arquivos.forEach(arquivo => transferencia.items.add(arquivo));
    input.files = transferencia.files;
    limparUrls();
    previews.replaceChildren();
    status.textContent = arquivos.length ? `${arquivos.length} imagem(ns) selecionada(s)` : '';
    arquivos.forEach((arquivo, indice) => {
      const miniatura = document.createElement('div');
      miniatura.className = 'composer-preview';
      const imagem = document.createElement('img');
      const url = URL.createObjectURL(arquivo);
      urls.push(url);
      imagem.src = url;
      imagem.alt = arquivo.name;
      const remover = document.createElement('button');
      remover.type = 'button';
      remover.textContent = '×';
      remover.setAttribute('aria-label', `Remover ${arquivo.name}`);
      remover.addEventListener('click', () => {
        arquivos.splice(indice, 1);
        atualizar();
        input.closest('form').querySelector('.primary-button').focus();
      });
      miniatura.append(imagem, remover);
      previews.append(miniatura);
    });
  }

  input.addEventListener('change', () => {
    const novosArquivos = Array.from(input.files || []);
    const validos = novosArquivos.filter((arquivo) => {
      if (arquivo.size > 10 * 1024 * 1024) {
        window.alert(`A imagem ou GIF "${arquivo.name}" ultrapassa o limite máximo de 10 MB.`);
        return false;
      }
      return true;
    });
    arquivos.push(...validos);
    atualizar();
  });

  const audioInput = document.getElementById('composer-audio');
  if (audioInput) {
    audioInput.addEventListener('change', () => {
      const audio = audioInput.files?.[0];
      if (audio && audio.size > 10 * 1024 * 1024) {
        window.alert('O áudio ultrapassa o limite máximo de 10 MB.');
        audioInput.value = '';
      }
    });
  }
})();