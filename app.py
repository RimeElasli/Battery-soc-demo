import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from scipy.interpolate import PchipInterpolator

# ===== Modèle de la batterie =====
z_tab = np.array([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
OCV_tab = np.array([2.500, 3.331, 3.461, 3.545, 3.602, 3.666, 3.770, 3.860, 3.946, 4.054, 4.184])
ocv = PchipInterpolator(z_tab, OCV_tab)
docv = ocv.derivative()

R0 = 0.0528
R1 = 0.0362
R2 = 1e-4
TAU1 = 12.37
TAU2 = 60.0
Q = 7187.0

def tension(i, iR1, iR2, z):
    return ocv(z) - R0*i - R1*iR1 - R2*iR2

def predire(i, iR1, iR2, z, dt):
    a1 = np.exp(-dt/TAU1)
    a2 = np.exp(-dt/TAU2)
    iR1_new = a1*iR1 + (1 - a1)*i
    iR2_new = a2*iR2 + (1 - a2)*i
    z_new = z - (i/Q)*dt
    return z_new, iR1_new, iR2_new

@st.cache_data
def charger(cycle):
    return pd.read_csv(cycle)

@st.cache_data
def simuler(cycle, z0, k_saut, saut):
    df = charger(cycle)
    t = df["t"].to_numpy(dtype=float)
    i_mes = df["i"].to_numpy(dtype=float)
    v_mes = df["v"].to_numpy(dtype=float)
    if np.mean(i_mes) < 0:
        i_mes = -i_mes
    dt = np.diff(t)
    Q_ref = np.sum(i_mes[1:] * dt)

    z_ref = 1.0
    z_cc = z0
    z_v1, iR1_v1, iR2_v1 = z0, 0.0, 0.0
    z, iR1, iR2 = z0, 0.0, 0.0
    K = 0.1
    P = np.diag([0.1**2, 0.01, 0.01])
    Q_bruit = np.diag([1e-6, 1e-4, 1e-4])
    R_bruit = 0.07**2

    ref, cc, v1, ekf = [], [], [], []
    for k in range(1, len(t)):
        if k == k_saut:
            z_cc = z_cc + saut
            z_v1 = z_v1 + saut
            z = z + saut

        z_ref = z_ref - (i_mes[k]/Q_ref)*dt[k-1]
        z_cc = z_cc - (i_mes[k]/Q)*dt[k-1]

        z_pred, iR1_v1, iR2_v1 = predire(i_mes[k], iR1_v1, iR2_v1, z_v1, dt[k-1])
        e = v_mes[k] - tension(i_mes[k], iR1_v1, iR2_v1, z_pred)
        z_v1 = z_pred + K*e/docv(z_pred)

        z_pred, iR1_pred, iR2_pred = predire(i_mes[k], iR1, iR2, z, dt[k-1])
        e = v_mes[k] - tension(i_mes[k], iR1_pred, iR2_pred, z_pred)
        a1 = np.exp(-dt[k-1]/TAU1)
        a2 = np.exp(-dt[k-1]/TAU2)
        A = np.diag([1, a1, a2])
        P_pred = A @ P @ A.T + Q_bruit
        H = np.array([docv(z_pred), -R1, -R2])
        S = H @ P_pred @ H + R_bruit
        K_v2 = P_pred @ H / S
        z, iR1, iR2 = np.array([z_pred, iR1_pred, iR2_pred]) + K_v2*e
        P = (np.eye(3) - np.outer(K_v2, H)) @ P_pred

        ref.append(z_ref)
        cc.append(z_cc)
        v1.append(z_v1)
        ekf.append(z)

    return t[1:], np.array(ref), np.array(v1), np.array(ekf), np.array(cc)

# ===== Page =====
st.set_page_config(page_title="Jeu de la batterie", page_icon="🔋")
st.title("🔋 Peut-on tromper le filtre ?")

onglet1, onglet2 = st.tabs(["Trompe le filtre", "Devine le SOC"])

with onglet1:
    st.write("La batterie se décharge. Le filtre doit deviner son niveau de charge (SOC) en regardant seulement le courant et la tension. À toi de le piéger : donne-lui un mauvais départ, ou fausse son calcul en cours de route.")

    choix = st.radio("Batterie", ["Neuve", "Vieillie"], horizontal=True)
    st.caption("Vieillie : la même batterie après une centaine de cycles. Elle a perdu de la capacité, mais le filtre ne le sait pas.")
    cycle = "cycle0.csv" if choix == "Neuve" else "cycle100.csv"
    t_csv = charger(cycle)["t"].to_numpy(dtype=float)

    z0 = st.slider("SOC de départ donné au filtre (%)", 50, 100, 100, step=5) / 100
    t_saut = st.slider("Moment de l'erreur injectée (s)", 0, int(t_csv[-1]), int(t_csv[-1]) // 2, step=50)
    saut = st.slider("Taille de l'erreur injectée (%)", -30, 30, -10, step=5) / 100
    st.caption("Le vrai SOC part toujours de 100 %. Au moment choisi, on fausse brutalement le SOC que le filtre croit connaître, comme un bug.")
    k_saut = int(np.searchsorted(t_csv, t_saut))

    t1, ref, v1, ekf, cc = simuler(cycle, z0, k_saut, saut)

    fig, ax = plt.subplots()
    ax.plot(t1, ref*100, "k--", label="vrai SOC")
    ax.plot(t1, v1*100, label="v1 gain fixe")
    ax.plot(t1, ekf*100, label="EKF")
    ax.plot(t1, cc*100, ":", color="gray", label="comptage seul")
    if saut != 0 and k_saut > 0:
        ax.axvline(t_saut, color="red", lw=0.8, label="erreur injectée")
    ax.set_xlabel("temps (s)")
    ax.set_ylabel("SOC (%)")
    ax.legend()
    st.pyplot(fig)
    st.caption("Noir : le vrai SOC. Gris : on compte seulement le courant, sans regarder la tension, donc une erreur n'est jamais rattrapée. Bleu : un filtre simple à gain fixe. Orange : le filtre de Kalman étendu (EKF), qui ajuste sa confiance à chaque instant.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Erreur moyenne EKF", f"{np.mean(np.abs(ekf - ref))*100:.1f} %")
    c2.metric("Erreur moyenne v1", f"{np.mean(np.abs(v1 - ref))*100:.1f} %")
    c3.metric("Erreur moyenne comptage", f"{np.mean(np.abs(cc - ref))*100:.1f} %")
    st.caption("Erreur moyenne : écart moyen entre l'estimation et le vrai SOC, sur toute la décharge.")

with onglet2:
    st.write("Un instant de la décharge est tiré au hasard. Tu vois seulement la tension de la batterie : devine son niveau de charge !")

    t2, ref2, v1_2, ekf2, cc2 = simuler("cycle0.csv", 1.0, 0, 0.0)   # cellule neuve, sans erreur injectée
    v_csv = charger("cycle0.csv")["v"].to_numpy(dtype=float)
    candidats = np.where((ref2 > 0.05) & (ref2 < 0.95))[0]           # on évite les tout débuts et toutes fins

    if "j" not in st.session_state:
        st.session_state.j = int(np.random.choice(candidats))
        st.session_state.revele = False

    j = st.session_state.j
    st.metric("Tension mesurée", f"{v_csv[j+1]:.2f} V")
    st.caption("Indice : pleine, la batterie affiche environ 4,2 V ; vide, environ 2,7 V. Mais entre les deux, la tension bouge très peu…")

    guess = st.slider("Ton estimation du SOC (%)", 0, 100, 50, step=1)

    col_a, col_b = st.columns(2)
    if col_a.button("Révéler"):
        st.session_state.revele = True
    if col_b.button("Nouvel instant"):
        st.session_state.j = int(np.random.choice(candidats))
        st.session_state.revele = False
        st.rerun()

    if st.session_state.revele:
        vrai = ref2[j] * 100
        filtre = ekf2[j] * 100
        c1, c2, c3 = st.columns(3)
        c1.metric("Ta réponse", f"{guess} %", f"{guess - vrai:+.1f} pts", delta_color="off")
        c2.metric("Filtre (EKF)", f"{filtre:.1f} %", f"{filtre - vrai:+.1f} pts", delta_color="off")
        c3.metric("Vrai SOC", f"{vrai:.1f} %")
        if abs(guess - vrai) < abs(filtre - vrai):
            st.success("Bravo, tu as battu le filtre !")
        else:
            st.warning("Le filtre a gagné cette fois.")
        st.caption("Le filtre ne regarde pas qu'une seule tension : il suit tout l'historique du courant et de la tension depuis le début de la décharge.")
        st.title("🔋 Peut-on tromper le filtre ?")
