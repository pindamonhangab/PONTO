import threading
import logging
import time
from datetime import datetime, timedelta
from django.apps import AppConfig

logger = logging.getLogger(__name__)

# Horário diário de verificação (padrão: 08:00)
HORA_EXECUCAO   = 8
MINUTO_EXECUCAO = 0


def _rodar_verificacao():
    """Roda o comando verificar_contas dentro do processo Django."""
    try:
        # Importa aqui para garantir que o Django já está pronto
        from django.utils import timezone
        from datetime import timedelta
        from gestao.models import ContaPagar, ConfiguracaoBordado
        from gestao.email_alertas import enviar_alerta_conta, EmailAlertaError

        config = ConfiguracaoBordado.objects.first()
        if not config:
            return

        dias_aviso = config.dias_aviso_conta
        hoje       = timezone.localdate()

        contas = ContaPagar.objects.filter(
            status='pendente',
            vencimento__lte=hoje + timedelta(days=dias_aviso),
            notificacao_enviada=False,
        )

        if not contas.exists():
            logger.info("[PONTO Scheduler] Nenhuma conta para notificar hoje.")
            return

        logger.info(f"[PONTO Scheduler] {contas.count()} conta(s) para notificar.")

        for conta in contas:
            try:
                enviar_alerta_conta(conta)
                logger.info(f"[PONTO Scheduler] ✅ Alerta enviado: {conta.descricao}")
            except EmailAlertaError as e:
                logger.error(f"[PONTO Scheduler] ❌ Erro em '{conta.descricao}': {e}")

    except Exception as e:
        logger.error(f"[PONTO Scheduler] ❌ Erro geral: {e}")


def _loop_scheduler():
    """
    Loop infinito em thread separada.
    Verifica uma vez por dia no horário configurado.
    Não bloqueia o servidor Django.
    """
    logger.info(f"[PONTO Scheduler] Iniciado — verificação diária às {HORA_EXECUCAO:02d}:{MINUTO_EXECUCAO:02d}h")

    while True:
        agora = datetime.now()
        alvo  = agora.replace(
            hour=HORA_EXECUCAO, minute=MINUTO_EXECUCAO,
            second=0, microsecond=0
        )
        if agora >= alvo:
            alvo += timedelta(days=1)

        espera = (alvo - datetime.now()).total_seconds()
        logger.info(f"[PONTO Scheduler] Próxima verificação: {alvo.strftime('%d/%m/%Y às %H:%M')}")

        # Dorme em blocos de 60s (permite resposta a sinais do sistema)
        while datetime.now() < alvo:
            time.sleep(min(60, max(1, (alvo - datetime.now()).total_seconds())))

        _rodar_verificacao()

        # Pausa para não disparar duas vezes no mesmo minuto
        time.sleep(65)


class GestaoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestao'

    def ready(self):
        """
        Chamado automaticamente pelo Django quando o app está pronto.
        Inicia o scheduler em uma thread daemon — morre junto com o servidor.
        """
        import os

        # Evita rodar duas vezes no modo de desenvolvimento (Django usa 2 processos)
        if os.environ.get('RUN_MAIN') != 'true':
            return

        t = threading.Thread(target=_loop_scheduler, daemon=True, name='ponto-scheduler')
        t.start()
        logger.info("[PONTO Scheduler] Thread iniciada com sucesso.")
