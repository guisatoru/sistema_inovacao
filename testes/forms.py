from django import forms
from django.contrib.auth import get_user_model
from dal import autocomplete

from .models import Colaborador, Funcao, Loja, Solicitante, TestePromocao

User = get_user_model()

class TestePromocaoForm(forms.ModelForm):
    class Meta:
        model = TestePromocao
        fields = [
            "loja",
            "colaborador",
            "colaborador_re",   # vai ficar readonly (apenas visual)
            "solicitante",
            "funcao",
            "data_inicio",
            "anexo_folha_teste",
            "observacoes",
        ]
        widgets = {
            "loja": forms.Select(attrs={
                "data-combobox": "loja",
                "data-placeholder": "Selecione a loja...",
            }),

            "colaborador": forms.Select(attrs={
                "data-combobox": "colaborador",
                "data-placeholder": "Selecione o colaborador...",
            }),

            "solicitante": forms.Select(attrs={
                "data-combobox": "solicitante",
                "data-placeholder": "Selecione o solicitante...",
            }),
            "funcao": forms.Select(attrs={
                "data-combobox": "funcao",
                "data-placeholder": "Selecione a função...",
            }),

            "data_inicio": forms.DateInput(attrs={
                "type": "text",
                "placeholder": "dd/mm/aaaa",
                "data-flatpickr": "1",
                "autocomplete": "off",
            }),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Loja/Colaborador: combobox remoto (Tom Select).
        # Mantemos apenas o item selecionado no queryset para nao renderizar listas enormes no HTML.
        loja_qs = Loja.objects.none()
        colab_qs = Colaborador.objects.none()
        solicitante_qs = Solicitante.objects.none()
        funcao_qs = Funcao.objects.none()

        selected_loja_id = None
        selected_colab_id = None
        selected_solicitante_id = None
        selected_funcao_id = None

        if self.is_bound:
            selected_loja_id = self.data.get(self.add_prefix("loja")) or None
            selected_colab_id = self.data.get(self.add_prefix("colaborador")) or None
            selected_solicitante_id = self.data.get(self.add_prefix("solicitante")) or None
            selected_funcao_id = self.data.get(self.add_prefix("funcao")) or None
        elif self.instance and self.instance.pk:
            selected_loja_id = self.instance.loja_id
            selected_colab_id = self.instance.colaborador_id
            selected_solicitante_id = self.instance.solicitante_id
            selected_funcao_id = self.instance.funcao_id

        if selected_loja_id:
            loja_qs = Loja.objects.filter(pk=selected_loja_id)
        if selected_colab_id:
            colab_qs = Colaborador.objects.filter(pk=selected_colab_id)
        if selected_solicitante_id:
            solicitante_qs = Solicitante.objects.filter(pk=selected_solicitante_id)
        if selected_funcao_id:
            funcao_qs = Funcao.objects.filter(pk=selected_funcao_id)

        self.fields["loja"].queryset = loja_qs
        self.fields["colaborador"].queryset = colab_qs
        self.fields["solicitante"].queryset = solicitante_qs
        self.fields["funcao"].queryset = funcao_qs

        # RE apenas visual (não confiamos nele)
        if "colaborador_re" in self.fields:
            self.fields["colaborador_re"].required = False
            self.fields["colaborador_re"].widget.attrs.update({
                "readonly": "readonly",
            })

    def clean(self):
        cleaned = super().clean()

        loja = cleaned.get("loja")
        colab = cleaned.get("colaborador")
        funcao = cleaned.get("funcao")

        if not loja:
            self.add_error("loja", "Selecione a loja.")
            return cleaned

        if not colab:
            self.add_error("colaborador", "Selecione o colaborador.")
            return cleaned

        if colab.loja_id != loja.id:
            self.add_error("colaborador", "Este colaborador não pertence à loja selecionada.")

        # Regra de negócio: o teste deve ser para uma funcao diferente da funcao atual do colaborador.
        if funcao and getattr(colab, "funcao_id", None) and colab.funcao_id == funcao.id:
            self.add_error("colaborador", "Este colaborador já está na função selecionada para o teste.")
            self.add_error("funcao", "Selecione uma função diferente da função atual do colaborador.")

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)

        # snapshot SEMPRE vem do Colaborador
        if obj.colaborador_id:
            obj.colaborador_nome = obj.colaborador.nome
            obj.colaborador_re = obj.colaborador.re

        if commit:
            obj.save()
            self.save_m2m()

        return obj

class ImportGestaoPessoasForm(forms.Form):
    arquivo = forms.FileField(
        label="Planilha Gestão de Pessoas (.xlsm/.xlsx)",
        help_text="Envie a planilha para gerar o preview antes de confirmar."
    )


# =========================
# Admin interno (usuarios)
# =========================
class UsuarioCreateForm(forms.ModelForm):
    PERFIL_CHOICES = (
        ("usuario", "Usuário"),
        ("admin", "Admin"),
    )

    perfil = forms.ChoiceField(
        label="Perfil",
        choices=PERFIL_CHOICES,
        initial="usuario",
        widget=forms.RadioSelect,
    )

    password1 = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Use uma senha forte.",
    )
    password2 = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name"]
        labels = {
            "username": "Usuário",
            "first_name": "Nome",
            "last_name": "Sobrenome",
        }
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "off"}),
            "first_name": forms.TextInput(attrs={"autocomplete": "off"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "off"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        text_class = (
            "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm "
            "text-slate-900 outline-none placeholder:text-slate-400 focus:ring-4 focus:ring-indigo-100"
        )
        for name, field in self.fields.items():
            if name == "perfil":
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {text_class}".strip()

        self.fields["perfil"].widget.attrs.update({
            "class": "h-4 w-4 border-slate-300 text-indigo-600 focus:ring-indigo-100"
        })
        self.fields["username"].help_text = "Formato sugerido: nome.sobrenome"

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip().lower()
        if not username:
            return username

        qs = User.objects.filter(username__iexact=username)
        if qs.exists():
            raise forms.ValidationError("Já existe um usuário com esse login.")
        return username

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")

        if p1 and p2 and p1 != p2:
            self.add_error("password2", "As senhas não conferem.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = (user.username or "").strip().lower()
        user.is_active = True

        perfil = self.cleaned_data.get("perfil", "usuario")
        user.is_superuser = perfil == "admin"
        user.is_staff = user.is_superuser

        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()
            self.save_m2m()
        return user


class UsuarioUpdateForm(forms.ModelForm):
    PERFIL_CHOICES = (
        ("usuario", "Usuário"),
        ("admin", "Admin"),
    )

    perfil = forms.ChoiceField(
        label="Perfil",
        choices=PERFIL_CHOICES,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name"]
        labels = {
            "username": "Usuário",
            "first_name": "Nome",
            "last_name": "Sobrenome",
        }
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "off"}),
            "first_name": forms.TextInput(attrs={"autocomplete": "off"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "off"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        text_class = (
            "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm "
            "text-slate-900 outline-none placeholder:text-slate-400 focus:ring-4 focus:ring-indigo-100"
        )
        for name, field in self.fields.items():
            if name == "perfil":
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {text_class}".strip()

        self.fields["perfil"].widget.attrs.update({
            "class": "h-4 w-4 border-slate-300 text-indigo-600 focus:ring-indigo-100"
        })

        if self.instance and self.instance.pk:
            self.fields["perfil"].initial = "admin" if self.instance.is_superuser else "usuario"

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip().lower()
        if not username:
            return username
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um usuário com esse login.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = (user.username or "").strip().lower()
        perfil = self.cleaned_data.get("perfil", "usuario")
        user.is_superuser = perfil == "admin"
        user.is_staff = user.is_superuser
        if commit:
            user.save()
            self.save_m2m()
        return user


class UsuarioResetSenhaForm(forms.Form):
    password1 = forms.CharField(
        label="Nova senha",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Use uma senha forte.",
    )
    password2 = forms.CharField(
        label="Confirmar nova senha",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        text_class = (
            "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm "
            "text-slate-900 outline-none placeholder:text-slate-400 focus:ring-4 focus:ring-indigo-100"
        )
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {text_class}".strip()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") and cleaned.get("password2") and cleaned["password1"] != cleaned["password2"]:
            self.add_error("password2", "As senhas não conferem.")
        return cleaned
