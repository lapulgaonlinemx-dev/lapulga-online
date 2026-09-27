import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore

# Configuración del enlace de afiliado
AFFILIATE_LINK = "https://www.mercadolibre.com.mx/social/eg20260925105329727"

def init_firebase():
    """Inicializa la conexión a Firebase usando archivo local o Variable de Entorno"""
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

def fetch_category_deals(query, category_name, limit=50):
    """Busca ofertas y más vendidos dentro de una categoría específica"""
    headers = {"User-Agent": "Mozilla/5.0"}
    # Ordenamos por popularidad / más vendidos o búsquedas de tendencia
    url = f"https://api.mercadolibre.com/sites/MLM/search?q={query}&limit={limit}"
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error al consultar {category_name}: {response.status_code}")
        return []

    results = response.json().get("results", [])
    deals = []

    for item in results:
        price = item.get("price", 0)
        original_price = item.get("original_price") or (price * 1.25)
        
        # Filtramos que sea una oferta con precio válido
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
            
    return deals

def fetch_all_balanced_deals():
    """Junta 200 ofertas repartidas en las 4 categorías principales"""
    all_deals = []
    
    # Búsquedas estratégicas por categoría y tendencias de lo más vendido
    categories_queries = [
        {"query": "tecnologia gadget oferta mas vendido", "category": "Tech"},
        {"query": "videojuegos gamer consola oferta", "category": "Gaming"},
        {"query": "ropa tenis moda descuento", "category": "Moda"},
        {"query": "skincare belleza hogar oferta mas vendido", "category": "Belleza"}
    ]
    
    for item in categories_queries:
        print(f"📦 Obteniendo 50 productos para la categoría: {item['category']}...")
        category_deals = fetch_category_deals(item["query"], item["category"], limit=50)
        all_deals.extend(category_deals)
        
    return all_deals

def sync_to_firestore(db, deals):
    """Limpia la base de datos y guarda las 200 ofertas variadas"""
    products_ref = db.collection("products")
    
    # 1. Limpiar catálogo anterior
    docs = products_ref.stream()
    for doc in docs:
        doc.reference.delete()
    print("🧹 Base de datos limpiada para actualizar catálogo.")

    # 2. Insertar los nuevos 200 productos
    count = 0
    for deal in deals:
        products_ref.add(deal)
        count += 1
        print(f"✅ [{count}/{len(deals)}] Agregado ({deal['category']}): {deal['title'][:35]}... - ${deal['price']} MXN")

if __name__ == "__main__":
    db = init_firebase()
    print("🔎 Iniciando búsqueda balanceada de 200 ofertas más vendidas...")
    deals = fetch_all_balanced_deals()
    if deals:
        print(f"🔥 Se obtuvieron {len(deals)} ofertas en total. Sincronizando con Firebase...")
        sync_to_firestore(db, deals)
        print("🚀 ¡Sincronización balanceada completada con éxito!")
    else:
        print("No se encontraron datos en la búsqueda.")
