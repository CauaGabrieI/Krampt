from django import forms


class EnviarMensagemForm(forms.Form):
    conteudo = forms.CharField(
        label="Mensagem",
        max_length=280,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Escreva uma mensagem...",
                "maxlength": 280,
                "aria-label": "Escreva sua mensagem",
            }
        ),
    )

    def clean_conteudo(self):
        conteudo = self.cleaned_data.get("conteudo", "").strip()
        if not conteudo:
            raise forms.ValidationError("A mensagem não pode estar vazia.")
        return conteudo
