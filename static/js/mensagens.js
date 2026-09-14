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