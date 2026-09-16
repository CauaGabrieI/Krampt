from mensagens.adapters import PoliticaMensagensDjango
from mensagens.application import ServicoMensagens
from notificacoes.adapters import NotificacoesDjango
from posts.adapters import ProcessadorImagemDjango
from posts.application import ServicoComandosPost, ServicoInteracoesPost
from profile.application import ServicoRelacionamentos


# Composition root: as views dependem de casos de uso; os casos de uso
# recebem implementações concretas apenas aqui.
notificacoes = NotificacoesDjango()
processador_imagem = ProcessadorImagemDjango()
politica_mensagens = PoliticaMensagensDjango()

servico_interacoes_post = ServicoInteracoesPost(notificacoes)
servico_comandos_post = ServicoComandosPost(
    notificacoes,
    processador_imagem,
)
servico_relacionamentos = ServicoRelacionamentos(notificacoes)
servico_mensagens = ServicoMensagens(politica_mensagens)
