import requests
import time
import os
import html
import re
import unicodedata
from xml.sax.saxutils import escape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# CONFIGURACIÓN (Open API - Basic Auth)
# ==========================================
API_USER = os.environ.get('FOURTHWALL_API_USER')
API_PASS = os.environ.get('FOURTHWALL_API_PASS')
STORE_URL = 'https://opispot.com' 
BASE_API_URL = 'https://api.fourthwall.com/open-api/v1.0'

session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 429, 500, 502, 503, 504 ])
session.mount('https://', HTTPAdapter(max_retries=retries))
session.auth = (API_USER, API_PASS)
session.headers.update({
    'Content-Type': 'application/json',
    'Accept': 'application/json'
})

# ==========================================
# TRADUCCIÓN DE COLORES PARA SEO EN ESPAÑOL
# ==========================================
COLORES_ESPANOL = {
    "black": "Negro", "dark chocolate": "Marrón Chocolate", "navy": "Azul Marino",
    "true navy": "Azul Marino", "purple": "Morado", "maroon": "Granate",
    "forest green": "Verde Bosque", "heather navy": "Azul Marino Jaspeado",
    "dark heather grey": "Gris Oscuro", "dark heather": "Gris Oscuro",
    "graphite heather": "Gris Grafito", "royal": "Azul Real",
    "military green": "Verde Militar", "charcoal": "Gris Carbón",
    "sapphire": "Azul Zafiro", "heather indigo": "Índigo Jaspeado",
    "heather red": "Rojo Jaspeado", "red": "Rojo", "brick": "Rojo Ladrillo",
    "berry": "Frambuesa", "flo blue": "Azul Eléctrico", "watermelon": "Rosa Sandía",
    "grey": "Gris", "violet": "Violeta", "butter": "Amarillo Pastel",
    "heather royal": "Azul Real Jaspeado", "kelly green": "Verde Esmeralda",
    "heliconia": "Rosa Fucsia", "orange": "Naranja", "tropical blue": "Azul Tropical",
    "irish green": "Verde Vivo", "jade dome": "Verde Jade",
    "heather irish green": "Verde Vivo Jaspeado", "coral silk": "Coral",
    "sand": "Arena", "sport grey": "Gris Jaspeado", "light blue": "Azul Claro",
    "daisy": "Amarillo", "ice grey": "Gris Claro", "white": "Blanco",
    "cornsilk": "Beige", "natural": "Crudo / Natural"
}

CATEGORIAS = {
    "apparel": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "is_apparel": True, "is_art": False},
    "drinkware": {"gpc": "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs", "is_apparel": False, "is_art": False},
    "art": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "is_apparel": False, "is_art": True},
    "stationery": {"gpc": "Office Supplies > Office Instruments > Notebooks & Notepads", "is_apparel": False, "is_art": False},
    "sticker": {"gpc": "Arts & Entertainment > Hobbies & Creative Arts > Arts & Crafts > Art & Crafting Materials > Embellishments & Trims > Stickers", "is_apparel": False, "is_art": False},
    "accessories": {"gpc": "Electronics > Electronics Accessories > Computer Components > Computer Accessories > Laptop Accessories > Laptop Cases", "is_apparel": False, "is_art": False}
}

CATEGORIA_DEFAULT = {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "is_apparel": True, "is_art": False}

def safe_escape(val):
    if not val: return ""
    if isinstance(val, dict): val = val.get('name', val.get('value', str(val)))
    elif isinstance(val, list): val = ", ".join(str(v) for v in val)
    return escape(str(val))

def clean_text(text):
    if not text: return ""
    text = html.unescape(str(text))
    text = html.unescape(text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[\u2600-\u27BF]', '', text)
    text = re.sub(r'[\U00010000-\U0010FFFF]', '', text)
    text = text.replace("Copy of ", "").replace("Copy of", "")
    return " ".join(text.split()).strip()

def remove_accents(text):
    if not text: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(text)) if unicodedata.category(c) != 'Mn')

# --- CORRECCIÓN DEL STOCK PARA PRINT-ON-DEMAND ---
def extract_availability(product_state, variant_stock):
    if isinstance(product_state, dict) and product_state.get('type') == 'SOLD_OUT': 
        return 'out of stock'
    
    if isinstance(variant_stock, dict):
        stock_type = variant_stock.get('type')
        if stock_type == 'UNLIMITED':
            return 'in stock'
        if stock_type == 'LIMITED':
            return 'in stock' if variant_stock.get('inStock', 0) > 0 else 'out of stock'
            
    return 'in stock'

def extract_price(data_dict):
    if not data_dict or not isinstance(data_dict, dict): return "0.00 USD"
    price_obj = data_dict.get('unitPrice') or data_dict.get('price')
    if isinstance(price_obj, dict):
        val = price_obj.get('value', price_obj.get('amount', '0.00'))
        curr = price_obj.get('currency', price_obj.get('currencyCode', 'USD'))
        return f"{val} {curr}"
    return "0.00 USD"

def clasificar_producto(variant, title):
    t = title.lower()
    if any(w in t for w in ['sticker', 'pegatina']): return CATEGORIAS["sticker"], "Título (Sticker)"
    if any(w in t for w in ['taza', 'mug', 'vaso']): return CATEGORIAS["drinkware"], "Título (Taza/Mug)"
    if any(w in t for w in ['libreta', 'notebook', 'cuaderno']): return CATEGORIAS["stationery"], "Título (Libreta)"
    if any(w in t for w in ['funda', 'case', 'sleeve', 'fundas para portátil']): return CATEGORIAS["accessories"], "Título (Accesorio)"
    if any(w in t for w in ['poster', 'print', 'lienzo', 'cuadro', 'canvas']): return CATEGORIAS["art"], "Título (Arte)"
    if any(w in t for w in ['camiseta', 'shirt', 'hoodie', 'sudadera', 'gorra', 'ropa', 'top', 'vestido']): return CATEGORIAS["apparel"], "Título (Ropa)"
    
    attrs = variant.get('attributes', {})
    size_obj = attrs.get('size', {})
    size_name = str(size_obj.get('name', '')).lower().strip() if isinstance(size_obj, dict) else str(size_obj).lower().strip()
    if size_name:
        if size_name in ['xs', 's', 'm', 'l', 'xl', 'xxl', '2xl', '3xl', '4xl', '5xl']: return CATEGORIAS["apparel"], f"Atributo Talla ({size_name})"
    return CATEGORIA_DEFAULT, "Valor por Defecto"

def determinar_genero(title):
    t_lower = title.lower()
    if any(w in t_lower for w in ['mujer', 'chica', 'women', 'ladies', 'crop top', 'vestido', 'falda']): return "female"
    elif any(w in t_lower for w in ['hombre', 'chico', 'men', 'mens']): return "male"
    return "unisex"

def get_all_products_summary():
    products, page, total_pages = [], 0, 1
    print("📦 Descargando catálogo...")
    while page < total_pages:
        url = f"{BASE_API_URL}/products?page={page}&size=50"
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            items = data.get('results', [])
            if not items: break
            products.extend(items)
            total_pages = data.get('totalPages', 1)
            page += 1
        else: break
    return products

def build_xml_feed():
    summary_products = get_all_products_summary()
    pinterest_items, google_items, bing_items = [], [], []

    for summary in summary_products:
        product_id = summary.get('id')
        title = clean_text(summary.get('name', 'Producto'))
        slug = summary.get('slug', '')
        detailed_product = session.get(f"{BASE_API_URL}/products/{product_id}").json()
        
        if detailed_product.get('access', {}).get('type', 'PUBLIC') != 'PUBLIC': continue

        all_image_urls = [img.get('url') for img in detailed_product.get('images', []) if isinstance(img, dict)]
        if not all_image_urls: continue

        clean_description = clean_text(detailed_product.get('description', '')) or title
        product_link = f"{STORE_URL}/products/{slug}"
        product_state = detailed_product.get('state', {})
        variants = detailed_product.get('variants', [])
        base_price_str = extract_price(detailed_product)

        def create_xml_item(v_id, v_group_id, v_title, v_link, v_img, v_price, v_availability, v_cat, v_color=None, v_size=None, v_sku=None, v_images=None, v_gender=None):
            xml = f"""
        <item>
            <g:id>{safe_escape(v_id)}</g:id>
            <g:item_group_id>{safe_escape(v_group_id)}</g:item_group_id>
            <g:title><![CDATA[{v_title[:150]}]]></g:title>
            <!-- DESC_PLACEHOLDER -->
            <g:link>{safe_escape(v_link)}</g:link>
            <g:image_link>{safe_escape(v_img)}</g:image_link>"""
            if v_images:
                for add_img in v_images[1:11]:
                    if add_img != v_img: xml += f"\n            <g:additional_image_link>{safe_escape(add_img)}</g:additional_image_link>"
            xml += f"""
            <g:price>{safe_escape(v_price)}</g:price>
            <g:availability>{v_availability}</g:availability>
            <g:condition>new</g:condition>
            <g:brand>Opispot</g:brand>
            <g:identifier_exists>no</g:identifier_exists>
            <g:google_product_category><![CDATA[{v_cat}]]></g:google_product_category>"""
            if v_color: xml += f"\n            <g:color><![CDATA[{v_color}]]></g:color>"
            if v_size: xml += f"\n            <g:size><![CDATA[{v_size}]]></g:size>"
            if v_gender: xml += f"\n            <g:gender>{v_gender}</g:gender>\n            <g:age_group>adult</g:age_group>"
            xml += "\n        </item>"
            return xml

        if not variants:
            cat_obj, _ = clasificar_producto({}, title)
            gender = determinar_genero(title) if cat_obj['is_apparel'] else None
            
            prefijo = "Ropa Urbana " + ("Unisex" if gender=="unisex" else ("Hombre" if gender=="male" else "Mujer")) + " - " if cat_obj['is_apparel'] else ("Póster Decorativo - " if cat_obj['is_art'] else "")
            seo_title = f"{prefijo}{title}"
            
            desc_unica = f"{seo_title}. Diseño original de la marca independiente Opispot. {clean_description}"
            
            xml = create_xml_item(product_id, product_id, seo_title, product_link, all_image_urls[0], base_price_str, extract_availability(product_state, {}), cat_obj['gpc'], v_images=all_image_urls, v_gender=gender)
            
            pinterest_items.append(xml.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{desc_unica[:500]}]]></g:description>"))
            google_items.append(xml.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{desc_unica[:5000]}]]></g:description>"))
            bing_base = remove_accents(xml)
            bing_desc = remove_accents(desc_unica[:10000])
            bing_items.append(bing_base.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{bing_desc}]]></g:description>"))
        else:
            for variant in variants:
                v_id = variant.get('id', product_id)
                v_name = clean_text(variant.get('name', ''))
                v_name_clean = re.sub(re.escape(title), '', v_name, flags=re.IGNORECASE).strip(' -')
                cat_obj, _ = clasificar_producto(variant, title)
                
                color_raw = variant.get('attributes', {}).get('color', {}).get('name', '')
                color_es = COLORES_ESPANOL.get(color_raw.lower(), color_raw)
                gender = determinar_genero(f"{title} {v_name_clean}") if cat_obj['is_apparel'] else None
                prefijo = "Ropa Urbana " + ("Unisex" if gender=="unisex" else ("Hombre" if gender=="male" else "Mujer")) + " - " if cat_obj['is_apparel'] else ("Póster Decorativo - " if cat_obj['is_art'] else "")
                
                full_title = f"{prefijo}{title} Color {color_es}" if color_es else f"{prefijo}{title}"
                if v_name_clean and color_raw.lower() not in v_name_clean.lower():
                    full_title += f" - {v_name_clean}"
                
                desc_unica = f"{full_title}. Diseño original de la marca independiente Opispot. Detalles: {clean_description}"
                
                v_images = [img.get('url') for img in variant.get('images', [])] or all_image_urls
                v_img = variant.get('thumbnailImage', {}).get('url') or v_images[0]
                
                xml = create_xml_item(v_id, product_id, full_title, f"{product_link}?variant={v_id}", v_img, extract_price(variant), extract_availability(product_state, variant.get('stock')), cat_obj['gpc'], v_color=color_es, v_size=variant.get('attributes',{}).get('size',{}).get('name'), v_images=v_images, v_gender=gender)
                
                pinterest_items.append(xml.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{desc_unica[:500]}]]></g:description>"))
                google_items.append(xml.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{desc_unica[:5000]}]]></g:description>"))
                bing_base = remove_accents(xml)
                bing_desc = remove_accents(desc_unica[:10000])
                bing_items.append(bing_base.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{bing_desc}]]></g:description>"))
        
        print(f"✔️ {title[:30]}... procesado")

    # Guardado final
    def write_feed(filename, items_list):
        with open(filename, 'w', encoding='utf-8-sig') as f:
            f.write(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel><title>Opispot</title><link>{STORE_URL}</link>{"".join(items_list)}</channel></rss>')

    write_feed('pinterest_feed.xml', pinterest_items)
    write_feed('google_feed.xml', google_items)
    write_feed('bing_feed.xml', bing_items)
    print("✅ Feeds generados con éxito con Títulos y Descripciones SEO Únicas, y Stock ilimitado corregido.")

if __name__ == "__main__":
    if not API_USER or not API_PASS: print("❌ Credenciales faltantes")
    else: build_xml_feed()
