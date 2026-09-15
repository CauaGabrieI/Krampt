import json
from smtplib import SMTPException

from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.sessions.models import Session
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from login.models import VerificacaoEmail
from login.services import emitir_codigo
from mensagens.models import Mensagem
from posts.models import Post
from profile.forms import EditarPerfilForm
from profile.models import Perfil
from profile.services import salvar_edicao_perfil

from .forms import (
    AparenciaForm,
    ConfirmacaoForm,
    ContaForm,
    ExcluirContaForm,
    MensagensForm,
    NotificacoesForm,
    PrivacidadeForm,
)
from .models import PreferenciasUsuario


SECOES = (
    ("conta", "Conta", "manage_accounts"),
    ("perfil", "Perfil", "person"),
    ("privacidade", "Privacidade", "lock"),
    ("mensagens", "Mensagens", "chat"),
    ("notificacoes", "Notificações", "notifications"),
    ("seguranca", "Segurança", "shield"),
    ("aparencia", "Aparência", "palette"),
    ("conteudo", "Conteúdo", "visibility"),
    ("dados", "Dados e armazenamento", "database"),
)
FORMULARIOS_PREFERENCIAS = {
    "privacidade": PrivacidadeForm,
    "mensagens": MensagensForm,
    "notificacoes": NotificacoesForm,
    "aparencia": AparenciaForm,
}


def _sessoes_do_usuario(request):
    sessoes = []
    for sessao in Session.objects.filter(expire_date__gte=timezone.now()):
        dados = sessao.get_decoded()
        if str(dados.get("_auth_user_id")) == str(request.user.pk):
            sessoes.append(
                {
                    "chave": sessao.session_key,
                    "expira_em": sessao.expire_date,
                    "atual": sessao.session_key == request.session.session_key,
                }
            )
    return sessoes


def _formulario_da_secao(request, secao, preferencias):
    dados = request.POST if request.method == "POST" else None
    if secao == "conta":
        return ContaForm(
            request.user,
            dados,
            initial={
                "nome": request.user.first_name or request.user.username,
                "username": request.user.username,
                "email": request.user.email,
            },
        )
    if secao == "perfil":
        perfil = Perfil.objects.filter(usuario=request.user).first()
        return EditarPerfilForm(
            dados,
            request.FILES if request.method == "POST" else None,
            initial={
                "nome": request.user.first_name or request.user.username,
                "biografia": perfil.biografia if perfil else "",
            },
        )
    if secao == "seguranca":
        return PasswordChangeForm(request.user, dados)
    classe = FORMULARIOS_PREFERENCIAS.get(secao)
    return classe(dados, instance=preferencias) if classe else None


@login_required
@require_http_methods(["GET", "POST"])
def configuracoes_view(request, secao="conta"):
    secoes_validas = {item[0] for item in SECOES}
    if secao not in secoes_validas:
        raise Http404
    preferencias, _ = PreferenciasUsuario.objects.get_or_create(usuario=request.user)
    formulario = _formulario_da_secao(request, secao, preferencias)

    if request.method == "POST":
        acao = request.POST.get("acao", "salvar")
        if acao == "desativar":
            confirmacao = ConfirmacaoForm(request.POST)
            if confirmacao.is_valid() and confirmacao.cleaned_data["confirmacao"] == request.user.username:
                request.user.is_active = False
                request.user.save(update_fields=["is_active"])
                logout(request)
                return redirect("login:login")
            messages.error(request, "Digite seu usuário exatamente para desativar a conta.")
            return redirect("configuracoes:secao", secao="conta")
        elif acao == "excluir_conta":
            confirmacao = ExcluirContaForm(request.POST)
            if (
                confirmacao.is_valid()
                and confirmacao.cleaned_data["confirmacao"] == request.user.username
                and request.user.check_password(confirmacao.cleaned_data["senha"])
            ):
                usuario = request.user
                logout(request)
                usuario.delete()
                return redirect("cadastro")
            messages.error(request, "Confirmação ou senha inválida.")
            return redirect("configuracoes:secao", secao="conta")
        elif acao == "sair_outras_sessoes" and secao == "seguranca":
            chaves = [item["chave"] for item in _sessoes_do_usuario(request) if not item["atual"]]
            Session.objects.filter(session_key__in=chaves).delete()
            messages.success(request, "As outras sessões foram encerradas.")
            return redirect("configuracoes:secao", secao="seguranca")
        elif acao == "excluir_posts" and secao == "dados":
            if request.POST.get("confirmacao") == "EXCLUIR POSTS":
                Post.objects.filter(autor=request.user).delete()
                messages.success(request, "Suas publicações foram excluídas.")
            else:
                messages.error(request, "Digite EXCLUIR POSTS para confirmar.")
            return redirect("configuracoes:secao", secao="dados")
        elif acao == "excluir_mensagens" and secao == "dados":
            if request.POST.get("confirmacao") == "EXCLUIR MENSAGENS":
                Mensagem.objects.filter(autor=request.user).delete()
                messages.success(request, "As mensagens enviadas por você foram excluídas.")
            else:
                messages.error(request, "Digite EXCLUIR MENSAGENS para confirmar.")
            return redirect("configuracoes:secao", secao="dados")
        elif formulario and formulario.is_valid():
            if secao == "conta":
                try:
                    with transaction.atomic():
                        email_alterado = formulario.save()
                        if email_alterado:
                            request.user.is_active = False
                            request.user.save(update_fields=["is_active"])
                            verificacao, _ = VerificacaoEmail.objects.get_or_create(usuario=request.user)
                            verificacao.codigo_hash = ""
                            verificacao.expira_em = None
                            verificacao.verificado_em = None
                            verificacao.tentativas = 0
                            verificacao.bloqueado_ate = None
                            verificacao.ultimo_envio_em = None
                            verificacao.janela_reenvio_em = None
                            verificacao.reenvios_na_janela = 0
                            verificacao.save(
                                update_fields=[
                                    "codigo_hash",
                                    "expira_em",
                                    "verificado_em",
                                    "tentativas",
                                    "bloqueado_ate",
                                    "ultimo_envio_em",
                                    "janela_reenvio_em",
                                    "reenvios_na_janela",
                                ]
                            )
                            emitir_codigo(verificacao)
                except (SMTPException, OSError):
                    formulario.add_error(
                        "email", "Não foi possível enviar a verificação agora. O e-mail não foi alterado."
                    )
                else:
                    if email_alterado:
                        usuario_id = request.user.pk
                        logout(request)
                        request.session["verificacao_usuario_id"] = usuario_id
                        return redirect("verificar_email")
                    messages.success(request, "Alterações salvas.")
                    return redirect("configuracoes:secao", secao=secao)
            elif secao == "perfil":
                perfil = Perfil.objects.filter(usuario=request.user).first()
                salvar_edicao_perfil(request.user, perfil, formulario.cleaned_data)
            elif secao == "seguranca":
                usuario = formulario.save()
                update_session_auth_hash(request, usuario)
            else:
                formulario.save()
            if secao != "conta":
                messages.success(request, "Alterações salvas.")
                return redirect("configuracoes:secao", secao=secao)

    verificacao = VerificacaoEmail.objects.filter(usuario=request.user).first()
    contexto = {
        "secao": secao,
        "secoes": SECOES,
        "formulario": formulario,
        "preferencias": preferencias,
        "email_verificado": bool(verificacao and verificacao.verificado_em),
        "sessoes": _sessoes_do_usuario(request) if secao == "seguranca" else (),
        "perfil": Perfil.objects.filter(usuario=request.user).first() if secao == "perfil" else None,
    }
    return render(request, "configuracoes.html", contexto)


@login_required
@require_GET
def exportar_dados(request):
    perfil = Perfil.objects.filter(usuario=request.user).first()
    dados = {
        "conta": {
            "username": request.user.username,
            "nome": request.user.first_name,
            "email": request.user.email,
            "criada_em": request.user.date_joined,
        },
        "perfil": {
            "biografia": perfil.biografia if perfil else "",
            "foto": perfil.foto.name if perfil and perfil.foto else None,
            "banner": perfil.banner.name if perfil and perfil.banner else None,
        },
        "posts": list(
            Post.objects.filter(autor=request.user).values(
                "id", "conteudo", "criado_em", "original_id"
            )
        ),
        "mensagens_enviadas": list(
            Mensagem.objects.filter(autor=request.user).values(
                "id", "conversa_id", "conteudo", "criada_em"
            )
        ),
    }
    resposta = HttpResponse(
        json.dumps(dados, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2),
        content_type="application/json",
    )
    resposta["Content-Disposition"] = 'attachment; filename="dados-krampt.json"'
    return resposta
