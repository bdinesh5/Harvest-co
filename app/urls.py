from django.urls import path
from . import views

urlpatterns = [
    path('',                                      views.home,             name='home'),
    path('marketplace/',
         views.marketplace,      name='marketplace'),
    path('product/<int:product_id>/',
         views.product_detail,   name='product_detail'),

    # Cart
    path('cart/',
         views.cart,             name='cart'),
    path('cart/add/<int:product_id>/',
         views.add_to_cart,      name='add_to_cart'),
    path('cart/update/<int:item_id>/',
         views.update_cart,      name='update_cart'),
    path('cart/remove/<int:item_id>/',
         views.remove_from_cart, name='remove_from_cart'),

    # Checkout & Orders
    path('checkout/',
         views.checkout,         name='checkout'),
    path('place-order/',
         views.place_order,      name='place_order'),
    path('order/success/<int:order_id>/',
         views.order_success,    name='order_success'),
    path('orders/',
         views.orders,           name='orders'),
    path('orders/<int:order_id>/',
         views.order_detail,     name='order_detail'),
    path('orders/<int:order_id>/invoice/',
         views.order_pdf,        name='order_pdf'),

    # Wishlist
    path('wishlist/',
         views.wishlist,         name='wishlist'),
    path('wishlist/toggle/<int:product_id>/',
         views.toggle_wishlist,  name='toggle_wishlist'),

    # Auth
    path('about/',
         views.about,            name='about'),
    path('login/',
         views.login,            name='login'),
    path('signup/',
         views.signup,           name='signup'),
    path('logout/',
         views.logout,           name='logout'),
    path('profile/',
         views.profile,          name='profile'),
]
