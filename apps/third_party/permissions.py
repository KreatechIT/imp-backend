from rest_framework import permissions


class IsKocMember(permissions.BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_member):
            return False
        member = request.user.member
        return bool(member.role and member.role.name == "koc")
