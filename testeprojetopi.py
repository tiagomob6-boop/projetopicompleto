import streamlit as st        # Framework para criar o site interativo
import pandas as pd           # Manipulação de tabelas de dados
import numpy as np            # Cálculos numéricos
import os                     # Acesso a arquivos do sistema
import sqlite3                # Banco de dados local (sem precisar instalar nada extra)
import hashlib                # Para criptografar senhas com SHA-25
from datetime import datetime, date  # Trabalhar com datas e horários

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA (deve ser o primeiro comando Streamlit do arquivo)
# ==============================================================================
st.set_page_config(
    page_title="Sistema Nutricional",
    page_icon="🥗",
    layout="wide"
)

# CSS customizado para deixar a tela de login mais bonita
st.markdown("""
<style>
    /* Cartão centralizado na tela de login */
    .login-card {
        background: #f8f9fa;
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    }
    /* Cor de destaque nos títulos */
    .titulo-verde {
        color: #2e7d32;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# SEÇÃO 1 — BANCO DE DADOS (SQLite)
# Todas as funções que criam, lêem e escrevem no banco nutricional.db
# ==============================================================================

def init_database():
    """
    Cria o arquivo 'nutricional.db' e todas as tabelas necessárias,
    caso ainda não existam. É chamada uma vez ao iniciar o app.
    """
    conn = sqlite3.connect('nutricional.db')
    cursor = conn.cursor()

    # ----- Tabela de usuários -----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,   -- Nome de usuário único
            email         TEXT    UNIQUE NOT NULL,   -- E-mail único
            senha_hash    TEXT    NOT NULL,          -- Senha criptografada (SHA-256)
            data_cadastro TEXT    NOT NULL           -- Data/hora do cadastro
        )
    ''')

    # ----- Tabela de refeições (cabeçalho) -----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS refeicoes (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,        -- Dono da refeição
            data             TEXT    NOT NULL,         -- Data escolhida pelo usuário (YYYY-MM-DD)
            nome_refeicao    TEXT,                    -- Ex: "Almoço", "Café da manhã"
            total_kcal       REAL,                    -- Totais calculados
            total_proteina   REAL,
            total_carboidrato REAL,
            total_gordura    REAL,
            total_fibra      REAL,
            data_registro    TEXT    NOT NULL,         -- Momento em que foi salva
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )
    ''')

    # ----- Tabela de itens de cada refeição (detalhe) -----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itens_refeicao (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            refeicao_id  INTEGER NOT NULL,             -- Refeição à qual pertence
            alimento     TEXT    NOT NULL,
            quantidade   REAL,
            unidade      TEXT,                        -- 'g' ou 'ml'
            kcal         REAL,
            proteina     REAL,
            carboidrato  REAL,
            gordura      REAL,
            fibra        REAL,
            categoria    TEXT,                        -- 'Comida' ou 'Bebida'
            FOREIGN KEY (refeicao_id) REFERENCES refeicoes(id)
        )
    ''')

    conn.commit()
    conn.close()


# ---- Funções auxiliares de segurança ----

def hash_senha(senha: str) -> str:
    """Retorna o hash SHA-256 da senha em hexadecimal."""
    return hashlib.sha256(senha.encode('utf-8')).hexdigest()


# ---- Funções de usuário ----

def cadastrar_usuario(username: str, email: str, senha: str):
    """
    Insere um novo usuário no banco.
    Retorna (True, mensagem) em caso de sucesso ou (False, erro) em falha.
    """
    try:
        conn = sqlite3.connect('nutricional.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO usuarios (username, email, senha_hash, data_cadastro) VALUES (?, ?, ?, ?)',
            (username.strip(), email.strip().lower(), hash_senha(senha),
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        conn.close()
        return True, "✅ Cadastro realizado com sucesso! Faça login para continuar."

    except sqlite3.IntegrityError as e:
        # Identifica qual campo já existe
        msg = "Nome de usuário já existe!" if 'username' in str(e) else "E-mail já cadastrado!"
        return False, f"❌ {msg}"
    except Exception as e:
        return False, f"❌ Erro inesperado: {e}"


def fazer_login(username: str, senha: str):
    """
    Verifica credenciais.
    Retorna (True, dict_usuario) ou (False, None).
    """
    try:
        conn = sqlite3.connect('nutricional.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, username, email FROM usuarios WHERE username = ? AND senha_hash = ?',
            (username.strip(), hash_senha(senha))
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return True, {'id': row[0], 'username': row[1], 'email': row[2]}
        return False, None
    except Exception:
        return False, None


# ---- Funções de refeição ----

def salvar_refeicao(user_id: int, data_refeicao: str, nome_refeicao: str,
                    lista_alimentos: list, totais: dict):
    """
    Persiste uma refeição completa (cabeçalho + itens) no SQLite.
    Retorna (True, mensagem) ou (False, erro).
    """
    try:
        conn = sqlite3.connect('nutricional.db')
        cursor = conn.cursor()

        # 1. Insere o cabeçalho da refeição
        cursor.execute('''
            INSERT INTO refeicoes
                (user_id, data, nome_refeicao, total_kcal, total_proteina,
                 total_carboidrato, total_gordura, total_fibra, data_registro)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, data_refeicao, nome_refeicao,
              totais['kcal'], totais['proteina'], totais['carboidrato'],
              totais['gordura'], totais['fibra'],
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        refeicao_id = cursor.lastrowid  # ID gerado para usar nos itens

        # 2. Insere cada alimento/bebida da lista
        for item in lista_alimentos:
            cursor.execute('''
                INSERT INTO itens_refeicao
                    (refeicao_id, alimento, quantidade, unidade,
                     kcal, proteina, carboidrato, gordura, fibra, categoria)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (refeicao_id, item['alimento'], item['quantidade'], item['unidade'],
                  item['kcal'], item['proteina'], item['carboidrato'],
                  item['gordura'], item['fibra'], item['categoria']))

        conn.commit()
        conn.close()
        return True, "✅ Refeição salva no histórico com sucesso!"

    except Exception as e:
        return False, f"❌ Erro ao salvar: {e}"


def buscar_historico(user_id: int, data_inicio=None, data_fim=None):
    """
    Retorna lista de refeições do usuário, opcionalmente filtradas por período.
    Cada linha é uma tupla:
      (id, data, nome_refeicao, total_kcal, total_proteina,
       total_carboidrato, total_gordura, total_fibra, data_registro)
    """
    try:
        conn = sqlite3.connect('nutricional.db')
        cursor = conn.cursor()

        query = '''
            SELECT id, data, nome_refeicao, total_kcal, total_proteina,
                   total_carboidrato, total_gordura, total_fibra, data_registro
            FROM refeicoes
            WHERE user_id = ?
        '''
        params = [user_id]

        # Filtros opcionais de data
        if data_inicio:
            query += ' AND data >= ?'
            params.append(str(data_inicio))
        if data_fim:
            query += ' AND data <= ?'
            params.append(str(data_fim))

        query += ' ORDER BY data DESC, data_registro DESC'

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def buscar_itens_refeicao(refeicao_id: int):
    """
    Retorna os itens de uma refeição específica.
    Cada linha: (alimento, quantidade, unidade, kcal, proteina,
                 carboidrato, gordura, fibra, categoria)
    """
    try:
        conn = sqlite3.connect('nutricional.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT alimento, quantidade, unidade, kcal, proteina,
                   carboidrato, gordura, fibra, categoria
            FROM itens_refeicao
            WHERE refeicao_id = ?
        ''', (refeicao_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def deletar_refeicao(refeicao_id: int) -> bool:
    """Remove uma refeição e todos os seus itens do banco."""
    try:
        conn = sqlite3.connect('nutricional.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM itens_refeicao WHERE refeicao_id = ?', (refeicao_id,))
        cursor.execute('DELETE FROM refeicoes WHERE id = ?', (refeicao_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# ==============================================================================
# SEÇÃO 2 — TELA DE LOGIN / CADASTRO
# Exibida ANTES do app principal quando o usuário não está autenticado
# ==============================================================================

def tela_login():
    """
    Página de autenticação com duas abas: Login e Cadastro.
    Quando o login é bem-sucedido, salva o usuário em session_state
    e o app principal é liberado via st.rerun().
    """
    # Logo / cabeçalho centralizado
    col_c, col_m, col_d = st.columns([1, 2, 1])
    with col_m:
        st.markdown("## 🥗 Sistema Nutricional")
        st.markdown("##### Seu assistente de alimentação saudável")
        st.markdown("---")

        # Abas de Login e Cadastro
        aba_login, aba_cadastro = st.tabs(["🔑 Entrar", "📝 Criar Conta"])

        # ===== ABA DE LOGIN =====
        with aba_login:
            st.markdown("### Acesse sua conta")

            username_login = st.text_input(
                "Nome de usuário", key="login_user",
                placeholder="seu_usuario"
            )
            senha_login = st.text_input(
                "Senha", type="password", key="login_pass",
                placeholder="••••••••"
            )

            col_btn, _ = st.columns([1, 1])
            with col_btn:
                if st.button("🚀 Entrar", use_container_width=True, type="primary"):
                    if not username_login or not senha_login:
                        st.warning("⚠️ Preencha usuário e senha.")
                    else:
                        ok, usuario = fazer_login(username_login, senha_login)
                        if ok:
                            # Salva dados do usuário na sessão
                            st.session_state.usuario_logado = usuario
                            st.success(f"Bem-vindo(a), {usuario['username']}! 👋")
                            st.rerun()   # Recarrega o app já autenticado
                        else:
                            st.error("❌ Usuário ou senha incorretos.")

        # ===== ABA DE CADASTRO =====
        with aba_cadastro:
            st.markdown("### Crie sua conta gratuita")

            novo_username = st.text_input(
                "Nome de usuário", key="cad_user",
                placeholder="escolha um nome único"
            )
            novo_email = st.text_input(
                "E-mail", key="cad_email",
                placeholder="seu@email.com"
            )
            nova_senha = st.text_input(
                "Senha (mín. 6 caracteres)", type="password",
                key="cad_pass", placeholder="••••••••"
            )
            confirma_senha = st.text_input(
                "Confirme a senha", type="password",
                key="cad_pass2", placeholder="••••••••"
            )

            if st.button("✅ Criar Conta", use_container_width=True, type="primary"):
                # Validações básicas antes de gravar no banco
                if not all([novo_username, novo_email, nova_senha, confirma_senha]):
                    st.warning("⚠️ Preencha todos os campos.")
                elif len(nova_senha) < 6:
                    st.error("❌ A senha deve ter pelo menos 6 caracteres.")
                elif nova_senha != confirma_senha:
                    st.error("❌ As senhas não coincidem.")
                elif "@" not in novo_email:
                    st.error("❌ E-mail inválido.")
                else:
                    ok, msg = cadastrar_usuario(novo_username, novo_email, nova_senha)
                    if ok:
                        st.success(msg)
                        st.info("Agora acesse a aba **Entrar** para fazer login.")
                    else:
                        st.error(msg)


# ==============================================================================
# SEÇÃO 3 — INICIALIZAÇÃO DO SESSION STATE
# Garante que todas as variáveis globais existam antes de usar
# ==============================================================================

def init_session_state():
    """Inicializa variáveis da sessão (executada uma vez por sessão)."""

    defaults = {
        'usuario_logado':        None,   # Dict com dados do usuário autenticado
        'tdee_usuario':          0,      # Gasto calórico diário calculado
        'total_kcal':            0.0,    # Acumuladores da refeição atual
        'total_proteina':        0.0,
        'total_carboidrato':     0.0,
        'total_gordura':         0.0,
        'total_fibra':           0.0,
        'lista_alimentos':       [],     # Itens adicionados à refeição
        'data_refeicao':         date.today(),  # Data selecionada pelo usuário
        'nome_refeicao':         'Almoço',      # Nome padrão da refeição
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


# ==============================================================================
# SEÇÃO 4 — CARREGAMENTO DOS DADOS NUTRICIONAIS (CSV + Excel)
# ==============================================================================

@st.cache_data  # Cache: só recarrega quando o arquivo mudar
def carregar_dados():
    """
    Lê Tabela_Alimentos_Original.csv e tabela_bebidas.xlsx,
    padroniza colunas e retorna um único DataFrame combinado.
    """
    dataframes = []

    # ----- COMIDAS (CSV) -----
    try:
        if os.path.exists("Tabela_Alimentos_Original.csv"):
            df_comidas = pd.read_csv(
                "Tabela_Alimentos_Original.csv", sep=";", encoding="latin1"
            )
            df_comidas.columns = df_comidas.columns.str.strip()
            df_comidas['Alimento'] = df_comidas['Alimento'].str.strip()
            df_comidas['Categoria'] = 'Comida'
            df_comidas['Unidade'] = 'g'
            dataframes.append(df_comidas)
            st.sidebar.success(f"✅ Comidas carregadas: {len(df_comidas)} itens")
        else:
            st.sidebar.warning("⚠️ Tabela_Alimentos_Original.csv não encontrado")
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar comidas: {e}")

    # ----- BEBIDAS (Excel) -----
    try:
        if os.path.exists("tabela_bebidas.xlsx"):
            df_bebidas = pd.read_excel("tabela_bebidas.xlsx")
            df_bebidas.columns = df_bebidas.columns.str.strip()

            # Tenta renomear a coluna de nome das bebidas para 'Alimento'
            for col in df_bebidas.columns:
                if 'bebida' in col.lower():
                    df_bebidas = df_bebidas.rename(columns={col: 'Alimento'})
                    break

            # Mapeamento de possíveis nomes de colunas nutricionais → nome padrão
            mapa_colunas = {
                'Calorias (kcal)':    ['kcal', 'caloria', 'energia', 'cal'],
                'Proteínas (g)':      ['proteína', 'proteina', 'prot', 'protein'],
                'Carboidratos (g)':   ['carboidrato', 'carb', 'carbo'],
                'Fibras (g)':         ['fibra', 'fibras', 'fiber'],
                'Gorduras (g)':       ['gordura', 'gord', 'lipídio', 'lipideo'],
            }
            for coluna_padrao, aliases in mapa_colunas.items():
                for col in df_bebidas.columns:
                    if any(alias in col.lower() for alias in aliases):
                        df_bebidas = df_bebidas.rename(columns={col: coluna_padrao})
                        break

            df_bebidas['Alimento']  = df_bebidas['Alimento'].astype(str).str.strip()
            df_bebidas['Categoria'] = 'Bebida'
            df_bebidas['Unidade']   = 'ml'

            # Garante que colunas obrigatórias existam
            for col in ['Calorias (kcal)', 'Proteínas (g)', 'Carboidratos (g)',
                        'Fibras (g)', 'Gorduras (g)']:
                if col not in df_bebidas.columns:
                    df_bebidas[col] = 0

            dataframes.append(df_bebidas)
            st.sidebar.success(f"✅ Bebidas carregadas: {len(df_bebidas)} itens")
        else:
            st.sidebar.warning("⚠️ tabela_bebidas.xlsx não encontrado")
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar bebidas: {e}")

    # ----- COMBINA TUDO -----
    if dataframes:
        df = pd.concat(dataframes, ignore_index=True)

        # Converte colunas numéricas (troca vírgula por ponto antes)
        for col in df.columns:
            if col not in ["Alimento", "Categoria", "Unidade", "#"]:
                df[col] = (df[col].astype(str)
                           .str.replace(",", ".", regex=False)
                           .str.strip())
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    else:
        st.error("❌ Nenhum arquivo de dados carregado!")
        return pd.DataFrame()


# ==============================================================================
# SEÇÃO 5 — ABA 1: SOBRE NUTRIÇÃO (conteúdo educativo)
# ==============================================================================

def aba_sobre_nutricao():
    """Primeira aba com informações educativas sobre nutrição."""

    st.title("🥗 Guia Alimentar para uma Vida Saudável")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("""
        ### 🌱 A Base: Qualidade Segundo o Guia Alimentar

        Antes de calcular números, o governo brasileiro destaca que a saúde vem da escolha dos alimentos.
        """)

        categorias = pd.DataFrame({
            "Categoria": ["**In Natura**", "**Processados**", "**Ultraprocessados**"],
            "Recomendação": ["Base da dieta", "Limitar", "Evitar"],
            "Exemplos": [
                "Arroz, feijão, carnes, ovos, frutas, tubérculos",
                "Queijos, pães artesanais, conservas simples",
                "Refrigerantes, biscoitos recheados, macarrão instantâneo"
            ]
        })
        st.table(categorias)
        
        st.markdown("---")
        st.markdown("""
        ### ⚠️ 1. Desinformação Nutricional
    
        As redes sociais frequentemente propagam dietas milagrosas e o medo injustificado de
        alimentos (como glúten e carboidratos). Essas práticas podem levar a:

        - **Deficiências nutricionais** e queda de imunidade
        - **Transtornos alimentares** devido a restrições severas
        - **Perda de fibras** e nutrientes essenciais
        """)

        st.markdown("---")
        st.markdown("""
        ### 🔥 2. Entendendo o Gasto Energético

        **TMB (Taxa Metabólica Basal):** Gasto energético mínimo para manter funções vitais em
        repouso. Representa cerca de 60-75% do gasto diário.

        **TMT (Taxa Metabólica Total):** Soma de toda a energia gasta em 24 horas (TMB + atividades
        físicas + digestão). O fator de atividade varia entre 1,2 e 1,9.

        **Déficit Calórico:** Estado em que o corpo consome menos calorias do que gasta,
        forçando o organismo a usar reservas de gordura como energia — princípio fundamental
        do emagrecimento saudável. Recomenda-se um déficit gradual de **200 a 500 kcal/dia**.
        """)


        col_tmb, col_tmt = st.columns(2)
        with col_tmb:
            st.info("""
            **📊 TMB — Taxa Metabólica Basal**

            • Gasto em repouso completo
            • 60–75 % do gasto diário
            • Varia com idade, sexo, peso e altura
            """)
        with col_tmt:
            st.info("""
            **📈 TMT — Taxa Metabólica Total**

            • Gasto total nas 24 horas
            • TMB + atividades físicas
            • Fator de atividade: 1,2 a 1,9
            """)


        st.markdown("---")
        st.markdown("⚖️ 3. Como As Calorias Agem No Nosso Corpo.")
        st.markdown("""Imagine o seu corpo como um carro: as calorias são o combustível que faz tudo funcionar,
                    desde o bater do coração até uma corrida no parque. Se você coloca combustível demais e não usa, 
                    o corpo guarda esse estoque em forma de gordura para emergências. 
                    Mas não é só a quantidade que importa; o tipo de caloria dita o ritmo do seu metabolismo. 
                    Por exemplo, 100 calorias de açúcar dão energia rápida, mas logo te deixam com fome de novo,
                    enquanto 100 calorias de proteína exigem mais esforço do corpo para digerir, mantendo você satisfeito por muito mais tempo""")
        st.markdown("---")

        st.markdown("**🥦 4.  Como a Origem dos Alimentos Infuenciam a Digestão**.")
        st.markdown("""A origem dos alimentos funciona como a "qualidade" desse combustível e das peças de reposição. 
                    Alimentos naturais (como frutas, carnes e grãos) vêm "completos", trazendo fibras e vitaminas que regulam o intestino e os hormônios,
                    deixando sua máquina rodando macio. 
                    Já os alimentos ultraprocessados (como salgadinhos e refrigerantes) são como combustível batizado: dão energia, mas inflamam o corpo, bagunçam os sinais de saciedade e podem causar danos a longo prazo, como diabetes e cansaço constante. 
                    No fim das contas, a origem do que você come decide se seu corpo vai trabalhar a seu favor ou contra você""")
        st.markdown("---")


    with col2:
        st.markdown("""
        ### 🎯 Recomendação Diária (por kg de peso)

        **Proteína:** 1,5 g/kg
        **Gordura:** 1,0 g/kg
        **Carboidrato:** 5,0 g/kg

        > **Exemplo:** Pessoa com 80 kg precisa de ~120 g de proteína por dia
        """)
        st.markdown("---")
        st.markdown("""
        ### 🍽️ Como Comer

        - Comer em horários regulares
        - Preferir comida caseira
        - Mastigar bem os alimentos
        - Beber água ao longo do dia
        """)
        st.markdown("---")
        st.warning("""
        **💡 Dica Importante:**

        Desconfie de dietas da moda. Nutrição saudável é baseada em equilíbrio e evidências
        científicas. Para emagrecimento saudável, faça um déficit calórico moderado de
        200–500 kcal abaixo da TMT!
        """)
        st.markdown("---")
        st.markdown("""
        ### 🔗 Fontes Confiáveis

        - [Ministério da Saúde](https://www.gov.br/saude)
        - [Guia Alimentar da População Brasileira](https://www.gov.br/saude)
        - [CFN — Conselho Federal de Nutrição](https://www.cfn.org.br)
        """)
        st.markdown("""
        ###  Como se Proteger

        - **Verifique a fonte:** Priorize informações de nutricionistas registrados e órgãos oficiais.
        - **Desconfie de promessas rápidas:** Não existem milagres alimentares sem evidência científica.
        - **Déficit calórico comprovado:** Para emagrecimento saudável, é necessário fazer déficit calórico.
        """)


# ==============================================================================
# SEÇÃO 6 — ABA 2: CALCULADORA TMB
# ==============================================================================

def aba_calculadora_tmb():
    """Segunda aba: calcula TMB e TDEE e salva no session_state."""

    st.title("⚖️ Calculadora de Gasto Diário")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📝 Dados Pessoais")

        peso    = st.number_input("Peso (kg)",    min_value=20.0,  max_value=200.0, value=70.0,  step=0.1)
        altura  = st.number_input("Altura (cm)",  min_value=100.0, max_value=250.0, value=170.0, step=0.1)
        idade   = st.number_input("Idade",        min_value=15,    max_value=100,   value=30,    step=1)
        sexo    = st.selectbox("Sexo", ["Homem", "Mulher"])

        atividade = st.selectbox(
            "Nível de Atividade",
            ["Sedentário", "Levemente ativo", "Moderado", "Muito ativo", "Extremamente ativo"]
        )

        fatores = {
            "Sedentário":           1.200,
            "Levemente ativo":      1.375,
            "Moderado":             1.550,
            "Muito ativo":          1.725,
            "Extremamente ativo":   1.900,
        }

        if st.button("Calcular Gasto Diário", type="primary"):
            # Fórmula de Mifflin-St Jeor
            if sexo == "Homem":
                tmb = (10 * peso) + (6.25 * altura) - (5 * idade) + 5
            else:
                tmb = (10 * peso) + (6.25 * altura) - (5 * idade) - 161

            tdee = tmb * fatores[atividade]
            st.session_state.tdee_usuario = tdee  # Salva para usar em outras abas

            with col2:
                st.subheader("📊 Resultados")

                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Taxa Metabólica Basal (TMB)", f"{tmb:.0f} kcal")
                with col_b:
                    st.metric("Gasto Total Diário (TDEE)",   f"{tdee:.0f} kcal")

                st.subheader("🥩 Macronutrientes Recomendados")
                st.info(f"""
                - **Proteína:**     {peso * 1.5:.0f} g/dia
                - **Gordura:**      {peso * 1.0:.0f} g/dia
                - **Carboidrato:**  {peso * 5.0:.0f} g/dia
                """)

                # Mostra sugestão de déficit calórico
                st.success(f"""
                **🎯 Para emagrecimento saudável:**
                Consuma entre **{tdee - 500:.0f}** e **{tdee - 200:.0f}** kcal/dia
                (déficit de 200–500 kcal)
                """)

    # Se já calculou antes, mantém o resultado visível
    if st.session_state.tdee_usuario > 0 and 'col2' not in locals():
        with col2:
            st.subheader("📊 Último Cálculo")
            st.metric("Gasto Total Diário", f"{st.session_state.tdee_usuario:.0f} kcal")


# ==============================================================================
# SEÇÃO 7 — ABA 3: CALCULADORA DE REFEIÇÃO (com data e nome)
# ==============================================================================

def aba_buscador_alimentos():
    """
    Terceira aba: busca comidas/bebidas, monta a refeição e permite salvar
    no histórico com data e nome personalizados.
    """
    st.title("🔍 Calculadora de Refeição")

    # Carrega base de dados
    df = carregar_dados()
    if df.empty:
        st.error("❌ Nenhuma base de dados carregada!")
        return

    # Resumo na sidebar
    st.sidebar.subheader("📊 Base de Dados")
    st.sidebar.write(f"Total: **{len(df)}** itens")
    st.sidebar.write(f"Comidas: **{len(df[df['Categoria']=='Comida'])}**")
    st.sidebar.write(f"Bebidas: **{len(df[df['Categoria']=='Bebida'])}**")

    # ---- Linha superior: DATA e NOME DA REFEIÇÃO ----
    st.markdown("### 📅 Identificação da Refeição")
    col_data, col_nome, col_limpar = st.columns([1, 2, 1])

    with col_data:
        data_escolhida = st.date_input(
            "Data da refeição:",
            value=st.session_state.data_refeicao,
            format="DD/MM/YYYY",
            key="seletor_data"
        )
        st.session_state.data_refeicao = data_escolhida  # Persiste na sessão

    with col_nome:
        # Nome/tipo da refeição
        nome_refeicao = st.selectbox(
            "Tipo de refeição:",
            ["Café da manhã", "Lanche da manhã", "Almoço",
             "Lanche da tarde", "Jantar", "Ceia", "Outro"],
            index=2,  # Padrão: Almoço
            key="sel_nome_refeicao"
        )
        st.session_state.nome_refeicao = nome_refeicao

    with col_limpar:
        st.markdown("<br>", unsafe_allow_html=True)  # Espaçamento vertical
        if st.button("🗑️ Limpar Refeição", use_container_width=True):
            # Zera todos os acumuladores e a lista
            st.session_state.lista_alimentos   = []
            st.session_state.total_kcal        = 0.0
            st.session_state.total_proteina    = 0.0
            st.session_state.total_carboidrato = 0.0
            st.session_state.total_gordura     = 0.0
            st.session_state.total_fibra       = 0.0
            st.rerun()

    st.divider()

    # ---- Layout principal: busca (esquerda) | lista (direita) ----
    col_esquerda, col_direita = st.columns([1, 1])

    # ===== COLUNA ESQUERDA: BUSCA DE ALIMENTOS =====
    with col_esquerda:
        tab_comida, tab_bebida = st.tabs(["🍛 COMIDAS", "🥤 BEBIDAS"])

        # ---------- ABA COMIDAS ----------
        with tab_comida:
            st.subheader("🍛 Buscar Comida")
            df_comidas = df[df['Categoria'] == 'Comida']

            busca_comida = st.text_input(
                "Nome da comida:",
                placeholder="Ex: arroz, frango, feijão...",
                key="busca_comida"
            )

            if busca_comida.strip():
                filtrados = df_comidas[
                    df_comidas['Alimento'].str.lower().str.contains(
                        busca_comida.strip().lower(), na=False
                    )
                ]
                st.caption(f"🔍 {len(filtrados)} resultado(s) encontrado(s)")
            else:
                filtrados = df_comidas
                st.caption(f"📋 {len(df_comidas)} comidas disponíveis")

            if not filtrados.empty:
                alimento_sel = st.selectbox(
                    "Selecione:",
                    filtrados['Alimento'].tolist(),
                    key="select_comida"
                )
                info = df[df['Alimento'] == alimento_sel].iloc[0]

                qtd = st.number_input(
                    "Quantidade (g):", min_value=1, max_value=2000,
                    value=100, step=10, key="qtd_comida"
                )

                # Cálculo proporcional (tabela está por 100g — ajuste se necessário)
                # A tabela armazena valores POR GRAMA, então multiplica direto pela quantidade
                kcal  = info['Calorias (kcal)']    * qtd
                prot  = info['Proteínas (g)']      * qtd
                carb  = info['Carboidratos (g)']   * qtd
                gord  = info['Gorduras (g)']       * qtd
                fibra = info['Fibras (g)']         * qtd
                st.subheader("📊 Valores Nutricionais")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("kcal",    f"{kcal:.0f}")
                c2.metric("Prot.",   f"{prot:.1f}g")
                c3.metric("Carb.",   f"{carb:.1f}g")
                c4.metric("Gord.",   f"{gord:.1f}g")
                c5.metric("Fibra",   f"{fibra:.1f}g")

                if st.button("➕ Adicionar comida", use_container_width=True, key="btn_comida"):
                    st.session_state.lista_alimentos.append({
                        'alimento': alimento_sel, 'quantidade': qtd, 'unidade': 'g',
                        'kcal': kcal, 'proteina': prot, 'carboidrato': carb,
                        'gordura': gord, 'fibra': fibra, 'categoria': 'Comida'
                    })
                    st.session_state.total_kcal        += kcal
                    st.session_state.total_proteina    += prot
                    st.session_state.total_carboidrato += carb
                    st.session_state.total_gordura     += gord
                    st.session_state.total_fibra       += fibra
                    st.success(f"✅ {alimento_sel} adicionado!")
                    st.rerun()

        # ---------- ABA BEBIDAS ----------
        with tab_bebida:
            st.subheader("🥤 Buscar Bebida")
            df_bebidas = df[df['Categoria'] == 'Bebida']

            busca_bebida = st.text_input(
                "Nome da bebida:",
                placeholder="Ex: água, suco, refrigerante...",
                key="busca_bebida"
            )

            if busca_bebida.strip():
                filtrados_b = df_bebidas[
                    df_bebidas['Alimento'].str.lower().str.contains(
                        busca_bebida.strip().lower(), na=False
                    )
                ]
                st.caption(f"🔍 {len(filtrados_b)} resultado(s) encontrado(s)")
            else:
                filtrados_b = df_bebidas
                st.caption(f"📋 {len(df_bebidas)} bebidas disponíveis")

            if not filtrados_b.empty:
                bebida_sel = st.selectbox(
                    "Selecione:",
                    filtrados_b['Alimento'].tolist(),
                    key="select_bebida"
                )
                info_b = df[df['Alimento'] == bebida_sel].iloc[0]

                qtd_b = st.number_input(
                    "Quantidade (ml):", min_value=1, max_value=2000,
                    value=200, step=50, key="qtd_bebida"
                )

                # A tabela armazena valores POR ML, multiplica direto pela quantidade
                kcal_b  = info_b['Calorias (kcal)']  * qtd_b
                prot_b  = info_b['Proteínas (g)']    * qtd_b
                carb_b  = info_b['Carboidratos (g)'] * qtd_b
                gord_b  = info_b['Gorduras (g)']     * qtd_b
                fibra_b = info_b['Fibras (g)']       * qtd_b

                st.subheader("📊 Valores Nutricionais")
                b1, b2, b3, b4, b5 = st.columns(5)
                b1.metric("kcal",  f"{kcal_b:.0f}")
                b2.metric("Prot.", f"{prot_b:.1f}g")
                b3.metric("Carb.", f"{carb_b:.1f}g")
                b4.metric("Gord.", f"{gord_b:.1f}g")
                b5.metric("Fibra", f"{fibra_b:.1f}g")

                if st.button("➕ Adicionar bebida", use_container_width=True, key="btn_bebida"):
                    st.session_state.lista_alimentos.append({
                        'alimento': bebida_sel, 'quantidade': qtd_b, 'unidade': 'ml',
                        'kcal': kcal_b, 'proteina': prot_b, 'carboidrato': carb_b,
                        'gordura': gord_b, 'fibra': fibra_b, 'categoria': 'Bebida'
                    })
                    st.session_state.total_kcal        += kcal_b
                    st.session_state.total_proteina    += prot_b
                    st.session_state.total_carboidrato += carb_b
                    st.session_state.total_gordura     += gord_b
                    st.session_state.total_fibra       += fibra_b
                    st.success(f"✅ {bebida_sel} adicionada!")
                    st.rerun()

    # ===== COLUNA DIREITA: LISTA DA REFEIÇÃO =====
    with col_direita:
        # Cabeçalho com data e nome
        data_fmt = st.session_state.data_refeicao.strftime('%d/%m/%Y')
        st.subheader(f"📝 {st.session_state.nome_refeicao} — {data_fmt}")

        if st.session_state.lista_alimentos:
            # Lista cada item com botão de remover
            for i, item in enumerate(st.session_state.lista_alimentos):
                with st.container():
                    col_del, col_info = st.columns([1, 6])
                    with col_del:
                        if st.button("❌", key=f"del_{i}", help="Remover item"):
                            # Subtrai do total antes de remover
                            st.session_state.total_kcal        -= item['kcal']
                            st.session_state.total_proteina    -= item['proteina']
                            st.session_state.total_carboidrato -= item['carboidrato']
                            st.session_state.total_gordura     -= item['gordura']
                            st.session_state.total_fibra       -= item['fibra']
                            st.session_state.lista_alimentos.pop(i)
                            st.rerun()
                    with col_info:
                        icone = "🍛" if item['categoria'] == 'Comida' else "🥤"
                        st.write(f"{icone} **{item['alimento']}** — {item['quantidade']}{item['unidade']}")
                        st.caption(
                            f"{item['kcal']:.0f} kcal | "
                            f"P: {item['proteina']:.1f}g | "
                            f"C: {item['carboidrato']:.1f}g | "
                            f"G: {item['gordura']:.1f}g | "
                            f"F: {item['fibra']:.1f}g"
                        )

            st.divider()

            # Totais da refeição
            st.subheader("📊 Total da Refeição")
            t1, t2, t3, t4, t5 = st.columns(5)
            t1.metric("kcal",  f"{st.session_state.total_kcal:.0f}")
            t2.metric("Prot.", f"{st.session_state.total_proteina:.1f}g")
            t3.metric("Carb.", f"{st.session_state.total_carboidrato:.1f}g")
            t4.metric("Gord.", f"{st.session_state.total_gordura:.1f}g")
            t5.metric("Fibra", f"{st.session_state.total_fibra:.1f}g")

            # Barra de progresso em relação ao TDEE (se calculado)
            if st.session_state.tdee_usuario > 0:
                perc = (st.session_state.total_kcal / st.session_state.tdee_usuario) * 100
                st.progress(min(perc / 100, 1.0))
                st.caption(
                    f"{perc:.1f}% do gasto diário "
                    f"({st.session_state.tdee_usuario:.0f} kcal)"
                )

            st.divider()

            # ---- BOTÃO SALVAR NO HISTÓRICO ----
            st.markdown("### 💾 Salvar no Histórico")
            if st.button("✅ Salvar esta refeição", use_container_width=True, type="primary"):
                usuario = st.session_state.usuario_logado

                totais = {
                    'kcal':        st.session_state.total_kcal,
                    'proteina':    st.session_state.total_proteina,
                    'carboidrato': st.session_state.total_carboidrato,
                    'gordura':     st.session_state.total_gordura,
                    'fibra':       st.session_state.total_fibra,
                }

                ok, msg = salvar_refeicao(
                    user_id       = usuario['id'],
                    data_refeicao = str(st.session_state.data_refeicao),
                    nome_refeicao = st.session_state.nome_refeicao,
                    lista_alimentos = st.session_state.lista_alimentos,
                    totais        = totais
                )

                if ok:
                    st.success(msg)
                    # Limpa a refeição após salvar
                    st.session_state.lista_alimentos   = []
                    st.session_state.total_kcal        = 0.0
                    st.session_state.total_proteina    = 0.0
                    st.session_state.total_carboidrato = 0.0
                    st.session_state.total_gordura     = 0.0
                    st.session_state.total_fibra       = 0.0
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info(
                "Sua refeição está vazia.\n\n"
                "Use as abas ao lado para adicionar comidas e bebidas! 👈"
            )


# ==============================================================================
# SEÇÃO 8 — ABA 4: HISTÓRICO DE REFEIÇÕES
# ==============================================================================

def aba_historico():
    """
    Quarta aba: exibe o histórico de refeições salvas do usuário logado,
    com filtro por período, visualização detalhada e opção de excluir.
    """
    st.title("📅 Histórico de Refeições")

    usuario = st.session_state.usuario_logado
    st.markdown(f"Exibindo registros de **{usuario['username']}**")

    # ---- Filtro de período ----
    st.subheader("🔎 Filtrar por Período")
    col_ini, col_fim, col_btn = st.columns([1, 1, 1])

    with col_ini:
        data_inicio = st.date_input("De:", value=date.today().replace(day=1), format="DD/MM/YYYY", key="hist_ini")
    with col_fim:
        data_fim = st.date_input("Até:", value=date.today(), format="DD/MM/YYYY", key="hist_fim")
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        buscar = st.button("🔍 Buscar", use_container_width=True, type="primary")

    # Busca sempre ao carregar a aba, e novamente quando clicar em Buscar
    refeicoes = buscar_historico(usuario['id'], data_inicio, data_fim)

    st.divider()

    # ---- Exibição dos resultados ----
    if not refeicoes:
        st.info("Nenhuma refeição encontrada para o período selecionado. 📭")
        return

    # Agrupamento por data para melhor visualização
    datas_unicas = sorted(
        set(r[1] for r in refeicoes),  # r[1] = campo 'data' da tupla
        reverse=True  # Mais recente primeiro
    )

    # Resumo geral do período
    total_kcal_periodo = sum(r[3] for r in refeicoes if r[3])
    st.markdown(
        f"**{len(refeicoes)} refeição(ões)** encontrada(s) | "
        f"Total do período: **{total_kcal_periodo:.0f} kcal**"
    )
    st.divider()

    # Itera por data, mostrando cada refeição
    for data_str in datas_unicas:
        # Formata a data para exibição em pt-BR
        try:
            data_obj = datetime.strptime(data_str, '%Y-%m-%d')
            data_exib = data_obj.strftime('%d/%m/%Y')
        except Exception:
            data_exib = data_str

        # Filtra refeições do dia
        refeicoes_do_dia = [r for r in refeicoes if r[1] == data_str]
        kcal_dia = sum(r[3] for r in refeicoes_do_dia if r[3])

        # Cabeçalho do dia em expander
        with st.expander(
            f"📆 **{data_exib}** — {len(refeicoes_do_dia)} refeição(ões) | "
            f"{kcal_dia:.0f} kcal no dia",
            expanded=(data_str == str(date.today()))  # Abre o dia de hoje por padrão
        ):
            for ref in refeicoes_do_dia:
                # Desempacota a tupla
                (ref_id, ref_data, ref_nome, ref_kcal, ref_prot,
                 ref_carb, ref_gord, ref_fibra, ref_registro) = ref

                # Cabeçalho da refeição
                col_ref, col_excluir = st.columns([5, 1])
                with col_ref:
                    st.markdown(f"#### 🍽️ {ref_nome or 'Refeição'}")
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("kcal",  f"{ref_kcal:.0f}"  if ref_kcal  else "—")
                    m2.metric("Prot.", f"{ref_prot:.1f}g"  if ref_prot  else "—")
                    m3.metric("Carb.", f"{ref_carb:.1f}g"  if ref_carb  else "—")
                    m4.metric("Gord.", f"{ref_gord:.1f}g"  if ref_gord  else "—")
                    m5.metric("Fibra", f"{ref_fibra:.1f}g" if ref_fibra else "—")

                with col_excluir:
                    if st.button("🗑️ Excluir", key=f"excl_{ref_id}",
                                 help="Excluir esta refeição permanentemente"):
                        if deletar_refeicao(ref_id):
                            st.success("Refeição excluída!")
                            st.rerun()
                        else:
                            st.error("Erro ao excluir.")

                # Detalhes dos itens (tabela)
                itens = buscar_itens_refeicao(ref_id)
                if itens:
                    with st.expander("Ver alimentos desta refeição"):
                        df_itens = pd.DataFrame(
                            itens,
                            columns=["Alimento", "Qtd", "Und", "kcal",
                                     "Prot(g)", "Carb(g)", "Gord(g)", "Fibra(g)", "Tipo"]
                        )
                        # Formata colunas numéricas
                        for col_num in ["kcal", "Prot(g)", "Carb(g)", "Gord(g)", "Fibra(g)"]:
                            df_itens[col_num] = df_itens[col_num].apply(
                                lambda x: f"{x:.1f}" if pd.notna(x) else "—"
                            )
                        st.dataframe(df_itens, use_container_width=True, hide_index=True)

                # Horário em que foi registrada
                st.caption(f"🕐 Registrada em: {ref_registro}")
                st.markdown("---")


# ==============================================================================
# SEÇÃO 9 — SIDEBAR DO USUÁRIO LOGADO
# ==============================================================================

def sidebar_usuario():
    """Exibe informações do usuário e botão de logout na barra lateral."""

    usuario = st.session_state.usuario_logado
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"### 👤 {usuario['username']}")
    st.sidebar.caption(usuario['email'])

    if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
        # Limpa toda a sessão ao sair
        for chave in list(st.session_state.keys()):
            del st.session_state[chave]
        st.rerun()

    st.sidebar.markdown("---")


# ==============================================================================
# SEÇÃO 10 — FUNÇÃO PRINCIPAL (main)
# Controla o fluxo: login → app principal
# ==============================================================================

def main():
    """
    Ponto de entrada do app.
    1. Inicializa o banco de dados (cria tabelas se necessário).
    2. Inicializa o session_state.
    3. Se não logado → mostra tela de login.
    4. Se logado → mostra o app completo com 4 abas.
    """

    # Garante que o banco existe antes de qualquer operação
    init_database()

    # Inicializa variáveis de sessão
    init_session_state()

    # ---- USUÁRIO NÃO AUTENTICADO ----
    if st.session_state.usuario_logado is None:
        tela_login()
        return  # Para aqui: não renderiza o app principal

    # ---- USUÁRIO AUTENTICADO ----
    sidebar_usuario()

    # Cria as 4 abas principais
    tab1, tab2, tab3, tab4 = st.tabs([
        "📖 Sobre Nutrição",
        "⚖️ Calculadora TMB",
        "🔍 Calculadora de Refeição",
        "📅 Histórico"
    ])

    with tab1:
        aba_sobre_nutricao()

    with tab2:
        aba_calculadora_tmb()

    with tab3:
        aba_buscador_alimentos()

    with tab4:
        aba_historico()

    # Rodapé
    st.divider()
    st.caption("Sistema Nutricional — Baseado no Guia Alimentar para a População Brasileira")


# ==============================================================================
# PONTO DE ENTRADA
# ==============================================================================
if __name__ == "__main__":
    main()