from rest_framework import permissions


class IsAdminOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to access it.
    """

    def has_object_permission(self, request, view):

        return request.user and request.user.is_staff