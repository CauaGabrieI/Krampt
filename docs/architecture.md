# Arquitetura do Krampt

O Krampt permanece um **monólito modular**. A intenção é ganhar organização,
testabilidade e eficiência sem pagar o custo operacional de microserviços antes
de existir uma necessidade real.

## Escritas

Fluxos que alteram estado seguem:

```text
HTTP -> view/form -> application -> ports -> adapters -> ORM/serviços externos
```

`application.py` contém casos de uso e limites transacionais. `ports.py` define
contratos pequenos e `adapters.py` conecta implementações concretas.

## Leituras — CQRS-lite

Consultas complexas seguem:

```text
HTTP -> view -> selectors -> ORM
```

`selectors.py` é somente leitura. Ele centraliza `select_related`,
`prefetch_related`, anotações, filtros e read models. Não existe banco separado,
event bus obrigatório ou duplicação de models: é apenas uma separação explícita
entre comandos e consultas.

## Orçamento de queries

Os caminhos de leitura críticos possuem testes com orçamento máximo de queries.
Isso detecta regressões N+1 mesmo quando a quantidade de posts, perfis ou
conversas aumenta.

Os testes usam limite máximo, não um número exato, para evitar acoplamento
desnecessário a pequenas diferenças entre SQLite e PostgreSQL.

## Transactional Outbox

E-mail e remoção de arquivos externos usam uma Outbox persistida no mesmo
PostgreSQL das operações de negócio:

```text
transaction.atomic
    ├── alteração de negócio
    └── EventoOutbox
             ↓ commit
          worker
             ├── e-mail
             └── storage/R2
```

O worker usa lease para recuperar eventos abandonados, retry com backoff e
`select_for_update(skip_locked=True)` quando o banco suporta. Depois do envio de
e-mail, o payload é apagado para não reter código/token temporário.

Em testes, `OUTBOX_EAGER` é ativado para manter feedback imediato e facilitar
assertivas. Em produção ele fica desligado por padrão e o worker deve rodar como
processo separado:

```bash
python manage.py process_outbox
```

A Outbox oferece entrega **pelo menos uma vez**. Handlers precisam permanecer
idempotentes sempre que possível; exclusão de arquivo já é naturalmente
idempotente e e-mails usam uma chave de evento para impedir criação duplicada
da mesma intenção.
