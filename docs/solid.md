# SOLID no Krampt

O Krampt aplica SOLID de forma pragmática sobre os fluxos de escrita mais críticos.

- **S — Single Responsibility**: views tratam HTTP; classes em `application.py` executam casos de uso; adapters integram implementações concretas.
- **O — Open/Closed**: notificações, processamento de imagem e política de mensagens podem ganhar novas implementações sem alterar os casos de uso.
- **L — Liskov Substitution**: adapters e fakes usados nos testes respeitam as mesmas portas (`Protocol`) e podem ser substituídos.
- **I — Interface Segregation**: as portas são pequenas e específicas (`PortaNotificacoes`, `PortaProcessadorImagem`, `PortaPoliticaMensagens`).
- **D — Dependency Inversion**: os casos de uso dependem das portas; `krampt/container.py` é o composition root que injeta os adapters Django.

Os models Django continuam responsáveis por estrutura e invariantes persistentes. `transaction.atomic`,
constraints e idempotency keys continuam sendo a última linha de defesa para consistência.
