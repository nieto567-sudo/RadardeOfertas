"""
Automatic product category classifier.

Assigns a human-readable Spanish category to a product based on keyword
matching against the product name.  Updates ``Product.category`` only when
the field is empty, so manual overrides are preserved.

Classification is pure keyword lookup — fast, deterministic, and easy to
extend.  No ML dependencies required.

Usage
-----
::

    from services.product_classifier import classify_product, update_product_category

    # Just get a category string
    cat = classify_product("iPhone 15 Pro Max 256GB")
    # → "Celulares y Smartphones"

    # Update ORM instance (no-op if category already set)
    changed = update_product_category(product, data)
"""
from __future__ import annotations

from database.models import Product
from scrapers.base import ProductData

# Ordered rules: (category_name, [keywords]).
# First match wins; all comparisons are lowercased.
_RULES: list[tuple[str, list[str]]] = [
    (
        "Celulares y Smartphones",
        [
            "iphone", "samsung galaxy", "xiaomi redmi", "redmi note",
            "poco x", "pixel ", "motorola moto", "smartphone", "celular",
            "teléfono móvil", "android phone", "5g phone",
        ],
    ),
    (
        "Gaming y Videojuegos",
        [
            "playstation", "ps5", "ps4", "ps3",
            "xbox series", "xbox one", "nintendo switch",
            "game boy", "gaming headset", "silla gamer",
            "teclado gamer", "mouse gamer", "control inalámbrico",
            "videojuego", "consola de", "mando de juego",
        ],
    ),
    (
        "Laptops y Computadoras",
        [
            "laptop", "macbook", "notebook", "chromebook",
            "computadora de escritorio", "pc gamer", "all-in-one pc",
            "procesador intel", "procesador amd", "tarjeta de video",
            "ram ddr", "ssd nvme", "disco duro interno",
        ],
    ),
    (
        "Televisores y Audio",
        [
            "smart tv", "televisor", "television", "monitor gaming",
            "oled tv", "qled tv", "4k uhd", "8k tv",
            "soundbar", "barra de sonido", "bocina bluetooth",
            "altavoz portátil", "audífonos", "auriculares bluetooth",
            "airpods", "headphones", "earbuds",
        ],
    ),
    (
        "Tablets y E-readers",
        [
            "ipad", "tablet samsung", "kindle", "e-reader",
            "galaxy tab", "tablet android",
        ],
    ),
    (
        "Fotografía y Video",
        [
            "cámara", "camara reflex", "canon eos", "nikon d",
            "sony alpha", "gopro", "dji drone", "lente 50mm",
            "objetivo fotográfico",
        ],
    ),
    (
        "Electrodomésticos",
        [
            "lavadora", "refrigerador", "microondas", "licuadora",
            "cafetera", "tostadora", "freidora de aire", "aspiradora",
            "plancha de vapor", "secadora de ropa", "estufa",
            "horno de microondas", "lavavajillas", "aire acondicionado",
        ],
    ),
    (
        "Ropa y Accesorios",
        [
            "camisa", "pantalón", "vestido", "zapato", "tenis nike",
            "tenis adidas", "bolsa de mano", "mochila escolar",
            "gorra", "jersey", "sudadera", "playera", "chamarra",
            "bota", "sandalias", "calcetines",
        ],
    ),
    (
        "Juguetes y Bebés",
        [
            "juguete", "lego", "barbie", "hot wheels", "funko pop",
            "muñeca", "peluche", "pañal", "cochecito", "biberón",
        ],
    ),
    (
        "Deportes y Fitness",
        [
            "bicicleta", "patines", "caminadora", "pesas",
            "yoga mat", "pelota de futbol", "balón de basketball",
            "raqueta de tenis", "traje de natación",
        ],
    ),
    (
        "Hogar y Muebles",
        [
            "sillón", "sofá", "cama matrimonial", "colchón",
            "escritorio", "silla de oficina", "lámpara", "cortina",
            "almohada", "toalla", "vajilla", "sartén", "olla express",
        ],
    ),
    (
        "Belleza y Salud",
        [
            "perfume", "crema hidratante", "shampoo", "maquillaje",
            "vitamina", "suplemento", "termómetro digital", "mascarilla",
            "secador de pelo", "plancha de cabello",
        ],
    ),
    (
        "Herramientas y Construcción",
        [
            "taladro", "sierra circular", "martillo", "destornillador",
            "pintura para pared", "cemento", "llave inglesa",
        ],
    ),
    (
        "Libros y Educación",
        [
            "libro", "novela", "enciclopedia", "manual de",
            "diccionario", "atlas",
        ],
    ),
    (
        "Mascotas",
        [
            "alimento para perro", "alimento para gato",
            "acuario", "collera para", "cama para perro",
        ],
    ),
]

_DEFAULT_CATEGORY = "General"


def classify_product(name: str) -> str:
    """
    Return the best-matching Spanish category label for a product *name*.

    Falls back to ``"General"`` when no keyword matches.
    """
    name_lower = name.lower()
    for category, keywords in _RULES:
        if any(kw in name_lower for kw in keywords):
            return category
    return _DEFAULT_CATEGORY


def update_product_category(product: Product, data: ProductData) -> bool:
    """
    Assign an auto-classified category to *product* if it does not already
    have one.

    Returns ``True`` when the category was updated, ``False`` when it was
    already set (preserving manual overrides).
    """
    if product.category:
        return False
    product.category = classify_product(data.name)
    return True
