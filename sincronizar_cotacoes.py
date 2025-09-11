import pyodbc
import sys
import datetime

# --- CONFIGURAÇÕES DOS BANCOS DE DADOS ---
# O banco de dados de ORIGEM (onde os dados são criados/atualizados)
SOURCE_CONFIG = {
    'server': '172.16.1.218',
    'database': 'P12_PROD',
    'user': 'totvs',
    'password': 'totvs@1010',
    'driver': '{ODBC Driver 17 for SQL Server}'
}

# O banco de dados de DESTINO (para onde os dados serão copiados)
DESTINATION_CONFIG = {
    'server': '172.16.1.223',
    'database': 'P12_BI',
    'user': 'sa',
    'password': 'Rp@T3ch#50',
    'driver': '{ODBC Driver 17 for SQL Server}'
}

TABLE_NAME = 'SC8010'

# --- LISTA FINAL E CORRETA DE COLUNAS DA SC8 ---
# A instrução MERGE requer a lista de colunas para o INSERT e o UPDATE.
COLUMNS_TO_SYNC = [
    "C8_FILIAL", "C8_NUM", "C8_ITEM", "C8_PRODUTO", "C8_QUANT", "C8_UM",
    "C8_PRECO", "C8_TOTAL", "C8_FORNECE", "C8_LOJA", "C8_CONTATO", "C8_COND",
    "C8_VLDESC", "C8_VALFRE", "C8_SEGURO", "C8_DESPESA", "C8_VALIPI", "C8_VALICM",
    "C8_DATPRF", "C8_PRAZO", "C8_TPFRETE", "C8_OBS", "C8_NUMSC",
    "R_E_C_N_O_", "D_E_L_E_T_"
]

def log(message):
    """Função simples para registrar mensagens com data e hora."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def table_exists(config, table_name):
    """Verifica explicitamente se a tabela existe no banco de dados de destino."""
    conn_str = f"DRIVER={config['driver']};SERVER={config['server']};DATABASE={config['database']};UID={config['user']};PWD={config['password']}"
    try:
        with pyodbc.connect(conn_str) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = '{table_name}'")
                return cursor.fetchone()[0] == 1
    except Exception as e:
        log(f"ERRO ao verificar existência da tabela {table_name}: {e}")
        return False

def create_table(config):
    """Cria a tabela no destino caso ela não exista."""
    create_sql = f"""
    CREATE TABLE {TABLE_NAME} (
        C8_FILIAL VARCHAR(10), C8_NUM VARCHAR(20), C8_ITEM VARCHAR(4), C8_PRODUTO VARCHAR(30),
        C8_QUANT DECIMAL(10, 2), C8_UM VARCHAR(4), C8_PRECO DECIMAL(10, 4), C8_TOTAL DECIMAL(10, 2),
        C8_FORNECE VARCHAR(20), C8_LOJA VARCHAR(4), C8_CONTATO VARCHAR(50), C8_COND VARCHAR(20),
        C8_VLDESC DECIMAL(10, 2), C8_VALFRE DECIMAL(10, 2), C8_SEGURO DECIMAL(10, 2),
        C8_DESPESA DECIMAL(10, 2), C8_VALIPI DECIMAL(10, 2), C8_VALICM DECIMAL(10, 2),
        C8_DATPRF VARCHAR(8), C8_PRAZO DECIMAL(5, 0), C8_TPFRETE VARCHAR(2),
        C8_OBS VARCHAR(255), C8_NUMSC VARCHAR(20),
        R_E_C_N_O_ INT PRIMARY KEY,
        D_E_L_E_T_ VARCHAR(1)
    );
    """
    conn_str = f"DRIVER={config['driver']};SERVER={config['server']};DATABASE={config['database']};UID={config['user']};PWD={config['password']}"
    try:
        with pyodbc.connect(conn_str) as conn:
            with conn.cursor() as cursor:
                cursor.execute(create_sql)
                conn.commit()
                log(f"Tabela {TABLE_NAME} criada com sucesso no destino.")
    except Exception as e:
        log(f"ERRO CRÍTICO ao tentar criar a tabela {TABLE_NAME} no destino: {e}")
        sys.exit(1)

def fetch_records_for_sync(config, last_recno):
    """Busca todos os registros, novos e atualizados, a partir do último R_E_C_N_O_."""
    conn_str = f"DRIVER={config['driver']};SERVER={config['server']};DATABASE={config['database']};UID={config['user']};PWD={config['password']}"
    select_columns = ", ".join([f"[{col}]" for col in COLUMNS_TO_SYNC])
    
    # Adicionamos a cláusula OR para buscar registros com R_E_C_N_O_ antigos que foram alterados
    query = f"SELECT {select_columns} FROM {TABLE_NAME} WHERE R_E_C_N_O_ > ? OR (D_E_L_E_T_ = '*' AND R_E_C_N_O_ < ?)"
    
    try:
        with pyodbc.connect(conn_str) as conn:
            with conn.cursor() as cursor:
                log(f"Buscando registros da {TABLE_NAME} na origem com R_E_C_N_O_ > {last_recno}.")
                cursor.execute(query, last_recno, last_recno)
                return cursor.fetchall()
    except Exception as e:
        log(f"ERRO ao buscar novos registros na origem: {e}")
        sys.exit(1)

def get_last_recno(config):
    """Retorna o maior R_E_C_N_O_ do banco de dados de destino."""
    conn_str = f"DRIVER={config['driver']};SERVER={config['server']};DATABASE={config['database']};UID={config['user']};PWD={config['password']}"
    try:
        with pyodbc.connect(conn_str) as conn:
            with conn.cursor() as cursor:
                log(f"Buscando último R_E_C_N_O_ da {TABLE_NAME} no destino.")
                cursor.execute(f"SELECT MAX(R_E_C_N_O_) FROM {TABLE_NAME}")
                result = cursor.fetchone()[0]
                return result if result is not None else 0
    except Exception as e:
        log(f"ERRO ao buscar R_E_C_N_O_: {e}")
        sys.exit(1)

def upsert_records(config, records):
    """Sincroniza os registros usando a instrução MERGE."""
    conn_str = f"DRIVER={config['driver']};SERVER={config['server']};DATABASE={config['database']};UID={config['user']};PWD={config['password']}"
    
    # Prepara a instrução MERGE para o upsert
    set_clauses = ", ".join([f"T.[{col}] = S.[{col}]" for col in COLUMNS_TO_SYNC if col != "R_E_C_N_O_"])
    columns_list = ", ".join([f"[{col}]" for col in COLUMNS_TO_SYNC])
    placeholders = ", ".join(["?" for _ in COLUMNS_TO_SYNC])
    
    merge_query = f"""
    MERGE INTO {TABLE_NAME} AS T
    USING (VALUES ({placeholders})) AS S ({columns_list})
    ON (T.R_E_C_N_O_ = S.R_E_C_N_O_)
    WHEN MATCHED THEN
        UPDATE SET {set_clauses}
    WHEN NOT MATCHED THEN
        INSERT ({columns_list})
        VALUES ({placeholders});
    """
    
    try:
        with pyodbc.connect(conn_str) as conn:
            with conn.cursor() as cursor:
                log(f"Iniciando sincronização (upsert) de {len(records)} registros da {TABLE_NAME} no destino.")
                
                # Para evitar erros com o fast_executemany em MERGE, executamos um a um.
                # Se a performance for um problema, uma tabela temporária poderia ser usada.
                count_upserted = 0
                for record in records:
                    # MERGE requer que os parâmetros sejam passados duas vezes para a instrução
                    params = tuple(record) * 2
                    cursor.execute(merge_query, params)
                    count_upserted += 1
                    
                conn.commit()
                log(f"Sincronização concluída. Registros processados: {count_upserted}.")
    except Exception as e:
        log(f"ERRO CRÍTICO ao sincronizar registros: {e}")
        sys.exit(1)

def main():
    log(f"--- Iniciando Script de Sincronização da Tabela {TABLE_NAME} ---")
    
    if not table_exists(DESTINATION_CONFIG, TABLE_NAME):
        log(f"Tabela {TABLE_NAME} não encontrada no destino. Criando...")
        create_table(DESTINATION_CONFIG)
    else:
        log(f"Tabela {TABLE_NAME} já existe no destino.")
        
    last_recno_in_dest = get_last_recno(DESTINATION_CONFIG)
    
    # A consulta agora pode trazer registros antigos que foram deletados
    records_to_sync = fetch_records_for_sync(SOURCE_CONFIG, last_recno_in_dest)
    
    if not records_to_sync:
        log("Nenhum novo registro ou atualização encontrado. Sincronização em dia.")
    else:
        log(f"Encontrados {len(records_to_sync)} registros para sincronizar.")
        upsert_records(DESTINATION_CONFIG, records_to_sync)

    log(f"--- Fim do Script de Sincronização ---")

if __name__ == "__main__":
    main()