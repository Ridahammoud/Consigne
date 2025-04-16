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

    # Fonctions de calcul
    def calculate_hours(row):
        date = row['Date']
        start = datetime.combine(date, row['Début'])
        end = datetime.combine(date + timedelta(days=1) if row['Fin'] < row['Début'] else date, row['Fin'])
        total = (end - start).total_seconds() / 3600

        is_renfort = 'renfort' in row['Notes du superviseur']
        heures_jour = heures_nuit = heures_dimanche = 0

        if is_renfort:
            return pd.Series([0, 0, 0, total])  # seulement heures supp

        current = start
        while current < end:
            next_minute = current + timedelta(minutes=1)
            hour = current.hour + current.minute / 60

            if current.weekday() == 6:  # dimanche
                heures_dimanche += 1/60
            elif JOUR_START <= hour < JOUR_END:
                heures_jour += 1/60
            else:
                heures_nuit += 1/60

            current = next_minute

        # Retirer pause des heures de jour
        pause = row['Pause non payée']
        heures_jour = max(0, heures_jour - pause)

        return pd.Series([heures_jour, heures_nuit, heures_dimanche, 0])

    df[['Heures jour', 'Heures nuit', 'Heures dimanche', 'Heures supp']] = df.apply(calculate_hours, axis=1)
    jours_travaillés = df['Date'].nunique()

    # Résumés
    total_jour = df['Heures jour'].sum()
    total_nuit = df['Heures nuit'].sum()
    total_dimanche = df['Heures dimanche'].sum()
    total_renfort = df['Heures supp'].sum() - df[df['Notes du superviseur'].str.contains('renfort')]['Date'].nunique()
    
    # Résultat global
    st.header("Résultat global")
    st.write(f"**Nombre de jours travaillés :** {jours_travaillés}")
    st.write(f"**Heures de jour :** {total_jour:.2f} h")
    st.write(f"**Heures de nuit :** {total_nuit:.2f} h")
    st.write(f"**Heures de dimanche :** {total_dimanche:.2f} h")
    st.write(f"**Heures supplémentaires (renfort) :** {total_renfort :.2f} h")
    st.write(f"**Total Heures calculés :** {total_jour + total_nuit + total_dimanche + total_renfort:.2f} h")

    # Notes du superviseur
    st.header("Notes du superviseur")
    st.write(f"**Les notes des superviseurs :** {df[~df['Notes du superviseur'].isnull()][['Date','Notes du superviseur']]} ")

    # Visualisation
    st.header("Visualisation")
    fig, ax = plt.subplots(figsize=(10, 5))
    df_viz = pd.DataFrame({
        'Jour': [d.strftime("%d/%m") for d in df['Date']],
        'Jour': df['Heures jour'],
        'Nuit': df['Heures nuit'],
        'Dimanche': df['Heures dimanche'],
        'Renfort': df['Heures supp'],
    })

    df_viz.set_index('Jour').plot(kind='bar', stacked=True, ax=ax)
    plt.ylabel("Heures")
    plt.title("Répartition des heures par jour")
    st.pyplot(fig)

    # Détails
    st.header("Détail par ligne")
    st.dataframe(df[['Date', 'Heures jour', 'Heures nuit', 'Heures dimanche', 'Heures supp']])

