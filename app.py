import uuid
import random
import tkinter as tk
from tkinter import messagebox, Toplevel, Label, Button, Entry, Listbox, StringVar, OptionMenu, Frame
import tkinter.simpledialog as simpledialog
from cassandra.cluster import Cluster

# ----------------------------------------------------------------
# Conexão com o Cassandra (local)
# ----------------------------------------------------------------
cluster = Cluster(['127.0.0.1'])
session = cluster.connect()

# ----------------------------------------------------------------
# Criação do keyspace e tabelas, se não existirem
# ----------------------------------------------------------------
session.execute("""
    CREATE KEYSPACE IF NOT EXISTS game_manager 
    WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'}
""")
session.set_keyspace('game_manager')

session.execute("""
    CREATE TABLE IF NOT EXISTS tournaments (
        id text PRIMARY KEY,
        name text,
        simulated boolean
    )
""")

session.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id text PRIMARY KEY,
        name text,
        in_match boolean,
        tournament_id text
    )
""")

session.execute("""
    CREATE TABLE IF NOT EXISTS game_matches (
        id text PRIMARY KEY,
        title text,
        description text,
        status text,
        teams list<text>
    )
""")

# ----------------------------------------------------------------
# FUNÇÕES PARA TORNEIOS
# ----------------------------------------------------------------
def create_tournament(tournament_name):
    """Cria um torneio com simulated = False."""
    try:
        t_id = str(uuid.uuid4())
        query = "INSERT INTO tournaments (id, name, simulated) VALUES (%s, %s, %s)"
        session.execute(query, (t_id, tournament_name, False))
        return t_id
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao criar torneio: {e}")
        return None

def read_tournaments():
    """Retorna uma lista de torneios cadastrados."""
    rows = session.execute("SELECT id, name FROM tournaments")
    return [(row.id, row.name) for row in rows]

def read_tournament(t_id):
    """Retorna os detalhes de um torneio."""
    query = "SELECT id, name, simulated FROM tournaments WHERE id = %s"
    return session.execute(query, (t_id,)).one()

# ----------------------------------------------------------------
# FUNÇÕES PARA TIMES
# ----------------------------------------------------------------
def create_team(team_name, tournament_id):
    """Cria um time vinculado a um torneio."""
    try:
        team_id = str(uuid.uuid4())
        query = """
            INSERT INTO teams (id, name, in_match, tournament_id)
            VALUES (%s, %s, %s, %s)
        """
        session.execute(query, (team_id, team_name, False, tournament_id))
        return team_id
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao criar time: {e}")
        return None

def read_teams():
    """Retorna todos os times cadastrados."""
    rows = session.execute("SELECT id, name FROM teams")
    return [(row.id, row.name) for row in rows]

def read_teams_by_tournament(tournament_id):
    """Retorna os times pertencentes a um torneio específico."""
    query = "SELECT id, name FROM teams WHERE tournament_id = %s ALLOW FILTERING"
    rows = session.execute(query, (tournament_id,))
    return [(row.id, row.name) for row in rows]

def generate_ai_team_names(num_names, tournament_id):
    """
    Gera nomes para times utilizando uma combinação mais extensa de adjetivos e substantivos,
    criando variações que ajudam a evitar repetições e nomes genéricos.
    """
    adjectives = ["Cyber", "Quantum", "Digital", "Neo", "Synth", "Virtual", "AI", "Alpha", "Nova", "Cosmic", "Galactic", "Pixel", "Binary", "Electro", "Fusion", "Radical", "Mystic", "Vortex", "Epic", "Prime", "Legendary", "Infinite"]
    nouns = ["Knights", "Titans", "Gladiators", "Rangers", "Warriors", "Dynamos", "Phantoms", "Legends", "Storm", "Dragons", "Vikings", "Pirates", "Samurais", "Renegades", "Nomads", "Outlaws", "Saviors", "Defenders", "Champions", "Conquerors", "Invincibles"]
    possible_names = set()
    for adj in adjectives:
        for noun in nouns:
            possible_names.add(f"{adj} {noun}")
            possible_names.add(f"{adj} {noun} FC")
            possible_names.add(f"{noun} of {adj}")
    # Remover os nomes já existentes no torneio
    existing = set([name for _, name in read_teams_by_tournament(tournament_id)])
    valid_names = list(possible_names - existing)
    if len(valid_names) < num_names:
        messagebox.showwarning("Aviso", "Poucas opções disponíveis para nomes únicos. Considere resetar os times.")
        return []
    return random.sample(valid_names, num_names)

def generate_random_teams(tournament_id):
    """
    Gera uma quantidade definida de times aleatórios com nomes gerados "inteligentemente".
    Pergunta ao usuário quantos times deseja criar.
    """
    num_teams_to_generate = simpledialog.askinteger("Gerar Times", "Quantos times deseja gerar?", minvalue=2)
    if not num_teams_to_generate:
        return
    names = generate_ai_team_names(num_teams_to_generate, tournament_id)
    if not names:
        return
    for name in names:
        create_team(name, tournament_id)
    messagebox.showinfo("Sucesso", f"{num_teams_to_generate} times aleatórios foram adicionados ao torneio!")

# ----------------------------------------------------------------
# FUNÇÕES PARA PARTIDAS (game_matches)
# ----------------------------------------------------------------
def create_match(title, description):
    """Cria um registro de partida."""
    try:
        match_id = str(uuid.uuid4())
        query = """
            INSERT INTO game_matches (id, title, description, status, teams)
            VALUES (%s, %s, %s, %s, %s)
        """
        session.execute(query, (match_id, title, description, "Aguardando", []))
        return match_id
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao criar partida: {e}")
        return None

def read_matches():
    """Retorna todos os registros de partidas."""
    rows = session.execute("SELECT id, title, description, status, teams FROM game_matches")
    return [(row.id, row.title, row.description, row.status, row.teams) for row in rows]

def add_team_to_match(match_id, team_id):
    """Adiciona um time a uma partida (se estiver 'Aguardando')."""
    match_query = "SELECT status, teams FROM game_matches WHERE id = %s"
    team_query = "SELECT name, in_match FROM teams WHERE id = %s"
    match_row = session.execute(match_query, (match_id,)).one()
    team_row = session.execute(team_query, (team_id,)).one()
    
    if match_row and team_row and match_row.status == "Aguardando" and not team_row.in_match:
        update_match = "UPDATE game_matches SET teams = teams + [%s] WHERE id = %s"
        session.execute(update_match, (team_row.name, match_id))
        update_team = "UPDATE teams SET in_match = %s WHERE id = %s"
        session.execute(update_team, (True, team_id))
        return True
    return False

# ----------------------------------------------------------------
# FUNÇÃO DE SIMULAÇÃO DE TORNEIO (SIMULAÇÃO DINÂMICA)
# ----------------------------------------------------------------
def simulate_tournament_dynamic(tournament_id):
    """
    Simula um torneio knockout para qualquer quantidade de times (mínimo 2) e gera um ranking final.
    Em cada rodada, se houver número ímpar, um time recebe bye.
    Cada partida é simulada aleatoriamente e é registrado em qual rodada o time foi eliminado.
    O ranking final é determinado com base na rodada alcançada (quanto mais avançado, melhor a posição).
    """
    teams_list = read_teams_by_tournament(tournament_id)
    num_teams = len(teams_list)
    if num_teams < 2:
        return None, "O torneio deve ter pelo menos 2 times para simulação."
    
    teams = [name for _, name in teams_list]
    random.shuffle(teams)
    round_logs = []
    elimination_round = {}  # Guarda a rodada em que cada time foi eliminado
    current_round = 1
    current_competitors = teams.copy()
    
    while len(current_competitors) > 1:
        round_logs.append(f"Rodada {current_round}: {current_competitors}")
        next_round_competitors = []
        
        # Se número ímpar, escolhe um time para bye
        if len(current_competitors) % 2 == 1:
            bye_team = random.choice(current_competitors)
            next_round_competitors.append(bye_team)
            current_competitors.remove(bye_team)
            round_logs.append(f"Equipe com bye: {bye_team}")
        
        # Simula partidas em duplas
        for i in range(0, len(current_competitors), 2):
            team1 = current_competitors[i]
            team2 = current_competitors[i+1]
            winner = random.choice([team1, team2])
            loser = team2 if winner == team1 else team1
            next_round_competitors.append(winner)
            elimination_round[loser] = current_round
            round_logs.append(f"Jogo: {team1} vs {team2} -> Vencedor: {winner}")
        
        current_competitors = next_round_competitors
        current_round += 1
    
    champion = current_competitors[0]
    elimination_round[champion] = current_round
    # Ordena os times: quem sobreviveu mais rodadas fica melhor posicionado
    ranking_order = sorted(elimination_round.items(), key=lambda x: (-x[1], random.random()))
    ranking = [(f"{i+1}º Lugar", team) for i, (team, rnd) in enumerate(ranking_order)]
    round_logs.append("Ranking Final:")
    for pos, team in ranking:
        round_logs.append(f"{pos}: {team}")
    
    return ranking, "\n".join(round_logs)

# ----------------------------------------------------------------
# FUNÇÕES DE MANUTENÇÃO DO BANCO
# ----------------------------------------------------------------
def clear_database():
    """Apaga todos os dados (zera o banco)."""
    try:
        session.execute("TRUNCATE tournaments")
        session.execute("TRUNCATE teams")
        session.execute("TRUNCATE game_matches")
        messagebox.showinfo("Sucesso", "Banco de dados resetado com sucesso!")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao resetar banco de dados: {e}")

def delete_tournament_by_id(tournament_id):
    """Deleta um torneio e todos os times vinculados a ele."""
    try:
        session.execute("DELETE FROM tournaments WHERE id = %s", (tournament_id,))
        teams = read_teams_by_tournament(tournament_id)
        for team in teams:
            session.execute("DELETE FROM teams WHERE id = %s", (team[0],))
        messagebox.showinfo("Sucesso", "Torneio deletado com sucesso!")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao deletar torneio: {e}")

def on_delete_tournament():
    """Deleta o torneio selecionado (e seus times)."""
    selected_tournament_name = tournament_var.get()
    if selected_tournament_name == "Nenhum torneio cadastrado":
        messagebox.showerror("Erro", "Selecione um torneio para deletar!")
        return
    t_id = next((tid for tid, name in read_tournaments() if name == selected_tournament_name), None)
    if not t_id:
        messagebox.showerror("Erro", "Torneio inválido!")
        return
    if messagebox.askyesno("Confirmar", f"Tem certeza que deseja deletar o torneio '{selected_tournament_name}'?"):
        delete_tournament_by_id(t_id)
        update_tournament_menu()

# ----------------------------------------------------------------
# FUNÇÕES DE INTERFACE (GUI)
# ----------------------------------------------------------------
def update_match_list():
    match_listbox.delete(0, tk.END)
    try:
        for m in read_matches():
            teams_str = ', '.join(m[4]) if m[4] else ""
            match_listbox.insert(tk.END, f"ID: {m[0]} - {m[1]} - {m[2]} - {m[3]} - Ranking: {teams_str}")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao atualizar partidas: {e}")

def open_match_view():
    selected_match = match_listbox.get(tk.ACTIVE)
    if not selected_match:
        messagebox.showerror("Erro", "Selecione uma partida!")
        return
    match_id = selected_match.split(" - ")[0].replace("ID: ", "").strip()
    try:
        query = "SELECT title, description, status, teams FROM game_matches WHERE id = %s"
        row = session.execute(query, (match_id,)).one()
        if not row:
            messagebox.showerror("Erro", "Partida não encontrada!")
            return
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao recuperar partida: {e}")
        return
    
    match_window = Toplevel(root)
    match_window.title(f"Detalhes da Partida: {row.title}")
    match_window.geometry("400x300")
    
    Label(match_window, text=f"Título: {row.title}", font=("Arial", 14, "bold")).pack(pady=5)
    Label(match_window, text=f"Descrição: {row.description}", font=("Arial", 12)).pack(pady=5)
    Label(match_window, text=f"Status: {row.status}", font=("Arial", 12)).pack(pady=5)
    if row.status == "Terminado" and row.teams:
        Label(match_window, text="Ranking Final:", font=("Arial", 12, "bold")).pack(pady=5)
        for ranking_line in row.teams:
            Label(match_window, text=ranking_line, bg="lightblue", width=30, height=2).pack(pady=2)
    else:
        Label(match_window, text="Partida em andamento...", font=("Arial", 12, "italic")).pack(pady=5)

def open_tournament_view():
    """Exibe os detalhes do torneio selecionado e seus times."""
    selected_tournament_name = tournament_var.get()
    if selected_tournament_name == "Nenhum torneio cadastrado":
        messagebox.showerror("Erro", "Selecione um torneio!")
        return
    t_id = next((tid for tid, name in read_tournaments() if name == selected_tournament_name), None)
    if not t_id:
        messagebox.showerror("Erro", "Torneio inválido!")
        return

    teams_in_tournament = read_teams_by_tournament(t_id)
    tw = Toplevel(root)
    tw.title(f"Detalhes do Torneio: {selected_tournament_name}")
    tw.geometry("400x300")
    
    Label(tw, text=f"Torneio: {selected_tournament_name}", font=("Arial", 14, "bold")).pack(pady=5)
    Label(tw, text=f"ID: {t_id}", font=("Arial", 10, "italic")).pack(pady=5)
    if not teams_in_tournament:
        Label(tw, text="Nenhum time neste torneio.", fg="red").pack(pady=5)
    else:
        for tid, tname in teams_in_tournament:
            Label(tw, text=tname, bg="lightblue", width=20, height=2).pack(pady=2)

def on_create_tournament():
    name = tournament_entry.get()
    if not name:
        messagebox.showerror("Erro", "Digite um nome para o torneio!")
        return
    t_id = create_tournament(name)
    if t_id:
        messagebox.showinfo("Sucesso", f"Torneio '{name}' criado (ID: {t_id})!")
        update_tournament_menu()

def on_create_team():
    team_name = team_entry.get()
    if not team_name:
        messagebox.showerror("Erro", "Digite um nome para o time!")
        return
    selected_tournament_name = tournament_var.get()
    if selected_tournament_name == "Nenhum torneio cadastrado":
        messagebox.showerror("Erro", "Crie ou selecione um torneio antes de criar um time!")
        return
    t_id = next((tid for tid, name in read_tournaments() if name == selected_tournament_name), None)
    if not t_id:
        messagebox.showerror("Erro", "Torneio inválido!")
        return
    create_team(team_name, t_id)
    messagebox.showinfo("Sucesso", f"Time '{team_name}' criado no torneio '{selected_tournament_name}'!")

def on_simulate_tournament():
    selected_tournament_name = tournament_var.get()
    if selected_tournament_name == "Nenhum torneio cadastrado":
        messagebox.showerror("Erro", "Selecione um torneio para simular!")
        return
    t_id = next((tid for tid, name in read_tournaments() if name == selected_tournament_name), None)
    if not t_id:
        messagebox.showerror("Erro", "Torneio inválido!")
        return

    tournament_details = read_tournament(t_id)
    if tournament_details and tournament_details.simulated:
        messagebox.showerror("Erro", "Este torneio já foi simulado e não pode ser simulado novamente.")
        return

    sim_match_id = create_match("Simulação do Torneio " + selected_tournament_name, "Simulação realizada")
    if not sim_match_id:
        return

    ranking, log_text = simulate_tournament_dynamic(t_id)
    if ranking is None:
        messagebox.showerror("Erro", log_text)
        return
    
    ranking_lines = [f"{pos}: {team}" for pos, team in ranking]
    update_query = "UPDATE game_matches SET status = %s, teams = %s WHERE id = %s"
    session.execute(update_query, ("Terminado", ranking_lines, sim_match_id))
    
    session.execute("UPDATE tournaments SET simulated = %s WHERE id = %s", (True, t_id))
    
    sim_window = Toplevel(root)
    sim_window.title("Simulação do Torneio")
    sim_window.geometry("600x450")
    sim_window.configure(bg="#f0f8ff")
    
    title_label = Label(sim_window, text="Resultados da Simulação", font=("Helvetica", 16, "bold"), fg="#003366", bg="#f0f8ff")
    title_label.pack(pady=10)
    
    ranking_str = "\n".join(ranking_lines)
    result_label = Label(sim_window, text=f"Ranking Final:\n{ranking_str}", font=("Helvetica", 14), fg="green", bg="#f0f8ff")
    result_label.pack(pady=5)
    
    text_box = tk.Text(sim_window, width=70, height=18, font=("Courier", 10), bg="#e6f2ff")
    text_box.pack(pady=10)
    text_box.insert(tk.END, log_text)
    text_box.config(state=tk.DISABLED)
    
    update_match_list()

def on_generate_random_teams():
    selected_tournament_name = tournament_var.get()
    if selected_tournament_name == "Nenhum torneio cadastrado":
        messagebox.showerror("Erro", "Selecione um torneio para gerar times!")
        return
    t_id = next((tid for tid, name in read_tournaments() if name == selected_tournament_name), None)
    if not t_id:
        messagebox.showerror("Erro", "Torneio inválido!")
        return
    generate_random_teams(t_id)

def on_reset_database():
    if messagebox.askyesno("Confirmar", "Tem certeza que deseja resetar o banco (apagar TODOS os dados)?"):
        clear_database()
        update_tournament_menu()

def on_delete_tournament():
    selected_tournament_name = tournament_var.get()
    if selected_tournament_name == "Nenhum torneio cadastrado":
        messagebox.showerror("Erro", "Selecione um torneio para deletar!")
        return
    t_id = next((tid for tid, name in read_tournaments() if name == selected_tournament_name), None)
    if not t_id:
        messagebox.showerror("Erro", "Torneio inválido!")
        return
    if messagebox.askyesno("Confirmar", f"Tem certeza que deseja deletar o torneio '{selected_tournament_name}'?"):
        delete_tournament_by_id(t_id)
        update_tournament_menu()

def update_tournament_menu():
    all_tournaments = [name for _, name in read_tournaments()]
    if all_tournaments:
        tournament_var.set(all_tournaments[0])
    else:
        tournament_var.set("Nenhum torneio cadastrado")
    tournament_menu['menu'].delete(0, 'end')
    for t in all_tournaments:
        tournament_menu['menu'].add_command(label=t, command=lambda val=t: tournament_var.set(val))

# ----------------------------------------------------------------
# INTERFACE PRINCIPAL (GUI)
# ----------------------------------------------------------------
root = tk.Tk()
root.title("Gerenciador de Jogos - Column Family (Cassandra)")
root.geometry("900x650")
root.configure(bg="#e6e6fa")

main_frame = Frame(root, bg="#e6e6fa", padx=20, pady=20)
main_frame.pack(expand=True, fill="both")

# Seção de Torneios
t_frame = Frame(main_frame, bg="#e6e6fa", pady=10)
t_frame.pack(fill="x")
Label(t_frame, text="Nome do Torneio:", font=("Arial", 12, "bold"), bg="#e6e6fa").grid(row=0, column=0, sticky="w")
tournament_entry = Entry(t_frame, width=30, font=("Arial", 12))
tournament_entry.grid(row=0, column=1, padx=10)
Button(t_frame, text="Criar Torneio", font=("Arial", 12), command=on_create_tournament).grid(row=0, column=2, padx=10)
Label(t_frame, text="Selecione um Torneio:", font=("Arial", 12, "bold"), bg="#e6e6fa").grid(row=1, column=0, sticky="w", pady=5)
tournament_var = StringVar(t_frame)
all_tournaments = [name for _, name in read_tournaments()]
tournament_var.set(all_tournaments[0] if all_tournaments else "Nenhum torneio cadastrado")
tournament_menu = OptionMenu(t_frame, tournament_var, *(all_tournaments if all_tournaments else ["Nenhum torneio cadastrado"]))
tournament_menu.config(font=("Arial", 12))
tournament_menu.grid(row=1, column=1, padx=10)
Button(t_frame, text="Ver Detalhes do Torneio", font=("Arial", 12), command=open_tournament_view).grid(row=1, column=2, padx=10)
Button(t_frame, text="Gerar Times Aleatórios", font=("Arial", 12), command=on_generate_random_teams).grid(row=1, column=3, padx=10)
Button(t_frame, text="Deletar Torneio", font=("Arial", 12), command=on_delete_tournament).grid(row=1, column=4, padx=10)
Button(t_frame, text="Resetar Banco", font=("Arial", 12), command=on_reset_database).grid(row=0, column=4, padx=10)

# Seção de Times
team_frame = Frame(main_frame, bg="#e6e6fa", pady=10)
team_frame.pack(fill="x")
Label(team_frame, text="Nome do Time:", font=("Arial", 12, "bold"), bg="#e6e6fa").grid(row=0, column=0, sticky="w")
team_entry = Entry(team_frame, width=30, font=("Arial", 12))
team_entry.grid(row=0, column=1, padx=10)
Button(team_frame, text="Criar Time no Torneio", font=("Arial", 12), command=on_create_team).grid(row=0, column=2, padx=10)

# Seção para Simulação de Torneio
sim_frame = Frame(main_frame, bg="#e6e6fa", pady=10)
sim_frame.pack(fill="x")
Button(sim_frame, text="Simular Torneio", font=("Arial", 12, "bold"), bg="orange", command=on_simulate_tournament).pack(pady=5)

# Seção de Partidas
part_frame = Frame(main_frame, bg="#e6e6fa", pady=10)
part_frame.pack(fill="both", expand=True)
Label(part_frame, text="Partidas:", font=("Arial", 12, "bold"), bg="#e6e6fa").pack(anchor="w")
match_listbox = Listbox(part_frame, width=100, height=6, font=("Arial", 12))
match_listbox.pack(padx=10, pady=10, fill="both", expand=True)
Button(part_frame, text="Ver Detalhes da Partida", font=("Arial", 12), command=open_match_view).pack(pady=5)
Button(part_frame, text="Atualizar Partidas", font=("Arial", 12), command=update_match_list).pack(pady=5)

update_tournament_menu()
update_match_list()

root.mainloop()

# Para visualizar todas as tabelas no cqlsh (Docker), execute:
# docker pull cassandra casso seja necessario baixar a imagen 
# docker run --name cassandra-container -p 9042:9042 cassandra cria e ativa o container
# docker start cassandra-container
# docker exec -it cassandra-container bash entra no container cassandra
# USE game_manager;
# DESC TABLES;
#
#
# Isso exibirá: tournaments, teams e game_matches.

result = session.execute("""
    SELECT table_name
    FROM system_schema.tables
    WHERE keyspace_name = 'game_manager'
""")
print("Tabelas no keyspace 'game_manager':")
for row in result:
    print(row.table_name)

cluster.shutdown()
