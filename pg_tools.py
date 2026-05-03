import os
from dotenv import load_dotenv
import psycopg2
from typing import Optional, List
from langchain.tools import tool
from pydantic import BaseModel, Field
 
load_dotenv()
 
DATABASE_URL = os.getenv("DATABASE_URL")  
 
def get_conn():
    return psycopg2.connect(DATABASE_URL)
 
def _local_date_filter_sql(field: str = "occurred_at") -> str:
    """
    Retorna um trecho SQL para filtragem por dia local em America/Sao_Paulo.
    Ex.: (occurred_at AT TIME ZONE 'America/Sao_Paulo')::date = %s::date
    """
    return f"(({field} AT TIME ZONE 'America/Sao_Paulo')::date = %s::date)"
 
 
class AddTransactionArgs(BaseModel):
    amount: float = Field(..., description="Valor da transação (use positivo).")
    source_text: str = Field(..., description="Texto original do usuário.")
    occurred_at: Optional[str] = Field(
        default=None,
        description="Timestamp ISO 8601; se ausente, usa NOW() no banco."
    )
    type_id: Optional[int] = Field(default=None, description="ID em transaction_types (1=INCOME, 2=EXPENSES, 3=TRANSFER).")
    type_name: Optional[str] = Field(default=None, description="Nome do tipo: INCOME | EXPENSES | TRANSFER.")
    category_id: Optional[int] = Field(default=None, description="FK de categories (opcional).")
    category_name:Optional[str] = Field(default=None, description="Nome da categoria: COMIDA | BESTEIRA | ESTUDO | FERIAS | TRANSPORTE | MORADIA | SAUDE | LAZER | CONTAS | INVESTIMENTO | PRESENTE | OUTROS.")
    description: Optional[str] = Field(default=None, description="Descrição (opcional).")
    payment_method: Optional[str] = Field(default=None, description="Forma de pagamento (opcional).")
 
class QueryTransactionsArgs(BaseModel):
    keyword: Optional[str] = Field(
        default=None,
        description="Palavra-chave para buscar em source_text ou description."
    )
    type_name: Optional[str] = Field(
        default=None,
        description="Filtrar por tipo: INCOME | EXPENSES | TRANSFER."
    )
    category_name: Optional[str] = Field(
        default=None,
        description="Filtrar por categoria (ex: COMIDA, TRANSPORTE)."
    )
    date_from_local: Optional[str] = Field(
        default=None,
        description="Data inicial no fuso America/Sao_Paulo (YYYY-MM-DD)."
    )
    date_to_local: Optional[str] = Field(
        default=None,
        description="Data final no fuso America/Sao_Paulo (YYYY-MM-DD)."
    )
    amount_min: Optional[float] = Field(
        default=None,
        description="Valor mínimo da transação."
    )
    amount_max: Optional[float] = Field(
        default=None,
        description="Valor máximo da transação."
    )
    limit: int = Field(
        default=20,
        description="Máximo de registros retornados (padrão 20)."
    )
 
 
 
class SaldoDiarioArgs(BaseModel):
    date_local: str = Field(
        ...,
        description="Data local em America/Sao_Paulo no formato YYYY-MM-DD."
    )
 
TYPE_ALIASES = {
    "INCOME": "INCOME","ENTRADA": "INCOME","RECEITA": "INCOME","SALÁRIO": "INCOME",
    "EXPENSE": "EXPENSES","SAÍDA": "EXPENSES","DESPESA": "EXPENSES","GASTO": "EXPENSES","EXPENSES": "EXPENSES",
    "TRANSFER": "TRANSFER","TRANSFERENCIA": "TRANSFER","TRANSFERÊNCIA": "TRANSFER"
}
 
#Garante que o campo type da tabela transactions receba um id válido (1=INCOME, 2=EXPENSES, 3=TRANSFER
def _resolve_type_id(cur, type_id: Optional[int], type_name: Optional[str]) -> Optional[int]:
    if type_name:
        t = type_name.strip().upper()
        if t in TYPE_ALIASES:
            t = TYPE_ALIASES[t]
        cur.execute("SELECT id FROM transaction_types WHERE UPPER(type)=%s LIMIT 1;", (t,))
        row = cur.fetchone()
        return row[0] if row else None
    if type_id:
        return int(type_id)
    return None
 
CATEGORY_ALIASES = {
    "COMIDA": "COMIDA","ALIMENTACAO": "COMIDA","ALIMENTAÇÃO": "COMIDA","FOOD": "COMIDA",
    "BESTEIRA": "BESTEIRA","DOCE": "BESTEIRA","SNACK": "BESTEIRA",
    "ESTUDO": "ESTUDO", "CURSO": "ESTUDO", "FACULDADE": "ESTUDO",
    "FERIAS": "FÉRIAS", "FÉRIAS": "FÉRIAS", "VIAGEM": "FÉRIAS",
    "TRANSPORTE": "TRANSPORTE", "UBER": "TRANSPORTE",
    "ONIBUS": "TRANSPORTE", "ÔNIBUS": "TRANSPORTE",
    "MORADIA": "MORADIA","ALUGUEL": "MORADIA",
    "SAUDE": "SAÚDE","SAÚDE": "SAÚDE","MEDICO": "SAÚDE","REMEDIO": "SAÚDE",
    "LAZER": "LAZER","DIVERSAO": "LAZER","DIVERSÃO": "LAZER",
    "CONTA": "CONTAS","CONTAS": "CONTAS","LUZ": "CONTAS","AGUA": "CONTAS",
    "INVESTIMENTO": "INVESTIMENTO","INVESTIR": "INVESTIMENTO",
    "PRESENTE": "PRESENTE",
    "OUTROS": "OUTROS"
}
 
def _resolve_category_id(cur,category_id: Optional[int], category_name: Optional[str]) -> Optional[int]:
    if category_name:
        c = category_name.strip().upper()
        if c in CATEGORY_ALIASES:
            c = CATEGORY_ALIASES[c]
        cur.execute("SELECT id FROM categories WHERE UPPER(name)=%s LIMIT 1;", (c,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("SELECT id FROM categories WHERE UPPER(name)='OUTROS' LIMIT 1;")
        fallback = cur.fetchone()
        return fallback[0] if fallback else None
    if category_id:
        return int(category_id)
    return None
 
# Tool: add_transaction
@tool("add_transaction", args_schema=AddTransactionArgs)
def add_transaction(
    amount: float,
    source_text: str,
    occurred_at: Optional[str] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> dict:
   
   
    """Insere uma transação financeira no banco de dados Postgres.""" # docstring obrigatório da @tools do langchain (estranho, mas legal né?)
    conn = get_conn()
    cur = conn.cursor()
    try:
        resolved_type_id = _resolve_type_id(cur, type_id, type_name)
        if not resolved_type_id:
            return {"status": "error", "message": "Tipo inválido (use type_id ou type_name: INCOME/EXPENSES/TRANSFER)."}
       
        resolved_category_id = _resolve_category_id(cur, category_id, category_name)
       
 
        if occurred_at:
            cur.execute(
                """
                INSERT INTO transactions
                    (amount, type, category_id, description, payment_method, occurred_at, source_text)
                VALUES
                    (%s, %s, %s, %s, %s, %s::timestamptz, %s)
                RETURNING id, occurred_at;
                """,
                (amount, resolved_type_id, resolved_category_id, description, payment_method, occurred_at, source_text),
            )
        else:
            cur.execute(
                """
                INSERT INTO transactions
                    (amount, type, category_id, description, payment_method, occurred_at, source_text)
                VALUES
                    (%s, %s, %s, %s, %s, NOW(), %s)
                RETURNING id, occurred_at;
                """,
                (amount, resolved_type_id, resolved_category_id, description, payment_method, source_text),
            )
 
        new_id, occurred = cur.fetchone()
        conn.commit()
        return {"status": "ok", "id": new_id, "occurred_at": str(occurred)}
 
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
 
@tool("search_transactions", args_schema=QueryTransactionsArgs)
def search_transactions(
    keyword: Optional[str] = None
    ,type_name: Optional[str] = None
    ,category_name:Optional[str] = None
    ,date_from_local: Optional[str] = None
    ,date_to_local: Optional[str] = None
    ,amount_max: Optional[float] = None
    ,amount_min: Optional[float] = None
    ,limit: int = 20
 
) -> dict:
    """
    Consulta transações com filtros por texto (source_text/description), tipo e datas locais (America/ Sao_Paulo).
    Os dados devem vir na seguinte ordem:
    - Intervalo (date_from_local/date_to_local): ASC (cronológico).
    - Caso contrário:  DESC (mais recente primeiro).
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        conditions = []
        params = []
 
        # Filtro por palavra-chave
        if keyword:
            conditions.append("(t.source_text ILIKE %s OR t.description ILIKE %s)")
            kw = f"%{keyword}%"
            params.extend([kw, kw])
 
        # Filtro por tipo
        if type_name:
            tipo = TYPE_ALIASES.get(type_name.strip().upper(), type_name.strip().upper())
            conditions.append("UPPER(tt.type) = %s")
            params.append(tipo)
       
        # Filtro por categoria
        if category_name:
            categoria = CATEGORY_ALIASES.get(
                category_name.strip().upper(),
                category_name.strip().upper()
            )
            conditions.append("UPPER(c.name) = %s")
            params.append(categoria)
       
        # Filtro por intervalo de datas (fuso local)
        if date_from_local:
            conditions.append(
                "(t.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date >= %s::date"
            )
            params.append(date_from_local)
 
        if date_to_local:
            conditions.append(
                "(t.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date <= %s::date"
            )
            params.append(date_to_local)
 
        if amount_min is not None:
            conditions.append("t.amount >= %s")
            params.append(amount_min)
 
        if amount_max is not None:
            conditions.append("t.amount <= %s")
            params.append(amount_max)
 
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
 
        if date_from_local or date_to_local:
            order = "ASC"
        else:
            order = "DESC"
 
        query = f"""
        SELECT
            t.id,
                t.amount,
                tt.type                                              AS type_name,
                c.name                                               AS category_name,
                t.description,
                t.payment_method,
                (t.occurred_at AT TIME ZONE 'America/Sao_Paulo')
                    ::timestamp                                       AS occurred_local,
                t.source_text
            FROM transactions t
            JOIN transaction_types tt ON tt.id = t.type
            LEFT JOIN categories    c  ON c.id  = t.category_id
            {where}
            ORDER BY t.occurred_at {order}
            LIMIT %s;
        """
        params.append(limit)
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = ["id", "amount", "type_name", "category_name",
                "description", "payment_method", "occurred_local", "source_text"]
       
        return {
            "status": "ok",
            "count": len(rows),
            "transactions": [dict(zip(cols, r)) for r in rows],
        }
   
    except Exception as e:
        return {"status": "error", "message": str(e)}
       
    finally:
        cur.close()
        conn.close()
 
 
 
@tool("saldo_atual")
def saldo_atual() -> dict:
    """
    Retorna o saldo total (INCOME - EXPENSES) em todo o histórico (ignora TRANSFER).
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT
                COALESCE(SUM(CASE WHEN tt.type = 'INCOME' THEN t.amount ELSE 0 END), 0) AS total_income
                ,COALESCE(SUM(CASE WHEN tt.type = 'EXPENSES' THEN t.amount ELSE 0 END), 0) AS total_expenses
        FROM transactions t
        JOIN transaction_types tt ON tt.id = t.type
        WHERE tt.type IN ('INCOME', 'EXPENSES');
        """)
 
        income, expenses = cur.fetchone()
 
        return {
            "status": "ok",
            "total_income": float(income),
            "total_expenses": float(expenses),
            "saldo": float(income - expenses),
        }
   
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()
 
@tool("saldo_diario", args_schema=SaldoDiarioArgs)
def saldo_diario(date_local: str) -> dict:
    """
    Retorna o saldo (INCOME - EXPENSES) do dia local informado (YYYY-MM-DD) em America/Sao_Paulo.
    Ignora TRANSFER (type=3).
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN tt.type = 'INCOME'   THEN t.amount ELSE 0 END), 0) AS total_income,
                COALESCE(SUM(CASE WHEN tt.type = 'EXPENSES' THEN t.amount ELSE 0 END), 0) AS total_expenses
            FROM transactions t
            JOIN transaction_types tt ON tt.id = t.type
            WHERE tt.type IN ('INCOME', 'EXPENSES')
              AND (t.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date = %s::date;
        """, (date_local,))
        income, expenses = cur.fetchone()
        return {
            "status": "ok",
            "date": date_local,
            "total_income": float(income),
            "total_expenses": float(expenses),
            "saldo": float(income - expenses),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()
 
class UpdateTransactionArgs(BaseModel):
    id: Optional[int] = Field(
        default=None,
        description="ID da transação a atualizar. Se ausente, será feita uma busca por (match_text + date_local)."
    )
    match_text: Optional[str] = Field(
        default=None,
        description="Texto para localizar transação quando id não for informado (busca em source_text/description)."
    )
    date_local: Optional[str] = Field(
        default=None,
        description="Data local (YYYY-MM-DD) em America/Sao_Paulo; usado em conjunto com match_text quando id ausente."
    )
    amount: Optional[float] = Field(default=None, description="Novo valor.")
    type_id: Optional[int] = Field(default=None, description="Novo type_id (1/2/3).")
    type_name: Optional[str] = Field(default=None, description="Novo type_name: INCOME | EXPENSES | TRANSFER.")
    category_id: Optional[int] = Field(default=None, description="Nova categoria (id).")
    category_name: Optional[str] = Field(default=None, description="Nova categoria (nome).")
    description: Optional[str] = Field(default=None, description="Nova descrição.")
    payment_method: Optional[str] = Field(default=None, description="Novo meio de pagamento.")
    occurred_at: Optional[str] = Field(default=None, description="Novo timestamp ISO 8601.")
 
@tool("update_transaction", args_schema=UpdateTransactionArgs)
def update_transaction(
    id: Optional[int] = None,
    match_text: Optional[str] = None,
    date_local: Optional[str] = None,
    amount: Optional[float] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> dict:
    """
    Atualiza uma transação existente.
    Estratégias:
      - Se 'id' for informado: atualiza diretamente por ID.
      - Caso contrário: localiza a transação mais recente que combine (match_text em source_text/description)
        E (date_local em America/Sao_Paulo), então atualiza.
    Retorna: status, rows_affected, id, e o registro atualizado.
    """
    if not any([amount, type_id, type_name, category_id, category_name, description, payment_method, occurred_at]):
        return {"status": "error", "message": "Nada para atualizar: forneça pelo menos um campo (amount, type, category, description, payment_method, occurred_at)."}
 
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Resolve target_id
        target_id = id
        if target_id is None:
            if not match_text or not date_local:
                return {"status": "error", "message": "Sem 'id': informe match_text E date_local para localizar o registro."}
 
            # Buscar o mais recente no dia local informado que combine o texto
            cur.execute(
                f"""
                SELECT t.id
                FROM transactions t
                WHERE (t.source_text ILIKE %s OR t.description ILIKE %s)
                  AND {_local_date_filter_sql("t.occurred_at")}
                ORDER BY t.occurred_at DESC
                LIMIT 1;
                """,
                (f"%{match_text}%", f"%{match_text}%", date_local)
            )
            row = cur.fetchone()
            if not row:
                return {"status": "error", "message": "Nenhuma transação encontrada para os filtros fornecidos."}
            target_id = row[0]
 
        # Resolver type_id / category_id a partir de nomes, se fornecidos
        resolved_type_id = _resolve_type_id(cur, type_id, type_name) if (type_id or type_name) else None
        resolved_category_id = category_id
        if category_name and not category_id:
            resolved_category_id = _resolve_category_id(cur, category_name)
 
        # Montar SET dinâmico
        sets = []
        params: List[object] = []
        if amount is not None:
            sets.append("amount = %s")
            params.append(amount)
        if resolved_type_id is not None:
            sets.append("type = %s")
            params.append(resolved_type_id)
        if resolved_category_id is not None:
            sets.append("category_id = %s")
            params.append(resolved_category_id)
        if description is not None:
            sets.append("description = %s")
            params.append(description)
        if payment_method is not None:
            sets.append("payment_method = %s")
            params.append(payment_method)
        if occurred_at is not None:
            sets.append("occurred_at = %s::timestamptz")
            params.append(occurred_at)
 
        if not sets:
            return {"status": "error", "message": "Nenhum campo válido para atualizar."}
 
        params.append(target_id)
 
        cur.execute(
            f"UPDATE transactions SET {', '.join(sets)} WHERE id = %s;",
            params
        )
        rows_affected = cur.rowcount
        conn.commit()
 
        # Retornar o registro atualizado
        cur.execute(
            """
            SELECT
              t.id, t.occurred_at, t.amount, tt.type AS type_name,
              c.name AS category_name, t.description, t.payment_method, t.source_text
            FROM transactions t
            JOIN transaction_types tt ON tt.id = t.type
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.id = %s;
            """,
            (target_id,)
        )
        r = cur.fetchone()
        updated = None
        if r:
            updated = {
                "id": r[0],
                "occurred_at": str(r[1]),
                "amount": float(r[2]),
                "type": r[3],
                "category": r[4],
                "description": r[5],
                "payment_method": r[6],
                "source_text": r[7],
            }
 
        return {
            "status": "ok",
            "rows_affected": rows_affected,
            "id": target_id,
            "updated": updated
        }
 
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
 
# Exporta a lista de tools
TOOLS = [add_transaction, search_transactions, saldo_atual,saldo_diario]
