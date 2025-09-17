from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.store.models import (CartModel, CategoryModel, ProductModel, CartItemModel,
                               OrderItemModel, OrderModel)

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def create(self, validated_data):
        print("VALIDATED DATA:", validated_data)  # 🔍 Debug
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        CartModel.objects.create(user=user)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'password', 'is_staff']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryModel
        fields = ['id', 'name', 'slug']


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=CategoryModel.objects.all(), source='category', write_only=True
    )

    class Meta:
        model = ProductModel
        fields = ('id', 'name', 'description', 'price', 'quantity',
                  'image', 'category', 'category_id', 'created_at')


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductModel.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = CartItemModel
        fields = ['id', 'product', 'product_id', 'quantity']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(read_only=True, many=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = CartModel
        fields = ['id', 'items', 'user', 'total']

    def get_total(self, obj):
        return obj.total()


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItemModel
        fields = ['id', 'product', 'quantity', 'price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(read_only=True, many=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = OrderModel
        fields = ('id', 'user', 'total', 'status', 'created_at', 'updated_at', 'items')
        read_only_fields = ('total', 'status', 'created_at', 'updated_at', 'items', 'user')


class CreateOrderSerializer(serializers.ModelSerializer):
    def validate(self, data):
        return data

    def create(self, validated_data):
        raise NotImplementedError('Use view to create order in a transaction')
