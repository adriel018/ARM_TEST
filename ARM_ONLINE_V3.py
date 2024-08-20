import streamlit as st  # Biblioteca da interface
import streamlit_authenticator as stauth
from streamlit_option_menu import option_menu  # Menu personalizado do site
from streamlit_js_eval import streamlit_js_eval
from streamlit.components.v1 import html
from PIL import Image  # Converte a imagem da logo para um formato que pode ser exibido no site
import numpy as np  # Biblioteca para cálculo com funções
import plotly.graph_objects as go  # Bibliotoeca para criação dos gráficos
from numpy import mean, ceil  # Biblioteca para cálculo com funções
import yaml  # Biblioteca do banco de dados
from yaml.loader import SafeLoader  # Biblioteca para leitura do banco de dados
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import TableStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.platypus import Table
from reportlab.pdfgen import canvas
import io
import base64
from datetime import datetime
import dropbox
from time import sleep

units = {
    'm': lambda x: x,
    'ft': lambda x: x / 3.281,
    'miles': lambda x: x * 1609,
    'C': lambda x: x,
    'F': lambda x: (x - 32) / 1.8,
    'K': lambda x: x - 273
}

#  Abrindo o arquivo com o banco de dados de scores e ações mitigadoras
with open('ARM_database.yaml') as file:
    db = yaml.load(file, Loader=SafeLoader)

with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

#  Configurações da página web
logo = 'logo.png'
img_logo = Image.open(logo)
arquivo = 'logo.png'
image = Image.open(arquivo)
PAGE_CONFIG = {"page_title": "Web app | Syngular Solutions",
               "page_icon": image,
               "layout": "wide",
               "initial_sidebar_state": "auto",
               }

st.set_page_config(**PAGE_CONFIG)
st.image(img_logo, width=150)  # Inserindo a logo no site


authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['pre-authorized']
)

aux = False
query = st.query_params

with open('log.txt', 'w') as log:
    for ch, valor in st.session_state.items():
        log.write(f'{ch}: {valor}\n')



@st.experimental_dialog("Load file")
def upload():
    pass


@st.experimental_dialog("Save progress")
def save():
    pass


@st.experimental_dialog("New session")
def new_session():
    st.markdown('Start a new session?')
    st.markdown('Any information not saved can be lost! :warning:')
    space1, space2 = st.columns(2)
    with space1:
        if st.button("Yes", use_container_width=True):
            streamlit_js_eval(js_expressions="parent.window.location.reload()")
    with space2:
        if st.button('No', use_container_width=True):
            st.rerun()


# Função que controla o score de robustness para plotar no gráfico
def sum_rob(check, mandatory, type_robustness, type_complexity, end):
    count = sum(1 for action in st.session_state if action.endswith(f"{end}"))

    try:
        step = float(st.session_state[type_complexity]) / count

    except ZeroDivisionError:
        step = 0

    if mandatory:
        if st.session_state[f'{check}']:
            robustness = float(st.session_state[type_robustness]) + step
            st.session_state[type_robustness] = format(robustness, '.2f')
        else:
            robustness = float(st.session_state[type_robustness]) - step
            st.session_state[type_robustness] = format(robustness, '.2f')
    else:
        if st.session_state[f'{check}']:
            robustness = float(st.session_state[type_robustness]) + (step + 0.3)
            st.session_state[type_robustness] = format(robustness, '.2f')
        else:
            robustness = float(st.session_state[type_robustness]) - (step + 0.3)
            st.session_state[type_robustness] = format(robustness, '.2f')


def add_contingency(location, col1, col2):
    if 'count_contingency' not in st.session_state:
        st.session_state.count_contingency = 1
    st.session_state.count_contingency += 1
    for i in range(st.session_state.count_contingency - 1):
        with col1:
            st.text_input(f'Action {i + 2}',
                          key=f'Action {i + 2}_contingency')
        with col2:
            st.text_input('Considerations',
                          key=f'Considerations {i + 2}_consider')


# Função que reseta a robustness quando o usuário altera o tipo de problema do poço
def reset_rob(end_m, end_s, robustness_type):
    for j in st.session_state:
        if j.endswith(f'{end_m}') or j.endswith(f'{end_s}'):
            st.session_state[f'{j}'] = False

    st.session_state[f'{robustness_type}'] = 0


def formation_drilled(dict_key, formation_type):
    if st.session_state[f'{dict_key}']:
        st.session_state.formation_geoscore += db['Geology']['Formation to Drill'][
            f'{formation_type}']['score']
    else:
        st.session_state.formation_geoscore -= db['Geology']['Formation to Drill'][
            f'{formation_type}']['score']


def pressure_drilled(dict_key, pressure_type):
    if 'pressure_geoscore' not in st.session_state:
        st.session_state.pressure_geoscore = 0

    if st.session_state[f'{dict_key}']:
        st.session_state.pressure_geoscore += db['Geology']['Formations Pressures'][
            f'{pressure_type}']['score']
    else:
        st.session_state.pressure_geoscore -= db['Geology']['Formations Pressures'][
            f'{pressure_type}']['score']


def reset_action_f(key, action_type, type_robustness, type_complexity, end):
    st.session_state[f'{key}'] = False
    if action_type:
        sum_rob(key, True, type_robustness, type_complexity, end)
    else:
        sum_rob(key, False, type_robustness, type_complexity, end)


def reset_action_t(key, action_type, type_robustness, type_complexity, end):
    st.session_state[f'{key}'] = True
    if action_type:
        sum_rob(key, True, type_robustness, type_complexity, end)
    else:
        sum_rob(key, False, type_robustness, type_complexity, end)


# Função que adiciona um novo problema no ARM (por um ADM) e coloca no banco de dados de problemas
def ad_problem(area, problem, options, score, mandatory, suggest, mandatory_score, suggest_score):
    op_select = options.split(';')
    m_act = mandatory.split(';')
    s_act = suggest.split(';')
    parameters = {'action_s_score': suggest_score, 'action_m_score': mandatory_score,
                  'actions_s': s_act, 'actions_m': m_act, 'options': op_select, 'score': score}

    db_input['Master'][f'{area}'][f'{problem}'] = parameters

    with open('teste.yaml', 'w') as file:
        yaml.dump(db_input, file, default_flow_style=False)


def add_user(name, username, password, email, company, user_type, date):
    pass


def crit_matrix():
    fig2 = go.Figure()

    if 'general_complexity' not in st.session_state:
        st.session_state.general_complexity = 0
    if 'gen_robustness' not in st.session_state:
        st.session_state.gen_robustness = 0

    if 'geo_complexity' not in st.session_state:
        st.session_state.geo_complexity = 0
    if 'geo_robustness' not in st.session_state:
        st.session_state.geo_robustness = 0

    if 'drill_complexity' not in st.session_state:
        st.session_state.drill_complexity = 0
    if 'drill_robustness' not in st.session_state:
        st.session_state.drill_robustness = 0

    if 'comp_complexity' not in st.session_state:
        st.session_state.comp_complexity = 0
    if 'comp_robustness' not in st.session_state:
        st.session_state.comp_robustness = 0

    if 'log_complexity' not in st.session_state:
        st.session_state.log_complexity = 0
    if 'log_robustness' not in st.session_state:
        st.session_state.log_robustness = 0

    if 'meto_complexity' not in st.session_state:
        st.session_state.meto_complexity = 0
    if 'meto_robustness' not in st.session_state:
        st.session_state.meto_robustness = 0

    if 'brk_complexity' not in st.session_state:
        st.session_state.brk_complexity = 0
    if 'brk_robustness' not in st.session_state:
        st.session_state.brk_robustness = 0

    for i in st.session_state:
        if i.endswith('_robustness'):
            if float(st.session_state[f'{i}']) > 5:
                st.session_state[f'{i}'] = 5

    # Adicionando cor de fundo do gráfico (verde claro)
    fig2.add_shape(
        type='rect',
        x0=0, y0=0, x1=5, y1=5,
        fillcolor='rgba(0, 255, 0, 0.5)',
        line=dict(color='rgba(0, 255, 0, 0)'),
        layer='below'
    )

    # Adicionando linha pontilhada da diagonal do gráfico
    fig2.add_shape(
        type='line',
        x0=0,
        y0=0,
        x1=5,
        y1=5,
        line=dict(
            dash='dot',
            color='black',
            width=2
        ),
        layer='below'
    )

    # Adicionando diagonal superior (verde escuro)

    fig2.add_shape(
        type='path',
        path='M 0 0.5 L 0 5 L 4.5 5 Z',
        fillcolor='rgba(35, 142, 35, 1.0)',
        line=dict(color='rgba(0, 100, 0, 0)'),
        layer='below'
    )

    # Adicionando diagonal inferior (vermelha)
    fig2.add_shape(
        type='path',
        path='M 0.5 0 L 5 4.5 L 5 0 Z',
        fillcolor='rgba(255, 0, 0, 1.0)',
        line=dict(color='rgba(255, 0, 0, 0)'),
        layer='below'
    )

    points = [
        {"x": float(st.session_state.general_complexity), "y": float(st.session_state.gen_robustness),
         "symbol": "diamond", "name": "Well Characteristics", 'color': 'blue'},
        {"x": float(st.session_state.geo_complexity), "y": float(st.session_state.geo_robustness),
         "symbol": "circle", "name": "Geology", 'color': 'orange'},
        {"x": float(st.session_state.drill_complexity), "y": float(st.session_state.drill_robustness),
         "symbol": "pentagon", "name": "Drilling", 'color': 'brown'},
        {"x": float(st.session_state.comp_complexity), "y": float(st.session_state.comp_robustness),
         "symbol": "star", "name": "Completion", 'color': 'navy'},
        {"x": float(st.session_state.log_complexity), "y": float(st.session_state.log_robustness),
         "symbol": "triangle-up", "name": "Logistic", 'color': 'black'},
        {"x": float(st.session_state.meto_complexity), "y": float(st.session_state.meto_robustness),
         "symbol": "hexagon", "name": "Metocean", 'color': 'gray'},
        {"x": float(st.session_state.brk_complexity), "y": float(st.session_state.brk_robustness),
         "symbol": "square", "name": "Braskem", 'color': 'cyan'},
    ]

    for point in points:
        fig2.add_trace(go.Scatter(
            x=[point["x"]],
            y=[point["y"]],
            mode='markers',
            marker=dict(symbol=point["symbol"], size=10, color=point['color']),
            name=point["name"],
        ))

    fig2.update_layout(
        title=dict(
            text='Robustness Matrix',
            x=0.6,  # Posição central horizontal
            xanchor='center'  # Ancoragem central
        ),
        xaxis=dict(
            title='Complexity',
            range=[0, 5],
            tickmode='array',
            tickvals=np.arange(0, 6, 1),
            side="bottom",
            mirror=True,
            ticks='outside',
            showline=True,
            linewidth=2,
            linecolor='black',
            showgrid=False  # Remove as linhas de grade
        ),
        yaxis=dict(
            title='Robustness',
            range=[0, 5],
            tickmode='array',
            tickvals=np.arange(0, 6, 1),
            side="left",
            mirror=True,
            ticks='outside',
            showline=True,
            linewidth=2,
            linecolor='black',
            showgrid=False  # Remove as linhas de grade
        ),
        showlegend=True,
        legend=dict(
            orientation="h",  # Orientação horizontal
            y=-0.4,  # Posição abaixo do gráfico
            x=0.1,  # Alinhamento central
            # bordercolor='rgb(128,128,128)',  # Cor da borda da legenda
            # borderwidth=1  # Largura da borda da legenda
        ),
        autosize=False,
        width=315,
        height=400,
        margin=dict(l=60, r=15, t=30, b=0)
    )
    return fig2


def ic_graph(complexity, robustness, name):
    if f'{complexity}' not in st.session_state:
        st.session_state[f'{complexity}'] = 0
    if f'{robustness}' not in st.session_state:
        st.session_state[f'{robustness}'] = 0
    plot_bgcolor = "#FFFFFF00"
    if name == 'Complexity':
        gph_colors = [plot_bgcolor, "#f25829", "#f2a529", "#eff229", "#85e043", "#2bad4e"]
    else:
        gph_colors = [plot_bgcolor, '#005a32', '#238443', '#4daf4a', '#7fbc41', '#c7e9c0']

    quadrant_colors = gph_colors
    # quadrant_text = ["", "<b>Very high</b>", "<b>High</b>", "<b>Medium</b>", "<b>Low</b>", "<b>Very low</b>"]
    n_quadrants = len(quadrant_colors) - 1

    current_value = st.session_state[f'{complexity}']
    min_value = 0
    max_value = 5
    hand_length = np.sqrt(2) / 3.5
    hand_angle = np.pi * (
            1 - (max(min_value, min(max_value, current_value)) - min_value) / (max_value - min_value))

    annotations = [
        go.layout.Annotation(
            text=f"{0}",
            x=-0.03, xanchor="center", xref="paper",
            y=0.48, yanchor="bottom", yref="paper",

            showarrow=False,
            font=dict(
                size=15,  # Tamanho do texto
                color="black",  # Cor do texto
                family="Arial, sans-serif",  # Família de fontes
                weight="bold"  # Negrito
            )
        ),
        go.layout.Annotation(
            text=f"{1}",
            x=0.07, xanchor="center", xref="paper",
            y=0.77, yanchor="bottom", yref="paper",

            showarrow=False,
            font=dict(
                size=15,  # Tamanho do texto
                color="black",  # Cor do texto
                family="Arial, sans-serif",  # Família de fontes
                weight="bold"  # Negrito
            )
        ),
        go.layout.Annotation(
            text=f"{2}",
            x=0.33, xanchor="center", xref="paper",
            y=0.96, yanchor="bottom", yref="paper",

            showarrow=False,
            font=dict(
                size=15,  # Tamanho do texto
                color="black",  # Cor do texto
                family="Arial, sans-serif",  # Família de fontes
                weight="bold"  # Negrito
            )
        ),
        go.layout.Annotation(
            text=f"{3}",
            x=0.67, xanchor="center", xref="paper",
            y=0.96, yanchor="bottom", yref="paper",

            showarrow=False,
            font=dict(
                size=15,  # Tamanho do texto
                color="black",  # Cor do texto
                family="Arial, sans-serif",  # Família de fontes
                weight="bold"  # Negrito
            )
        ),
        go.layout.Annotation(
            text=f"{4}",
            x=0.935, xanchor="center", xref="paper",
            y=0.77, yanchor="bottom", yref="paper",

            showarrow=False,
            font=dict(
                size=15,  # Tamanho do texto
                color="black",  # Cor do texto
                family="Arial, sans-serif",  # Família de fontes
                weight="bold"  # Negrito
            )
        ),
        go.layout.Annotation(
            text=f"{5}",
            x=1.03, xanchor="center", xref="paper",
            y=0.48, yanchor="bottom", yref="paper",

            showarrow=False,
            font=dict(
                size=15,  # Tamanho do texto
                color="black",  # Cor do texto
                family="Arial, sans-serif",  # Família de fontes
                weight="bold"  # Negrito
            )
        )
    ]

    fig = go.Figure(
        data=(
            go.Pie(
                values=[0.5] + (np.ones(n_quadrants) / 2 / n_quadrants).tolist(),
                rotation=90,
                hole=0.5,
                marker=dict(colors=quadrant_colors),
                # text=quadrant_text,
                textinfo="text",
                hoverinfo="skip",
            ),
        ),
        layout=go.Layout(
            title=dict(
                text=f'{name}',
                x=0.5,  # Posição central horizontal
                xanchor='center'  # Ancoragem central
            ),
            showlegend=False,
            margin=dict(b=30, t=30, l=30, r=30),
            width=280,
            height=280,
            # paper_bgcolor=plot_bgcolor,
            annotations=annotations,
            shapes=[
                go.layout.Shape(
                    type="circle",
                    x0=0.48, x1=0.52,
                    y0=0.48, y1=0.52,
                    fillcolor="#333",
                    line=dict(color="#333"),
                ),
                go.layout.Shape(
                    type="line",
                    x0=0.5, x1=0.5 + hand_length * np.cos(hand_angle),
                    y0=0.5, y1=0.5 + hand_length * np.sin(hand_angle),
                    line=dict(color="#333", width=4)
                )
            ]
        )
    )
    return fig


def actions_fallow_up():
    total_mandatory_actions = sum(
        1 for chave, valor in dict(st.session_state).items() if chave.endswith('maction'))

    m_actions_fallow = sum(1 for chave, valor in st.session_state.items() if chave.endswith('maction') and valor)

    total_suggest_actions = sum(
        1 for chave, valor in dict(st.session_state).items() if chave.endswith('saction'))

    s_actions_fallow = sum(1 for chave, valor in st.session_state.items() if chave.endswith('saction') and valor)

    try:
        st.session_state.r_mandatory = (m_actions_fallow / total_mandatory_actions) * 100
    except ZeroDivisionError:
        st.session_state.r_mandatory = 0

    try:
        st.session_state.r_suggest = (s_actions_fallow / total_suggest_actions) * 100
    except ZeroDivisionError:
        st.session_state.r_suggest = 0

    return st.session_state.r_suggest, st.session_state.r_mandatory


# Página inicial do menu do site
def home_page():
    # query['Access'] = 'Home'
    st.title('Syngular Solutions Web Application')
    st.markdown('---')
    st.markdown('''
We are excited to introduce our latest software, an innovative tool developed for the oil and gas industry. This software has been carefully designed to identify and analyze the complexities involved in well drilling operations. Aiming to enhance the robustness and efficiency of drilling projects, our tool not only detects potential challenges but also offers precise recommendations for mitigative actions. \n
With a user-friendly interface, our software stands out by providing practical solutions that help minimize risks and optimize operations. Whether you are an experienced drilling engineer or a project manager, this tool will be essential for improving decision-making and ensuring the success of your drilling operations. \n
Access now and discover how our software can transform your projects, providing greater safety, efficiency, and resource savings in oil well drilling.
    ''')


# Página do ARM
def arm_page():
    # query['Access'] = '/Advanced-risk-mitigation'
    st.title('Advanced Risk Mitigation - ARM')  # Título

    s1, s2, s3, s4, s5 = st.columns((0.2, 0.2, 0.2, 1, 1))

    with s1:
        if st.button(':page_facing_up: New', use_container_width=True, type="secondary"):
            new_session()

    with s2:
        if st.button(':floppy_disk: Save', use_container_width=True, type="secondary"):
            save()
    with s3:
        if st.button(':open_file_folder: Load', use_container_width=True, type="secondary"):
            upload()

    tabs = st.tabs(['Input', 'Actions', 'Output', 'Report'])  # Criando as abas de ações do ARM

    with tabs[0]:
        tabs2 = st.tabs(['General', 'Geology', 'Drilling', 'Completion', 'Logistics',
                         'Metocean', 'Braskem'])  # Criando as abas de áreas da perfuração
        # Cada área da perfurção tem seu Input e Actions

    # Aba General
    with tabs2[0]:

        # Tips
        help_well_type = '''
        # Infill

        Test

        # Development


        Test
        '''

        col1, col2, col3, col4 = st.columns((1, 1.2, 1, 1.1))  # Criando as colunas e definindo as larguras

        #  Coluna de informações báscias do poço e do usuário
        with col1:
            container = st.container(border=True)  # Criando um container com borda
            with container:
                st.write('Basic Well Info')
                st.text_input('User Name', max_chars=None, key='user_name', type="default")
                st.text_input('Country', max_chars=None, key='country_name', type="default")
                st.text_input('Company Name', max_chars=None, key='company_name', type="default")
                st.text_input('Field Name', max_chars=None, key='field_name', type="default")
                st.text_input('Well Name', max_chars=None, key='well_name', type="default")
                st.text_input('Well Coordinates UTM(m): N/S E/W', max_chars=None, key='coordinate', type="default")
                st.text_input('Datum', key='date')
                st.text_area('Well objective', max_chars=None, key='comments')

        # Conluna de problemas das característiscas do poço
        with col2:
            container2 = st.container(border=True)
            with container2:
                st.write('Well Characteristics')
                st.selectbox('Operation Area',
                             ['Oil & Gas', 'CO2 Injection', 'Dissolution Mining'],
                             key='op_area', on_change=reset_rob,
                             args=('_maction', '_action', 'gen_robustness'))

                well_options = ['Infill', 'Development', 'Wildcat', 'Exploratory', 'Decommissioning Well',
                                'Intervention', 'Interception well', 'Geothermal']
                well_type = st.selectbox('Well Type',
                                         well_options,
                                         key='well_type', on_change=reset_rob,
                                         args=('_maction', '_action', 'gen_robustness'), help=help_well_type)

                if st.session_state.well_type == 'Interception well':
                    st.selectbox('Interception Type',
                                 ['Relief Well', 'Decommissioning Well'],
                                 key='inter_type', on_change=reset_rob,
                                 args=('_maction', '_action', 'gen_robustness'))

                if 'fp' not in st.session_state:
                    st.session_state.fp = 0

                if 'wd' not in st.session_state:
                    st.session_state.wd = 0

                if well_type == 'Relief Well':
                    st.number_input('Open Flow Potential', help='Valor em "bpd"',
                                    step=100.0, format='%f', on_change=reset_rob, key='fp',
                                    min_value=0.0, args=('_maction', '_action', 'gen_robustness'))
                rig_type = st.selectbox('Rig Type',
                                        ['Onshore', 'Jack Up', 'Fixed', 'TLP,Spar or Compliant Tower',
                                         'Floater Anchored',
                                         'Floater DP'], key='rig_type', on_change=reset_rob,
                                        args=('_maction', '_action', 'gen_robustness'))
                if rig_type == 'Onshore':
                    st.number_input('Rotary Table Height', key='rt', help='Value in "meters')
                else:
                    st.number_input('Airgap', key='airgap', help='Value in "meters')
                    c1, c2 = st.columns((1, 0.4))
                    with c1:
                        st.number_input('Water Depth', help='Valor em "ft"', step=100.0, format='%f',
                                        on_change=reset_rob, key='wt', min_value=0.0,
                                        args=('_maction', '_action', 'gen_robustness'))
                    with c2:
                        st.selectbox('Unit:', options=['m', 'ft'], key='wd_unit')
                        st.session_state.wd = units[f'{st.session_state.wd_unit}'](st.session_state.wt)

                st.selectbox('Rig Status', ['Defined', 'Defined with limitation', 'Not defined'],
                             key='rig_status', on_change=reset_rob, args=('_maction', '_action', 'gen_robustness'))

                st.selectbox('Correlation Wells',
                             ['Select', 'Above 2 correlation wells', '1 or 2 correlation wells',
                              'No correlation wells'], key='Correlation_wells',
                             on_change=reset_rob, args=('_maction', '_action', 'gen_robustness'))
                st.selectbox('Data Quality and Confiability',
                             ['Good Quality and Good Confiability',
                              'Good Quality and Poor Confiability',
                              'Poor Quality and Good Confiability',
                              'Poor Quality and Poor Confiability'],
                             key='Data_quality', on_change=reset_rob, args=('_maction', '_action', 'gen_robustness'))
                st.selectbox('Learning Curve',
                             ['Good Learning Curve', 'Poor Learning Curve', 'No Learning Curve'],
                             key='Learning_curve', on_change=reset_rob, args=('_maction', '_action', 'gen_robustness'))
                # try:
                #     for i in db_input['Master']['General']:
                #         st.selectbox(f'{i}', db_input['Master']['General'][f'{i}']['options'], key=f'{i}')
                # except:
                #     pass

                st.session_state.well_type_score_s = db['Well_characteristics']['well_type'][
                    f'{st.session_state.well_type}']['score']
                st.session_state.rig_type_score_s = db['Well_characteristics']['Rig_type'][
                    f'{st.session_state.rig_type}']['score']
                st.session_state.rig_status_score_s = db['Well_characteristics']['Rig_status'][
                    f'{st.session_state.rig_status}']['score']
                st.session_state.Correlation_wellss_score_s = db['Well_characteristics']['Correlation_wells'][
                    f'{st.session_state.Correlation_wells}']['score']
                st.session_state.data_score_s = db['Well_characteristics']['Data_quality'][
                    f'{st.session_state.Data_quality}']['score']
                st.session_state.l_curve_score_s = db['Well_characteristics']['Learning_curve'][
                    f'{st.session_state.Learning_curve}']['score']

                if well_type == 'Relief Well':
                    if st.session_state.fp > 69000:
                        st.session_state.open_flow_score_s = 10
                    else:
                        st.session_state.open_flow_score_s = int(ceil(st.session_state.fp * 0.000138 - 0.5538461))
                if rig_type != 'Onshore':
                    if st.session_state.wd > 1495:
                        st.session_state.water_score_s = 10
                    else:
                        st.session_state.water_score_s = round(
                            (-3 * 10 ** -6) * st.session_state.wd ** 2 + 0.0107 * st.session_state.wd + 0.6741)

                sum_general_complexity = []
                for i in st.session_state:
                    if i.endswith('_s'):  # and st.session_state[f'{i}'] != 0:
                        sum_general_complexity.append(st.session_state[f'{i}'])

                st.session_state.general_complexity = mean(sum_general_complexity) / 2

        # Coluna do índice de complexidade
        with col3:
            container_ic = st.container(border=True)
            fig = ic_graph('general_complexity', 'gen_robustness', 'Complexity')
            img_bytes_c = io.BytesIO()
            fig.write_image(img_bytes_c, format='png', scale=2)
            img_bytes_c.seek(0)
            with container_ic:
                cp_well = format(st.session_state.general_complexity, '.2f')
                st.plotly_chart(fig, use_container_width=False, config={'editable': False, 'displayModeBar': False})
                st.text_input('Well Characteristics Complexity', value=cp_well, disabled=True, key='gen_cp')

        # Coluna da matriz de criticidade
        with col4:
            container_matrix = st.container(border=True)
            fig2 = crit_matrix()
            with container_matrix:
                st.plotly_chart(fig2, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False, "scrollZoom": False})
            img_bytes = io.BytesIO()
            fig2.write_image(img_bytes, format='png', scale=3, width=400, height=400)
            img_bytes.seek(0)

    # Aba Geology
    with tabs2[1]:
        geo0, geo1, geo2, geo3, geo4 = st.columns((0.1, 1.2, 0.65, 0.7, 0.1))

        # Coluna de informações da geologia
        with geo1:
            container_geo1 = st.container(border=True)
            with container_geo1:
                st.write('Geology')
                st.selectbox('Shallow Hazard Risk', ['None', 'Shallow Water Flow', 'Hydrate', 'Shallow Gas'],
                             key='shallow_hazard', on_change=reset_rob,
                             args=('_geomaction', 'geosaction', 'geo_robustness'))
                st.number_input('H2S Content', help='Value in "ppm"', step=1.0, format='%f', min_value=0.0,
                                max_value=43.0, key='h2s_content', on_change=reset_rob,
                                args=('_geomaction', 'geosaction', 'geo_robustness'))
                st.number_input('CO2 Content', help='Value in "%"', step=10.0, format='%f', min_value=0.0,
                                max_value=100.0, key='co2_content', on_change=reset_rob,
                                args=('_geomaction', 'geosaction', 'geo_robustness'))
                container_head = st.container(border=True)
                with container_head:
                    st.write('Maximum Wellhead Pressure')
                    col_head1, col_head2 = st.columns(2)
                    with col_head1:
                        st.number_input('Maximum Pore Pressure Gradient', help='Value in "ppg"', step=1.0, format='%f',
                                        key='pore_pressure', on_change=reset_rob,
                                        args=('_geomaction', 'geosaction', 'geo_robustness'))
                        st.number_input('Pore Pressure Gradient at Well Bottom', help='Value in "ppg"',
                                        step=1.0, format='%f', key='pressure_depht', on_change=reset_rob,
                                        args=('_geomaction', 'geosaction', 'geo_robustness'))
                    with col_head2:
                        st.number_input('Depht (TVD)', help='Value in "meters"', step=500.0, format='%f',
                                        key='depht_pore', on_change=reset_rob,
                                        args=('_geomaction', 'geosaction', 'geo_robustness'))
                        st.number_input('Well Bottom Depht (TVD)', help='Value in "meters"', step=500.0, format='%f',
                                        key='bottom_tvd', on_change=reset_rob,
                                        args=('_geomaction', 'geosaction', 'geo_robustness'))

                    gas_hydrostatic_max_pore = 0.1704 * 3.5 * st.session_state.depht_pore
                    gas_hydrostatic_bottom = 0.1704 * 3.5 * st.session_state.bottom_tvd
                    max_pore_pressure = 0.1704 * st.session_state.pore_pressure * st.session_state.depht_pore - gas_hydrostatic_max_pore
                    bottom_pore_pressure = 0.1704 * st.session_state.pressure_depht * st.session_state.bottom_tvd - gas_hydrostatic_bottom

                    if max_pore_pressure > bottom_pore_pressure:
                        max_well_head = max_pore_pressure
                    else:
                        max_well_head = bottom_pore_pressure

                    st.session_state.max_wellhead = max_well_head

                st.number_input('Minimum pressure gradient of the operational window', help='Value in "ppg"', step=0.5,
                                format='%f', key='op_window', on_change=reset_rob,
                                args=('_geomaction', 'geosaction', 'geo_robustness'))

                c1, c2 = st.columns((1, 0.4))
                with c1:
                    st.number_input('Maximum Bottom hole Temperature', help='Value in "°C"', step=5.0, format='%f',
                                    min_value=0.0, key='temp_b', on_change=reset_rob,
                                    args=('_geomaction', 'geosaction', 'geo_robustness'))
                with c2:
                    st.selectbox('Unit:', options=['C', 'F', 'K'], key='temp_unit')
                    st.session_state.max_bottom_hole = units[f'{st.session_state.temp_unit}'](st.session_state.temp_b)

                st.selectbox('Tectonic Effect', ['No', 'Yes'], key='tec_effect')
                st.selectbox('Formation subsidence', ['No', 'Yes'], key='form_sub')
                st.selectbox('Salt Formation', ['None', 'Immovable Salt', 'Movable Salt', 'Allochthonous',
                                                'Autochthonous'],
                             key='salt_formation', on_change=reset_rob,
                             args=('_geomaction', 'geosaction', 'geo_robustness'))

                container_p = st.container(border=True)
                container_p.write('Formations Pressure To Be Drilled')
                container_p.checkbox('Normal Pressure (8,5 to 9 ppg)', key='normal_pressure',
                                     on_change=pressure_drilled, args=('normal_pressure',
                                                                       'Normal Pressure (8,5 to 9 ppg)'))
                container_p.checkbox('Abnormal Low Pressure (6 to 8,5 ppg)', key='ab_pressure',
                                     on_change=pressure_drilled, args=('ab_pressure',
                                                                       'Abnormal Low Pressure (6 to 8,5 ppg)'))

                container_p.checkbox('Depletion (< 6ppg)', key='dp_pressure',
                                     on_change=pressure_drilled, args=('dp_pressure',
                                                                       'Depletion (< 6ppg)'))
                container_p.checkbox('Over Pressure (9,1 to 90% Overburden)', key='ov_pressure',
                                     on_change=pressure_drilled, args=('ov_pressure',
                                                                       'Over Pressure (9,1 to 90% Overburden)'))
                container_p.checkbox('High Overpressure (above 90% Overburden)', key='ho_pressure',
                                     on_change=pressure_drilled, args=('ho_pressure',
                                                                       'High Overpressure (above 90% Overburden)'))

                container = st.container(border=True)
                container.write('Formations To Be Drilled')
                regular = container.checkbox('Regular', key='reg_form')
                weak = container.checkbox('Weak', key='weak_form', on_change=formation_drilled,
                                          args=('weak_form', 'Weak'))
                fractured = container.checkbox('Fractured', key='fractured_form', on_change=formation_drilled,
                                               args=('fractured_form', 'Fractured'))
                reactive = container.checkbox('Reactive', key='reactive_form', on_change=formation_drilled,
                                              args=('reactive_form', 'Reactive'))
                abrasive = container.checkbox('Abrasive', key='abrasive_form', on_change=formation_drilled,
                                              args=('abrasive_form', 'Abrasive'), help='Abrasive formation')
                hard = container.checkbox('Hard', key='hard_form', on_change=formation_drilled,
                                          args=('hard_form', 'Hard'))

                if 'formation_geoscore' not in st.session_state:
                    st.session_state.formation_geoscore = 0

                selected_formations = {
                    'Formation': ['Regular', 'Weak', 'Fractured', 'Reactive', 'Abrasive', 'Hard'],
                    'Selected': [regular, weak, fractured, reactive, abrasive, hard]
                }
                df = pd.DataFrame(selected_formations)

                # Selecionando apenas as formações que foram selecionadas
                selected_df = df.loc[df['Selected'], 'Formation']

                # Juntando os nomes das formações em uma única string separada por vírgula
                selected_formations_str = ', '.join(selected_df)

                st.selectbox('Stress State Knowledge', ['Magnitude and Orientation', 'Magnitude', 'None'],
                             key='stress_state', on_change=reset_rob,
                             args=('_geomaction', 'geosaction', 'geo_robustness'))

                if st.session_state.op_area == 'Oil & Gas':
                    fluid_options = ['Select', 'Oil', 'Condensate', 'Gas']
                elif st.session_state.op_area == 'Dissolution Mining':
                    fluid_options = ['Brine']
                else:
                    fluid_options = ['Injection Well']

                st.selectbox('Expected Formation Fluid', fluid_options, key='expected_fluid',
                             on_change=reset_rob, args=('_geomaction', 'geosaction', 'geo_robustness'))

                st.session_state.shallow_geoscore = db['Geology']['Shallow Hazard Risk'][
                    f'{st.session_state.shallow_hazard}']['score']

                if st.session_state.h2s_content >= 43:
                    st.session_state.h2s_geoscore = 10
                else:
                    st.session_state.h2s_geoscore = round(-0.0037 * st.session_state.h2s_content ** 2 +
                                                          0.391 * st.session_state.h2s_content + 0.0112)

                if st.session_state.co2_content >= 43:
                    st.session_state.co2_geoscore = 10
                else:
                    st.session_state.co2_geoscore = round(-0.0035 * st.session_state.co2_content ** 2 +
                                                          0.3777 * st.session_state.co2_content + 0.1589)

                if st.session_state.max_wellhead <= 8250:
                    st.session_state.wellhead_geoscore = 0
                elif st.session_state.max_wellhead >= 12750:
                    st.session_state.wellhead_geoscore = 10
                else:
                    st.session_state.wellhead_geoscore = round(0.002 * st.session_state.max_wellhead - 15.503)

                if 0 < st.session_state.op_window <= 0.45:
                    st.session_state.op_window_geoscore = 10
                elif st.session_state.op_window >= 1.46 or st.session_state.op_window == 0:
                    st.session_state.op_window_geoscore = 0
                else:
                    st.session_state.op_window_geoscore = round(-2.1915 * st.session_state.op_window ** 2 -
                                                                3.2781 * st.session_state.op_window + 11.476)

                if st.session_state.max_bottom_hole <= 64:
                    st.session_state.hole_temp_geoscore = 0
                elif st.session_state.max_bottom_hole >= 138:
                    st.session_state.hole_temp_geoscore = 10
                else:
                    st.session_state.hole_temp_geoscore = round(-0.0009 * st.session_state.max_bottom_hole ** 2 +
                                                                0.3033 * st.session_state.max_bottom_hole - 14.311)
                if st.session_state.tec_effect == 'Yes':
                    st.session_state.tec_geoscore = 10
                else:
                    st.session_state.tec_geoscore = 0

                if st.session_state.form_sub == 'Yes':
                    st.session_state.sub_geoscore = 10
                else:
                    st.session_state.sub_geoscore = 0

                st.session_state.salt_geoscore = db['Geology']['Salt Formation'][f'{st.session_state.salt_formation}'][
                    'score']

                if st.session_state.stress_state != 'Magnitude and Orientation':
                    st.session_state.stress_geoscore = db['Geology']['Stress State'][
                        f'{st.session_state.stress_state}']['score']
                else:
                    st.session_state.stress_geoscore = 0

                st.session_state.form_fluid_geoscore = db['Geology']['Formation Fluid'][
                    f'{st.session_state.expected_fluid}']['score']

                sum_geo_complexity = []
                for i in st.session_state:
                    if i.endswith('_geoscore'):
                        sum_geo_complexity.append(st.session_state[f'{i}'])

                st.session_state.geo_complexity = mean(sum_geo_complexity) / 2

        # Coluna do índice de complexidade da geologia
        with geo2:
            container_geo_ic = st.container(border=True)
            fig_ic_geo = ic_graph('geo_complexity', 'geo_robustness', 'Complexity')
            with container_geo_ic:
                cp_geo = float(st.session_state.geo_complexity)
                st.plotly_chart(fig_ic_geo, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False})
                st.text_input('Geology Complexity', value=f'{cp_geo:.2f}', disabled=True, key='geo_cp')

        # Coluna da matriz de criticidade
        with geo3:
            container_geo3 = st.container(border=True)
            fig2 = crit_matrix()
            with container_geo3:
                st.plotly_chart(fig2, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False, "scrollZoom": False})

    # # Aba reservoir
    # with tabs2[2]:
    #     res0, res1, res2, res3, res4 = st.columns((0.1, 1, 0.6, 0.7, 0.1))
    #     with res1:
    #         container_res1 = st.container(border=True)
    #         with container_res1:
    #
    #             st.write('Reservoir')
    #             st.number_input('Reservoir Top (TVD)', help='Value in "ft"', step=100.0, format='%f', min_value=0.0,
    #                             key='top_reservoir')
    #             st.number_input('Reservoir Base (TVD)', help='Value in "ft"', step=100.0, format='%f', min_value=0.0,
    #                             key='base_reservoir')
    #             st.selectbox('Reservoir Litology', ['Carbonate', 'Sendstone', 'Shale'],
    #                          key='litology_reservoir')
    #             st.number_input('Pressure Gradient', help='Value in "ppg"', step=0.1, format='%f', min_value=0.0,
    #                             key='pressure_gradient')
    #             st.number_input('Reservoir Pressure', help='Value in "psi"', step=10.0, format='%f', min_value=0.0,
    #                             key='reservoir_pressure')
    #             st.number_input('Vertical Permeability (Kv)', help='Value in "mD"', step=1.0, format='%f',
    #                             min_value=0.0,
    #                             key='vertical_permeability')
    #             st.number_input('Horizontal Permeability (Kv)', help='Value in "mD"', step=1.0, format='%f',
    #                             min_value=0.0,
    #                             key='horizontal_permeability')
    #             st.number_input('Gas-Oil Contact (TVD)', help='Value in "ft"', step=100.0, format='%f', min_value=0.0,
    #                             key='goc')
    #             st.number_input('Oil-Water Contact (TVD)', help='Value in "ft"', step=100.0, format='%f', min_value=0.0,
    #                             key='owc')
    #             st.number_input('Young Modulus', help='Value in "psi"', step=100, min_value=0,
    #                             key='young_modulus')
    #             st.number_input('Biot Coeficient', step=100, min_value=0, key='biot')
    #             st.number_input('Poisson Coeficient', step=100, min_value=0, key='poisson')
    #             st.number_input('Compressive Strength', help='Value in "psi"', step=100, min_value=0,
    #                             key='compressive_strength')
    #             st.number_input('Lithostatic Gradient', help='Value in "psi/ft"', step=100, min_value=0,
    #                             key='lithostatic_gradient')
    #             st.number_input('Vertical Stress', help='Value in "psi"', step=100, min_value=0,
    #                             key='vertical_stress')
    #             st.number_input('Minimum Horizontal Stress', help='Value in "psi"', step=100, min_value=0,
    #                             key='mim_horizontal_stress')
    #             st.number_input('Vertical Stress / Hrizontal Stress', min_value=0, key='vertical_horizontal_stress')
    #
    #             container_res2 = st.container(border=True)
    #             with container_res2:
    #                 st.write('Fracture Pressure')
    #                 st.number_input('Penetrating Fluid', help='Value in "psi"', step=100, min_value=0,
    #                                 key='penetrating_fluid')
    #                 st.number_input('Non Penetrating Fluid', help='Value in "psi"', step=100, min_value=0,
    #                                 key='non_penetrating_fluid')
    #     # Coluna do índice de complexidade da geologia
    #     with res2:
    #         container_res_ic = st.container(border=True)
    #         fig_ic_res = ic_graph('geo_complexity', 'geo_robustness', 'Complexity')
    #         with container_res_ic:
    #             cp_res = float(st.session_state.geo_complexity)
    #             st.plotly_chart(fig_ic_res, use_container_width=False,
    #                             config={'editable': False, 'displayModeBar': False})
    #             st.text_input('Reservoir Complexity', value=f'{cp_res:.2f}', disabled=True)
    #
    #     # Coluna da matriz de criticidade
    #     with res3:
    #         container_res3 = st.container(border=True)
    #         fig2_res = crit_matrix()
    #         with container_res3:
    #             st.plotly_chart(fig2_res, use_container_width=False,
    #                             config={'editable': False, 'displayModeBar': False, "scrollZoom": False})

    # Aba drilling
    with tabs2[2]:
        drill0, drill1, drill2, drill3, drill4 = st.columns((0.1, 1, 0.6, 0.7, 0.1))

        with drill1:
            container_drill0 = st.container(border=True)
            with container_drill0:
                st.write('Driling')
                container_drill1 = st.container(border=True)
                with container_drill1:
                    st.write('Well Sections / Geometry')
                    c1, c2 = st.columns((1, 0.4))
                    with c1:
                        st.number_input('Total Depth (MD)', help='Value in "meters"', step=200.0, format='%f',
                                        min_value=0.0, on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'), key='td')
                        st.number_input('Total Vertical Depth (TVD)', help='Value in "meters"', step=200.0, format='%f',
                                        min_value=0.0, key='tvd_m', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                    with c2:
                        st.selectbox('Unit:', options=['m', 'ft'], key='total_unit')
                        st.session_state.total_depth = units[f'{st.session_state.total_unit}'](st.session_state.td)

                        st.selectbox('Unit:', options=['m', 'ft'], key='tvd_unit')
                        st.session_state.total_tvd = units[f'{st.session_state.tvd_unit}'](st.session_state.tvd_m)

                    st.selectbox('Well Alignment', ['Maximum Stress', 'Minimum Stress', 'Intermediate', 'Unknown'],
                                 key='well_alignment', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                    st.selectbox('Maximum Number of Phases',
                                 ['3 phases', '4 phases', '5 phases', '6 phases', '7 or Above'], key='number_phases',
                                 on_change=reset_rob, args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                    st.selectbox('Hole Enlargements',
                                 ['None', 'One', 'Two', '3 or more', 'Rock or abrasive formation'],
                                 key='hole_enlargements', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                    st.selectbox('Slim Hole (<6,5 in)', ['Slim hole not planned', 'Slim hole as contingency',
                                                         'Slim hole planned'],
                                 key='slim_hole', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'),)
                    st.number_input('Minimum Hole Diameter', help='Value in "inch"', step=1.0, format='%f',
                                    min_value=0.0, key='min_hole_diameter', on_change=reset_rob,
                                    args=('_drillmaction', 'drillsaction', 'drill_robustness'))

                # with drill1:
                container_drill2 = st.container(border=True)
                with container_drill2:
                    st.write('Trajectory')
                    st.selectbox('Vertical Well', ['Yes', 'No'], key='vertical_well', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                    if st.session_state.vertical_well == 'No':
                        st.number_input('Slant Sec Maximum Inclination', help='Value in degrees', step=1.0, format='%f',
                                        min_value=0.0,
                                        max_value=90.0, key='max_inclination', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                        st.number_input('Maximum Lateral Displacement', help='Value in "ft"', step=100.0, format='%f',
                                        min_value=0.0, key='max_lateral_displacement', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                        st.selectbox('Complex Trajectory Planned', ['None', 'J Curve', 'S Curve'],
                                     key='complex_trajectory_planned', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                        st.number_input('Maximum Dogleg', step=1.0, format='%f', min_value=0.0, key='max_dogleg',
                                        on_change=reset_rob, args=('_drillmaction', 'drillsaction', 'drill_robustness'))

                        if 4 <= st.session_state.max_inclination <= 54:
                            st.session_state.slant = db['Drilling']['Slant Maximum Inclination'][
                                f'min']['score']
                        elif 55 <= st.session_state.max_inclination <= 89:
                            st.session_state.slant = db['Drilling']['Slant Maximum Inclination'][
                                f'med']['score']
                        elif st.session_state.max_inclination > 89:
                            st.session_state.slant = db['Drilling']['Slant Maximum Inclination'][
                                f'max']['score']

                        if st.session_state.max_dogleg <= 2.24:
                            st.session_state.dogleg = db['Drilling']['Maximum Dogleg'][
                                f'min']['score']
                        elif 2.25 <= st.session_state.max_dogleg <= 3.37:
                            st.session_state.dogleg = db['Drilling']['Maximum Dogleg'][
                                f'med']['score']
                        elif st.session_state.max_dogleg > 3.37:
                            st.session_state.dogleg = db['Drilling']['Maximum Dogleg'][
                                f'max']['score']

                        st.session_state.trajectory = db['Drilling']['Trajectory Planned'][
                            f'{st.session_state.complex_trajectory_planned}']['score']

                        try:
                            st.session_state.trajectory_drillscore = mean([st.session_state.slant,
                                                                           st.session_state.dogleg,
                                                                           st.session_state.trajectory])

                        except:
                            st.session_state.casing_drillscore = 0

                    else:
                        # st.write('Vertical Well')
                        st.session_state.max_inclination = 0
                        st.session_state.max_lateral_displacement = 0
                        st.session_state.complex_trajectory_planned = 'None'
                        st.session_state.max_dogleg = 0

                    st.selectbox('Distance from the wellhead to nearby wells',
                                 ['Above 20 meters', '10 - 20 meters', '5 - 10 meters', 'Below 5 meters'],
                                 key='well_distance', on_change=reset_rob,
                                 args=('_drillmaction', 'drillsaction', 'drill_robustness'))

                # with drill1:
                container_drill3 = st.container(border=True)
                with container_drill3:
                    st.write('Aquifer')
                    st.selectbox('Type of Aquifer (Environmental Issues)', ['None', 'Shallow salt water',
                                                                            'Deep salt water', 'Deep fresh water',
                                                                            'Shallow fresh water'], key='type_aquifer',
                                 on_change=reset_rob,
                                 args=('_drillmaction', 'drillsaction', 'drill_robustness')
                                 )

                # with drill1:
                container_drill4 = st.container(border=True)
                with container_drill4:
                    st.write('Cement')
                    c3, c4 = st.columns((1, 0.4))
                    with c3:
                        st.number_input('Longest Cement Interval', help='Value in "meters"', step=200, min_value=0,
                                        key='cement', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                    with c4:
                        st.selectbox('Unit:', options=['m', 'ft'], key='cement_unit')
                        st.session_state.cement_interval = units[f'{st.session_state.cement_unit}'](
                            st.session_state.cement)
                    st.selectbox('Casing Type', ['Conventional Casing', 'Liner', 'Tieback', 'Expandable',
                                                 'Casing Drilling'], key='casing_type', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                    st.selectbox('Non-shear Casing', ['Select', 'Yes, no reservoir exposed',
                                                      'Yes, reservoir exposed'], key='non_shear_casing',
                                 on_change=reset_rob,
                                 args=('_drillmaction', 'drillsaction', 'drill_robustness'),
                                 )

                # with drill1:
                container_drill5 = st.container(border=True)
                with container_drill5:
                    st.write('Fluid')
                    st.number_input('Maximum Driling fluid density', help='Value in "ppg"', step=1.0, format='%f',
                                    min_value=0.0, key='fluid_density', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                    st.selectbox('Lost Circulation', ['No loss', 'Partial loss (below 25 bbl/h)',
                                                      'Severe loss (above 25 bbl/h)', 'Total loss'],
                                 key='lost_circulation', on_change=reset_rob,
                                        args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                    st.selectbox('Zones with reduced pore pressure', ['No', 'Yes'], key='reducing_zone',
                                 on_change=reset_rob, args=('_drillmaction', 'drillsaction', 'drill_robustness'),)
                    if rig_type != 'Onshore':
                        st.selectbox('Riser Safety Margin', ['Considering', 'None'], key='riser_safety_margin',
                                     on_change=reset_rob, args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                        st.session_state.riser_drillscore = db['Drilling']['Riser Safety Margin'][
                            f'{st.session_state.riser_safety_margin}']['score']
                    st.selectbox('Driling Fluid', ['Select', 'Synthetic fluid', 'Water based (high performance)',
                                                   'Water based (inhibited)', 'Water based', 'Foamed', 'Aerated'],
                                 key='drilling_fluid', on_change=reset_rob,
                                 args=('_drillmaction', 'drillsaction', 'drill_robustness'))
                if st.session_state.total_depth <= 3352:
                    st.session_state.depth_drillscore = db['Drilling']['Total Depth'][
                        f'min']['score']
                elif 3352 < st.session_state.total_depth <= 5333:
                    st.session_state.depth_drillscore = db['Drilling']['Total Depth'][
                        f'med']['score']
                elif st.session_state.total_depth > 5333:
                    st.session_state.depth_drillscore = db['Drilling']['Total Depth'][
                        f'max']['score']

                st.session_state.align_drillscore = db['Drilling']['Well Alignment'][
                    f'{st.session_state.well_alignment}']['score']

                st.session_state.phases_drillscore = db['Drilling']['Phase Number'][
                    f'{st.session_state.number_phases}']['score']

                st.session_state.hole_drillscore = db['Drilling']['Hole Enlargements'][
                    f'{st.session_state.hole_enlargements}']['score']

                st.session_state.slim_drillscore = db['Drilling']['Slim Hole'][
                    f'{st.session_state.slim_hole}']['score']

                st.session_state.distance_well_drillscore = db['Drilling']['Distance to Well'][
                    f'{st.session_state.well_distance}']['score']

                st.session_state.aquifer_drillscore = db['Drilling']['Type of Aquifer'][
                    f'{st.session_state.type_aquifer}']['score']

                if st.session_state.cement_interval <= 784:
                    st.session_state.cement_interval_drillscore = 0
                else:
                    st.session_state.cement_interval_drillscore = round(
                        min(0.0229 * st.session_state.cement_interval - 17.221, 10))

                st.session_state.casing_drillscore = db['Drilling']['Casing Type'][
                    f'{st.session_state.casing_type}']['score']

                st.session_state.shear_drillscore = db['Drilling']['Non-shear Casing'][
                    f'{st.session_state.non_shear_casing}']['score']

                if st.session_state.fluid_density <= 10.35:
                    st.session_state.ppg_drillscore = db['Drilling']['Maximum fluid density'][
                        f'min']['score']

                elif 10.36 <= st.session_state.fluid_density <= 12.47:
                    st.session_state.ppg_drillscore = db['Drilling']['Maximum fluid density'][
                        f'med']['score']

                elif 12.48 <= st.session_state.fluid_density <= 13.88:
                    st.session_state.ppg_drillscore = db['Drilling']['Maximum fluid density'][
                        f'med2']['score']

                elif st.session_state.fluid_density > 13.88:
                    st.session_state.ppg_drillscore = db['Drilling']['Maximum fluid density'][
                        f'max']['score']

                st.session_state.fluid_drillscore = db['Drilling']['Drilling Fluid'][
                    f'{st.session_state.drilling_fluid}']['score']

                if st.session_state.reducing_zone == 'Yes':
                    st.session_state.reducing_drillscore = 10
                else:
                    st.session_state.reducing_drillscore = 0

                st.session_state.lost_drillscore = db['Drilling']['Lost Circulation'][
                    f'{st.session_state.lost_circulation}']['score']

                sum_drill_complexity = []
                for i in st.session_state:
                    if i.endswith('_drillscore'):
                        sum_drill_complexity.append(st.session_state[f'{i}'])
                st.session_state.drill_complexity = mean(sum_drill_complexity) / 2

        with drill2:
            container_drill_ic = st.container(border=True)
            fig_ic_drill = ic_graph('drill_complexity', 'drill_robustness', 'Complexity')
            with container_drill_ic:
                cp_drill = float(st.session_state.drill_complexity)
                st.plotly_chart(fig_ic_drill, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False})
                st.text_input('Drilling Complexity', value=f'{cp_drill:.2f}', disabled=True, key='drill_cp')

        # Coluna da matriz de criticidade
        with drill3:
            container_drill3 = st.container(border=True)
            fig2_drill = crit_matrix()
            with container_drill3:
                st.plotly_chart(fig2_drill, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False, "scrollZoom": False})

    # Aba completion
    with tabs2[3]:
        comp0, comp1, comp2, comp3, comp4 = st.columns((0.1, 1, 0.6, 0.7, 0.1))

        with comp1:
            container_comp0 = st.container(border=True)
            with container_comp0:
                st.write('Completion')
                container_comp1 = st.container(border=True)

                with container_comp1:
                    st.write('Trajectory Within the Reservoir')
                    st.number_input('Inclination', help='Value in degrees', step=1, min_value=0, key='res_inclination',
                                    on_change=reset_rob,
                                    args=('_compmaction', 'compsaction', 'comp_robustness'),
                                    )
                    c1, c2 = st.columns((1, 0.4))
                    with c1:
                        st.number_input('Length', help='Value in "meters"', step=150, min_value=0, key='res',
                                        on_change=reset_rob,
                                        args=('_compmaction', 'compsaction', 'comp_robustness')
                                        )

                    with c2:
                        st.selectbox('Unit:', options=['m', 'ft'], key='res_unit')
                        st.session_state.res_length = units[f'{st.session_state.res_unit}'](st.session_state.res)

                container_comp2 = st.container(border=True)

                with container_comp2:
                    st.write('Reservoir Well Interface')
                    st.selectbox('Production Casing', ['Cased-cemented-perforated', 'Non -cemented', 'Barefoot'],
                                 key='production_casing',on_change=reset_rob,
                                    args=('_compmaction', 'compsaction', 'comp_robustness'))
                    st.selectbox('Multizone Completion', ['Just one zone', 'Dual zone completion', 'Three zones',
                                                          'Above three zones'],
                                 key='multizone_completion', on_change=reset_rob,
                                    args=('_compmaction', 'compsaction', 'comp_robustness'))
                    st.selectbox('Reservoir with Pressure Contrast', ['None', 'Yes (Contrast below 10%)',
                                                                      'Yes (Contrast above 10%)'],
                                 key='pressure_contrast', on_change=reset_rob,
                                    args=('_compmaction', 'compsaction', 'comp_robustness'))

                container_comp3 = st.container(border=True)
                with container_comp3:
                    st.write('Well Simulation')
                    st.radio('Simulation', ['Hydraulic Fracturing', 'Matrix Stimulation'], key='frat_type',
                             on_change=reset_rob, args=('_compmaction', 'compsaction', 'comp_robustness'))
                    if st.session_state.frat_type == 'Hydraulic Fracturing':
                        frac_options = ['No fracturing', 'Single fracture', 'Multi-stage fracturing']

                    else:
                        frac_options = ['No stimulation', 'Single zone', 'Selective multi-zone', 'Multi-zone bull-head']

                    st.selectbox(st.session_state.frat_type, frac_options, key='fracturing', on_change=reset_rob,
                                    args=('_compmaction', 'compsaction', 'comp_robustness'))
                    st.session_state.frat_compscore = db['Completion'][f'{st.session_state.frat_type}'][
                        f'{st.session_state.fracturing}']['score']
                container_comp4 = st.container(border=True)
                with container_comp4:
                    st.write('Sand Control Completion')
                    st.radio('Sand Control Completion Type', ['Stand Alone', 'Gravel Pack', 'Frack Pack'],
                             key='sand_control_type', on_change=reset_rob,
                                    args=('_compmaction', 'compsaction', 'comp_robustness'))
                    if st.session_state.sand_control_type == 'Stand Alone':
                        sand_options = ['None', 'Stand alone (<2500 ft)', 'Stand alone (2500 to 4000 ft)',
                                        'Stand alone (above 4000 ft)']

                    elif st.session_state.sand_control_type == 'Gravel Pack':
                        sand_options = ['None', 'Gravel Pack (<2500 ft)', 'Gravel Pack (2500 to 4000 ft)',
                                        'Gravel Pack (above 4000 ft)']
                    else:
                        sand_options = ['None', 'Frack Pack (<2500 ft)', 'Frack Pack (2500 to 4000 ft)',
                                        'Frack Pack (above 4000 ft)']

                    st.selectbox(st.session_state.sand_control_type, sand_options, key='sand_pack', on_change=reset_rob,
                                    args=('_compmaction', 'compsaction', 'comp_robustness'))
                    st.session_state.sand_compscore = db['Completion'][f'{st.session_state.sand_control_type}'][
                        f'{st.session_state.sand_pack}']['score']

                container_comp5 = st.container(border=True)
                with container_comp5:
                    st.write('Artificial Lift')
                    st.selectbox('Type of Artificial Lift',
                                 ['Flowing well', 'Sucker-rod Pumping', 'Gas lift or intermittent gas lift',
                                  'ESP'], key='artificial_lift', on_change=reset_rob,
                                    args=('_compmaction', 'compsaction', 'comp_robustness'))

                container_comp6 = st.container(border=True)
                with container_comp6:
                    st.write('Production Data')
                    st.selectbox('Production Flow Rate', ['Gas and/or condensate', 'q < 500 bpd', '500 =< q < 1000 bpd',
                                                          '1000 =< q < 10000 bpd', '10000 =< q < 40000 bpd',
                                                          'q >= 40000 bpd'], key='production_data',
                                 on_change=reset_rob,
                                 args=('_compmaction', 'compsaction', 'comp_robustness')
                                 )

            # Complexity inclination score
            if st.session_state.res_inclination <= 23:
                st.session_state.base_inc_compscore = db['Completion']['Inclination'][
                    f'min']['score']
            elif st.session_state.res_inclination <= 78:
                st.session_state.base_inc_compscore = db['Completion']['Inclination'][
                    f'med']['score']
            else:
                st.session_state.base_inc_compscore = db['Completion']['Inclination'][
                    f'max']['score']

            # Complexity length score
            if st.session_state.res_length <= 357:
                st.session_state.len_compscore = db['Completion']['Length'][
                    f'min']['score']
            elif st.session_state.res_length <= 1303:
                st.session_state.len_compscore = db['Completion']['Length'][
                    f'med']['score']
            else:
                st.session_state.len_compscore = db['Completion']['Length'][
                    f'max']['score']

            st.session_state.prod_compscore = db['Completion']['Production Casing'][
                f'{st.session_state.production_casing}']['score']

            st.session_state.zone_compscore = db['Completion']['Multizone completion'][
                f'{st.session_state.multizone_completion}']['score']

            st.session_state.contrast_compscore = db['Completion']['Res. with pressure contrast'][
                f'{st.session_state.pressure_contrast}']['score']

            st.session_state.lift_compscore = db['Completion']['Type of Artificial Lift'][
                f'{st.session_state.artificial_lift}']['score']

            st.session_state.data_prod_compscore = db['Completion']['Production flow rate'][
                f'{st.session_state.production_data}']['score']

            sum_comp_complexity = []
            for i in st.session_state:
                if i.endswith('_compscore'):
                    sum_comp_complexity.append(st.session_state[f'{i}'])
            st.session_state.comp_complexity = mean(sum_comp_complexity) / 2

        with comp2:
            container_comp_ic = st.container(border=True)
            fig_ic_comp = ic_graph('comp_complexity', 'comp_robustness', 'Complexity')
            with container_comp_ic:
                cp_comp = float(st.session_state.comp_complexity)
                st.plotly_chart(fig_ic_comp, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False})
                st.text_input('Completion Complexity', value=f'{cp_comp:.2f}', disabled=True, key='comp_cp')

        # Coluna da matriz de criticidade
        with comp3:
            container_comp3 = st.container(border=True)
            fig2_comp = crit_matrix()
            with container_comp3:
                st.plotly_chart(fig2_comp, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False, "scrollZoom": False})

    # Aba logistic
    with tabs2[4]:
        col_log1, col_log2, col_log3, col_log4, col_log5 = st.columns((0.1, 1, 0.6, 0.7, 0.1))

        # Selection complexity Column
        with col_log2:
            log_container1 = st.container(border=True)
            with log_container1:
                st.write('Logistic')
                st.selectbox('Operational Support', ['Good support', 'Poor support', 'No support'],
                             key='op_support', on_change=reset_rob,
                             args=('_logmaction', 'logsaction', 'log_robustness'))
                st.selectbox('Fluids and Cuts Disposal', ['Onshore drilling', 'Offshore - water based fluid',
                                                          'Offshore - synthetic fluid'],
                             key='fluid_disposal', on_change=reset_rob,
                             args=('_logmaction', 'logsaction', 'log_robustness'))

                c1, c2 = st.columns((1, 0.4))
                with c1:
                    st.number_input('Distance to Operation Base', help='Value in "meters"', step=200.0, format='%f',
                                    min_value=0.0, key='base', on_change=reset_rob,
                                    args=('_logmaction', 'logsaction', 'log_robustness'))

                    st.number_input('Distance to WareHouse', help='Value in "meters"', step=200.0, format='%f',
                                    min_value=0.0, key='ware', on_change=reset_rob,
                                    args=('_logmaction', 'logaction', 'log_robustness'))

                with c2:
                    st.selectbox('Unit:', options=['m', 'miles'], key='base_unit')
                    st.session_state.distance_base = units[f'{st.session_state.base_unit}'](st.session_state.base)

                    st.selectbox('Unit:', options=['m', 'miles'], key='ware_unit')
                    st.session_state.distance_warehouse = units[f'{st.session_state.ware_unit}'](st.session_state.ware)

                # Complexity logistic support score
                st.session_state.op_support_logscore = db['Logistic']['Operational Support'][
                    f'{st.session_state.op_support}']['score']

                # Complexity fluid disposal score
                st.session_state.fluid_disposal_logscore = db['Logistic']['Fluid Disposal'][
                    f'{st.session_state.fluid_disposal}']['score']

                # Complexity base score
                if st.session_state.distance_base <= 537406:
                    st.session_state.base_distance_logscore = db['Logistic']['Distance to Operational Base'][
                        f'min']['score']
                elif st.session_state.distance_base <= 1551000:
                    st.session_state.base_distance_logscore = db['Logistic']['Distance to Operational Base'][
                        f'med']['score']
                else:
                    st.session_state.base_distance_logscore = db['Logistic']['Distance to Operational Base'][
                        f'max']['score']

                # Complexity warehouse score
                if st.session_state.distance_warehouse <= 176990:
                    st.session_state.ware_distance_logscore = db['Logistic']['Distance to Warehouse'][
                        f'min']['score']
                elif st.session_state.distance_warehouse <= 455000:
                    st.session_state.ware_distance_logscore = db['Logistic']['Distance to Warehouse'][
                        f'med']['score']
                else:
                    st.session_state.ware_distance_logscore = db['Logistic']['Distance to Warehouse'][
                        f'max']['score']

                sum_log_complexity = []
                for i in st.session_state:
                    if i.endswith('_logscore'):
                        sum_log_complexity.append(st.session_state[f'{i}'])

                st.session_state.log_complexity = mean(sum_log_complexity) / 2

        # Complexity Index Column
        with col_log3:
            container_geo2 = st.container(border=True)
            fig_ic_log = ic_graph('log_complexity', 'log_robustness', 'Complexity')
            with container_geo2:
                cp_log = st.session_state.log_complexity
                st.plotly_chart(fig_ic_log, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False})
                st.text_input('Logistic Complexity', value=f'{cp_log:.2f}', disabled=True)

        # Critic Matrix Column
        with col_log4:
            container_geo3 = st.container(border=True)
            fig_log = crit_matrix()
            with container_geo3:
                st.plotly_chart(fig_log, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False, "scrollZoom": False})

    # Aba metocean
    with tabs2[5]:
        col_meto1, col_meto2, col_meto3, col_meto4, col_meto5 = st.columns((0.1, 1, 0.6, 0.7, 0.1))

        with col_meto2:
            meto_container1 = st.container(border=True)
            # Selection complexity Column
            with meto_container1:
                st.write('Metocean')
                st.number_input('Sea Current', help='Value in "knots"', step=10.0, format='%f',
                                min_value=0.0, key='sea_current', on_change=reset_rob,
                                args=('_metomaction', 'metosaction', 'meto_robustness'))
                c1, c2 = st.columns((1, 0.4))
                with c1:
                    st.number_input('Waves Height', help='Value in "meters"', step=10.0, format='%f',
                                    min_value=0.0, key='wave_alt', on_change=reset_rob,
                                    args=('_metomaction', 'metosaction', 'meto_robustness'))

                with c2:
                    st.selectbox('Unit:', options=['m', 'ft'], key='wave_unit')
                    st.session_state.wave_h = units[f'{st.session_state.wave_unit}'](st.session_state.wave_alt)
                st.number_input('Wind Speed', help='Value in "knots"', step=10.0, format='%f',
                                min_value=0.0, key='wind_speed', on_change=reset_rob,
                                args=('_metomaction', 'metosaction', 'meto_robustness'))

                # Sea current score
                if st.session_state.sea_current <= 2.1:
                    st.session_state.sea_metoscore = db['Metocean']['Sea Current'][f'min']['score']
                elif st.session_state.sea_current <= 3.95:
                    st.session_state.sea_metoscore = db['Metocean']['Sea Current'][f'med']['score']
                else:
                    st.session_state.sea_metoscore = db['Metocean']['Sea Current'][f'max']['score']

                # Wave height score
                if st.session_state.wave_h <= 3.05:
                    st.session_state.wave_metoscore = db['Metocean']['Waves Height'][f'min']['score']
                elif st.session_state.wave_h <= 4.88:
                    st.session_state.wave_metoscore = db['Metocean']['Waves Height'][f'med']['score']
                elif st.session_state.wave_h <= 5.79:
                    st.session_state.wave_metoscore = db['Metocean']['Waves Height'][f'med2']['score']
                else:
                    st.session_state.wave_metoscore = db['Metocean']['Waves Height'][f'max']['score']

                # Wind speed score
                if st.session_state.wind_speed <= 20.74:
                    st.session_state.wind_metoscore = db['Metocean']['Wind Speed'][f'min']['score']
                elif st.session_state.wind_speed <= 34.24:
                    st.session_state.wind_metoscore = db['Metocean']['Wind Speed'][f'med']['score']
                else:
                    st.session_state.wind_metoscore = db['Metocean']['Wind Speed'][f'max']['score']

                sum_meto_complexity = []
                for i in st.session_state:
                    if i.endswith('_metoscore'):
                        sum_meto_complexity.append(st.session_state[f'{i}'])

                st.session_state.meto_complexity = mean(sum_meto_complexity) / 2

        # Complexity Index Column
        with col_meto3:
            container_meto2 = st.container(border=True)
            fig_ic_meto = ic_graph('meto_complexity', 'meto_robustness', 'Complexity')
            with container_meto2:
                cp_meto = st.session_state.meto_complexity
                st.plotly_chart(fig_ic_meto, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False})
                st.text_input('Metocean Complexity', value=f'{cp_meto:.2f}', disabled=True)

        # Critic Matrix Column
        with col_meto4:
            container_meto3 = st.container(border=True)
            fig_meto = crit_matrix()
            with container_meto3:
                st.plotly_chart(fig_meto, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False, "scrollZoom": False})

    # Aba Braskem
    with tabs2[6]:
        col_brk1, col_brk2, col_brk3, col_brk4, col_brk5 = st.columns((0.1, 1, 0.6, 0.7, 0.1))

        with col_brk2:
            container1 = st.container(border=True)  # Criando um container com borda
            with container1:
                st.selectbox('Cavity Status', ['Select', 'Pressurized', 'Slightly pressurized', 'Unpressurized'],
                             key='press')

                if st.session_state.press == 'Pressurized':
                    if 'salt_brkscore' in st.session_state:
                        del st.session_state.salt_brkscore
                    st.selectbox('Exist total loss zone near the cavity?', ['No', 'Yes'], key='loss_zone')
                    objective_options = ['Piezometer', 'Plugging']
                    if st.session_state.loss_zone == 'Yes':
                        st.session_state.loss_brkscore = 10
                    else:
                        st.session_state.loss_brkscore = 0

                elif st.session_state.press == 'Slightly pressurized':
                    if 'salt_brkscore' in st.session_state:
                        del st.session_state.salt_brkscore
                    st.selectbox('Exist total loss zone near the cavity?', ['No', 'Yes'], key='loss_zone')
                    objective_options = ['Select', 'Piezometer', 'Plugging', 'Backfilling']
                    if st.session_state.loss_zone == 'Yes':
                        st.session_state.loss_brkscore = 10
                    else:
                        st.session_state.loss_brkscore = 0
                else:
                    if 'salt_brkscore' in st.session_state:
                        del st.session_state.salt_brkscore
                    if 'loss_brkscore' in st.session_state:
                        del st.session_state.loss_brkscore
                    objective_options = ['Select', 'Backfilling', 'Plugging']

                st.selectbox('Well objective', objective_options, key='well_objective')

                if st.session_state.press == 'Unpressurized':
                    st.selectbox('Cavity within the salt zone', ['Inside', 'Outside'], key='cave_salt')
                    st.session_state.salt_brkscore = db['Braskem']['Location'][
                        f'{st.session_state.cave_salt}']['score']

                st.session_state.cavity_brkscore = db['Braskem']['Cavity Status'][
                    f'{st.session_state.press}']['score']
                st.session_state.objective_brkscore = db['Braskem']['Well Objective'][
                    f'{st.session_state.well_objective}']['score']

                sum_brk_complexity = []
                for i in st.session_state:
                    if i.endswith('_brkscore'):
                        sum_brk_complexity.append(st.session_state[f'{i}'])
                st.session_state.brk_complexity = mean(sum_brk_complexity) / 2

        # Complexity Index Column
        with col_brk3:
            container_brk2 = st.container(border=True)
            fig_ic_brk = ic_graph('brk_complexity', 'brk_robustness', 'Complexity')
            with container_brk2:
                cp_brk = st.session_state.brk_complexity
                st.plotly_chart(fig_ic_brk, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False})
                st.text_input('Braskem Project Complexity', value=f'{cp_brk:.2f}', disabled=True)

        # Critic Matrix Column
        with col_brk4:
            container_brk3 = st.container(border=True)
            fig_brk = crit_matrix()
            with container_brk3:
                st.plotly_chart(fig_brk, use_container_width=False,
                                config={'editable': False, 'displayModeBar': False, "scrollZoom": False})

    # Aba actions
    with tabs[1]:
        tabs2 = st.tabs(['Mitigating', 'Review', 'Declined', 'Suggested'])

        # Aba mitigating
        with tabs2[0]:
            tabs3 = st.tabs(['General', 'Geology and Reservoir', 'Drilling',
                             'Completions', 'Logistics', 'Metocean', 'Braskem'])
            # General actions
            with tabs3[0]:
                st.write(':red[Mandatory Actions*]')
                action_c1, action_c2, action_c3 = st.columns((1.3, 0.6, 0.4))

                # Exibindo as ações mitigadoras para cada problema selecionado
                with action_c1.expander(f'Mitigations for {st.session_state.well_type}', expanded=True):
                    for i in db['Well_characteristics']['well_type'][f'{st.session_state.well_type}']['actions_m']:
                        key = f'well_type {i}_maction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'gen_robustness', 'general_complexity', '_maction'))
                    for i in db['Well_characteristics']['well_type'][f'{st.session_state.well_type}']['actions_s']:
                        key = f'well_type {i}_action'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'robustness', 'gen_general_complexity', '_maction'))

                if st.session_state.wd != 0:
                    with action_c1.expander(f'Mitigations for Water depth {st.session_state.wd} ft', expanded=True):
                        wd_m_actions = []
                        wd_s_actions = []
                        for keys, subdict in db['Well_characteristics']['water_depth'].items():
                            if subdict['score'] == int(st.session_state.water_score_s):
                                wd_m_actions = subdict['actions_m']
                                wd_s_actions = subdict['actions_s']
                        for i in wd_m_actions:
                            key = f'water_depth {i}_maction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'gen_robustness', 'general_complexity', '_maction'))

                        for i in wd_s_actions:
                            key = f'water_depth {i}_action'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'gen_robustness', 'general_complexity', '_maction'))

                with action_c1.expander(f'Mitigations for Rig Status: {st.session_state.rig_status}', expanded=True):
                    for i in db['Well_characteristics']["Rig_status"][f'{st.session_state.rig_status}'][
                        'actions_m']:
                        key = f'Correlation_wells {i}_maction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'gen_robustness', 'general_complexity', '_maction'))
                    for i in db['Well_characteristics']["Rig_status"][f'{st.session_state.rig_status}'][
                        'actions_s']:
                        key = f'Correlation_wells {i}_action'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'gen_robustness', 'general_complexity', '_maction'))

                with action_c1.expander(f'Mitigations for {st.session_state.Correlation_wells}', expanded=True):
                    for i in db['Well_characteristics']["Correlation_wells"][f'{st.session_state.Correlation_wells}'][
                        'actions_m']:
                        key = f'Correlation_wells {i}_maction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'gen_robustness', 'general_complexity', '_maction'))
                    for i in db['Well_characteristics']['Correlation_wells'][f'{st.session_state.Correlation_wells}'][
                        'actions_s']:
                        key = f'Correlation_wells {i}_action'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'gen_robustness', 'general_complexity', '_maction'))

                with action_c1.expander(f'Mitigations for {st.session_state.Data_quality}', expanded=True):
                    for i in db['Well_characteristics']['Data_quality'][f'{st.session_state.Data_quality}'][
                        'actions_m']:
                        key = f'Data_quality {i}_maction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'gen_robustness', 'general_complexity', '_maction'))
                    for i in db['Well_characteristics']['Data_quality'][f'{st.session_state.Data_quality}'][
                        'actions_s']:
                        key = f'Data_quality {i}_action'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'gen_robustness', 'general_complexity', '_maction'))

                with action_c1.expander(f'Mitigations for {st.session_state.Learning_curve}', expanded=True):
                    for i in db['Well_characteristics']['Learning_curve'][f'{st.session_state.Learning_curve}'][
                        'actions_m']:
                        key = f'Learning_curve {i}_maction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'gen_robustness', 'general_complexity', '_maction'))
                    for i in db['Well_characteristics']['Learning_curve'][f'{st.session_state.Learning_curve}'][
                        'actions_s']:
                        key = f'Learning_curve {i}_action'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'gen_robustness', 'general_complexity', '_maction'))

                if float(st.session_state.general_complexity) == 5:
                    with action_c1.expander(f'Mitigations for complex area', expanded=True):
                        for i in db['Well_characteristics']['General_actions']['actions']:
                            key = f'General {i}_maction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'gen_robustness', 'general_complexity', '_maction'))

                with action_c2:
                    st.plotly_chart(fig2, use_container_width=False, config={'editable': False, 'displayModeBar': False,
                                                                             "scrollZoom": False})

                with action_c3:
                    gen_cp = format(st.session_state.general_complexity, '.2f')
                    st.text_input('Well Characteristics Complexity', disabled=True, value=gen_cp)
                    st.text_input('Robustness', disabled=True, value=st.session_state.gen_robustness)

            # Geology and Reservoir actions
            with tabs3[1]:
                st.write(':red[Mandatory Actions*]')
                geo_c1, geo_c2, geo_c3 = st.columns((1.3, 0.6, 0.4))

                # Actions for type of shallow hazard
                with geo_c1.expander(f'Mitigations for {st.session_state.shallow_hazard}', expanded=True):
                    for i in db['Geology']['Shallow Hazard Risk'][f'{st.session_state.shallow_hazard}']['actions_m']:
                        key = f'Geology {i}_geomaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))

                    for i in db['Geology']['Shallow Hazard Risk'][f'{st.session_state.shallow_hazard}']['actions_s']:
                        key = f'Geology {i}_geosaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))

                # Actions for presence of H2S
                if st.session_state.h2s_content != 0:
                    with geo_c1.expander(f'Mitigations for {st.session_state.h2s_content} ppm of H2S', expanded=True):
                        for i in db['Geology']['H2S Content']['actions']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                elif st.session_state.h2s_geoscore >= 10:
                    with geo_c1.expander(f'Mitigations for {st.session_state.h2s_content} ppm of H2S', expanded=True):
                        for i in db['Geology']['H2S Content']['actions10']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))

                # Actions for presence of CO2
                if st.session_state.co2_content != 0:
                    with geo_c1.expander(f'Mitigations for {st.session_state.co2_content}% of CO2', expanded=True):
                        for i in db['Geology']['CO2 Content']['actions']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))

                # Actions for Max Wellhead pressure
                if st.session_state.wellhead_geoscore != 0:
                    with geo_c1.expander(
                            f'Mitigations for {st.session_state.max_wellhead:.2f} psi of Max Wellhead Pressure',
                            expanded=True):
                        for i in db['Geology']['Wellhead Pressure']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))

                        if st.session_state.wellhead_geoscore >= 4:
                            for i in db['Geology']['Wellhead Pressure']['actions_s']:
                                key = f'Geology {i}_geosaction'
                                st.checkbox(f':black[{i}*]', key=key,
                                            on_change=sum_rob,
                                            args=(key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))

                # Actions for Mud Wight Window
                with geo_c1.expander(f'Mitigations for {st.session_state.op_window} ppg of mud weight window',
                                     expanded=True):
                    if st.session_state.op_window_geoscore == 2:
                        for i in db['Geology']['Mud Wight Window']['min']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                        for i in db['Geology']['Mud Wight Window']['min']['actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':black[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))

                    elif 3 <= st.session_state.op_window_geoscore < 7:

                        for i in db['Geology']['Mud Wight Window']['near']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                        for i in db['Geology']['Mud Wight Window']['near']['actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':black[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'geo_robustness', 'geo_complexity', '_geomaction'))

                    elif 7 <= st.session_state.op_window_geoscore < 10:

                        for i in db['Geology']['Mud Wight Window']['med']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                        for i in db['Geology']['Mud Wight Window']['med']['actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':black[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'geo_robustness', 'geo_complexity', '_geomaction'))

                    elif st.session_state.op_window_geoscore >= 10:
                        for i in db['Geology']['Mud Wight Window']['max']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                        for i in db['Geology']['Mud Wight Window']['max']['actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':black[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'geo_robustness', 'geo_complexity', '_geomaction'))

                # Actions for temperature
                with geo_c1.expander(
                        f'Mitigations for {st.session_state.max_bottom_hole} °C of bottom hole temperature',
                        expanded=True):
                    if st.session_state.hole_temp_geoscore == 3:
                        for i in db['Geology']['Hole Temperature']['min']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                        for i in db['Geology']['Hole Temperature']['min']['actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':black[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(
                                            key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))

                    elif 3 < st.session_state.hole_temp_geoscore <= 7:

                        for i in db['Geology']['Hole Temperature']['near']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                        for i in db['Geology']['Hole Temperature']['near']['actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':black[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(
                                            key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))

                    elif 7 < st.session_state.hole_temp_geoscore < 10:

                        for i in db['Geology']['Hole Temperature']['med']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                        for i in db['Geology']['Hole Temperature']['med']['actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':black[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(
                                            key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))

                    elif st.session_state.hole_temp_geoscore >= 10:
                        for i in db['Geology']['Hole Temperature']['max']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                        for i in db['Geology']['Hole Temperature']['max']['actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':black[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(
                                            key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))

                # Actions for the presence of tectonic effect
                if st.session_state.tec_effect == 'Yes':
                    with geo_c1.expander(f'Mitigations for presence of tectonic effect', expanded=True):
                        for i in db['Geology']['Tectonic']['actions']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))

                # Actions for type of salt formation
                with geo_c1.expander(f'Mitigations for salt formation: {st.session_state.salt_formation}',
                                     expanded=True):
                    for i in db['Geology']['Salt Formation'][f'{st.session_state.salt_formation}']['actions_m']:
                        key = f'Geology {i}_geomaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))

                    for i in db['Geology']['Salt Formation'][f'{st.session_state.salt_formation}']['actions_s']:
                        key = f'Geology {i}_geosaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))

                # Actions for formation pressure
                if st.session_state.ab_pressure:
                    with geo_c1.expander(f'Mitigations for well with Abnormal Low Pressure',
                                         expanded=True):
                        for i in db['Geology']['Formations Pressures'][f'Abnormal Low Pressure (6 to 8,5 ppg)'][
                            'actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))
                if st.session_state.dp_pressure:
                    with geo_c1.expander(f'Mitigations for well with Depletion',
                                         expanded=True):
                        for i in db['Geology']['Formations Pressures'][f'Depletion (< 6ppg)']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))

                        for i in db['Geology']['Formations Pressures'][f'Depletion (< 6ppg)']['actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))
                if st.session_state.ov_pressure:
                    with geo_c1.expander(f'Mitigations for well with Over Pressure',
                                         expanded=True):
                        for i in db['Geology']['Formations Pressures'][f'Over Pressure (9,1 to 90% Overburden)'][
                            'actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))

                        for i in db['Geology']['Formations Pressures'][f'Over Pressure (9,1 to 90% Overburden)'][
                            'actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))
                if st.session_state.ho_pressure:
                    with geo_c1.expander(f'Mitigations for well with High Overpressure',
                                         expanded=True):
                        for i in db['Geology']['Formations Pressures'][f'High Overpressure (above 90% Overburden)'][
                            'actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))

                # Actions for formation to be drilled type
                if st.session_state.weak_form:
                    with geo_c1.expander(f'Mitigations for drill weak formation',
                                         expanded=True):
                        for i in db['Geology']['Formation to Drill'][f'Weak']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                if st.session_state.fractured_form:
                    with geo_c1.expander(f'Mitigations for drill fractured formation',
                                         expanded=True):
                        for i in db['Geology']['Formation to Drill'][f'Fractured']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                if st.session_state.reactive_form:
                    with geo_c1.expander(f'Mitigations for drill reactive formation',
                                         expanded=True):
                        for i in db['Geology']['Formation to Drill'][f'Reactive']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                if st.session_state.reactive_form:
                    with geo_c1.expander(f'Mitigations for drill abrasive formation',
                                         expanded=True):
                        for i in db['Geology']['Formation to Drill'][f'Abrasive']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                if st.session_state.hard_form:
                    with geo_c1.expander(f'Mitigations for drill hard formation',
                                         expanded=True):
                        for i in db['Geology']['Formation to Drill'][f'Hard']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))
                        for i in db['Geology']['Formation to Drill'][f'Hard']['actions_s']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':black[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'geo_robustness', 'geo_complexity', '_geomaction'))

                if st.session_state.stress_state != 'Magnitude and Orientation':
                    with geo_c1.expander(f'Mitigations for stress state {st.session_state.stress_state}',
                                         expanded=True):
                        for i in db['Geology']['Stress State'][f'{st.session_state.stress_state}']['actions_m']:
                            key = f'Geology {i}_geomaction'
                            st.checkbox(f':red[{i}*]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))

                        for i in db['Geology']['Stress State'][f'{st.session_state.stress_state}']['actions_s']:
                            key = f'Geology {i}_geosaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))

                # Actions for formation fluid
                with geo_c1.expander(f'Mitigations for formation fluid: {st.session_state.expected_fluid}',
                                     expanded=True):
                    for i in db['Geology']['Formation Fluid'][f'{st.session_state.expected_fluid}']['actions_m']:
                        key = f'Geology {i}_geomaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'geo_robustness', 'geo_complexity', '_geomaction'))

                    for i in db['Geology']['Formation Fluid'][f'{st.session_state.expected_fluid}']['actions_s']:
                        key = f'Geology {i}_geosaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'geo_robustness', 'geo_complexity', '_geosaction'))

                with geo_c2:
                    fig_geo = crit_matrix()
                    st.plotly_chart(fig_geo, use_container_width=False,
                                    config={'editable': False, 'displayModeBar': False,
                                            "scrollZoom": False})
                with geo_c3:
                    cc = float(st.session_state.geo_complexity)
                    rr = float(st.session_state.geo_robustness)
                    st.text_input('Geology Complexity', disabled=True, value=f'{cc:.2f}')
                    st.text_input('Geology Robustness', disabled=True, value=f'{rr:.2f}')

            # Drilling Mitigation Action
            with tabs3[2]:
                st.write(':red[Mandatory Actions*]')
                drill_c1, drill_c2, drill_c3 = st.columns((1.3, 0.6, 0.4))

                with drill_c1.expander(f'Mitigations for {st.session_state.total_depth} ft of total depht',
                                       expanded=True):
                    if 3810 <= st.session_state.total_depth <= 5333:
                        for i in db['Drilling']['Total Depth'][f'med']['actions_s']:
                            key = f'Drilling {i}_drillsaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                    elif st.session_state.total_depth > 5333:
                        for i in db['Drilling']['Total Depth'][f'max']['actions_m']:
                            key = f'Drilling {i}_drillmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                with drill_c1.expander(f'Mitigations for Well Alignment: {st.session_state.well_alignment}',
                                       expanded=True):
                    for i in db['Drilling']['Well Alignment'][f'{st.session_state.well_alignment}']['actions_m']:
                        key = f'Drilling {i}_drillmaction'
                        st.checkbox(f':red[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                    for i in db['Drilling']['Well Alignment'][f'{st.session_state.well_alignment}']['actions_s']:
                        key = f'Drilling {i}_drillsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                with drill_c1.expander(f'Mitigations for {st.session_state.number_phases}',
                                       expanded=True):
                    for i in db['Drilling']['Phase Number'][f'{st.session_state.number_phases}']['actions_m']:
                        key = f'Drilling {i}_drillmaction'
                        st.checkbox(f':red[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                    for i in db['Drilling']['Phase Number'][f'{st.session_state.number_phases}']['actions_s']:
                        key = f'Drilling {i}_drillsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                with drill_c1.expander(f'Mitigations for {st.session_state.hole_enlargements} hole enlargements',
                                       expanded=True):
                    for i in db['Drilling']['Hole Enlargements'][f'{st.session_state.hole_enlargements}']['actions_m']:
                        key = f'Drilling {i}_drillmaction'
                        st.checkbox(f':red[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                    for i in db['Drilling']['Hole Enlargements'][f'{st.session_state.hole_enlargements}']['actions_s']:
                        key = f'Drilling {i}_drillsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                with drill_c1.expander(f'Mitigations for {st.session_state.slim_hole}',
                                       expanded=True):
                    for i in db['Drilling']['Slim Hole'][f'{st.session_state.slim_hole}']['actions_m']:
                        key = f'Drilling {i}_drillmaction'
                        st.checkbox(f':red[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                    for i in db['Drilling']['Slim Hole'][f'{st.session_state.slim_hole}']['actions_s']:
                        key = f'Drilling {i}_drillsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                if st.session_state.vertical_well == 'No':
                    with drill_c1.expander(
                            f'Mitigations for {st.session_state.max_inclination} of slant max inclination',
                            expanded=True):
                        if 4 <= st.session_state.max_inclination <= 54:
                            for i in db['Drilling']['Slant Maximum Inclination'][f'min']['actions_s']:
                                key = f'Drilling {i}_drillsaction'
                                st.checkbox(f':black[{i}]', key=key,
                                            on_change=sum_rob,
                                            args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                        elif 55 <= st.session_state.max_inclination <= 89:
                            for i in db['Drilling']['Slant Maximum Inclination'][f'med']['actions_m']:
                                key = f'Drilling {i}_drillmaction'
                                st.checkbox(f':red[{i}]', key=key,
                                            on_change=sum_rob,
                                            args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))
                            for i in db['Drilling']['Slant Maximum Inclination'][f'med']['actions_s']:
                                key = f'Drilling {i}_drillsaction'
                                st.checkbox(f':black[{i}]', key=key,
                                            on_change=sum_rob,
                                            args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                        elif st.session_state.max_inclination > 89:
                            for i in db['Drilling']['Slant Maximum Inclination'][f'max']['actions_m']:
                                key = f'Drilling {i}_drillmaction'
                                st.checkbox(f':red[{i}]', key=key,
                                            on_change=sum_rob,
                                            args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))
                            for i in db['Drilling']['Slant Maximum Inclination'][f'max']['actions_s']:
                                key = f'Drilling {i}_drillsaction'
                                st.checkbox(f':black[{i}]', key=key,
                                            on_change=sum_rob,
                                            args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                    with drill_c1.expander(
                            f'Mitigations for  trajectory: {st.session_state.complex_trajectory_planned}',
                            expanded=True):

                        for i in db['Drilling']['Trajectory Planned'][f'{st.session_state.complex_trajectory_planned}'][
                            'actions_m']:
                            key = f'Drilling {i}_drillmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                        for i in db['Drilling']['Trajectory Planned'][f'{st.session_state.complex_trajectory_planned}'][
                            'actions_s']:
                            key = f'Drilling {i}_drillsaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                    with drill_c1.expander(
                            f'Mitigations for {st.session_state.max_dogleg} of trajectory maximum dogleg',
                            expanded=True):
                        if 2.47 <= st.session_state.max_dogleg <= 3.37:
                            for i in db['Drilling']['Maximum Dogleg'][f'med']['actions_s']:
                                key = f'Drilling {i}_drillsaction'
                                st.checkbox(f':black[{i}]', key=key,
                                            on_change=sum_rob,
                                            args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                        elif st.session_state.max_dogleg >= 3.38:
                            for i in db['Drilling']['Maximum Dogleg'][f'max']['actions_m']:
                                key = f'Drilling {i}_drillmaction'
                                st.checkbox(f':red[{i}]', key=key,
                                            on_change=sum_rob,
                                            args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                with drill_c1.expander(f'Mitigations for maximum distance to other wells: {st.session_state.well_distance}',
                                       expanded=True):
                    for i in db['Drilling']['Distance to Well'][f'{st.session_state.well_distance}']['actions_m']:
                        key = f'Drilling {i}_drillmaction'
                        st.checkbox(f':red[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                    for i in db['Drilling']['Distance to Well'][f'{st.session_state.well_distance}']['actions_s']:
                        key = f'Drilling {i}_drillsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                with drill_c1.expander(f'Mitigations for {st.session_state.type_aquifer} aquifer',
                                       expanded=True):
                    for i in db['Drilling']['Type of Aquifer'][f'{st.session_state.type_aquifer}']['actions_m']:
                        key = f'Drilling {i}_drillmaction'
                        st.checkbox(f':red[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                    for i in db['Drilling']['Type of Aquifer'][f'{st.session_state.type_aquifer}']['actions_s']:
                        key = f'Drilling {i}_drillsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                with drill_c1.expander(f'Mitigations for casing type: {st.session_state.casing_type}',
                                       expanded=True):
                    for i in db['Drilling']['Casing Type'][f'{st.session_state.casing_type}']['actions_m']:
                        key = f'Drilling {i}_drillmaction'
                        st.checkbox(f':red[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                    for i in db['Drilling']['Casing Type'][f'{st.session_state.casing_type}']['actions_s']:
                        key = f'Drilling {i}_drillsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                with drill_c1.expander(f'Mitigations for shear Casing: {st.session_state.non_shear_casing}',
                                       expanded=True):
                    for i in db['Drilling']['Non-shear Casing'][f'{st.session_state.non_shear_casing}']['actions_m']:
                        key = f'Drilling {i}_drillmaction'
                        st.checkbox(f':red[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                    for i in db['Drilling']['Non-shear Casing'][f'{st.session_state.non_shear_casing}']['actions_s']:
                        key = f'Drilling {i}_drillsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                if 0 < st.session_state.fluid_density <= 10.35:
                    with drill_c1.expander(f'Mitigations for {st.session_state.fluid_density} of maximum fluid density',
                                           expanded=True):
                        for i in db['Drilling']['Maximum fluid density'][f'min']['actions_s']:
                            key = f'Drilling {i}_drillsaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                elif 10.36 <= st.session_state.fluid_density <= 12.47:
                    with drill_c1.expander(f'Mitigations for {st.session_state.fluid_density} of maximum fluid density',
                                           expanded=True):
                        for i in db['Drilling']['Maximum fluid density'][f'med']['actions_s']:
                            key = f'Drilling {i}_drillsaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                elif 12.48 <= st.session_state.fluid_density <= 13.88:
                    with drill_c1.expander(f'Mitigations for {st.session_state.fluid_density} of maximum fluid density',
                                           expanded=True):
                        for i in db['Drilling']['Maximum fluid density'][f'med2']['actions_s']:
                            key = f'Drilling {i}_drillsaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                elif st.session_state.fluid_density > 13.88:
                    with drill_c1.expander(f'Mitigations for {st.session_state.fluid_density} of maximum fluid density',
                                           expanded=True):
                        for i in db['Drilling']['Maximum fluid density'][f'max']['actions_m']:
                            key = f'Drilling {i}_drillmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                        for i in db['Drilling']['Maximum fluid density'][f'max']['actions_s']:
                            key = f'Drilling {i}_drillsaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                with drill_c1.expander(f'Mitigations for {st.session_state.lost_circulation}',
                                       expanded=True):
                    for i in db['Drilling']['Lost Circulation'][f'{st.session_state.lost_circulation}']['actions_m']:
                        key = f'Drilling {i}_drillmaction'
                        st.checkbox(f':red[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                    for i in db['Drilling']['Lost Circulation'][f'{st.session_state.lost_circulation}']['actions_s']:
                        key = f'Drilling {i}_drillsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                if st.session_state.reducing_zone == 'Yes':
                    with drill_c1.expander(f'Mitigations for zones with reduced pore pressure',
                                           expanded=True):
                        for i in db['Drilling']['Reducing pressure zone']['actions_m']:
                            key = f'Drilling {i}_drillmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                if rig_type != 'Onshore':
                    with drill_c1.expander(f'Mitigations for not considering riser safety margin',
                                           expanded=True):
                        for i in db['Drilling']['Riser Safety Margin'][f'{st.session_state.riser_safety_margin}'][
                            'actions_m']:
                            key = f'Drilling {i}_drillmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                        for i in db['Drilling']['Riser Safety Margin'][f'{st.session_state.riser_safety_margin}'][
                            'actions_s']:
                            key = f'Drilling {i}_drillsaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                with drill_c1.expander(f'Mitigations for drilling fluid: {st.session_state.drilling_fluid}',
                                       expanded=True):
                    for i in db['Drilling']['Drilling Fluid'][f'{st.session_state.drilling_fluid}']['actions_m']:
                        key = f'Drilling {i}_drillmaction'
                        st.checkbox(f':red[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'drill_robustness', 'drill_complexity', '_drillmaction'))

                    for i in db['Drilling']['Drilling Fluid'][f'{st.session_state.drilling_fluid}']['actions_s']:
                        key = f'Drilling {i}_drillsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'drill_robustness', 'drill_complexity', '_drillsaction'))

                with drill_c2:
                    fig_drill_matrix = crit_matrix()
                    st.plotly_chart(fig_drill_matrix, use_container_width=False, config={'editable': False,
                                                                                         'displayModeBar': False,
                                                                                         "scrollZoom": False})
                with drill_c3:
                    cc = st.session_state.drill_complexity
                    rr = float(st.session_state.drill_robustness)
                    st.text_input('Drilling Complexity', disabled=True, value=f'{cc:.2f}', key='drill_cc')
                    st.text_input('Drilling Robustness', disabled=True, value=f'{rr:.2f}')

            # Completion Mitigation Action
            with tabs3[3]:
                st.write(':red[Mandatory Actions*]')
                comp_c1, comp_c2, comp_c3 = st.columns((1.3, 0.6, 0.4))

                # Actions for trajectory inclination in the reservoir
                with comp_c1.expander(f'Mitigations for {st.session_state.res_inclination}º'
                                      f' of trajectory inclination within the reservoir  ', expanded=True):
                    if 57 <= st.session_state.res_inclination <= 78:
                        for i in db['Completion']['Inclination'][f'med']['actions_s']:
                            key = f'Completion {i}_compsaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'comp_robustness', 'comp_complexity', '_compsaction'))

                    elif st.session_state.res_inclination >= 79:
                        for i in db['Completion']['Inclination'][f'max']['actions_m']:
                            key = f'Completion {i}_compmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'comp_robustness', 'comp_complexity', '_compmaction'))

                # Actions for trajectory length in the reservoir
                with comp_c1.expander(f'Mitigations for {st.session_state.res_length} ft'
                                      f' of trajectory length within the reservoir  ', expanded=True):
                    if 777 <= st.session_state.res_length <= 1303:
                        for i in db['Completion']['Length'][f'med']['actions_s']:
                            key = f'Completion {i}_compsaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'comp_robustness', 'comp_complexity', '_compsaction'))

                    elif st.session_state.res_length > 1303:
                        for i in db['Completion']['Length'][f'max']['actions_m']:
                            key = f'Completion {i}_commaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'comp_robustness', 'comp_complexity', '_compmaction'))
                # Actions for production casing cementing
                with comp_c1.expander(f'Mitigations for Production Casing: {st.session_state.production_casing}',
                                      expanded=True):
                    for i in db['Completion']["Production Casing"][f'{st.session_state.production_casing}'][
                        'actions_m']:
                        key = f'Completion {i}_compmaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'comp_robustness', 'comp_complexity', '_compmaction'))
                    for i in db['Completion']["Production Casing"][f'{st.session_state.production_casing}'][
                        'actions_s']:
                        key = f'Completion {i}_compsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'comp_robustness', 'comp_complexity', '_compsaction'))

                # Actions for zone completion
                with comp_c1.expander(f'Mitigations for Zone Completion: {st.session_state.multizone_completion}',
                                      expanded=True):
                    for i in db['Completion']["Multizone completion"][f'{st.session_state.multizone_completion}'][
                        'actions_m']:
                        key = f'Completion {i}_compmaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'comp_robustness', 'comp_complexity', '_compmaction'))
                    for i in db['Completion']["Multizone completion"][f'{st.session_state.multizone_completion}'][
                        'actions_s']:
                        key = f'Completion {i}_compsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'comp_robustness', 'comp_complexity', '_compsaction'))
                # Actions for reservoir pressure contrast
                with comp_c1.expander(
                        f'Mitigations for reservoir with pressure contrast: {st.session_state.pressure_contrast}',
                        expanded=True):
                    for i in db['Completion']["Res. with pressure contrast"][f'{st.session_state.pressure_contrast}'][
                        'actions_m']:
                        key = f'Completion {i}_compmaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'comp_robustness', 'comp_complexity', '_compmaction'))
                    for i in db['Completion']["Res. with pressure contrast"][f'{st.session_state.pressure_contrast}'][
                        'actions_s']:
                        key = f'Completion {i}_compsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'comp_robustness', 'comp_complexity', '_compsaction'))

                # Actions for type of fracture
                with comp_c1.expander(
                        f'Mitigations for {st.session_state.frat_type}: {st.session_state.fracturing}',
                        expanded=True):
                    for i in db['Completion'][f"{st.session_state.frat_type}"][f'{st.session_state.fracturing}'][
                        'actions_m']:
                        key = f'Completion {i}_compmaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'comp_robustness', 'comp_complexity', '_compmaction'))
                    for i in db['Completion'][f"{st.session_state.frat_type}"][f'{st.session_state.fracturing}'][
                        'actions_s']:
                        key = f'Completion {i}_compsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'comp_robustness', 'comp_complexity', '_compsaction'))

                # Actions for sand control type
                with comp_c1.expander(f'Mitigations for {st.session_state.sand_control_type} '
                                      f'Sand Control Completion Type: {st.session_state.sand_pack}', expanded=True):
                    for i in db['Completion'][f"{st.session_state.sand_control_type}"][f'{st.session_state.sand_pack}'][
                        'actions_m']:
                        key = f'Completion {i}_compmaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'comp_robustness', 'comp_complexity', '_compmaction'))
                    for i in db['Completion'][f"{st.session_state.sand_control_type}"][f'{st.session_state.sand_pack}'][
                        'actions_s']:
                        key = f'Completion {i}_compsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'comp_robustness', 'comp_complexity', '_compsaction'))

                # Actions for artificial lift
                with comp_c1.expander(
                        f'Mitigations for artificial lift type: {st.session_state.artificial_lift}',
                        expanded=True):
                    for i in db['Completion']["Type of Artificial Lift"][f'{st.session_state.artificial_lift}'][
                        'actions_m']:
                        key = f'Completion {i}_compmaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'comp_robustness', 'comp_complexity', '_compmaction'))
                    for i in db['Completion']["Type of Artificial Lift"][f'{st.session_state.artificial_lift}'][
                        'actions_s']:
                        key = f'Completion {i}_compsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'comp_robustness', 'comp_complexity', '_compsaction'))
                # Actions for production data
                with comp_c1.expander(
                        f'Mitigations for production flow rate: {st.session_state.production_data}',
                        expanded=True):
                    for i in db['Completion']["Production flow rate"][f'{st.session_state.production_data}'][
                        'actions_m']:
                        key = f'Completion {i}_compmaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'comp_robustness', 'comp_complexity', '_compmaction'))
                    for i in db['Completion']["Production flow rate"][f'{st.session_state.production_data}'][
                        'actions_s']:
                        key = f'Completion {i}_compsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'comp_robustness', 'comp_complexity', '_compsaction'))

                with comp_c2:
                    fig_comp_matrix = crit_matrix()
                    st.plotly_chart(fig_comp_matrix, use_container_width=False, config={'editable': False,
                                                                                        'displayModeBar': False,
                                                                                        "scrollZoom": False})
                with comp_c3:
                    cc = st.session_state.comp_complexity
                    rr = float(st.session_state.comp_robustness)
                    st.text_input('Completion Complexity', disabled=True, value=f'{cc:.2f}', key='comp_cc')
                    st.text_input('Completion Robustness', disabled=True, value=f'{rr:.2f}')

            # Logistic Mitigation Action
            with tabs3[4]:
                st.write(':red[Mandatory Actions*]')
                log_c1, log_c2, log_c3 = st.columns((1.3, 0.6, 0.4))

                # Mitigation actions for operational support
                with log_c1.expander(f'Mitigations for {st.session_state.op_support}', expanded=True):
                    for i in db['Logistic']['Operational Support'][f'{st.session_state.op_support}']['actions_m']:
                        key = f'Logistic {i}_logmaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'log_robustness', 'log_complexity', '_logmaction'))
                    for i in db['Logistic']['Operational Support'][f'{st.session_state.op_support}']['actions_s']:
                        key = f'Logistic {i}_logsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'log_robustness', 'log_complexity', '_logsaction'))

                # Mitigation actions for fluid and cuts disposal
                with log_c1.expander(f'Mitigations for {st.session_state.fluid_disposal}', expanded=True):
                    for i in db['Logistic']['Fluid Disposal'][f'{st.session_state.fluid_disposal}']['actions_m']:
                        key = f'Logistic {i}_logmaction'
                        st.checkbox(f':red[{i}*]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'log_robustness', 'log_complexity', '_logmaction'))
                    for i in db['Logistic']['Fluid Disposal'][f'{st.session_state.fluid_disposal}']['actions_s']:
                        key = f'Logistic {i}_logsaction'
                        st.checkbox(f':black[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, False, 'log_robustness', 'log_complexity', '_logsaction'))

                with log_c1.expander(f'Mitigations for {st.session_state.distance_base} miles of distance from base',
                                     expanded=True):
                    if 537406 <= st.session_state.distance_base <= 1551000:
                        for i in db['Logistic']['Distance to Operational Base'][f'med']['actions_s']:
                            key = f'Logistic {i}_logsaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'log_robustness', 'log_complexity', '_logsaction'))

                    elif st.session_state.distance_base > 1551000:
                        for i in db['Logistic']['Distance to Operational Base'][f'max']['actions_m']:
                            key = f'Logistic {i}_logmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'log_robustness', 'log_complexity', '_logmaction'))

                with log_c1.expander(
                        f'Mitigations for {st.session_state.distance_warehouse} miles of distance from warehouse',
                        expanded=True):
                    if 178599 <= st.session_state.distance_warehouse <= 465000:
                        for i in db['Logistic']['Distance to Warehouse'][f'med']['actions_s']:
                            key = f'Logistic {i}_logsaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'log_robustness', 'log_complexity', '_logsaction'))

                    elif st.session_state.distance_warehouse > 465000:
                        for i in db['Logistic']['Distance to Warehouse'][f'max']['actions_m']:
                            key = f'Logistic {i}_logmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'log_robustness', 'log_complexity', '_logmaction'))

                with log_c2:
                    fig_log_matrix = crit_matrix()
                    st.plotly_chart(fig_log_matrix, use_container_width=False, config={'editable': False,
                                                                                       'displayModeBar': False,
                                                                                       "scrollZoom": False})
                with log_c3:
                    cc = st.session_state.log_complexity
                    rr = float(st.session_state.log_robustness)
                    st.text_input('Logistic Complexity', disabled=True, value=f'{cc:.2f}', key='log_cc')
                    st.text_input('Logistic Robustness', disabled=True, value=f'{rr:.2f}')

            # Metocean Mitigation Action
            with tabs3[5]:
                st.write(':red[Mandatory Actions*]')
                meto_c1, meto_c2, meto_c3 = st.columns((1.3, 0.6, 0.4))

                with meto_c1.expander(f'Mitigations for {st.session_state.sea_current} knots of sea current',
                                      expanded=True):
                    if 2.2 <= st.session_state.sea_current <= 3.95:
                        for i in db['Metocean']['Sea Current'][f'med']['actions_s']:
                            key = f'Metocean {i}_metosaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'meto_robustness', 'meto_complexity', '_metosaction'))

                    elif st.session_state.sea_current >= 3.96:
                        for i in db['Metocean']['Sea Current'][f'max']['actions_m']:
                            key = f'Metocean {i}_metomaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'meto_robustness', 'meto_complexity', '_metomaction'))

                with meto_c1.expander(f'Mitigations for {st.session_state.wave_h} meters of wave height',
                                      expanded=True):
                    if 3.35 <= st.session_state.wave_h <= 4.88:
                        for i in db['Metocean']['Waves Height'][f'med']['actions_s']:
                            key = f'Metocean {i}_metosaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'meto_robustness', 'meto_complexity', '_metosaction'))

                    elif 4.88 < st.session_state.wave_h <= 5.79:
                        for i in db['Metocean']['Waves Height'][f'med2']['actions_m']:
                            key = f'Metocean {i}_metomaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'meto_robustness', 'meto_complexity', '_metomaction'))

                        for i in db['Metocean']['Waves Height'][f'med2']['actions_s']:
                            key = f'Metocean {i}_metosaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'meto_robustness', 'meto_complexity', '_metosaction'))

                    elif st.session_state.wave_h >= 6.10:
                        for i in db['Metocean']['Waves Height'][f'max']['actions_m']:
                            key = f'Metocean {i}_metomaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'meto_robustness', 'meto_complexity', '_metomaction'))

                with meto_c1.expander(f'Mitigations for {st.session_state.wind_speed} knots of wind speed',
                                      expanded=True):
                    if 20.74 <= st.session_state.wind_speed <= 34.24:
                        for i in db['Metocean']['Wind Speed'][f'med']['actions_s']:
                            key = f'Metocean {i}_metosaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'meto_robustness', 'meto_complexity', '_metosaction'))

                    elif st.session_state.wind_speed >= 34.25:
                        for i in db['Metocean']['Wind Speed'][f'max']['actions_m']:
                            key = f'Metocean {i}_metomaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'meto_robustness', 'meto_complexity', '_metomaction'))

                with meto_c2:
                    fig_meto_matrix = crit_matrix()
                    st.plotly_chart(fig_meto_matrix, use_container_width=False, config={'editable': False,
                                                                                        'displayModeBar': False,
                                                                                        "scrollZoom": False})
                with meto_c3:
                    cc = st.session_state.meto_complexity
                    rr = float(st.session_state.meto_robustness)
                    st.text_input('Metocean Complexity', disabled=True, value=f'{cc:.2f}', key='meto_cc')
                    st.text_input('Metocean Robustness', disabled=True, value=f'{rr:.2f}')

            # Braskem Mitigation Action
            with tabs3[6]:
                if 'loss_zone' not in st.session_state:
                    st.session_state.loss_zone = 'No'
                st.write(':red[Mandatory Actions*]')
                brk_c1, brk_c2, brk_c3 = st.columns((1.3, 0.6, 0.4))

                with brk_c1.expander(f'Mitigations for cavity {st.session_state.press}', expanded=True):
                    if st.session_state.press == 'Unpressurized':
                        st.write('Drilling fluid systems')
                        for i in db['Braskem']['Cavity Status'][f'Unpressurized']['actions_m_flu']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                        for i in db['Braskem']['Cavity Status'][f'Unpressurized']['actions_s_flu']:
                            key = f'Braskem {i}_brksaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'brk_robustness', 'brk_complexity', '_brksaction'))

                        st.write('Employment of technologies')
                        for i in db['Braskem']['Cavity Status'][f'Unpressurized']['actions_m_tec']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                        for i in db['Braskem']['Cavity Status'][f'Unpressurized']['actions_s_tec']:
                            key = f'Braskem {i}_brksaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'brk_robustness', 'brk_complexity', '_brksaction'))

                        st.write('Casing and cementing')
                        for i in db['Braskem']['Cavity Status'][f'Unpressurized']['actions_m_rc']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                        st.write('Well planning')
                        for i in db['Braskem']['Cavity Status'][f'Unpressurized']['actions_m_pp']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                        st.write('Drilling rig')
                        for i in db['Braskem']['Cavity Status'][f'Unpressurized']['actions_m_s']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                        for i in db['Braskem']['Cavity Status'][f'Unpressurized']['actions_s_s']:
                            key = f'Braskem {i}_brksaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'brk_robustness', 'brk_complexity', '_brksaction'))

                        st.write('Logistics')
                        for i in db['Braskem']['Cavity Status'][f'Unpressurized']['actions_m_log']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))
                    elif st.session_state.press == 'Pressurized':
                        for i in db['Braskem']['Cavity Status'][f'Pressurized']['actions_m']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                if st.session_state.loss_zone == 'Yes':
                    with brk_c1.expander(f'Mitigations for loss zone near the cavity', expanded=True):
                        st.write('Drilling fluid systems')
                        for i in db['Braskem']['Cavity Status'][f'Loss zone']['actions_m_flu']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                        for i in db['Braskem']['Cavity Status'][f'Loss zone']['actions_s_flu']:
                            key = f'Braskem {i}_brksaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'brk_robustness', 'brk_complexity', '_brksaction'))

                        st.write('Technologies')
                        for i in db['Braskem']['Cavity Status'][f'Loss zone']['actions_m_tec']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                        for i in db['Braskem']['Cavity Status'][f'Loss zone']['actions_s_tec']:
                            key = f'Braskem {i}_brksaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'brk_robustness', 'brk_complexity', '_brksaction'))

                        st.write('Casing and cementing')
                        for i in db['Braskem']['Cavity Status'][f'Loss zone']['actions_m_rc']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                        st.write('Well design')
                        for i in db['Braskem']['Cavity Status'][f'Loss zone']['actions_m_pp']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                        st.write('Drilling rig')
                        for i in db['Braskem']['Cavity Status'][f'Loss zone']['actions_m_s']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                        for i in db['Braskem']['Cavity Status'][f'Loss zone']['actions_s_s']:
                            key = f'Braskem {i}_brksaction'
                            st.checkbox(f':black[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, False, 'brk_robustness', 'brk_complexity', '_brksaction'))

                        st.write('Logistics')
                        for i in db['Braskem']['Cavity Status'][f'Loss zone']['actions_m_log']:
                            key = f'Braskem {i}_brkmaction'
                            st.checkbox(f':red[{i}]', key=key,
                                        on_change=sum_rob,
                                        args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                with brk_c1.expander(f'Mitigations for a {st.session_state.well_objective} well', expanded=True):
                    for i in db['Braskem']['Well Objective'][f'{st.session_state.well_objective}']['actions_m']:
                        key = f'Braskem {i}_brkmaction'
                        st.checkbox(f':red[{i}]', key=key,
                                    on_change=sum_rob,
                                    args=(key, True, 'brk_robustness', 'brk_complexity', '_brkmaction'))

                with brk_c2:
                    fig_brk_matrix = crit_matrix()
                    st.plotly_chart(fig_brk_matrix, use_container_width=False, config={'editable': False,
                                                                                       'displayModeBar': False,
                                                                                       "scrollZoom": False})

                with brk_c3:
                    cc = st.session_state.brk_complexity
                    rr = float(st.session_state.brk_robustness)
                    st.text_input('Braskem project Complexity', disabled=True, value=f'{cc:.2f}', key='brk_cc')
                    st.text_input('Braskem project Robustness', disabled=True, value=f'{rr:.2f}')

        # aba de review
        with tabs2[1]:
            selected_mandatory_actions = []
            not_selected_mandatory_actions = []
            selected_suggested_actions = []
            not_selected_suggested_actions = []

            # Well characteristics review
            with st.expander(f'Well Info', expanded=True):
                st.write('Mandatory')
                container_selected = st.container(border=True)
                container_not_selected = st.container(border=True)
                with container_not_selected:
                    st.write('Not selected')
                with container_selected:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_maction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            selected_mandatory_actions.append(n1[:-8])
                            with container_selected:
                                st.checkbox(f':red[{n1[:-8]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(i, True, 'gen_robustness', 'general_complexity', '_maction'),
                                            key=f'{i[:-8]}_review', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            not_selected_mandatory_actions.append(n1[:-8])
                            with container_not_selected:
                                st.checkbox(f':red[{n1[:-8]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(i, True, 'gen_robustness', 'general_complexity', '_maction'),
                                            key=f'{i[:-8]}_review', disabled=False)
                st.write('Suggest')
                container_selected_s = st.container(border=True)
                container_not_selected_s = st.container(border=True)
                with container_not_selected_s:
                    st.write('Not selected')
                with container_selected_s:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_action'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            selected_suggested_actions.append(n1[:-8])
                            with container_selected_s:
                                st.checkbox(f'{n1[:-8]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(i, False, 'gen_robustness', 'general_complexity', '_action'),
                                            key=f'{i[:-8]}_reviews', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            not_selected_suggested_actions.append(n1[:-8])
                            with container_not_selected_s:
                                st.checkbox(f'{n1[:-8]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(i, False, 'gen_robustness', 'general_complexity', '_action'),
                                            key=f'{i[:-8]}_review', disabled=False)

            # Geology review
            with st.expander(f'Geology', expanded=True):
                st.write('Mandatory')
                container_geo_selected = st.container(border=True)
                container_not_geo_selected = st.container(border=True)
                with container_not_geo_selected:
                    st.write('Not selected')
                with container_geo_selected:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_geomaction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # selected_mandatory_actions.append(n1[:-8])
                            with container_geo_selected:
                                st.checkbox(f':red[{n1[:-11]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(i, True, 'geo_robustness', 'geo_complexity', '_geomaction'),
                                            key=f'{i[:-11]}_review', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # not_selected_mandatory_actions.append(n1[:-8])
                            with container_not_geo_selected:
                                st.checkbox(f':red[{n1[:-11]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(i, True, 'geo_robustness', 'geo_complexity', '_geomaction'),
                                            key=f'{i[:-11]}_review', disabled=False)

                st.write('Suggest')
                container_geo_selected_s = st.container(border=True)
                container_not_geo_selected_s = st.container(border=True)
                with container_not_geo_selected_s:
                    st.write('Not selected')
                with container_geo_selected_s:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_geosaction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # selected_suggested_actions.append(n1[:-8])
                            with container_geo_selected_s:
                                st.checkbox(f'{n1[:-11]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(i, False, 'geo_robustness', 'geo_complexity', '_geosaction'),
                                            key=f'{i[:-11]}_reviews', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            not_selected_suggested_actions.append(n1[:-8])
                            with container_not_geo_selected_s:
                                st.checkbox(f'{n1[:-11]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(i, False, 'geo_robustness', 'geo_complexity', '_geosaction'),
                                            key=f'{i[:-11]}_review', disabled=False)

            # Drilling review
            with st.expander(f'Drilling', expanded=True):
                st.write('Mandatory')
                container_drill_selected = st.container(border=True)
                container_not_drill_selected = st.container(border=True)
                with container_not_drill_selected:
                    st.write('Not selected')
                with container_drill_selected:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_drillmaction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # selected_mandatory_actions.append(n1[:-8])
                            with container_drill_selected:
                                st.checkbox(f':red[{n1[:-12]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(
                                                i, True, 'drill_robustness', 'drill_complexity', '_drillmaction'),
                                            key=f'{i[:-12]}_review', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # not_selected_mandatory_actions.append(n1[:-8])
                            with container_not_drill_selected:
                                st.checkbox(f':red[{n1[:-12]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(
                                                i, True, 'drill_robustness', 'drill_complexity', '_drillmaction'),
                                            key=f'{i[:-12]}_review', disabled=False)

                st.write('Suggest')
                container_drill_selected_s = st.container(border=True)
                container_not_drill_selected_s = st.container(border=True)
                with container_not_drill_selected_s:
                    st.write('Not selected')
                with container_drill_selected_s:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_drillsaction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            with container_drill_selected_s:
                                st.checkbox(f'{n1[:-12]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(
                                                i, False, 'drill_robustness', 'drill_complexity', '_drillsaction'),
                                            key=f'{i[:-12]}_reviews', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            with container_not_drill_selected_s:
                                st.checkbox(f'{n1[:-11]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(
                                                i, False, 'drill_robustness', 'drill_complexity', '_drillsaction'),
                                            key=f'{i[:-12]}_review', disabled=False)

            # Completion review
            with st.expander(f'Completion', expanded=True):
                st.write('Mandatory')
                container_comp_selected = st.container(border=True)
                container_not_comp_selected = st.container(border=True)
                with container_not_comp_selected:
                    st.write('Not selected')
                with container_comp_selected:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_compmaction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # selected_mandatory_actions.append(n1[:-8])
                            with container_comp_selected:
                                st.checkbox(f':red[{n1[:-12]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(i, True, 'comp_robustness', 'comp_complexity', '_compmaction'),
                                            key=f'{i[:-12]}_review', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # not_selected_mandatory_actions.append(n1[:-8])
                            with container_not_comp_selected:
                                st.checkbox(f':red[{n1[:-12]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(i, True, 'comp_robustness', 'comp_complexity', '_compmaction'),
                                            key=f'{i[:-12]}_review', disabled=False)

                st.write('Suggest')
                container_comp_selected_s = st.container(border=True)
                container_not_comp_selected_s = st.container(border=True)
                with container_not_comp_selected_s:
                    st.write('Not selected')
                with container_comp_selected_s:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_compsaction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            with container_comp_selected_s:
                                st.checkbox(f'{n1[:-12]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(i, False, 'comp_robustness', 'comp_complexity', '_compsaction'),
                                            key=f'{i[:-12]}_reviews', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            with container_not_comp_selected_s:
                                st.checkbox(f'{n1[:-11]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(i, False, 'comp_robustness', 'comp_complexity', '_compsaction'),
                                            key=f'{i[:-12]}_review', disabled=False)

            # Logistic review
            with st.expander(f'Logistic', expanded=True):
                st.write('Mandatory')
                container_log_selected = st.container(border=True)
                container_not_log_selected = st.container(border=True)
                with container_not_log_selected:
                    st.write('Not selected')
                with container_log_selected:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_logmaction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # selected_mandatory_actions.append(n1[:-11])
                            with container_log_selected:
                                st.checkbox(f':red[{n1[:-11]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(i, True, 'log_robustness', 'log_complexity', '_logmaction'),
                                            key=f'{i[:-11]}_review', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # not_selected_mandatory_actions.append(n1[:-11])
                            with container_not_log_selected:
                                st.checkbox(f':red[{n1[:-11]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(i, True, 'log_robustness', 'log_complexity', '_logmaction'),
                                            key=f'{i[:-11]}_review', disabled=False)
                st.write('Suggest')
                container_selected_s = st.container(border=True)
                container_not_selected_s = st.container(border=True)
                with container_not_selected_s:
                    st.write('Not selected')
                with container_selected_s:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_logsaction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # selected_suggested_actions.append(n1[:-11])
                            with container_selected_s:
                                st.checkbox(f'{n1[:-11]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(i, False, 'log_robustness', 'log_complexity', '_logsaction'),
                                            key=f'{i[:-11]}_reviews', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            not_selected_suggested_actions.append(n1[:-11])
                            with container_not_selected_s:
                                st.checkbox(f'{n1[:-11]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(i, False, 'log_robustness', 'log_complexity', '_logsaction'),
                                            key=f'{i[:-11]}_review', disabled=False)

            # Metocean review
            with st.expander('Metocean', expanded=True):
                st.write('Mandatory')
                container_selected = st.container(border=True)
                container_not_selected = st.container(border=True)
                with container_not_selected:
                    st.write('Not selected')
                with container_selected:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_metomaction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # selected_mandatory_actions.append(n1[:-11])
                            with container_selected:
                                st.checkbox(f':red[{n1[:-11]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(i, True, 'meto_robustness', 'meto_complexity', '_metomaction'),
                                            key=f'{i[:-11]}_review', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # not_selected_mandatory_actions.append(n1[:-11])
                            with container_not_selected:
                                st.checkbox(f':red[{n1[:-11]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(i, True, 'meto_robustness', 'meto_complexity', '_metomaction'),
                                            key=f'{i[:-11]}_review', disabled=False)

            # Braskem review
            with st.expander('Braskem Project', expanded=True):
                st.write('Mandatory')
                container_selected = st.container(border=True)
                container_not_selected = st.container(border=True)
                with container_not_selected:
                    st.write('Not selected')
                with container_selected:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_brkmaction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # selected_mandatory_actions.append(n1[:-11])
                            with container_selected:
                                st.checkbox(f':red[{n1[:-11]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(
                                                i, True, 'brk_robustness', 'brk_complexity', '_brkmaction'),
                                            key=f'{i[:-11]}_review', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # not_selected_mandatory_actions.append(n1[:-11])
                            with container_not_selected:
                                st.checkbox(f':red[{n1[:-11]}]', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(
                                                i, True, 'brk_robustness', 'brk_complexity', '_brkmaction'),
                                            key=f'{i[:-11]}_review', disabled=False)

                st.write('Suggest')
                container_selected_s = st.container(border=True)
                container_not_selected_s = st.container(border=True)
                with container_not_selected_s:
                    st.write('Not selected')
                with container_selected_s:
                    st.write('Selected')
                for i in st.session_state:
                    if i.endswith('_brksaction'):
                        if st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            # selected_suggested_actions.append(n1[:-11])
                            with container_selected_s:
                                st.checkbox(f'{n1[:-11]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_f,
                                            args=(i, False, 'brk_robustness', 'brk_complexity', '_brksaction'),
                                            key=f'{i[:-11]}_reviews', disabled=False)
                        else:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            not_selected_suggested_actions.append(n1[:-11])
                            with container_not_selected_s:
                                st.checkbox(f'{n1[:-11]}', value=st.session_state[f'{i}'],
                                            on_change=reset_action_t,
                                            args=(i, False, 'brk_robustness', 'brk_complexity', '_brksaction'),
                                            key=f'{i[:-11]}_review', disabled=False)

        # Aba declined
        with tabs2[2]:

            well_exp = st.expander(f'Well Characteristics', expanded=True)
            with well_exp:
                st.write('Declined mandatory actions')

            geology_exp = st.expander(f'Geology', expanded=True)
            with geology_exp:
                st.write('Declined mandatory actions')

            drilling_exp = st.expander(f'Drilling', expanded=True)
            with drilling_exp:
                st.write('Declined mandatory actions')

            completion_exp = st.expander(f'Completion', expanded=True)
            with completion_exp:
                st.write('Declined mandatory actions')

            log_exp = st.expander(f'Logistic', expanded=True)
            with log_exp:
                st.write('Declined mandatory actions')

            meto_exp = st.expander(f'Metocen', expanded=True)
            with meto_exp:
                st.write('Declined mandatory actions')

            brk_exp = st.expander(f'Braskem Project', expanded=True)
            with brk_exp:
                st.write('Declined mandatory actions')

            for i in st.session_state:
                if i.endswith('_maction'):
                    with well_exp:
                        if not st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            st.text_input(f' Justification for not "{n1[:-8]}"',
                                          key=f'{i[:-8]}_justification')

                if i.endswith('_geomaction'):
                    with geology_exp:
                        if not st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            st.text_input(f' Justification for not "{n1[:-11]}"',
                                          key=f'{i[:-11]}_justification')

                if i.endswith('_drillmaction'):
                    with drilling_exp:
                        if not st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            st.text_input(f'Justification for not "{n1[:-12]}"',
                                          key=f'{i[:-12]}_justification')

                if i.endswith('_compmaction'):
                    with completion_exp:
                        if not st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            st.text_input(f' Justification for not "{n1[:-12]}"',
                                          key=f'{i[:-12]}_justification')

                if i.endswith('_logmaction'):
                    with log_exp:
                        if not st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            st.text_input(f' Justification for not "{n1[:-11]}"',
                                          key=f'{i[:-11]}_justification')

                if i.endswith('_metomaction'):
                    with meto_exp:
                        if not st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            st.text_input(f' Justification for not "{n1[:-11]}"',
                                          key=f'{i[:-11]}_justification')

                if i.endswith('_brkmaction'):
                    with brk_exp:
                        if not st.session_state[f'{i}']:
                            n = i.split(' ')
                            n1 = ' '.join(n[1:])
                            st.text_input(f' Justification for not "{n1[:-11]}"',
                                          key=f'{i[:-11]}_justification')

        # aba de suggest
        with tabs2[3]:
            cl1, cl2 = st.columns(2)
            with cl1:
                st.text_input('Action 1', key='Action 1_contingency')
            with cl2:
                st.text_input('Considerations', key='consideration 1_consider')

            if st.button('Add :heavy_plus_sign:'):
                add_contingency(tabs2[3], cl1, cl2)
            # for i in st.session_state:

    # Aba output
    with tabs[2]:

        if 'r_mandatory' not in st.session_state:
            st.session_state.r_mandatory = 0
        if 'r_suggest' not in st.session_state:
            st.session_state.r_suggest = 0

        t0, t1, output_col1, output_col2, t3 = st.columns((0.7, 0.7, 0.7, 0.4, 0.8))

        total_cp = 0
        total_rb = 0
        for key in st.session_state:
            if key.endswith('_complexity'):
                total_cp += st.session_state[f'{key}']
            if key.endswith('_robustness'):
                total_rb += float(st.session_state[f'{key}'])
        med_complexity = sum(
            1 for cp, value in dict(st.session_state).items() if cp.endswith('_complexity'))

        med_robustness = sum(
            1 for cp, value in dict(st.session_state).items() if cp.endswith('_robustness'))

        st.session_state.global_cp = total_cp / med_complexity
        st.session_state.global_rb = total_rb / med_robustness

        with t0:
            st.session_state.r_suggest, st.session_state.r_mandatory = actions_fallow_up()
            st.markdown('### Actions Fallow-Up')
            st.write(f"{st.session_state.r_mandatory:.1f}% of mandatory")
            st.write(f"{st.session_state.r_suggest:.1f}% of suggest")

        with output_col1:
            fig_ic_global = ic_graph('global_cp', 'global_rb', 'Complexity')
            img_bytes_complexity = io.BytesIO()
            fig_ic_global.write_image(img_bytes_complexity, format='png', scale=2)
            # img_bytes_complexity = fig_ic_global.to_image(format='png', scale=2, engine='kaleido')
            st.plotly_chart(fig_ic_global, use_container_width=False,
                            config={'editable': False, 'displayModeBar': False, "scrollZoom": False})

            st.text_input('Project Complexity', value=f'{st.session_state.global_cp:.2f}', disabled=True,
                          key='Output_general_cp')

            # Criar o gráfico de pizza com Plotly
            labels = ['General', 'Geology', 'Completion', 'Logistic', 'Metocean', 'Braskem']
            values = [float(st.session_state.general_complexity), float(st.session_state.geo_complexity),
                      float(st.session_state.comp_complexity), float(st.session_state.log_complexity),
                      float(st.session_state.meto_complexity), float(st.session_state.brk_complexity)]

            colors_pie = ['#85e043', '#f2a529', '#2bad4e', '#f25829', '#eff229', '#29f2e1', '#6a29f2']

            # Criar o gráfico de pizza com Plotly
            fig_pizza1 = go.Figure(
                data=[go.Pie(labels=labels, values=values, textinfo='label+percent',
                             insidetextorientation='radial', marker=dict(colors=colors_pie))])
            fig_pizza1.update_layout(
                width=300,
                height=300,
                showlegend=False,  # Desativar legendas
                margin=dict(l=0, r=0, t=30, b=0),
                title={
                    'text': "Complexity per area",
                    'y': 1,  # Ajustar a posição vertical do título
                    'x': 0.5,  # Centralizar o título horizontalmente
                    'xanchor': 'center',
                    'yanchor': 'top',
                    'font': {
                        'size': 18  # Aumentar o tamanho da fonte do título
                    }
                }
            )
            img_bytes_pizaa_c = io.BytesIO()
            fig_pizza1.write_image(img_bytes_pizaa_c, format='png', scale=2)
            st.plotly_chart(fig_pizza1, use_container_width=False, config={'editable': False, 'displayModeBar': False,
                                                                           "scrollZoom": False})

        with output_col2:
            st.plotly_chart(fig2, use_container_width=False, config={'editable': False, 'displayModeBar': False,
                                                                     "scrollZoom": False})

        with t1:

            fig_rb_global = ic_graph('global_rb', 'global_rb', 'Robustness')
            img_bytes_r = io.BytesIO()
            fig_rb_global.write_image(img_bytes_r, format='png', scale=2)
            img_bytes_r.seek(0)
            st.plotly_chart(fig_rb_global, use_container_width=False,
                            config={'editable': False, 'displayModeBar': False})
            st.text_input('Project Robustness', value=f'{st.session_state.global_rb:.2f}', disabled=True,
                          key='Outpu_rob')
            labels = ['General', 'Geology', 'Completion', 'Logistic', 'Metocean', 'Braskem']
            values = [float(st.session_state.gen_robustness), float(st.session_state.geo_robustness),
                      float(st.session_state.comp_robustness), float(st.session_state.log_robustness),
                      float(st.session_state.meto_robustness), float(st.session_state.brk_robustness)]

            colors_pie = ['#85e043', '#f2a529', '#2bad4e', '#f25829', '#eff229', '#29f2e1', '#6a29f2']

            # Criar o gráfico de pizza com Plotly
            fig_pizza1 = go.Figure(
                data=[go.Pie(labels=labels, values=values, textinfo='label+percent',
                             insidetextorientation='radial', marker=dict(colors=colors_pie))])

            fig_pizza1.update_layout(
                width=300,
                height=300,
                showlegend=False,  # Desativar legendas
                margin=dict(l=0, r=0, t=30, b=0),
                title={
                    'text': "Robustness per area",
                    'y': 0.98,  # Ajustar a posição vertical do título
                    'x': 0.5,  # Centralizar o título horizontalmente
                    'xanchor': 'center',
                    'yanchor': 'top',
                    'font': {
                        'size': 18  # Aumentar o tamanho da fonte do título
                    }
                },
            )
            st.plotly_chart(fig_pizza1, use_container_width=False, config={'editable': False, 'displayModeBar': False,
                                                                           "scrollZoom": False})
            img_bytes_pizaa_r = io.BytesIO()
            fig_pizza1.write_image(img_bytes_pizaa_r, format='png', scale=2)
            img_bytes_pizza_r = fig_pizza1.to_image(format='png', scale=2, engine='kaleido')
            with open("fig_pizza1.png", "wb") as f:
                f.write(img_bytes_pizza_r)
            img_bytes_pizaa_r.seek(0)

    # Aba report
    with tabs[3]:

        st.session_state.r_suggest, st.session_state.r_mandatory = actions_fallow_up()

        hora_now = datetime.now()

        # Função para gerar o PDF
        def generate_pdf(logo, table_data, geology_data, drilling_data_1, drilling_data_2, drilling_data_3,
                         drilling_data_4, drilling_data_5, completion_data_1, completion_data_2, completion_data_3,
                         completion_data_4,
                         completion_data_5, logistic_data_1, met_data_1):

            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            c.drawImage(logo, 230, height - 100, width=150, height=100)

            c.setFont("Helvetica-Bold", 25)
            c.drawString(200, height - 350, "ARM Final Report")

            c.setFont("Helvetica-Bold", 18)
            well_name = f" {st.session_state.well_name}"

            # Obter a largura do texto
            text_width = c.stringWidth(well_name, "Helvetica-Bold", 20)

            # Calcular a posição X para centralizar o texto
            x_position = (width - text_width) / 2

            # Desenhar o texto na posição calculada
            c.drawString(x_position, height - 375, well_name)

            c.setFont("Helvetica", 12)
            c.line(30, height - 690, width - 30, height - 690)
            c.drawString(40, height - 710, 'Syngular Solutions')
            c.drawString(40, height - 730, 'Houston, TX 77077')
            c.drawString(40, height - 750, 'info@syngularsolutions.com')

            c.showPage()

            c.drawImage(logo, 30, height - 100, width=150, height=100)

            c.setFont("Helvetica", 12)
            c.line(30, height - 100, width - 30, height - 100)
            c.drawString(30, height - 130,
                         f"Report date: {st.session_state.date} @ {hora_now.strftime('%H:%M:%S')}")
            c.drawString(30, height - 150, f"File name: {st.session_state.well_name}")
            c.setFont("Helvetica-Bold", 20)
            c.drawString(30, height - 200, "Actions Follow-Up")
            c.setFont("Helvetica-Bold", 18)
            c.drawString(30, height - 230, f"{st.session_state.r_mandatory:.1f}% of mandatory")
            c.drawString(30, height - 255, f"{st.session_state.r_suggest:.1f}% of recommended")
            c.drawString(30, height - 290, f"Comments")
            img_matrix = ImageReader(img_bytes)
            img_general_complexity = ImageReader(img_bytes_complexity)
            img_robustness = ImageReader(img_bytes_r)
            img_pizza1_robustness = ImageReader(img_bytes_pizaa_r)
            img_pizza1_complexity = ImageReader(img_bytes_pizaa_c)
            c.drawImage(img_matrix, 300, height - 400, width=250, height=250)
            c.drawImage(img_general_complexity, 40, height - 650, width=220, height=220)
            c.drawImage(img_robustness, 340, height - 650, width=220, height=220)
            c.drawImage(img_pizza1_robustness, 360, height - 745, width=180, height=180)
            c.drawImage(img_pizza1_complexity, 60, height - 745, width=180, height=180)
            c.line(30, height - 750, width - 30, height - 750)

            c.showPage()

            if logo:
                c.drawImage(logo, 30, height - 100, width=150, height=100)

            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 110, "Basic Well Info")
            c.setFont("Helvetica", 12)
            c.line(30, height - 130, width - 30, height - 130)
            c.drawString(30, height - 150, f"User Name: {st.session_state.user_name}")
            c.drawString(30, height - 170, f"Well Name: {st.session_state.well_name}")
            c.drawString(30, height - 190, f"Field Name: {st.session_state.field_name}")
            c.drawString(30, height - 210, f"Company Name: {st.session_state.company_name}")
            c.drawString(30, height - 230, f"Country: {st.session_state.country_name}")
            c.drawString(30, height - 250, f"Well Coordinates UTM(m): {st.session_state.coordinate}")
            c.drawString(30, height - 270, f"Datum: {st.session_state.date}")
            # c.drawString(30, height - 290, f"Comments: {st.session_state.comments}")
            comments = st.session_state.comments
            max_length_per_line = 90  # Defina o comprimento máximo por linha conforme necessário
            comment_lines = [comments[i:i + max_length_per_line] for i in
                             range(0, len(comments), max_length_per_line)]
            c.setFont("Helvetica", 12)
            c.drawString(30, height - 290, "Comments:")
            y_position = height - 290
            for line in comment_lines:
                c.drawString(95, y_position, line)
                y_position -= 15
            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 350, "Well Characteristics")
            c.setFont("Helvetica", 12)
            c.line(30, height - 370, width - 30, height - 370)
            c.line(30, height - 750, width - 30, height - 750)

            # Adicionando tabela ao PDF
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.black),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ])

            table = Table(table_data)
            table.setStyle(table_style)

            # Calculate position of the table in the PDF
            table.wrapOn(c, width, height)
            table.drawOn(c, 30, height - 550)

            c.showPage()

            if logo:
                c.drawImage(logo, 30, height - 100, width=150, height=100)

            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 110, "Geology Info")
            c.setFont("Helvetica", 12)
            c.line(30, height - 130, width - 30, height - 130)
            c.line(30, height - 750, width - 30, height - 750)

            # Adicionando tabela de Geologia ao PDF
            geology_table = Table(geology_data)
            geology_table.setStyle(table_style)

            # Calculate position of the table in the PDF
            geology_table.wrapOn(c, width, height)
            geology_table.drawOn(c, 30, height - 380)

            c.showPage()

            if logo:
                c.drawImage(logo, 30, height - 100, width=150, height=100)

            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 110, "Reservoir Info")
            c.setFont("Helvetica", 12)
            c.line(30, height - 130, width - 30, height - 130)
            c.line(30, height - 750, width - 30, height - 750)

            c.showPage()

            if logo:
                c.drawImage(logo, 30, height - 100, width=150, height=100)

            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 110, "Drilling Info")
            c.setFont("Helvetica-Bold", 15)
            c.drawString(30, height - 150, "Well Sections / Geometryo")
            c.setFont("Helvetica-Bold", 15)
            c.drawString(30, height - 340, "Trajectory")
            c.setFont("Helvetica-Bold", 15)
            c.drawString(30, height - 510, "Aquifer")
            c.line(30, height - 130, width - 30, height - 130)
            c.line(30, height - 750, width - 30, height - 750)

            drilling_table = Table(drilling_data_1)
            drilling_table.setStyle(table_style)
            drilling_table.wrapOn(c, width, height)
            drilling_table.drawOn(c, 30, height - 315)

            drilling_table = Table(drilling_data_2)
            drilling_table.setStyle(table_style)
            drilling_table.wrapOn(c, width, height)
            drilling_table.drawOn(c, 30, height - 485)

            drilling_table = Table(drilling_data_3)
            drilling_table.setStyle(table_style)
            drilling_table.wrapOn(c, width, height)
            drilling_table.drawOn(c, 30, height - 565)

            c.showPage()

            if logo:
                c.drawImage(logo, 30, height - 100, width=150, height=100)

            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 110, "Drilling Info")
            c.setFont("Helvetica", 12)
            c.setFont("Helvetica-Bold", 15)
            c.drawString(30, height - 150, "Cement")
            c.setFont("Helvetica-Bold", 15)
            c.drawString(30, height - 270, "Fluid")
            c.line(30, height - 130, width - 30, height - 130)
            c.line(30, height - 750, width - 30, height - 750)

            drilling_table = Table(drilling_data_4)
            drilling_table.setStyle(table_style)
            drilling_table.wrapOn(c, width, height)
            drilling_table.drawOn(c, 30, height - 240)

            drilling_table = Table(drilling_data_5)
            drilling_table.setStyle(table_style)
            drilling_table.wrapOn(c, width, height)
            drilling_table.drawOn(c, 30, height - 380)

            c.showPage()

            if logo:
                c.drawImage(logo, 30, height - 100, width=150, height=100)

            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 110, "Completion Info")
            c.setFont("Helvetica", 12)
            c.setFont("Helvetica-Bold", 15)
            c.drawString(30, height - 150, "Trajectory Within the Reservoir")
            c.setFont("Helvetica-Bold", 15)
            c.drawString(30, height - 250, "Reservoir Well Interface")
            c.setFont("Helvetica-Bold", 15)
            c.drawString(30, height - 365, "Well Simulation")
            c.setFont("Helvetica-Bold", 15)
            c.drawString(30, height - 445, "Artificial Lift")
            c.setFont("Helvetica-Bold", 15)
            c.drawString(30, height - 525, "Production Data")
            c.line(30, height - 130, width - 30, height - 130)
            c.line(30, height - 750, width - 30, height - 750)

            completion_table = Table(completion_data_1)
            completion_table.setStyle(table_style)
            completion_table.wrapOn(c, width, height)
            completion_table.drawOn(c, 30, height - 225)

            completion_table = Table(completion_data_2)
            completion_table.setStyle(table_style)
            completion_table.wrapOn(c, width, height)
            completion_table.drawOn(c, 30, height - 340)

            compl_table = Table(completion_data_3)
            compl_table.setStyle(table_style)
            compl_table.wrapOn(c, width, height)
            compl_table.drawOn(c, 30, height - 420)

            compl_table = Table(completion_data_4)
            compl_table.setStyle(table_style)
            compl_table.wrapOn(c, width, height)
            compl_table.drawOn(c, 30, height - 500)

            compl_table = Table(completion_data_5)
            compl_table.setStyle(table_style)
            compl_table.wrapOn(c, width, height)
            compl_table.drawOn(c, 30, height - 580)

            c.showPage()

            if logo:
                c.drawImage(logo, 30, height - 100, width=150, height=100)

            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 110, "Logistics Info")
            c.setFont("Helvetica", 12)
            c.line(30, height - 130, width - 30, height - 130)
            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 450, "Metocean Info")
            c.setFont("Helvetica", 12)
            c.line(30, height - 460, width - 30, height - 460)
            c.line(30, height - 750, width - 30, height - 750)

            logistic_table = Table(logistic_data_1)
            logistic_table.setStyle(table_style)
            logistic_table.wrapOn(c, width, height)
            logistic_table.drawOn(c, 30, height - 240)

            met_table = Table(met_data_1)
            met_table.setStyle(table_style)
            met_table.wrapOn(c, width, height)
            met_table.drawOn(c, 30, height - 570)

            # Adicionando a página para as ações de Well Info
            show_page = True

            if show_page:
                c.showPage()
                if logo:
                    c.drawImage(logo, 30, height - 100, width=150, height=100)

                c.setFont("Helvetica-Bold", 25)
                c.drawString(30, height - 110, "Well Info Actions")
                c.line(30, height - 130, width - 30, height - 130)
                c.line(30, height - 750, width - 30, height - 750)
                cont = height - 160

                selected_actions = []
                not_selected_actions = []
                selected_actions_s = []
                not_selected_actions_s = []

                for i in st.session_state:
                    if i.endswith('_maction'):
                        if st.session_state[f'{i}']:
                            selected_actions.append(i[:-8])
                        else:
                            not_selected_actions.append(i[:-8])
                for i in st.session_state:
                    if i.endswith('_action'):
                        if st.session_state[f'{i}']:
                            selected_actions_s.append(i[:-8])
                        else:
                            not_selected_actions_s.append(i[:-8])

                if selected_actions:
                    c.setFont("Helvetica", 20)
                    c.drawString(30, cont, "Selected Mandatory Actions")
                    cont -= 20
                    c.setFont("Helvetica", 10)
                    for action in selected_actions:
                        if cont > height - 730:
                            c.drawString(30, cont, action)
                            cont -= 20

                    cont -= 20

                if not_selected_actions:
                    c.setFont("Helvetica", 20)
                    c.drawString(30, cont, "Not Selected Mandatory Actions")
                    cont -= 20
                    c.setFont("Helvetica", 10)
                    for action in not_selected_actions:
                        if cont > height - 730:
                            c.drawString(30, cont, action)
                            cont -= 20

                    cont -= 20

                if selected_actions_s:
                    c.setFont("Helvetica", 20)
                    c.drawString(30, cont, "Selected Suggested Actions")
                    cont -= 20
                    c.setFont("Helvetica", 10)
                    for action in selected_actions_s:
                        if cont > height - 730:
                            c.drawString(30, cont, action)
                            cont -= 20

                    cont -= 20

                if not_selected_actions_s:
                    c.setFont("Helvetica", 20)
                    c.drawString(30, cont, "Not Selected Suggested Actions")
                    cont -= 20
                    c.setFont("Helvetica", 10)
                    for action in not_selected_actions_s:
                        if cont > height - 730:
                            c.drawString(30, cont, action)
                            cont -= 20

            # Página Geology and Reservoir Info Mandatory
            show_page = False

            # Verificar se há ações selecionadas
            for i in st.session_state:
                if i.endswith('_geomaction') and st.session_state[f'{i}']:
                    show_page = True
                    break

            if show_page:
                c.showPage()
                if logo:
                    c.drawImage(logo, 30, height - 100, width=150, height=100)

                c.setFont("Helvetica-Bold", 25)
                c.drawString(30, height - 110, "Geology and Reservoir Actions")
                c.line(30, height - 130, width - 30, height - 130)
                c.line(30, height - 750, width - 30, height - 750)
                cont = height - 160

                for i in st.session_state:
                    if i.endswith('_geomaction') and st.session_state[f'{i}']:
                        if cont > height - 730:
                            c.setFont("Helvetica", 20)
                            c.drawString(30, height - 160, "Selected Mandatory Actions")
                            c.setFont("Helvetica", 10)
                            cont -= 20
                            c.drawString(30, cont, f'{i[8:-11]}')
                        elif cont < height - 730:
                            c.showPage()
                            if logo:
                                c.drawImage(logo, 30, height - 100, width=150, height=100)
                            c.setFont("Helvetica-Bold", 25)
                            c.drawString(30, height - 110, "Geology and Reservoir Actions")
                            c.setFont("Helvetica", 20)
                            c.drawString(30, height - 160, "Selected Mandatory Actions")
                            c.setFont("Helvetica", 10)
                            c.line(30, height - 130, width - 30, height - 130)
                            c.line(30, height - 750, width - 30, height - 750)
                            cont = height - 185
                            c.drawString(30, cont, f'{i[8:-11]}')

            # Página Geology e Reservoir Actions
            show_page = False

            for i in st.session_state:
                if i.endswith('_geomaction') and not st.session_state[f'{i}']:
                    show_page = True
                    break

            if show_page:
                c.showPage()
                if logo:
                    c.drawImage(logo, 30, height - 100, width=150, height=100)

                c.setFont("Helvetica-Bold", 25)
                c.drawString(30, height - 110, "Geology and Reservoir Actions")
                c.line(30, height - 130, width - 30, height - 130)
                c.line(30, height - 750, width - 30, height - 750)
                cont = height - 160

                for i in st.session_state:
                    if i.endswith('_geomaction') and not st.session_state[f'{i}']:
                        if cont > height - 730:
                            c.setFont("Helvetica", 20)
                            c.drawString(30, height - 160, "Not Selected Mandatory Actions")
                            c.setFont("Helvetica", 10)
                            cont -= 20
                            c.drawString(30, cont, f'{i[8:-11]}')
                        elif cont < height - 730:
                            c.showPage()
                            if logo:
                                c.drawImage(logo, 30, height - 100, width=150, height=100)
                            c.setFont("Helvetica-Bold", 25)
                            c.drawString(30, height - 110, "Geology and Reservoir Actions")
                            c.setFont("Helvetica", 20)
                            c.drawString(30, height - 160, "Not Selected Mandatory Actions")
                            c.setFont("Helvetica", 10)
                            c.line(30, height - 130, width - 30, height - 130)
                            c.line(30, height - 750, width - 30, height - 750)
                            cont = height - 185
                            c.drawString(50, cont, f'{i[8:-11]}')

            # Página Geology and Reservoir Info Suggested
            show_page = False

            # Verificar se há ações selecionadas ou não
            for i in st.session_state:
                if i.endswith('_geosaction'):
                    show_page = True
                    break

            if show_page:
                c.showPage()
                if logo:
                    c.drawImage(logo, 30, height - 100, width=150, height=100)

                c.setFont("Helvetica-Bold", 25)
                c.drawString(30, height - 110, "Geology and Reservoir Actions")
                c.line(30, height - 130, width - 30, height - 130)
                c.line(30, height - 750, width - 30, height - 750)
                cont = height - 160

                selected_actions = []
                not_selected_actions = []

                for i in st.session_state:
                    if i.endswith('_geosaction'):
                        if st.session_state[f'{i}']:
                            selected_actions.append(i[8:-11])
                        else:
                            not_selected_actions.append(i[8:-11])

                if selected_actions:
                    c.setFont("Helvetica", 20)
                    c.drawString(30, cont, "Selected Suggested Actions")
                    cont -= 20
                    c.setFont("Helvetica", 10)
                    for action in selected_actions:
                        if cont > height - 730:
                            c.drawString(30, cont, action)
                            cont -= 20

                    cont -= 20  # Mudança: Adicionado espaço extra entre as seções

                if not_selected_actions:
                    c.setFont("Helvetica", 20)
                    c.drawString(30, cont, "Not Selected Suggested Actions")
                    cont -= 20
                    c.setFont("Helvetica", 10)
                    for action in not_selected_actions:
                        if cont > height - 730:
                            c.drawString(30, cont, action)
                            cont -= 20

            # Página Drilling Actions
            show_page = False

            # Verificar se há ações selecionadas
            for i in st.session_state:
                if i.endswith('_drillmaction') and st.session_state[f'{i}']:
                    show_page = True
                    break

            if show_page:
                c.showPage()
                if logo:
                    c.drawImage(logo, 30, height - 100, width=150, height=100)

                c.setFont("Helvetica-Bold", 25)
                c.drawString(30, height - 110, "Drilling Actions")
                c.line(30, height - 130, width - 30, height - 130)
                c.line(30, height - 750, width - 30, height - 750)
                cont = height - 160

                for i in st.session_state:
                    if i.endswith('_drillmaction') and st.session_state[f'{i}']:
                        if cont > height - 730:
                            c.setFont("Helvetica", 20)
                            c.drawString(30, height - 160, "Selected Mandatory Actions")
                            c.setFont("Helvetica", 10)
                            cont -= 20
                            c.drawString(30, cont, f'{i[8:-13]}')
                        elif cont < height - 730:
                            c.showPage()
                            if logo:
                                c.drawImage(logo, 30, height - 100, width=150, height=100)
                            c.setFont("Helvetica-Bold", 25)
                            c.drawString(30, height - 110, "Drilling Actions")
                            c.setFont("Helvetica", 20)
                            c.drawString(30, height - 160, "Selected Mandatory Actions")
                            c.setFont("Helvetica", 10)
                            c.line(30, height - 130, width - 30, height - 130)
                            c.line(30, height - 750, width - 30, height - 750)
                            cont = height - 185
                            c.drawString(30, cont, f'{i[8:-13]}')

            # Página Drilling Actions
            show_page = False

            for i in st.session_state:
                if i.endswith('_drillmaction') and not st.session_state[f'{i}']:
                    show_page = True
                    break

            if show_page:
                c.showPage()
                if logo:
                    c.drawImage(logo, 30, height - 100, width=150, height=100)

                c.setFont("Helvetica-Bold", 25)
                c.drawString(30, height - 110, "Drilling Actions")
                c.line(30, height - 130, width - 30, height - 130)
                c.line(30, height - 750, width - 30, height - 750)
                cont = height - 160

                for i in st.session_state:
                    if i.endswith('_drillmaction') and not st.session_state[f'{i}']:
                        if cont > height - 730:
                            c.setFont("Helvetica", 20)
                            c.drawString(30, height - 160, "Not Selected Mandatory Actions")
                            c.setFont("Helvetica", 10)
                            cont -= 20
                            c.drawString(30, cont, f'{i[8:-13]}')
                        elif cont < height - 730:
                            c.showPage()
                            if logo:
                                c.drawImage(logo, 30, height - 100, width=150, height=100)
                            c.setFont("Helvetica-Bold", 25)
                            c.drawString(30, height - 110, "Drilling Actions")
                            c.setFont("Helvetica", 20)
                            c.drawString(30, height - 160, "Not Selected Mandatory Actions")
                            c.setFont("Helvetica", 10)
                            c.line(30, height - 130, width - 30, height - 130)
                            c.line(30, height - 750, width - 30, height - 750)
                            cont = height - 185
                            c.drawString(50, cont, f'{i[8:-13]}')

            # Página Drilling Actions
            show_page = False

            # Verificar se há ações selecionadas ou não
            for i in st.session_state:
                if i.endswith('_drillsaction'):
                    show_page = True
                    break

            if show_page:
                c.showPage()
                if logo:
                    c.drawImage(logo, 30, height - 100, width=150, height=100)

                c.setFont("Helvetica-Bold", 25)
                c.drawString(30, height - 110, "Drilling Actions")
                c.line(30, height - 130, width - 30, height - 130)
                c.line(30, height - 750, width - 30, height - 750)
                cont = height - 160

                selected_actions = []
                not_selected_actions = []

                for i in st.session_state:
                    if i.endswith('_drillsaction'):
                        if st.session_state[f'{i}']:
                            selected_actions.append(i[8:-13])
                        else:
                            not_selected_actions.append(i[8:-13])

                if selected_actions:
                    c.setFont("Helvetica", 20)
                    c.drawString(30, cont, "Selected Suggested Actions")
                    cont -= 20
                    c.setFont("Helvetica", 10)
                    for action in selected_actions:
                        if cont > height - 730:
                            c.drawString(30, cont, action)
                            cont -= 20

                    cont -= 20  # Mudança: Adicionado espaço extra entre as seções

                if not_selected_actions:
                    c.setFont("Helvetica", 20)
                    c.drawString(30, cont, "Not Selected Suggested Actions")
                    cont -= 20
                    c.setFont("Helvetica", 10)
                    for action in not_selected_actions:
                        if cont > height - 730:
                            c.drawString(30, cont, action)
                            cont -= 20

            # Adicionando a página para as ações de Completion
            c.showPage()
            if logo:
                c.drawImage(logo, 30, height - 100, width=150, height=100)

            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 110, "Completion Info Actions")
            c.line(30, height - 130, width - 30, height - 130)
            c.line(30, height - 750, width - 30, height - 750)
            cont = height - 160

            selected_actions = []
            not_selected_actions = []
            selected_actions_s = []
            not_selected_actions_s = []

            for i in st.session_state:
                if i.endswith('_compmaction'):
                    if st.session_state[f'{i}']:
                        selected_actions.append(i)
                    else:
                        not_selected_actions.append(i)
            for i in st.session_state:
                if i.endswith('_compsaction'):
                    if st.session_state[f'{i}']:
                        selected_actions_s.append(i)
                    else:
                        not_selected_actions_s.append(i)

            if selected_actions:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Selected Mandatory Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in selected_actions:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

                cont -= 20

            if not_selected_actions:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Not Selected Mandatory Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in not_selected_actions:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

                cont -= 20

            if selected_actions_s:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Selected Suggested Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in selected_actions_s:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

                cont -= 20

            if not_selected_actions_s:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Not Selected Suggested Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in not_selected_actions_s:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

            # Adicionando a página para as ações de Logistic Info
            c.showPage()
            if logo:
                c.drawImage(logo, 30, height - 100, width=150, height=100)

            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 110, "Logistic Info Actions")
            c.line(30, height - 130, width - 30, height - 130)
            c.line(30, height - 750, width - 30, height - 750)
            cont = height - 160

            selected_actions = []
            not_selected_actions = []
            selected_actions_s = []
            not_selected_actions_s = []

            for i in st.session_state:
                if i.endswith('_logmaction'):
                    if st.session_state[f'{i}']:
                        selected_actions.append(i)
                    else:
                        not_selected_actions.append(i)
            for i in st.session_state:
                if i.endswith('_logsaction'):
                    if st.session_state[f'{i}']:
                        selected_actions_s.append(i)
                    else:
                        not_selected_actions_s.append(i)

            if selected_actions:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Selected Mandatory Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in selected_actions:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

                cont -= 20

            if not_selected_actions:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Not Selected Mandatory Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in not_selected_actions:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

                cont -= 20

            if selected_actions_s:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Selected Suggested Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in selected_actions_s:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

                cont -= 20

            if not_selected_actions_s:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Not Selected Suggested Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in not_selected_actions_s:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

            # Adicionando a página para as ações de Metocean Info
            c.showPage()
            if logo:
                c.drawImage(logo, 30, height - 100, width=150, height=100)

            c.setFont("Helvetica-Bold", 25)
            c.drawString(30, height - 110, "Metocean Info Actions")
            c.line(30, height - 130, width - 30, height - 130)
            c.line(30, height - 750, width - 30, height - 750)
            cont = height - 160

            selected_actions = []
            not_selected_actions = []
            selected_actions_s = []
            not_selected_actions_s = []

            for i in st.session_state:
                if i.endswith('_metomaction'):
                    if st.session_state[f'{i}']:
                        selected_actions.append(i[9:-12])
                    else:
                        not_selected_actions.append(i[9:-12])
            for i in st.session_state:
                if i.endswith('_metosaction'):
                    if st.session_state[f'{i}']:
                        selected_actions_s.append(i[9:-12])
                    else:
                        not_selected_actions_s.append(i[9:-12])

            if selected_actions:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Selected Mandatory Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in selected_actions:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

                cont -= 20

            if not_selected_actions:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Not Selected Mandatory Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in not_selected_actions:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

                cont -= 20

            if selected_actions_s:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Selected Suggested Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in selected_actions_s:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

                cont -= 20

            if not_selected_actions_s:
                c.setFont("Helvetica", 20)
                c.drawString(30, cont, "Not Selected Suggested Actions")
                cont -= 20
                c.setFont("Helvetica", 10)
                for action in not_selected_actions_s:
                    if cont > height - 730:
                        c.drawString(30, cont, action)
                        cont -= 20

            c.showPage()
            c.save()
            buffer.seek(0)
            return buffer

            # Dados para a tabela

        data = {
            "Item": ["Well Type", "Rig Type", "Rig Status", "Correlation Wells", "Data Quality and Confiability",
                     "Learning Curve"],
            "Selection": [well_type, rig_type, st.session_state.rig_status, st.session_state.Correlation_wells,
                          st.session_state.Data_quality,
                          st.session_state.Learning_curve],
        }

        # Adiciona as seleções e pontuações adicionais para "Relief Well" e "Onshore"
        if well_type == 'Relief Well':
            data["Item"].append("Open Flow Potential (bpd)")
            data["Selection"].append(st.session_state.fp)

        if rig_type != 'Onshore':
            data["Item"].append("Water Depth (ft)")
            data["Selection"].append(st.session_state.wd)

        # Criando um DataFrame com os dados
        df = pd.DataFrame(data)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        table_data = [df.columns.tolist()] + df.values.tolist()
        st.session_state.formation_drill = 'xx'

        # Dados para a tabela "Geology Info"
        geology_data = {
            "Item": ["Shallow Hazard Risk", "H2S Content (ppm)", "CO2 Content (%)",
                     "Maximum Wellhead Pressure (psi)",
                     "Minimum Operational Mud Weight Window (ppg)", "Maximum Bottomhole Temperature (°F)",
                     "Tectonic Effect",
                     "Salt Formation", "Formations Pressure To Be Drilled", "Stress State Knowledge",
                     "Expected Formation Fluid", "Formations To Be Drilled"],
            "Selection": [st.session_state.shallow_hazard, st.session_state.h2s_content,
                          st.session_state.co2_content,
                          st.session_state.max_wellhead, st.session_state.op_window,
                          st.session_state.max_bottom_hole,
                          st.session_state.tec_effect, st.session_state.salt_formation,
                          st.session_state.formation_drill, st.session_state.stress_state,
                          st.session_state.expected_fluid, selected_formations_str],
        }

        # Criando um DataFrame com os dados de geologia
        df_geology = pd.DataFrame(geology_data)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        geology_table_data = [df_geology.columns.tolist()] + df_geology.values.tolist()

        # Dados para a tabela "Drilling Info Well Sections / Geometry"

        drilling_data_1 = {
            "Item": ["Total Depth (m)", "Total Vertical Depth (m)", "Well Alignment", "Maximum Number of Phases",
                     "Number of Hole Enlargements", "Slim Hole (<6,5 in)", "Minimum Hole Diameter (inch)"],
            "Selection": [st.session_state.total_depth, st.session_state.total_tvd,
                          st.session_state.well_alignment,
                          st.session_state.number_phases, st.session_state.hole_enlargements,
                          st.session_state.slim_hole,
                          st.session_state.min_hole_diameter],
        }

        # Criando um DataFrame com os dados de perfuração
        df_drilling = pd.DataFrame(drilling_data_1)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        drilling_1_table_data = [df_drilling.columns.tolist()] + df_drilling.values.tolist()

        # Dados para a tabela "Drilling Info Trajectory"

        drilling_data_2 = {
            "Item": ["Vertical Well", "Slant Sec Maximum Inclination (°)", "Maximum Lateral Displacement (ft)",
                     "Complex Trajectory Planned", "Maximum Dogleg (°/100ft)"],

            "Selection": [st.session_state.vertical_well, st.session_state.max_inclination,
                          st.session_state.max_lateral_displacement,
                          st.session_state.complex_trajectory_planned, st.session_state.max_dogleg],
        }

        # Criando um DataFrame com os dados de perfuração
        df_drilling = pd.DataFrame(drilling_data_2)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        drilling_2_table_data = [df_drilling.columns.tolist()] + df_drilling.values.tolist()

        # Dados para a tabela "Aquifer"

        drilling_data_3 = {
            "Item": ["Type of Aquifer (Environmental Issues)"],
            "Selection": [st.session_state.type_aquifer],
        }

        # Criando um DataFrame com os dados de perfuração
        df_drilling = pd.DataFrame(drilling_data_3)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        drilling_3_table_data = [df_drilling.columns.tolist()] + df_drilling.values.tolist()

        # Dados para a tabela "Cement"

        drilling_data_4 = {
            "Item": ["Longest Cement Interval (ft)", "Casing Type", "Non-shear Casing"],
            "Selection": [st.session_state.cement_interval, st.session_state.casing_type,
                          st.session_state.non_shear_casing],
        }

        # Criando um DataFrame com os dados de perfuração
        df_drilling = pd.DataFrame(drilling_data_4)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        drilling_4_table_data = [df_drilling.columns.tolist()] + df_drilling.values.tolist()

        # Dados para a tabela "Fluid"


        drilling_data_5 = {
            "Item": ["Driling Fluid", "Maximum Driling Fluid Density (ppg)", "Lost Circulation"],
            "Selection": [st.session_state.drilling_fluid, st.session_state.fluid_density,
                          st.session_state.lost_circulation],
        }

        # Criando um DataFrame com os dados de perfuração
        df_drilling = pd.DataFrame(drilling_data_5)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        drilling_5_table_data = [df_drilling.columns.tolist()] + df_drilling.values.tolist()

        # Dados para a tabela "Trajectory Within the Reservoir"

        completion_data_1 = {
            "Item": ["Inclination (°)", "Length (ft)"],
            "Selection": [st.session_state.res_inclination, st.session_state.res_length],
        }

        # Criando um DataFrame com os dados de perfuração
        df_completion = pd.DataFrame(completion_data_1)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        completion_1_table_data = [df_completion.columns.tolist()] + df_completion.values.tolist()

        # Dados para a tabela "Trajectory Within the Reservoir"

        completion_data_2 = {
            "Item": ["Production Casing ", "Multizone Completion", "Reservoir with Pressure Contrast"],
            "Selection": [st.session_state.production_casing, st.session_state.multizone_completion,
                          st.session_state.pressure_contrast],
        }

        # Criando um DataFrame com os dados de perfuração
        df_completion = pd.DataFrame(completion_data_2)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        completion_2_table_data = [df_completion.columns.tolist()] + df_completion.values.tolist()

        # Dados para a tabela "Well Simulation"

        completion_data_3 = {
            "Item": [st.session_state.frat_type],
            "Selection": [st.session_state.fracturing],
        }

        # Criando um DataFrame com os dados de perfuração
        df_completion = pd.DataFrame(completion_data_3)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        completion_3_table_data = [df_completion.columns.tolist()] + df_completion.values.tolist()

        # Dados para a tabela "Artificial Lift"

        completion_data_4 = {
            "Item": ["Artificial Lift"],
            "Selection": [st.session_state.artificial_lift],
        }

        # Criando um DataFrame com os dados de perfuração
        df_completion = pd.DataFrame(completion_data_4)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        completion_4_table_data = [df_completion.columns.tolist()] + df_completion.values.tolist()

        # Dados para a tabela "Production Data"

        completion_data_5 = {
            "Item": ["Production Data"],
            "Selection": [st.session_state.production_data],
        }

        # Criando um DataFrame com os dados de perfuração
        df_completion = pd.DataFrame(completion_data_5)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        completion_5_table_data = [df_completion.columns.tolist()] + df_completion.values.tolist()

        # Dados para a tabela "Logistic"

        logistic_data_1 = {
            "Item": ["Operational Support", "Fluids and Cuts Disposal", "Distance to Operation Base (mi)",
                     "Distance to Warehouse (mi)"],
            "Selection": [st.session_state.op_support, st.session_state.fluid_disposal,
                          st.session_state.distance_base,
                          st.session_state.distance_warehouse],
        }

        # Criando um DataFrame com os dados de perfuração
        df_logistic = pd.DataFrame(logistic_data_1)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        logistic_1_table_data = [df_logistic.columns.tolist()] + df_logistic.values.tolist()

        # Dados para a tabela "Metocean"

        met_data_1 = {
            "Item": ["Sea Current (knots)", "Waves Height (ft)", "Wind Speed (knots)"],
            "Selection": [st.session_state.sea_current, st.session_state.wave_h, st.session_state.wind_speed],
        }

        # Criando um DataFrame com os dados de perfuração
        df_met = pd.DataFrame(met_data_1)

        # Convertendo os dados do DataFrame em uma lista de listas para a tabela do PDF
        met_1_table_data = [df_met.columns.tolist()] + df_met.values.tolist()

        # Função para converter PDF para base64
        def pdf_to_base64(pdf_buffer):
            pdf_bytes = pdf_buffer.getvalue()
            encoded_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            return encoded_pdf

        st.title("ARM Reports")

        # Gerar o PDF
        pdf_buffer = generate_pdf(logo, table_data, geology_table_data, drilling_1_table_data,
                                  drilling_2_table_data,
                                  drilling_3_table_data,
                                  drilling_4_table_data, drilling_5_table_data, completion_1_table_data,
                                  completion_2_table_data, completion_3_table_data,
                                  completion_4_table_data, completion_5_table_data, logistic_1_table_data,
                                  met_1_table_data)
        # Nome do arquivo PDF
        pdf_file_name = f"Well_Report_{st.session_state.well_name}.pdf"

        col1, col2 = st.columns((0.3, 1))

        with col1:
            st.download_button(
                label="⬇️ Download PDF",
                data=pdf_buffer,
                file_name=pdf_file_name,
                mime="application/pdf"
            )

        with col2:
            pdf_base64 = pdf_to_base64(pdf_buffer)
            pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_base64}" width="870" height="800" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)


# Página Settings
def settings_page():
    pass


# Página de contatos da empresa
def contact_page():
    # query['Access'] = 'Contact'
    st.title('Contact Us')
    st.markdown('---')
    st.markdown('Syngular Solutions')
    st.markdown('Houston, TX 77077')
    st.markdown('info@syngularsolutions.com')


# Página de informações do usuário
def my_account():
    st.title('User information')
    st.markdown('---')

menu_option = ["Home", "ARM", "Settings", "Contact Us", "My Account"]
menu_icons = ["house", "list-task", "gear", "envelope", "person-circle"]

# Criando menu principal
selected = option_menu(
    menu_title=None,  # required
    options=menu_option,  # required
    icons=menu_icons,  # optional
    menu_icon="cast",  # optional
    default_index=0,  # optional
    orientation="horizontal",
    key='option_menu'
)

# Condições para entrar em cada página do site
if selected == 'Home':
    home_page()

elif selected == 'ARM':
    arm_page()

elif selected == 'Settings':
    settings_page()

elif selected == 'Contact Us':
    contact_page()

elif selected == 'My Account':
    my_account()

# Define o JavaScript
my_js = """
window.onbeforeunload = function(event) {
    event.preventDefault();
    event.returnValue = '';
    alert("If you reload the page, your information may be lost.");
};
"""

# Empacota o JavaScript como código HTML
my_html = f"<script>{my_js}</script>"

html(my_html)


