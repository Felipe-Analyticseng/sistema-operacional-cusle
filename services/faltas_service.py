# services/faltas_service.py

from db.database import run_query


def listar_faltas():
    """
    Lista ausências registradas no app existente de faltas.
    Fonte: public.faltas
    """
    return run_query(
        """
        SELECT
            id,
            quem_escolhe,
            justificativa,
            data_registro
        FROM public.faltas
        ORDER BY data_registro DESC;
        """
    )