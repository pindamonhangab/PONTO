"""
Management command para verificar contas próximas do vencimento e enviar alertas por email.

Coloque em: gestao/management/commands/verificar_contas.py

Configurar no cron (roda todo dia às 8h da manhã):
    crontab -e
    0 8 * * * cd ~/PONTO && .venv/bin/python manage.py verificar_contas
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from gestao.models import ContaPagar, ConfiguracaoBordado
from gestao.email_alertas import enviar_alerta_conta, EmailAlertaError


class Command(BaseCommand):
    help = 'Verifica contas próximas do vencimento e envia alertas por email'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Simula sem enviar emails')
        parser.add_argument('--forcar', action='store_true',
                            help='Envia mesmo para contas que já receberam notificação')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        forcar  = options['forcar']

        config = ConfiguracaoBordado.objects.first()
        if not config:
            self.stderr.write("❌ Configuração não encontrada.")
            return

        dias_aviso = config.dias_aviso_conta
        hoje       = timezone.localdate()

        contas = ContaPagar.objects.filter(
            status='pendente',
            vencimento__lte=hoje + timezone.timedelta(days=dias_aviso),
        )
        if not forcar:
            contas = contas.filter(notificacao_enviada=False)

        if not contas.exists():
            self.stdout.write("✅ Nenhuma conta para notificar hoje.")
            return

        self.stdout.write(f"📋 {contas.count()} conta(s) para notificar:\n")
        enviados = falhas = 0

        for conta in contas:
            d = conta.dias_para_vencer
            status_str = f"VENCIDA há {abs(d)}d" if d < 0 else ("HOJE" if d == 0 else f"em {d}d")
            self.stdout.write(f"  → {conta.descricao} | R$ {conta.valor} | {status_str}")

            if dry_run:
                self.stdout.write("     [DRY-RUN] Email NÃO enviado.\n")
                continue

            try:
                enviar_alerta_conta(conta)
                self.stdout.write(self.style.SUCCESS("     ✅ Email enviado!"))
                enviados += 1
            except EmailAlertaError as e:
                self.stderr.write(self.style.ERROR(f"     ❌ Erro: {e}"))
                falhas += 1

        if not dry_run:
            self.stdout.write(f"\n📊 Resultado: {enviados} enviado(s), {falhas} falha(s).")
