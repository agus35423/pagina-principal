from django.contrib.auth.backends import ModelBackend

from .models import PerfilUsuario


class TallerAdminBackend(ModelBackend):
    def has_perm(self, user_obj, perm, obj=None):
        if self._es_administrador_taller(user_obj):
            return True
        return super().has_perm(user_obj, perm, obj)

    def has_module_perms(self, user_obj, app_label):
        if self._es_administrador_taller(user_obj):
            return True
        return super().has_module_perms(user_obj, app_label)

    @staticmethod
    def _es_administrador_taller(user_obj):
        return bool(
            user_obj.is_authenticated
            and PerfilUsuario.objects.filter(
                usuario_id=user_obj.pk,
                rol="administrador",
            ).exists()
        )
