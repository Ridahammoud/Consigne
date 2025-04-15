import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import altair as alt
import io
import locale
import re

st.title("Calcul des heures travaillées")

input_text = st.text_area("Collez ici votre tableau (copié depuis Excel)", height=300)

def parse_french_date(date_str):
    try:
        # Ex: "lundi 3 mars 2025"
        date_str = re.sub(r'\s+', ' ', date_str.strip())
        return datetime.strptime(date_str, "%A %d %B %Y")
    except:
        return pd.NaT

if input_text:
    try:
        df = pd.read_csv(io.StringIO(input_text), sep="\t")

        # Affiche le tableau brut pour vérification
        st.subheader("Tableau collé détecté :")
        st.dataframe(df)

        # Nettoyage des données
        df['Date'] = df['Date'].apply(parse_french_date)
        df['Début'] = pd.to_datetime(df['Début'], format="%H:%M", errors='coerce').dt.time
        df['Fin'] = pd.to_datetime(df['Fin'], format="%H:%M", errors='coerce').dt.time
        df['Pause non payée'] = df['Pause non payée'].astype(str).str.replace(",", ".").astype(float)
        df['Total (h)'] = df['Total (h)'].astype(str).str.replace(",", ".").astype(float)
        df['Notes du superviseur'] = df['Notes du superviseur'].fillna('').astype(str)

        # Résultats
        total_jours = 0
        total_heure_jour = 0.0
        total_heure_nuit = 0.0
        total_heure_dimanche = 0.0
        total_heure_sup = 0.0

        heure_nuit_debut = time(21, 0)
        heure_nuit_fin = time(6, 0)

        for _, row in df.iterrows():
            if pd.isna(row['Date']) or pd.isna(row['Début']) or pd.isna(row['Fin']):
                continue

            debut_datetime = datetime.combine(row['Date'], row['Début'])
            fin_datetime = datetime.combine(
                row['Date'] + timedelta(days=1) if row['Fin'] < row['Début'] else row['Date'],
                row['Fin']
            )
            duree_totale = (fin_datetime - debut_datetime).total_seconds() / 3600
            duree_travail = duree_totale - row['Pause non payée']

            if 'renfort' in row['Notes du superviseur'].lower():
                total_heure_sup += duree_travail
                continue  # On saute les heures normales

            total_jours += 1

            current_time = debut_datetime
            while current_time < fin_datetime:
                next_time = current_time + timedelta(minutes=15)
                segment_heure = (next_time - current_time).total_seconds() / 3600
                jour_semaine = current_time.weekday()

                if jour_semaine == 6:
                    total_heure_dimanche += segment_heure
                elif jour_semaine == 5 and current_time.hour < 6:
                    total_heure_dimanche += segment_heure
                elif heure_nuit_fin <= current_time.time() < heure_nuit_debut:
                    total_heure_jour += segment_heure
                else:
                    total_heure_nuit += segment_heure

                current_time = next_time

        # Résultats
        st.subheader("Résultat global")
        st.markdown(f"- **Nombre de jours travaillés** : {total_jours}")
        st.markdown(f"- **Heures de jour** : {round(total_heure_jour, 2)} h")
        st.markdown(f"- **Heures de nuit** : {round(total_heure_nuit, 2)} h")
        st.markdown(f"- **Heures de dimanche** : {round(total_heure_dimanche, 2)} h")
        st.markdown(f"- **Heures supplémentaires (renfort)** : {round(total_heure_sup, 2)} h")

        # Graphique
        st.subheader("Visualisation")
        chart_df = pd.DataFrame({
            "Type": ["Jour", "Nuit", "Dimanche", "Supplémentaire"],
            "Heures": [total_heure_jour, total_heure_nuit, total_heure_dimanche, total_heure_sup]
        })
        chart = alt.Chart(chart_df).mark_bar().encode(
            x="Type",
            y="Heures",
            color="Type",
            tooltip=["Type", "Heures"]
        ).properties(width=600)
        st.altair_chart(chart)

    except Exception as e:
        st.error(f"Erreur lors du traitement : {e}")
