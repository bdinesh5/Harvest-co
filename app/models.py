from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    user    = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar  = models.ImageField(upload_to='avatars/', blank=True, null=True)
    phone   = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city    = models.CharField(max_length=100, blank=True)
    state   = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.user.username}'s profile"


class Category(models.Model):
    name        = models.CharField(max_length=100)
    image       = models.ImageField(upload_to='categories/')
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    category    = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name        = models.CharField(max_length=100)
    image       = models.ImageField(upload_to='subcategories/', blank=True, null=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Sub Categories'
        ordering = ['name']

    def __str__(self):
        return f"{self.category.name} → {self.name}"


class Product(models.Model):
    category    = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    subcategory = models.ForeignKey(SubCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    name        = models.CharField(max_length=200)
    image       = models.ImageField(upload_to='products/')
    description = models.TextField(blank=True)
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    rating      = models.FloatField(default=0)
    is_sale     = models.BooleanField(default=False)
    is_limited  = models.BooleanField(default=False)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return self.name


class Wishlist(models.Model):
    user     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product  = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering        = ['-added_at']

    def __str__(self):
        return f"{self.user.username} ♡ {self.product.name}"


class Cart(models.Model):
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    updated_at = models.DateTimeField(auto_now=True)

    def get_total(self):
        total = self.items.aggregate(
            total=models.Sum(models.F('quantity') * models.F('product__price'), output_field=models.DecimalField())
        )['total']
        return total if total is not None else 0

    def get_count(self):
        count = self.items.aggregate(total_qty=models.Sum('quantity'))['total_qty']
        return count if count is not None else 0

    def __str__(self):
        return f"{self.user.username}'s cart"



class CartItem(models.Model):
    cart     = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product  = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product')

    def get_subtotal(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.quantity} × {self.product.name}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped',   'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_CHOICES = [
        ('cod',   'Cash on Delivery'),
        ('gpay',  'Google Pay'),
        ('card',  'Credit / Debit Card'),
        ('upi',   'UPI'),
    ]

    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method   = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='cod')
    payment_status   = models.CharField(max_length=20, default='pending')  # pending / paid / failed
    total            = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_charge  = models.DecimalField(max_digits=6, decimal_places=2, default=49)
    grand_total      = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # delivery address snapshot
    full_name        = models.CharField(max_length=200, blank=True)
    phone            = models.CharField(max_length=20, blank=True)
    address          = models.TextField(blank=True)
    city             = models.CharField(max_length=100, blank=True)
    state            = models.CharField(max_length=100, blank=True)
    pincode          = models.CharField(max_length=10, blank=True)

    # tracking
    tracking_number  = models.CharField(max_length=50, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} — {self.user.username}"

    def get_status_steps(self):
        """Returns list of (step_name, label, completed, active)"""
        steps  = ['pending', 'confirmed', 'shipped', 'out_for_delivery', 'delivered']
        labels = ['Order Placed', 'Confirmed', 'Shipped', 'Out for Delivery', 'Delivered']
        current_idx = steps.index(self.status) if self.status in steps else 0
        result = []
        for i, (s, l) in enumerate(zip(steps, labels)):
            result.append({
                'key':       s,
                'label':     l,
                'completed': i < current_idx,
                'active':    i == current_idx,
            })
        return result


class OrderItem(models.Model):
    order    = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product  = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    name     = models.CharField(max_length=200)   # snapshot name
    image    = models.ImageField(upload_to='order_items/', blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    price    = models.DecimalField(max_digits=10, decimal_places=2)

    def get_subtotal(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.quantity} × {self.name}"