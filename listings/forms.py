from django import forms

class CsvImportForm(forms.Form):
    csv_file = forms.FileField(
        label= "Archivo CSV",
        help_text= "Sube un archivo CSV con las columnas requeridas por InmoData"
    )

    dry_run = forms.BooleanField(
        required= False,
        initial=  True,
        label="Simular importacion",
        help_text= "Revisa el archivo sin modificar propiedades ni historial de precios"

    )

    deactivate_missing = forms.BooleanField(
        required= False,
        label= "Desactivar propiedades ausentes",
        help_text=(
            "Usalo solamente si el csv contiene el catalogo completo"
            "y actualizado de cada fuente incluida."

        ),
    )

    def clean_csv_file(self):
        uploaded_file = self.cleaned_data["csv_file"]

        if not uploaded_file.name.lower().endswith(".csv"):
            raise forms.ValidationError(
                "Solo se permiten archivos con extension .csv."
            )

        max_size = 5 * 1024 * 1024

        if uploaded_file.size > max_size:
            raise forms.ValidationError(
                "El archivo no puede superar 5 MB"
            )

        return uploaded_file

