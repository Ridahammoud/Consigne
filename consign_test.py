import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

st.title("Calcul des heures travaillées")

input_text = st.text_area("Collez ici le tableau copié depuis Excel :", height=300)

if input_text:
    try:
        df = pd.read_csv(StringIO(input_text), sep="\t")
    except Exception as e:
        st.error("Erreur lors de la lecture du tableau. Assurez-vous d'avoir copié un tableau valide depuis Excel.")
        st.stop()

    # Nettoyage des colonnes
    df.columns = df.columns.str.strip()
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Date'])  # élimine les lignes avec des dates invalides

    df['Début'] = pd.to_datetime(df['Début'], format='%H:%M', errors='coerce').dt.time
    df['Fin'] = pd.to_datetime(df['Fin'], format='%H:%M', errors='coerce').dt.time
    df['Pause non payée'] = df['Pause non payée'].astype(str).str.replace(",", ".").astype(float)
    df['Total (h)'] = df['Total (h)'].astype(str).str.replace(",", ".").astype(float)
    df['Notes du superviseur'] = df['Notes du superviseur'].fillna("").str.lower()

    # Constantes
    JOUR_START = 6
    JOUR_END = 21

    # Liste des jours fériés
    holidays = set([
        datetime(2025, 1, 1).date(),
        datetime(2025, 4, 21).date(),
        datetime(2025, 5, 1).date(),
        datetime(2025, 7, 5).date(),
        datetime(2025, 11, 1).date(),
        # Ajouter d'autres jours fériés ici
    ])

    def calculate_hours(row):
        date = row['Date'].date()
        start = datetime.combine(date, row['Début'])
        end = datetime.combine(date + timedelta(days=1) if row['Fin'] < row['Début'] else date, row['Fin'])
        total = (end - start).total_seconds() / 3600

        is_renfort = 'renfort' in row['Notes du superviseur']
        is_holiday = date in holidays
        heures_jour = heures_nuit = heures_dimanche = heures_ferie = 0

        # Supplémentaires dans les notes
        supplements = {
            '+0.5h': 0.5,
            '+1h': 1.0,
            '+1.5h': 1.5,
            '+2h': 2.0,
            '+2.5h': 2.5,
        }

        current = start
        while current < end:
            next_minute = current + timedelta(minutes=1)
            hour = current.hour + current.minute / 60
            minute_date = current.date()

            if minute_date in holidays:
                heures_ferie += 1/60
            elif current.weekday() == 6:
                heures_dimanche += 1/60
            elif JOUR_START <= hour < JOUR_END:
                heures_jour += 1/60
            else:
                heures_nuit += 1/60

            current = next_minute

        # Déduction pause sur les heures de jour
        pause = row['Pause non payée']
        heures_jour = max(0, heures_jour - pause)

        heures_supp = 0
        for key, value in supplements.items():
            if key in row['Notes du superviseur']:
                if heures_nuit >= value:
                    heures_nuit -= value
                elif heures_jour >= value:
                    heures_jour -= value
                else:
                    continue
                heures_supp += value

        # Cas renfort : déplacer heures vers supp sauf dimanche
        if is_renfort:
            if heures_dimanche > 0:
                heures_supp += heures_jour + heures_nuit
                heures_jour = 0
                heures_nuit = 0
            else:
                heures_supp += heures_jour + heures_nuit + heures_dimanche
                heures_jour = heures_nuit = heures_dimanche = 0

        return pd.Series([heures_jour, heures_nuit, heures_dimanche, heures_supp, heures_ferie])

    df[['Heures jour', 'Heures nuit', 'Heures dimanche', 'Heures supp', 'Heures férié']] = df.apply(calculate_hours, axis=1)
    jours_travaillés = df['Date'].nunique()

    # Résumés
    total_jour = df['Heures jour'].sum()
    total_nuit = df['Heures nuit'].sum()
    total_dimanche = df['Heures dimanche'].sum()
    total_renfort = df['Heures supp'].sum()
    total_ferie = df['Heures férié'].sum()

    # Résultat global
    st.header("Résultat global")
    st.write(f"**Nombre de jours travaillés :** {jours_travaillés}")
    st.write(f"**Heures de jour :** {total_jour:.2f} h")
    st.write(f"**Heures de nuit :** {total_nuit:.2f} h")
    st.write(f"**Heures de dimanche :** {total_dimanche:.2f} h")
    st.write(f"**Heures de jours fériés :** {total_ferie:.2f} h")
    st.write(f"**Heures supplémentaires (renfort et notes) :** {total_renfort:.2f} h")
    st.write(f"**Total Heures calculées :** {total_jour + total_nuit + total_dimanche + total_ferie + total_renfort:.2f} h")

    # Notes du superviseur
    st.header("Notes du superviseur")
    st.dataframe(df[['Date', 'Notes du superviseur']][df['Notes du superviseur'] != ""])

    # Visualisation
    st.header("Visualisation")
    df_viz = pd.DataFrame({
        'Date': df['Date'].dt.strftime("%d/%m"),
        'Jour': df['Heures jour'],
        'Nuit': df['Heures nuit'],
        'Dimanche': df['Heures dimanche'],
        'Férié': df['Heures férié'],
        'Renfort': df['Heures supp'],
    })
    df_viz.set_index('Date')[['Jour', 'Nuit', 'Dimanche', 'Férié', 'Renfort']].plot(
        kind='bar', stacked=True, figsize=(12, 6))
    plt.ylabel("Heures")
    plt.title("Répartition des heures par jour")
    st.pyplot(plt)

    # Détail
    st.header("Détail de Calcul par ligne")
    st.dataframe(df[['Date', 'Heures jour', 'Heures nuit', 'Heures dimanche', 'Heures férié', 'Heures supp']])
