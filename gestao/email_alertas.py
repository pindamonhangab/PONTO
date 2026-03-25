"""
Serviço de alertas de contas a pagar via Email (Gmail).

Configuração rápida (só uma vez):
1. Acesse https://myaccount.google.com/security
2. Ative "Verificação em duas etapas" se ainda não tiver
3. Acesse https://myaccount.google.com/apppasswords
4. Crie uma senha de app: selecione "Outro" e digite "PONTO"
5. Google vai gerar uma senha de 16 caracteres — use ela em Ajustes → Email

Pronto. Sem Docker, sem servidor, sem custo.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .models import ConfiguracaoBordado

logger = logging.getLogger(__name__)


class EmailAlertaError(Exception):
    pass


def _get_config():
    config = ConfiguracaoBordado.objects.first()
    if not config:
        raise EmailAlertaError("Configuração do sistema não encontrada.")
    if not all([config.email_remetente, config.email_senha_app, config.email_destinatario]):
        raise EmailAlertaError(
            "Email não configurado. "
            "Preencha remetente, senha de app e destinatário em Ajustes → Email."
        )
    return config


def enviar_email(assunto: str, corpo_html: str, corpo_texto: str = "") -> bool:
    """
    Envia um email via Gmail SMTP.
    Retorna True se enviado com sucesso, False se falhou.
    """
    config = _get_config()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"]    = f"PONTO Sistema <{config.email_remetente}>"
    msg["To"]      = config.email_destinatario

    if corpo_texto:
        msg.attach(MIMEText(corpo_texto, "plain", "utf-8"))
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(config.email_remetente, config.email_senha_app)
            smtp.sendmail(config.email_remetente, config.email_destinatario, msg.as_string())
        logger.info(f"Email enviado: {assunto}")
        return True
    except smtplib.SMTPAuthenticationError:
        raise EmailAlertaError(
            "Erro de autenticação no Gmail. "
            "Verifique se usou a Senha de App (não a senha normal da conta)."
        )
    except smtplib.SMTPException as e:
        raise EmailAlertaError(f"Erro ao enviar email: {e}")
    except Exception as e:
        raise EmailAlertaError(f"Erro inesperado: {e}")


def enviar_alerta_conta(conta) -> bool:
    """
    Envia alerta de vencimento de uma ContaPagar por email.
    Marca `notificacao_enviada = True` se enviado com sucesso.
    """
    d = conta.dias_para_vencer

    if d < 0:
        situacao_txt = f"VENCIDA há {abs(d)} dia(s)"
        situacao_cor = "#dc3545"
        emoji        = "🚨"
    elif d == 0:
        situacao_txt = "VENCE HOJE"
        situacao_cor = "#fd7e14"
        emoji        = "⚠️"
    else:
        situacao_txt = f"Vence em {d} dia(s)"
        situacao_cor = "#ffc107"
        emoji        = "📅"

    assunto = f"{emoji} PONTO — Conta a vencer: {conta.descricao} ({conta.vencimento.strftime('%d/%m/%Y')})"

    corpo_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px;">
      <div style="background: #dc3545; padding: 16px 24px; border-radius: 10px 10px 0 0;">
        <h2 style="color: white; margin: 0; font-size: 20px;">🧵 PONTO — Alerta Financeiro</h2>
      </div>
      <div style="background: #f8f9fa; padding: 24px; border-radius: 0 0 10px 10px; border: 1px solid #dee2e6;">

        <div style="background: {situacao_cor}; color: white; padding: 10px 16px;
                    border-radius: 8px; font-weight: bold; font-size: 16px; margin-bottom: 20px;">
          {emoji} {situacao_txt}
        </div>

        <table style="width: 100%; border-collapse: collapse;">
          <tr>
            <td style="padding: 8px 0; color: #6c757d; font-size: 13px; width: 40%;">Descrição</td>
            <td style="padding: 8px 0; font-weight: bold;">{conta.descricao}</td>
          </tr>
          <tr style="background: white;">
            <td style="padding: 8px; color: #6c757d; font-size: 13px;">Valor</td>
            <td style="padding: 8px; font-weight: bold; color: #dc3545; font-size: 18px;">
              R$ {conta.valor:.2f}
            </td>
          </tr>
          <tr>
            <td style="padding: 8px 0; color: #6c757d; font-size: 13px;">Vencimento</td>
            <td style="padding: 8px 0; font-weight: bold;">{conta.vencimento.strftime('%d/%m/%Y')}</td>
          </tr>
          <tr style="background: white;">
            <td style="padding: 8px; color: #6c757d; font-size: 13px;">Categoria</td>
            <td style="padding: 8px;">{conta.get_categoria_display()}</td>
          </tr>
          {'<tr><td style="padding: 8px 0; color: #6c757d; font-size: 13px;">Fornecedor</td><td style="padding: 8px 0;">' + conta.fornecedor + '</td></tr>' if conta.fornecedor else ''}
          {'<tr style="background: white;"><td style="padding: 8px; color: #6c757d; font-size: 13px;">Observações</td><td style="padding: 8px;">' + conta.observacoes + '</td></tr>' if conta.observacoes else ''}
        </table>

        <div style="margin-top: 24px; padding: 12px; background: #fff3cd;
                    border-radius: 8px; font-size: 13px; color: #856404;">
          💡 Acesse o sistema PONTO para marcar esta conta como paga.
        </div>

      </div>
      <p style="text-align: center; color: #adb5bd; font-size: 11px; margin-top: 16px;">
        Enviado automaticamente pelo sistema PONTO
      </p>
    </div>
    """

    corpo_texto = (
        f"PONTO — Alerta Financeiro\n\n"
        f"{situacao_txt}\n\n"
        f"Descrição: {conta.descricao}\n"
        f"Valor: R$ {conta.valor:.2f}\n"
        f"Vencimento: {conta.vencimento.strftime('%d/%m/%Y')}\n"
        f"Categoria: {conta.get_categoria_display()}\n"
        + (f"Fornecedor: {conta.fornecedor}\n" if conta.fornecedor else "")
        + "\nAcesse o sistema PONTO para marcar como paga."
    )

    try:
        sucesso = enviar_email(assunto, corpo_html, corpo_texto)
        if sucesso:
            conta.notificacao_enviada = True
            conta.save(update_fields=['notificacao_enviada'])
        return sucesso
    except EmailAlertaError as e:
        logger.error(f"Erro ao enviar alerta da conta {conta.id}: {e}")
        raise


def testar_conexao() -> tuple:
    """Envia um email de teste. Retorna (sucesso: bool, mensagem: str)"""
    try:
        config = _get_config()
        enviado = enviar_email(
            assunto="✅ PONTO — Teste de conexão",
            corpo_html="""
            <div style="font-family: Arial, sans-serif; padding: 24px; max-width: 400px;">
              <h2 style="color: #198754;">✅ Conexão funcionando!</h2>
              <p>Os alertas de contas a pagar do sistema <strong>PONTO</strong>
                 serão enviados para este email.</p>
            </div>
            """,
            corpo_texto="PONTO — Conexão de email funcionando! Os alertas serão enviados para este endereço.",
        )
        return True, f"✅ Email de teste enviado para {config.email_destinatario}!"
    except EmailAlertaError as e:
        return False, str(e)
