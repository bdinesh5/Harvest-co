from django import template

register = template.Library()


@register.inclusion_tag('partials/stars.html')
def stars(rating, max_stars=5):
    """
    Renders dynamic SVG stars based on a float rating.
    Usage: {% load star_tags %} then {% stars product.rating %}
    Supports full, half, and empty stars.
    """
    full  = int(rating)                    # e.g. 4.5 → 4
    half  = 1 if (rating - full) >= 0.5 else 0   # e.g. 4.5 → 1
    empty = max_stars - full - half        # e.g. 5 - 4 - 1 → 0

    return {
        'full':      range(full),
        'half':      half,
        'empty':     range(empty),
        'rating':    rating,
        'max_stars': max_stars,
    }