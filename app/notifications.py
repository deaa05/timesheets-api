import logging

logger = logging.getLogger("timesheets.notificaciones")


async def notificar(destinatario_email: str, asunto: str, mensaje: str) -> None:
    """
    Punto único de notificación (RF-03: notificar al coordinador al enviar un timesheet,
    RF-14: recordatorios automáticos).

    Esta implementación solo deja un registro en el log. Para producción,
    reemplazar el cuerpo de esta función por el envío real usando, por ejemplo,
    Resend, SendGrid, Postmark o el servicio de correo que prefiera CORPEI.
    """
    logger.info("Notificación -> destinatario=%s | asunto=%s | mensaje=%s", destinatario_email, asunto, mensaje)
