import requests
import time
import os
from xml.sax.saxutils import escape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# CONFIGURACIÓN
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
# DICCIONARIO ESTRICTO DE CLASIFICACIÓN
# ==========================================
# Mapea los tipos de plantilla/etiquetas internas de Fourthwall a Google Product Categories
CATEGORIAS_FOURTHWALL = {
    # ROPA (is_apparel: True)
    "shirt": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "is_apparel": True},
    "t-shirt": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "is_apparel": True},
    "hoodie": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "is_apparel": True},
    "sweatshirt": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "is_apparel": True},
    "tank top": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "is_apparel": True},
    
    # HOGAR Y ACCESORIOS (is_apparel: False)
    "mug": {"gpc": "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs", "is_apparel": False},
    "sticker": {"gpc": "Arts & Entertainment > Hobbies & Creative Arts > Arts & Crafts > Art & Crafting Materials > Embellishments & Trims > Stickers", "is_apparel": False},
    "notebook": {"gpc": "Office Supplies > Office Instruments > Notebooks & Notepads", "is_apparel": False},
    "journal": {"gpc": "Office Supplies > Office Instruments > Notebooks & Notepads", "is_apparel": False},
    "laptop sleeve": {"gpc": "Electronics > Electronics Accessories > Computer Components > Computer Accessories > Laptop Accessories > Laptop Cases", "is_apparel": False},
    "poster": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "is_apparel": False},
    "print": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "is_apparel": False},
    "canvas": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "is_apparel": False}
}

# Categoría por defecto de seguridad si Fourthwall crea un producto totalmente nuevo que no esté en el diccionario
CATEGORIA_DEFAULT = {"gpc": "Apparel & Accessories", "is_apparel": True} 

def safe_escape(val):
    if not val: return ""
    if isinstance(val, dict): val = val.get('name', val.get('value', str(val)))
    elif isinstance(val, list): val = ", ".join(str(v) for v in val)
    return escape(str(val))

def extract_price(data_dict):
    price_obj = data_dict.get('price') or data_dict.get('unitPrice') or data_dict.get('retailPrice')
    if isinstance(price_obj, dict):
        val = price_obj.get('value', price_obj.get('amount', '0.00'))
        curr = price_obj.get('currency', price_obj.get('currencyCode', 'USD'))
        return f"{val} {curr}"
    elif isinstance(price_obj, (int, float, str)) and price_obj:
        return f"{price_obj} USD"
    return "0.00 USD"

def get_all_products():
    products = []
    page = 1
    total_pages = 1
    print("📦 Obteniendo catálogo completo...")
    
    while page <= total_pages:
        url = f"{BASE_API_URL}/products?page={page}&limit=50"
        response = session.get(url)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('results', [])
            products.extend(items)
            total_pages = data.get('totalPages', 1)
            page += 1
        else:
            print(f"❌ Error API: {response.status_code}")
            break
            
    print(f"✅ Total de productos en la tienda: {len(products)}")
    return products

def get_exact_classification(product):
    """
    Clasifica el producto leyendo estrictamente los datos de la plataforma, NO el título.
    """
    # 1. Buscamos el tipo de producto oficial en los metadatos de Fourthwall
    fw_type = product.get('productType', '').lower()
    
    # 2. Si no está en 'productType', buscamos en las etiquetas (tags) oficiales
    tags = [tag.lower() for tag in product.get('tags', [])]
    
    # Buscamos coincidencias exactas en nuestro diccionario
    for key, data in CATEGORIAS_FOURTHWALL.items():
        # Verificamos el tipo de producto oficial
        if key in fw_type:
            return data
        # O verificamos los tags (Fourthwall suele etiquetar las plantillas, ej: "Mug")
        if any(key in tag for tag in tags):
            return data

    # Si no se encuentra en el diccionario, aplicamos el default
    return CATEGORIA_DEFAULT

def build_xml_feed():
    products = get_all_products()
    if not products:
        print("⚠️ No se encontraron productos.")
        return

    xml_items = []

    for product in products:
        product_id = product.get('id')
        title = product.get('name', 'Producto sin nombre')
        slug = product.get('slug', '')
        
        raw_description = product.get('description', '')
        clean_description = raw_description.replace('<p>', '').replace('</p>', '').replace('<br>', ' ').strip()
        if not clean_description: clean_description = title

        product_link = f"{STORE_URL}/products/{slug}"
        
        # <<< LLAMADA AL NUEVO MOTOR ESTRICTO >>>
        classification = get_exact_classification(product)

        raw_images = product.get('images', [])
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

        base_price_str = extract_price(product)
        variants = product.get('variants', [])

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
                item_xml += f"\n            <g:gender>unisex</g:gender>"
                item_xml += f"\n            <g:age_group>adult</g:age_group>"
                
            item_xml += "\n        </item>"
            xml_items.append(item_xml)
        else:
            for variant in variants:
                variant_id = variant.get('id', product_id)
                v_name = variant.get('name', '')
                full_title = f"{title} - {v_name}" if v_name else title
                
                variant_price_str = extract_price(variant)
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
                    item_xml += f"\n            <g:gender>unisex</g:gender>"
                    item_xml += f"\n            <g:age_group>adult</g:age_group>"
                    
                item_xml += "\n        </item>"
                xml_items.append(item_xml)

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
