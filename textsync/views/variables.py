"""Per-user variable CRUD — backs the [[var:name]] resolver in the extension.

Scoping rule (enforced at queryset + create level): every operation reads /
writes only the requesting user's variables. There's no admin override here;
superusers manage other users' vars via Django admin if ever needed.
"""

from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError

from ..models import UserVariable
from ..serializers import UserVariableSerializer


class UserVariableViewSet(viewsets.ModelViewSet):
    """
    GET    /api/user-variables/         — list current user's variables
    POST   /api/user-variables/         — create one
    PUT    /api/user-variables/{id}/    — replace
    PATCH  /api/user-variables/{id}/    — partial update
    DELETE /api/user-variables/{id}/    — remove

    Names are unique per user (DB constraint). Conflicting POST surfaces
    as a 400 with a friendly message instead of the bare IntegrityError.
    """

    serializer_class = UserVariableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Strict scope — never expose another user's vars even by id guess.
        return UserVariable.objects.filter(user=self.request.user).order_by("name")

    def perform_create(self, serializer):
        name = serializer.validated_data.get("name")
        if UserVariable.objects.filter(user=self.request.user, name=name).exists():
            raise ValidationError({"name": f"Variable '{name}' already exists."})
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        new_name = serializer.validated_data.get("name")
        if new_name and new_name != serializer.instance.name:
            clash = (
                UserVariable.objects.filter(user=self.request.user, name=new_name)
                .exclude(pk=serializer.instance.pk)
                .exists()
            )
            if clash:
                raise ValidationError(
                    {"name": f"Variable '{new_name}' already exists."}
                )
        serializer.save()
