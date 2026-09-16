import unicodedata

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


def normalizar_usuario(valor):
    """Canonical form for usernames: NFKC, no whitespace, lowercase."""
    return ''.join(unicodedata.normalize('NFKC', valor).split()).lower()


def normalizar_identidade_login(valor):
    identidade = ''.join(unicodedata.normalize('NFKC', valor).split()).lower()
    return identidade


class CadastroForm(forms.Form):
    name = forms.CharField(label='Nome', max_length=150)
    username = forms.CharField(label='Usuário', max_length=150)
    email = forms.EmailField(label='E-mail', max_length=254)
    password = forms.CharField(label='Senha', strip=False, widget=forms.PasswordInput)
    password_confirm = forms.CharField(label='Confirmar senha', strip=False, widget=forms.PasswordInput)
    aceitou_termos = forms.BooleanField(
        label='Termos de Uso e Política de Privacidade',
        required=True,
        error_messages={
            'required': 'Você precisa aceitar os Termos de Uso e a Política de Privacidade para criar a conta.',
        },
    )

    def clean_name(self):
        nome = ' '.join(unicodedata.normalize('NFKC', self.cleaned_data['name']).split())
        if not nome:
            raise forms.ValidationError('Informe seu nome.')
        return nome

    def clean_username(self):
        username = normalizar_usuario(self.cleaned_data['username'])
        User._meta.get_field('username').clean(username, None)
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Este usuário já está em uso.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este e-mail já está em uso.')
        return email

    def clean(self):
        dados = super().clean()
        senha = dados.get('password')
        confirmacao = dados.get('password_confirm')
        if senha and confirmacao and senha != confirmacao:
            self.add_error('password_confirm', 'As senhas não coincidem.')
        if senha:
            usuario = User(username=dados.get('username', ''), first_name=dados.get('name', ''), email=dados.get('email', ''))
            try:
                validate_password(senha, usuario)
            except forms.ValidationError as erro:
                self.add_error('password', erro)
        return dados

    def save(self):
        return User.objects.create_user(
            username=self.cleaned_data['username'],
            first_name=self.cleaned_data['name'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            is_active=False,
        )


class LoginForm(forms.Form):
    username = forms.CharField(label='Usuário', max_length=150)
    password = forms.CharField(label='Senha', strip=False, widget=forms.PasswordInput)

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.usuario = None

    def clean(self):
        dados = super().clean()
        username = normalizar_identidade_login(dados.get('username', ''))
        senha = dados.get('password')
        if username and senha:
            login_username = username
            if '@' in username:
                usuario = User.objects.filter(email__iexact=username, is_active=True).first()
                login_username = usuario.username if usuario else username
            self.usuario = authenticate(self.request, username=login_username, password=senha)
            if self.usuario is None:
                raise forms.ValidationError('Usuário ou senha inválidos.')
        elif not username and 'username' in dados:
            self.add_error('username', 'Informe seu usuário.')
        return dados


class VerificacaoForm(forms.Form):
    codigo = forms.RegexField(
        regex=r"^[0-9]{6}$",
        label="Código",
        error_messages={
            "required": "Informe o código de 6 dígitos.",
            "invalid": "O código deve ter exatamente 6 números.",
        },
    )


class TrocarEmailVerificacaoForm(forms.Form):
    email = forms.EmailField(label="Novo e-mail", max_length=254)

    def __init__(self, usuario, *args, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.exclude(pk=self.usuario.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("Este e-mail já está em uso.")
        return email

    def save(self):
        self.usuario.email = self.cleaned_data["email"]
        self.usuario.save(update_fields=["email"])
        return self.usuario


class RedefinirSenhaForm(PasswordResetForm):
    email = forms.EmailField(
        label="E-mail",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )


class TesteEmailForm(forms.Form):
    email = forms.EmailField(label="E-mail de destino", max_length=254)


class AdminExcluirUsuarioForm(forms.Form):
    usuario_id = forms.IntegerField(widget=forms.HiddenInput)
    confirmacao = forms.CharField(label="Confirmar username", max_length=150)
    senha_admin = forms.CharField(
        label="Sua senha de admin",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

class AdminVerificarUsuarioForm(forms.Form):
    usuario_id = forms.IntegerField(widget=forms.HiddenInput)
    desired_state = forms.ChoiceField(
        choices=(("1", "Verificar"), ("0", "Remover verificação")),
        widget=forms.HiddenInput,
    )
