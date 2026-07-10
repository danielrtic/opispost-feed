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
session.auth = (API_USER, API_PASS)[cite: 2]
session.headers.update({
    'Content-Type': 'application/json',
    'Accept': 'application/json'
})

CATEGORIAS = {
    "apparel": {"gpc": "Apparel & Accessories > Clothing", "is_apparel": True},
    "drinkware": {"gpc": "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs", "is_apparel": False},
    "art": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "is_apparel": False},
    "stationery": {"gpc": "Office Supplies > Office Instruments > Notebooks & Notepads", "is_apparel": False},
    "sticker": {"gpc": "Arts & Entertainment > Hobbies & Creative Arts > Arts & Crafts > Art & Crafting Materials > Embellishments & Trims > Stickers", "is_apparel": False},
    "accessories": {"gpc": "Electronics > Electronics Accessories > Computer Components > Computer Accessories > Laptop Accessories > Laptop Cases", "is_apparel": False}
}

CATEGORIA_DEFAULT = {"gpc": "Apparel & Accessories", "is_apparel": True}

def safe_escape(val):
    if not val: return ""
    if isinstance(val, dict): val = val.get('name', val.get('value', str(val)))
    elif isinstance(val, list): val = ", ".join(str(v) for v in val)
    return escape(str(val))

def clean_title_text(text):
    if not text: return ""
    cleaned = text.replace("Copy of ", "").replace("Copy of", "")
    return cleaned.strip()

def extract_availability(product_state, variant_stock):
    if isinstance(product_state, dict) and product_state.get('type') == 'SOLD_OUT':[cite: 1]
        return 'out of stock'
    if isinstance(variant_stock, dict):
        stock_type = variant_stock.get('type')[cite: 1]
        if stock_type == 'UNLIMITED': return 'in stock'[cite: 1]
        if stock_type == 'LIMITED':[cite: 1]
            return 'in stock' if variant_stock.get('inStock', 0) > 0 else 'out of stock'[cite: 1]
    return 'in stock'

def extract_price(data_dict):
    if not data_dict or not isinstance(data_dict, dict): return "0.00 USD"
    price_obj = data_dict.get('unitPrice') or data_dict.get('price')[cite: 1]
    if isinstance(price_obj, dict):
        val = price_obj.get('value', price_obj.get('amount', '0.00'))[cite: 1]
        curr = price_obj.get('currency', price_obj.get('currencyCode', 'USD'))[cite: 1]
        return f"{val} {curr}"
    return "0.00 USD"

def clasificar_producto(variant, title):
    t = title.lower()
    if any(w in t for w in ['sticker', 'pegatina']): return CATEGORIAS["sticker"], "Título (Sticker)"
    if any(w in t for w in ['taza', 'mug', 'vaso']): return CATEGORIAS["drinkware"], "Título (Taza/Mug)"
    if any(w in t for w in ['libreta', 'notebook', 'cuaderno']): return CATEGORIAS["stationery"], "Título (Libreta)"
    if any(w in t for w in ['funda', 'case', 'sleeve', 'fundas para portátil']): return CATEGORIAS["accessories"], "Título (Accesorio)"
    if any(w in t for w in ['poster', 'print', 'lienzo', 'cuadro', 'canvas']): return CATEGORIAS["art"], "Título (Arte)"
    if any(w in t for w in ['camiseta', 'shirt', 'hoodie', 'sudadera', 'gorra', 'ropa']): return CATEGORIAS["apparel"], "Título (Ropa)"

    attrs = variant.get('attributes', {})[cite: 1]
    size_obj = attrs.get('size', {})[cite: 1]
    size_name = str(size_obj.get('name', '')).lower().strip() if isinstance(size_obj, dict) else str(size_obj).lower().strip()[cite: 1]
            
    if size_name:
        if 'oz' in size_name or 'onza' in size_name: return CATEGORIAS["drinkware"], f"Atributo Talla ({size_name})"
        if size_name in ['xs', 's', 'm', 'l', 'xl', 'xxl', '2xl', '3xl', '4xl', '5xl', 'small', 'medium', 'large']: return CATEGORIAS["apparel"], f"Atributo Talla ({size_name})"
        if 'x' in size_name and any(m in size_name for m in ['"', 'cm', 'in', 'mm']): return CATEGORIAS["art"], f"Atributo Medida ({size_name})"

    return CATEGORIA_DEFAULT, "Valor por Defecto"

def get_all_products_summary():
    products = []
    page = 0 
    total_pages = 1
    print("📦 Conectando a Open API y descargando catálogo completo...")
    
    while page < total_pages:
        url = f"{BASE_API_URL}/products?page={page}&size=50"[cite: 2]
        print(f"-> Descargando página {page}...")
        
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            items = data.get('results', [])[cite: 2]
            if not items: break
            products.extend(items)
            total_pages = data.get('totalPages', 1)[cite: 2]
            page += 1
        else:
            print(f"❌ Error API listando productos: {response.status_code}")
            break
    return products

def build_xml_feed():
    summary_products = get_all_products_summary()
    if not summary_products:
        print("⚠️ No se encontraron productos.")
        return

    xml_items = []
    print(f"\n🔍 Procesando {len(summary_products)} productos base...")

    for summary in summary_products:
        product_id = summary.get('id')[cite: 1]
        raw_title = summary.get('name', 'Producto sin nombre')[cite: 1]
        title = clean_title_text(raw_title)
        slug = summary.get('slug', '')[cite: 1]
        
        url_detail = f"{BASE_API_URL}/products/{product_id}"[cite: 2]
        resp_detail = session.get(url_detail)
        detailed_product = resp_detail.json() if resp_detail.status_code == 200 else summary

        # ---------------------------------------------------------
        # >>> NUEVOS FILTROS DE SEGURIDAD <<<
        # ---------------------------------------------------------
        
        # 1. Verificar el acceso (ignorar HIDDEN, PRIVATE, ARCHIVED)
        access_info = detailed_product.get('access', {})[cite: 1]
        access_type = access_info.get('type', 'PUBLIC') if isinstance(access_info, dict) else 'PUBLIC'[cite: 1]
        
        if access_type != 'PUBLIC':
            print(f"🚫 Omitiendo [{title[:30]}...] -> No es público ({access_type})")
            continue

        raw_images = detailed_product.get('images', [])[cite: 1]
        all_image_urls = []
        for img in raw_images:
            img_url = img.get('url', '') if isinstance(img, dict) else img if isinstance(img, str) else ""[cite: 1]
            if img_url and img_url not in all_image_urls: all_image_urls.append(img_url)

        # 2. Verificar que el producto tenga al menos una imagen
        if not all_image_urls:
            print(f"🚫 Omitiendo [{title[:30]}...] -> Sin imágenes (Borrador/Error)")
            continue
            
        # ---------------------------------------------------------

        raw_description = detailed_product.get('description', '')[cite: 1]
        clean_description = raw_description.replace('<p>', '').replace('</p>', '').replace('<br>', ' ').strip()
        if not clean_description: clean_description = title
        product_link = f"{STORE_URL}/products/{slug}"
        
        product_state = detailed_product.get('state', {})[cite: 1]
        variants = detailed_product.get('variants', [])[cite: 1]
        base_price_str = extract_price(detailed_product)

        if not variants:
            classification, razon = clasificar_producto({}, title)
            main_image_link = all_image_urls[0] if all_image_urls else ""
            
            item_xml = f"""
        <item>
            <g:id>{safe_escape(product_id)}</g:id>
            <g:item_group_id>{safe_escape(product_id)}</g:item_group_id>
            <g:title>{safe_escape(title[:150])}</g:title>
            <g:description>{safe_escape(clean_description[:500])}</g:description>
            <g:link>{safe_escape(product_link)}</g:link>
            <g:image_link>{safe_escape(main_image_link)}</g:image_link>"""
            
            for add_img in all_image_urls[1:11]:
                item_xml += f"\n            <g:additional_image_link>{safe_escape(add_img)}</g:additional_image_link>"

            item_xml += f"""
            <g:price>{safe_escape(base_price_str)}</g:price>
            <g:availability>{extract_availability(product_state, {})}</g:availability>
            <g:condition>new</g:condition>
            <g:brand>Opispot</g:brand>
            <g:google_product_category>{safe_escape(classification['gpc'])}</g:google_product_category>"""
            
            if classification['is_apparel']:
                item_xml += f"\n            <g:gender>unisex</g:gender>\n            <g:age_group>adult</g:age_group>"
            item_xml += "\n        </item>"
            xml_items.append(item_xml)
            print(f"✔️ [{title[:35]}...] -> Procesado correctamente")
        else:
            for variant in variants:
                variant_id = variant.get('id', product_id)[cite: 1]
                raw_v_name = variant.get('name', '')[cite: 1]
                v_name = clean_title_text(raw_v_name)
                
                full_title = f"{title} - {v_name}" if v_name else title
                
                classification, razon = clasificar_producto(variant, title)
                
                variant_price_str = extract_price(variant)
                if variant_price_str == "0.00 USD": variant_price_str = base_price_str
                
                availability = extract_availability(product_state, variant.get('stock'))[cite: 1]
                
                attributes = variant.get('attributes', {})[cite: 1]
                color_name = ""
                color_obj = attributes.get('color')[cite: 1]
                if isinstance(color_obj, dict): color_name = color_obj.get('name', '')[cite: 1]
                
                size_name = ""
                size_obj = attributes.get('size')[cite: 1]
                if isinstance(size_obj, dict): size_name = size_obj.get('name', '')[cite: 1]

                sku = variant.get('sku', '')[cite: 1]
                weight = variant.get('weight', {})[cite: 1]
                weight_str = f"{weight.get('value')} {weight.get('unit', 'g')}" if isinstance(weight, dict) and weight.get('value') else ""[cite: 1]

                var_thumb = variant.get('thumbnailImage', {})[cite: 1]
                main_image_link = var_thumb.get('url') if isinstance(var_thumb, dict) and var_thumb.get('url') else (all_image_urls[0] if all_image_urls else "")[cite: 1]

                item_xml = f"""
        <item>
            <g:id>{safe_escape(variant_id)}</g:id>
            <g:item_group_id>{safe_escape(product_id)}</g:item_group_id>
            <g:title>{safe_escape(full_title[:150])}</g:title>
            <g:description>{safe_escape(clean_description[:500])}</g:description>
            <g:link>{safe_escape(f"{product_link}?variant={variant_id}")}</g:link>
            <g:image_link>{safe_escape(main_image_link)}</g:image_link>"""
                
                for add_img in all_image_urls[1:11]:
                    if add_img != main_image_link: 
                        item_xml += f"\n            <g:additional_image_link>{safe_escape(add_img)}</g:additional_image_link>"

                item_xml += f"""
            <g:price>{safe_escape(variant_price_str)}</g:price>
            <g:availability>{availability}</g:availability>
            <g:condition>new</g:condition>
            <g:brand>Opispot</g:brand>
            <g:google_product_category>{safe_escape(classification['gpc'])}</g:google_product_category>"""
                
                if color_name: item_xml += f"\n            <g:color>{safe_escape(color_name)}</g:color>"
                if size_name: item_xml += f"\n            <g:size>{safe_escape(size_name)}</g:size>"
                if sku: item_xml += f"\n            <g:mpn>{safe_escape(sku)}</g:mpn>"
                if weight_str: item_xml += f"\n            <g:shipping_weight>{safe_escape(weight_str)}</g:shipping_weight>"
                
                if classification['is_apparel']:
                    item_xml += f"\n            <g:gender>unisex</g:gender>\n            <g:age_group>adult</g:age_group>"
                item_xml += "\n        </item>"
                xml_items.append(item_xml)
            print(f"✔️ [{title[:35]}...] -> Procesado correctamente")
            
        time.sleep(0.05)

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
