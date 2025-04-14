import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
import altair as alt
import io
import locale
import re

st.set_page_config(page_title="Analyse des Heures", layout="wide")
st.title("🕒 Analyse des heures de travail - Coller depuis Excel (format FR)")

text_input = st.text_area(
    "📋 Collez ici le tableau depuis Excel :",
    height=350,
    help="Collez les données avec entêtes (colonnes : Date, Début, Fin, Pause non payée, Total (h), Notes du superviseur)"
)

def parse_french_date(text):
    try:
        clean = re.sub(r"^\w+\s", "", text)  # Supprime "lundi ", "mardi ", etc.
        return datetime.strptime(clean, "%d %B %Y")
    except Exception:
        return pd.NaT

def parse_datetime(date_str, hour_str):
    if pd.isna(date_str) or pd.isna(hour_str):
        return None
    try:
        hour_str = str(hour_str).replace(',', '.')
        h, m = map(int, hour_str.split(":"))
        date_obj = parse_french_date(date_str)
        return datetime.combine(date_obj.date(), time(h, m))
    except:
        return None

def calculate_hours(start, end):
    if pd.isna(start) or pd.isna(end):
        return 0, 0, 0

    if end <= start:
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

if text_input:
    try:
        sep = "\t" if "\t" in text_input else ";"
        df = pd.read_csv(io.StringIO(text_input), sep=sep)

        # Convertir noms de colonnes en uniformes
        df.columns = [col.strip() for col in df.columns]

        # Normaliser les colonnes avec noms exacts
        expected_cols = ["Date", "Début", "Fin", "Pause non payée", "Total (h)", "Notes du superviseur"]
        if not all(col in df.columns for col in expected_cols):
            st.error("❌ Veuillez inclure toutes les colonnes attendues : " + ", ".join(expected_cols))
        else:
            summary = {
                "Jours travaillés": 0,
                "Heures de Jour": 0,
                "Heures de Nuit": 0,
                "Heures de Dimanche": 0,
                "Heures Sup. Renfort": 0,
            }

            details = []

            for _, row in df.iterrows():
                date_str = row["Date"]
                debut = parse_datetime(date_str, row["Début"])
                fin = parse_datetime(date_str, row["Fin"])
                pause = float(str(row["Pause non payée"]).replace(',', '.')) if not pd.isna(row["Pause non payée"]) else 0
                total_h = float(str(row["Total (h)"]).replace(',', '.')) if not pd.isna(row["Total (h)"]) else 0
                notes = str(row.get("Notes du superviseur", "")).lower()

                if pd.notna(debut) and pd.notna(fin):
                    summary["Jours travaillés"] += 1
                    jour, nuit, dimanche = calculate_hours(debut, fin)
                    jour -= pause

                    summary["Heures de Jour"] += max(jour, 0)
                    summary["Heures de Nuit"] += max(nuit, 0)
                    summary["Heures de Dimanche"] += max(dimanche, 0)

                    if "renfort" in notes:
                        summary["Heures Sup. Renfort"] += total_h

                    details.append({
                        "Date": parse_french_date(date_str).date(),
                        "Heures de Jour": round(jour, 2),
                        "Heures de Nuit": round(nuit, 2),
                        "Heures de Dimanche": round(dimanche, 2),
                        "Heures Sup. Renfort": round(total_h if "renfort" in notes else 0, 2)
                    })

            st.subheader("🧾 Résumé global")
            st.write(pd.DataFrame([summary]))

            st.subheader("📈 Visualisation graphique")
            details_df = pd.DataFrame(details)

            melted = details_df.melt(
                id_vars="Date",
                value_vars=["Heures de Jour", "Heures de Nuit", "Heures de Dimanche", "Heures Sup. Renfort"],
                var_name="Type d'heure",
                value_name="Durée (h)"
            )

            chart = alt.Chart(melted).mark_bar().encode(
                x='Date:T',
                y='Durée (h):Q',
                color='Type d\'heure:N',
                tooltip=['Date:T', 'Type d\'heure:N', 'Durée (h):Q']
            ).properties(width=800, height=400).interactive()

            st.altair_chart(chart, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Erreur lors du traitement : {e}")
