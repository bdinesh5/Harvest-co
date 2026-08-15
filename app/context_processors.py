from .models import Wishlist, Cart


def wishlist_count(request):
    if request.user.is_authenticated:
        count = Wishlist.objects.filter(user=request.user).count()
    else:
        count = 0
    return {'wishlist_count': count}


def cart_count(request):
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            count = cart.get_count()
        except Cart.DoesNotExist:
            count = 0
    else:
        count = 0
    return {'cart_count': count}
