from django.contrib import admin
from .models import Profile, Category, SubCategory, Product, Wishlist, Cart, CartItem, Order, OrderItem


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'city', 'state')
    search_fields = ('user__username', 'user__email')


class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    extra = 1
    fields = ('name', 'image', 'description')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    inlines = [SubCategoryInline]


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name', 'category__name')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'subcategory',
                    'price', 'rating', 'is_sale', 'is_limited')
    list_filter = ('category', 'subcategory', 'is_sale', 'is_limited')
    search_fields = ('name',)
    list_editable = ('price', 'is_sale', 'is_limited')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'added_at')
    list_filter = ('user',)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ('product', 'quantity')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_count', 'get_total', 'updated_at')
    search_fields = ('user__username',)
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('name', 'quantity', 'price')
    readonly_fields = ('name', 'price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'payment_method',
                    'payment_status', 'grand_total', 'created_at')
    list_filter = ('status', 'payment_method', 'payment_status')
    search_fields = ('user__username', 'full_name', 'phone')
    list_editable = ('status',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [OrderItemInline]
