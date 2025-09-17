# apps/store/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdminOrReadOnly(BasePermission):
    """
    GET/HEAD/OPTIONS — hamma uchun.
    POST — authenticated foydalanuvchilar (agar xohlasangiz restriction qo'shish mumkin).
    PUT/PATCH/DELETE — faqat admin (is_staff).
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if request.method == "POST":
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)


class IsOwnerOrAdmin(BasePermission):
    """
    Ob'ekt egasi yoki admin bo'lsa o'zgartirishga ruxsat.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user and request.user.is_staff:
            return True
        # ko'p modellar user maydoniga ega bo'ladi (order.user, cart.user)
        return hasattr(obj, "user") and obj.user == request.user
