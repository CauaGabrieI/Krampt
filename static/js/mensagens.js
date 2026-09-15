const busca = document.querySelector('#dm-search-input');
if (busca) {
  const conversas = document.querySelectorAll('[data-conversation-name]');
  busca.addEventListener('input', () => {
    const termo = busca.value.toLocaleLowerCase('pt-BR').trim();
    conversas.forEach((conversa) => {
      conversa.closest('li').hidden = !conversa.dataset.conversationName.toLocaleLowerCase('pt-BR').includes(termo);
    });
  });
}

document.addEventListener('keydown', (event) => {
  if (event.key.toLocaleLowerCase('pt-BR') !== 'n') return;
  if (event.ctrlKey || event.metaKey || event.altKey) return;

  const ativo = document.activeElement;
  const estaDigitando = ativo && (
    ativo.matches('input, textarea, select') ||
    ativo.isContentEditable
  );
  if (estaDigitando) return;

  const botaoNovaConversa = document.querySelector('.dm-new-button[href]');
  if (botaoNovaConversa) {
    window.location.href = botaoNovaConversa.href;
  }
});
