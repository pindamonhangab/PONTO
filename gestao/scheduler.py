"""
Agendador automático de alertas de contas a pagar.
Funciona em Mac, Windows e Linux — sem configuração do sistema operacional.

Como usar:
    python scheduler.py

Deixe rodando em segundo plano. Ele verifica as contas uma vez por dia
no horário configurado e envia os emails de alerta automaticamente.

Para rodar em segundo plano no Mac/Linux:
    nohup python scheduler.py &

Para rodar em segundo plano no Windows:
    pythonw scheduler.py
    (ou use o arquivo .bat gerado automaticamente)
"""

import time
import subprocess
import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Configuração de log
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%d/%m/%Y %H:%M:%S',
    handlers=[
        logging.FileHandler('scheduler.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# Horário de execução diária (padrão: 08:00)
HORA_EXECUCAO = 8
MINUTO_EXECUCAO = 0

# Caminho do projeto
BASE_DIR = Path(__file__).parent
PYTHON   = sys.executable
MANAGE   = BASE_DIR / 'manage.py'


def rodar_verificacao():
    """Roda o comando Django verificar_contas."""
    logger.info("▶ Iniciando verificação de contas a pagar...")
    try:
        result = subprocess.run(
            [PYTHON, str(MANAGE), 'verificar_contas'],
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR),
        )
        if result.stdout:
            for linha in result.stdout.strip().split('\n'):
                logger.info(f"   {linha}")
        if result.returncode == 0:
            logger.info("✅ Verificação concluída com sucesso.")
        else:
            logger.error(f"❌ Erro na verificação: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ Erro ao executar verificação: {e}")


def proxima_execucao():
    """Calcula o datetime da próxima execução."""
    agora = datetime.now()
    alvo  = agora.replace(hour=HORA_EXECUCAO, minute=MINUTO_EXECUCAO, second=0, microsecond=0)
    if agora >= alvo:
        alvo += timedelta(days=1)
    return alvo


def main():
    logger.info("=" * 50)
    logger.info("🧵 PONTO — Agendador de Alertas iniciado")
    logger.info(f"   Verificação diária às {HORA_EXECUCAO:02d}:{MINUTO_EXECUCAO:02d}h")
    logger.info("=" * 50)

    while True:
        alvo    = proxima_execucao()
        agora   = datetime.now()
        espera  = (alvo - agora).total_seconds()

        logger.info(f"⏰ Próxima verificação: {alvo.strftime('%d/%m/%Y às %H:%M')}")

        # Dorme até o horário alvo (em blocos de 60s para não travar o processo)
        while datetime.now() < alvo:
            time.sleep(min(60, (alvo - datetime.now()).total_seconds()))

        rodar_verificacao()

        # Pequena pausa para não disparar duas vezes no mesmo minuto
        time.sleep(65)


if __name__ == '__main__':
    main()
