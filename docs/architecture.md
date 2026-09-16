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

## Próximo limite arquitetural

E-mail, processamento pesado de mídia e integrações externas não devem ser
colocados dentro de uma falsa "transação distribuída". Quando houver necessidade,
o próximo passo é uma **Transactional Outbox** no PostgreSQL e um worker
assíncrono. O outbox deve ser introduzido apenas junto com o processo de consumo,
retry e observabilidade, para não adicionar infraestrutura sem benefício real.
