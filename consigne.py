import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
import altair as alt

st.set_page_config(page_title="Analyse des Heures", layout="wide")
st.title("🕒 Analyse des Heures de Travail")

uploaded_file = st.file_uploader("📤 Importer un fichier Excel ou CSV", type=["xlsx", "xls", "csv"])

def parse_datetime(date_str, time_str):
    if pd.isna(date_str) or pd.isna(time_str):
        return None
    try:
        if isinstance(time_str, str) and ":" not in time_str:
            time_str = f"{time_str}:00"
        dt_str = f"{date_str} {time_str}"
        return pd.to_datetime(dt_str)
    except:
        return None

def calculate_hours(start, end):
    if pd.isna(start) or pd.isna(end):
        return 0, 0, 0

    if end < start:
        end += timedelta(days=1)

    total_day = timedelta()
    total_night = timedelta()
    total_sunday = timedelta()

    current = start
    while current < end:
        next_step = min(end, current + timedelta(minutes=1))

        if current.weekday() == 6:
            total_sunday += (next_step - current)

        if time(6, 0) <= current.time() < time(21, 0):
            total_day += (next_step - current)
        else:
            total_night += (next_step - current)

        current = next_step

    return total_day.total_seconds() / 3600, total_night.total_seconds() / 3600, total_sunday.total_seconds() / 3600

if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    required_cols = ["Date", "Début", "Fin", "Pause non payé", "Total (h)", "Notes de superviseur"]
    if not all(col in df.columns for col in required_cols):
        st.error(f"Le fichier doit contenir les colonnes : {', '.join(required_cols)}")
    else:
        # Résumé
        summary = {
            "Jours travaillés": 0,
            "Heures de Jour": 0,
            "Heures de Nuit": 0,
            "Heures de Dimanche": 0,
            "Heures Sup. Renfort": 0,
        }

        # Détail par date pour le graphique
        details = []

        for idx, row in df.iterrows():
            date = row["Date"]
            debut = parse_datetime(date, row["Début"])
            fin = parse_datetime(date, row["Fin"])
            pause = row["Pause non payé"] if not pd.isna(row["Pause non payé"]) else 0
            total_h = row["Total (h)"] if not pd.isna(row["Total (h)"]) else 0
            notes = row.get("Notes de superviseur", "")

            if pd.notna(debut) and pd.notna(fin):
                summary["Jours travaillés"] += 1
                jour, nuit, dimanche = calculate_hours(debut, fin)
                jour -= pause

                summary["Heures de Jour"] += max(jour, 0)
                summary["Heures de Nuit"] += max(nuit, 0)
                summary["Heures de Dimanche"] += max(dimanche, 0)

                if isinstance(notes, str) and "renfort" in notes.lower():
                    summary["Heures Sup. Renfort"] += total_h

                details.append({
                    "Date": pd.to_datetime(date).date(),
                    "Heures de Jour": round(jour, 2),
                    "Heures de Nuit": round(nuit, 2),
                    "Heures de Dimanche": round(dimanche, 2),
                    "Heures Sup. Renfort": round(total_h if "renfort" in str(notes).lower() else 0, 2)
                })

        st.subheader("📊 Résumé des heures")
        st.write(pd.DataFrame([summary]))

        # === Graphique par date ===
        st.subheader("📈 Visualisation des heures par date")
        details_df = pd.DataFrame(details)

        hours_long = details_df.melt(id_vars="Date", 
                                     value_vars=["Heures de Jour", "Heures de Nuit", "Heures de Dimanche", "Heures Sup. Renfort"],
                                     var_name="Type d'heure", value_name="Durée (h)")

        chart = alt.Chart(hours_long).mark_bar().encode(
            x='Date:T',
            y='Durée (h):Q',
            color='Type d\'heure:N',
            tooltip=['Date:T', 'Type d\'heure:N', 'Durée (h):Q']
        ).properties(
            width=800,
            height=400
        ).interactive()

        st.altair_chart(chart, use_container_width=True)
