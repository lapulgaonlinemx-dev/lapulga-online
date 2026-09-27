import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore

# Configuración del enlace de afiliado
AFFILIATE_LINK = "https://www.mercadolibre.com.mx/social/eg20260925105329727"

# Sesión con encabezados optimizados para evitar bloqueos
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9",
    "Connection": "keep-alive"
})

def init_firebase():
    """Inicializa la conexión a Firebase desde las variables secretas"""
    if os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
    elif "FIREBASE_CREDENTIALS" in os.environ:
        cred_dict = json.loads(os.environ["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(cred_dict)
    else:
        raise Exception("No se encontraron las credenciales de Firebase.")
    
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

def fetch_category_deals(category_id, category_name, total_needed=100):
    """Obtiene productos directamente por ID de categoría de Mercado Libre MLM"""
    deals = []
    
    # En lugar de buscar por palabras de texto (que da 403), consultamos directo la categoría MLM
    # Categorías MLM: MLM1051 (Tech/Electrónica), MLM1144 (Gaming/Consolas), MLM1430 (Moda), MLM1246 (Belleza)
    for offset in [0, 50]:
        url = f"https://api.mercadolibre.com/sites/MLM/search?category={category_id}&limit=50&offset={offset}&sort=relevance"
        
        try:
            response = session.get(url, timeout=12)
            
            if response.status_code != 200:
                print(f"⚠️ Reintentando búsqueda alternativa para {category_name} (offset {offset}). Status: {response.status_code}")
                # Fallback en caso de que falle la búsqueda directa por ID
                url = f"https://api.mercadolibre.com/sites/MLM/search?q={category_name.lower()}&limit=50&offset={offset}"
                response = session.get(url, timeout=12)

            if response.status_code == 200:
                results = response.json().get("results", [])
                for item in results:
                    price = item.get("price", 0)
                    original_price = item.get("original_price") or (price * 1.25)
                    
                    if price > 0:
                        thumbnail = item.get("thumbnail", "").replace("I.jpg", "O.jpg")
                        deals.append({
                            "title": item.get("title", "Oferta Destacada"),
                            "store": "Mercado Libre",
                            "category": category_name,
                            "price": float(price),
                            "oldPrice": float(original_price if original_price > price else price * 1.2),
                            "image": thumbnail,
                            "link": AFFILIATE_LINK,
                            "active": True,
                            "ml_id": item.get("id")
                        })
            else:
                print(f"❌ Error final {response.status_code} en {category_name}")
                
        except Exception as e:
            print(f"❌ Excepción en consulta {category_name}: {e}")
            
    return deals[:total_needed]

def fetch_all_balanced_deals():
    """Junta 400 ofertas usando IDs de categoría oficiales de Mercado Libre México"""
    all_deals = []
    
    # IDs de categorías oficiales en Mercado Libre México (MLM):
    # MLM1051 = Celulares y Telefonía / Tecnología
    # MLM1144 = Consolas y Videojuegos / Gaming
    # MLM1430 = Ropa y Accesorios / Moda
    # MLM1246 = Belleza y Cuidado Personal / Belleza
    categories_queries = [
        {"cat_id": "MLM1051", "category": "Tech"},
        {"cat_id": "MLM1144", "category": "Gaming"},
        {"cat_id": "MLM1430", "category": "Moda"},
        {"cat_id": "MLM1246", "category": "Belleza"}
    ]
    
    for item in categories_queries:
        print(f"📦 Obteniendo 100 productos para la categoría: {item['category']}...")
        category_deals = fetch_category_deals(item["cat_id"], item["category"], total_needed=100)
        all_deals.extend(category_deals)
        print(f"✔️ Obtenidos {len(category_deals)} de {item['category']}.")
        
    return all_deals

def sync_to_firestore(db, deals):
    """Limpia la base de datos y guarda las ofertas obtenidas"""
    products_ref = db.collection("products")
    
    # 1. Limpiar catálogo anterior
    docs = products_ref.stream()
    for doc in docs:
        doc.reference.delete()
    print("🧹 Base de datos limpiada para actualizar catálogo.")

    # 2. Insertar los productos nuevos
    count = 0
    for deal in deals:
        products_ref.add(deal)
        count += 1
        print(f"✅ [{count}/{len(deals)}] Agregado ({deal['category']}): {deal['title'][:35]}... - ${deal['price']} MXN")

if __name__ == "__main__":
    db = init_firebase()
    print("🔎 Iniciando búsqueda de ofertas más vendidas...")
    deals = fetch_all_balanced_deals()
    if deals:
        print(f"🔥 Se obtuvieron {len(deals)} ofertas en total. Sincronizando con Firebase...")
        sync_to_firestore(db, deals)
        print("🚀 ¡Sincronización completada con éxito!")
    else:
        print("❌ No se encontraron datos en la búsqueda. Revisa la conectividad.")
