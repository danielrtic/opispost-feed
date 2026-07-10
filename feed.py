import requests
import time
import os
from xml.sax.saxutils import escape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# CONFIGURACIÓN (Lee las credenciales de GitHub Secrets)
# ==========================================
API_USER = os.environ.get('FOURTHWALL_API_USER')
API_PASS = os.environ.get('FOURTHWALL_API_PASS')

# ¡IMPORTANTE! Cambia esto por la URL real de tu tienda:
STORE_URL = 'https://tu-tienda.fourthwall.com' 

# URL corregida para la Open API de Fourthwall
BASE_API_URL = 'https://api.fourthwall.com/open-api/v1.0'

# Configuración de sesión y reintentos automáticos
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 429, 500, 502, 503, 504 ])
session.mount('https://', HTTPAdapter(max_retries=retries))

# >>> SOLUCIÓN: Autenticación Basic Auth (Usuario y Contraseña) <<<
session.auth = (API_USER, API_PASS)
session.headers.update({
    'Content-Type': 'application/json',
    'Accept': 'application/json'
})

def get_all_products():
    """Obtiene todos los productos paginados."""
    products = []
    page = 1
    total_pages = 1
    print("📦 Obteniendo catálogo completo...")
    
    while page <= total_pages:
        url = f"{BASE_API_URL}/products?page={page}&limit=50"
        response = session.get(url)
        
        if response.status_code == 200:
            data = response.json()
            products.extend(data.get('data', []))
            total_pages = data.get('pagination', {}).get('total_pages', 1)
            page += 1
        else:
            print(f"❌ Error API: {response.status_code} al llamar a {url}")
            print(f"Detalle: {response.text}")
            break
            
    return products

def categorize_product(title, tags, template_category):
    """Categorización inteligente para Google / Pinterest."""
    search_string = f"{title} {' '.join(tags)} {template_category}".lower()
    category = "Apparel & Accessories"
    gender = "unisex"
    age_group = "adult"
    is_apparel = True 

    if any(word in search_string for word in ['mug', 'taza', 'cup']):
        category = 'Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs'
        is_apparel = False
    elif any(word in search_string for word in ['poster', 'print', 'canvas']):
        category = 'Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork'
        is_apparel = False
    
    return {'gpc': category, 'gender': gender if is_apparel else '', 'age_group': age_group if is_apparel else '', 'is_apparel': is_apparel}

def build_xml_feed():
    products = get_all_products()
    if not products:
        print("⚠️ No se encontraron productos o falló la conexión.")
        return

    xml_items = []

    for product in products:
        product_id = product.get('id')
        details = session.get(f"{BASE_API_URL}/products/{product_id}").json().get('data', {})
        template_id = details.get('template_id')
        template = session.get(f"{BASE_API_URL}/product-templates/{template_id}").json().get('data', {}) if template_id else {}
        
        title = details.get('name', product.get('name', ''))
        tags = details.get('tags', [])
        template_category = template.get('category', 'Merch')
        classification = categorize_product(title, tags, template_category)
        
        description = details.get('description', '').replace('\n', ' ')
        product_link = f"{STORE_URL}/products/{details.get('slug', '')}"
        
        images = details.get('images', [])
        main_image_link = images[0].get('url') if images else ''
        material = template.get('material_info', '')
        product_type = ", ".join(tags[:3]) if tags else template_category

        for variant in details.get('variants', []):
            variant_id = variant.get('id')
            attributes = variant.get('attributes', {})
            
            color = attributes.get('color', attributes.get('Color', '')) if classification['is_apparel'] else ''
            size = attributes.get('size', attributes.get('Size', '')) if classification['is_apparel'] else ''

            price_info = variant.get('price', {})
            price_str = f"{price_info.get('value', 0)} {price_info.get('currency', 'USD')}"
            full_title = f"{title} - {variant.get('name', '')}" if variant.get('name', '') else title

            # Crear nodo XML
            item_xml = f"""
        <item>
            <g:id>{escape(variant_id)}</g:id>
            <g:item_group_id>{escape(product_id)}</g:item_group_id>
            <g:title>{escape(full_title[:150])}</g:title>
            <g:description>{escape(description[:500])}</g:description>
            <g:link>{escape(f"{product_link}?variant={variant_id}")}</g:link>
            <g:image_link>{escape(main_image_link)}</g:image_link>
            <g:price>{escape(price_str)}</g:price>
            <g:availability>in stock</g:availability>
            <g:condition>new</g:condition>
            <g:google_product_category>{escape(classification['gpc'])}</g:google_product_category>
            <g:product_type>{escape(product_type)}</g:product_type>"""
            
            if color: item_xml += f"\n            <g:color>{escape(color)}</g:color>"
            if size: item_xml += f"\n            <g:size>{escape(size)}</g:size>"
            if classification['gender']: item_xml += f"\n            <g:gender>{classification['gender']}</g:gender>"
            if classification['age_group']: item_xml += f"\n            <g:age_group>{classification['age_group']}</g:age_group>"
            if material: item_xml += f"\n            <g:material>{escape(material)}</g:material>"
            if tags: item_xml += f"\n            <g:custom_label_0>{escape(tags[0])}</g:custom_label_0>"
            
            item_xml += "\n        </item>"
            xml_items.append(item_xml)
            
        time.sleep(0.05)

    final_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
    <channel>
        <title>Mi Tienda Fourthwall</title>
        <link>{STORE_URL}</link>
        <description>Catálogo oficial de productos para Pinterest</description>
        {''.join(xml_items)}
    </channel>
</rss>"""

    with open('pinterest_feed.xml', 'w', encoding='utf-8') as f:
        f.write(final_xml)
    print("✅ Feed XML generado exitosamente.")

if __name__ == "__main__":
    if not API_USER or not API_PASS:
        print("❌ Error: Faltan las credenciales FOURTHWALL_API_USER y/o FOURTHWALL_API_PASS.")
    else:
        build_xml_feed()
