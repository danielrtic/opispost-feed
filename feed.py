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

# Autenticación con Usuario y Contraseña (La que nunca falla aquí)
session.auth = (API_USER, API_PASS)
session.headers.update({
    'Content-Type': 'application/json',
    'Accept': 'application/json'
})

# ==========================================
# DICCIONARIO DE CATEGORÍAS GOOGLE
# ==========================================
CATEGORIAS = {
    "apparel": {"gpc": "Apparel & Accessories > Clothing", "is_apparel": True},
    "drinkware": {"gpc": "Home & Garden > Kitchen & Dining > Tableware > Drinkware", "is_apparel": False},
    "art": {"gpc": "Home & Garden > Decor > Artwork", "is_apparel": False},
    "stationery": {"gpc": "Office Supplies", "is_apparel": False}
}

CATEGORIA_DEFAULT = {"gpc": "Apparel & Accessories", "is_apparel": True}

def safe_escape(val):
    if not val: return ""
    if isinstance(val, dict): val = val.get('name', val.get('value', str(val)))
    elif isinstance(val, list): val = ", ".join(str(v) for v in val)
    return escape(str(val))

def extract_price(price_info):
    if isinstance(price_info, dict):
        val = price_info.get('value', price_info.get('amount', '0.00'))
        curr = price_info.get('currency', price_info.get('currencyCode', 'USD'))
        return f"{val} {curr}"
    return "0.00 USD"

def get_all_products_summary():
    products = []
    page = 1
    total_pages = 1
    print("📦 Conectando a Open API con Usuario/Contraseña...")
    
    while page <= total_pages:
        url = f"{BASE_API_URL}/products?page={page}&limit=50"
        response = session.get(url)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('results', data.get('data', []))
            products.extend(items)
            pagination = data.get('pagination', {})
            total_pages = data.get('totalPages', pagination.get('total_pages', 1))
            page += 1
        else:
            print(f"❌ Error API: {response.status_code} - {response.text}")
            break
            
    return products

def get_product_details(product_id):
    url = f"{BASE_API_URL}/products/{product_id}"
    response = session.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('data', data)
    return None

def clasificar_por_fisica(detailed_product):
    """Clasifica empíricamente leyendo los atributos reales de las variantes."""
    variants = detailed_product.get('variants', [])
    for variant in variants:
        attrs = variant.get('attributes', {})
        for attr_key, attr_val in attrs.items():
            val_str = str(attr_val).lower()
            
            # Si se mide en onzas, es una taza/vaso
            if 'oz' in val_str: 
                return CATEGORIAS["drinkware"], "Capacidad (oz)"
                
            # Si usa tallaje estándar, es ropa
            if val_str in ['xs', 's', 'm', 'l', 'xl', '2xl', '3xl', '4xl']: 
                return CATEGORIAS["apparel"], "Tallaje textil"
                
            # Si tiene medidas multiplicadas, es un póster/cuadro
            if 'x' in val_str and ('"' in val_str or 'cm' in val_str or 'inch' in val_str): 
                return CATEGORIAS["art"], "Medidas (cm/inch)"

    return None, None

def build_xml_feed():
    summary_products = get_all_products_summary()
    if not summary_products:
        print("⚠️ No se encontraron productos.")
        return

    xml_items = []
    print(f"🔍 Procesando {len(summary_products)} productos...")

    for summary in summary_products:
        product_id = summary.get('id')
        title = summary.get('name', 'Producto sin nombre')
        slug = summary.get('slug', '')
        
        detailed_product = get_product_details(product_id)
        if not detailed_product: 
            detailed_product = summary
            
        # Intentamos clasificar por las propiedades físicas irrefutables
        classification, razon = clasificar_por_fisica(detailed_product)
        
        if classification:
            print(f"✔️ [{title[:30]}...] -> Identificado por {razon} -> {classification['gpc'].split('>')[-1].strip()}")
        else:
            classification = CATEGORIA_DEFAULT
            print(f"⚠️ [{title[:30]}...] -> Sin atributos físicos claros. Asignado a Ropa por defecto.")

        raw_description = detailed_product.get('description', '')
        clean_description = raw_description.replace('<p>', '').replace('</p>', '').replace('<br>', ' ').strip()
        if not clean_description: clean_description = title
        product_link = f"{STORE_URL}/products/{slug}"

        raw_images = detailed_product.get('images', [])
        all_image_urls = []
        for img in raw_images:
            img_url = img.get('url', img.get('transformedUrl', '')) if isinstance(img, dict) else img if isinstance(img, str) else ""
            if img_url and img_url not in all_image_urls:
                all_image_urls.append(img_url)

        main_image_link = all_image_urls[0] if all_image_urls else ""
        additional_images = all_image_urls[1:11] 

        image_tags_xml = f"\n            <g:image_link>{safe_escape(main_image_link)}</g:image_link>"
        for add_img in additional_images:
            image_tags_xml += f"\n            <g:additional_image_link>{safe_escape(add_img)}</g:additional_image_link>"

        base_price_str = extract_price(detailed_product.get('price', summary.get('price')))
        variants = detailed_product.get('variants', summary.get('variants', []))

        if not variants:
            item_xml = f"""
        <item>
            <g:id>{safe_escape(product_id)}</g:id>
            <g:item_group_id>{safe_escape(product_id)}</g:item_group_id>
            <g:title>{safe_escape(title[:150])}</g:title>
            <g:description>{safe_escape(clean_description[:500])}</g:description>
            <g:link>{safe_escape(product_link)}</g:link>{image_tags_xml}
            <g:price>{safe_escape(base_price_str)}</g:price>
            <g:availability>in stock</g:availability>
            <g:condition>new</g:condition>
            <g:google_product_category>{safe_escape(classification['gpc'])}</g:google_product_category>"""
            
            if classification['is_apparel']:
                item_xml += f"\n            <g:gender>unisex</g:gender>\n            <g:age_group>adult</g:age_group>"
            item_xml += "\n        </item>"
            xml_items.append(item_xml)
        else:
            for variant in variants:
                variant_id = variant.get('id', product_id)
                v_name = variant.get('name', '')
                full_title = f"{title} - {v_name}" if v_name else title
                
                variant_price_str = extract_price(variant.get('price'))
                if variant_price_str == "0.00 USD": variant_price_str = base_price_str
                
                attributes = variant.get('attributes', {})
                color = attributes.get('color', attributes.get('Color', ''))
                size = attributes.get('size', attributes.get('Size', ''))

                item_xml = f"""
        <item>
            <g:id>{safe_escape(variant_id)}</g:id>
            <g:item_group_id>{safe_escape(product_id)}</g:item_group_id>
            <g:title>{safe_escape(full_title[:150])}</g:title>
            <g:description>{safe_escape(clean_description[:500])}</g:description>
            <g:link>{safe_escape(f"{product_link}?variant={variant_id}")}</g:link>{image_tags_xml}
            <g:price>{safe_escape(variant_price_str)}</g:price>
            <g:availability>in stock</g:availability>
            <g:condition>new</g:condition>
            <g:google_product_category>{safe_escape(classification['gpc'])}</g:google_product_category>"""
                
                if color: item_xml += f"\n            <g:color>{safe_escape(color)}</g:color>"
                if size: item_xml += f"\n            <g:size>{safe_escape(size)}</g:size>"
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
        print("❌ Error: Faltan las credenciales FOURTHWALL_API_USER y/o FOURTHWALL_API_PASS.")
    else:
        build_xml_feed()
