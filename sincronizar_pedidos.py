import pyodbc
import sys
import datetime

# --- CONFIGURAÇÕES DOS BANCOS DE DADOS ---
SOURCE_CONFIG = {
    'server': '172.16.1.218',
    'database': 'P12_PROD',
    'user': 'totvs',
    'password': 'totvs@1010',
    'driver': '{ODBC Driver 17 for SQL Server}'
}

DESTINATION_CONFIG = {
    'server': '172.16.1.223',
    'database': 'P12_BI',
    'user': 'sa',
    'password': 'Rp@T3ch#50',
    'driver': '{ODBC Driver 17 for SQL Server}'
}

TABLE_NAME = 'SC7010'

# Lista explícita de colunas para garantir que a ordem e a quantidade sejam as mesmas.
# Adicionando D_E_L_E_T_ e C7_CONAPRO para tratar atualizações de status.
COLUMNS_TO_SYNC = [
    "C7_FILIAL", "C7_NUM", "C7_ITEM", "C7_PRODUTO", "C7_DESCRI",
    "C7_QUANT", "C7_PRECO", "C7_TOTAL", "C7_EMISSAO", "C7_FORNECE",
    "C7_ENCER", "R_E_C_N_O_", "C7_CONTATO", "C7_EMITIDO", "C7_TPFRETE",
    "C7_NUMSC", "C7_NUMCOT", "C7_COMPRA", "C7_QUJE",
    "C7_COND", "C7_DATPRF", "C7_IPI", "C7_FRETE",
    "C7_VLDESC", "C7_TRANSP", "C7_LOCAL", "C7_UM", "C7_OBS",
    "D_E_L_E_T_", "C7_CONAPRO"
]

def log(message):
    """Função simples para registrar mensagens com data e hora."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def get_last_recno(config):
    """Busca o maior R_E_C_N_O_ no banco de dados de destino."""
    conn_str = f"DRIVER={config['driver']};SERVER={config['server']};DATABASE={config['database']};UID={config['user']};PWD={config['password']}"
    try:
        with pyodbc.connect(conn_str) as conn:
            with conn.cursor() as cursor:
                log(f"Conectado ao destino ({config['server']}) para buscar o último R_E_C_N_O_.")
                cursor.execute(f"SELECT MAX(R_E_C_N_O_) FROM {TABLE_NAME}")
                result = cursor.fetchone()[0]
                return result if result is not None else 0
    except Exception as e:
        log(f"ERRO ao conectar ou buscar o último R_E_C_N_O_ no destino: {e}")
        sys.exit(1)

def fetch_records_for_sync(config, last_recno):
    """
    Busca novos registros e também atualizações (incluindo exclusões lógicas)
    que ocorreram desde o último R_E_C_N_O_.
    """
    conn_str = f"DRIVER={config['driver']};SERVER={config['server']};DATABASE={config['database']};UID={config['user']};PWD={config['password']}"
    
    select_columns = ", ".join([f"[{col}]" for col in COLUMNS_TO_SYNC])
    
    # A query busca registros com R_E_C_N_O_ maior que o último,
    # e também registros que foram marcados para exclusão (`D_E_L_E_T_ = '*'`)
    # mesmo que o R_E_C_N_O_ seja menor.
    query = f"SELECT {select_columns} FROM {TABLE_NAME} WHERE R_E_C_N_O_ > ? OR D_E_L_E_T_ = '*'"
    
    try:
        with pyodbc.connect(conn_str) as conn:
            with conn.cursor() as cursor:
                log(f"Conectado à origem ({config['server']}) para buscar registros > {last_recno} ou deletados.")
                cursor.execute(query, last_recno)
                return cursor.fetchall()
    except Exception as e:
        log(f"ERRO ao buscar registros na origem: {e}")
        sys.exit(1)

def upsert_records(config, records):
    """Sincroniza os registros usando a instrução MERGE."""
    conn_str = f"DRIVER={config['driver']};SERVER={config['server']};DATABASE={config['database']};UID={config['user']};PWD={config['password']}"

    set_clauses = ", ".join([f"T.[{col}] = S.[{col}]" for col in COLUMNS_TO_SYNC if col not in ["R_E_C_N_O_"]])
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
                
                # MERGE requer que os parâmetros sejam passados duas vezes para a instrução
                count_upserted = 0
                for record in records:
                    params = tuple(record) * 2
                    cursor.execute(merge_query, params)
                    count_upserted += 1
                    
                conn.commit()
                log(f"Sincronização concluída. Registros processados: {count_upserted}.")
    except Exception as e:
        log(f"ERRO CRÍTICO ao sincronizar registros: {e}")
        sys.exit(1)

def main():
    log("--- Iniciando Script de Sincronização de Pedidos ---")
    
    # TODO: A lógica de criação de tabela precisa ser implementada para SC7010.
    
    last_recno_in_dest = get_last_recno(DESTINATION_CONFIG)
    log(f"Último R_E_C_N_O_ encontrado no destino: {last_recno_in_dest}")
    
    records_to_sync = fetch_records_for_sync(SOURCE_CONFIG, last_recno_in_dest)
    
    if not records_to_sync:
        log("Nenhum novo registro ou atualização encontrado. Sincronização em dia.")
    else:
        log(f"Encontrados {len(records_to_sync)} registros para sincronizar.")
        upsert_records(DESTINATION_CONFIG, records_to_sync)

    log("--- Fim do Script de Sincronização ---")

if __name__ == "__main__":
    main()