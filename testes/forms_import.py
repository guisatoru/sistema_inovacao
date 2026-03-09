from django import forms

class ImportGestaoPessoasForm(forms.Form):
    arquivo = forms.FileField(label="Planilha (.xlsm)")