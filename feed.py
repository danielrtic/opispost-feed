import requests
import time
import os
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

CATEGORIAS = {
    "apparel": {"gpc": "Apparel & Accessories > Clothing", "is_apparel": True},
    "drinkware": {"gpc": "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs", "is_apparel": False},
    "art": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "is_apparel": False},
    "stationery": {"gpc": "Office Supplies > Office Instruments > Notebooks & Notepads", "is_apparel": False},
    "sticker": {"gpc": "Arts & Entertainment > Hobbies & Creative Arts > Arts & Crafts > Art & Crafting Materials > Embellishments & Trims > Stickers", "is_apparel": False}
}
CATEGORIA_DEFAULT = {"gpc": "Apparel & Accessories", "is_apparel": True}

def safe_escape(val):
    if not val: return ""
    return escape(str(val))

def extract_availability(product_state, variant_stock):
    """Calcula disponibilidad usando los esquemas OfferStateV1 y StockV1 de Fourthwall"""
    if isinstance(product_state, dict) and product_state.get('type') == 'SOLD_OUT':
        return 'out of stock'
    
    if isinstance(variant_stock, dict):
        stock_type = variant_stock.get('type')
        if stock_type == 'UNLIMITED':
            return 'in stock'
        if stock_type == 'LIMITED':
            in_stock = variant_stock.get('inStock', 0)
            return 'in stock' if in_stock > 0 else 'out of stock'
            
    return 'in stock'

def clasificar_por_fisica(variant, title):
    """Clasificación basada en OfferVariantAbstractV1 (Dimensiones, Peso, Atributos)"""
    
    # 1. Por Talla Textil / Onzas (Atributos)
    attrs = variant.get('attributes', {})
    size_obj = attrs.get('size', {})
    size_name = str(size_obj.get('name', '')).lower() if isinstance(size_obj, dict) else str(size_obj).lower()
    
    if size_name:
        if 'oz' in size_name or 'onza' in size_name: return CATEGORIAS["drinkware"], f"Tamaño ({size_name})"
        if size_name in ['xs', 's', 'm', 'l', 'xl', 'xxl', '2xl', '3xl', '4xl', 'small', 'medium', 'large']: 
            return CATEGORIAS["apparel"], f"Talla Textil ({size_name})"
        if 'x' in size_name and ('"' in size_name or 'cm' in size_name): 
            return CATEGORIAS["art"], f"Medidas de Arte ({size_name})"

    # 2. Por Dimensiones Exactas (Si existe en OfferVariantV1.dimensions)
    dims = variant.get('dimensions', {})
    if dims and isinstance(dims, dict):
        # Si tiene dimensiones exactas de longitud/anchura sin ser ropa, suele ser pósters/cuadros/libretas
        return CATEGORIAS["art"], "Por dimensiones físicas declaradas"

    # 3. Respaldo Final por Título (Requerido ya que la API oculta la plantilla)
    t = title.lower()
    if any(w in t for w in ['taza', 'mug', 'vaso']): return CATEGORIAS["drinkware"], "Título (Taza/Mug)"
    if any(w in t for w in ['sticker', 'pegatina']): return CATEGORIAS["sticker"], "Título (Sticker)"
    if any(w in t for w in ['libreta', 'notebook', 'cuaderno']): return CATEGORIAS["stationery"], "Título (Libreta)"
    if any(w in t for w in ['poster', 'print', 'lienzo', 'cuadro']): return CATEGORIAS["art"], "Título (Arte)"
    if any(w in t for w in ['camiseta', 'shirt', 'hoodie', 'sudadera']): return CATEGORIAS["apparel"], "Título (Ropa)"

    return CATEGORIA_DEFAULT, "Valor por Defecto"

def get_all_products_summary():
    products = []
    page = 1
    total_pages = 1
    print("📦 Conectando a Fourthwall Open API...")
    
    while page <= total_pages:
        url = f"{BASE_API_URL}/products?page={page}&limit=50"
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            items = data.get('results', data.get('data', []))
            products.extend(items)
            total_pages = data.get('totalPages', data.get('pagination', {}).get('total_pages', 1))
            page += 1
        else:
            break
    return products

def build_xml_feed():
    summary_products = get_all_products_summary()
    if not summary_products:
        print("⚠️ No se encontraron productos.")
        return

    xml_items = []
    print(f"🔍 Procesando {len(summary_products)} productos (Deep Fetch para extraer MPN/Peso/Variantes)...")

    for summary in summary_products:
        product_id = summary.get('id')
        title = summary.get('name', 'Producto sin nombre')
        slug = summary.get('slug', '')
        
        # Obtenemos el OfferFullV1
        url_detail = f"{BASE_API_URL}/products/{product_id}"
        resp_detail = session.get(url_detail)
        product = resp_detail.json().get('data', summary) if resp_detail.status_code == 200 else summary

        raw_desc = product.get('description', '')
        clean_desc = raw_desc.replace('<p>', '').replace('</p>', '').replace('<br>', ' ').strip()
        if not clean_desc: clean_desc = title
        product_link = f"{STORE_URL}/products/{slug}"
        
        product_state = product.get('state', {})

        # Extraer todas las imágenes del producto
        all_image_urls = []
        for img in product.get('images', []):
            if isinstance(img, dict) and img.get('url'):
                all_image_urls.append(img.get('url'))

        variants = product.get('variants', [])
        
        for variant in variants:
            variant_id = variant.get('id', product_id)
            v_name = variant.get('name', '')
            full_title = f"{title} - {v_name}" if v_name else title
            
            # Clasificación Inteligente
            classification, razon = clasificar_por_fisica(variant, title)
            
            # Precio (OfferVariantV1.unitPrice)
            price_obj = variant.get('unitPrice', {})
            price_str = f"{price_obj.get('value', '0.00')} {price_obj.get('currency', 'USD')}"
            
            # Disponibilidad
            availability = extract_availability(product_state, variant.get('stock'))
            
            # Atributos oficiales
            attrs = variant.get('attributes', {})
            color_obj = attrs.get('color', {})
            color_name = color_obj.get('name', '') if isinstance(color_obj, dict) else str(color_obj)
            
            size_obj = attrs.get('size', {})
            size_name = size_obj.get('name', '') if isinstance(size_obj, dict) else str(size_obj)
            
            # SKUs y Peso (OfferVariantV1.sku / OfferVariantV1.weight)
            sku = variant.get('sku', '')
            weight_obj = variant.get('weight', {})
            shipping_weight = ""
            if isinstance(weight_obj, dict) and weight_obj.get('value'):
                shipping_weight = f"{weight_obj.get('value')} {weight_obj.get('unit', 'kg')}"
                
            # Imágenes (Imagen principal de la variante o fallback al producto)
            var_thumb = variant.get('thumbnailImage', {})
            main_image_link = var_thumb.get('url') if isinstance(var_thumb, dict) and var_thumb.get('url') else (all_image_urls[0] if all_image_urls else "")
            
            # Construcción del nodo
            item_xml = f"""
        <item>
            <g:id>{safe_escape(variant_id)}</g:id>
            <g:item_group_id>{safe_escape(product_id)}</g:item_group_id>
            <g:title>{safe_escape(full_title[:150])}</g:title>
            <g:description>{safe_escape(clean_desc[:500])}</g:description>
            <g:link>{safe_escape(f"{product_link}?variant={variant_id}")}</g:link>
            <g:image_link>{safe_escape(main_image_link)}</g:image_link>"""
            
            for add_img in all_image_urls[1:11]:
                item_xml += f"\n            <g:additional_image_link>{safe_escape(add_img)}</g:additional_image_link>"

            item_xml += f"""
            <g:price>{safe_escape(price_str)}</g:price>
            <g:availability>{availability}</g:availability>
            <g:condition>new</g:condition>
            <g:brand>Opispot</g:brand>
            <g:google_product_category>{safe_escape(classification['gpc'])}</g:google_product_category>"""
            
            if color_name: item_xml += f"\n            <g:color>{safe_escape(color_name)}</g:color>"
            if size_name: item_xml += f"\n            <g:size>{safe_escape(size_name)}</g:size>"
            if sku: item_xml += f"\n            <g:mpn>{safe_escape(sku)}</g:mpn>"
            if shipping_weight: item_xml += f"\n            <g:shipping_weight>{safe_escape(shipping_weight)}</g:shipping_weight>"
            
            if classification['is_apparel']:
                item_xml += f"\n            <g:gender>unisex</g:gender>\n            <g:age_group>adult</g:age_group>"
                
            item_xml += "\n        </item>"
            xml_items.append(item_xml)
            
        time.sleep(0.05) # Pausa amigable

    final_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
    <channel>
        <title>Opispot</title>
        <link>{STORE_URL}</link>
        <description>Catálogo oficial de productos para Pinterest</description>
        {''.join(xml_items)}
    </channel>
</rss>"""

    with open('pinterest_feed.xml', 'w', encoding='utf-8') as f:
        f.write(final_xml)
    print(f"✅ Feed XML generado exitosamente con {len(xml_items)} variantes totales.")

if __name__ == "__main__":
    if not API_USER or not API_PASS:
        print("❌ Error: Faltan las credenciales.")
    else:
        build_xml_feed()
