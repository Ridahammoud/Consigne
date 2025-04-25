import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta, date
import matplotlib.pyplot as plt

st.title("Calcul des heures travaillées")

# Liste des jours fériés en France (modifiables)
def get_french_holidays(year):
    # Jours fixes
    fixed = [
        date(year, 1, 1),    # Jour de l'An
        date(year, 5, 1),    # Fête du travail
        date(year, 4, 21),   # Fête de paques
        date(year, 5, 8),    # Victoire 1945
        date(year, 7, 14),   # Fête nationale
        date(year, 8, 15),   # Assomption
        date(year, 11, 1),   # Toussaint
        date(year, 11, 11),  # Armistice
        date(year, 12, 25),  # Noël
    ]
    # Pâques et fêtes mobiles
    def easter(year):
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(year, month, day)

    easter_day = easter(year)
    movable = [
        easter_day + timedelta(days=1),    # Lundi de Pâques
        easter_day + timedelta(days=39),   # Ascension
        easter_day + timedelta(days=50),   # Lundi de Pentecôte
    ]
    return set(fixed + movable)

input_text = st.text_area("Collez ici le tableau copié depuis Excel :", height=300)

if input_text:
    try:
        df = pd.read_csv(StringIO(input_text), sep="\t")
    except Exception as e:
        st.error("Erreur lors de la lecture du tableau. Assurez-vous d'avoir copié un tableau valide depuis Excel.")
        st.stop()

    # Nettoyage
    df.columns = df.columns.str.strip()
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Date'])

    df['Début'] = pd.to_datetime(df['Début'], format='%H:%M', errors='coerce').dt.time
    df['Fin'] = pd.to_datetime(df['Fin'], format='%H:%M', errors='coerce').dt.time
    df['Pause non payée'] = df['Pause non payée'].astype(str).str.replace(",", ".").astype(float)
    df['Total (h)'] = df['Total (h)'].astype(str).str.replace(",", ".").astype(float)
    df['Notes du superviseur'] = df['Notes du superviseur'].fillna("").str.lower()

    JOUR_START = 6
    JOUR_END = 21

    # Jours fériés uniques de l'année
    holidays = set()
    for year in df['Date'].dt.year.unique():
        holidays.update(get_french_holidays(year))

    def calculate_hours(row):
        date = row['Date'].date()
        start = datetime.combine(date, row['Début'])
        end = datetime.combine(date + timedelta(days=1) if row['Fin'] < row['Début'] else date, row['Fin'])

        is_renfort = 'renfort' in row['Notes du superviseur']
        is_holiday = date in holidays
        heures_jour = heures_nuit = heures_dimanche = heures_ferie = 0

        is_supp_05 = '+0.5h' in row['Notes du superviseur']
        is_supp_1 = '+1h' in row['Notes du superviseur']
        is_supp_15 = '+1.5h' in row['Notes du superviseur']
        is_supp_2 = '+2h' in row['Notes du superviseur']
        is_supp_25 = '+2.5h' in row['Notes du superviseur']

        current = start
        while current < end:
            next_minute = current + timedelta(minutes=1)
            hour = current.hour + current.minute / 60

            if is_holiday:
                heures_ferie += 1/60
            elif current.weekday() == 6:
                heures_dimanche += 1/60
            elif JOUR_START <= hour < JOUR_END:
                heures_jour += 1/60
            else:
                heures_nuit += 1/60

            current = next_minute

        # Retirer pause des heures de jour
        heures_jour = max(0, heures_jour - row['Pause non payée'])

        supp_hours = 0
        for val, amount in [
            (is_supp_25, 2.5),
            (is_supp_2, 2.0),
            (is_supp_15, 1.5),
            (is_supp_1, 1.0),
            (is_supp_05, 0.5),
        ]:
            if val:
                if heures_nuit >= amount:
                    heures_nuit -= amount
                elif heures_jour >= amount:
                    heures_jour -= amount
                else:
                    deducted = min(heures_jour + heures_nuit, amount)
                    if heures_nuit >= deducted:
                        heures_nuit -= deducted
                    else:
                        deducted_nuit = heures_nuit
                        heures_nuit = 0
                        heures_jour = max(0, heures_jour - (amount - deducted_nuit))
                supp_hours += amount

        # Cas spécial renfort avec heures dimanche => on les garde en dimanche
        if is_renfort and heures_dimanche > 0:
            supp_hours = 0

        if is_renfort:
            return pd.Series([0, 0, heures_dimanche, total, heures_ferie])

        return pd.Series([heures_jour, heures_nuit, heures_dimanche, supp_hours, heures_ferie])

    df[['Heures jour', 'Heures nuit', 'Heures dimanche', 'Heures supp', 'Heures férié']] = df.apply(calculate_hours, axis=1)
    jours_travaillés = df['Date'].nunique()

    # Résumés
    total_jour = df['Heures jour'].sum()
    total_nuit = df['Heures nuit'].sum()
    total_dimanche = df['Heures dimanche'].sum()
    total_ferie = df['Heures férié'].sum()
    total_supp = df['Heures supp'].sum()

    st.header("Résultat global")
    st.write(f"**Nombre de jours travaillés :** {jours_travaillés}")
    st.write(f"**Heures de jour :** {total_jour:.2f} h")
    st.write(f"**Heures de nuit :** {total_nuit:.2f} h")
    st.write(f"**Heures de dimanche :** {total_dimanche:.2f} h")
    st.write(f"**Heures de jours fériés :** {total_ferie:.2f} h")
    st.write(f"**Heures supplémentaires :** {total_supp:.2f} h")
    st.write(f"**Total Heures calculées :** {total_jour + total_nuit + total_dimanche + total_ferie + total_supp:.2f} h")

    # Visualisation
    st.header("Visualisation")
    fig, ax = plt.subplots(figsize=(10, 5))
    df_viz = pd.DataFrame({
        'Date': [d.strftime("%d/%m") for d in df['Date']],
        'Jour': df['Heures jour'],
        'Nuit': df['Heures nuit'],
        'Dimanche': df['Heures dimanche'],
        'Férié': df['Heures férié'],
        'Supp': df['Heures supp'],
    })

    df_viz.set_index('Date').plot(kind='bar', stacked=True, ax=ax)
    plt.ylabel("Heures")
    plt.title("Répartition des heures par jour")
    st.pyplot(fig)

    # Détails
    st.header("Détail de Calcul par ligne")
    st.dataframe(df[['Date', 'Heures jour', 'Heures nuit', 'Heures dimanche', 'Heures férié', 'Heures supp']])
