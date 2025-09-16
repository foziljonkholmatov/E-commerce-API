from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.template.context_processors import request
from rest_framework import generics, viewsets, mixins
from django.contrib.auth import get_user_model
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from apps.store.models import CategoryModel, ProductModel, CartModel, CartItemModel, OrderModel, OrderItemModel
from apps.store.permissions import IsAdminOrReadOnly
from apps.store.serializers import RegisterSerializer, UserProfileSerializer, CategorySerializer, ProductSerializer, \
    CartSerializer, CartItemSerializer, OrderSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = CategoryModel.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'id'

class ProductViewSet(viewsets.ModelViewSet):
    queryset = ProductModel.objects.select_related('category').all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'price': ['gte', 'lte'],
        'category__id': ['exact']
    }
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at']

class CartViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        cart, _ = CartModel.objects.get_or_create(user=self.request.user)
        return cart
    @action(detail=False, method=['POST'])
    def add_item(self):
        cart = self.get_object()
        serializer = CartItemSerializer
        serializer.is_valid(raise_exception=True)
        prod = serializer.validated_data['product']
        qty = serializer.validated_data['quantity']
        if qty < 1:
            return Response({'Detail': 'quantity must be >=1'}, status=400)
        if prod.quantity < qty:
            return Response({'detail': 'Not enough stock'}, status=400)
        item, created = CartItemModel.objects.get_or_create(cart=cart, product=prod, defaults={'quantity': qty})
        if not created:
            new_qty = item.quantity + qty
            if prod.quantity < new_qty:
                return Response({'detail': 'Not enough stock for total quantity'}, status=400)
            item.quantity = new_qty
            item.save()
        return Response(CartSerializer(cart, context={'request': request}).data, status=201)

    @action(detail=True, methods=['patch'], url_path='items/(?P<item_id>[^/.]+)')
    def update_item(self, request, item_id=None):
        cart = self.get_object()
        item = get_object_or_404(CartItemModel, pk=item_id, cart=cart)
        qty = int(request.data.get('quantity', item.quantity))
        if qty < 1:
            item.delete()
            return Response({'detail': 'Item removed'}, status=204)
        if item.product.quantity < qty:
            return Response({'detail': 'Not enough stock'}, status=400)
        item.quantity = qty
        item.save()
        return Response(CartSerializer(cart).data)

    @action(detail=True, methods=['delete'], url_path='items/(?P<item_id>[^/.]+)')
    def delete_item(self, request, item_id=None):
        cart = self.get_object()
        item = get_object_or_404(CartItemModel, pk=item_id, cart=cart)
        item.delete()
        return Response(status=204)


class OrderViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff and self.action == 'admin_list':
            return OrderModel.objects.all().order_by('-created_at')
        return OrderModel.objects.filter(user=user).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='admin', permission_classes=[IsAuthenticated])
    def admin_list(self, request):
        if not request.user.is_staff:
            return Response(status=403)
        qs = OrderModel.objects.all().order_by('-created_at')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def create_order(self, request):
        cart, _ = CartModel.objects.get_or_create(user=request.user)
        items = cart.items.select_related('product').all()
        if not items.exists():
            return Response({'detail': 'Cart is empty'}, status=400)

        with transaction.atomic():
            total = Decimal('0.00')
            for it in items:
                if it.product.quantity < it.quantity:
                    return Response({'detail': f'Not enough stock for {it.product.name}'}, status=400)
                total += it.product.price * it.quantity

            order = OrderModel.objects.create(user=request.user, total=total)
            for it in items:
                OrderItemModel.objects.create(
                    order=order,
                    product=it.product,
                    quantity=it.quantity,
                    price=it.product.price
                )
                it.product.quantity = it.product.quantity - it.quantity
                it.product.save()
            items.delete()

        serializer = OrderSerializer(order, context={'request': request})
        return Response(serializer.data, status=201)


