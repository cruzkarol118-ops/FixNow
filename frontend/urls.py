from django.urls import path

from . import views

urlpatterns = [
    # Público
    path("", views.landing, name="landing"),
    path("ingresar/", views.login_view, name="login"),
    path("salir/", views.logout_view, name="logout"),
    path("cuenta/password/", views.cambiar_password, name="cambiar_password"),
    path("registro/", views.registro_cliente, name="registro_cliente"),
    path("registro/tecnico/", views.registro_tecnico, name="registro_tecnico"),
    # Cliente
    path("cliente/", views.cliente_inicio, name="cliente_inicio"),
    path("cliente/solicitud/nueva/", views.solicitud_nueva, name="solicitud_nueva"),
    # Bloque F1: endpoint liviano de sugerencia de categoría (?texto=...).
    path("cliente/solicitud/sugerir/", views.sugerir_categoria,
         name="sugerir_categoria"),
    path("cliente/tecnicos/", views.tecnicos, name="tecnicos"),
    # Bloque G: ficha pública del técnico con reseñas.
    path("cliente/tecnicos/<int:pk>/", views.tecnico_publico,
         name="tecnico_publico"),
    # Bloque G: baja voluntaria de la cuenta.
    path("cliente/cuenta/desactivar/", views.cuenta_desactivar,
         name="cuenta_desactivar"),
    path("cliente/historial/", views.cliente_historial, name="cliente_historial"),
    path("cliente/perfil/", views.cliente_perfil, name="cliente_perfil"),
    path("cliente/solicitud/<int:pk>/cancelar/", views.solicitud_cancelar,
         name="solicitud_cancelar"),
    path("cliente/solicitud/<int:pk>/calificar/", views.solicitud_calificar,
         name="solicitud_calificar"),
    # Bloque H: ajustar precio/visibilidad + aceptar/rechazar monto.
    path("cliente/solicitud/<int:pk>/precio/", views.solicitud_precio,
         name="solicitud_precio"),
    path("cliente/solicitud/monto/", views.monto_decidir,
         name="monto_decidir"),
    path("cliente/solicitud/<int:pk>/pagar/", views.solicitud_pagar,
         name="solicitud_pagar"),
    # Técnico
    path("tecnico/solicitudes/", views.tecnico_solicitudes, name="tecnico_solicitudes"),
    path("tecnico/disponibilidad/", views.tecnico_disponibilidad,
         name="tecnico_disponibilidad"),
    path("tecnico/solicitudes/<int:solicitud_id>/aceptar/", views.tecnico_aceptar,
         name="tecnico_aceptar"),
    path("tecnico/solicitudes/<int:solicitud_id>/rechazar/", views.tecnico_rechazar,
         name="tecnico_rechazar"),
    path("tecnico/solicitudes/<int:solicitud_id>/finalizar/", views.tecnico_finalizar,
         name="tecnico_finalizar"),
    path("tecnico/perfil/", views.tecnico_perfil, name="tecnico_perfil"),
    path("tecnico/historial/", views.tecnico_historial, name="tecnico_historial"),
    # Bloque H: mapa de solicitudes de clientes.
    path("tecnico/mapa/", views.tecnico_mapa, name="tecnico_mapa"),
    # Bloque G: certificados extra + baja voluntaria.
    path("tecnico/documentos/agregar/", views.documento_agregar,
         name="documento_agregar"),
    path("tecnico/documentos/<int:pk>/eliminar/", views.documento_eliminar,
         name="documento_eliminar"),
    path("tecnico/cuenta/desactivar/", views.cuenta_desactivar,
         name="tecnico_desactivar"),
    # Administrador
    path("panel/tecnicos/", views.admin_tecnicos, name="admin_tecnicos"),
    # Bloque G: ficha de revisión + moderación de reseñas.
    path("panel/tecnicos/<int:pk>/", views.admin_ficha_tecnico,
         name="admin_ficha_tecnico"),
    path("panel/resenas/", views.admin_resenas, name="admin_resenas"),
    path("panel/resenas/moderar/", views.resena_moderar,
         name="resena_moderar"),
    # Bloque D: tablero de aprendizaje de la IA.
    path("panel/ia/", views.admin_ia, name="admin_ia"),
    # Bloque I: aprobar/rechazar habilidad postulada.
    path("panel/documentos/decidir/", views.documento_decidir,
         name="documento_decidir"),
    path("panel/usuarios/", views.admin_usuarios, name="admin_usuarios"),
    path("panel/reportes/", views.admin_reportes, name="admin_reportes"),
    # Notificaciones (FN-19)
    path("notificaciones/", views.notificaciones, name="notificaciones"),
    path("notificaciones/<int:pk>/leer/", views.notificacion_leer,
         name="notificacion_leer"),
]
