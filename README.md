# Krampt

Rede social em Django (Python 3.13+) com autenticação via e-mail, publicações
com imagens e áudio, comentários, reposts, curtidas, mensagens diretas e
notificações.

## Funcionalidades

- Cadastro com código de verificação por e-mail e recuperação de senha
- Feed com filtro "seguindo", hashtags e busca
- Perfis com foto, banner, biografia e abas (publicações, reposts, mídia, salvos)
- Comentários em cascata com resposta, curtidas e mídia
- Repostagens e salvos por usuário
- Mensagens diretas em conversas por par de usuários
- Notificações de curtidas, comentários, respostas e seguidores
- Limite de tentativas por IP e por usuário (login e recuperação de senha)
- Validação e compressão de mídia (dimensões, pixels, quadros de GIF)
- Paginação de feed, mensagens e notificações

## Requisitos

- Python 3.13+ (testado com Django 6.1 e Pillow 12)
- Banco SQLite para desenvolvimento ou PostgreSQL para produção

## Configuração local

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # ajuste conforme necessário
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Variáveis de ambiente

Veja `.env.example`. As principais:

| Variável | Descrição | Padrão |
| --- | --- | --- |
| `SECRET_KEY` | Chave secreta do Django (obrigatória) | — |
| `DEBUG` | `true` em desenvolvimento | `true` (local) |
| `ALLOWED_HOSTS` | Hosts aceitos, separados por vírgula | `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | Origens confiáveis de CSRF (separadas por vírgula) | vazio |
| `PGHOST` | Habilita PostgreSQL quando definido | SQLite |
| `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGPORT` | Conexão do banco | — |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP para códigos e redefinição de senha | console (local) |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_TIMEOUT` | Opções do SMTP | TLS ligado, timeout 10s |
| `DEFAULT_FROM_EMAIL` | Remetente dos e-mails | Krampt |
| `SESSION_COOKIE_SECURE` | Cookie de sessão apenas via HTTPS | `false` (local), `true` (produção) |
| `WHITENOISE` | `true` em produção para servir estáticos compilados | — |
| `TRUST_PROXY_HEADERS` | `true` para confiar em `X-Forwarded-For` (limites de tentativa) | — |
| `RENDER` | Definido automaticamente no Render (produção) | — |

## Testes

```bash
python manage.py test            # suite completa
python manage.py test posts      # apenas um app
python manage.py check           # acusa SMTP ausente quando DEBUG=false
```

## Produção

1. Configure as variáveis acima com `DEBUG=false`, `ALLOWED_HOSTS` apontando
   para o domínio e as variáveis `PG*` para o PostgreSQL.
2. Com `WHITENOISE=true`, rode `python manage.py collectstatic --noinput`.
3. Execute o servidor:

```bash
gunicorn krampt.wsgi:application --bind 0.0.0.0:$PORT
```

(No Render, `$PORT` é definido automaticamente.)

## Comandos úteis

```bash
python manage.py limpar_autenticacao_expirada --prazo-horas 24 --dry-run
```

Remove tentativas de login antigas e contas inativas criadas e nunca
verificadas além do prazo. Use `--dry-run` para conferir antes de aplicar.

## Estrutura

| Diretório | Responsabilidade |
| --- | --- |
| `login/` | Autenticação, verificação por e-mail, redefinição de senha, limpeza |
| `posts/` | Publicações, comentários, hashtags, mídia e sua validação |
| `profile/` | Perfil, foto/banner, seguir e abas |
| `mensagens/` | Conversas e mensagens diretas |
| `notificacoes/` | Notificações |
| `krampt/` | Configurações, URLs, paginação e middleware de login |
| `templates/` | Templates (separados dos estáticos) |
| `static/` e `imgs/` | CSS, JS e imagens estáticas |